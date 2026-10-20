"""Warning attribution across the sync bridge (#300).

A warning emitted on the event-loop thread must resolve to the caller's
file and line, and must not trip importlib's loader warning on newer
interpreters when the caller is a ``__main__`` script.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import warnings
from pathlib import Path

from toolregistry._async_runtime import AsyncRuntime
from toolregistry.utils import ToolNameFilter


async def _emit_filter_warning() -> None:
    ToolNameFilter(include=["nope"]).warn_if_all_filtered_out(
        total=1, accepted=0, source="MCP"
    )


def test_sync_bridge_passes_registry_not_module_globals(monkeypatch) -> None:
    """Pin the warn_explicit arguments, independent of interpreter version.

    ``module_globals`` triggers importlib's loader warning on interpreters
    where that path exists (3.11+); the local env and CI run 3.10, so spy
    on the call rather than relying on the warning being emitted.
    """
    captured: dict[str, object] = {}
    real_warn_explicit = warnings.warn_explicit

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return real_warn_explicit(*args, **kwargs)

    monkeypatch.setattr(warnings, "warn_explicit", spy)
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        AsyncRuntime.run_sync(_emit_filter_warning())

    assert "registry" in captured
    assert "module_globals" not in captured


SCRIPT = textwrap.dedent(
    """
    import warnings

    from toolregistry._async_runtime import AsyncRuntime
    from toolregistry.utils import ToolNameFilter


    async def emit() -> None:
        ToolNameFilter(include=["nope"]).warn_if_all_filtered_out(
            total=1, accepted=0, source="MCP"
        )


    # Scope the error filter to the call: unrelated third-party
    # deprecations raised at import time must not decide this test.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        try:
            AsyncRuntime.run_sync(emit())
        except UserWarning:
            print("USERWARNING")
        except DeprecationWarning as exc:
            print(f"DEPRECATION {exc}")
        else:
            print("NO-WARNING")
    """
)


def test_main_script_sync_bridge_raises_only_userwarning(tmp_path: Path) -> None:
    """A ``__main__`` caller must not get importlib's loader warning.

    Passing ``module_globals`` to ``warn_explicit`` makes importlib emit a
    ``DeprecationWarning`` for a ``__main__`` script without
    ``__spec__.loader``.  Under an error filter that warning is raised
    first, so callers catching ``UserWarning`` stop working.
    """
    script = tmp_path / "probe.py"
    script.write_text(SCRIPT, encoding="utf-8")

    env = os.environ.copy()
    src = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr
    assert "USERWARNING" in proc.stdout
    assert "DEPRECATION" not in proc.stdout

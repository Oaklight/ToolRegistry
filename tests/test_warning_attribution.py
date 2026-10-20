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
from pathlib import Path

SCRIPT = textwrap.dedent(
    """
    import warnings

    from toolregistry._async_runtime import AsyncRuntime
    from toolregistry.utils import ToolNameFilter


    async def emit() -> None:
        ToolNameFilter(include=["nope"]).warn_if_all_filtered_out(
            total=1, accepted=0, source="MCP"
        )


    try:
        AsyncRuntime.run_sync(emit())
    except UserWarning:
        print("USERWARNING")
    else:
        print("NO-WARNING")
    """
)


def test_main_script_under_w_error_raises_userwarning_only(tmp_path: Path) -> None:
    """``python -W error script.py`` must see the intended category.

    Passing ``module_globals`` to ``warn_explicit`` makes importlib emit a
    ``DeprecationWarning`` for a ``__main__`` script without
    ``__spec__.loader``.  Under ``-W error`` that warning is raised first,
    so callers catching ``UserWarning`` stop working.
    """
    script = tmp_path / "probe.py"
    script.write_text(SCRIPT, encoding="utf-8")

    env = os.environ.copy()
    src = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.run(
        [sys.executable, "-W", "error", str(script)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stderr
    assert "USERWARNING" in proc.stdout
    assert "DeprecationWarning" not in proc.stderr

"""Smoke tests for the runtimes.BashTool integration (bashtool submodule)."""

import pytest

from toolregistry.runtimes import BashTool
from toolregistry.runtimes._bashtool import truncate, validate_command


class TestBashToolImport:
    """Verify that BashTool is importable from toolregistry.runtimes."""

    def test_import_bashtool(self):
        assert BashTool is not None
        assert hasattr(BashTool, "execute")

    def test_submodule_internals_accessible(self):
        """Internal utils are accessible from _bashtool but not from runtimes."""
        assert callable(validate_command)
        assert callable(truncate)


class TestBashToolExecute:
    """Basic execution tests via the runtimes re-export."""

    def test_echo(self):
        result = BashTool.execute("echo hello")
        assert result["stdout"].strip() == "hello"
        assert result["exit_code"] == 0
        assert result["timed_out"] is False

    def test_return_dict_keys(self):
        result = BashTool.execute("echo test")
        assert set(result.keys()) == {"stdout", "stderr", "exit_code", "timed_out"}

    def test_timeout(self):
        result = BashTool.execute("sleep 10", timeout=1)
        assert result["timed_out"] is True
        assert result["exit_code"] == -1


class TestValidateCommand:
    """Verify safety validation via the runtimes re-export."""

    def test_safe_command_passes(self):
        validate_command("ls -la")

    def test_dangerous_command_blocked(self):
        with pytest.raises(ValueError, match="Recursive forced deletion"):
            validate_command("rm -rf /")

    def test_sudo_blocked(self):
        with pytest.raises(ValueError, match="sudo"):
            validate_command("sudo apt update")


class TestTruncate:
    """Verify truncation via the runtimes re-export."""

    def test_short_text_unchanged(self):
        assert truncate("hello") == "hello"

    def test_long_text_truncated(self):
        long_text = "x" * 200_000
        result = truncate(long_text, max_bytes=100)
        assert len(result.encode("utf-8")) < 200_000
        assert "[output truncated]" in result

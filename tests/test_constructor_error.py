"""Tests for improved error messages when registering classes with required constructor arguments."""

import pytest

from toolregistry import ToolRegistry


# ---------------------------------------------------------------------------
# Test fixture classes
# ---------------------------------------------------------------------------


class ServiceWithRequiredArgs:
    """Class that requires constructor arguments."""

    def __init__(self, api_key: str, timeout: int):
        self.api_key = api_key
        self.timeout = timeout

    def call_api(self, endpoint: str) -> str:
        return f"{self.api_key}:{endpoint}"


class ServiceWithDefaults:
    """Class whose constructor has only default arguments."""

    def __init__(self, retries: int = 3, verbose: bool = False):
        self.retries = retries
        self.verbose = verbose

    def status(self) -> str:
        return "ok"


class ServiceNoArgs:
    """Class with a no-argument constructor."""

    def __init__(self):
        self.ready = True

    def ping(self) -> str:
        return "pong"


class ServiceWithVariadic:
    """Class whose constructor accepts *args and **kwargs only."""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def info(self) -> str:
        return "variadic"


class ServiceMixedWithVariadic:
    """Class with one required arg plus *args/**kwargs."""

    def __init__(self, name: str, *args, **kwargs):
        self.name = name
        self.args = args
        self.kwargs = kwargs

    def greet(self) -> str:
        return f"hello {self.name}"


class ServiceUnannotated:
    """Class with required args but no type annotations."""

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def connect(self) -> str:
        return f"{self.host}:{self.port}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConstructorErrorMessage:
    """Verify that registering a class with required constructor args
    produces a clear, actionable error message."""

    def test_required_args_error_mentions_params(self):
        """Error message should list parameter names and type annotations."""
        registry = ToolRegistry()
        with pytest.raises(TypeError, match=r"api_key: str.*timeout: int"):
            registry.register_from_class(ServiceWithRequiredArgs)

    def test_required_args_error_mentions_class_name(self):
        """Error message should include the class name."""
        registry = ToolRegistry()
        with pytest.raises(TypeError, match=r"ServiceWithRequiredArgs"):
            registry.register_from_class(ServiceWithRequiredArgs)

    def test_required_args_error_suggests_instantiation(self):
        """Error message should suggest calling register_from_class with an instance."""
        registry = ToolRegistry()
        with pytest.raises(TypeError, match=r"register_from_class\("):
            registry.register_from_class(ServiceWithRequiredArgs)

    def test_default_args_works(self):
        """A class whose __init__ has only default args should be instantiated fine."""
        registry = ToolRegistry()
        registry.register_from_class(ServiceWithDefaults)
        assert "status" in registry.list_tools()

    def test_no_args_works(self):
        """A class with a no-argument constructor should work."""
        registry = ToolRegistry()
        registry.register_from_class(ServiceNoArgs)
        assert "ping" in registry.list_tools()

    def test_pre_instantiated_works(self):
        """Passing an already-instantiated object should register methods."""
        registry = ToolRegistry()
        instance = ServiceWithRequiredArgs(api_key="key123", timeout=30)
        registry.register_from_class(instance)
        assert "call_api" in registry.list_tools()

    def test_variadic_only_attempts_instantiation(self):
        """A class with only *args/**kwargs should not be blocked — instantiation succeeds."""
        registry = ToolRegistry()
        registry.register_from_class(ServiceWithVariadic)
        assert "info" in registry.list_tools()

    def test_mixed_required_and_variadic_reports_required(self):
        """If there is a required arg alongside *args/**kwargs, the error
        should mention the required arg but not *args/**kwargs."""
        registry = ToolRegistry()
        with pytest.raises(TypeError, match=r"name: str"):
            registry.register_from_class(ServiceMixedWithVariadic)
        # Should NOT mention *args or **kwargs in the error
        with pytest.raises(TypeError) as exc_info:
            registry.register_from_class(ServiceMixedWithVariadic)
        assert "*args" not in str(exc_info.value)
        assert "**kwargs" not in str(exc_info.value)

    def test_unannotated_params_shown_without_type(self):
        """Parameters without annotations should be listed by name only."""
        registry = ToolRegistry()
        with pytest.raises(TypeError, match=r"host, port"):
            registry.register_from_class(ServiceUnannotated)
        # Verify no ": <empty>" or similar artifact
        with pytest.raises(TypeError) as exc_info:
            registry.register_from_class(ServiceUnannotated)
        msg = str(exc_info.value)
        assert "host" in msg
        assert "port" in msg
        # Unannotated params should appear without colon
        assert "host:" not in msg
        assert "port:" not in msg

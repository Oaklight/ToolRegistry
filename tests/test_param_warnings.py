"""Tests for parameter introspection warnings.

Verifies that warnings are emitted when:
- *args (VAR_POSITIONAL) parameters are skipped during schema generation
- **kwargs (VAR_KEYWORD) parameters are skipped during schema generation
- Parameter model generation fails entirely
"""

import warnings
from unittest.mock import patch

import pytest

from toolregistry.parameter_models import _generate_parameters_model
from toolregistry.tool import Tool


class TestVarPositionalWarning:
    """Test that *args parameters emit a warning."""

    def test_args_emits_warning(self):
        """Registering a function with *args should warn about exclusion."""

        def func_with_args(x: int, *args: str) -> str:
            return str(x)

        with pytest.warns(
            UserWarning,
            match=r"Parameter '\*args' \(\*args\) in 'func_with_args'.*excluded",
        ):
            _generate_parameters_model(func_with_args)

    def test_args_via_tool_from_function(self):
        """Tool.from_function with *args should warn about exclusion."""

        def func_with_args(x: int, *args: str) -> str:
            return str(x)

        with pytest.warns(
            UserWarning,
            match=r"Parameter '\*args' \(\*args\) in 'func_with_args'.*excluded",
        ):
            tool = Tool.from_function(func_with_args)

        # The tool should still be created successfully, with only 'x' in schema
        assert tool is not None
        assert "x" in tool.parameters.get("properties", {})

    def test_custom_args_name(self):
        """Custom *args name should appear in the warning message."""

        def func_with_custom_args(x: int, *my_args: str) -> str:
            return str(x)

        with pytest.warns(
            UserWarning,
            match=r"Parameter '\*my_args' \(\*args\) in 'func_with_custom_args'",
        ):
            _generate_parameters_model(func_with_custom_args)


class TestVarKeywordWarning:
    """Test that **kwargs parameters emit a warning."""

    def test_kwargs_emits_warning(self):
        """Registering a function with **kwargs should warn about exclusion."""

        def func_with_kwargs(x: int, **kwargs: str) -> str:
            return str(x)

        with pytest.warns(
            UserWarning,
            match=r"Parameter '\*\*kwargs' \(\*\*kwargs\) in 'func_with_kwargs'.*excluded",
        ):
            _generate_parameters_model(func_with_kwargs)

    def test_kwargs_via_tool_from_function(self):
        """Tool.from_function with **kwargs should warn about exclusion."""

        def func_with_kwargs(x: int, **kwargs: str) -> str:
            return str(x)

        with pytest.warns(
            UserWarning,
            match=r"Parameter '\*\*kwargs' \(\*\*kwargs\) in 'func_with_kwargs'.*excluded",
        ):
            tool = Tool.from_function(func_with_kwargs)

        # The tool should still be created successfully, with only 'x' in schema
        assert tool is not None
        assert "x" in tool.parameters.get("properties", {})

    def test_custom_kwargs_name(self):
        """Custom **kwargs name should appear in the warning message."""

        def func_with_custom_kwargs(x: int, **options: str) -> str:
            return str(x)

        with pytest.warns(
            UserWarning,
            match=r"Parameter '\*\*options' \(\*\*kwargs\) in 'func_with_custom_kwargs'",
        ):
            _generate_parameters_model(func_with_custom_kwargs)


class TestBothArgsAndKwargs:
    """Test that functions with both *args and **kwargs emit two warnings."""

    def test_args_and_kwargs_both_warn(self):
        """Both *args and **kwargs should each produce a warning."""

        def func_with_both(x: int, *args: str, **kwargs: str) -> str:
            return str(x)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _generate_parameters_model(func_with_both)

        user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
        assert len(user_warnings) == 2

        messages = [str(w.message) for w in user_warnings]
        assert any("*args" in m and "'*args'" in m for m in messages)
        assert any("**kwargs" in m and "'**kwargs'" in m for m in messages)


class TestParameterModelGenerationFailureWarning:
    """Test that failure in _generate_parameters_model emits a warning in from_function."""

    def test_generation_failure_emits_warning(self):
        """When _generate_parameters_model raises, from_function should warn."""

        def normal_func(x: int) -> str:
            return str(x)

        with patch(
            "toolregistry.tool._generate_parameters_model",
            side_effect=RuntimeError("mock introspection failure"),
        ):
            with pytest.warns(
                UserWarning,
                match=r"Failed to generate parameter model for 'normal_func'.*mock introspection failure",
            ):
                tool = Tool.from_function(normal_func)

        # Tool should still be created, but without parameter validation
        assert tool is not None
        assert tool.parameters_model is None
        assert tool.parameters == {}

    def test_generation_failure_warning_includes_func_name(self):
        """Warning message should include the function name."""

        def my_special_func(x: int) -> str:
            return str(x)

        with patch(
            "toolregistry.tool._generate_parameters_model",
            side_effect=ValueError("bad annotation"),
        ):
            with pytest.warns(
                UserWarning,
                match=r"'my_special_func'.*bad annotation.*without parameter validation",
            ):
                Tool.from_function(my_special_func)

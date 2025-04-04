import asyncio
import inspect
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field

from .parameter_models import _generate_parameters_model


class Tool(BaseModel):
    """
    Represents a tool (function) that can be called by the language model.
    """

    name: str = Field(description="Name of the tool")
    description: str = Field(description="Description of what the tool does")
    parameters: Dict[str, Any] = Field(description="JSON schema for tool parameters")
    callable: Callable[..., Any] = Field(exclude=True)
    is_async: bool = Field(default=False, description="Whether the tool is async")
    parameters_model: Optional[Any] = Field(
        default=None, description="Pydantic Model for tool parameters"
    )

    @classmethod
    def from_function(
        cls,
        func: Callable[..., Any],
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> "Tool":
        """Create a Tool from a function."""
        func_name = name or func.__name__

        if func_name == "<lambda>":
            raise ValueError("You must provide a name for lambda functions")

        func_doc = description or func.__doc__ or ""
        is_async = inspect.iscoroutinefunction(func)

        parameters_model = None
        try:
            parameters_model = _generate_parameters_model(func)
        except Exception:
            parameters_model = None
        parameters_schema = (
            parameters_model.model_json_schema() if parameters_model else {}
        )
        return cls(
            name=func_name,
            description=func_doc,
            parameters=parameters_schema,
            callable=func,
            is_async=is_async,
            parameters_model=parameters_model if parameters_model is not None else None,
        )

    def _validate_parameters(self, parameters):
        if self.parameters_model is None:
            validated_params = parameters
        else:
            model = self.parameters_model(**parameters)
            validated_params = model.model_dump_one_level()
        return validated_params

    def run(self, parameters: Dict[str, Any]) -> Any:
        """Run the tool with the given parameters."""
        try:
            validated_params = self._validate_parameters(parameters)
            return self.callable(**validated_params)
        except Exception as e:
            return f"Error executing {self.name}: {str(e)}"

    async def arun(self, parameters: Dict[str, Any]) -> Any:
        """Async run the tool with the given parameters."""
        try:
            validated_params = self._validate_parameters(parameters)

            if inspect.iscoroutinefunction(self.callable):
                return await self.callable(**validated_params)
            elif hasattr(self.callable, "__call__"):
                return await self.callable(**validated_params)
            raise NotImplementedError(
                "Async execution requires either an async function (coroutine) "
                "or a callable whose __call__ method is async or returns an awaitable object."
            )
        except Exception as e:
            return f"Error executing {self.name}: {str(e)}"

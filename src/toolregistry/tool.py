import inspect
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field

from toolregistry.parameter_models import _generate_parameters_model


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

    def run(self, parameters: Dict[str, Any]) -> Any:
        """Run the tool with the given parameters."""
        try:
            if self.parameters_model is None:
                # Directly call the function if no parameters model is defined
                result = self.callable(**parameters)
            else:
                # Convert parameters to model instance for validation
                model = self.parameters_model(**parameters)
                # Call the underlying function with validated parameters
                result = self.callable(**model.model_dump_one_level())
            return f"{self.name} -> {result}"
        except Exception as e:
            return f"Error executing {self.name}: {str(e)}"

    async def arun(self, parameters: Dict[str, Any]) -> Any:
        """Async run the tool with the given parameters."""
        try:
            if self.parameters_model is None:
                # Directly call the async function if no parameters model is defined
                if inspect.iscoroutinefunction(self.callable):
                    result = await self.callable(**parameters)
                elif hasattr(self.callable, "__acall__"):
                    result = await self.callable.__acall__(**parameters)
                else:
                    raise NotImplementedError(
                        "Async execution requires either __acall__ implementation "
                        "or the callable to be a coroutine function"
                    )
            else:
                # Convert parameters to model instance for validation
                model = self.parameters_model(**parameters)
                # Call the underlying async function with validated parameters
                if inspect.iscoroutinefunction(self.callable):
                    result = await self.callable(**model.model_dump_one_level())
                elif hasattr(self.callable, "__acall__"):
                    result = await self.callable.__acall__(
                        **model.model_dump_one_level()
                    )
                else:
                    raise NotImplementedError(
                        "Async execution requires either __acall__ implementation "
                        "or the callable to be a coroutine function"
                    )
            return f"{self.name} -> {result}"
        except Exception as e:
            return f"Error executing {self.name}: {str(e)}"

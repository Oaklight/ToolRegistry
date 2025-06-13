import asyncio
import atexit
import json
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

import dill
from loguru import logger

from .utils import ChatCompletionMessageToolCall  # type: ignore


class Executor:
    """Handles execution of tool calls using thread/process pools."""

    def __init__(self):
        self._process_pool = ProcessPoolExecutor()
        self._thread_pool = ThreadPoolExecutor()
        self._execution_mode: Literal["process", "thread"] = "process"
        atexit.register(self._shutdown_executors)

    @property
    def execution_mode(self) -> Literal["process", "thread"]:
        return self._execution_mode

    def _shutdown_executors(self) -> None:
        """Shuts down the executors gracefully."""
        self._process_pool.shutdown(wait=True)
        self._thread_pool.shutdown(wait=True)

    @staticmethod
    def _process_tool_call_helper(
        serialized_func: Optional[bytes],
        tool_call_id: str,
        function_name: str,
        function_args: Dict[str, Any],
    ) -> Tuple[str, str]:
        """Helper function to execute a single tool call.

        Args:
            serialized_func: Serialized callable function using dill.
            tool_call_id: Unique ID for the tool call.
            function_name: Name of the function to call.
            function_args: Dictionary of arguments to pass to the function.

        Returns:
            Tuple[str, str]: A tuple containing (tool_call_id, tool_result).
        """
        try:
            if serialized_func:
                # Deserialize the function using dill
                callable_func = dill.loads(serialized_func)

                # Check if callable_func is a coroutine function
                if asyncio.iscoroutinefunction(callable_func):
                    # Run the coroutine and get the result
                    tool_result = asyncio.run(callable_func(**function_args))
                else:
                    # Directly execute the callable with unpacked arguments
                    tool_result = callable_func(**function_args)
                # Ensure the result is JSON serializable (or handle appropriately)
                # For simplicity, converting non-JSON serializable results to string
                try:
                    json.dumps(tool_result)
                except TypeError:
                    tool_result = str(tool_result)
            else:
                tool_result = (
                    f"Error: Tool '{function_name}' not found or callable is None"
                )
        except Exception as e:
            tool_result = f"Error executing {function_name}: {str(e)}"
        return (tool_call_id, tool_result)

    @staticmethod
    def _execute_tool_calls_parallel(
        executor_pool: Union[ProcessPoolExecutor, ThreadPoolExecutor],
        tasks_to_submit: List[Tuple[Optional[bytes], str, str, Dict[str, Any]]],
    ) -> Dict[str, str]:
        """Execute tool calls in parallel using executor pool.

        Args:
            executor_pool: Process or thread pool executor.
            tasks_to_submit: List of tasks to submit to executor.

        Returns:
            Dict[str, str]: Dictionary mapping tool call IDs to results.
        """
        """Execute tool calls using concurrent.futures executors."""
        tool_responses = {}
        futures = {
            executor_pool.submit(
                Executor._process_tool_call_helper, cfunc, callid, fname, fargs
            ): callid
            for (cfunc, callid, fname, fargs) in tasks_to_submit
        }
        for future in futures:
            callid = futures[future]
            try:
                t_id, t_result = future.result()
                tool_responses[t_id] = t_result
            except Exception as e:
                tool_responses[callid] = f"Error executing tool call: {str(e)}"
        return tool_responses

    def set_execution_mode(self, mode: Literal["thread", "process"]) -> None:
        """Set the execution mode for parallel tasks.

        Args:
            mode (Literal["thread", "process"]): The desired execution mode.

        Raises:
            ValueError: If an invalid mode is provided.
        """
        if mode not in {"thread", "process"}:
            logger.error(
                "Invalid mode. Choose 'thread' or 'process'. Fall back to 'process' mode."
            )
        self._execution_mode = mode
        logger.info(f"Execution mode set to: {self.execution_mode}")

    def execute_tool_calls(
        self,
        tool_calls: List[ChatCompletionMessageToolCall],
        execution_mode: Optional[Literal["process", "thread"]] = None,
    ) -> Dict[str, str]:
        """Execute tool calls with concurrency using dill for serialization."""
        tool_responses = {}
        tasks_to_submit = []

        # Use self.execution_mode as default unless overridden by user
        execution_mode = execution_mode or self.execution_mode
        assert execution_mode in ["process", "thread"], "execution_mode must be set"

        # Prepare tasks
        for tool_call in tool_calls:
            try:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                tool_call_id = tool_call.id
                tool_obj = self.get_tool(function_name)
                callable_func = tool_obj.callable if tool_obj else None

                # Serialize the function using dill if using process pool
                serialized_func = dill.dumps(callable_func) if callable_func else None

                tasks_to_submit.append(
                    (serialized_func, tool_call_id, function_name, function_args)
                )
            except Exception as e:
                tool_responses[getattr(tool_call, "id", "unknown_id")] = (
                    f"Error preparing tool call {getattr(tool_call.function, 'name', 'unknown_name')}: {str(e)}"
                )

        if not tasks_to_submit:
            return tool_responses

        # Attempt multi-process or fallback
        if execution_mode == "process":
            try:
                tool_responses = self._execute_tool_calls_parallel(
                    self._process_pool, tasks_to_submit
                )
            except Exception as e:
                logger.error(f"Error executing tool calls in process pool: {str(e)}")
                tool_responses = self._execute_tool_calls_parallel(
                    self._thread_pool, tasks_to_submit
                )
        else:
            tool_responses = self._execute_tool_calls_parallel(
                self._thread_pool, tasks_to_submit
            )
        return tool_responses

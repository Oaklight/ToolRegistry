# Events

The events module provides the event infrastructure for the ToolRegistry callback mechanism, enabling subscribers to receive notifications when tool state changes occur.

## Overview

The callback mechanism allows external components to react to changes in the ToolRegistry, such as tool registration, enabling, or disabling. This is particularly useful for:

- **UI Updates**: Refreshing tool lists in admin panels
- **Logging**: Tracking tool lifecycle events
- **Synchronization**: Keeping external systems in sync with registry state
- **Monitoring**: Observing tool usage patterns

## ChangeEventType

An enumeration of all possible change event types that can occur in ToolRegistry.

### Values

| Value | Description |
|-------|-------------|
| `REGISTER` | A tool was registered |
| `UNREGISTER` | A tool was unregistered (reserved for future use) |
| `ENABLE` | A tool was enabled |
| `DISABLE` | A tool was disabled |
| `REFRESH` | A single tool was refreshed (reserved for future use) |
| `REFRESH_ALL` | All tools were refreshed/reloaded (reserved for future use) |
| `PERMISSION_DENIED` | A tool call was denied by the permission policy |
| `PERMISSION_ASKED` | A tool call was escalated to a permission handler |
| `METADATA_UPDATE` | A tool's metadata was updated at runtime |
| `TOOL_ERROR` | A tool execution failed with an exception |

### Example

```python
from toolregistry import ChangeEventType

# Check event type
if event.event_type == ChangeEventType.REGISTER:
    print("A new tool was registered!")
elif event.event_type == ChangeEventType.DISABLE:
    print(f"Tool disabled: {event.reason}")
elif event.event_type == ChangeEventType.PERMISSION_DENIED:
    print(f"Tool call denied: {event.tool_name}")
elif event.event_type == ChangeEventType.PERMISSION_ASKED:
    print(f"Tool call escalated: {event.tool_name}")
elif event.event_type == ChangeEventType.METADATA_UPDATE:
    print(f"Metadata updated: {event.tool_name}, fields: {event.metadata}")
elif event.event_type == ChangeEventType.TOOL_ERROR:
    print(f"Tool error: {event.tool_name}, type: {event.metadata.get('exception_type')}")
```

## ChangeEvent

An immutable dataclass representing a change event in the registry.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `event_type` | `ChangeEventType` | The type of change that occurred |
| `tool_name` | `str \| None` | Name of the affected tool, or `None` for bulk operations |
| `reason` | `str \| None` | Optional reason string, primarily used for disable events |
| `metadata` | `dict[str, Any]` | Optional additional context data (defaults to empty dict) |

### Example

```python
from toolregistry import ChangeEvent, ChangeEventType

# Events are created internally by ToolRegistry
# Here's what they look like:
event = ChangeEvent(
    event_type=ChangeEventType.REGISTER,
    tool_name="calculator.add",
)

# Access event properties
print(f"Event: {event.event_type.value}")  # "register"
print(f"Tool: {event.tool_name}")          # "calculator.add"

# Disable event with reason
disable_event = ChangeEvent(
    event_type=ChangeEventType.DISABLE,
    tool_name="risky_tool",
    reason="Security vulnerability detected",
)
```

## ChangeCallback

A type alias for callback functions that handle change events.

### Signature

```python
ChangeCallback = Callable[[ChangeEvent], None]
```

Callbacks receive a `ChangeEvent` and return nothing. They should be lightweight and not raise exceptions that need to propagate.

## API Reference

::: toolregistry.events
    options:
        show_source: false
        show_root_heading: false
        show_root_toc_entry: false
        members:
            - ChangeEventType
            - ChangeEvent
            - ChangeCallback

## Usage with ToolRegistry

### Registering Callbacks

Use `on_change()` to register a callback that will be notified of all change events:

```python
from toolregistry import ToolRegistry, ChangeEvent, ChangeEventType

registry = ToolRegistry()

def my_callback(event: ChangeEvent) -> None:
    """Handle tool registry changes."""
    print(f"[{event.event_type.value}] {event.tool_name}")
    if event.reason:
        print(f"  Reason: {event.reason}")

# Register the callback
registry.on_change(my_callback)

# Now any changes will trigger the callback
def add(a: int, b: int) -> int:
    return a + b

registry.register(add)  # Prints: [register] add
registry.disable("add", reason="Maintenance")  # Prints: [disable] add, Reason: Maintenance
registry.enable("add")  # Prints: [enable] add
```

### Removing Callbacks

Use `remove_on_change()` to unregister a callback:

```python
# Remove the callback when no longer needed
removed = registry.remove_on_change(my_callback)
print(f"Callback removed: {removed}")  # True

# Subsequent changes won't trigger the callback
registry.register(another_function)  # No output
```

### Multiple Callbacks

Multiple callbacks can be registered and will be invoked in registration order:

```python
def logger_callback(event: ChangeEvent) -> None:
    logging.info(f"Tool event: {event.event_type.value} - {event.tool_name}")

def metrics_callback(event: ChangeEvent) -> None:
    metrics.increment(f"tool.{event.event_type.value}")

registry.on_change(logger_callback)
registry.on_change(metrics_callback)

# Both callbacks will be invoked for each change
registry.register(some_tool)
```

### Error Handling

Callbacks should not raise exceptions. If a callback does raise an exception, it is logged but does not prevent other callbacks from being invoked:

```python
def faulty_callback(event: ChangeEvent) -> None:
    raise ValueError("Something went wrong!")

def reliable_callback(event: ChangeEvent) -> None:
    print(f"Event received: {event.event_type.value}")

registry.on_change(faulty_callback)
registry.on_change(reliable_callback)

# faulty_callback's exception is logged, but reliable_callback still runs
registry.register(some_tool)  # Prints: Event received: register
```

## Thread Safety

The callback mechanism is thread-safe:

- Callbacks are stored in a thread-safe manner using a lock
- Callback invocation copies the callback list to allow safe modification during iteration
- Each callback is invoked synchronously in the calling thread

## Best Practices

1. **Keep callbacks lightweight**: Heavy processing should be offloaded to a separate thread or task queue
2. **Don't raise exceptions**: Handle errors within the callback or log them
3. **Avoid blocking operations**: Use async patterns for I/O-bound work
4. **Clean up callbacks**: Remove callbacks when they're no longer needed to prevent memory leaks

```python
# Good: Lightweight callback that queues work
def async_handler(event: ChangeEvent) -> None:
    task_queue.put(event)  # Quick, non-blocking

# Bad: Heavy processing in callback
def slow_handler(event: ChangeEvent) -> None:
    time.sleep(5)  # Blocks the registry operation
    database.save(event)  # I/O in callback
```

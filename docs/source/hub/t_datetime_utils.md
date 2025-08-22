# DateTime Utilities

The `DateTime` module provides comprehensive datetime utilities for LLM tools with timezone support. It supports both IANA timezone names and UTC/GMT offset formats, making it ideal for international applications and timezone conversions.

## Features

- Get current time in ISO 8601 format with timezone support
- Convert time between different timezones
- Support for IANA timezone names (e.g., "Asia/Shanghai", "America/New_York")
- Support for UTC/GMT offset formats (e.g., "UTC+5", "GMT-3", "UTC+5:30")
- Static methods for easy integration
- Python 3.8+ compatibility with zoneinfo fallback

## Methods

### `now(timezone_name: Optional[str] = None) -> str`

Get current time in ISO 8601 format.

**Parameters:**

- `timezone_name` (optional): Timezone name (IANA format like "Asia/Shanghai" or offset format like "UTC+5"). Defaults to UTC if None.

**Returns:**

- Current time as ISO 8601 string

**Raises:**

- `ValueError`: If timezone is invalid

### `convert_timezone(time_str: str, source_timezone: str, target_timezone: str) -> Dict[str, Any]`

Convert time between timezones.

**Parameters:**

- `time_str`: Time in 24-hour format (HH:MM)
- `source_timezone`: Source timezone (e.g., "America/Chicago", "UTC+5")
- `target_timezone`: Target timezone (e.g., "Asia/Shanghai", "GMT-3")

**Returns:**

- Dictionary containing:
  - `source_time`: Source time in ISO 8601 format
  - `target_time`: Target time in ISO 8601 format
  - `time_difference`: Time difference string (e.g., "+8.0h")
  - `source_timezone`: Source timezone name
  - `target_timezone`: Target timezone name

**Raises:**

- `ValueError`: If timezone or time format is invalid

## Example Usage

### Basic Current Time

```python
from toolregistry_hub import DateTime

# Get current UTC time
current_time = DateTime.now()
print(current_time)
# Output: 2025-08-22T09:12:43+00:00

# Get current time in specific timezone (IANA format)
tokyo_time = DateTime.now("Asia/Tokyo")
print(tokyo_time)
# Output: 2025-08-22T18:12:43+09:00

# Get current time with UTC offset
ny_time = DateTime.now("UTC-5")
print(ny_time)
# Output: 2025-08-22T04:12:43-05:00
```

### Timezone Conversion

```python
from toolregistry_hub import DateTime

# Convert time between IANA timezones
result = DateTime.convert_timezone("14:30", "America/Chicago", "Asia/Shanghai")
print(result)
# Output: {
#     'source_time': '2025-08-22T14:30:00-05:00',
#     'target_time': '2025-08-23T03:30:00+08:00',
#     'time_difference': '+13.0h',
#     'source_timezone': 'America/Chicago',
#     'target_timezone': 'Asia/Shanghai'
# }

# Convert using UTC/GMT offsets
result = DateTime.convert_timezone("09:15", "UTC+0", "GMT+5:30")
print(result)
# Output: {
#     'source_time': '2025-08-22T09:15:00+00:00',
#     'target_time': '2025-08-22T14:45:00+05:30',
#     'time_difference': '+5.5h',
#     'source_timezone': 'UTC+0',
#     'target_timezone': 'GMT+5:30'
# }

# Mixed timezone formats
result = DateTime.convert_timezone("22:00", "America/New_York", "UTC+8")
print(result)
```

## Supported Timezone Formats

### IANA Timezone Names

- `Asia/Shanghai`
- `Asia/Tokyo`
- `America/Chicago`
- `Europe/London`
- `Australia/Sydney`
- And many more...

For interactive viewing of IANA timezone names, see <https://ntp.fays.al/iana-timezones>.

### UTC/GMT Offset Formats

- `UTC` or `GMT` (equivalent to UTC+0)
- `UTC+5`, `GMT+5` (5 hours ahead of UTC)
- `UTC-3`, `GMT-3` (3 hours behind UTC)
- `UTC+5:30`, `GMT+5:30` (5 hours 30 minutes ahead of UTC)
- `UTC-9:30`, `GMT-9:30` (9 hours 30 minutes behind UTC)

## Error Handling

The module provides clear error messages for invalid inputs:

```python
# Invalid timezone format
try:
    DateTime.now("Invalid/Timezone")
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Invalid timezone: Invalid/Timezone

# Invalid time format
try:
    DateTime.convert_timezone("25:00", "UTC", "UTC+1")
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Invalid time format. Expected HH:MM [24-hour format]

# Invalid UTC offset
try:
    DateTime.now("UTC+25")
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Invalid time offset: UTC+25
```

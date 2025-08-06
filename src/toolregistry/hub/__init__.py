"""ToolRegistry Hub - Alternative import name for toolregistry.hub.

This module provides an alternative import path for toolregistry.hub,
allowing users to import using either:
- from toolregistry.hub import Calculator
- from toolregistry_hub import Calculator

All functionality is re-exported from toolregistry.hub for compatibility.
"""

# Safe re-export: only import what's explicitly defined in __all__
try:
    import toolregistry_hub as _hub

    # Get the __all__ list from the original module
    __all__ = _hub.__all__

    # Dynamically re-export only the items in __all__
    for _name in __all__:
        globals()[_name] = getattr(_hub, _name)

    # Clean up temporary variables
    del _hub, _name

except ImportError:
    raise ImportError(
        "The toolregistry_hub package is not installed. "
        "Please install it with: `pip install toolregistry-hub`"
        "or `pip install toolregistry[hub]`"
    )
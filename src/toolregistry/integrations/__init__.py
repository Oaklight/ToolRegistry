"""Integration sub-packages for external tool ecosystems.

Each sub-package (mcp, openapi, langchain, native) bridges a specific
ecosystem into the ToolRegistry framework.  Sub-packages with optional
dependencies are imported lazily; importing this package alone does NOT
pull in any optional dependency.
"""

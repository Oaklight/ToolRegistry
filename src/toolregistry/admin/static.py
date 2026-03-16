"""Static assets for admin panel UI.

Loads the admin panel HTML from admin.html using importlib.resources.
"""

import importlib.resources


def _load_html() -> str:
    """Load admin.html from the package data."""
    package = __package__ or __name__
    return importlib.resources.files(package).joinpath("admin.html").read_text("utf-8")


ADMIN_HTML = _load_html()

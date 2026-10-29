"""Static assets for the admin panel.

The UI lives in ``admin.html`` next to this module and is shipped as package
data.  Loading it at import time keeps a single source of truth: an earlier
embedded copy drifted from ``admin.html``, so fixes (for example the runtime
warnings UI) never reached the panel the server actually serves.
"""

from importlib.resources import files

ADMIN_HTML: str = (
    files("toolregistry.admin").joinpath("admin.html").read_text(encoding="utf-8")
)

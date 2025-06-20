# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys

project = "ToolRegistry"
copyright = "2024-2025, Peng Ding"
author = "Peng Ding"
html_title = "ToolRegistry"
release = "0.4.13"


sys.path.insert(0, os.path.abspath("../../src"))
print("Current sys.path:", sys.path)

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",  # for Google & Numpy style docstring
    "sphinx.ext.autosummary",
    "myst_parser",
    "sphinx_multitoc_numbering",
    "sphinx_copybutton",
]

templates_path = ["_templates"]
exclude_patterns = []

# -- Options for autodoc -----------------------------------------------------
autodoc_member_order = "bysource"
autodoc_default_options = {
    "exclude-members": "__weakref__, __dict__, __module__, __annotations__",
    "special-members": "__init__",
    "undoc-members": True,
    "private-members": False,
}
# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# html_theme = "furo"
html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]
autosummary_generate = True
html_search_options = {"type": "default"}

# html_logo = "_static/logo/toolregistry_logo_9.jpeg"
# html_logo = "https://em-content.zobj.net/source/animated-noto-color-emoji/356/mechanical-arm_1f9be.gif"


html_theme_options = {
    # "announcement": ("v0.4.10.post1 released!"),
    "show_toc_level": 2,
    "show_nav_level": 2,
    "collapse_navigation": False,
    "icon_links": [
        {
            # Label for this link
            "name": "GitHub",
            "url": "https://github.com/Oaklight/ToolRegistry",  # required
            "icon": "fa-brands fa-github",
        },
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/toolregistry/",
            "icon": "https://pypi.org/static/images/logo-small.8998e9d1.svg",
            "type": "url",
        },
    ],
}

html_context = {
    # "github_url": "https://github.com", # or your GitHub Enterprise site
    "github_user": "Oaklight",
    "github_repo": "ToolRegistry",
    "github_version": "master",
    "doc_path": "docs",
}

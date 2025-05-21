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
release = "0.4.9"


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

html_theme = "furo"
html_static_path = ["_static"]
autosummary_generate = True
html_search_options = {"type": "default"}

# html_logo = "_static/logo/toolregistry_logo_9.jpeg"
# html_logo = "https://em-content.zobj.net/source/animated-noto-color-emoji/356/mechanical-arm_1f9be.gif"


html_css_files = [
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/fontawesome.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/solid.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/brands.min.css",
]

html_theme_options = {
    "announcement": ("v0.4.9 released! Now with support for LangChain tools! 🦜"),
    "source_repository": "https://github.com/Oaklight/ToolRegistry",
    "source_branch": "master",
    "source_directory": "docs/source/",
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/Oaklight/ToolRegistry",
            "html": "",
            "class": "fa-brands fa-solid fa-github fa-2x",
        },
    ],
}

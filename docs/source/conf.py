# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "ToolRegistry"
copyright = "2024-2025, Peng Ding"
author = "Peng Ding"
html_title = "ToolRegistry"
release = "0.2.0"

import os
import sys

sys.path.insert(0, os.path.abspath("../../src"))
print("Current sys.path:", sys.path)

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.autosummary",
    "myst_parser",
    "sphinx_multitoc_numbering",
    "sphinx_copybutton",
]

templates_path = ["_templates"]
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]

html_logo = "_static/logo/toolregistry_logo_6.jpeg"

autosummary_generate = True
html_search_options = {"type": "default"}

html_theme_options = {
    "announcement": (
        "Welcome to ToolRegistry, a Python library for managing and executing tools in a structured way."
    ),
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

# MkDocs Documentation Build Script for ToolRegistry
#

# You can set these variables from the command line.
SPHINXOPTS    ?=
SPHINXBUILD   ?= mkdocs
SOURCEDIR     = docs
BUILDDIR      = site

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# Clean build directory
clean:
	@echo "Cleaning build directory..."
	@rm -rf $(BUILDDIR)

# Build HTML documentation
html: clean
	@echo "Building HTML documentation..."
	@$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# Build and serve documentation locally
serve: html
	@echo "Serving documentation at http://localhost:8000"
	@cd $(BUILDDIR) && python -m http.server 8000

# Deploy to GitHub Pages
deploy: html
	@echo "Deploying to GitHub Pages..."
	@mkdocs gh-deploy --force

# Live reload documentation during development
live:
	@echo "Starting live documentation server..."
	@mkdocs serve --dev-addr localhost:8000

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
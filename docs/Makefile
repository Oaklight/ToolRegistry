# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = source
BUILDDIR      = build
DOCS_DIR      = $(BUILDDIR)/html  # Default Sphinx docs path

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# custom functions
# Host the documentation on the remote server
host:
	@echo "Syncing documentation to the remote server..."
	@DOCS_DIR="$(DOCS_DIR)" ./host_docs.sh

# Combined target: generate and host documentation
publish: html host
	@echo "Documentation has been generated and hosted."

# Regenerate API templates before building HTML
html: clean regenerate
	@echo "Building HTML documentation..."
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# Regenerate API templates
regenerate:
	@echo "Regenerating API templates..."
	@./regenerate_api_template.sh
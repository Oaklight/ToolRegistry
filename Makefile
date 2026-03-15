# Makefile for toolregistry package

# Variables
PACKAGE_NAME := toolregistry
DIST_DIR := dist

# Default target
all: lint test build

# ──────────────────────────────────────────────
# Linting & Type Checking
# ──────────────────────────────────────────────

# Run ty type checker
lint:
	@echo "Running ty check..."
	ty check
	@echo "Type check complete."

# ──────────────────────────────────────────────
# Testing
# ──────────────────────────────────────────────

# Run tests
test:
	@echo "Running tests..."
	pytest tests/ -v --tb=short
	@echo "Tests completed."

# ──────────────────────────────────────────────
# Package targets
# ──────────────────────────────────────────────

# Build the package
build: clean
	@echo "Building $(PACKAGE_NAME) version ..."
	python -m build
	@echo "Build complete. Distribution files are in $(DIST_DIR)/"

# Push the package to PyPI
push:
	@echo "Pushing $(PACKAGE_NAME) version to PyPI..."
	twine upload dist/*
	@echo "Package pushed to PyPI."

# Clean up build and distribution files
clean:
	@echo "Cleaning up build and distribution files..."
	rm -rf $(DIST_DIR) *.egg-info
	@echo "Cleanup complete."

# Help target
help:
	@echo "Available targets:"
	@echo ""
	@echo "Development:"
	@echo "  lint    - Run ty type checker"
	@echo "  test    - Run tests with pytest"
	@echo ""
	@echo "Package targets:"
	@echo "  build   - Build the pip package"
	@echo "  push    - Push the package to PyPI"
	@echo "  clean   - Clean up build and distribution files"
	@echo ""
	@echo "Composite targets:"
	@echo "  all     - Run lint, test, and build (default)"

.PHONY: all lint test build push clean help

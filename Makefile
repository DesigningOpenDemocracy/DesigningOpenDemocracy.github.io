.PHONY: serve build clean help

# Serve the book and open it in the default web browser
serve: # Serve the book locally and automatically open it in the browser
	xdg-open http://127.0.0.1:8000/
	mkdocs serve

# Build the book without serving
build: # Compile the markdown files into HTML format
	mkdocs build

# Clean the directory of generated book
clean: # Remove generated book files
	rm -rf site

# Display available commands
help: # Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*#' Makefile | sort | awk 'BEGIN {FS = ":.*#"}; {printf "\033[1;32m%-30s\033[00m %s\n", $$1, $$2}'

# Default target
all: build

# Example of defining a default target
.DEFAULT_GOAL := help

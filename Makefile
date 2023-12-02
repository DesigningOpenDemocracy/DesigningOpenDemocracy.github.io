.PHONY: serve build clean help

# Configure and setup Python Virtual Enviroment Folder
venv: venv/touchfile
venv/touchfile: requirements.txt
# Check if venv exist, if not then create one
	test -d venv || python -m venv venv
# Install requirements into the python virtual enviroment 
	. venv/bin/activate; pip install -Ur requirements.txt
# Mark the virtual enviroment folder as setup and ready to go
	touch venv/touchfile

# Serve the book and open it in the default web browser
serve: venv # Serve the book locally and automatically open it in the browser
	xdg-open http://127.0.0.1:8000/
	. venv/bin/activate; mkdocs serve

# Build the book without serving
build: venv # Compile the markdown files into HTML format
	. venv/bin/activate; mkdocs build

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

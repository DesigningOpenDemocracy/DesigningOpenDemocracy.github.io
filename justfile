set dotenv-load := false

venv := "venv"
python := venv + "/bin/python"
pip := venv + "/bin/pip"
mkdocs := venv + "/bin/mkdocs"

# Show available commands
default:
    @just --list

# Set up Python virtual environment and install dependencies
setup:
    test -d {{venv}} || python3 -m venv {{venv}}
    {{pip}} install -Ur requirements.txt

# Set up utility script dependencies (createPost, frontmatter_updator)
setup-util:
    test -d {{venv}} || python3 -m venv {{venv}}
    {{pip}} install -Ur util/requirements.txt

# Serve the site locally (opens browser)
serve: setup
    xdg-open http://127.0.0.1:8000/ &
    {{mkdocs}} serve

# Build the site into site/
build: setup
    {{mkdocs}} build

# Remove generated site files
clean:
    rm -rf site

# Deploy to GitHub Pages
deploy: setup
    {{mkdocs}} gh-deploy --force

# Create a new blog post interactively
post: setup
    {{python}} util/createPost.py

# Auto-fill frontmatter using OpenAI (requires OPENAI_API_KEY)
frontmatter file: setup setup-util
    {{python}} util/frontmatter_updator.py {{file}}

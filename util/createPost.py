#!/usr/bin/env python3

import os
from datetime import datetime

# Function to ask for user input
def ask(question):
    return input(question + ": ")

# Generate front matter for the document
def generate_front_matter(title, authors, summary, tags, date):
    tags_list = "\n".join([f"- {tag.strip()}" for tag in tags.split(',')])
    # Escape double quotes in summary
    summary_escaped = summary.replace('"', '\\"')
    front_matter = (f"---\n"
                    f"authors:\n"
                    f"- {authors}\n"
                    f"categories: []\n"
                    f"date: {date} 00:00:00\n"
                    f'summary: "{summary_escaped}"\n'  # Uses double quotes and escapes them in summary
                    f"tags:\n"
                    f"{tags_list}\n"
                    f"title: {title}\n"
                    "---\n\n")
    return front_matter



# Create a new document in the docs/blog directory
def create_new_doc():
    title = ask("Document title")
    authors = ask("Authors (comma-separated for multiple authors, will take first as primary)")
    summary = ask("Summary")
    tags = ask("Tags (comma-separated)")
    date = ask("Date (YYYY-MM-DD), leave blank for today's date")

    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    
    filename = f"{date}-{title.lower().replace(' ', '-')}.md"
    
    # Adjusted to point to 'docs/blog' directory
    docs_path = os.path.join(os.getcwd(), 'docs', 'blog', 'posts')
    file_path = os.path.join(docs_path, filename)
    
    # Check if docs/blog directory exists, create if not
    if not os.path.isdir(docs_path):
        os.makedirs(docs_path, exist_ok=True)
    
    front_matter = generate_front_matter(title, authors, summary, tags, date)
    
    with open(file_path, 'w') as f:
        f.write(front_matter)
    
    print(f"New document created at: {file_path}")

if __name__ == "__main__":
    create_new_doc()

#!/usr/bin/env python3
# LLM Based Frontmatter updator for Jekyll and MkDocs
# By Brian Khuu (2023)
# This script is to assist users in filling in summaries, tags, categories and other relevant fields
#    this is especially helpful for blog posts as it makes it easier to search for posts later on.
# You would need an OPENAI_API_KEY to use this script so make sure to include it in your ~/.bashrc startup script

import os
import re
import sys
import json
from dateutil import parser
from datetime import datetime
import frontmatter
from glob import glob
from openai import OpenAI

# Set your OpenAI GPT API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def limit_content_by_characters(content, max_characters):
    # Split the content into sentences based on newline and period
    sentences = re.split(r'\n |\. ', content)
    
    # Join sentences until the character limit is reached
    limited_content = ''
    for sentence in sentences:
        if len(limited_content) + len(sentence) <= max_characters:
            limited_content += sentence + '. '
        else:
            break
    
    return limited_content.strip()

def format_date_to_datetime(date_str):
    try:
        # Parse the input date string using dateutil.parser
        parsed_date = parser.parse(date_str)
        return parsed_date
    except Exception as e:
        print(f"Error parsing date: {date_str}")
        return None

def generate_response(content, existing_metadata, character_limit=2000):
    # Create a prompt that includes the existing metadata and the Jekyll page content
    message_prompt=[
        {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
        {"role": "system", "content": "You are trying to generate metadata for a metadata frontmatter in mkdocs"},
        {"role": "system", "content": "You are focused only on these fields date, authors, title, categories, tags, summary"},
        {"role": "system", "content": "Any date or time is in ISO 8601 format"},
        {"role": "user", "content": f"Page Content:\n{limit_content_by_characters(content, character_limit)}"},
        {"role": "user", "content": f"Existing Metadata:\n{existing_metadata}"},
    ]

    # Make a request to the OpenAI API
    chat_completion = client.chat.completions.create(
        model="gpt-3.5-turbo-1106",
        response_format={ "type": "json_object" },
        messages=message_prompt,
    )

    output_result = chat_completion.choices[0].message.content.strip()
    print(f"LLM Response: \'{output_result}\'")

    # Parse the JSON response
    try:
        response_json = json.loads(output_result)

        # Format date to datetime object
        if 'date' in response_json:
            response_json['date'] = format_date_to_datetime(response_json['date'])

        # Format update to datetime object
        if 'update' in response_json:
            response_json['update'] = format_date_to_datetime(response_json['update'])

        # Dump any keys with empty value
        response_json = {k: v for k, v in response_json.items() if v}

        return response_json
    except json.JSONDecodeError as e:
        print("Error decoding JSON response:")
        print(e)
        raise ValueError("Error generating response.")

def read_jekyll_page_content(file_path):
    # Read the Jekyll page
    with open(file_path, 'r', encoding='utf-8') as file:
        try:
            # Try to load front matter
            content = frontmatter.load(file)
        except frontmatter.FrontmatterError:
            # If there's no front matter, just read the entire file content
            print("no front matter detected")
            file.seek(0)
            content = frontmatter.loads(f"---\n---\n{file.read()}")

    # Extract the content excluding the front matter
    page_content = content.content
    metadata = content.metadata
    return page_content, metadata

def update_jekyll_page(file_path, response):
    # Read the Jekyll page
    with open(file_path, 'r', encoding='utf-8') as file:
        content = frontmatter.load(file)

    # Update the 'metadata_field' with the generated response
    content.metadata.update(response)

    # Convert the content to a string before saving
    content_str = frontmatter.dumps(content)

    # Save the updated content back to the file
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content_str)

def process_file(md_file):
    print(f"=== {md_file} ===")
    # Read the content of the Jekyll page
    page_content, existing_metadata = read_jekyll_page_content(md_file)

    # Generate a response from ChatGPT based on the content
    # We have a retry logic here since the LLM endpoint can sometimes cark out and spit half a response
    #   the json parser would then cark out on their end. This is good still, as it means we are only
    #   accepting valid json responses from the LLM.
    #   In more advance cases we may do a schema validation, but since this is essentally for a markdown
    #   based workflow... we can have a bit more loose approach
    response = None
    maxRetry = 3
    for i in range(0, maxRetry):
        try:
            charLimit = 2000/(1+i)
            response = generate_response(page_content, existing_metadata, charLimit)
        except Exception:
            print(f"RETRYING {i} (charlim was {charLimit})")
            if i < maxRetry - 1: # i is zero indexed
                continue
            else:
                raise
        break

    # Show response
    print(response)

    # Update the Jekyll page with the generated response in the metadata field
    update_jekyll_page(md_file, response)

    print(f"Jekyll page '{md_file}' updated successfully.\n")

if __name__ == "__main__":
    # Check if the correct number of command-line arguments is provided
    if len(sys.argv) < 2:
        print("Usage: python update_jekyll_page.py <file_path>")
        sys.exit(1)

    # Extract file path from command-line arguments
    jekyll_page_path = sys.argv[1]

    if os.path.isfile(jekyll_page_path):
        # Single file provided
        process_file(jekyll_page_path)
    elif os.path.isdir(jekyll_page_path):
        # Directory provided, process all Markdown files in the directory
        md_files = glob(os.path.join(jekyll_page_path, '*.md'))
        for md_file in md_files:
            process_file(md_file)

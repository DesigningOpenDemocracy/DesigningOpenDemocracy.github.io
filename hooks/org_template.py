def on_page_markdown(markdown, *, page, config, files):
    """Auto-apply organisation.html template to all org pages that don't set one explicitly."""
    if (page.file.src_path.startswith('organisations/')
            and page.file.src_path != 'organisations/organisations.md'
            and not page.meta.get('template')):
        page.meta['template'] = 'organisation.html'
    return markdown

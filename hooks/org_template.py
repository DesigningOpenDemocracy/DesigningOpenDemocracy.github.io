def on_page_markdown(markdown, *, page, config, files):
    """Auto-apply organisation.html template to all org pages that don't set one explicitly.

    Also hides the primary sidebar for the whole organisations/ section — with
    100+ org pages, Material's default nav tree would list every one of them
    down the left side of every page in the section. The section is reachable
    from the top nav tab, and browsing within it uses the index page's own
    filterable/sortable table instead of a sidebar tree.
    """
    if page.file.src_path.startswith('organisations/'):
        hide = page.meta.get('hide') or []
        if 'navigation' not in hide:
            page.meta['hide'] = hide + ['navigation']
        if (page.file.src_path != 'organisations/index.md'
                and not page.meta.get('template')):
            page.meta['template'] = 'organisation.html'
    return markdown

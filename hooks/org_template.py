LANDSCAPE_INDEX = 'organisations/index.md'

# The nav section switched on for the org page currently rendering, so
# on_post_page can switch it back off. See on_page_context.
_lit = []


def on_page_markdown(markdown, *, page, config, files):
    """Auto-apply organisation.html template to all org pages that don't set one explicitly.

    Also hides the primary sidebar for the whole organisations/ section. The
    org pages themselves aren't in the nav (see on_page_context), so this is
    no longer about a 170-entry sidebar tree; it's about width. The index's
    sortable table and each profile's layout want the full page, and the
    section's two entries, Directory and Map, are offered instead by the
    in-page switcher (partials/section-tabs.html) and the mobile menu.
    """
    if page.file.src_path.startswith('organisations/'):
        hide = page.meta.get('hide') or []
        if 'navigation' not in hide:
            page.meta['hide'] = hide + ['navigation']
        if (page.file.src_path != 'organisations/index.md'
                and not page.meta.get('template')):
            page.meta['template'] = 'organisation.html'
    return markdown


def landscape_section(items):
    """The nav section holding the Landscape directory page, or None."""
    for item in items or []:
        children = getattr(item, 'children', None)
        if not children:
            continue
        for child in children:
            f = getattr(child, 'file', None)
            if f is not None and f.src_uri == LANDSCAPE_INDEX:
                return item
        found = landscape_section(children)
        if found is not None:
            return found
    return None


def on_page_context(context, *, page, config, nav):
    """Keep the Democracy Landscape tab highlighted on org profile pages.

    The ~170 org pages are deliberately left out of SUMMARY.md: Material
    embeds the whole nav tree in every page on the site (it's the mobile
    menu), so listing them there cost every page ~65 KB of markup and put
    170 entries in the Landscape section of the mobile menu. A page outside
    the nav has no section to mark active, though, so its tab would fall
    dark. Switching the section on for the render, and off again after
    (on_post_page), is what MkDocs itself does for pages that are in the nav.
    """
    src = page.file.src_uri
    if src.startswith('organisations/') and src != LANDSCAPE_INDEX and page not in nav.pages:
        section = landscape_section(nav.items)
        if section is not None and not section.active:
            section.active = True
            _lit.append(section)
    return context


def on_post_page(output, *, page, config):
    while _lit:
        _lit.pop().active = False
    return output

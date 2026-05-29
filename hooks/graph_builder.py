"""
Build hook: extracts concept/org/project relationships → graph.json

  - Org → Concept edges from `concepts:` frontmatter on org (and project) pages
  - Concept → Concept edges from "See also" sections in concept page markdown
  - Writes {site_dir}/graph.json after every build (compatible with `mkdocs serve`)
"""
import json
import os
import re

_nodes: dict = {}
_edges: list = []

_SEE_ALSO_RE = re.compile(
    r'##\s+See\s+[Aa]lso\b[^\n]*\n([\s\S]*?)(?=\n##\s|\Z)',
)
_MD_LINK_RE = re.compile(r'\[[^\]]+\]\(([^)#\s]+\.md)(?:#[^)]*)?\)')


def on_pre_build(config):
    _nodes.clear()
    _edges.clear()


def on_page_markdown(markdown, *, page, config, files):
    src = page.file.src_path
    if not src.startswith('concepts/') or src == 'concepts/concepts.md':
        return markdown

    slug = src[len('concepts/'):].replace('.md', '')
    m = _SEE_ALSO_RE.search(markdown)
    if not m:
        return markdown

    for link_m in _MD_LINK_RE.finditer(m.group(1)):
        href = link_m.group(1)
        # Local concept-to-concept links only — skip ../ org links and http URLs
        if href.startswith('..') or href.startswith('http') or '/' in href:
            continue
        target_slug = href.replace('.md', '')
        if target_slug:
            _edges.append({
                'source': f'concept:{slug}',
                'target': f'concept:{target_slug}',
                'type': 'see_also',
            })
    return markdown


def on_page_context(context, *, page, config, nav):
    url = page.url or ''

    if url.startswith('concepts/') and url not in ('concepts/', 'concepts/concepts/'):
        slug = url.replace('concepts/', '').rstrip('/')
        _nodes[f'concept:{slug}'] = {
            'id': f'concept:{slug}',
            'label': page.title or slug,
            'type': 'concept',
            'url': f'/{url}',
        }

    elif url.startswith('organisations/') and url not in ('organisations/', 'organisations/organisations/'):
        slug = url.replace('organisations/', '').rstrip('/')
        node_id = f'org:{slug}'
        _nodes[node_id] = {
            'id': node_id,
            'label': page.title or slug,
            'type': 'organisation',
            'status': page.meta.get('status', ''),
            'org_type': page.meta.get('type', ''),
            'url': f'/{url}',
        }
        for c in (page.meta.get('concepts') or []):
            _edges.append({'source': node_id, 'target': f'concept:{c}', 'type': 'relates_to'})

    elif url.startswith('projects/') and url not in ('projects/', 'projects/projects/'):
        slug = url.replace('projects/', '').rstrip('/')
        node_id = f'project:{slug}'
        _nodes[node_id] = {
            'id': node_id,
            'label': page.title or slug,
            'type': 'project',
            'status': page.meta.get('status', ''),
            'url': f'/{url}',
        }
        for c in (page.meta.get('concepts') or []):
            _edges.append({'source': node_id, 'target': f'concept:{c}', 'type': 'relates_to'})

    return context


def on_post_build(config):
    valid_ids = set(_nodes)

    seen: set = set()
    unique_edges = []
    for e in _edges:
        if e['source'] not in valid_ids or e['target'] not in valid_ids:
            continue
        key = (e['source'], e['target'], e['type'])
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)

    graph = {'nodes': list(_nodes.values()), 'edges': unique_edges}

    out_path = os.path.join(config['site_dir'], 'graph.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)

    print(
        f'[graph_builder] {len(_nodes)} nodes, {len(unique_edges)} edges → graph.json'
    )

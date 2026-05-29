"""
Build hook: extracts concept/org/project relationships → graph.json

  - Org/Project → Concept edges from `concepts:` frontmatter
  - Concept → Concept edges from "See also" sections in concept page markdown
  - Project → Org edges from "../organisations/" links in project page "See also" sections
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
    m = _SEE_ALSO_RE.search(markdown)

    if src.startswith('concepts/') and src != 'concepts/concepts.md':
        slug = src[len('concepts/'):].replace('.md', '')
        if m:
            for link_m in _MD_LINK_RE.finditer(m.group(1)):
                href = link_m.group(1)
                # Local concept-to-concept links only
                if href.startswith('..') or href.startswith('http') or '/' in href:
                    continue
                target_slug = href.replace('.md', '')
                if target_slug:
                    _edges.append({
                        'source': f'concept:{slug}',
                        'target': f'concept:{target_slug}',
                        'type': 'see_also',
                    })

    elif src.startswith('projects/') and src != 'projects/projects.md':
        slug = src[len('projects/'):].replace('.md', '')
        if m:
            for link_m in _MD_LINK_RE.finditer(m.group(1)):
                href = link_m.group(1)
                if href.startswith('../organisations/') and not href.startswith('http'):
                    target_slug = href[len('../organisations/'):].replace('.md', '')
                    if target_slug:
                        _edges.append({
                            'source': f'project:{slug}',
                            'target': f'org:{target_slug}',
                            'type': 'relates_to',
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

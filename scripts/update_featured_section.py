#!/usr/bin/env python3
"""
Update the README Featured Projects section in-place using the GitHub API.
Replaces content between <!-- FEATURED:START --> and <!-- FEATURED:END --> markers.

Usage:
  python3 scripts/update_featured_section.py [--token=YOUR_GITHUB_TOKEN]

Reads config from profile-config.json.
"""
import json
import os
import re
import sys
from typing import List

import requests

ROOT = os.path.dirname(os.path.dirname(__file__))
README_PATH = os.path.join(ROOT, 'README.md')
CONFIG_PATH = os.path.join(ROOT, 'profile-config.json')

# Use full markers (including the closing -->) to avoid matching issues
START_MARK = '<!-- FEATURED:START -->'
END_MARK = '<!-- FEATURED:END -->'


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def fetch_repos(username: str, token: str | None) -> List[dict]:
    url = f'https://api.github.com/users/{username}/repos?per_page=200&sort=updated'
    headers = {'Accept': 'application/vnd.github+json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def choose_featured(repos: List[dict], count: int) -> List[dict]:
    # Prefer non-fork, non-archived, sorted by stars then forks then recent update
    candidates = [r for r in repos if not r.get('fork') and not r.get('archived')]
    candidates.sort(key=lambda r: (
        r.get('stargazers_count', 0),
        r.get('forks_count', 0),
        r.get('updated_at', '')
    ), reverse=True)
    return candidates[:count]


def render_md(repos: List[dict]) -> str:
    lines = []
    for r in repos:
        name = r['name']
        desc = (r.get('description') or 'No description provided.').strip()
        url = r['html_url']
        lines.append(f"- **{name}** — {desc}. [Repo link]({url})")
    return '\n'.join(lines)


def replace_between(text: str, start: str, end: str, new_content: str) -> str:
    pattern = rf"{re.escape(start)}[\s\S]*?{re.escape(end)}"
    block = f"{start}\n{new_content}\n{end}"
    return re.sub(pattern, block, text, flags=re.MULTILINE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', help='GitHub token (optional)')
    parser.add_argument('--dry-run', action='store_true', help='Show changes without writing README')
    args = parser.parse_args()

    cfg = load_config()
    username = cfg.get('username', '')
    count = int(cfg.get('featured_count', 3))

    repos = fetch_repos(username, args.token)
    featured = choose_featured(repos, count)
    md = render_md(featured)

    with open(README_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    updated = replace_between(content, START_MARK, END_MARK, md)

    if updated != content:
        if args.dry_run:
            print('[dry-run] Featured section would be updated:')
            start = updated.find(START_MARK)
            end = updated.find(END_MARK, start) + len(END_MARK)
            print(updated[start:end])
        else:
            with open(README_PATH, 'w', encoding='utf-8') as f:
                f.write(updated)
            print('README updated successfully.')
    else:
        print('No changes to README.')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Fetch top repositories for a GitHub user and print a markdown list for the README's
Featured Projects section.

Usage:
  python3 scripts/fetch_featured_repos.py [--token YOUR_GITHUB_TOKEN]

If you don't provide a token, the script will make unauthenticated requests (rate-limited).
"""
import json
import os
import sys
from operator import itemgetter

import requests

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'profile-config.json')


def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)


def fetch_repos(username, token=None):
    url = f'https://api.github.com/users/{username}/repos?per_page=200'
    headers = { 'Accept': 'application/vnd.github.v3+json' }
    if token:
        headers['Authorization'] = f'token {token}'
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def top_repos(repos, count=3):
    # sort by stargazers_count, then forks
    sorted_repos = sorted(repos, key=lambda r: (r.get('stargazers_count', 0), r.get('forks_count',0)), reverse=True)
    return sorted_repos[:count]


def format_markdown(repos):
    lines = []
    for r in repos:
        name = r['name']
        desc = r.get('description') or 'No description provided.'
        url = r['html_url']
        lines.append(f"- **{name}** — {desc}. [Repo link]({url})")
    return '\n'.join(lines)


def main():
    cfg = load_config()
    username = cfg.get('username')
    count = cfg.get('featured_count', 3)
    token = None
    # allow token via CLI arg
    if len(sys.argv) > 1 and sys.argv[1].startswith('--token'):
        parts = sys.argv[1].split('=', 1)
        if len(parts) == 2:
            token = parts[1]

    repos = fetch_repos(username, token=token)
    top = top_repos(repos, count=count)
    md = format_markdown(top)
    print('# Featured Projects (auto-generated)')
    print()
    print(md)


if __name__ == '__main__':
    main()

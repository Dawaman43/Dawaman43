#!/usr/bin/env python3
"""
Update the README Top Followers section in-place.
Selects top N followers by their own follower counts.

Usage:
  python3 scripts/update_followers_section.py [--token=YOUR_GITHUB_TOKEN]

Reads config from profile-config.json. Writes avatar grid markdown/HTML.
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

START_MARK = '<!-- FOLLOWERS:START'
END_MARK = '<!-- FOLLOWERS:END -->'

AVATAR_SIZE = 64


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def gh_get(url: str, token: str | None):
    headers = {'Accept': 'application/vnd.github+json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_followers(username: str, token: str | None) -> List[dict]:
    followers = gh_get(f'https://api.github.com/users/{username}/followers?per_page=100', token)
    # Enrich with each follower's follower count
    enriched = []
    for f in followers:
        login = f['login']
        user = gh_get(f'https://api.github.com/users/{login}', token)
        enriched.append({
            'login': login,
            'html_url': f'https://github.com/{login}',
            'avatar_url': user.get('avatar_url') or f.get('avatar_url'),
            'followers': user.get('followers', 0),
            'name': user.get('name') or login,
        })
    return enriched


def render_avatar_grid(users: List[dict], cols: int = 5) -> str:
    # Render a table grid of avatars with links and tooltips
    lines = ["<table>"]
    for i in range(0, len(users), cols):
        lines.append("  <tr>")
        for u in users[i:i+cols]:
            lines.append(
                f"    <td align=\"center\" width=\"{100//cols}%\">"
                f"<a href=\"{u['html_url']}\" title=\"{u['name']} — {u['followers']} followers\">"
                f"<img src=\"{u['avatar_url']}\" width=\"{AVATAR_SIZE}\" height=\"{AVATAR_SIZE}\" style=\"border-radius:50%\" alt=\"{u['login']}\"/></a><br/>"
                f"<sub>@{u['login']}</sub>"
                f"</td>"
            )
        lines.append("  </tr>")
    lines.append("</table>")
    return "\n".join(lines)


def replace_between(text: str, start: str, end: str, new_content: str) -> str:
    pattern = rf"{re.escape(start)}[\s\S]*?{re.escape(end)}"
    block = f"{start} -->\n{new_content}\n{end}"
    return re.sub(pattern, block, text, flags=re.MULTILINE)


def main():
    cfg = load_config()
    username = cfg.get('username', 'Dawaman43')
    count = int(cfg.get('top_followers_count', 10))

    token = None
    if len(sys.argv) > 1 and sys.argv[1].startswith('--token='):
        token = sys.argv[1].split('=', 1)[1]

    followers = fetch_followers(username, token)
    followers.sort(key=lambda u: u['followers'], reverse=True)
    top = followers[:count]
    grid = render_avatar_grid(top, cols=5)

    with open(README_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    updated = replace_between(content, START_MARK, END_MARK, grid)

    if updated != content:
        with open(README_PATH, 'w', encoding='utf-8') as f:
            f.write(updated)
        print('README updated with Top Followers.')
    else:
        print('No changes to README (followers section unchanged).')


if __name__ == '__main__':
    main()

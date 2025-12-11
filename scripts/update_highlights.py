#!/usr/bin/env python3
"""
Fetch basic GitHub user stats and update the README HIGHLIGHTS block.
Usage: python3 scripts/update_highlights.py [--token GITHUB_TOKEN] [--dry-run]
"""
import argparse
import json
import os
import re
import sys
from urllib.parse import quote_plus

import requests

HERE = os.path.dirname(os.path.dirname(__file__))
README_PATH = os.path.join(HERE, "README.md")
CONFIG_PATH = os.path.join(HERE, "profile-config.json")
CACHE_PATH = os.path.join(HERE, ".cache_user.json")
CACHE_REPOS_PATH = os.path.join(HERE, ".cache_repos.json")

# Markers in README should include the full HTML comment markers
H_START = "<!-- HIGHLIGHTS:START -->"
H_END = "<!-- HIGHLIGHTS:END -->"


def read_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_user(username, token=None):
    url = f"https://api.github.com/users/{username}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json()


def fetch_repos(username, token=None):
    url = f"https://api.github.com/users/{username}/repos?per_page=200"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    repos = r.json()
    # save repos cache for offline/dry-run use
    try:
        with open(CACHE_REPOS_PATH, "w", encoding="utf-8") as f:
            json.dump(repos, f)
    except Exception:
        pass
    return repos


def load_repos_cache():
    if not os.path.exists(CACHE_REPOS_PATH):
        return None
    try:
        with open(CACHE_REPOS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_cache():
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_cache(user):
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(user, f)
    except Exception:
        pass


def render_badges(user, cfg=None):
    # Create simple shields-style static badges using img.shields.io/badge
    followers = user.get("followers", 0)
    repos = user.get("public_repos", 0)
    gists = user.get("public_gists", 0)
    created = user.get("created_at", "")
    # allow optional badge colors from config
    colors = {}
    if cfg and isinstance(cfg, dict):
        colors = cfg.get("badge_colors", {})

    def badge(label, value, color=None):
        label_enc = quote_plus(label)
        value_enc = quote_plus(str(value))
        if color is None:
            color = colors.get(label, "2ea44f")
        return f"![{label}: {value}](https://img.shields.io/badge/{label_enc}-{value_enc}-{color}.svg)"

    badges = []
    badges.append(badge("Followers", followers))
    badges.append(badge("Public Repos", repos))
    badges.append(badge("Public Gists", gists))
    if created:
        date = created.split("T")[0]
        badges.append(badge("Member Since", date))

    md = "<p align=\"center\">\n  " + "\n  ".join(badges) + "\n</p>\n"
    return md


def render_top_languages(repos, top_n=3):
    if not repos:
        # try to load cached repos
        cached = load_repos_cache()
        if cached:
            repos = cached
        else:
            # fallback to scanning local files in the repo root for language inference
            langs = detect_local_languages(HERE)
            if not langs:
                return ""
            items = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
            badges = []
            for lang, cnt in items:
                badges.append(f"![{lang}: {cnt}](https://img.shields.io/badge/{quote_plus(lang)}-{cnt}-blue.svg)")
            return " ".join(badges)
    counts = {}
    for r in repos:
        lang = r.get("language") or "Unknown"
        counts[lang] = counts.get(lang, 0) + 1
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    badges = []
    for lang, cnt in items:
        label = lang.replace(" ", "+")
        badges.append(f"![{lang}: {cnt}](https://img.shields.io/badge/{quote_plus(lang)}-{cnt}-blue.svg)")
    return " ".join(badges)


def detect_local_languages(root_path):
    # Map common extensions to language names
    ext_map = {
        '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript', '.java': 'Java',
        '.go': 'Go', '.rs': 'Rust', '.cpp': 'C++', '.c': 'C', '.h': 'C', '.hpp': 'C++',
        '.php': 'PHP', '.rb': 'Ruby', '.swift': 'Swift', '.kt': 'Kotlin', '.m': 'Objective-C',
        '.dart': 'Dart', '.cs': 'C#', '.sh': 'Shell', '.html': 'HTML', '.css': 'CSS'
    }
    counts = {}
    for dirpath, dirnames, filenames in os.walk(root_path):
        # skip .git and virtualenvs
        if '/.git' in dirpath or '/venv' in dirpath or 'node_modules' in dirpath:
            continue
        for fn in filenames:
            _, ext = os.path.splitext(fn.lower())
            lang = ext_map.get(ext)
            if lang:
                counts[lang] = counts.get(lang, 0) + 1
    return counts


def replace_between(text, start_marker, end_marker, replacement):
    # Replace the block between the full start and end markers (inclusive).
    pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.DOTALL)
    header = start_marker
    footer = end_marker
    new_block = header + "\n<!-- generated by scripts/update_highlights.py - do not edit directly -->\n" + replacement + footer
    if pattern.search(text):
        return pattern.sub(new_block, text)
    # If markers missing, append block at end of file
    return text + "\n" + new_block


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", help="GitHub token (optional)")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing README")
    args = parser.parse_args()

    cfg = read_config()
    username = cfg.get("username")
    if not username:
        print("username not set in profile-config.json", file=sys.stderr)
        sys.exit(1)

    try:
        user = fetch_user(username, args.token)
        # save a local cache to allow dry-runs when rate-limited
        save_cache(user)
    except Exception as e:
        # Handle GitHub rate limit specially: try to use cached data if present
        msg = str(e)
        # check for requests HTTPError with 403 status
        use_cache = False
        try:
            if isinstance(e, requests.exceptions.HTTPError) and e.response is not None and e.response.status_code == 403:
                use_cache = True
        except Exception:
            pass

        if use_cache:
            cached = load_cache()
            if cached:
                print("Rate limit exceeded — using cached user data for dry-run.")
                user = cached
            else:
                print(f"Failed to fetch user info: {e}", file=sys.stderr)
                print("Rate limit exceeded and no cache available. Try again with a token.", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"Failed to fetch user info: {e}", file=sys.stderr)
            sys.exit(1)

    badges_md = render_badges(user, cfg)

    # attempt to fetch repos to compute top languages (best-effort)
    try:
        repos = fetch_repos(username, args.token)
    except Exception:
        repos = []

    languages_md = render_top_languages(repos, top_n=3)
    if languages_md:
        badges_md = badges_md + "\n\n" + languages_md

    # Append activity graph and contribution-snake animation using the configured username
    uname = cfg.get("username", username)
    activity_md = (
        f'<p align="center">\n'
        f'  <img src="https://github-readme-activity-graph.vercel.app/graph?username={uname}&theme=dracula&hide_border=true&bg_color=0D1117&color=F75C7E&line=F75C7E&point=00FFFF&area=true&area_color=00FFFF20" width="100%" alt="Activity Graph"/>'
        f'\n</p>\n\n'
        f'<p align="center">\n'
        f'  <img src="https://raw.githubusercontent.com/{uname}/{uname}/output/github-contribution-grid-snake.svg" alt="Snake animation" />\n'
        f'</p>\n'
    )

    badges_md = badges_md + "\n" + activity_md

    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    new_readme = replace_between(readme, H_START, H_END, badges_md)

    if new_readme != readme:
        if args.dry_run:
            print("[dry-run] README would be updated. Here's the new highlights block:\n")
            start = new_readme.find(H_START)
            end = new_readme.find(H_END, start) + len(H_END)
            print(new_readme[start:end])
        else:
            with open(README_PATH, "w", encoding="utf-8") as f:
                f.write(new_readme)
            print("README highlights updated")
    else:
        print("No changes to README")


if __name__ == "__main__":
    main()

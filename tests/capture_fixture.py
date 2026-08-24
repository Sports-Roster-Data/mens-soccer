#!/usr/bin/env python3
"""Capture a roster page as a test fixture, fetched through the scraper's own
code path so the saved HTML is exactly what the parsers will see.

Usage:
    python tests/capture_fixture.py <parser_name> <label> <url> [--js]

Example:
    python tests/capture_fixture.py table albany \\
        https://ualbanysports.com/sports/mens-soccer/roster/2025
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

from rosters.fetch import fetch_url, fetch_html_with_javascript  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('parser_name')
    ap.add_argument('label')
    ap.add_argument('url')
    ap.add_argument('--js', action='store_true', help='render with shot-scraper')
    args = ap.parse_args()

    if args.js:
        soup = fetch_html_with_javascript(args.url)
        if soup is None:
            print('failed to render', args.url)
            return 1
        content = str(soup)
    else:
        resp = fetch_url(args.url)
        if resp.status_code != 200:
            print(f'fetch {resp.status_code} for {args.url}')
            return 1
        content = resp.content.decode('utf-8', errors='replace')

    out_dir = FIXTURES / args.parser_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f'{args.label}.html'
    out.write_text(content)
    print(f'wrote {out} ({len(content)} bytes)')
    return 0


if __name__ == '__main__':
    sys.exit(main())

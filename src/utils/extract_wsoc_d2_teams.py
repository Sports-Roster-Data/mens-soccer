#!/usr/bin/env python3
"""
Extract Division II Women's Soccer team information from NCAA stats page.

This script:
1. Parses wsoc_d2.html to find team links
2. Attempts to map team names to URLs using men's soccer data as a reference
3. Creates a CSV with team name, ID, and URL

Note: Uses men's soccer URLs as a bootstrap by converting /mens-soccer to /womens-soccer
"""

import csv
import re
from pathlib import Path
from bs4 import BeautifulSoup

def parse_teams_from_html(html_path):
    """
    Parse the HTML file to extract team names and IDs.

    Returns:
        List of tuples (team_name, team_id)
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')

    # Find all team links (href="/teams/{id}")
    team_links = soup.find_all('a', href=re.compile(r'^/teams/\d+$'))

    teams = []
    seen_ids = set()
    for link in team_links:
        team_name = link.get_text(strip=True)
        href = link['href']
        # Extract team ID from href (e.g., "/teams/603104" -> "603104")
        team_id = href.split('/')[-1]

        # Avoid duplicates
        if team_id not in seen_ids:
            teams.append((team_name, team_id))
            seen_ids.add(team_id)

    print(f"Found {len(teams)} unique teams in HTML file")
    return teams

def load_mens_soccer_teams(csv_path):
    """
    Load men's soccer teams to use as a reference for URLs.

    Returns:
        Dictionary mapping team names to their URLs
    """
    teams_map = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            team_name = row['team']
            url = row['url']
            teams_map[team_name] = url

    print(f"Loaded {len(teams_map)} men's soccer teams as reference")
    return teams_map

def normalize_team_name(name):
    """
    Normalize team name for matching.

    Handles variations like:
    - "St." vs "State"
    - Removing "Lady", "Women's", etc.
    """
    # Remove common prefixes/suffixes
    name = name.replace('Lady ', '').replace(' Lady', '')
    name = name.replace('Women\'s ', '').replace(' Women\'s', '')

    return name.strip()

def convert_to_womens_url(mens_url):
    """
    Convert a men's soccer URL to women's soccer URL.

    Examples:
    - /mens-soccer -> /womens-soccer
    - /m-soccer -> /w-soccer
    - /msoc -> /wsoc
    """
    # Try different conversion patterns
    if '/mens-soccer' in mens_url:
        return mens_url.replace('/mens-soccer', '/womens-soccer')
    elif '/m-soccer' in mens_url:
        return mens_url.replace('/m-soccer', '/w-soccer')
    elif '/msoc' in mens_url:
        return mens_url.replace('/msoc', '/wsoc')
    else:
        # If no clear pattern, just try womens-soccer
        # Extract base domain and add /sports/womens-soccer
        if '/sports/' in mens_url:
            base = mens_url.split('/sports/')[0]
            return f"{base}/sports/womens-soccer"

    return mens_url

def main():
    # Paths
    html_path = Path('data/input/wsoc_d2.html')
    mens_csv_path = Path('data/input/teams.csv')
    output_path = Path('data/input/teams_wsoc_d2.csv')

    # Parse teams from HTML
    print("Parsing teams from HTML file...")
    teams = parse_teams_from_html(html_path)

    # Load men's soccer teams for URL reference
    print("\nLoading men's soccer teams for URL mapping...")
    mens_teams = load_mens_soccer_teams(mens_csv_path)

    # Map women's teams to URLs
    print(f"\nMapping {len(teams)} women's teams to URLs...")
    results = []
    matched = 0
    unmatched = 0

    for i, (team_name, team_id) in enumerate(teams, 1):
        normalized_name = normalize_team_name(team_name)

        # Try to find matching men's team
        womens_url = ''

        # Direct match
        if normalized_name in mens_teams:
            mens_url = mens_teams[normalized_name]
            womens_url = convert_to_womens_url(mens_url)
            matched += 1
            print(f"[{i}/{len(teams)}] {team_name} -> Matched (direct)")
        # Try original name
        elif team_name in mens_teams:
            mens_url = mens_teams[team_name]
            womens_url = convert_to_womens_url(mens_url)
            matched += 1
            print(f"[{i}/{len(teams)}] {team_name} -> Matched (original)")
        else:
            # Try fuzzy matching on key parts of the name
            found = False
            for mens_team, mens_url in mens_teams.items():
                # Extract key identifier (usually the school name before comma or last word)
                team_key = normalized_name.split()[-1] if normalized_name else ''
                mens_key = mens_team.split()[-1] if mens_team else ''

                if team_key and len(team_key) > 3 and team_key == mens_key:
                    womens_url = convert_to_womens_url(mens_url)
                    matched += 1
                    print(f"[{i}/{len(teams)}] {team_name} -> Matched (fuzzy: {mens_team})")
                    found = True
                    break

            if not found:
                unmatched += 1
                print(f"[{i}/{len(teams)}] {team_name} -> No match found")

        results.append({
            'team': team_name,
            'team_id': team_id,
            'url': womens_url
        })

    # Write to CSV
    print(f"\nWriting results to {output_path}...")
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['team', 'team_id', 'url'])
        writer.writeheader()
        writer.writerows(results)

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total teams: {len(results)}")
    print(f"Matched with URLs: {matched}")
    print(f"Unmatched (no URL): {unmatched}")
    print(f"Output saved to: {output_path}")
    print("="*60)

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Phase 3: URL Pattern Analysis

Analyzes teams.csv to categorize teams by URL pattern and scraping strategy.
Tests sample URLs to validate patterns and generate TeamConfig data.
"""

import sys
import csv
import requests
from pathlib import Path
from collections import defaultdict
from urllib.parse import urlparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from soccer_roster_scraper import SeasonVerifier, logger
from bs4 import BeautifulSoup

def categorize_url_pattern(url: str) -> str:
    """
    Categorize URL by its pattern

    Returns:
        'sidearm' - /sports/mens-soccer pattern
        'msoc_index' - /sports/msoc/index pattern
        'other' - Other patterns
    """
    if '/sports/mens-soccer' in url:
        return 'sidearm'
    elif '/sports/msoc/index' in url:
        return 'msoc_index'
    elif '/Sports/msoc' in url:
        return 'msoc_index'  # Capital S variant
    elif '/sports/m-soccer' in url:
        return 'sidearm'  # Treat as sidearm variant
    else:
        return 'other'


def test_url_with_season(url: str, season: str = '2025', timeout: int = 10):
    """
    Test if a roster URL returns valid HTML

    Returns:
        dict with 'status', 'has_sidearm', 'title', 'error'
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
    }

    # Build roster URL
    roster_url = f"{url}/roster/{season}"

    result = {
        'url': roster_url,
        'status': None,
        'has_sidearm': False,
        'has_table': False,
        'title': '',
        'error': None
    }

    try:
        response = requests.get(roster_url, headers=headers, timeout=timeout)
        result['status'] = response.status_code

        if response.status_code == 200:
            html = BeautifulSoup(response.content, 'html.parser')

            # Check for Sidearm structure
            sidearm_players = html.find_all('li', class_='sidearm-roster-player')
            result['has_sidearm'] = len(sidearm_players) > 0

            # Check for table structure
            tables = html.find_all('table')
            result['has_table'] = len(tables) > 0

            # Get title
            title = html.find('title')
            if title:
                result['title'] = title.get_text().strip()

    except requests.Timeout:
        result['error'] = 'Timeout'
    except requests.RequestException as e:
        result['error'] = str(e)
    except Exception as e:
        result['error'] = f"Parse error: {e}"

    return result


def analyze_teams(csv_path: str, sample_per_pattern: int = 5):
    """
    Analyze all teams in teams.csv and categorize by URL pattern
    """
    print("=" * 80)
    print("Phase 3: URL Pattern Analysis")
    print("=" * 80)

    # Load teams
    teams_by_pattern = defaultdict(list)
    teams_by_division = defaultdict(list)

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pattern = categorize_url_pattern(row['url'])
            teams_by_pattern[pattern].append(row)
            teams_by_division[row['division']].append(row)

    # Summary statistics
    print(f"\n1. TEAMS BY DIVISION")
    print("-" * 80)
    for division in sorted(teams_by_division.keys()):
        count = len(teams_by_division[division])
        print(f"   Division {division:3s}: {count:3d} teams")

    total_teams = sum(len(teams) for teams in teams_by_division.values())
    print(f"   {'Total':8s}: {total_teams:3d} teams")

    # Pattern breakdown
    print(f"\n2. TEAMS BY URL PATTERN")
    print("-" * 80)
    for pattern in sorted(teams_by_pattern.keys()):
        teams = teams_by_pattern[pattern]
        count = len(teams)
        pct = (count / total_teams * 100) if total_teams > 0 else 0
        print(f"   {pattern:15s}: {count:3d} teams ({pct:5.1f}%)")

    # Show pattern examples
    print(f"\n3. URL PATTERN EXAMPLES")
    print("-" * 80)

    for pattern, teams in sorted(teams_by_pattern.items()):
        print(f"\n   Pattern: {pattern}")
        for team in teams[:3]:
            print(f"      {team['team']:30s} - {team['url']}")

    # Test sample URLs
    print(f"\n4. TESTING SAMPLE URLs (season=2025)")
    print("-" * 80)

    results_by_pattern = defaultdict(list)

    for pattern, teams in sorted(teams_by_pattern.items()):
        print(f"\n   Testing {pattern} pattern ({min(sample_per_pattern, len(teams))} samples)...")

        for i, team in enumerate(teams[:sample_per_pattern], 1):
            print(f"      {i}. {team['team']:25s} ... ", end='', flush=True)

            result = test_url_with_season(team['url'])
            results_by_pattern[pattern].append({
                'team': team,
                'result': result
            })

            if result['status'] == 200:
                if result['has_sidearm']:
                    print(f"✓ 200 (Sidearm HTML)")
                elif result['has_table']:
                    print(f"✓ 200 (Table HTML)")
                else:
                    print(f"⚠ 200 (Unknown structure)")
            elif result['status']:
                print(f"✗ {result['status']}")
            else:
                print(f"✗ {result['error']}")

    # Analysis summary
    print(f"\n5. SCRAPING STRATEGY RECOMMENDATIONS")
    print("-" * 80)

    for pattern, results in sorted(results_by_pattern.items()):
        print(f"\n   Pattern: {pattern}")

        successful = [r for r in results if r['result']['status'] == 200]
        has_sidearm = [r for r in successful if r['result']['has_sidearm']]
        has_table = [r for r in successful if r['result']['has_table']]

        print(f"      Tested: {len(results)} teams")
        print(f"      Success (200): {len(successful)}")
        print(f"      Has Sidearm HTML: {len(has_sidearm)}")
        print(f"      Has Table HTML: {len(has_table)}")

        if len(has_sidearm) > 0:
            print(f"      → Recommendation: Use StandardScraper")
        elif len(has_table) > 0:
            print(f"      → Recommendation: Use TableScraper")
        else:
            print(f"      → Recommendation: Needs investigation")

    # Generate TeamConfig data
    print(f"\n6. TEAMCONFIG POPULATION DATA")
    print("-" * 80)

    for pattern, teams in sorted(teams_by_pattern.items()):
        print(f"\n   # {pattern.upper()} pattern ({len(teams)} teams)")
        print(f"   # Sample team IDs:")

        # Show first 10 team IDs
        for team in teams[:10]:
            url_format = 'default' if pattern == 'sidearm' else pattern
            print(f"   {team['ncaa_id']:8s}: {{'url_format': '{url_format}', 'notes': '{team['team']}'}}  # Division {team['division']}")

        if len(teams) > 10:
            print(f"   # ... and {len(teams) - 10} more teams")

    print("\n" + "=" * 80)
    print("Analysis Complete!")
    print("=" * 80)

    return teams_by_pattern, results_by_pattern


if __name__ == '__main__':
    csv_path = 'data/input/teams.csv'
    teams_by_pattern, results_by_pattern = analyze_teams(csv_path, sample_per_pattern=5)

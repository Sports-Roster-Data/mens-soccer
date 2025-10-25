#!/usr/bin/env python3
"""
Test StandardScraper with msoc_index pattern

Tests that our URL auto-detection and building works for
teams with /sports/msoc/index URLs.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from soccer_roster_scraper import StandardScraper, TeamConfig, URLBuilder

def test_msoc_pattern():
    """Test StandardScraper with American Int'l (msoc_index pattern)"""

    print("=" * 80)
    print("Testing msoc_index Pattern with American Int'l")
    print("=" * 80)

    # American Int'l details from teams.csv
    team_id = 588199
    team_name = "American Int'l"
    team_url = "https://www.aicyellowjackets.com/sports/msoc/index"
    division = "II"
    season = "2025"

    print(f"\n1. Team Configuration")
    print(f"   Team: {team_name}")
    print(f"   Team ID: {team_id}")
    print(f"   Team URL: {team_url}")
    print(f"   Pattern: msoc_index")

    # Test URL building
    url_format = TeamConfig.get_url_format(team_id, team_url)
    roster_url = URLBuilder.build_roster_url(team_url, season, url_format)

    print(f"\n2. URL Auto-Detection")
    print(f"   Detected Format: {url_format}")
    print(f"   Roster URL: {roster_url}")
    print(f"   Expected: https://www.aicyellowjackets.com/sports/msoc/roster/2025")

    # Test scraping
    print(f"\n3. Scraping Roster")
    scraper = StandardScraper()
    players = scraper.scrape_team(team_id, team_name, team_url, season, division)

    print(f"\n4. Results")
    print(f"   Total Players: {len(players)}")

    if players:
        print(f"\n5. Sample Players (first 3):")
        for i, player in enumerate(players[:3], 1):
            print(f"\n   Player {i}: {player.name}")
            print(f"      Jersey: {player.jersey}")
            print(f"      Position: {player.position}")
            print(f"      Year: {player.year}")
            print(f"      URL: {player.url}")

        print("\n" + "=" * 80)
        print(f"✓ msoc_index pattern test: PASSED")
        print(f"✓ Successfully scraped {len(players)} players")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("✗ msoc_index pattern test: FAILED")
        print("=" * 80)

    return players


if __name__ == '__main__':
    players = test_msoc_pattern()

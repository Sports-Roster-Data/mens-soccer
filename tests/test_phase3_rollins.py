#!/usr/bin/env python3
"""
Test StandardScraper with Rollins (msoc_plain pattern)

Rollins uses /sports/msoc without /index, making it unique among the 4 "other" teams.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from soccer_roster_scraper import StandardScraper, TeamConfig, URLBuilder

def test_rollins():
    """Test StandardScraper with Rollins (msoc_plain pattern)"""

    print("=" * 80)
    print("Testing msoc_plain Pattern with Rollins")
    print("=" * 80)

    # Rollins details from teams.csv
    team_id = 584
    team_name = "Rollins"
    team_url = "https://rollinssports.com/sports/msoc"
    division = "II"
    season = "2025"

    print(f"\n1. Team Configuration")
    print(f"   Team: {team_name}")
    print(f"   Team ID: {team_id}")
    print(f"   Team URL: {team_url}")
    print(f"   Pattern: msoc_plain (no /index)")

    # Test URL building
    url_format = TeamConfig.get_url_format(team_id, team_url)
    roster_url = URLBuilder.build_roster_url(team_url, season, url_format)

    print(f"\n2. URL Auto-Detection")
    print(f"   Detected Format: {url_format}")
    print(f"   Roster URL: {roster_url}")
    print(f"   Expected: https://rollinssports.com/sports/msoc/roster/2025")

    if url_format != 'msoc_plain':
        print(f"\n✗ ERROR: Expected 'msoc_plain', got '{url_format}'")
        return []

    # Test scraping
    print(f"\n3. Scraping Roster")
    scraper = StandardScraper()
    players = scraper.scrape_team(team_id, team_name, team_url, season, division)

    print(f"\n4. Results")
    print(f"   Total Players: {len(players)}")

    if players:
        print(f"\n5. Sample Players (first 5):")
        for i, player in enumerate(players[:5], 1):
            print(f"\n   Player {i}: {player.name}")
            print(f"      Jersey: {player.jersey}")
            print(f"      Position: {player.position}")
            print(f"      Height: {player.height}")
            print(f"      Year: {player.year}")

        # Field coverage
        stats = {
            'Jersey': sum(1 for p in players if p.jersey),
            'Position': sum(1 for p in players if p.position),
            'Height': sum(1 for p in players if p.height),
            'Year': sum(1 for p in players if p.year),
        }

        print(f"\n6. Field Coverage")
        total = len(players)
        for field, count in stats.items():
            pct = (count / total * 100) if total > 0 else 0
            print(f"   {field:10s}: {count:2d}/{total} ({pct:5.1f}%)")

        print("\n" + "=" * 80)
        print(f"✓ msoc_plain pattern test: PASSED")
        print(f"✓ Successfully scraped {len(players)} players from Rollins")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("✗ msoc_plain pattern test: FAILED")
        print("=" * 80)

    return players


if __name__ == '__main__':
    players = test_rollins()

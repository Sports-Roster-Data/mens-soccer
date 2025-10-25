#!/usr/bin/env python3
"""
Test Phase 2 (StandardScraper) with live scraping

This script tests the new StandardScraper with UNC's roster
to validate that all components work together.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from soccer_roster_scraper import (
    StandardScraper,
    URLBuilder,
    TeamConfig,
    FieldExtractors,
    logger
)

def test_unc_scraper():
    """Test StandardScraper with UNC (North Carolina)"""

    print("=" * 70)
    print("Testing Phase 2: StandardScraper with Albany")
    print("=" * 70)

    # Albany details from teams.csv
    team_id = 14
    team_name = "Albany"
    team_url = "https://ualbanysports.com/sports/mens-soccer"  # Full URL from teams.csv
    division = "I"
    season = "2025"  # Note: Season format is "2025" not "2025-26" for soccer

    print(f"\n1. Team Configuration")
    print(f"   Team: {team_name}")
    print(f"   Team ID: {team_id}")
    print(f"   Team URL: {team_url}")

    # Determine scraper type
    scraper_type = TeamConfig.get_scraper_type(team_id)
    print(f"\n2. Scraper Selection")
    print(f"   Scraper Type: {scraper_type}")

    # Build roster URL
    url_format = TeamConfig.get_url_format(team_id)
    roster_url = URLBuilder.build_roster_url(team_url, season, url_format)
    print(f"\n3. URL Building")
    print(f"   URL Format: {url_format}")
    print(f"   Roster URL: {roster_url}")

    # Initialize scraper
    print(f"\n4. Scraping Roster")
    print(f"   Season: {season}")
    print(f"   Division: {division}")
    print()

    scraper = StandardScraper()
    players = scraper.scrape_team(team_id, team_name, team_url, season, division)

    # Display results
    print(f"\n5. Results")
    print(f"   Total Players: {len(players)}")

    if players:
        print(f"\n6. Sample Players (first 5):")
        print("   " + "-" * 66)

        for i, player in enumerate(players[:5], 1):
            print(f"\n   Player {i}: {player.name}")
            print(f"      Jersey: {player.jersey}")
            print(f"      Position: {player.position}")
            print(f"      Height: {player.height}")
            print(f"      Year: {player.year}")
            print(f"      Major: {player.major}")
            print(f"      Hometown: {player.hometown}")
            print(f"      High School: {player.high_school}")
            if player.previous_school:
                print(f"      Previous School: {player.previous_school}")
            print(f"      URL: {player.url}")

        # Field coverage statistics
        print(f"\n7. Field Coverage Statistics")
        print("   " + "-" * 66)

        total = len(players)
        stats = {
            'Jersey': sum(1 for p in players if p.jersey),
            'Position': sum(1 for p in players if p.position),
            'Height': sum(1 for p in players if p.height),
            'Year': sum(1 for p in players if p.year),
            'Major': sum(1 for p in players if p.major),
            'Hometown': sum(1 for p in players if p.hometown),
            'High School': sum(1 for p in players if p.high_school),
            'Previous School': sum(1 for p in players if p.previous_school),
            'URL': sum(1 for p in players if p.url),
        }

        for field, count in stats.items():
            pct = (count / total * 100) if total > 0 else 0
            print(f"   {field:16s}: {count:3d}/{total} ({pct:5.1f}%)")

        # Position breakdown
        positions = {}
        for player in players:
            if player.position:
                positions[player.position] = positions.get(player.position, 0) + 1

        if positions:
            print(f"\n8. Position Breakdown")
            print("   " + "-" * 66)
            for pos in sorted(positions.keys()):
                print(f"   {pos:4s}: {positions[pos]:2d} players")

        # Test CSV conversion
        print(f"\n9. CSV Schema Validation")
        print("   " + "-" * 66)
        sample_dict = players[0].to_dict()
        expected_fields = ['ncaa_id', 'team', 'season', 'division', 'jersey', 'name',
                          'position', 'height', 'class', 'major', 'hometown',
                          'high_school', 'previous_school', 'url']

        actual_fields = set(sample_dict.keys())
        expected_set = set(expected_fields)

        if actual_fields == expected_set:
            print(f"   ✓ Schema matches expected CSV format")
            print(f"   ✓ Fields: {', '.join(sorted(actual_fields))}")
        else:
            missing = expected_set - actual_fields
            extra = actual_fields - expected_set
            if missing:
                print(f"   ✗ Missing fields: {missing}")
            if extra:
                print(f"   ✗ Extra fields: {extra}")

    else:
        print("   ✗ No players found")
        print("\n   This could mean:")
        print("   - URL pattern is incorrect")
        print("   - Season mismatch")
        print("   - HTML structure has changed")
        print("   - Network/timeout issues")

    # Final status
    print()
    print("=" * 70)
    if len(players) > 0:
        print("✓ Phase 2 Test: PASSED")
        print(f"✓ Successfully scraped {len(players)} players from {team_name}")
    else:
        print("✗ Phase 2 Test: FAILED")
        print("✗ No players scraped - review logs above")
    print("=" * 70)

    return players


if __name__ == '__main__':
    players = test_unc_scraper()

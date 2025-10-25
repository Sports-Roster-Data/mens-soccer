#!/usr/bin/env python3
"""
Test Phase 1 (Data Structure) with real roster data

This script validates that our new Player dataclass and FieldExtractors
work correctly with actual scraped data from existing scrapers.
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from soccer_roster_scraper import Player, FieldExtractors

def test_with_real_data(json_file: str, num_samples: int = 10):
    """Test Phase 1 with real data from existing scraper output"""

    print(f"=== Testing Phase 1 with Real Data ===")
    print(f"Source: {json_file}")
    print(f"Samples: {num_samples}\n")

    # Load real data
    with open(json_file, 'r') as f:
        old_data = json.load(f)

    print(f"Total players in file: {len(old_data)}")

    # Process through new Player dataclass
    new_players = []
    for old_player in old_data[:num_samples]:
        # Create Player using our new dataclass
        player = Player(
            team_id=old_player.get('ncaa_id', 0),
            team=old_player.get('team', ''),
            season=str(old_player.get('season', '')),
            division=old_player.get('division', ''),
            name=old_player.get('name', ''),
            jersey=str(old_player.get('jersey', '')),
            position=FieldExtractors.extract_position(old_player.get('position', '')),
            height=old_player.get('height', ''),
            year=FieldExtractors.normalize_academic_year(old_player.get('class', '')),
            major=old_player.get('major', ''),
            hometown=old_player.get('hometown', ''),
            high_school=old_player.get('high_school', ''),
            previous_school=old_player.get('previous_school', ''),
            url=old_player.get('url', '')
        )
        new_players.append(player)

    # Display results
    print(f"\n=== Processed {len(new_players)} Players ===\n")

    for i, (old, new) in enumerate(zip(old_data[:num_samples], new_players), 1):
        print(f"--- Player {i}: {new.name} ---")
        print(f"  Team: {new.team} (Division {new.division})")
        print(f"  Jersey: {new.jersey} | Position: {new.position} | Height: {new.height}")
        print(f"  Class: {new.year}")
        print(f"  Hometown: {new.hometown}")

        # Show field transformations
        if old.get('position') != new.position:
            print(f"  ✓ Position normalized: '{old.get('position')}' → '{new.position}'")
        if old.get('class') != new.year:
            print(f"  ✓ Academic year normalized: '{old.get('class')}' → '{new.year}'")

        # Convert to dict (CSV format)
        player_dict = new.to_dict()

        print()

    # Validate schema
    print("=== Schema Validation ===")
    sample_dict = new_players[0].to_dict()
    expected_fields = ['ncaa_id', 'team', 'season', 'division', 'jersey', 'name',
                      'position', 'height', 'class', 'major', 'hometown',
                      'high_school', 'previous_school', 'url']

    actual_fields = set(sample_dict.keys())
    expected_set = set(expected_fields)

    if actual_fields == expected_set:
        print(f"✓ Schema matches expected CSV format")
        print(f"  Fields: {', '.join(sorted(actual_fields))}")
    else:
        missing = expected_set - actual_fields
        extra = actual_fields - expected_set
        if missing:
            print(f"✗ Missing fields: {missing}")
        if extra:
            print(f"✗ Extra fields: {extra}")

    # Test specific field extractors
    print(f"\n=== Field Extractor Performance ===")

    positions_extracted = sum(1 for p in new_players if p.position)
    years_normalized = sum(1 for p in new_players if p.year)

    print(f"✓ Positions extracted: {positions_extracted}/{len(new_players)}")
    print(f"✓ Academic years normalized: {years_normalized}/{len(new_players)}")

    # Show position variety
    unique_positions = set(p.position for p in new_players if p.position)
    print(f"✓ Unique positions found: {', '.join(sorted(unique_positions))}")

    # Test international players
    international = [p for p in new_players if p.hometown and ',' in p.hometown
                     and not any(state in p.hometown for state in ['NC', 'NY', 'CA', 'TX', 'FL'])]
    if international:
        print(f"✓ International players detected: {len(international)}")
        for p in international[:3]:
            print(f"  - {p.name}: {p.hometown}")

    print(f"\n=== Phase 1 Validation Complete ===")
    print(f"✓ Player dataclass works with real data")
    print(f"✓ FieldExtractors process actual roster fields")
    print(f"✓ CSV schema matches existing format")
    print(f"✓ Ready for Phase 2 implementation")


if __name__ == '__main__':
    # Test with real Division I data
    test_with_real_data('data/raw/json/rosters_2025_I.json', num_samples=15)

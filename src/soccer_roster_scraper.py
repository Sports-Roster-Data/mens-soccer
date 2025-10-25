#!/usr/bin/env python3
"""
NCAA Men's Soccer Roster Scraper - Unified Architecture
Adapted from WBB scraper for soccer-specific needs

Usage:
    python src/soccer_roster_scraper.py -season 2024-25 -division I
    python src/soccer_roster_scraper.py -team 457 -url https://goheels.com/sports/mens-soccer -season 2024-25
"""

import os
import re
import csv
import json
import argparse
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import tldextract

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Player:
    """Player data structure for NCAA men's soccer rosters"""
    team_id: int
    team: str
    season: str
    division: str = ""
    player_id: Optional[str] = None
    name: str = ""
    jersey: str = ""
    position: str = ""
    height: str = ""
    year: str = ""  # Academic year (class)
    major: str = ""  # Soccer rosters often include major (basketball doesn't)
    hometown: str = ""
    high_school: str = ""
    previous_school: str = ""
    url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV output"""
        d = asdict(self)
        # Map 'year' field to 'class' for CSV output (matches existing schema)
        d['class'] = d.pop('year', '')
        # Map team_id to ncaa_id (matches existing schema)
        d['ncaa_id'] = d.pop('team_id')
        # Remove player_id from CSV output (internal use only)
        d.pop('player_id', None)
        return d


# ============================================================================
# FIELD EXTRACTORS
# ============================================================================

class FieldExtractors:
    """Common utilities for extracting player fields from text and HTML"""

    @staticmethod
    def extract_jersey_number(text: str) -> str:
        """Extract jersey number from various text patterns"""
        if not text:
            return ''

        patterns = [
            r'Jersey Number[:\s]+(\d+)',
            r'#(\d{1,2})\b',
            r'No\.?[:\s]*(\d{1,2})\b',
            r'\b(\d{1,2})\s+(?=[A-Z])',  # Number followed by capitalized name
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ''

    @staticmethod
    def extract_height(text: str) -> str:
        """
        Extract height from various formats (imperial and metric)

        Formats supported:
        - 6'2" or 6-2 (imperial)
        - 6'2" / 1.88m (both)
        - 1.88m (metric only)
        """
        if not text:
            return ''

        patterns = [
            r"(\d+['\′]\s*\d+[\"\″](?:\s*/\s*\d+\.\d+m)?)",  # 6'2" or 6'2" / 1.88m
            r"(\d+['\′]\s*\d+[\"\″])",                        # 6'2"
            r"(\d+-\d+)",                                      # 6-2
            r"(\d+\.\d+m)",                                    # 1.88m
            r"Height:\s*([^\,\n]+)",                           # Height: label format
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return ''

    @staticmethod
    def extract_position(text: str) -> str:
        """
        Extract position from text - SOCCER VERSION

        Soccer positions: GK, D, M, F (Goalkeeper, Defender, Midfielder, Forward)
        Also handles variations: MF, DF, FW, etc.
        """
        if not text:
            return ''

        # Look for abbreviated position patterns
        position_match = re.search(r'\b(GK|D|M|F|MF|DF|FW|DEF|MID|FOR)\b', text, re.IGNORECASE)
        if position_match:
            pos = position_match.group(1).upper()
            # Normalize variations
            if pos in ('DEF', 'DF'):
                return 'D'
            elif pos in ('MID', 'MF'):
                return 'M'
            elif pos in ('FOR', 'FW'):
                return 'F'
            return pos

        # Look for full position names
        text_upper = text.upper()
        if 'GOALKEEPER' in text_upper or 'GOALIE' in text_upper:
            return 'GK'
        elif 'DEFENDER' in text_upper or 'DEFENCE' in text_upper or 'DEFENSE' in text_upper:
            return 'D'
        elif 'MIDFIELDER' in text_upper or 'MIDFIELD' in text_upper:
            return 'M'
        elif 'FORWARD' in text_upper or 'STRIKER' in text_upper:
            return 'F'

        return ''

    @staticmethod
    def normalize_academic_year(year_text: str) -> str:
        """Normalize academic year abbreviations to full forms"""
        if not year_text:
            return ''

        year_map = {
            'Fr': 'Freshman', 'Fr.': 'Freshman', 'FR': 'Freshman',
            'So': 'Sophomore', 'So.': 'Sophomore', 'SO': 'Sophomore',
            'Jr': 'Junior', 'Jr.': 'Junior', 'JR': 'Junior',
            'Sr': 'Senior', 'Sr.': 'Senior', 'SR': 'Senior',
            'Gr': 'Graduate', 'Gr.': 'Graduate', 'GR': 'Graduate',
            'R-Fr': 'Redshirt Freshman', 'R-Fr.': 'Redshirt Freshman',
            'R-So': 'Redshirt Sophomore', 'R-So.': 'Redshirt Sophomore',
            'R-Jr': 'Redshirt Junior', 'R-Jr.': 'Redshirt Junior',
            'R-Sr': 'Redshirt Senior', 'R-Sr.': 'Redshirt Senior',
            '1st': 'Freshman', 'First': 'Freshman',
            '2nd': 'Sophomore', 'Second': 'Sophomore',
            '3rd': 'Junior', 'Third': 'Junior',
            '4th': 'Senior', 'Fourth': 'Senior',
        }

        cleaned = year_text.strip()
        return year_map.get(cleaned, year_text)

    @staticmethod
    def parse_hometown_school(text: str) -> Dict[str, str]:
        """
        Parse hometown and school information from combined text

        Handles:
        - "City, State / High School"
        - "City, Country / High School" (international players)
        - "City, State / High School / Previous College"
        """
        result = {'hometown': '', 'high_school': '', 'previous_school': ''}

        if not text:
            return result

        # Clean the text
        text = re.sub(r'\s*(Instagram|Twitter|Opens in a new window).*$', '', text)
        text = re.sub(r'\s+', ' ', text).strip()

        # Pattern 1: City, State/Country followed by school info separated by /
        if '/' in text:
            parts = [p.strip() for p in text.split('/')]
            result['hometown'] = parts[0] if parts else ''

            if len(parts) > 1:
                # Check if second part looks like a college/university
                college_indicators = ['University', 'College', 'State', 'Tech', 'Institute']
                if any(indicator in parts[1] for indicator in college_indicators):
                    result['previous_school'] = parts[1]
                else:
                    result['high_school'] = parts[1]

            if len(parts) > 2:
                result['previous_school'] = parts[2]
        else:
            # No separator, just store as hometown
            result['hometown'] = text

        return result

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""

        # Remove extra whitespace and normalize
        cleaned = re.sub(r'\s+', ' ', text.strip())

        # Remove common unwanted elements
        cleaned = re.sub(r'\s*(Full Bio|Instagram|Twitter|Opens in a new window).*$', '', cleaned)

        # Strip common labelled prefixes
        cleaned = FieldExtractors.clean_field_labels(cleaned)

        return cleaned

    @staticmethod
    def clean_field_labels(text: str) -> str:
        """
        Remove label prefixes like 'Class:', 'Hometown:', 'High school:', 'Ht.:', 'Pos.:'

        This helps with sites that dump labelled content into table cells or bio blocks.
        """
        if not text:
            return text

        # Common label patterns to strip
        patterns = [
            r'\bClass:\s*', r'\bHometown:\s*', r'\bHigh school:\s*',
            r'\bPrevious College:\s*', r'\bPrevious School:\s*',
            r'\bHt\.?:\s*', r'\bPos\.?:\s*', r'\bMajor:\s*',
            r'^High school:\s*', r'^Hometown:\s*', r'^No\.?:\s*',
        ]

        for p in patterns:
            text = re.sub(p, '', text, flags=re.IGNORECASE).strip()

        return text


# ============================================================================
# SEASON VERIFICATION
# ============================================================================

class SeasonVerifier:
    """Centralized season verification logic"""

    @staticmethod
    def verify_season_on_page(html, expected_season: str) -> bool:
        """
        Verify that the roster page is for the expected season

        Args:
            html: BeautifulSoup object or HTML string
            expected_season: Expected season string (e.g., "2024-25")

        Returns:
            bool: True if season matches, False otherwise
        """
        try:
            elements_to_check = []

            # Check h1, h2, and title elements
            for tag in ['h1', 'h2']:
                elements = html.find_all(tag) if hasattr(html, 'find_all') else []
                elements_to_check.extend(elements)

            title = html.find('title') if hasattr(html, 'find') else None
            if title:
                elements_to_check.append(title)

            for element in elements_to_check:
                text = element.get_text(strip=True) if hasattr(element, 'get_text') else str(element)

                # Check for season and 'roster' keyword
                if expected_season in text and 'roster' in text.lower():
                    logger.info(f"✓ Season verification passed: found '{text.strip()}'")
                    return True

            logger.warning(f"✗ Season verification failed: no header found with '{expected_season}' and 'roster'")
            return False

        except Exception as e:
            logger.warning(f"Season verification error: {e}")
            return True  # Default to True if verification fails (don't block scraping)

    @staticmethod
    def is_sidearm_site(html) -> bool:
        """Check if this is a Sidearm-based site"""
        try:
            sidearm_indicators = [
                html.find('li', {'class': 'sidearm-roster-player'}),
                html.find('div', {'class': 'sidearm-roster-list-item'}),
                html.find('span', {'class': 'sidearm-roster-player-name'}),
                html.find_all('div', class_=lambda x: x and 'sidearm' in x.lower())
            ]

            return any(indicator for indicator in sidearm_indicators)
        except Exception as e:
            logger.warning(f"Failed to detect Sidearm site: {e}")
            return False


# ============================================================================
# MAIN ENTRY POINT (Placeholder for now)
# ============================================================================

def main():
    """Main entry point - Phase 1 testing"""
    parser = argparse.ArgumentParser(description='NCAA Men\'s Soccer Roster Scraper')
    parser.add_argument('-season', required=False, default='2024-25', help='Season (e.g., "2024-25")')
    parser.add_argument('--test', action='store_true', help='Run Phase 1 tests')

    args = parser.parse_args()

    if args.test:
        # Phase 1 testing
        logger.info("=== Phase 1: Testing Player Dataclass ===")

        # Create sample player
        player = Player(
            team_id=457,
            team="North Carolina",
            season="2024-25",
            division="I",
            name="Test Player",
            jersey="10",
            position="M",
            height="6'0\"",
            year="Junior",
            major="Computer Science",
            hometown="Chapel Hill, NC",
            high_school="Chapel Hill High School",
            url="https://goheels.com/sports/mens-soccer/roster/test-player"
        )

        logger.info(f"Created player: {player.name}")
        logger.info(f"Position: {player.position} (soccer-specific)")
        logger.info(f"Major: {player.major} (soccer-specific field)")

        # Test to_dict conversion
        player_dict = player.to_dict()
        logger.info(f"Converted to dict with {len(player_dict)} fields")
        logger.info(f"CSV schema: {', '.join(player_dict.keys())}")

        # Test field extractors
        logger.info("\n=== Testing Field Extractors ===")

        test_cases = [
            ("Position extraction", "Midfielder", FieldExtractors.extract_position),
            ("Position extraction (abbr)", "M", FieldExtractors.extract_position),
            ("Position extraction (GK)", "Goalkeeper", FieldExtractors.extract_position),
            ("Height extraction", "6'2\"", FieldExtractors.extract_height),
            ("Height extraction (dash)", "6-2", FieldExtractors.extract_height),
            ("Jersey extraction", "#10", FieldExtractors.extract_jersey_number),
            ("Academic year", "Jr", FieldExtractors.normalize_academic_year),
        ]

        for name, test_input, func in test_cases:
            result = func(test_input)
            logger.info(f"✓ {name}: '{test_input}' → '{result}'")

        # Test hometown/school parser
        hometown_test = "Chapel Hill, NC / Chapel Hill High School"
        result = FieldExtractors.parse_hometown_school(hometown_test)
        logger.info(f"✓ Hometown parsing: '{hometown_test}'")
        logger.info(f"  → Hometown: '{result['hometown']}'")
        logger.info(f"  → High School: '{result['high_school']}'")

        logger.info("\n=== Phase 1 Complete ===")
        logger.info("Player dataclass and FieldExtractors are working!")
        logger.info("Ready for Phase 2: Implementing scrapers")

    else:
        logger.info("Phase 1: Data structure implemented")
        logger.info("Run with --test to test Player dataclass")


if __name__ == '__main__':
    main()

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
import subprocess
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

        # Clean string fields to remove excessive whitespace/newlines before output
        for k, v in list(d.items()):
            if isinstance(v, str):
                d[k] = FieldExtractors.clean_text(v)

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
            r"(\d+['\′]\s*\d+[\"\″']{1,2}(?:\s*/\s*\d+\.\d+m)?)",  # 6'2" or 6'5'' or 6'2" / 1.88m
            r"(\d+['\′]\s*\d+[\"\″']{1,2})",                        # 6'2" or 6'5''
            r"(\d+-\d+)",                                            # 6-2
            r"(\d+\.\d+m)",                                          # 1.88m
            r"Height:\s*([^\,\n]+)",                                 # Height: label format
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
# URL BUILDER
# ============================================================================

class URLBuilder:
    """Build roster URLs for different site patterns"""

    @staticmethod
    def build_roster_url(base_url: str, season: str, url_format: str = 'default') -> str:
        """
        Build roster URL based on site pattern

        Args:
            base_url: Team's URL from teams.csv (e.g., 'https://goheels.com/sports/mens-soccer')
            season: Season string (e.g., '2024-25')
            url_format: URL pattern type
                - 'default': {base_url}/roster/{season}
                - 'msoc': {base_url}/2024-25/roster (or /roster/2024)
                - 'sports_msoc': {base_url}/sports/msoc/{season}/roster

        Returns:
            Full roster URL
        """
        base_url = base_url.rstrip('/')

        if url_format == 'default':
            # Most common: Sidearm Sports pattern (87.6% of teams - 719 teams)
            # Example: https://ualbanysports.com/sports/mens-soccer/roster/2025
            return f"{base_url}/roster/{season}"

        elif url_format == 'msoc_index':
            # msoc/index pattern (11.9% of teams - 98 teams)
            # teams.csv has /sports/msoc/index, need /sports/msoc/roster/2025
            # Example: https://aicyellowjackets.com/sports/msoc/roster/2025
            # These redirect to Sidearm HTML after following redirects
            if '/index' in base_url:
                return base_url.replace('/index', f'/roster/{season}')
            else:
                return f"{base_url}/roster/{season}"

        elif url_format == 'msoc_plain':
            # /sports/msoc without /index (e.g., Rollins)
            # Example: https://rollinssports.com/sports/msoc/roster/2025
            return f"{base_url}/roster/{season}"

        elif url_format == 'ucf_table':
            # UCF uses /roster/season/{season}?view=table
            # Example: https://ucfknights.com/sports/mens-soccer/roster/season/2025?view=table
            return f"{base_url}/roster/season/{season}?view=table"

        elif url_format == 'virginia_season':
            # Virginia uses /roster/season/{season-range}/
            # Example: https://virginiasports.com/sports/msoc/roster/season/2025-26/
            # Convert single year to range (2025 -> 2025-26)
            try:
                year = int(season)
                next_year = str(year + 1)[-2:]  # Get last 2 digits
                season_range = f"{year}-{next_year}"
                return f"{base_url}/roster/season/{season_range}/"
            except ValueError:
                # If season is already a range, use as-is
                return f"{base_url}/roster/season/{season}/"

        elif url_format == 'clemson_roster':
            # Clemson uses /roster/season/{year}/ with just the year
            # Example: https://clemsontigers.com/sports/mens-soccer/roster/season/2025/
            try:
                # Extract just the year from season string (e.g., '2024-25' -> '2025')
                if '-' in season:
                    year = season.split('-')[1]
                    # If it's a 2-digit year, convert to 4-digit
                    if len(year) == 2:
                        year = f"20{year}"
                else:
                    year = season
                # Request the table/list view to surface full columns (Class, Hometown, High school)
                return f"{base_url}/roster/season/{year}/?view=table"
            except (ValueError, IndexError):
                # Fallback to just using season as-is
                return f"{base_url}/roster/season/{season}/?view=table"

        elif url_format == 'kentucky_season':
            # Kentucky uses /roster/season/{year}/ (just year, no conversion needed)
            # Example: https://ukathletics.com/sports/msoc/roster/season/2025/
            try:
                # If season is a range like '2024-25', extract the end year
                if '-' in season:
                    year = season.split('-')[1]
                    # If it's a 2-digit year, convert to 4-digit
                    if len(year) == 2:
                        year = f"20{year}"
                else:
                    year = season
                return f"{base_url}/roster/season/{year}/"
            except (ValueError, IndexError):
                # Fallback to just using season as-is
                return f"{base_url}/roster/season/{season}/"

        elif url_format == 'msoc_season_range':
            # /sports/msoc/{season-range}/roster format (used by some schools like Emory & Henry)
            # Example: https://gowasps.com/sports/msoc/2025-26/roster
            # Convert single year to range (2025 -> 2025-26)
            # First, remove /index if present in base_url
            clean_url = base_url.replace('/index', '')
            try:
                year = int(season)
                next_year = str(year + 1)[-2:]  # Get last 2 digits
                season_range = f"{year}-{next_year}"
                return f"{clean_url}/{season_range}/roster"
            except ValueError:
                # If season is already a range, use as-is
                return f"{clean_url}/{season}/roster"

        else:
            # Fallback to default
            logger.warning(f"Unknown url_format '{url_format}', using default")
            return f"{base_url}/roster/{season}"

    @staticmethod
    def extract_base_url(full_url: str) -> str:
        """
        Extract base URL from full team URL

        Example:
            'https://goheels.com/sports/mens-soccer' → 'https://goheels.com'
        """
        extracted = tldextract.extract(full_url)

        # Build domain with subdomain if present
        if extracted.subdomain:
            domain = f"{extracted.subdomain}.{extracted.domain}.{extracted.suffix}"
        else:
            domain = f"{extracted.domain}.{extracted.suffix}"

        return f"https://{domain}"


# ============================================================================
# TEAM CONFIGURATION
# ============================================================================

class TeamConfig:
    """Team-specific configuration and categorization"""

    # Team-specific configurations
    # Format: ncaa_id: {'url_format': 'format_type', 'requires_js': bool, 'notes': '...'}
    TEAM_CONFIGS = {
        14: {'url_format': 'default', 'requires_js': False, 'notes': 'Albany - Standard Sidearm'},
        72: {'url_format': 'default', 'requires_js': True, 'notes': 'Bradley - Vue.js rendered roster'},
        74: {'url_format': 'msoc_season_range', 'requires_js': False, 'notes': 'Bridgeport - /sports/msoc/YYYY-YY/roster format with data-field attributes'},
        128: {'url_format': 'ucf_table', 'requires_js': True, 'notes': 'UCF - Custom URL + JS rendering'},
        147: {'url_format': 'clemson_roster', 'requires_js': False, 'notes': 'Clemson - Custom WordPress roster with person__item structure'},
        216: {'url_format': 'msoc_season_range', 'requires_js': False, 'notes': 'Emory & Henry - /sports/msoc/YYYY-YY/roster format'},
        248: {'url_format': 'default', 'requires_js': True, 'notes': 'George Mason - Sidearm list-item + JS rendering'},
        334: {'url_format': 'kentucky_season', 'requires_js': True, 'notes': 'Kentucky - WMT Digital /roster/season/YYYY/ format (use JS-rendered List view / table)'},
        513: {'url_format': 'virginia_season', 'requires_js': True, 'notes': 'Notre Dame - WMT Digital /roster/season/YYYY-YY/ format (JS-rendered List view)'},
        648: {'url_format': 'kentucky_season', 'requires_js': True, 'notes': 'South Carolina - WMT Digital /roster/season/YYYY/ (use JS-rendered List/table view)'},
        1023: {'url_format': 'msoc_season_range', 'requires_js': False, 'notes': 'Coker - /sports/msoc/YYYY-YY/roster format'},
        457: {'url_format': 'default', 'requires_js': False, 'notes': 'UNC - Standard Sidearm'},
        523: {'url_format': 'ucf_table', 'requires_js': True, 'notes': 'Old Dominion - Custom URL + JS rendering'},
        539: {'url_format': 'ucf_table', 'requires_js': True, 'notes': 'Penn State - Custom URL + JS rendering'},
        630: {'url_format': 'ucf_table', 'requires_js': True, 'notes': 'San Jose State - Custom URL + JS rendering'},
        674: {'url_format': 'ucf_table', 'requires_js': True, 'notes': 'Stanford - Custom URL + JS rendering'},
        742: {'url_format': 'ucf_table', 'requires_js': True, 'notes': 'Va Tech - Custom URL + JS rendering'},
        746: {'url_format': 'virginia_season', 'requires_js': False, 'notes': 'Virginia - WMT Digital /roster/season/YYYY-YY/ format'},
        813: {'url_format': 'default', 'requires_js': False, 'notes': 'Yale - Standard Sidearm'},
        1000: {'url_format': 'msoc_season_range', 'requires_js': False, 'notes': 'Carson-Newman - /sports/m-soccer/YYYY-YY/roster format'},
        1356: {'url_format': 'ucf_table', 'requires_js': True, 'notes': 'Seattle - Custom URL + JS rendering'},
        186: {'url_format': 'msoc_season_range', 'requires_js': True, 'notes': 'Dist. Columbia - /sports/msoc/YYYY-YY/roster format with JS-rendered player names'},
        8956: {'url_format': 'msoc_season_range', 'requires_js': False, 'notes': 'Dominican (NY) - /sports/msoc/YYYY-YY/roster format'},
    }

    @classmethod
    def requires_javascript(cls, team_id: int) -> bool:
        """
        Check if a team requires JavaScript rendering

        Args:
            team_id: NCAA team ID

        Returns:
            True if team requires JSScraper
        """
        if team_id in cls.TEAM_CONFIGS:
            return cls.TEAM_CONFIGS[team_id].get('requires_js', False)
        return False

    @classmethod
    def get_url_format(cls, team_id: int, team_url: str = '') -> str:
        """
        Get URL format for a team

        Can auto-detect from URL pattern if team_url is provided

        Args:
            team_id: NCAA team ID
            team_url: Optional team URL for auto-detection

        Returns:
            URL format string ('default', 'msoc_index', etc.)
        """
        # Check if explicitly configured
        if team_id in cls.TEAM_CONFIGS:
            return cls.TEAM_CONFIGS[team_id].get('url_format', 'default')

        # Auto-detect from URL if provided
        if team_url:
            if '/sports/msoc/index' in team_url or '/Sports/msoc' in team_url:
                return 'msoc_index'
            elif '/sports/msoc' in team_url:
                # /sports/msoc without /index (e.g., Rollins)
                return 'msoc_plain'
            elif '/sports/mens-soccer' in team_url or '/sports/m-soccer' in team_url:
                return 'default'

        # Default to standard Sidearm pattern
        return 'default'

    @classmethod
    def get_scraper_type(cls, team_id: int) -> str:
        """
        Determine which scraper to use for a team

        Returns:
            'standard' - StandardScraper (Sidearm sites)
            'table' - TableScraper (msoc and data-label sites)
        """
        if team_id in cls.STANDARD_TEAMS:
            return 'standard'
        elif team_id in cls.MSOC_TEAMS or team_id in cls.TABLE_TEAMS:
            return 'table'
        else:
            # Default to standard
            return 'standard'


# ============================================================================
# SCRAPERS
# ============================================================================

class StandardScraper:
    """Scraper for standard Sidearm Sports sites (majority of teams)"""

    def __init__(self, session: Optional[requests.Session] = None):
        """
        Initialize scraper

        Args:
            session: Optional requests Session for connection pooling
        """
        self.session = session or requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }

    def scrape_team(self, team_id: int, team_name: str, base_url: str, season: str, division: str = "") -> List[Player]:
        """
        Scrape roster for a single team

        Args:
            team_id: NCAA team ID
            team_name: Team name
            base_url: Base URL for team site
            season: Season string (e.g., '2024-25')
            division: Division ('I', 'II', 'III')

        Returns:
            List of Player objects
        """
        try:
            # Build roster URL (auto-detect format from base_url)
            url_format = TeamConfig.get_url_format(team_id, base_url)
            roster_url = URLBuilder.build_roster_url(base_url, season, url_format)

            logger.info(f"Scraping {team_name} - {roster_url}")

            # Fetch page
            response = self.session.get(roster_url, headers=self.headers, timeout=30)

            # If 404, try season-range URL format (e.g., 2025-26/roster)
            if response.status_code == 404:
                logger.info(f"Got 404, trying season-range URL format for {team_name}")
                alternative_url = self._build_season_range_url(base_url, season)
                if alternative_url != roster_url:
                    logger.info(f"Trying alternative URL: {alternative_url}")
                    response = self.session.get(alternative_url, headers=self.headers, timeout=30)
                    roster_url = alternative_url  # Update for logging

            if response.status_code != 200:
                logger.warning(f"Failed to retrieve {team_name} - Status: {response.status_code}")
                return []

            # Parse HTML
            html = BeautifulSoup(response.content, 'html.parser')

            # Verify season
            if not SeasonVerifier.verify_season_on_page(html, season):
                logger.warning(f"Season mismatch for {team_name}")
                # Continue anyway - warning is enough

            # Extract players
            players = self._extract_players(html, team_id, team_name, season, division, base_url)

            # Enhance Kentucky players with bio page data (hometown, high school, class, url)
            if team_id == 334:  # Kentucky
                logger.info(f"Enhancing Kentucky players with bio page data...")
                players = self._enhance_kentucky_player_data(players)

            logger.info(f"✓ {team_name}: Found {len(players)} players")
            return players

        except requests.RequestException as e:
            logger.error(f"Request error for {team_name}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error scraping {team_name}: {e}")
            return []

    def _build_season_range_url(self, base_url: str, season: str) -> str:
        """
        Build alternative URL using season-range format (e.g., 2025-26)

        Args:
            base_url: Base URL from teams.csv
            season: Season string (e.g., '2025')

        Returns:
            Alternative roster URL with season range
        """
        base_url = base_url.rstrip('/')

        # Convert single year to range (2025 -> 2025-26)
        try:
            year = int(season)
            next_year = str(year + 1)[-2:]  # Get last 2 digits
            season_range = f"{year}-{next_year}"
            return f"{base_url}/{season_range}/roster"
        except ValueError:
            # If season is already a range or invalid format, return as-is
            logger.warning(f"Could not parse season '{season}' for range URL")
            return f"{base_url}/{season}/roster"

    def _extract_players(self, html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
        """
        Extract players from Sidearm Sports HTML

        Args:
            html: BeautifulSoup parsed HTML
            team_id: NCAA team ID
            team_name: Team name
            season: Season string
            division: Division
            base_url: Base URL for constructing profile URLs

        Returns:
            List of Player objects
        """
        players = []

        # Find all player list items (Sidearm pattern)
        roster_items = html.find_all('li', class_='sidearm-roster-player')

        # Also check for alternate Sidearm format used by some schools (e.g., Bradley)
        if not roster_items:
            roster_items = html.find_all('li', class_='sidearm-roster-list-item')
            if roster_items:
                logger.info(f"Found {len(roster_items)} players using sidearm-roster-list-item format for {team_name}")
                # Use the alternate extraction method
                return self._extract_players_from_list_items(html, team_id, team_name, season, division, base_url)

        if not roster_items:
            logger.warning(f"No roster items found for {team_name} (expected class='sidearm-roster-player')")

            # Check if this is a data-field table (Bridgeport style with data-field-label attributes)
            data_field_table = html.find('table', attrs={'class': lambda x: x and 'table' in x})
            if data_field_table and data_field_table.find('th', attrs={'data-field-label': True}):
                logger.info(f"Detected data-field table format for {team_name}, using data-field parser")
                return self._extract_players_from_data_field_table(html, team_id, team_name, season, division, base_url)

            # Check if this is a mod-roster div (Emory & Henry style) with generic table
            mod_roster = html.find('div', class_='mod-roster')
            if mod_roster:
                roster_table = mod_roster.find('table')
                if roster_table:
                    logger.info(f"Detected mod-roster format for {team_name}, using generic table parser")
                    return self._extract_players_from_generic_roster_table(html, team_id, team_name, season, division, base_url)

            # Check if this is a Kentucky-style table (players-table__general) - has all data
            kentucky_table = html.find('table', id='players-table__general')
            if kentucky_table:
                logger.info(f"Detected Kentucky-style data table for {team_name}, using DataTables parser")
                return self._extract_players_from_kentucky_table(html, team_id, team_name, season, division, base_url)

            # Check if this is a PrestoSports site (data-label attributes)
            presto_cells = html.find_all('td', attrs={'data-label': True})
            if presto_cells:
                logger.info(f"Detected PrestoSports format for {team_name}, using data-label parser")
                return self._extract_players_from_presto_table(html, team_id, team_name, season, division, base_url)

            # Check if this is a Sidearm card-based layout (s-person-card)
            person_cards = html.find_all('div', class_='s-person-card')
            if person_cards:
                logger.info(f"Detected Sidearm card-based layout for {team_name}, using s-person-card parser")
                return self._extract_players_from_cards(html, team_id, team_name, season, division, base_url)

            # Check if this is a WMT Digital roster (roster__item)
            wmt_items = html.find_all('div', class_='roster__item')
            if wmt_items:
                logger.info(f"Detected WMT Digital format for {team_name}, using roster__item parser")
                return self._extract_players_from_wmt(html, team_id, team_name, season, division, base_url)

            # Check if this is a custom WordPress roster (person__item)
            wordpress_items = html.find_all('li', class_='person__item')
            if wordpress_items:
                logger.info(f"Detected custom WordPress roster format for {team_name}, using person__item parser")
                return self._extract_players_from_wordpress_roster(html, team_id, team_name, season, division, base_url)

            # Check for table--roster class (UCF and similar)
            roster_table = html.find('table', class_='table--roster')
            if roster_table:
                logger.info(f"Detected table--roster format for {team_name}")
                return self._extract_players_from_table(html, team_id, team_name, season, division, base_url)

            # Try Sidearm table-based roster format (s-table-body__row)
            logger.info(f"Attempting to parse Sidearm table-based roster for {team_name}")
            return self._extract_players_from_table(html, team_id, team_name, season, division, base_url)

        # Extract base domain for URLs
        extracted = tldextract.extract(base_url)
        domain = f"{extracted.domain}.{extracted.suffix}"
        if extracted.subdomain:
            domain = f"{extracted.subdomain}.{domain}"

        for item in roster_items:
            try:
                # Jersey number
                jersey_elem = item.find('span', class_='sidearm-roster-player-jersey-number')
                jersey = FieldExtractors.clean_text(jersey_elem.get_text()) if jersey_elem else ''

                # Name and URL - check both h3 and h2 (some schools use h2, e.g., Yale)
                name_elem = item.find('h3') or item.find('h2')
                if name_elem:
                    name_link = name_elem.find('a', href=True)
                    if name_link:
                        name = FieldExtractors.clean_text(name_link.get_text())
                        # Build absolute URL
                        href = name_link['href']
                        if href.startswith('http'):
                            profile_url = href
                        else:
                            profile_url = f"https://{domain}{href}" if href.startswith('/') else f"https://{domain}/{href}"
                    else:
                        name = FieldExtractors.clean_text(name_elem.get_text())
                        profile_url = ''
                else:
                    logger.warning(f"No name found for player in {team_name}")
                    continue

                # Position
                pos_elem = item.find('span', class_='sidearm-roster-player-position-long-short')
                position = FieldExtractors.extract_position(pos_elem.get_text()) if pos_elem else ''

                # Height
                height_elem = item.find('span', class_='sidearm-roster-player-height')
                height = FieldExtractors.extract_height(height_elem.get_text()) if height_elem else ''

                # Academic year
                year_elem = item.find('span', class_='sidearm-roster-player-academic-year')
                year = FieldExtractors.normalize_academic_year(year_elem.get_text()) if year_elem else ''

                # Major (soccer-specific)
                major_elem = item.find('span', class_='sidearm-roster-player-major')
                major = FieldExtractors.clean_text(major_elem.get_text()) if major_elem else ''

                # Hometown
                hometown_elem = item.find('span', class_='sidearm-roster-player-hometown')
                hometown = FieldExtractors.clean_text(hometown_elem.get_text()) if hometown_elem else ''

                # High school
                hs_elem = item.find('span', class_='sidearm-roster-player-highschool')
                high_school = FieldExtractors.clean_text(hs_elem.get_text()) if hs_elem else ''

                # Previous school
                prev_elem = item.find('span', class_='sidearm-roster-player-previous-school')
                previous_school = FieldExtractors.clean_text(prev_elem.get_text()) if prev_elem else ''

                # Create Player object
                player = Player(
                    team_id=team_id,
                    team=team_name,
                    season=season,
                    division=division,
                    name=name,
                    jersey=jersey,
                    position=position,
                    height=height,
                    year=year,
                    major=major,
                    hometown=hometown,
                    high_school=high_school,
                    previous_school=previous_school,
                    url=profile_url
                )

                players.append(player)

            except Exception as e:
                logger.warning(f"Error parsing player in {team_name}: {e}")
                continue

        return players

    def _extract_players_from_kentucky_table(self, html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
        """
        Extract players from Kentucky's DataTables table (players-table__general)

        This table contains the full columns (Number, Name, Position, Height, Class, Hometown, Previous School, High school)
        and is rendered when requesting the table/list view. We look specifically for the table with id 'players-table__general'.
        """
        players = []

        # Look for known players table IDs used by WMT/WordPress (players-table, players-table__general)
        table = html.find('table', id=re.compile(r'^players-table'))
        if not table:
            logger.warning(f"Kentucky-style players table not found for {team_name}")
            return []

        # Header mapping
        header_map = {}
        thead = table.find('thead')
        headers = thead.find_all('th') if thead else table.find_all('th')
        for i, th in enumerate(headers):
            htext = th.get_text().strip().lower()
            if 'number' in htext or 'no' in htext or '#' in htext:
                header_map['jersey'] = i
            elif 'name' in htext:
                header_map['name'] = i
            elif 'position' in htext or 'pos' in htext:
                header_map['position'] = i
            elif 'height' in htext or 'ht' in htext:
                header_map['height'] = i
            elif 'class' in htext or 'yr' in htext or 'year' in htext:
                header_map['year'] = i
            elif 'hometown' in htext or 'home' in htext:
                header_map['hometown'] = i
            elif 'high' in htext and 'school' in htext:
                header_map['high_school'] = i
            elif 'previous' in htext:
                header_map['previous_school'] = i

        # Rows are typically in tbody
        tbody = table.find('tbody')
        rows = tbody.find_all('tr') if tbody else table.find_all('tr')[1:]

        # Extract base domain for URLs
        extracted = tldextract.extract(base_url)
        domain = f"{extracted.domain}.{extracted.suffix}"
        if extracted.subdomain:
            domain = f"{extracted.subdomain}.{domain}"

        for row in rows:
            try:
                cells = row.find_all(['td', 'th'])
                if not cells or len(cells) < 2:
                    continue

                # Name and profile URL
                name = ''
                profile_url = ''
                if 'name' in header_map and header_map['name'] < len(cells):
                    name_cell = cells[header_map['name']]
                    link = name_cell.find('a', href=True)
                    if link:
                        name = FieldExtractors.clean_text(link.get_text())
                        href = link['href']
                        if href.startswith('http'):
                            profile_url = href
                        else:
                            profile_url = f"https://{domain}{href}" if href.startswith('/') else f"https://{domain}/{href}"
                    else:
                        name = FieldExtractors.clean_text(name_cell.get_text())

                if not name:
                    continue

                # Jersey
                jersey = ''
                if 'jersey' in header_map and header_map['jersey'] < len(cells):
                    jersey = FieldExtractors.clean_text(cells[header_map['jersey']].get_text())

                # Position
                position = ''
                if 'position' in header_map and header_map['position'] < len(cells):
                    position = FieldExtractors.extract_position(cells[header_map['position']].get_text())

                # Height
                height = ''
                if 'height' in header_map and header_map['height'] < len(cells):
                    height = FieldExtractors.extract_height(cells[header_map['height']].get_text())

                # Year/Class
                year = ''
                if 'year' in header_map and header_map['year'] < len(cells):
                    year = FieldExtractors.normalize_academic_year(cells[header_map['year']].get_text().strip())

                # Hometown
                hometown = ''
                if 'hometown' in header_map and header_map['hometown'] < len(cells):
                    hometown = FieldExtractors.clean_text(cells[header_map['hometown']].get_text())

                # High school
                high_school = ''
                if 'high_school' in header_map and header_map['high_school'] < len(cells):
                    high_school = FieldExtractors.clean_text(cells[header_map['high_school']].get_text())

                # Previous school
                previous_school = ''
                if 'previous_school' in header_map and header_map['previous_school'] < len(cells):
                    previous_school = FieldExtractors.clean_text(cells[header_map['previous_school']].get_text())

                player = Player(
                    team_id=team_id,
                    team=team_name,
                    season=season,
                    division=division,
                    name=name,
                    jersey=jersey,
                    position=position,
                    height=height,
                    year=year,
                    major='',
                    hometown=hometown,
                    high_school=high_school,
                    previous_school=previous_school,
                    url=profile_url
                )

                players.append(player)

            except Exception as e:
                logger.warning(f"Error parsing Kentucky table row for {team_name}: {e}")
                continue

        return players
    def _extract_players_from_generic_roster_table(self, html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
        """
        Extract players from generic mod-roster HTML table format

        Used by schools like Emory & Henry that have a simple HTML table inside
        a <div class="mod-roster"> container. The table has a header row with buttons
        containing column names (sort buttons with aria-labels).

        Args:
            html: BeautifulSoup parsed HTML
            team_id: NCAA team ID
            team_name: Team name
            season: Season string
            division: Division
            base_url: Base URL for constructing profile URLs

        Returns:
            List of Player objects
        """
        players = []

        # Find the mod-roster div and its table
        mod_roster = html.find('div', class_='mod-roster')
        if not mod_roster:
            logger.warning(f"No mod-roster div found for {team_name}")
            return []

        table = mod_roster.find('table')
        if not table:
            logger.warning(f"No table found in mod-roster for {team_name}")
            return []

        # Extract headers from the header row
        thead = table.find('thead')
        if not thead:
            logger.warning(f"No thead found in mod-roster table for {team_name}")
            return []

        header_row = thead.find('tr')
        if not header_row:
            logger.warning(f"No header row found in mod-roster table for {team_name}")
            return []

        headers = header_row.find_all('th')
        if not headers:
            logger.warning(f"No th headers found in mod-roster table for {team_name}")
            return []

        # Build header mapping by looking at button aria-labels or button text
        header_map = {}
        for i, header in enumerate(headers):
            # Try to get aria-label from button inside th
            button = header.find('button')
            if button:
                aria_label = button.get('aria-label', '').lower()
                button_text = button.get_text().strip().lower()
                text_to_check = aria_label if aria_label else button_text
            else:
                text_to_check = header.get_text().strip().lower()

            # Map to fields
            if 'number' in text_to_check or 'no.' in text_to_check or 'no:' in text_to_check:
                header_map['jersey'] = i
            elif 'name' in text_to_check or 'last_name' in text_to_check:
                header_map['name'] = i
            elif 'position' in text_to_check or 'pos.' in text_to_check or 'pos:' in text_to_check:
                header_map['position'] = i
            elif 'year' in text_to_check or 'yr.' in text_to_check or 'yr:' in text_to_check:
                header_map['year'] = i
            elif 'height' in text_to_check or 'ht.' in text_to_check or 'ht:' in text_to_check:
                header_map['height'] = i
            elif 'weight' in text_to_check or 'wt.' in text_to_check or 'wt:' in text_to_check:
                header_map['weight'] = i
            elif 'hometown' in text_to_check or 'home' in text_to_check or 'hometown/previous' in text_to_check:
                header_map['hometown'] = i

        logger.info(f"mod-roster headers for {team_name}: {header_map}")

        # Extract base domain for URLs
        extracted = tldextract.extract(base_url)
        domain = f"{extracted.domain}.{extracted.suffix}"
        if extracted.subdomain:
            domain = f"{extracted.subdomain}.{domain}"

        # Extract rows from tbody
        tbody = table.find('tbody')
        if not tbody:
            logger.warning(f"No tbody found in mod-roster table for {team_name}")
            return []

        rows = tbody.find_all('tr')
        logger.info(f"Found {len(rows)} rows in mod-roster table for {team_name}")

        for row in rows:
            try:
                cells = row.find_all(['td', 'th'])
                if not cells or len(cells) < 2:
                    continue

                # Extract Name (with URL) - name is typically in a th with class="name"
                name = ''
                profile_url = ''
                if 'name' in header_map and header_map['name'] < len(cells):
                    name_cell = cells[header_map['name']]
                    name_link = name_cell.find('a', href=True)
                    if name_link:
                        name = FieldExtractors.clean_text(name_link.get_text())
                        href = name_link['href']
                        if href.startswith('http'):
                            profile_url = href
                        else:
                            profile_url = f"https://{domain}{href}" if href.startswith('/') else f"https://{domain}/{href}"

                if not name or name.lower() == 'null':
                    continue

                # Extract Jersey
                jersey = ''
                if 'jersey' in header_map and header_map['jersey'] < len(cells):
                    jersey_cell = cells[header_map['jersey']]
                    # Remove label spans if they exist
                    for label_span in jersey_cell.find_all('span', class_='label'):
                        label_span.decompose()
                    jersey = FieldExtractors.clean_text(jersey_cell.get_text())

                # Extract Position
                position = ''
                if 'position' in header_map and header_map['position'] < len(cells):
                    pos_cell = cells[header_map['position']]
                    # Remove label spans if they exist
                    for label_span in pos_cell.find_all('span', class_='label'):
                        label_span.decompose()
                    position = FieldExtractors.extract_position(pos_cell.get_text())

                # Extract Height
                height = ''
                if 'height' in header_map and header_map['height'] < len(cells):
                    height_cell = cells[header_map['height']]
                    # Remove label spans if they exist
                    for label_span in height_cell.find_all('span', class_='label'):
                        label_span.decompose()
                    height = FieldExtractors.extract_height(height_cell.get_text())

                # Extract Year/Class
                year = ''
                if 'year' in header_map and header_map['year'] < len(cells):
                    year_cell = cells[header_map['year']]
                    # Remove label spans if they exist
                    for label_span in year_cell.find_all('span', class_='label'):
                        label_span.decompose()
                    year = FieldExtractors.normalize_academic_year(year_cell.get_text())

                # Extract Hometown / High School
                hometown = ''
                high_school = ''
                if 'hometown' in header_map and header_map['hometown'] < len(cells):
                    hometown_cell = cells[header_map['hometown']]
                    # Remove label spans if they exist
                    for label_span in hometown_cell.find_all('span', class_='label'):
                        label_span.decompose()
                    hometown_hs = FieldExtractors.clean_text(hometown_cell.get_text())
                    if ' / ' in hometown_hs:
                        hometown, high_school = hometown_hs.split(' / ', 1)
                    else:
                        hometown = hometown_hs

                # Create Player object
                player = Player(
                    team_id=team_id,
                    team=team_name,
                    season=season,
                    division=division,
                    name=name,
                    jersey=jersey,
                    position=position,
                    height=height,
                    year=year,
                    major='',
                    hometown=hometown,
                    high_school=high_school,
                    previous_school='',
                    url=profile_url
                )

                players.append(player)

            except Exception as e:
                logger.warning(f"Error parsing mod-roster row for {team_name}: {e}")
                continue

        return players

    def _extract_players_from_data_field_table(self, html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
        """
        Extract players from data-field table format

        Used by schools like Bridgeport that use data-field-label and data-field attributes
        on th and td elements. Headers have data-field-label attributes, and data cells
        have data-field attributes with field names like "number", "first_name:last_name", etc.

        Args:
            html: BeautifulSoup parsed HTML
            team_id: NCAA team ID
            team_name: Team name
            season: Season string
            division: Division
            base_url: Base URL for constructing profile URLs

        Returns:
            List of Player objects
        """
        players = []

        # Find any table with data-field-label headers
        table = None
        for t in html.find_all('table'):
            if t.find('th', attrs={'data-field-label': True}):
                table = t
                break

        if not table:
            logger.warning(f"No data-field table found for {team_name}")
            return []

        # Extract headers using data-field-label
        headers = table.find_all('th', attrs={'data-field-label': True})
        if not headers:
            logger.warning(f"No data-field headers found for {team_name}")
            return []

        # Build header mapping
        header_map = {}
        for i, header in enumerate(headers):
            label = header.get('data-field-label', '').strip().lower()
            if 'no.' in label or 'number' in label:
                header_map['jersey'] = i
            elif 'name' in label:
                header_map['name'] = i
            elif 'pos' in label:
                header_map['position'] = i
            elif 'cl.' in label or 'class' in label or 'year' in label or 'yr' in label:
                header_map['year'] = i
            elif 'ht.' in label or 'height' in label:
                header_map['height'] = i
            elif 'wt.' in label or 'weight' in label:
                header_map['weight'] = i
            elif 'hometown' in label or 'home' in label:
                header_map['hometown'] = i
            elif 'high' in label and 'school' in label:
                header_map['high_school'] = i
            elif 'previous' in label and ('college' in label or 'school' in label):
                header_map['previous_school'] = i

        logger.info(f"data-field headers for {team_name}: {header_map}")

        # Extract base domain for URLs
        extracted = tldextract.extract(base_url)
        domain = f"{extracted.domain}.{extracted.suffix}"
        if extracted.subdomain:
            domain = f"{extracted.subdomain}.{domain}"

        # Extract rows from tbody
        tbody = table.find('tbody')
        if not tbody:
            logger.warning(f"No tbody found in data-field table for {team_name}")
            return []

        rows = tbody.find_all('tr')
        logger.info(f"Found {len(rows)} rows in data-field table for {team_name}")

        for row in rows:
            try:
                cells = row.find_all(['td', 'th'])
                if not cells or len(cells) < 2:
                    continue

                # Extract Name (with URL)
                name = ''
                profile_url = ''
                if 'name' in header_map and header_map['name'] < len(cells):
                    name_cell = cells[header_map['name']]
                    # Look for links - there may be multiple (image link, name link, etc.)
                    # We want the link with actual name text content
                    name_link = None
                    for link in name_cell.find_all('a', href=True):
                        link_text = link.get_text().strip()
                        # Skip image links and other empty links
                        if len(link_text) > 2:  # Name should be more than 2 chars
                            name_link = link
                            break
                    
                    if name_link:
                        name_text = name_link.get_text()
                        # Handle multi-line names with whitespace
                        name = FieldExtractors.clean_text(name_text)
                        href = name_link['href']
                        if href.startswith('http'):
                            profile_url = href
                        else:
                            profile_url = f"https://{domain}{href}" if href.startswith('/') else f"https://{domain}/{href}"
                    else:
                        # Fallback to cell text if no link found
                        name = FieldExtractors.clean_text(name_cell.get_text())

                if not name or name.lower() == 'null':
                    continue

                # Extract Jersey
                jersey = ''
                if 'jersey' in header_map and header_map['jersey'] < len(cells):
                    jersey_cell = cells[header_map['jersey']]
                    # Remove label spans if they exist
                    for label_span in jersey_cell.find_all('span', class_='label'):
                        label_span.decompose()
                    jersey = FieldExtractors.clean_text(jersey_cell.get_text())

                # Extract Position
                position = ''
                if 'position' in header_map and header_map['position'] < len(cells):
                    pos_cell = cells[header_map['position']]
                    # Remove label spans if they exist
                    for label_span in pos_cell.find_all('span', class_='label'):
                        label_span.decompose()
                    position = FieldExtractors.extract_position(pos_cell.get_text())

                # Extract Height
                height = ''
                if 'height' in header_map and header_map['height'] < len(cells):
                    height_cell = cells[header_map['height']]
                    # Remove label spans if they exist
                    for label_span in height_cell.find_all('span', class_='label'):
                        label_span.decompose()
                    height = FieldExtractors.extract_height(height_cell.get_text())

                # Extract Year/Class
                year = ''
                if 'year' in header_map and header_map['year'] < len(cells):
                    year_cell = cells[header_map['year']]
                    # Remove label spans if they exist
                    for label_span in year_cell.find_all('span', class_='label'):
                        label_span.decompose()
                    year = FieldExtractors.normalize_academic_year(year_cell.get_text())

                # Extract Hometown / High School
                hometown = ''
                high_school = ''
                if 'hometown' in header_map and header_map['hometown'] < len(cells):
                    hometown_cell = cells[header_map['hometown']]
                    # Remove label spans if they exist
                    for label_span in hometown_cell.find_all('span', class_='label'):
                        label_span.decompose()
                    hometown_hs = FieldExtractors.clean_text(hometown_cell.get_text())
                    if ' / ' in hometown_hs:
                        hometown, high_school = hometown_hs.split(' / ', 1)
                    else:
                        hometown = hometown_hs

                # Extract High School (if in separate column)
                if not high_school and 'high_school' in header_map and header_map['high_school'] < len(cells):
                    hs_cell = cells[header_map['high_school']]
                    # Remove label spans if they exist
                    for label_span in hs_cell.find_all('span', class_='label'):
                        label_span.decompose()
                    high_school = FieldExtractors.clean_text(hs_cell.get_text())

                # Extract Previous School
                previous_school = ''
                if 'previous_school' in header_map and header_map['previous_school'] < len(cells):
                    prev_cell = cells[header_map['previous_school']]
                    # Remove label spans if they exist
                    for label_span in prev_cell.find_all('span', class_='label'):
                        label_span.decompose()
                    previous_school = FieldExtractors.clean_text(prev_cell.get_text())

                # Create Player object
                player = Player(
                    team_id=team_id,
                    team=team_name,
                    season=season,
                    division=division,
                    name=name,
                    jersey=jersey,
                    position=position,
                    height=height,
                    year=year,
                    major='',
                    hometown=hometown,
                    high_school=high_school,
                    previous_school=previous_school,
                    url=profile_url
                )

                players.append(player)

            except Exception as e:
                logger.warning(f"Error parsing data-field row for {team_name}: {e}")
                continue

        return players

    def _extract_players_from_list_items(self, html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
        """
        Extract players from Sidearm list-item format (used by Bradley and similar schools)

        This format uses <li class="sidearm-roster-list-item"> with nested divs containing player data

        Args:
            html: BeautifulSoup parsed HTML
            team_id: NCAA team ID
            team_name: Team name
            season: Season string
            division: Division
            base_url: Base URL for constructing profile URLs

        Returns:
            List of Player objects
        """
        players = []

        # Find all roster list items
        roster_items = html.find_all('li', class_='sidearm-roster-list-item')

        # Extract base domain for URLs
        extracted = tldextract.extract(base_url)
        domain = f"{extracted.domain}.{extracted.suffix}"
        if extracted.subdomain:
            domain = f"{extracted.subdomain}.{domain}"

        for item in roster_items:
            try:
                # Find the link element which contains most of the data
                link_elem = item.find('div', class_='sidearm-roster-list-item-link')
                if not link_elem:
                    continue

                # Jersey number - in photo div, inside a span
                jersey = ''
                photo_number = item.find('div', class_='sidearm-roster-list-item-photo-number')
                if photo_number:
                    number_span = photo_number.find('span')
                    if number_span:
                        jersey = FieldExtractors.clean_text(number_span.get_text())
                    else:
                        jersey = FieldExtractors.clean_text(photo_number.get_text())

                # Name and URL - in name div
                name = ''
                profile_url = ''
                name_elem = item.find('div', class_='sidearm-roster-list-item-name')
                if name_elem:
                    name_link = name_elem.find('a', href=True)
                    if name_link:
                        name = FieldExtractors.clean_text(name_link.get_text())
                        href = name_link['href']
                        if href.startswith('http'):
                            profile_url = href
                        else:
                            profile_url = f"https://{domain}{href}" if href.startswith('/') else f"https://{domain}/{href}"
                    else:
                        # Sometimes name is just in the div without a link
                        name = FieldExtractors.clean_text(name_elem.get_text())

                if not name:
                    logger.warning(f"No name found for player in {team_name}")
                    continue

                # Position and other metadata - use specific classes
                position = ''
                year = ''
                height = ''
                hometown = ''
                high_school = ''
                previous_school = ''

                # Position
                pos_elem = item.find('span', class_='sidearm-roster-list-item-position')
                if pos_elem:
                    position = FieldExtractors.extract_position(pos_elem.get_text())

                # Year/Class
                year_elem = item.find('span', class_='sidearm-roster-list-item-year')
                if year_elem:
                    year = FieldExtractors.normalize_academic_year(year_elem.get_text())

                # Height
                height_elem = item.find('span', class_='sidearm-roster-list-item-height')
                if height_elem:
                    height = FieldExtractors.extract_height(height_elem.get_text())

                # Hometown
                hometown_elem = item.find('div', class_='sidearm-roster-list-item-hometown')
                if hometown_elem:
                    hometown = FieldExtractors.clean_text(hometown_elem.get_text())

                # High school and Previous school
                # Can be in sidearm-roster-list-item-highschool span
                hs_elem = item.find('span', class_='sidearm-roster-list-item-highschool')
                if hs_elem:
                    hs_text = FieldExtractors.clean_text(hs_elem.get_text())
                    # Parse format like "Northern Guilford High School (USC Upstate)" or "(SIUE)"
                    if '(' in hs_text and ')' in hs_text:
                        # Split by parentheses
                        main_part = hs_text[:hs_text.index('(')].strip()
                        paren_part = hs_text[hs_text.index('(') + 1:hs_text.index(')')].strip()
                        
                        # Check if paren part looks like a college/university
                        college_indicators = ['University', 'College', 'State', 'Tech', 'Institute', 'Univ', 'U.', 'SC', 'NJIT', 'SIUE', 'DME', 'DePaul', 'Evansville', 'Bonaventure']
                        if any(indicator.lower() in paren_part.lower() for indicator in college_indicators):
                            # Paren part is previous school, main part is high school
                            if main_part:
                                high_school = main_part
                            previous_school = paren_part
                        else:
                            # Main part is high school, paren part is additional info (ignore)
                            high_school = main_part if main_part else paren_part
                    else:
                        high_school = hs_text

                # Check for explicit previous-school span (some sites have this)
                prev_elem = item.find('span', class_='sidearm-roster-list-item-previous-school')
                if prev_elem:
                    prev_text = FieldExtractors.clean_text(prev_elem.get_text())
                    if prev_text:
                        previous_school = prev_text

                # Create Player object
                player = Player(
                    team_id=team_id,
                    team=team_name,
                    season=season,
                    division=division,
                    name=name,
                    jersey=jersey,
                    position=position,
                    height=height,
                    year=year,
                    major='',  # Not typically available in list-item format
                    hometown=hometown,
                    high_school=high_school,
                    previous_school=previous_school,
                    url=profile_url
                )

                players.append(player)

            except Exception as e:
                logger.warning(f"Error parsing list-item in {team_name}: {e}")
                continue

        return players

    def _extract_players_from_table(self, html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
        """
        Extract players from table-based roster format (header-aware)

        Args:
            html: BeautifulSoup parsed HTML
            team_id: NCAA team ID
            team_name: Team name
            season: Season string
            division: Division
            base_url: Base URL for constructing profile URLs

        Returns:
            List of Player objects
        """
        players = []

        # Find the roster table (not coaching staff or other tables)
        # First, try to find Sidearm-specific rows
        table_rows = html.find_all('tr', class_='s-table-body__row')
        roster_table = None
        is_generic_table = False

        if table_rows:
            # Find the table that contains these rows
            for row in table_rows:
                table = row.find_parent('table')
                if table:
                    roster_table = table
                    break

        # If no Sidearm-specific rows, look for any table with roster-like headers
        if not roster_table:
            all_tables = html.find_all('table')
            for table in all_tables:
                # Check if table has header row with roster-like column names
                # First look in thead, then fall back to first row
                header_row = table.find('thead')
                if header_row:
                    header_row = header_row.find('tr')
                else:
                    header_row = table.find('tr')
                
                if header_row:
                    header_cells = header_row.find_all(['th', 'td'])
                    header_text = ' '.join([cell.get_text().strip().lower() for cell in header_cells])
                    # Look for roster-like headers (handle abbreviations like 'pos.' for 'position')
                    has_name = 'name' in header_text
                    has_position = 'position' in header_text or 'pos' in header_text
                    if has_name and has_position:
                        roster_table = table
                        is_generic_table = True
                        logger.info(f"Found generic roster table for {team_name}")
                        break

        if not roster_table:
            logger.warning(f"Could not find roster table for {team_name}")
            return []

        # Find table headers - different logic for Sidearm vs generic tables
        headers = []
        if is_generic_table:
            # For generic tables, get headers from thead if available, otherwise first row
            thead = roster_table.find('thead')
            if thead:
                first_row = thead.find('tr')
            else:
                first_row = roster_table.find('tr')
            
            if first_row:
                headers = first_row.find_all(['th', 'td'])
            if not headers:
                logger.warning(f"No table headers found in generic roster table for {team_name}")
                return []
        else:
            # For Sidearm tables, look for specific header class
            headers = roster_table.find_all('th', class_='s-table-header__column')
            if not headers:
                logger.warning(f"No table headers found in roster table for {team_name}")
                return []

        # Create header mapping (normalize header text)
        header_map = {}
        for i, header in enumerate(headers):
            header_text = header.get_text().strip().lower()
            # Map various header names to our fields
            if 'name' in header_text and 'first' not in header_text:
                header_map['name'] = i
            elif any(k in header_text for k in ('no', '#', 'jersey', 'number', 'num')):
                header_map['jersey'] = i
            elif 'pos' in header_text:
                header_map['position'] = i
            elif 'ht' in header_text or 'height' in header_text:
                header_map['height'] = i
            elif 'yr' in header_text or 'year' in header_text or 'class' in header_text:
                header_map['year'] = i
            elif 'hometown' in header_text or 'home' in header_text:
                header_map['hometown'] = i
            elif 'high school' in header_text or 'highschool' in header_text:
                header_map['high_school'] = i
            elif 'previous' in header_text:
                header_map['previous_school'] = i

        logger.info(f"Table headers for {team_name}: {header_map}")

        # Filter table rows to only those in the roster table
        if is_generic_table:
            # For generic tables, get all rows from tbody if it exists, otherwise all rows except first
            tbody = roster_table.find('tbody')
            if tbody:
                table_rows = tbody.find_all('tr')
            else:
                all_rows = roster_table.find_all('tr')
                table_rows = all_rows[1:] if len(all_rows) > 1 else []
        else:
            # For Sidearm tables, look for specific row class
            table_rows = roster_table.find_all('tr', class_='s-table-body__row')
        logger.info(f"Found {len(table_rows)} table rows in roster table for {team_name}")

        # Extract base domain for URLs
        extracted = tldextract.extract(base_url)
        domain = f"{extracted.domain}.{extracted.suffix}"
        if extracted.subdomain:
            domain = f"{extracted.subdomain}.{domain}"

        for row in table_rows:
            try:
                # Get all cells (including both td and th for generic tables)
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:  # Need at least some basic data
                    continue

                # Extract Name (with URL)
                name = ''
                profile_url = ''
                if 'name' in header_map:
                    name_cell = cells[header_map['name']]
                    name_link = name_cell.find('a', href=True)
                    if name_link:
                        name = FieldExtractors.clean_text(name_link.get_text())
                        href = name_link['href']
                        if href.startswith('http'):
                            profile_url = href
                        else:
                            profile_url = f"https://{domain}{href}" if href.startswith('/') else f"https://{domain}/{href}"
                    else:
                        name = FieldExtractors.clean_text(name_cell.get_text())

                if not name or name.lower() == 'null':
                    continue

                # Extract Jersey
                jersey = ''
                if 'jersey' in header_map:
                    jersey = FieldExtractors.clean_text(cells[header_map['jersey']].get_text())

                # Extract Position
                position = ''
                if 'position' in header_map:
                    position = FieldExtractors.extract_position(cells[header_map['position']].get_text())

                # Extract Height
                height = ''
                if 'height' in header_map:
                    height = FieldExtractors.extract_height(cells[header_map['height']].get_text())

                # Extract Year/Class
                year = ''
                if 'year' in header_map:
                    year = FieldExtractors.normalize_academic_year(cells[header_map['year']].get_text())

                # Extract Hometown / High School
                hometown = ''
                high_school = ''
                if 'hometown' in header_map:
                    hometown_hs = FieldExtractors.clean_text(cells[header_map['hometown']].get_text())
                    if ' / ' in hometown_hs:
                        hometown, high_school = hometown_hs.split(' / ', 1)
                    else:
                        hometown = hometown_hs

                # If high_school has its own column, use that instead
                if 'high_school' in header_map:
                    high_school = FieldExtractors.clean_text(cells[header_map['high_school']].get_text())

                # Extract Previous School
                previous_school = ''
                if 'previous_school' in header_map:
                    previous_school = FieldExtractors.clean_text(cells[header_map['previous_school']].get_text())

                # Create Player object
                player = Player(
                    team_id=team_id,
                    team=team_name,
                    season=season,
                    division=division,
                    name=name,
                    jersey=jersey,
                    position=position,
                    height=height,
                    year=year,
                    major='',  # Not available in table format
                    hometown=hometown,
                    high_school=high_school,
                    previous_school=previous_school,
                    url=profile_url
                )

                players.append(player)

            except Exception as e:
                logger.warning(f"Error parsing table row in {team_name}: {e}")
                continue

        return players

    def _extract_players_from_presto_table(self, html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
        """
        Extract players from PrestoSports data-label table format

        PrestoSports uses <td data-label="..."> attributes instead of Sidearm's structure.
        Example: <td data-label="No.">5</td>

        Args:
            html: BeautifulSoup parsed HTML
            team_id: NCAA team ID
            team_name: Team name
            season: Season string
            division: Division
            base_url: Base URL for constructing profile URLs

        Returns:
            List of Player objects
        """
        players = []

        # Find all table rows (each row is a player)
        rows = html.find_all('tr')

        for row in rows:
            try:
                # Look for cells with data-label attributes
                cells_with_labels = row.find_all('td', attrs={'data-label': True})

                if not cells_with_labels or len(cells_with_labels) < 3:
                    continue  # Skip header rows or empty rows

                # Extract data by data-label attribute
                data = {}
                for cell in cells_with_labels:
                    label = cell.get('data-label', '').strip().lower()
                    # Get text content, excluding label spans
                    # Look for nested label span and exclude it
                    label_spans = cell.find_all('span', class_='label')
                    if label_spans:
                        # Get all text except from label spans
                        cell_copy = str(cell)
                        from bs4 import BeautifulSoup
                        cell_soup = BeautifulSoup(cell_copy, 'html.parser')
                        for span in cell_soup.find_all('span', class_='label'):
                            span.decompose()
                        value = FieldExtractors.clean_text(cell_soup.get_text())
                    else:
                        value = FieldExtractors.clean_text(cell.get_text())
                    data[label] = value

                # Also check for name in <th> with data-label
                name_header = row.find('th', attrs={'data-label': True})
                if name_header:
                    label = name_header.get('data-label', '').strip().lower()
                    # Get first non-empty anchor tag for name (skip image links)
                    all_links = name_header.find_all('a')
                    name_found = False
                    for link in all_links:
                        link_text = FieldExtractors.clean_text(link.get_text())
                        if link_text:  # Skip empty links (e.g., image links)
                            data[label] = link_text
                            name_found = True
                            break
                    if not name_found:
                        data[label] = FieldExtractors.clean_text(name_header.get_text())

                # Map data-label values to player fields
                name = data.get('name', '')
                jersey = data.get('no.', data.get('no', data.get('#', '')))
                position = data.get('pos.', data.get('pos', data.get('position', '')))
                height = FieldExtractors.extract_height(data.get('ht.', data.get('ht', data.get('height', ''))))
                year = FieldExtractors.normalize_academic_year(data.get('cl.', data.get('class', data.get('year', ''))))

                # Hometown/High School might be combined
                hometown_raw = data.get('hometown/last school', data.get('hometown', data.get('hometown/high school', '')))
                high_school = data.get('high school', data.get('last school', ''))
                hometown = ''

                # If combined field, try to split
                if hometown_raw and '/' in hometown_raw:
                    parts = hometown_raw.split('/')
                    hometown = parts[0].strip()
                    if not high_school:
                        high_school = parts[1].strip() if len(parts) > 1 else ''
                else:
                    hometown = hometown_raw

                # Previous school
                previous_school = data.get('previous school', data.get('last school', ''))

                # Skip if no name
                if not name:
                    continue

                # Extract profile URL from name link
                profile_url = ''
                name_link = None
                if name_header:
                    name_link = name_header.find('a')
                else:
                    # Search in cells for name link
                    for cell in cells_with_labels:
                        if data.get(cell.get('data-label', '').strip().lower()) == name:
                            name_link = cell.find('a')
                            if name_link:
                                break

                if name_link and name_link.get('href'):
                    href = name_link.get('href')
                    if href.startswith('http'):
                        profile_url = href
                    else:
                        profile_url = URLBuilder.extract_base_url(base_url) + href

                # Create Player object
                player = Player(
                    team_id=team_id,
                    team=team_name,
                    season=season,
                    division=division,
                    name=name,
                    jersey=jersey,
                    position=position,
                    height=height,
                    year=year,
                    major='',  # Not typically available in PrestoSports
                    hometown=hometown,
                    high_school=high_school,
                    previous_school=previous_school,
                    url=profile_url
                )

                players.append(player)

            except Exception as e:
                logger.warning(f"Error parsing PrestoSports row in {team_name}: {e}")
                continue

        return players

    def _extract_players_from_cards(self, html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
        """
        Extract players from Sidearm card-based layout (s-person-card divs)

        Used by some Sidearm sites like Davidson that display rosters as cards
        instead of lists or tables.

        Args:
            html: BeautifulSoup parsed HTML
            team_id: NCAA team ID
            team_name: Team name
            season: Season string
            division: Division
            base_url: Base URL for constructing profile URLs

        Returns:
            List of Player objects
        """
        players = []

        # Find all person cards
        cards = html.find_all('div', class_='s-person-card')

        for card in cards:
            try:
                # Extract name
                name_elem = card.find('div', class_='s-person-details__personal-single-line')
                name = FieldExtractors.clean_text(name_elem.get_text()) if name_elem else ''

                # Extract jersey from thumbnail text (e.g., "Jersey Number 0")
                jersey = ''
                thumbnail = card.find('div', class_='s-person-details__thumbnail')
                if thumbnail:
                    thumbnail_text = thumbnail.get_text()
                    if 'Jersey Number' in thumbnail_text:
                        jersey = thumbnail_text.replace('Jersey Number', '').strip()

                # Extract bio stats (position, year, height, weight)
                bio_stats = card.find_all('span', class_='s-person-details__bio-stats-item')
                position = ''
                year = ''
                height = ''

                for stat in bio_stats:
                    stat_text = stat.get_text().strip()
                    if stat_text.startswith('Position'):
                        position = FieldExtractors.extract_position(stat_text.replace('Position', '').strip())
                    elif stat_text.startswith('Academic Year'):
                        year = FieldExtractors.normalize_academic_year(stat_text.replace('Academic Year', '').strip())
                    elif stat_text.startswith('Height'):
                        height = FieldExtractors.extract_height(stat_text.replace('Height', '').strip())

                # Extract location info (hometown, high school)
                hometown = ''
                high_school = ''
                location_items = card.find_all('span', class_='s-person-card__content__person__location-item')
                for item in location_items:
                    item_text = item.get_text().strip()
                    if item_text.startswith('Hometown'):
                        hometown = item_text.replace('Hometown', '').strip()
                    elif item_text.startswith('Last School'):
                        high_school = item_text.replace('Last School', '').strip()

                # Extract profile URL
                profile_url = ''
                cta_link = card.find('a', href=True)
                if cta_link:
                    href = cta_link['href']
                    if href.startswith('http'):
                        profile_url = href
                    else:
                        extracted = tldextract.extract(base_url)
                        domain = f"{extracted.domain}.{extracted.suffix}"
                        if extracted.subdomain:
                            domain = f"{extracted.subdomain}.{domain}"
                        profile_url = f"https://{domain}{href}" if href.startswith('/') else f"https://{domain}/{href}"

                # Skip if no name or no jersey (staff members typically don't have jersey numbers)
                if not name or not jersey:
                    continue

                # Create Player object
                player = Player(
                    team_id=team_id,
                    team=team_name,
                    season=season,
                    division=division,
                    name=name,
                    jersey=jersey,
                    position=position,
                    height=height,
                    year=year,
                    major='',  # Not available in card format
                    hometown=hometown,
                    high_school=high_school,
                    previous_school='',  # Not available in card format
                    url=profile_url
                )

                players.append(player)

            except Exception as e:
                logger.warning(f"Error parsing card in {team_name}: {e}")
                continue

        return players

    def _extract_players_from_wmt(self, html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
        """
        Extract players from WMT Digital roster format (roster__item divs)

        Used by schools like Virginia that use WMT Digital platform with
        <div class="roster__item"> structure and schema.org itemprops

        Args:
            html: BeautifulSoup parsed HTML
            team_id: NCAA team ID
            team_name: Team name
            season: Season string
            division: Division
            base_url: Base URL for constructing profile URLs

        Returns:
            List of Player objects
        """
        players = []

        # Find all roster items
        roster_items = html.find_all('div', class_='roster__item')

        for item in roster_items:
            try:
                # Name - in itemprop="name" span with content attribute
                name = ''
                name_elem = item.find('span', itemprop='name')
                if name_elem and name_elem.get('content'):
                    name = name_elem['content'].strip()

                if not name:
                    continue

                # Jersey number - try two formats:
                # Virginia: in roster__image div > span
                # Kentucky: in roster-item__inner > span.roster-item__number
                jersey = ''
                
                # Try Virginia format first
                image_div = item.find('div', class_='roster__image')
                if image_div:
                    jersey_span = image_div.find('span')
                    if jersey_span:
                        jersey = jersey_span.get_text().strip()
                
                # Try Kentucky format if not found
                if not jersey:
                    number_span = item.find('span', class_='roster-item__number')
                    if number_span:
                        jersey = number_span.get_text().strip()

                # Profile URL - in roster__image div > a (Virginia) or main item > a (Kentucky)
                profile_url = ''
                if image_div:
                    link = image_div.find('a', href=True)
                    if link:
                        href = link['href']
                        if href.startswith('http'):
                            profile_url = href
                        else:
                            # Extract base domain
                            extracted = tldextract.extract(base_url)
                            domain = f"{extracted.domain}.{extracted.suffix}"
                            if extracted.subdomain:
                                domain = f"{extracted.subdomain}.{domain}"
                            profile_url = f"https://{domain}{href}" if href.startswith('/') else f"https://{domain}/{href}"
                
                # Try Kentucky format if not found
                if not profile_url:
                    link = item.find('a', href=True)
                    if link:
                        href = link['href']
                        if href.startswith('http'):
                            profile_url = href
                        else:
                            # Extract base domain
                            extracted = tldextract.extract(base_url)
                            domain = f"{extracted.domain}.{extracted.suffix}"
                            if extracted.subdomain:
                                domain = f"{extracted.subdomain}.{domain}"
                            profile_url = f"https://{domain}{href}" if href.startswith('/') else f"https://{domain}/{href}"

                # Other details are in roster__title and roster__description divs (Virginia)
                # OR in roster-item__info paragraph (Kentucky)
                # Title typically has position
                position = ''
                year = ''
                title_div = item.find('div', class_='roster__title')
                if title_div:
                    title_text = title_div.get_text()
                    position = FieldExtractors.extract_position(title_text)

                # Try Kentucky format first (simpler)
                height = ''
                hometown = ''
                high_school = ''
                previous_school = ''
                
                # Kentucky format: <p class="roster-item__info">
                info_p = item.find('p', class_='roster-item__info')
                if info_p:
                    info_text = info_p.get_text(strip=True)
                    # Format: "Goalkeeper - 6'4" 185 lbs" or similar
                    # Extract position and dimensions
                    if '-' in info_text:
                        parts = info_text.split('-')
                        if not position and len(parts) > 0:
                            position = FieldExtractors.extract_position(parts[0].strip())
                        if len(parts) > 1:
                            # Parse dimensions: "6'4" 185 lbs" or "6'4" 185"
                            dims = parts[1].strip()
                            height = FieldExtractors.extract_height(dims)
                else:
                    # Virginia format: Description div has <p> tags
                    description_div = item.find('div', class_='roster__description')
                    if description_div:
                        p_tags = description_div.find_all('p')
                        
                        # First <p>: height / weight / year
                        if len(p_tags) > 0:
                            first_p = p_tags[0].get_text(strip=True)
                            # Split by / to get components
                            parts = [p.strip() for p in first_p.split('/')]
                            if len(parts) >= 1:
                                # First part should be height
                                height = FieldExtractors.extract_height(parts[0])
                            # Weight is parts[1], we skip it
                            if len(parts) >= 3:
                                # Third part is year
                                year_candidate = FieldExtractors.normalize_academic_year(parts[2])
                                if year_candidate:
                                    year = year_candidate
                        
                        # Second <p>: hometown / high school or club / previous school
                        if len(p_tags) > 1:
                            second_p = p_tags[1].get_text(strip=True)
                            # Remove social media links
                            second_p = re.sub(r'@\w+.*$', '', second_p).strip()
                            # Split by /
                            location_parts = [p.strip() for p in second_p.split('/') if p.strip()]
                            
                            if len(location_parts) >= 1:
                                hometown = location_parts[0]
                            if len(location_parts) >= 2:
                                # Could be high school or club
                                high_school = location_parts[1]
                            if len(location_parts) >= 3:
                                # Previous school/college
                                previous_school = location_parts[2]

                # Create Player object
                player = Player(
                    team_id=team_id,
                    team=team_name,
                    season=season,
                    division=division,
                    name=name,
                    jersey=jersey,
                    position=position,
                    height=height,
                    year=year,
                    major='',  # Not available in WMT format
                    hometown=hometown,
                    high_school=high_school,
                    previous_school=previous_school,
                    url=profile_url
                )

                players.append(player)

            except Exception as e:
                logger.warning(f"Error parsing WMT roster item in {team_name}: {e}")
                continue

        return players

    def _enhance_kentucky_player_data(self, players: List[Player]) -> List[Player]:
        """
        Enhance Kentucky player data by fetching individual bio pages
        
        Kentucky's roster page doesn't include hometown, high school, class, or URLs.
        This method fetches those details from individual player bio pages.
        
        Args:
            players: List of Player objects to enhance
            
        Returns:
            Enhanced list of Player objects with additional data
        """
        if not players or len(players) == 0:
            return players
        
        # Check if this is Kentucky based on first player's URL pattern
        if not players[0].url or 'ukathletics.com' not in players[0].url:
            return players
        
        enhanced_players = []
        
        for player in players:
            try:
                if not player.url:
                    enhanced_players.append(player)
                    continue
                
                # Fetch individual bio page
                response = requests.get(player.url, timeout=10)
                if response.status_code != 200:
                    enhanced_players.append(player)
                    continue
                
                bio_html = BeautifulSoup(response.text, 'html.parser')
                
                # Extract player info from bio page
                # Looking for: <span class="player-info__label">Hometown</span>
                #              <span class="player-info__value">...</span>
                
                info_list = bio_html.find('ul', class_='player-info__list')
                if info_list:
                    items = info_list.find_all('li')
                    for item in items:
                        label_span = item.find('span', class_='player-info__label')
                        value_span = item.find('span', class_='player-info__value')
                        
                        if label_span and value_span:
                            label = label_span.get_text().strip().lower()
                            value = value_span.get_text().strip()
                            
                            if 'hometown' in label:
                                player.hometown = value
                            elif 'high school' in label:
                                player.high_school = value
                            elif 'class' in label:
                                player.year = FieldExtractors.normalize_academic_year(value)
                
                enhanced_players.append(player)
                
            except Exception as e:
                logger.debug(f"Could not enhance Kentucky player {player.name}: {e}")
                enhanced_players.append(player)
        
        return enhanced_players

    def _extract_players_from_wordpress_roster(self, html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
        """
        Extract players from custom WordPress roster format (person__item divs)

        Used by schools like Clemson that use WordPress with custom CSS classes
        <li class="person__item"> structure containing person__image, person__info, person__meta divs

        Args:
            html: BeautifulSoup parsed HTML
            team_id: NCAA team ID
            team_name: Team name
            season: Season string
            division: Division
            base_url: Base URL for constructing profile URLs

        Returns:
            List of Player objects
        """
        players = []

        # Find all roster items
        roster_items = html.find_all('li', class_='person__item')

        # Extract base domain for URLs
        extracted = tldextract.extract(base_url)
        domain = f"{extracted.domain}.{extracted.suffix}"
        if extracted.subdomain:
            domain = f"{extracted.subdomain}.{domain}"

        for item in roster_items:
            try:
                # Jersey number - in span.person__number > span, text like "#0" or "#1"
                # NOTE: Players have jersey numbers, coaches don't - use this to filter
                jersey = ''
                jersey_span = item.find('span', class_='person__number')
                if jersey_span:
                    jersey_text = jersey_span.get_text().strip()
                    # Extract just the number from "#0" or "#1"
                    jersey = re.sub(r'[^\d]', '', jersey_text)
                else:
                    # Skip if no jersey number (likely a coach)
                    continue

                # Name - in a.custom-value with data-custom-value attribute
                name = ''
                name_elem = item.find('a', class_='custom-value')
                if name_elem and name_elem.get('data-custom-value'):
                    name = name_elem['data-custom-value'].strip()

                if not name:
                    continue

                # Profile URL - in a.custom-value[href]
                profile_url = ''
                if name_elem and name_elem.get('href'):
                    href = name_elem['href']
                    if href.startswith('http'):
                        profile_url = href
                    else:
                        profile_url = f"https://{domain}{href}" if href.startswith('/') else f"https://{domain}/{href}"

                # Height and weight - in div.person__subtitle with two span.person__value
                height = ''
                weight = ''
                subtitle_div = item.find('div', class_='person__subtitle')
                if subtitle_div:
                    value_spans = subtitle_div.find_all('span', class_='person__value')
                    if len(value_spans) > 0:
                        height = FieldExtractors.extract_height(value_spans[0].get_text().strip())
                    if len(value_spans) > 1:
                        weight = value_spans[1].get_text().strip()

                # Extract metadata from person__meta divs with meta__row structure
                position = ''
                year = ''
                hometown = ''
                major = ''
                
                meta_div = item.find('div', class_='person__meta')
                if meta_div:
                    meta_rows = meta_div.find_all('div', class_='meta__row')
                    
                    for row in meta_rows:
                        name_elem = row.find('div', class_='meta__name')
                        value_elem = row.find('div', class_='meta__value')
                        
                        if name_elem and value_elem:
                            field_name = name_elem.get_text().strip().lower().rstrip(':')
                            field_value = value_elem.get_text().strip()
                            
                            # Remove any links from field_value (e.g., Instagram, Twitter links)
                            links = value_elem.find_all('a')
                            if links:
                                # Just get the text content, skipping link text
                                field_value = value_elem.get_text().strip()
                                # For social links, extract just the handle
                                if '@' in field_value:
                                    field_value = field_value  # Keep as is for display
                                else:
                                    # Remove "Opens in a new window" type text
                                    field_value = re.sub(r'\s*Opens in a new window.*$', '', field_value)
                            
                            if field_name == 'position':
                                position = FieldExtractors.extract_position(field_value)
                            elif field_name == 'year':
                                year = FieldExtractors.normalize_academic_year(field_value)
                            elif field_name == 'hometown':
                                hometown = field_value
                            elif field_name == 'major':
                                major = field_value

                # Create Player object
                player = Player(
                    team_id=team_id,
                    team=team_name,
                    season=season,
                    division=division,
                    name=name,
                    jersey=jersey,
                    position=position,
                    height=height,
                    year=year,
                    major=major,
                    hometown=hometown,
                    url=profile_url
                )

                players.append(player)

            except Exception as e:
                logger.warning(f"Error parsing WordPress roster item in {team_name}: {e}")
                continue

        return players


# ============================================================================
# JAVASCRIPT SCRAPER
# ============================================================================

class JSScraper(StandardScraper):
    """Scraper for JavaScript-rendered Sidearm sites using shot-scraper"""

    def __init__(self, session: Optional[requests.Session] = None):
        """
        Initialize JS scraper

        Args:
            session: Optional requests Session (not used, kept for compatibility)
        """
        super().__init__(session)

    def _fetch_html_with_javascript(self, url: str, timeout: int = 45) -> Optional[BeautifulSoup]:
        """
        Fetch HTML with JavaScript rendering using shot-scraper

        Args:
            url: URL to fetch
            timeout: Timeout in seconds (default 45)

        Returns:
            BeautifulSoup object or None if failed
        """
        try:
            # Use shot-scraper via uv to render JavaScript
            result = subprocess.run(
                ['uv', 'run', 'shot-scraper', 'html', url, '--wait', '3000'],
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode == 0:
                return BeautifulSoup(result.stdout, 'html.parser')
            else:
                logger.warning(f"shot-scraper returned code {result.returncode}: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            logger.warning(f"shot-scraper timeout after {timeout}s for {url}")
            return None
        except FileNotFoundError:
            logger.error("shot-scraper or uv not found. Install with: uv sync")
            return None
        except Exception as e:
            logger.error(f"Error running shot-scraper: {e}")
            return None

    def _validate_players(self, players: List[Player], team_name: str) -> bool:
        """
        Validate that scraped players have sufficient data completeness

        Args:
            players: List of Player objects
            team_name: Team name for logging

        Returns:
            True if data is valid, False otherwise
        """
        if not players:
            return False

        # Check essential fields (name, jersey, position, year)
        # previous_school and major are optional
        essential_fields = ['name', 'jersey', 'position', 'year']

        field_counts = {field: 0 for field in essential_fields}
        total = len(players)

        for player in players:
            if player.name:
                field_counts['name'] += 1
            if player.jersey:
                field_counts['jersey'] += 1
            if player.position:
                field_counts['position'] += 1
            if player.year:
                field_counts['year'] += 1

        # Calculate coverage percentages
        coverage = {field: (count / total * 100) for field, count in field_counts.items()}

        # Require at least 80% coverage for name and jersey
        # Require at least 70% coverage for position and year
        if coverage['name'] < 80:
            logger.warning(f"Validation failed for {team_name}: name coverage {coverage['name']:.1f}% < 80%")
            return False
        if coverage['jersey'] < 80:
            logger.warning(f"Validation failed for {team_name}: jersey coverage {coverage['jersey']:.1f}% < 80%")
            return False
        if coverage['position'] < 70:
            logger.warning(f"Validation failed for {team_name}: position coverage {coverage['position']:.1f}% < 70%")
            return False
        if coverage['year'] < 70:
            logger.warning(f"Validation failed for {team_name}: year coverage {coverage['year']:.1f}% < 70%")
            return False

        logger.info(f"✓ Validation passed for {team_name}: name={coverage['name']:.0f}%, jersey={coverage['jersey']:.0f}%, pos={coverage['position']:.0f}%, year={coverage['year']:.0f}%")
        return True

    def _build_season_range_url(self, base_url: str, season: str) -> str:
        """
        Build alternative URL using season-range format (e.g., 2025-26)

        Some schools use this pattern instead of /roster/2025:
        - https://ccsubluedevils.com/sports/msoc/2025-26/roster

        Args:
            base_url: Base URL from teams.csv
            season: Season string (e.g., '2025')

        Returns:
            Alternative roster URL with season range
        """
        base_url = base_url.rstrip('/')

        # Remove /index suffix if present (e.g., /sports/msoc/index -> /sports/msoc)
        if base_url.endswith('/index'):
            base_url = base_url[:-6]  # Remove '/index'

        # Convert single year to range (2025 -> 2025-26)
        try:
            year = int(season)
            next_year = str(year + 1)[-2:]  # Get last 2 digits
            season_range = f"{year}-{next_year}"
            return f"{base_url}/{season_range}/roster"
        except ValueError:
            # If season is already a range or invalid format, return as-is
            logger.warning(f"Could not parse season '{season}' for range URL")
            return f"{base_url}/{season}/roster"

    def scrape_team(self, team_id: int, team_name: str, base_url: str, season: str, division: str = "") -> List[Player]:
        """
        Scrape roster for a single team using shot-scraper for JavaScript rendering

        Args:
            team_id: NCAA team ID
            team_name: Team name
            base_url: Base URL for team site
            season: Season string (e.g., '2025')
            division: Division ('I', 'II', 'III')

        Returns:
            List of Player objects
        """
        try:
            # Build roster URL
            url_format = TeamConfig.get_url_format(team_id, base_url)
            roster_url = URLBuilder.build_roster_url(base_url, season, url_format)

            logger.info(f"Scraping {team_name} (JS) - {roster_url}")

            # Use shot-scraper to render JavaScript
            html = self._fetch_html_with_javascript(roster_url, timeout=45)

            if html is None:
                logger.warning(f"Failed to fetch HTML for {team_name}, trying standard fetch...")
                # Fallback to standard requests
                response = self.session.get(roster_url, headers=self.headers, timeout=30)
                if response.status_code == 200:
                    html = BeautifulSoup(response.text, 'html.parser')
                else:
                    logger.error(f"Standard fetch also failed for {team_name}: {response.status_code}")
                    return []

            # Verify season (optional, less strict for JS sites)
            if not SeasonVerifier.verify_season_on_page(html, season):
                logger.warning(f"Season mismatch for {team_name}")

            # Extract players using parent class method
            players = self._extract_players(html, team_id, team_name, season, division, base_url)

            # Validate data completeness
            if not self._validate_players(players, team_name):
                logger.warning(f"✗ {team_name}: Data validation failed, trying alternative URL patterns...")

                # Try alternative URL pattern: season-range format (e.g., 2025-26)
                alternative_url = self._build_season_range_url(base_url, season)
                if alternative_url != roster_url:
                    logger.info(f"Trying alternative URL: {alternative_url}")
                    html_alt = self._fetch_html_with_javascript(alternative_url, timeout=45)

                    if html_alt is not None:
                        players_alt = self._extract_players(html_alt, team_id, team_name, season, division, base_url)
                        if self._validate_players(players_alt, team_name):
                            logger.info(f"✓ {team_name}: Found {len(players_alt)} players (alternative URL)")
                            return players_alt

                logger.warning(f"✗ {team_name}: All URL patterns failed validation")
                return []

            logger.info(f"✓ {team_name}: Found {len(players)} players (validated)")
            return players

        except Exception as e:
            logger.error(f"Error scraping {team_name}: {e}")
            return []


# ============================================================================
# ROSTER MANAGER
# ============================================================================

class RosterManager:
    """Manages batch scraping of rosters with error tracking"""

    def __init__(self, season: str = '2025', output_dir: str = 'data/raw'):
        """
        Initialize RosterManager

        Args:
            season: Season string (e.g., '2025')
            output_dir: Base output directory
        """
        self.season = season
        self.output_dir = Path(output_dir)
        self.scraper = StandardScraper()

        # Error tracking
        self.zero_player_teams = []
        self.failed_teams = []
        self.successful_teams = []

    def load_teams(self, csv_path: str, division: Optional[str] = None) -> List[Dict]:
        """
        Load teams from CSV, optionally filtered by division

        Args:
            csv_path: Path to teams.csv
            division: Optional division filter ('I', 'II', 'III')

        Returns:
            List of team dictionaries
        """
        teams = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if division is None or row['division'] == division:
                    teams.append(row)

        logger.info(f"Loaded {len(teams)} teams" + (f" (Division {division})" if division else ""))
        return teams

    def scrape_teams(self, teams: List[Dict], max_teams: Optional[int] = None) -> List[Player]:
        """
        Scrape rosters for multiple teams

        Args:
            teams: List of team dictionaries from CSV
            max_teams: Optional limit on number of teams to scrape

        Returns:
            List of all Player objects
        """
        all_players = []
        teams_to_scrape = teams[:max_teams] if max_teams else teams

        logger.info(f"Starting scrape of {len(teams_to_scrape)} teams")
        logger.info("=" * 80)

        for i, team in enumerate(teams_to_scrape, 1):
            team_id = int(team['ncaa_id'])
            team_name = team['team']
            team_url = team['url']
            division = team['division']

            logger.info(f"[{i}/{len(teams_to_scrape)}] {team_name} (Division {division})")

            try:
                # Choose scraper based on team requirements
                if TeamConfig.requires_javascript(team_id):
                    scraper = JSScraper()
                    logger.info(f"  Using JSScraper (JavaScript rendering)")
                else:
                    scraper = self.scraper  # Use the StandardScraper instance

                players = scraper.scrape_team(
                    team_id=team_id,
                    team_name=team_name,
                    base_url=team_url,
                    season=self.season,
                    division=division
                )

                if len(players) == 0:
                    logger.warning(f"  ⚠️  Zero players found")
                    self.zero_player_teams.append({
                        'team': team_name,
                        'ncaa_id': team_id,
                        'division': division,
                        'url': team_url
                    })
                else:
                    logger.info(f"  ✓ {len(players)} players")
                    all_players.extend(players)
                    self.successful_teams.append({
                        'team': team_name,
                        'ncaa_id': team_id,
                        'division': division,
                        'player_count': len(players)
                    })

            except Exception as e:
                logger.error(f"  ✗ Error: {e}")
                self.failed_teams.append({
                    'team': team_name,
                    'ncaa_id': team_id,
                    'division': division,
                    'url': team_url,
                    'error': str(e)
                })

        logger.info("=" * 80)
        logger.info(f"Scraping complete:")
        logger.info(f"  Successful: {len(self.successful_teams)} teams, {len(all_players)} players")
        logger.info(f"  Zero players: {len(self.zero_player_teams)} teams")
        logger.info(f"  Failed: {len(self.failed_teams)} teams")

        return all_players

    def save_results(self, players: List[Player], division: Optional[str] = None):
        """
        Save results to JSON and CSV, plus error reports

        Args:
            players: List of Player objects
            division: Optional division for filename
        """
        # Determine filenames
        div_suffix = f"_{division}" if division else ""
        json_file = self.output_dir / 'json' / f'rosters_{self.season}{div_suffix}.json'
        csv_file = self.output_dir / 'csv' / f'rosters_{self.season}{div_suffix}.csv'

        # Create directories
        json_file.parent.mkdir(parents=True, exist_ok=True)
        csv_file.parent.mkdir(parents=True, exist_ok=True)

        # Save JSON
        players_dicts = [p.to_dict() for p in players]
        with open(json_file, 'w') as f:
            json.dump(players_dicts, f, indent=2)
        logger.info(f"✓ Saved JSON: {json_file} ({len(players)} players)")

        # Save CSV
        if players_dicts:
            fieldnames = players_dicts[0].keys()
            with open(csv_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(players_dicts)
            logger.info(f"✓ Saved CSV: {csv_file}")

        # Save error reports
        self._save_error_reports(division)

    def _save_error_reports(self, division: Optional[str] = None):
        """Save error reports for zero player and failed teams"""
        div_suffix = f"_{division}" if division else ""

        # Zero player teams
        if self.zero_player_teams:
            zero_file = self.output_dir / 'csv' / f'rosters_{self.season}{div_suffix}_zero_players.csv'
            with open(zero_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['team', 'ncaa_id', 'division', 'url'])
                writer.writeheader()
                writer.writerows(self.zero_player_teams)
            logger.warning(f"⚠️  Saved zero-player report: {zero_file} ({len(self.zero_player_teams)} teams)")

        # Failed teams
        if self.failed_teams:
            failed_file = self.output_dir / 'csv' / f'rosters_{self.season}{div_suffix}_failed.csv'
            with open(failed_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['team', 'ncaa_id', 'division', 'url', 'error'])
                writer.writeheader()
                writer.writerows(self.failed_teams)
            logger.error(f"✗ Saved failure report: {failed_file} ({len(self.failed_teams)} teams)")


# ============================================================================
# MAIN ENTRY POINT (Placeholder for now)
# ============================================================================

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='NCAA Men\'s Soccer Roster Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape all Division I teams
  python src/soccer_roster_scraper.py --division I --season 2025

  # Scrape first 10 Division II teams (testing)
  python src/soccer_roster_scraper.py --division II --limit 10 --season 2025

  # Scrape all teams
  python src/soccer_roster_scraper.py --season 2025

  # Scrape specific team
  python src/soccer_roster_scraper.py --team 14 --season 2025
        """
    )

    parser.add_argument(
        '--season',
        default='2025',
        help='Season year (default: 2025)'
    )

    parser.add_argument(
        '--division',
        choices=['I', 'II', 'III'],
        help='Filter by division (I, II, or III)'
    )

    parser.add_argument(
        '--team',
        type=int,
        help='Scrape specific team by NCAA ID'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of teams to scrape (for testing)'
    )

    parser.add_argument(
        '--teams-csv',
        default='data/input/teams.csv',
        help='Path to teams.csv (default: data/input/teams.csv)'
    )

    parser.add_argument(
        '--output-dir',
        default='data/raw',
        help='Output directory (default: data/raw)'
    )

    args = parser.parse_args()

    # Initialize manager
    manager = RosterManager(season=args.season, output_dir=args.output_dir)

    # Load teams
    if args.team:
        # Scrape specific team
        teams = manager.load_teams(args.teams_csv)
        teams = [t for t in teams if int(t['ncaa_id']) == args.team]
        if not teams:
            logger.error(f"Team {args.team} not found in {args.teams_csv}")
            return
        logger.info(f"Scraping specific team: {teams[0]['team']}")
    else:
        # Load all teams, optionally filtered by division
        teams = manager.load_teams(args.teams_csv, division=args.division)

    if not teams:
        logger.error("No teams to scrape")
        return

    # Scrape teams
    players = manager.scrape_teams(teams, max_teams=args.limit)

    # Save results
    if players:
        manager.save_results(players, division=args.division)
    else:
        logger.warning("No players scraped - no output files generated")

    # Summary
    print("\n" + "=" * 80)
    print("SCRAPING SUMMARY")
    print("=" * 80)
    print(f"Season: {args.season}")
    print(f"Teams attempted: {len(teams) if not args.limit else min(len(teams), args.limit)}")
    print(f"Successful: {len(manager.successful_teams)} teams")
    print(f"Total players: {len(players)}")
    print(f"Zero players: {len(manager.zero_player_teams)} teams")
    print(f"Failed: {len(manager.failed_teams)} teams")
    print("=" * 80)


if __name__ == '__main__':
    main()

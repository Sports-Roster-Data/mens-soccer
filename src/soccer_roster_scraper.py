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

    # Teams using standard Sidearm Sports pattern (majority of D-I)
    # Format: ncaa_id: {'url_format': 'default', 'notes': '...'}
    STANDARD_TEAMS = {
        14: {'url_format': 'default', 'notes': 'Albany - Sidearm Sports'},
        457: {'url_format': 'default', 'notes': 'UNC - Sidearm Sports (JS-rendered)'},
        # More teams will be added as we test and validate
    }

    # Teams using msoc URL pattern
    MSOC_TEAMS = {
        # Will be populated from analysis of existing scrapers
    }

    # Teams using data-label table pattern (mostly D-III)
    TABLE_TEAMS = {
        # Will be populated from d3teams.csv analysis
    }

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
        if team_id in cls.STANDARD_TEAMS:
            return cls.STANDARD_TEAMS[team_id].get('url_format', 'default')
        elif team_id in cls.MSOC_TEAMS:
            return cls.MSOC_TEAMS[team_id].get('url_format', 'msoc_index')
        elif team_id in cls.TABLE_TEAMS:
            return cls.TABLE_TEAMS[team_id].get('url_format', 'data_label')

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

            logger.info(f"✓ {team_name}: Found {len(players)} players")
            return players

        except requests.RequestException as e:
            logger.error(f"Request error for {team_name}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error scraping {team_name}: {e}")
            return []

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

        if not roster_items:
            logger.warning(f"No roster items found for {team_name} (expected class='sidearm-roster-player')")
            return []

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

                # Name and URL
                name_elem = item.find('h3')
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
                players = self.scraper.scrape_team(
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

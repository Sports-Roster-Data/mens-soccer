"""Roster URL construction for the various college-athletics platforms."""
import logging

import tldextract

logger = logging.getLogger(__name__)


class URLBuilder:
    """Build roster URLs for different site patterns."""

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

        # If a full roster URL is already provided, use it as-is
        if '/roster/' in base_url:
            return base_url

        if url_format == 'default':
            # Most common: Sidearm Sports pattern (87.6% of teams - 719 teams)
            # Example: https://ualbanysports.com/sports/mens-soccer/roster/2025
            return f"{base_url}/roster/{season}"

        elif url_format == 'sport_index':
            # msoc/index pattern (11.9% of teams - 98 teams)
            # teams.csv has /sports/msoc/index, need /sports/msoc/roster/2025
            # Example: https://aicyellowjackets.com/sports/msoc/roster/2025
            # These redirect to Sidearm HTML after following redirects
            if '/index' in base_url:
                return base_url.replace('/index', f'/roster/{season}')
            else:
                return f"{base_url}/roster/{season}"

        elif url_format == 'sport_plain':
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

        elif url_format == 'virginia_table':
            # Virginia table view adds ?view=table
            # Example: https://virginiasports.com/sports/msoc/roster/season/2025-26?view=table
            # Convert single year to range (2025 -> 2025-26)
            try:
                year = int(season)
                next_year = str(year + 1)[-2:]  # Get last 2 digits
                season_range = f"{year}-{next_year}"
                return f"{base_url}/roster/season/{season_range}?view=table"
            except ValueError:
                # If season is already a range, use as-is
                return f"{base_url}/roster/season/{season}?view=table"

        elif url_format == 'current_roster':
            # Season-less current roster. Some WMT sites (e.g. Arizona St.,
            # Texas A&M) 404 on explicit season slugs and only expose the
            # current roster at /roster; the page still renders the active
            # season's players.
            return f"{base_url}/roster"

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

        elif url_format == 'sport_season_range':
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

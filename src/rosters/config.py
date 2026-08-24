"""Sport configuration and team-list loading.

All sport-specific knowledge lives in SPORTS. Per-team overrides
(url_format, requires_js) live as columns in the teams CSVs, not in code.
"""
import csv
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

SPORTS = {
    'men': {
        'teams_file': 'data/input/teams.csv',
        'output_stem': 'rosters',
        'path_slugs': ['mens-soccer', 'm-soccer', 'msoc'],
        'roster_slug': 'mens-soccer',
    },
    'women': {
        'teams_file': 'data/input/teams_wsoc.csv',
        'output_stem': 'rosters_wsoc',
        'path_slugs': ['womens-soccer', 'w-soccer', 'wsoc'],
        'roster_slug': 'womens-soccer',
    },
}

TRUE_VALUES = {'true', 't', 'yes', 'y', '1'}


def _truthy(value: str) -> bool:
    return str(value or '').strip().lower() in TRUE_VALUES


def team_url_format(team: Dict) -> str:
    """Resolve a team's URL format: explicit CSV column wins, else auto-detect
    from the URL slug. Sport-neutral format names."""
    explicit = (team.get('url_format') or '').strip()
    if explicit:
        return explicit

    url = (team.get('url', '') or '').lower()
    if '/index' in url and ('/sports/msoc' in url or '/sports/wsoc' in url):
        return 'sport_index'
    if '/sports/msoc' in url or '/sports/wsoc' in url:
        return 'sport_plain'
    return 'default'


def team_requires_js(team: Dict) -> bool:
    return _truthy(team.get('requires_js'))


def load_teams(csv_path: str, division: Optional[str] = None) -> List[Dict]:
    """Load teams from CSV, optionally filtered by division.

    Tolerates both the men's schema (ncaa_id, division present) and any file
    missing a division column. Normalizes team_id -> ncaa_id.
    """
    teams: List[Dict] = []
    with open(csv_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'ncaa_id' not in row and 'team_id' in row:
                row['ncaa_id'] = row.get('team_id')
            if division is None or row.get('division', '') == division:
                teams.append(row)

    msg = f"Loaded {len(teams)} teams"
    if division:
        msg += f" (Division {division})"
        if not teams:
            logger.warning(
                f"No teams matched division '{division}' in {csv_path}; "
                "this file may lack division data."
            )
    logger.info(msg)
    return teams

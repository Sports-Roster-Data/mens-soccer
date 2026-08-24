"""Batch scraping orchestration and result persistence."""
import os
import csv
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .models import Player, CSV_FIELDS
from .config import SPORTS, load_teams
from .fetch import SESSION
from .scraper import scrape_team

logger = logging.getLogger(__name__)

RATE_LIMIT_SECONDS = 0.5


class RosterManager:
    """Runs a batch scrape and writes JSON/CSV plus error reports."""

    def __init__(self, sport: str, season: str, output_dir: str = 'data/raw'):
        self.sport_key = sport
        self.sport = SPORTS[sport]
        self.season = season
        self.output_dir = Path(output_dir)
        self.session = SESSION
        self.zero_player_teams: List[Dict] = []
        self.failed_teams: List[Dict] = []
        self.successful_teams: List[Dict] = []

    def scrape_teams(self, teams: List[Dict], max_teams: Optional[int] = None) -> List[Player]:
        all_players: List[Player] = []
        to_scrape = teams[:max_teams] if max_teams else teams

        logger.info(f"Starting scrape of {len(to_scrape)} teams")
        logger.info("=" * 80)

        for i, team in enumerate(to_scrape, 1):
            team_id = int(team.get('ncaa_id') or team.get('team_id'))
            team_name = team['team']
            division = team.get('division', '') or ''

            logger.info(f"[{i}/{len(to_scrape)}] {team_name}" + (f" (Division {division})" if division else ""))
            try:
                players = scrape_team(team, self.season, self.sport, self.session)
                if not players:
                    self.zero_player_teams.append({
                        'team': team_name, 'ncaa_id': team_id,
                        'division': division, 'url': team.get('url', ''),
                    })
                    logger.warning("  ⚠️  Zero players found")
                else:
                    all_players.extend(players)
                    self.successful_teams.append({
                        'team': team_name, 'ncaa_id': team_id,
                        'division': division, 'player_count': len(players),
                    })
                    logger.info(f"  ✓ {len(players)} players")
            except Exception as e:
                logger.error(f"  ✗ Error: {e}")
                self.failed_teams.append({
                    'team': team_name, 'ncaa_id': team_id, 'division': division,
                    'url': team.get('url', ''), 'error': str(e),
                })
            time.sleep(RATE_LIMIT_SECONDS)

        logger.info("=" * 80)
        logger.info("Scraping complete:")
        logger.info(f"  Successful: {len(self.successful_teams)} teams, {len(all_players)} players")
        logger.info(f"  Zero players: {len(self.zero_player_teams)} teams")
        logger.info(f"  Failed: {len(self.failed_teams)} teams")
        return all_players

    def save_results(self, players: List[Player], division: Optional[str] = None,
                     replace_ids: Optional[set] = None):
        stem = self.sport['output_stem']
        div_suffix = f"_{division}" if division else ""
        json_file = self.output_dir / 'json' / f'{stem}_{self.season}{div_suffix}.json'
        csv_file = self.output_dir / 'csv' / f'{stem}_{self.season}{div_suffix}.csv'
        json_file.parent.mkdir(parents=True, exist_ok=True)
        csv_file.parent.mkdir(parents=True, exist_ok=True)

        rows = [p.to_dict() for p in players]
        _write_json(json_file, rows, replace_ids)
        _write_csv(csv_file, rows, replace_ids)
        logger.info(f"✓ Saved {json_file} and {csv_file} ({len(rows)} new rows)")

        self._save_error_reports(stem, div_suffix)

    def _save_error_reports(self, stem: str, div_suffix: str):
        if self.zero_player_teams:
            f = self.output_dir / 'csv' / f'{stem}_{self.season}{div_suffix}_zero_players.csv'
            _write_report(f, self.zero_player_teams, ['team', 'ncaa_id', 'division', 'url'])
            logger.warning(f"⚠️  Zero-player report: {f} ({len(self.zero_player_teams)} teams)")
        if self.failed_teams:
            f = self.output_dir / 'csv' / f'{stem}_{self.season}{div_suffix}_failed.csv'
            _write_report(f, self.failed_teams, ['team', 'ncaa_id', 'division', 'url', 'error'])
            logger.error(f"✗ Failure report: {f} ({len(self.failed_teams)} teams)")


def _atomic_write(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(text)
    os.replace(tmp, path)


def _write_json(path: Path, rows: List[Dict], replace_ids: Optional[set]):
    if replace_ids and path.exists():
        existing = json.loads(path.read_text())
        kept = [r for r in existing if r.get('ncaa_id') not in replace_ids]
        rows = kept + rows
    _atomic_write(path, json.dumps(rows, indent=2))


def _write_csv(path: Path, rows: List[Dict], replace_ids: Optional[set]):
    if replace_ids and path.exists():
        with open(path, newline='') as f:
            existing = list(csv.DictReader(f))
        kept = [r for r in existing if str(r.get('ncaa_id')) not in {str(i) for i in replace_ids}]
        rows = kept + rows
    if not rows:
        return
    import io
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, '') for k in CSV_FIELDS})
    _atomic_write(path, buf.getvalue())


def _write_report(path: Path, records: List[Dict], fields: List[str]):
    import io
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    writer.writerows(records)
    _atomic_write(path, buf.getvalue())


def run(sport: str, season: str, division: Optional[str] = None,
        team_ids: Optional[List[int]] = None, max_teams: Optional[int] = None,
        teams_file: Optional[str] = None, output_dir: str = 'data/raw') -> List[Player]:
    manager = RosterManager(sport, season, output_dir)
    teams_file = teams_file or SPORTS[sport]['teams_file']

    if team_ids:
        all_teams = load_teams(teams_file)
        wanted = {str(t) for t in team_ids}
        teams = [t for t in all_teams if str(t.get('ncaa_id') or t.get('team_id')) in wanted]
        if not teams:
            logger.error(f"No matching teams for {team_ids} in {teams_file}")
            return []
    else:
        teams = load_teams(teams_file, division=division)

    if not teams:
        logger.error("No teams to scrape")
        return []

    players = manager.scrape_teams(teams, max_teams=max_teams)
    if players:
        # Targeted --team runs merge into the existing (undivided) season file.
        replace_ids = set(team_ids) if team_ids else None
        div = None if team_ids else division
        manager.save_results(players, division=div, replace_ids=replace_ids)
    else:
        logger.warning("No players scraped - no output files generated")
    return players

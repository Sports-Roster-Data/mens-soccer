"""CLI entry point:  python -m rosters --sport men --season 2025 [--division I]"""
import sys
import logging
import argparse
from pathlib import Path

# Resolve data paths relative to the repo root so the tool works from anywhere
# (shot-scraper and the default data/ paths are cwd-sensitive).
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

from .config import SPORTS
from .run import run

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="NCAA soccer roster scraper (men's and women's)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m rosters --sport men --season 2025 --division I
  python -m rosters --sport women --season 2025
  python -m rosters --sport men --season 2025 --team 746 334
""",
    )
    parser.add_argument('--sport', choices=sorted(SPORTS), default='men')
    parser.add_argument('--season', default='2025')
    parser.add_argument('--division', choices=['I', 'II', 'III'])
    parser.add_argument('--team', type=int, nargs='+', help='NCAA id(s); merges into the season file')
    parser.add_argument('--max-teams', type=int, help='Limit team count (testing)')
    parser.add_argument('--teams-file', help='Override the per-sport teams CSV')
    parser.add_argument('--output-dir', default=str(REPO_ROOT / 'data' / 'raw'))
    args = parser.parse_args(argv)

    teams_file = args.teams_file
    if teams_file is None:
        teams_file = str(REPO_ROOT / SPORTS[args.sport]['teams_file'])

    players = run(
        sport=args.sport, season=args.season, division=args.division,
        team_ids=args.team, max_teams=args.max_teams,
        teams_file=teams_file, output_dir=args.output_dir,
    )

    print("\n" + "=" * 80)
    print("SCRAPING SUMMARY")
    print("=" * 80)
    print(f"Sport: {args.sport}   Season: {args.season}")
    print(f"Total players: {len(players)}")
    print("=" * 80)
    return 0 if players else 1


if __name__ == '__main__':
    sys.exit(main())

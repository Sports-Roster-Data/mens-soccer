"""Per-team scrape orchestration: fetch -> (escalate) -> best_parse -> enhance."""
import logging
from html import unescape
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from . import parsers
from .models import Player
from .urls import URLBuilder
from .config import team_url_format, team_requires_js
from .extractors import FieldExtractors, SeasonVerifier
from .fetch import (SESSION, HEADERS, ROSTER_TIMEOUT, BIO_TIMEOUT, JS_TIMEOUT,
                    fetch_url, fetch_html_with_javascript, is_nuxt_page)

logger = logging.getLogger(__name__)


def validate_players(players: List[Player], team_name: str) -> bool:
    """Data-completeness gate for JS-rendered rosters. Relaxed for large
    rosters that legitimately omit position/year on the list view."""
    if not players:
        return False

    total = len(players)
    counts = {f: 0 for f in ('name', 'jersey', 'position', 'year')}
    for p in players:
        if p.name:
            counts['name'] += 1
        if p.jersey:
            counts['jersey'] += 1
        if p.position:
            counts['position'] += 1
        if p.year:
            counts['year'] += 1
    cov = {f: c / total * 100 for f, c in counts.items()}

    logger.info(
        f"Validation coverage for {team_name}: name={cov['name']:.1f}%, "
        f"jersey={cov['jersey']:.1f}%, pos={cov['position']:.1f}%, year={cov['year']:.1f}% (total={total})"
    )

    if cov['name'] < 80:
        logger.warning(f"Validation failed for {team_name}: name coverage {cov['name']:.1f}% < 80%")
        return False
    if cov['jersey'] < 80:
        if total >= 15 and cov['jersey'] >= 50:
            logger.info(f"Relaxed jersey validation for {team_name}: jersey={cov['jersey']:.1f}%")
        else:
            logger.warning(f"Validation failed for {team_name}: jersey coverage {cov['jersey']:.1f}% < 80%")
            return False
    if cov['position'] < 70 or cov['year'] < 70:
        if total >= 15 and (cov['position'] >= 50 or cov['year'] >= 50):
            logger.info(f"Relaxed validation for {team_name}: pos={cov['position']:.1f}%, year={cov['year']:.1f}%")
        elif total >= 15 and cov['name'] >= 80 and cov['jersey'] >= 50:
            logger.info(f"Fallback validation for {team_name}: accepting on name/jersey coverage")
        else:
            if cov['position'] < 70:
                logger.warning(f"Validation failed for {team_name}: position {cov['position']:.1f}% < 70%")
            if cov['year'] < 70:
                logger.warning(f"Validation failed for {team_name}: year {cov['year']:.1f}% < 70%")
            return False

    return True


def enhance_kentucky_player_data(players: List[Player], session: requests.Session) -> List[Player]:
    """Fill hometown/high_school/class from bio pages. Self-gating: only acts on
    ukathletics.com rosters, so it is safe to call unconditionally."""
    if not players or not players[0].url or 'ukathletics.com' not in players[0].url:
        return players

    out = []
    for player in players:
        try:
            if not player.url:
                out.append(player)
                continue
            resp = session.get(player.url, timeout=BIO_TIMEOUT)
            if resp.status_code != 200:
                out.append(player)
                continue
            bio = BeautifulSoup(resp.text, 'html.parser')
            info_list = bio.find('ul', class_='player-info__list')
            if info_list:
                for item in info_list.find_all('li'):
                    label = item.find('span', class_='player-info__label')
                    value = item.find('span', class_='player-info__value')
                    if label and value:
                        lt = label.get_text().strip().lower()
                        v = value.get_text().strip()
                        if 'hometown' in lt:
                            player.hometown = v
                        elif 'high school' in lt:
                            player.high_school = v
                        elif 'class' in lt:
                            player.year = FieldExtractors.normalize_academic_year(v)
            out.append(player)
        except Exception as e:
            logger.debug(f"Could not enhance Kentucky player {player.name}: {e}")
            out.append(player)
    return out


def enhance_sidearm_positions_from_bios(players: List[Player], team_name: str,
                                        session: requests.Session) -> List[Player]:
    """Fill missing positions from individual Sidearm bio pages."""
    if not players:
        return players
    missing = sum(1 for p in players if not p.position)
    if missing == 0:
        return players

    logger.info(f"Enhancing {missing} players with bio-page position data for {team_name}...")
    out = []
    for player in players:
        try:
            if player.position or not player.url:
                out.append(player)
                continue
            resp = session.get(player.url, timeout=BIO_TIMEOUT)
            if resp.status_code != 200:
                out.append(player)
                continue
            bio = BeautifulSoup(resp.text, 'html.parser')
            for label in bio.find_all('span', class_='sidearm-roster-player-field-label'):
                if 'position' in label.get_text().strip().lower():
                    parent = label.find_parent('div')
                    if parent:
                        for span in parent.find_all('span'):
                            if 'sidearm-roster-player-field-label' not in span.get('class', []):
                                player.position = FieldExtractors.extract_position(span.get_text().strip())
                                break
                    if player.position:
                        break
            out.append(player)
        except Exception as e:
            logger.debug(f"Could not enhance player {player.name}: {e}")
            out.append(player)
    return out


def enhance_sidearm_schools_from_bios(players: List[Player], team_name: str,
                                      session: requests.Session) -> List[Player]:
    """Fill missing high_school / previous_school from Sidearm bio pages.

    Some Sidearm list/card views omit the school fields even though each
    player's bio page carries them as cleanly-labeled <dl> ranked fields. This
    fetches those bios (one request per player) only when the roster is
    missing high-school data for the majority of players, and it self-gates:
    bios without the labels (e.g. sites that expose only a single school field)
    leave the player unchanged.
    """
    if not players:
        return players

    total = len(players)
    missing = [p for p in players if not p.high_school and p.url]
    # Only worth the per-player fetches when most of the roster lacks it.
    if not missing or len(missing) / total <= 0.5:
        return players

    logger.info(f"Enhancing {len(missing)} players with bio-page school data for {team_name}...")
    for player in missing:
        try:
            resp = session.get(player.url, timeout=BIO_TIMEOUT)
            if resp.status_code != 200:
                continue
            bio = BeautifulSoup(resp.text, 'html.parser')
            hs, prev = parsers.parse_bio_schools(bio)
            if hs and not player.high_school:
                player.high_school = hs
            if prev and not player.previous_school:
                player.previous_school = prev
        except Exception as e:
            logger.debug(f"Could not enhance schools for {player.name}: {e}")
    return players


def fetch_oas_players(html_text, team_id, team_name, season, division, base_url,
                      roster_slug, session) -> List[Player]:
    """Fetch and parse a WMT OAS API roster referenced in the page HTML."""
    api_url = parsers.build_oas_api_url(html_text)
    if not api_url:
        return []
    # build_oas_api_url may return a placeholder host when the embedded URL was
    # relative; repoint it at the team's real origin.
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(api_url)
    base = urlparse(base_url)
    if parsed.netloc in ('placeholder', 'oas-backend') and base.netloc:
        api_url = urlunparse(parsed._replace(netloc=base.netloc, scheme=base.scheme or 'https'))
    try:
        resp = session.get(api_url, timeout=ROSTER_TIMEOUT)
        if resp.status_code != 200:
            logger.warning(f"WMT OAS API request failed for {team_name}: {resp.status_code}")
            return []
        payload = resp.json()
    except Exception as e:
        logger.warning(f"WMT OAS API error for {team_name}: {e}")
        return []
    return parsers.parse_oas_payload(payload, team_id, team_name, season, division,
                                     base_url, roster_slug=roster_slug)


def _extract(html, team_id, team_name, season, division, base_url, roster_slug, session):
    """OAS check first (WMT sites), then the self-healing layout probe."""
    html_text = unescape(str(html))
    if 'website-api/player-rosters' in html_text:
        logger.info(f"Detected WMT OAS API roster data for {team_name}, using API parser")
        oas = fetch_oas_players(html_text, team_id, team_name, season, division,
                                base_url, roster_slug, session)
        if oas:
            return oas
    return parsers.best_parse(html, team_id, team_name, season, division, base_url)


def scrape_team(team, season, sport, session: Optional[requests.Session] = None) -> List[Player]:
    """Scrape one team's roster.

    team: dict with ncaa_id, team, url, and optional division/url_format/requires_js.
    sport: an entry from config.SPORTS (for roster_slug).
    """
    session = session or SESSION
    team_id = int(team.get('ncaa_id') or team.get('team_id'))
    team_name = team['team']
    base_url = team['url']
    division = team.get('division', '') or ''
    roster_slug = sport['roster_slug']

    url_format = team_url_format(team)
    roster_url = URLBuilder.build_roster_url(base_url, season, url_format)

    try:
        if team_requires_js(team):
            return _scrape_js(team_id, team_name, base_url, season, division,
                              roster_url, roster_slug, session)

        logger.info(f"Scraping {team_name} - {roster_url}")
        response = fetch_url(roster_url, session)

        if response.status_code == 404:
            alt = _season_range_url(base_url, season)
            if alt != roster_url:
                response = fetch_url(alt, session)
                roster_url = alt
        if response.status_code != 200:
            no_season = f"{base_url.rstrip('/')}/roster/"
            if no_season != roster_url:
                response = fetch_url(no_season, session)
                roster_url = no_season
        if response.status_code != 200:
            logger.warning(f"Failed to retrieve {team_name} - Status: {response.status_code}")
            return []

        html = BeautifulSoup(response.content, 'html.parser')
        if not SeasonVerifier.verify_season_on_page(html, season):
            logger.warning(f"Season mismatch for {team_name}")

        players = _extract(html, team_id, team_name, season, division, base_url, roster_slug, session)

        if not players and not roster_url.endswith('/roster/'):
            no_season = f"{base_url.rstrip('/')}/roster/"
            if no_season != roster_url:
                r2 = fetch_url(no_season, session)
                if r2.status_code == 200:
                    html = BeautifulSoup(r2.content, 'html.parser')
                    players = _extract(html, team_id, team_name, season, division, base_url, roster_slug, session)

        # Auto-escalate to JS rendering for client-rendered (Nuxt) skeletons.
        if not players and is_nuxt_page(html):
            logger.info(f"{team_name}: page looks client-rendered (Nuxt); escalating to JS")
            return _scrape_js(team_id, team_name, base_url, season, division,
                              roster_url, roster_slug, session)

        players = enhance_kentucky_player_data(players, session)

        missing = sum(1 for p in players if not p.position and p.url)
        if players and missing / len(players) > 0.2:
            players = enhance_sidearm_positions_from_bios(players, team_name, session)

        players = enhance_sidearm_schools_from_bios(players, team_name, session)

        logger.info(f"✓ {team_name}: Found {len(players)} players")
        return players

    except requests.RequestException as e:
        logger.error(f"Request error for {team_name}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error scraping {team_name}: {e}")
        return []


def _scrape_js(team_id, team_name, base_url, season, division, roster_url,
               roster_slug, session) -> List[Player]:
    logger.info(f"Scraping {team_name} (JS) - {roster_url}")
    html = fetch_html_with_javascript(roster_url, timeout=JS_TIMEOUT)
    if html is None:
        resp = fetch_url(roster_url, session)
        if resp.status_code == 200:
            html = BeautifulSoup(resp.text, 'html.parser')
        else:
            logger.error(f"JS and standard fetch both failed for {team_name}: {resp.status_code}")
            return []

    if not SeasonVerifier.verify_season_on_page(html, season):
        logger.warning(f"Season mismatch for {team_name}")

    players = _extract(html, team_id, team_name, season, division, base_url, roster_slug, session)
    if players:
        logger.info(f"✓ {team_name}: Found {len(players)} players")
        return players

    if not validate_players(players, team_name):
        alt = _season_range_url(base_url, season)
        if alt != roster_url:
            logger.info(f"Trying alternative URL: {alt}")
            html_alt = fetch_html_with_javascript(alt, timeout=JS_TIMEOUT)
            if html_alt is not None:
                players_alt = _extract(html_alt, team_id, team_name, season, division,
                                       base_url, roster_slug, session)
                if validate_players(players_alt, team_name):
                    logger.info(f"✓ {team_name}: Found {len(players_alt)} players (alternative URL)")
                    return players_alt
        return []
    return players


def _season_range_url(base_url, season):
    base_url = base_url.rstrip('/')
    if base_url.endswith('/index'):
        base_url = base_url[:-6]
    try:
        year = int(season)
        return f"{base_url}/{year}-{str(year + 1)[-2:]}/roster"
    except ValueError:
        logger.warning(f"Could not parse season '{season}' for range URL")
        return f"{base_url}/{season}/roster"

"""
Layout parsers for NCAA soccer roster pages.

Every parser has the signature
    parse_<layout>(html, team_id, team_name, season, division, base_url) -> List[Player]
and is PURE: it takes parsed HTML and returns players, doing no network I/O.
This lets best_parse() probe them in order and lets tests run fully offline
against captured HTML fixtures.

The bodies here were moved verbatim from the original monolith scrapers
(dedent + rename only) to preserve behaviour; see scripts/build_parsers.py.
"""
import re
import logging
from typing import List

import tldextract

from .models import Player
from .extractors import FieldExtractors

logger = logging.getLogger(__name__)



def parse_sidearm_players(html, team_id, team_name, season, division, base_url):
    """Extract players from the standard Sidearm `sidearm-roster-player` list."""
    players = []
    roster_items = html.find_all('li', class_='sidearm-roster-player')
    if not roster_items:
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
            if not pos_elem:
                # Alternative: position in text-bold span within sidearm-roster-player-position div
                pos_div = item.find('div', class_='sidearm-roster-player-position')
                if pos_div:
                    pos_elem = pos_div.find('span', class_='text-bold')

            # Extract position text
            if pos_elem:
                position = FieldExtractors.extract_position(pos_elem.get_text())
            else:
                # Fallback: look for any span with position-related class name
                position = ''
                all_spans = item.find_all('span')
                for span in all_spans:
                    span_class = ' '.join(span.get('class', [])).lower()
                    if 'position' in span_class or 'pos' in span_class:
                        position = FieldExtractors.extract_position(span.get_text())
                        if position:  # Found valid position
                            break

                # If still no position, look for any div with position-related class
                if not position:
                    all_divs = item.find_all('div')
                    for div in all_divs:
                        div_class = ' '.join(div.get('class', [])).lower()
                        if 'position' in div_class or 'pos' in div_class:
                            position = FieldExtractors.extract_position(div.get_text())
                            if position:  # Found valid position
                                break

            # Height
            height_elem = item.find('span', class_='sidearm-roster-player-height')
            height = FieldExtractors.extract_height(height_elem.get_text()) if height_elem else ''

            # Academic year
            year_elem = item.find('span', class_='sidearm-roster-player-academic-year')
            year = FieldExtractors.normalize_academic_year(year_elem.get_text()) if year_elem else ''

            # Major (soccer-specific)
            major_elem = item.find('span', class_='sidearm-roster-player-major')
            major = FieldExtractors.clean_text(major_elem.get_text()) if major_elem else ''

            # Hometown (check standard field, then custom2)
            hometown_elem = item.find('span', class_='sidearm-roster-player-hometown')
            if not hometown_elem:
                hometown_elem = item.find('span', class_='sidearm-roster-player-custom2')
            hometown = FieldExtractors.clean_text(hometown_elem.get_text()) if hometown_elem else ''

            # High school (check standard field, then custom3)
            hs_elem = item.find('span', class_='sidearm-roster-player-highschool')
            if not hs_elem:
                hs_elem = item.find('span', class_='sidearm-roster-player-custom3')
            high_school = FieldExtractors.clean_text(hs_elem.get_text()) if hs_elem else ''

            # Previous school (check standard field, then custom1)
            prev_elem = item.find('span', class_='sidearm-roster-player-previous-school')
            if not prev_elem:
                prev_elem = item.find('span', class_='sidearm-roster-player-custom1')
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



def parse_kentucky_table(html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
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



def parse_generic_roster_table(html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
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



def parse_data_field_table(html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
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



def parse_list_items(html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
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
            link_elem = item.find(class_='sidearm-roster-list-item-link')
            if not link_elem:
                continue

            # Jersey number - in photo div, inside a span
            jersey = ''
            number_box = item.find('div', class_='sidearm-roster-list-item-number')
            if number_box:
                jersey = FieldExtractors.extract_jersey_number(number_box.get_text())
            photo_number = item.find('div', class_='sidearm-roster-list-item-photo-number')
            if photo_number:
                number_span = photo_number.find('span')
                if number_span:
                    jersey = FieldExtractors.clean_text(number_span.get_text())
                else:
                    jersey = FieldExtractors.clean_text(photo_number.get_text())
            # Fallback: any element with number/jersey class
            if not jersey:
                number_elem = item.find(class_=lambda x: x and ('number' in x.lower() or 'jersey' in x.lower()) if x else False)
                if number_elem:
                    jersey = FieldExtractors.extract_jersey_number(number_elem.get_text())

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

            # Fallback: any anchor with visible text
            if not name:
                for link in item.find_all('a', href=True):
                    link_text = FieldExtractors.clean_text(link.get_text())
                    if link_text:
                        name = link_text
                        href = link['href']
                        if href.startswith('http'):
                            profile_url = href
                        else:
                            profile_url = f"https://{domain}{href}" if href.startswith('/') else f"https://{domain}/{href}"
                        break

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

            # Fallback: look for any span with position-related class name
            if not position:
                all_spans = item.find_all('span')
                for span in all_spans:
                    span_class = ' '.join(span.get('class', [])).lower()
                    if 'position' in span_class or 'pos' in span_class:
                        position = FieldExtractors.extract_position(span.get_text())
                        if position:  # Found valid position
                            break

            # If still no position, look for any div with position-related class
            if not position:
                all_divs = item.find_all('div')
                for div in all_divs:
                    div_class = ' '.join(div.get('class', [])).lower()
                    if 'position' in div_class or 'pos' in div_class:
                        position = FieldExtractors.extract_position(div.get_text())
                        if position:  # Found valid position
                            break

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



def parse_card_items(html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
    """
    Extract players from sidearm-list-card-item format (used by Elmira and similar schools)

    This format uses <li class="sidearm-list-card-item"> with player data in card structure

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

    # Find all card items
    card_items = html.find_all('li', class_='sidearm-list-card-item')

    # Extract base domain for URLs
    extracted = tldextract.extract(base_url)
    domain = f"{extracted.domain}.{extracted.suffix}"
    if extracted.subdomain:
        domain = f"{extracted.subdomain}.{domain}"

    for item in card_items:
        try:
            # Jersey number - in sidearm-roster-player-jersey span
            jersey = ''
            jersey_elem = item.find('span', class_='sidearm-roster-player-jersey')
            if jersey_elem:
                jersey_span = jersey_elem.find('span')
                if jersey_span:
                    jersey = FieldExtractors.extract_jersey_number(jersey_span.get_text())

            # Name and URL - in sidearm-roster-player-name link
            name = ''
            profile_url = ''
            name_elem = item.find('a', class_='sidearm-roster-player-name')
            if name_elem:
                name = FieldExtractors.clean_text(name_elem.get_text())
                if name_elem.get('href'):
                    href = name_elem['href']
                    if href.startswith('http'):
                        profile_url = href
                    else:
                        profile_url = f"https://{domain}{href}" if href.startswith('/') else f"https://{domain}/{href}"

            if not name:
                continue

            # Position - in sidearm-roster-player-position-short div
            position = ''
            pos_elem = item.find('div', class_='sidearm-roster-player-position-short')
            if pos_elem:
                position = FieldExtractors.extract_position(pos_elem.get_text())

            # Height, weight, year - often in combined div
            height = ''
            year = ''
            hwyr_elem = item.find('div', class_='sidearm-roster-details-height-weight-year-custom')
            if hwyr_elem:
                text = hwyr_elem.get_text()
                height = FieldExtractors.extract_height(text)
                year = FieldExtractors.normalize_academic_year(text)

            # Hometown and schools - in combined div
            hometown = ''
            high_school = ''
            hs_elem = item.find('div', class_='sidearm-roster-details-hometown-schools')
            if hs_elem:
                text = FieldExtractors.clean_text(hs_elem.get_text())
                # Usually format like "City, State / High School"
                if '/' in text:
                    parts = text.split('/', 1)
                    hometown = parts[0].strip()
                    high_school = parts[1].strip()
                else:
                    hometown = text

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
            logger.warning(f"Error parsing card-item in {team_name}: {e}")
            continue

    return players



def parse_table(html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
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
        elif 'yr' in header_text or 'year' in header_text or 'class' in header_text or 'cl.' in header_text:
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
            all_cells = row.find_all(['td', 'th'])

            # Filter out hidden cells used for responsive design (d-md-none, d-none, etc.)
            # These create duplicate cells that break column index mapping
            cells = []
            for cell in all_cells:
                cell_classes = cell.get('class', [])
                # Skip cells that are hidden on desktop (d-md-none) or always hidden (d-none)
                if 'd-md-none' in cell_classes:
                    continue
                cells.append(cell)

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
                jersey_cell = cells[header_map['jersey']]
                # Remove label spans if they exist
                for label_span in jersey_cell.find_all('span', class_='label'):
                    label_span.decompose()
                jersey = FieldExtractors.clean_text(jersey_cell.get_text())

            # Extract Position
            position = ''
            if 'position' in header_map:
                pos_cell = cells[header_map['position']]
                # Remove label spans if they exist
                for label_span in pos_cell.find_all('span', class_='label'):
                    label_span.decompose()
                position = FieldExtractors.extract_position(pos_cell.get_text())

            # Extract Height
            height = ''
            if 'height' in header_map:
                height_cell = cells[header_map['height']]
                # Remove label spans if they exist
                for label_span in height_cell.find_all('span', class_='label'):
                    label_span.decompose()
                height = FieldExtractors.extract_height(height_cell.get_text())

            # Extract Year/Class
            year = ''
            if 'year' in header_map:
                year_cell = cells[header_map['year']]
                # Remove label spans if they exist
                for label_span in year_cell.find_all('span', class_='label'):
                    label_span.decompose()
                year = FieldExtractors.normalize_academic_year(year_cell.get_text())

            # Extract Hometown / High School
            hometown = ''
            high_school = ''
            if 'hometown' in header_map:
                hometown_cell = cells[header_map['hometown']]
                # Remove label spans if they exist
                for label_span in hometown_cell.find_all('span', class_='label'):
                    label_span.decompose()
                hometown_hs = FieldExtractors.clean_text(hometown_cell.get_text())
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



def parse_presto_table(html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
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



def parse_cards(html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
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



def parse_generic_cards(html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
    """
    Extract players from generic card-based layout (player-card divs)

    Used by schools like Goucher and Carlow that use a simple card structure with
    <div class="player-card"> containing player information

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

    # Find all player cards - look for exact class 'player-card' to avoid matching wrapper/footer
    cards = html.find_all('div', class_=lambda x: 'player-card' in x.split() if x else False)

    # Extract base domain for URLs
    extracted = tldextract.extract(base_url)
    domain = f"{extracted.domain}.{extracted.suffix}"
    if extracted.subdomain:
        domain = f"{extracted.subdomain}.{domain}"

    for card in cards:
        try:
            # Find link first (needed for both name and URL)
            name_link = card.find('a', href=True)

            # Extract name - check for firstname/lastname structure first
            name = ''
            firstname_elem = card.find('span', class_='firstname')
            lastname_elem = card.find('span', class_='lastname')
            if firstname_elem and lastname_elem:
                firstname = FieldExtractors.clean_text(firstname_elem.get_text())
                lastname = FieldExtractors.clean_text(lastname_elem.get_text())
                name = f"{firstname} {lastname}"

            # Fallback: look for name in link
            if not name and name_link:
                name_span = name_link.find('span', class_='name')
                if name_span:
                    name = FieldExtractors.clean_text(name_span.get_text())
                else:
                    name = FieldExtractors.clean_text(name_link.get_text())

            # Final fallback: any header element
            if not name:
                for tag in ['h2', 'h3', 'h4']:
                    name_elem = card.find(tag)
                    if name_elem:
                        name = FieldExtractors.clean_text(name_elem.get_text())
                        if name and len(name) > 3:  # Basic validation
                            break

            if not name:
                continue

            # Extract jersey number - look for specific classes and patterns
            jersey = ''
            # Try 'number' class first (Goucher uses this)
            number_elem = card.find('span', class_='number')
            if number_elem:
                jersey = FieldExtractors.extract_jersey_number(number_elem.get_text())
            else:
                # Try generic jersey class
                jersey_elem = card.find(class_=lambda x: x and 'jersey' in x.lower() if x else False)
                if jersey_elem:
                    jersey = FieldExtractors.extract_jersey_number(jersey_elem.get_text())
                else:
                    # Look for any number in the card
                    card_text = card.get_text()
                    jersey = FieldExtractors.extract_jersey_number(card_text)

            # Check for bio-attr-short structure (Carlow uses this)
            # Contains 3 spans in order: position, year, height
            bio_attr = card.find('div', class_='bio-attr-short')
            position = ''
            year = ''
            height = ''

            if bio_attr:
                spans = bio_attr.find_all('span', class_='text-muted')
                if len(spans) >= 1:
                    position = FieldExtractors.extract_position(spans[0].get_text())
                if len(spans) >= 2:
                    year = FieldExtractors.normalize_academic_year(spans[1].get_text())
                if len(spans) >= 3:
                    height = FieldExtractors.extract_height(spans[2].get_text())

            # If bio-attr-short didn't provide data, try individual element extraction
            if not position:
                pos_elem = card.find(class_=lambda x: x and 'position' in x.lower() if x else False)
                if pos_elem:
                    position = FieldExtractors.extract_position(pos_elem.get_text())
                else:
                    # Try to find position in text
                    card_text = card.get_text()
                    position = FieldExtractors.extract_position(card_text)

            if not year:
                year_elem = card.find(class_=lambda x: x and ('year' in x.lower() or 'class' in x.lower()) if x else False)
                if year_elem:
                    year = FieldExtractors.normalize_academic_year(year_elem.get_text())
                else:
                    # Try to find year in text
                    card_text = card.get_text()
                    year = FieldExtractors.normalize_academic_year(card_text)

            if not height:
                height_elem = card.find(class_=lambda x: x and 'height' in x.lower() if x else False)
                if height_elem:
                    height = FieldExtractors.extract_height(height_elem.get_text())
                else:
                    # Try to find height in text
                    card_text = card.get_text()
                    height = FieldExtractors.extract_height(card_text)

            # Extract hometown and high school from bio-data section (Goucher uses this)
            hometown = ''
            high_school = ''
            previous_school = ''

            bio_data = card.find('div', class_='bio-data')
            if bio_data:
                # Parse list items with labels
                list_items = bio_data.find_all('li')
                for item in list_items:
                    item_text = item.get_text()
                    if 'Hometown:' in item_text:
                        # Remove the label and get the value
                        label_span = item.find('span', class_='fw-bold')
                        if label_span:
                            label_span.decompose()
                        hometown = FieldExtractors.clean_text(item.get_text())
                    elif 'Highschool:' in item_text or 'High School:' in item_text:
                        label_span = item.find('span', class_='fw-bold')
                        if label_span:
                            label_span.decompose()
                        high_school = FieldExtractors.clean_text(item.get_text())
                    elif 'Previous School:' in item_text or 'Prior School:' in item_text:
                        label_span = item.find('span', class_='fw-bold')
                        if label_span:
                            label_span.decompose()
                        previous_school = FieldExtractors.clean_text(item.get_text())

            # Fallback: try class-based search if bio-data didn't work
            if not hometown:
                hometown_elem = card.find(class_=lambda x: x and 'hometown' in x.lower() if x else False)
                if hometown_elem:
                    hometown = FieldExtractors.clean_text(hometown_elem.get_text())

            if not high_school:
                hs_elem = card.find(class_=lambda x: x and 'school' in x.lower() if x else False)
                if hs_elem:
                    high_school = FieldExtractors.clean_text(hs_elem.get_text())

            # Extract profile URL
            profile_url = ''
            if name_link:
                href = name_link['href']
                if href.startswith('http'):
                    profile_url = href
                else:
                    profile_url = f"https://{domain}{href}" if href.startswith('/') else f"https://{domain}/{href}"

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
            logger.warning(f"Error parsing generic card in {team_name}: {e}")
            continue

    return players



def parse_wmt(html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
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



def parse_wmt_cards(html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
    """Newer WMT Digital 'roster-card' card layout (e.g. Arizona St., Texas A&M).

    Player cards are <div class="roster-card"> with the name in
    a.roster-card__title-link, jersey in strong.roster-card__jersey-number,
    position/hometown in dedicated spans, and height/class in
    .roster-player-card-profile-field__value--basic spans. Staff cards carry an
    extra 'roster-staff-members-card-item' class and are skipped.
    """
    from urllib.parse import urljoin

    CLASS_WORDS = ('freshman', 'sophomore', 'junior', 'senior', 'graduate', 'redshirt')
    players = []
    for card in html.find_all('div', class_='roster-card'):
        try:
            if 'roster-staff-members-card-item' in card.get('class', []):
                continue

            link = card.find('a', class_='roster-card__title-link')
            name = link.get_text(strip=True) if link else ''
            if not name:
                continue

            jersey = ''
            jnum = card.find('strong', class_='roster-card__jersey-number')
            if jnum:
                jersey = jnum.get_text(strip=True).lstrip('#').strip()

            profile_url = ''
            if link and link.get('href'):
                profile_url = urljoin(base_url, link['href'])

            pos_el = card.find('span', class_='roster-card__position')
            position = FieldExtractors.extract_position(pos_el.get_text(strip=True)) if pos_el else ''

            home_el = card.find('span', class_='roster-card__hometown')
            hometown = home_el.get_text(strip=True) if home_el else ''

            height = ''
            year = ''
            for span in card.select('.roster-player-card-profile-field__value--basic'):
                text = span.get_text(strip=True)
                if not text:
                    continue
                h = FieldExtractors.extract_height(text)
                if h and not height:
                    height = h
                elif not year and any(w in text.lower() for w in CLASS_WORDS):
                    year = FieldExtractors.normalize_academic_year(text)

            players.append(Player(
                team_id=team_id, team=team_name, season=season, division=division,
                name=name, jersey=jersey, position=position, height=height, year=year,
                major='', hometown=hometown, high_school='', previous_school='',
                url=profile_url,
            ))
        except Exception as e:
            logger.warning(f"Error parsing WMT card in {team_name}: {e}")
            continue

    return players


def parse_wordpress_roster(html, team_id: int, team_name: str, season: str, division: str, base_url: str) -> List[Player]:
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



def parse_bio_schools(soup):
    """Pull (high_school, previous_school) from a Sidearm player bio page.

    Sidearm bios list ranked fields as <dl><dt>Label:</dt><dd>Value</dd></dl>.
    Returns a tuple of cleaned strings; each is '' when its label is absent, so
    a site that exposes only a "Previous School" field yields no high_school
    (we never invent one). Pure.
    """
    high_school = ''
    previous_school = ''
    for dt in soup.find_all('dt'):
        label = dt.get_text(strip=True).rstrip(':').strip().lower()
        if label not in ('high school', 'prev school', 'previous school'):
            continue
        dd = dt.find_next_sibling('dd')
        value = FieldExtractors.clean_text(dd.get_text()) if dd else ''
        if not value:
            continue
        if label == 'high school' and not high_school:
            high_school = value
        elif label in ('prev school', 'previous school') and not previous_school:
            previous_school = value
    return high_school, previous_school


# ============================================================================
# WMT OAS JSON API (split into pure helpers; the network GET lives in scraper)
# ============================================================================

def build_oas_api_url(html_text: str):
    """Find and normalize the WMT OAS player-rosters API URL embedded in a
    rendered page. Returns a fully-qualified URL string, or None. Pure."""
    from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

    api_match = (re.search(r'https?://[^"\s]*?/website-api/player-rosters[^"\s]*', html_text)
                 or re.search(r'/website-api/player-rosters[^"\s]*', html_text)
                 or re.search(r'website-api/player-rosters[^"\s]*', html_text))
    if not api_match:
        return None

    api_url = api_match.group(0)
    parsed = urlparse(api_url if api_url.startswith('http') else f"https://placeholder/{api_url.lstrip('/')}")

    qs = parse_qs(parsed.query)
    include_raw = qs.get('include', [''])[0]
    include_parts = [p for p in include_raw.split(',') if p]
    for inc in ['player', 'photo', 'classLevel', 'playerPosition',
                'profileFieldValues.profileField', 'profileFieldValues',
                'roster.sport', 'roster.season']:
        if inc not in include_parts:
            include_parts.append(inc)
    qs['include'] = [','.join(include_parts)]
    qs.setdefault('per_page', ['200'])
    qs.setdefault('page', ['1'])

    return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))


def parse_oas_payload(payload, team_id, team_name, season, division, base_url, roster_slug='mens-soccer'):
    """Convert a WMT OAS API JSON payload into Player objects. Pure."""
    from urllib.parse import urlparse

    players: List[Player] = []
    base_parsed = urlparse(base_url)
    base_origin = f"{base_parsed.scheme or 'https'}://{base_parsed.netloc}"

    for item in (payload.get('data', []) or []):
        try:
            player_info = item.get('player', {}) or {}
            name = player_info.get('full_name') or " ".join([
                player_info.get('first_name', ''), player_info.get('last_name', '')
            ]).strip()
            if not name:
                continue

            jersey = (player_info.get('jersey_number_label') or item.get('jersey_number_label')
                      or player_info.get('jersey_number') or item.get('jersey_number') or '')
            jersey = str(jersey) if jersey is not None else ''

            pos_obj = item.get('player_position') or {}
            pos_text = pos_obj.get('abbreviation') or pos_obj.get('name') or ''
            position = FieldExtractors.extract_position(str(pos_text)) if pos_text else ''

            feet = player_info.get('height_feet') or item.get('height_feet')
            inches = player_info.get('height_inches') or item.get('height_inches')
            if feet is not None and inches is not None:
                height = f"{feet}-{inches}"
            elif feet is not None:
                height = str(feet)
            else:
                height = ''

            class_obj = item.get('class_level') or {}
            year = FieldExtractors.normalize_academic_year(
                class_obj.get('name') or class_obj.get('abbreviation') or '')

            profile_url = ''
            slug = player_info.get('slug')
            if slug and base_parsed.netloc:
                profile_url = f"{base_origin}/sports/{roster_slug}/roster/{slug}"

            players.append(Player(
                team_id=team_id, team=team_name, season=season, division=division,
                name=name, jersey=jersey, position=position, height=height, year=year,
                major=player_info.get('major') or '',
                hometown=player_info.get('hometown') or '',
                high_school=player_info.get('high_school') or '',
                previous_school=player_info.get('previous_school') or '',
                url=profile_url,
            ))
        except Exception as e:
            logger.warning(f"Error parsing WMT OAS API player for {team_name}: {e}")
            continue

    return players


# ============================================================================
# SELF-HEALING PARSER PROBE
# ============================================================================
# Ordered most- to least-specific. Each entry: (name, gate, parser). `gate`
# is a predicate on the parsed HTML that mirrors the DOM check the original
# dispatcher used before calling the parser; a None gate is the catch-all
# fallback. best_parse tries them in order and returns the first non-empty
# roster, logging which layout matched.

def _cls(name, class_):
    """Gate: page contains a <name class=class_> element."""
    return lambda h: bool(h.find(name, class_=class_))


def _data_field_gate(h):
    t = h.find('table', attrs={'class': lambda x: x and 'table' in x})
    return bool(t and t.find('th', attrs={'data-field-label': True}))


PARSERS = [
    ('sidearm', _cls('li', 'sidearm-roster-player'), parse_sidearm_players),
    ('list_items', _cls('li', 'sidearm-roster-list-item'), parse_list_items),
    ('card_items', _cls('li', 'sidearm-list-card-item'), parse_card_items),
    ('data_field_table', _data_field_gate, parse_data_field_table),
    ('generic_roster_table', _cls('div', 'mod-roster'), parse_generic_roster_table),
    ('kentucky_table', lambda h: bool(h.find('table', id='players-table__general')), parse_kentucky_table),
    ('presto_table', lambda h: bool(h.find('td', attrs={'data-label': True})), parse_presto_table),
    ('cards', _cls('div', 's-person-card'), parse_cards),
    ('generic_cards', _cls('div', 'player-card'), parse_generic_cards),
    ('wmt', _cls('div', 'roster__item'), parse_wmt),
    ('wmt_cards', _cls('div', 'roster-card'), parse_wmt_cards),
    ('wordpress_roster', _cls('li', 'person__item'), parse_wordpress_roster),
    ('table', None, parse_table),  # catch-all fallback (s-table-body__row / table--roster)
]


def best_parse(html, team_id, team_name, season, division, base_url):
    """Probe registered parsers in priority order; return the first that
    yields players. Self-healing: if a site changes layout, the next matching
    parser still recovers the roster."""
    for name, gate, parser in PARSERS:
        try:
            if gate is not None and not gate(html):
                continue
        except Exception:
            continue
        try:
            roster = parser(html, team_id, team_name, season, division, base_url)
        except Exception as e:
            logger.debug(f"{team_name}: parser '{name}' raised {e}")
            continue
        if roster:
            logger.info(f"{team_name}: matched layout '{name}' ({len(roster)} players)")
            return roster
    return []

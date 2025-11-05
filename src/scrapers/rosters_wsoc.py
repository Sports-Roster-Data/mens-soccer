import requests
import tldextract
from bs4 import BeautifulSoup
import json
import csv
import argparse

def scrape_roster(team_name, season, base_url, team_id):
    """
    Scrapes the women's soccer team roster from the given URL and returns a JSON array with additional team and season info.
    Tries multiple URL patterns to find the roster page.

    Arguments:
    team_name -- The name of the team (string)
    season -- The season year (string or integer)
    base_url -- The base URL of the team's site (string)
    team_id -- The NCAA team ID (string)

    Returns:
    A list of dictionaries representing the roster data in JSON format, including the team, season, and team_id attributes.
    """
    try:
        # Headers to mimic a request from Firefox browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }

        # Try multiple URL patterns
        url_patterns = [
            f"{base_url}/roster",  # Most common pattern
            f"{base_url}/roster/{season}",
            f"{base_url}/{season}-{int(season)+1}/roster",  # e.g., /2024-25/roster
        ]

        response = None
        roster_url = None

        for url_pattern in url_patterns:
            try:
                response = requests.get(url_pattern, headers=headers, timeout=10)
                if response.status_code == 200:
                    roster_url = url_pattern
                    break
            except:
                continue

        if not response or response.status_code != 200:
            print(f"Failed to retrieve roster for {team_name} (status: {response.status_code if response else 'no response'})")
            return []

        er = tldextract.extract(roster_url)

        # Check if the request was successful
        if response.status_code == 200:
            # Parse the HTML content using BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')

            # List to store player information
            player_data = []

            # Find all <li> tags that contain player information
            roster_list_items = soup.find_all('li', class_='sidearm-roster-player')

            if roster_list_items:
                # Iterate over each <li> tag
                for player in roster_list_items:
                    # Extract the necessary information
                    jersey_element = player.find('span', class_='sidearm-roster-player-jersey-number')
                    jersey = jersey_element.text.strip() if jersey_element else None

                    # Extract the player name from the <h3> tag that contains an <a> tag
                    name_column = player.find('h3').find('a', href=True)
                    name = name_column.text.strip() if name_column else None
                    profile_url = f"https://www.{er.domain}.{er.suffix}{name_column['href']}" if name_column else None

                    position_element = player.find('span', class_='sidearm-roster-player-position-long-short')
                    position = position_element.text.strip() if position_element else None

                    height_element = player.find('span', class_='sidearm-roster-player-height')
                    height = height_element.text.strip() if height_element else None

                    class_year_element = player.find('span', class_='sidearm-roster-player-academic-year')
                    player_class = class_year_element.text.strip() if class_year_element else None

                    major_element = player.find('span', class_='sidearm-roster-player-major')
                    major = major_element.text.strip() if major_element else None

                    hometown_element = player.find('span', class_='sidearm-roster-player-hometown')
                    hometown = hometown_element.text.strip() if hometown_element else None

                    high_school_element = player.find('span', class_='sidearm-roster-player-highschool')
                    high_school = high_school_element.text.strip() if high_school_element else None

                    previous_school_element = player.find('span', class_='sidearm-roster-player-previous-school')
                    previous_school = previous_school_element.text.strip() if previous_school_element else None

                    # Append the player's data to the list
                    player_data.append({
                        'team_id': team_id,
                        'team': team_name,
                        'season': season,
                        'jersey': jersey,
                        'name': name,
                        'position': position,
                        'height': height,
                        'class': player_class,
                        'major': major,
                        'hometown': hometown,
                        'high_school': high_school,
                        'previous_school': previous_school,
                        'url': profile_url
                    })

                return player_data
            else:
                print(f"No player data found for {team_name}.")
                return []
        else:
            print(f"Failed to retrieve the page for {team_name}. Status code: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error scraping {team_name}: {e}")
        return []

def scrape_all_teams(season):
    """
    Loads the teams from teams_wsoc.csv, scrapes the roster for teams with '/womens-soccer' in the URL,
    and writes the data to a JSON file.

    Arguments:
    season -- The season year (string or integer).
    """
    rosters = []

    # Load teams_wsoc.csv using the csv module
    file_path = '../../data/input/teams_wsoc.csv'

    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)

        # Iterate over all teams in the CSV
        for row in reader:
            team_name = row['team']
            base_url = row['url']
            team_id = row.get('team_id')

            # Only scrape teams with '/womens-soccer' or similar in the original URL
            if '/womens-soccer' in row.get('url', '') or '/w-soccer' in row.get('url', '') or '/wsoc' in row.get('url', '') or '/soccer' in row.get('url', ''):
                print(f"Scraping {team_name}...")
                team_roster = scrape_roster(team_name, season, base_url, team_id)
                # scrape_roster returns a list; extend safely
                if team_roster:
                    rosters.extend(team_roster)

    # Write the collected rosters to a JSON file
    output_file = f'../../data/raw/json/rosters_wsoc_{season}.json'
    with open(output_file, 'w') as f:
        json.dump(rosters, f, indent=4)

    print(f"All rosters saved to {output_file}")

# Example usage
season = 2025
scrape_all_teams(season)

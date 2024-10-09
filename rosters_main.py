import requests
import tldextract
from bs4 import BeautifulSoup
import json
import csv

def scrape_roster(team_name, season, roster_url, division, ncaa_id):
    """
    Scrapes the soccer team roster from the given URL and returns a JSON array with additional team and season info.
    
    Arguments:
    team_name -- The name of the team (string)
    season -- The season year (string or integer)
    roster_url -- The URL of the team's roster page (string)
    division -- The division of the team (string)
    
    Returns:
    A list of dictionaries representing the roster data in JSON format, including the team, season, and division attributes.
    """
    try:
        # Headers to mimic a request from Firefox browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
        }

        # Send a GET request to the URL with headers
        response = requests.get(roster_url, headers=headers)
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
                        'ncaa_id': ncaa_id,
                        'team': team_name,
                        'season': season,
                        'division': division,
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
    Loads the teams from teams.csv, scrapes the roster for teams with '/mens-soccer' in the URL,
    and writes the data to a JSON file.
    
    Arguments:
    season -- The season year (string or integer).
    """
    rosters = []

    # Load teams.csv using the csv module
    file_path = 'teams.csv'
    
    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        
        # Iterate over all teams in the CSV
        for row in reader:
            team_name = row['team']
            roster_url = row['url'] + f'/roster/{season}'
            division = row['division']
            ncaa_id = row['ncaa_id']

            # Only scrape teams with '/mens-soccer' in the URL
            if '/mens-soccer' in roster_url:
                print(f"Scraping {team_name}...")
                team_roster = scrape_roster(team_name, season, roster_url, division, ncaa_id)
                rosters.extend(team_roster)
    
    # Write the collected rosters to a JSON file
    output_file = f'rosters_{season}.json'
    with open(output_file, 'w') as f:
        json.dump(rosters, f, indent=4)

    print(f"All rosters saved to {output_file}")

# Example usage
#season = 2024
#scrape_all_teams(season)

import csv
import json
import requests
import tldextract
from bs4 import BeautifulSoup

# Set the Firefox user-agent in the headers
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
}

# Function to clean up and split the Hometown/High School field
def clean_hometown_high_school(text):
    cleaned_text = ' '.join(text.split()).replace('Hometown/High School:', '').strip()
    if '/' in cleaned_text:
        parts = [part.strip() for part in cleaned_text.split('/', 1)]
        return parts[0], parts[1] if len(parts) > 1 else None
    return cleaned_text, None

# Function to clean text, removing excessive newlines and tabs
def clean_text(text):
    return ' '.join(text.split())

# Function to find a <td> by the label within a player row and extract the text that follows
def extract_value_by_label(row, label):
    # Find the <span> with the given label within the specific row
    label_span = row.find('span', string=lambda text: text and label in text)
    if label_span:
        # The actual value follows the <span> label inside the <td>
        td_element = label_span.find_parent('td')
        if td_element:
            # Extract all the contents of the <td> after the label
            contents = td_element.get_text(separator=" ", strip=True).replace(f'{label}:', '').strip()
            return contents
    return None

# Function to extract roster information from a specific row
def extract_roster(soup, team_name, division, season, er):
    roster = []

    # Locate the table containing the roster
    table = soup.find('table')

    # Extract the player rows
    rows = table.find_all('tr')[1:]  # Skipping the header row

    for row in rows:
        player = {}

        # Extract the jersey number from the class 'number'
        number_cell = row.find('td', class_='number')
        player['jersey'] = number_cell.get_text(strip=True).replace("No.:", "") if number_cell else None

        # Extract the full player name and URL from the 'name' <th> element
        name_cell = row.find('th', class_='name')
        if name_cell:
            name_link = name_cell.find('a')
            full_name = name_link.get_text() if name_link else None
            player['name'] = clean_text(full_name) if full_name else None
            player['url'] = f"https://www.{er.domain}.{er.suffix}{name_link['href']}" if name_link else None
#            player['url'] = name_link['href'] if name_link else None
        else:
            player['name'] = None
            player['url'] = None

        # Extract the position from the player's row
        player['position'] = extract_value_by_label(row, 'Pos.')

        # Extract the class (year) from the player's row
        player['class'] = extract_value_by_label(row, 'Cl.')

        # Extract hometown and high school from the player's row
        hometown_highschool = extract_value_by_label(row, 'Hometown/High School')
        if hometown_highschool:
            hometown, high_school = clean_hometown_high_school(hometown_highschool)
            player['hometown'] = hometown
            player['high_school'] = high_school
        else:
            player['hometown'] = None
            player['high_school'] = None

        # Add team name, division, and season to the player data
        player['team'] = team_name
        player['division'] = division
        player['season'] = season

        roster.append(player)

    return roster

# Main function to iterate through CSV and extract rosters
def process_teams_csv(csv_file_path, season=2024):
    rosters = []

    # Open and read the CSV file
    with open(csv_file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        
        # Iterate through each row in the CSV file
        for row in reader:
            team_name = row['team']
            team_url = row['url']
            division = row['division']

            # Only process rows with URLs that contain '/msoc/index'
            if '/msoc/index' in team_url:
                # Replace "/index" with "/2024-25/roster"
                roster_url = team_url.replace('/index', '/2024-25/roster')
                er = tldextract.extract(roster_url)
                print(f"Processing roster for {team_name} from {roster_url}...")
                
                try:
                    response = requests.get(roster_url, headers=headers)  # Include the headers with user-agent
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'html.parser')
                        roster = extract_roster(soup, team_name, division, season, er)
                        rosters.extend(roster)
                    else:
                        print(f"Failed to retrieve the page for {team_name}. Status code: {response.status_code}")
                except Exception as e:
                    print(f"Error processing {team_name}: {e}")

    # Save the rosters to a JSON file
    with open('rosters_msoc.json', 'w') as outfile:
        json.dump(rosters, outfile, indent=4)

    print("Roster extraction complete.")

# Example usage
process_teams_csv('teams.csv')

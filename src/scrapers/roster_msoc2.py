import requests
from bs4 import BeautifulSoup
import csv

# Load team data from need_rosters.csv
input_file = '../../data/input/d3teams.csv'
output_file = '../../data/additions/d3adds.csv'
season = 2024  # Set the season

# Custom headers with a Firefox User-Agent
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:93.0) Gecko/20100101 Firefox/93.0'
}

# Function to clean and normalize the text data
def clean_text(text):
    unwanted_labels = ['Pos.:', 'Ht.:', 'Cl.:', 'Hometown:', 'High School:', 'Hometown/']
    for label in unwanted_labels:
        text = text.replace(label, '').strip()
    return ' '.join(text.split())

# Function to scrape roster for a given team
def scrape_roster(ncaa_id, team, base_url, url, division, season, writer):
    # Modify the URL to point to the roster page
    roster_url = url.replace('/index', '/2024-25/roster')
    
    # Send a request with the custom User-Agent header
    response = requests.get(roster_url, headers=headers)
    
    # Check if the response is successful
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all player rows
        rows = soup.find_all('tr')

        for row in rows[1:]:  # Skip header row
            data = {}

            # Get all 'td' tags with data-labels
            for col in row.find_all('td'):
                label = col.get('data-label')
                value = clean_text(col.text)
                data[label] = value

            # Get player name and URL
            name_tag = row.find('a')
            if name_tag:
                player_name = clean_text(name_tag.text)
                player_url = base_url + name_tag['href']  # Use the school's base URL for player profile links
            else:
                player_name = clean_text(data.get('Name', ''))
                player_url = ''

            # Always split hometown and high school
            hometown_highschool = clean_text(data.get('Hometown/High School', '')).split('/', 1)
            hometown = hometown_highschool[0].strip() if len(hometown_highschool) > 0 else ''
            highschool = hometown_highschool[1].strip() if len(hometown_highschool) > 1 else ''

            # Write row data to the CSV
            writer.writerow([
                ncaa_id,
                team,
                season,
                division,
                data.get('No.', ''),
                player_name,
                data.get('Pos.', ''),
                data.get('Ht.', ''),
                data.get('Cl.', ''),
                '',  # Major (not available on the page)
                hometown,  # Hometown only
                highschool,  # High school only
                '',  # Previous School (if any)
                player_url
            ])
    else:
        print(f"Failed to scrape {roster_url}. Status code: {response.status_code}")

# Open the output CSV file
with open(output_file, mode='w', newline='', encoding='utf-8') as output_csv:
    writer = csv.writer(output_csv)

    # Write the headers to the output CSV
    writer.writerow([
        'ncaa_id', 'team', 'season', 'division', 'jersey', 'name', 'position', 
        'height', 'class', 'major', 'hometown', 'high_school', 'previous_school', 'url'
    ])

    # Read the input CSV file and scrape each team's roster
    with open(input_file, mode='r', newline='', encoding='utf-8') as input_csv:
        reader = csv.DictReader(input_csv)

        for row in reader:
            ncaa_id = row['ncaa_id']
            team = row['team']
            url = row['url']
            base_url = url.rsplit('/sports', 1)[0]  # Get base URL by removing everything after '/sports'
            division = row['division']
            print(team)

            # Scrape the roster for the current team
            scrape_roster(ncaa_id, team, base_url, url, division, season, writer)

print("All rosters have been successfully scraped and saved to adds.csv.")

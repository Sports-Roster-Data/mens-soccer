import csv
import requests

def check_wsoc_urls(csv_file):
    """
    Check URLs in teams_wsoc.csv for 404 errors and other issues.
    """
    # Headers to mimic a request from Firefox browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
    }

    # Lists to store results
    valid_urls = []
    invalid_urls = []
    error_urls = []

    # Read the CSV file
    with open(csv_file, newline='') as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            team_name = row['team']
            url = row['url']
            team_id = row['team_id']

            print(f"Checking {team_name}... ", end='')

            try:
                # Send a HEAD request to check the status code
                response = requests.head(url, headers=headers, allow_redirects=True, timeout=10)

                if response.status_code == 200:
                    print(f"✓ OK ({response.status_code})")
                    valid_urls.append({'team': team_name, 'team_id': team_id, 'url': url, 'status': response.status_code})
                elif response.status_code == 404:
                    print(f"✗ 404 NOT FOUND")
                    invalid_urls.append({'team': team_name, 'team_id': team_id, 'url': url, 'status': response.status_code})
                else:
                    print(f"⚠ Warning ({response.status_code})")
                    valid_urls.append({'team': team_name, 'team_id': team_id, 'url': url, 'status': response.status_code})

            except requests.RequestException as e:
                print(f"✗ ERROR: {e}")
                error_urls.append({'team': team_name, 'team_id': team_id, 'url': url, 'error': str(e)})

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total teams: {len(valid_urls) + len(invalid_urls) + len(error_urls)}")
    print(f"Valid URLs: {len(valid_urls)}")
    print(f"404 errors: {len(invalid_urls)}")
    print(f"Other errors: {len(error_urls)}")

    if invalid_urls:
        print("\n" + "="*60)
        print("TEAMS WITH 404 ERRORS")
        print("="*60)
        for item in invalid_urls:
            print(f"{item['team']} (ID: {item['team_id']})")
            print(f"  URL: {item['url']}")

    if error_urls:
        print("\n" + "="*60)
        print("TEAMS WITH OTHER ERRORS")
        print("="*60)
        for item in error_urls:
            print(f"{item['team']} (ID: {item['team_id']})")
            print(f"  URL: {item['url']}")
            print(f"  Error: {item['error']}")

    return valid_urls, invalid_urls, error_urls

# Run the check
csv_file = '../../data/input/teams_wsoc.csv'
valid_urls, invalid_urls, error_urls = check_wsoc_urls(csv_file)

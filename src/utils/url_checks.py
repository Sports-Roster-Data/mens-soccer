import json
import requests

def filter_valid_urls(json_file):
    # Load JSON data from the file
    with open(json_file, 'r') as file:
        data = json.load(file)

    # List to store valid items
    valid_items = []

    # Iterate over each item and check the URL
    for item in data:
        print(item['team'])
        if 'url' in item:
            try:
                # Send a HEAD request to check the status code without downloading the entire page
                response = requests.head(item['url'], allow_redirects=True)

                # If status code is 200 or 302, append the item to valid_items
                if response.status_code in [200, 302]:
                    valid_items.append(item)
            except requests.RequestException as e:
                print(f"Error checking {item['url']}: {e}")
                continue

    return valid_items

# Example usage
json_file = '../../data/input/teams.json'  # Replace with the path to your JSON file
valid_items = filter_valid_urls(json_file)

# Print the valid items
for item in valid_items:
    print(item)

# Optionally, you can save the valid items to a new JSON file
with open('../../data/input/valid_items.json', 'w') as outfile:
    json.dump(valid_items, outfile, indent=4)

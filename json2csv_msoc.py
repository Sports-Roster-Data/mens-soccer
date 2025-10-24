import json
import csv

def json_to_csv(json_file, csv_file):
    """
    Converts a JSON file into a CSV file.

    Arguments:
    json_file -- The path to the input JSON file.
    csv_file -- The path to the output CSV file.
    """
    try:
        # Load the JSON data from the file
        with open(json_file, 'r') as f:
            data = json.load(f)

        # Check if data is a list (JSON array)
        if isinstance(data, list) and len(data) > 0:
            # Extract the keys from the first dictionary as headers
            headers = data[0].keys()

            # Write the data to a CSV file
            with open(csv_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data)

            print(f"Successfully converted {json_file} to {csv_file}")
        else:
            print(f"No valid data found in {json_file}")

    except Exception as e:
        print(f"Error: {e}")

# Example usage
season = 2025
json_file = f'rosters_msoc.json'
csv_file = f'rosters_msoc_{season}.csv'
json_to_csv(json_file, csv_file)

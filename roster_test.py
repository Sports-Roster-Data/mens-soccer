from bs4 import BeautifulSoup

# Example HTML structure
html = '''
<td >
    <span class="label">Pos.:</span>
    M
</td>
<td >
    <span class="label">Cl.:</span>
    Sr
</td>
<td >
    <span class="label">Hometown/High School:</span>
    North Richland Hills, Texas
    /
    Birdville
</td>
'''

# Parse the HTML using BeautifulSoup
soup = BeautifulSoup(html, 'html.parser')

# Function to find a <td> by the label and extract the text that follows
def extract_value_by_label(soup, label):
    # Find the <span> with the given label
    label_span = soup.find('span', string=lambda text: text and label in text)
    if label_span:
        # The actual value follows the <span> label inside the <td>
        td_element = label_span.find_parent('td')
        if td_element:
            # Extract all the contents of the <td> after the label
            contents = td_element.get_text(separator=" ", strip=True).replace(f'{label}:', '').strip()
            return contents
    return None

# Extract position
position = extract_value_by_label(soup, 'Pos.')
print(f"Position: {position}")

# Extract year (class)
year = extract_value_by_label(soup, 'Cl.')
print(f"Year: {year}")

# Extract hometown and high school (split by '/')
hometown_highschool = extract_value_by_label(soup, 'Hometown/High School')
if hometown_highschool:
    hometown, high_school = [part.strip() for part in hometown_highschool.split('/')]
    print(f"Hometown: {hometown}")
    print(f"High School: {high_school}")

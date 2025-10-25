# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a web scraping and data processing project for NCAA men's soccer team rosters. The project scrapes roster data from college athletic websites and consolidates them into a unified dataset for the 2024 season.

## Data Architecture

### Source Data
- `teams.csv` - Master list of NCAA teams with columns: `team`, `url`, `ncaa_id`, `division`
- Teams are organized by NCAA division (I, II, III)

### Output Data Flow
1. Python scrapers generate JSON files (e.g., `rosters_2024.json`, `rosters_msoc.json`)
2. JSON files are converted to CSV via `json2csv.py` or `json2csv_msoc.py`
3. R (Quarto) script `cleaning.qmd` merges and reconciles roster data
4. Final output: `combined_rosters_2024.csv` with standardized roster fields

### Roster Data Schema
All roster CSVs follow this schema:
- `ncaa_id`, `team`, `season`, `division`, `jersey`, `name`, `position`, `height`, `class`, `major`, `hometown`, `high_school`, `previous_school`, `url`

## Web Scraping Architecture

The project uses **multiple scraping strategies** because NCAA teams use different website platforms with different HTML structures:

### Strategy 1: Sidearm Sports Platform (`rosters_main.py`)
- Targets URLs containing `/mens-soccer`
- Uses HTML classes like `sidearm-roster-player`, `sidearm-roster-player-jersey-number`
- Extracts comprehensive data including major and previous_school
- URL pattern: `{base_url}/roster/{season}`

### Strategy 2: Table-Based Platform (`roster_msoc.py`)
- Targets URLs containing `/msoc/index`
- Scrapes HTML tables with `<th class='name'>` and labeled `<td>` elements
- URL patterns: tries `/2024-25/roster` first, falls back to `/roster/2024`
- Does not capture major or height fields
- Splits "Hometown/High School" into separate fields

### Strategy 3: Data-Label Platform (`roster_msoc2.py`)
- Used for remaining teams (often D-III schools)
- Reads from specialized input CSVs (e.g., `d3teams.csv`)
- Scrapes tables with `data-label` attributes on `<td>` elements
- Outputs to specialized CSVs (e.g., `d3adds.csv`)
- Constructs player URLs by combining school base URL with relative paths

## Common Development Commands

### Running Scrapers
```bash
# Scrape Sidearm Sports platform teams (all divisions)
python rosters_main.py

# Scrape msoc/index platform teams
python roster_msoc.py

# Scrape D-III or specialized teams
python roster_msoc2.py
```

**Note:** To filter by division, edit the script's final lines to specify division:
- `scrape_all_teams(2025, "I")` - Division I only
- `scrape_all_teams(2025, "II")` - Division II only
- `scrape_all_teams(2025, "III")` - Division III only
- `scrape_all_teams(2025)` - All divisions

### JSON to CSV Conversion
```bash
# Convert standard rosters
python json2csv.py

# Convert msoc-specific rosters
python json2csv_msoc.py
```

### Data Cleaning and Merging
```bash
# Use Quarto to render the cleaning notebook
quarto render cleaning.qmd
```

### URL Validation
```bash
# Check team URLs for validity
python url_checks.py
```

## Key Implementation Details

### User-Agent Headers
All scrapers must use Firefox user-agent headers to avoid blocking:
```python
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
}
```

### URL Construction
- **Sidearm**: `{base_url}/roster/{season}`
- **msoc**: Try `{base_url}/2024-25/roster`, fallback to `{base_url}/roster/2024`
- **Data-label**: Base URL is extracted by splitting on `/sports`, then relative paths are appended

### Text Cleaning
All scrapers implement text normalization:
- Strip excess whitespace, newlines, tabs
- Remove label prefixes (e.g., "No.:", "Pos.:", "Cl.:")
- Split combined fields like "Hometown/High School"

### Error Handling
- Scrapers print team names during processing for progress tracking
- Failed requests print status codes
- Missing elements return `None` or empty string rather than raising exceptions

## Iterative Scraping Workflow

The scraping process is iterative because not all teams can be scraped at once:

1. Run scrapers to collect roster data into JSON files
2. Convert JSON to CSV
3. Run `cleaning.qmd` to merge data and generate `need_rosters.csv`
4. `need_rosters.csv` identifies teams that still need roster data
5. Create specialized input CSVs (e.g., `d3teams.csv`) for remaining teams
6. Run appropriate scraper for those teams
7. Merge results back into `combined_rosters_2024.csv`

This workflow repeats until all teams have roster data.

## Season Management

The project tracks multiple seasons:
- JSON/CSV files are named with season years (e.g., `rosters_2024.json`, `rosters_2025_I.json`)
- Division-specific runs append division to filename (e.g., `rosters_2025_I.json` for Division I only)
- Scrapers can be filtered by division using the division parameter in `scrape_all_teams(season, division)`

## Dependencies

Python packages (via `pyproject.toml`, managed with `uv`):
- `requests>=2.32.5` - HTTP requests
- `bs4>=0.0.2` - BeautifulSoup for HTML parsing
- `tldextract>=5.3.0` - URL parsing for domain extraction

Install dependencies:
```bash
uv sync
```

R packages (used in cleaning.qmd):
- `tidyverse` - Data manipulation and CSV I/O

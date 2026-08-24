# College Soccer Rosters

Scripts and data for collecting, cleaning, and analyzing NCAA **men's and
women's** college soccer rosters (Divisions I, II, and III). One unified Python
scraper pulls roster data from official team websites; an R/Quarto notebook
merges and standardizes it for analysis.

## Quick start

```bash
uv sync
uv run shot-scraper install          # one-time: Chromium for JavaScript-rendered sites

# Scrape a season (women's shown; use --sport men and add --division I/II/III for men's)
uv run python -m rosters --sport women --season 2026

# Re-scrape only certain teams (merges into the existing season file)
uv run python -m rosters --sport women --season 2026 --team 746 110

# Run the test suite (offline)
uv run pytest
```

Output lands in `data/raw/csv/` and `data/raw/json/` as
`rosters_<season>[_<division>].csv` (men's) or `rosters_wsoc_<season>...`
(women's), plus `_zero_players` / `_failed` diagnostic reports.

## How it works

- Team lists live in `data/input/teams.csv` (men's) and
  `data/input/teams_wsoc.csv` (women's). Per-team quirks — URL format, whether
  the site needs a JavaScript render — are columns in those files, not code.
- The scraper fetches each roster page, escalating from a plain request to a
  curl fallback (for bot-protected sites) to a headless-browser render when
  needed, then probes a list of layout parsers and keeps the first that
  produces a roster.
- See `CLAUDE.md` for the package layout and internals.

## Output data dictionary

| column | description |
|---|---|
| `ncaa_id` | NCAA team id |
| `team` | team name |
| `season` | season year (e.g. `2026`) |
| `division` | `I`, `II`, or `III` (men's; blank for women's until backfilled) |
| `jersey` | jersey number |
| `name` | player name |
| `position` | normalized to `GK` / `D` / `M` / `F` where possible |
| `height` | as published (imperial or metric) |
| `class` | academic year (Freshman … Graduate) |
| `major` | major, when listed |
| `hometown` | hometown as published |
| `high_school` | high school, when separable |
| `previous_school` | previous college, when listed |
| `url` | player profile URL |

## Cleaning and analysis

`analysis/cleaning.qmd` (R/Quarto) merges the scraped CSVs, standardizes
positions/classes/heights, parses hometown/state, and identifies international
players. Render with `quarto render analysis/cleaning.qmd`.

## License

Intended for educational and research purposes.

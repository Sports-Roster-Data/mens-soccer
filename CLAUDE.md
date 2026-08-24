# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## Tone of responses

Avoid exclamatory statements such as "You're absolutely right!" and "I see the issue!"; instead use even language. Consider the possibility that I might actually not be absolutely right. Your goal is not to please me but to help me write simple, effective code that works.

## Project overview

Scrapes NCAA **men's and women's** soccer team rosters from college athletic
websites and consolidates them into per-sport CSV/JSON datasets. One unified
Python package handles both sports; an R/Quarto notebook does downstream
cleaning.

## Layout

```
src/rosters/            # the scraper package (run as `python -m rosters`)
  __main__.py           # CLI (argparse): --sport, --season, --division, --team, ...
  config.py             # SPORTS dict + load_teams(); per-team overrides come from the CSV
  models.py             # Player dataclass + CSV_FIELDS (canonical output column order)
  extractors.py         # FieldExtractors (jersey/height/position/year/hometown) + SeasonVerifier
  urls.py               # URLBuilder.build_roster_url — all platform URL formats
  fetch.py              # shared retrying Session, curl-on-403 fallback, shot-scraper JS render, Nuxt sniff
  parsers.py            # pure layout parsers + PARSERS probe list + best_parse(); OAS helpers
  scraper.py            # per-team orchestration: fetch -> escalate -> best_parse -> enhance
  run.py                # batch loop + atomic/merge JSON+CSV writes + error reports
data/input/             # teams.csv (men), teams_wsoc.csv (women), fifa_teams.csv  (version controlled)
data/raw/{json,csv}/    # scraper output  (gitignored)
data/output/            # merged/cleaned outputs  (gitignored)
analysis/cleaning.qmd   # R/Quarto merge + normalization
tests/                  # offline pytest suite + HTML fixtures + capture_fixture.py
```

## Commands

```bash
uv sync
uv run shot-scraper install          # one-time: downloads Chromium for JS-rendered sites

# Scrape (writes data/raw/{json,csv}/rosters_2025[_DIV].csv, or rosters_wsoc_ for women)
uv run python -m rosters --sport men --season 2025 --division I
uv run python -m rosters --sport women --season 2025

# Re-scrape specific teams; merges into the season file (does not clobber other teams)
uv run python -m rosters --sport men --season 2025 --team 746 334

uv run pytest                        # fully offline

# Capture a new HTML fixture through the scraper's own fetch path
uv run python tests/capture_fixture.py <layout> <label> <roster_url> [--js]
```

Downstream cleaning: `cd analysis && quarto render cleaning.qmd`.

## How it works

- **Sport parameterization** lives entirely in `config.SPORTS` (teams file,
  output filename stem, URL slugs, roster-profile slug). Nothing else in the
  code knows the sport.
- **Team overrides are data, not code.** Each teams CSV has
  `team,url,ncaa_id,division,url_format,requires_js,notes`. An empty
  `url_format` means "auto-detect from the URL"; `requires_js=true` forces
  JavaScript rendering. Add or fix a team by editing its CSV row.
- **Self-healing parsing.** `parsers.best_parse` probes the ordered `PARSERS`
  list (most- to least-specific), each entry a `(name, gate, parser)`; it
  returns the first parser that yields players and logs which layout matched.
  When a site changes layout, the next matching parser recovers it.
- **Fetch escalation ladder** (`fetch.py` + `scraper.py`): plain GET on a
  retrying session → curl fallback on HTTP 403 → shot-scraper JS render when
  the team is flagged `requires_js` or the page is a Nuxt skeleton
  (`__NUXT_DATA__`). WMT/Nuxt sites that expose an OAS JSON API are read
  directly from that API.
- **Writes are atomic and mergeable.** `run.py` writes to a `.tmp` then
  `os.replace`; a targeted `--team` run merges those teams' rows into the
  existing season file instead of overwriting it.

## Roster schema (output CSV)

`ncaa_id, team, season, division, jersey, name, position, height, class,
major, hometown, high_school, previous_school, url` — defined once in
`models.CSV_FIELDS`.

## Conventions

- Never hardcode an `ncaa_id` inside a parser. Team-specific behavior belongs
  in the teams CSV (a config column) or in a self-gating helper (e.g. the
  Kentucky bio enhancement keys off the `ukathletics.com` URL, not an id).
- A new site layout = a new pure `parse_<layout>` function + an entry in
  `PARSERS` + an HTML fixture + a test. Parsers must be pure (no network) so
  tests stay offline; network I/O lives in `scraper.py`/`fetch.py`.
- `analysis/cleaning.qmd` depends on `data/input/teams.csv` columns 1–4 and on
  the `models.CSV_FIELDS` order. Appending CSV columns is safe; do not reorder
  or rename the first four teams columns or the roster output columns.

## Dependencies

Python via `uv` (`pyproject.toml`): `requests`, `bs4`, `tldextract`,
`playwright`, `shot-scraper`; dev group adds `pytest`. R (cleaning.qmd):
`tidyverse`, `janitor`, `postmastr`, `usdata`, `rvest`.

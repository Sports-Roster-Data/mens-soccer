# Repository Reorganization Plan

**Last Updated:** 2025-10-24
**Related Document:** See `WBB_SCRAPER_ADAPTATION_PLAN.md` for unified scraper architecture proposal

## Executive Summary

This document outlines a two-track approach for improving the repository:

**Track 1: Immediate Reorganization** (4-6 hours)
- Clean up file structure
- Separate code from data
- Improve git hygiene
- Can be done independently

**Track 2: Unified Scraper Architecture** (24-32 hours, see WBB_SCRAPER_ADAPTATION_PLAN.md)
- Adapt WBB scraper architecture
- Replace 3 separate scrapers with 1 unified tool
- Configuration-driven approach
- Can be done after or concurrent with Track 1

**Recommendation:** Do Track 1 first (immediate wins), then evaluate Track 2 based on needs.

---

## Current State Analysis

The repository currently has **31 files** in the root directory with no organizational structure. This makes it difficult to:
- Distinguish between source code, input data, intermediate data, and final outputs
- Identify which files are version-controlled vs. generated artifacts
- Understand the data pipeline flow
- Clean up old or obsolete files
- Scale to new scraping patterns or sports

### Current File Inventory

**Python Scripts (8 files):**
- `rosters_main.py` - Sidearm Sports platform scraper
- `roster_msoc.py` - msoc/index platform scraper
- `roster_msoc2.py` - data-label platform scraper
- `rosters.py` - Legacy Selenium-based scraper (uses Firefox driver)
- `json2csv.py` - Standard JSON to CSV converter
- `json2csv_msoc.py` - msoc JSON to CSV converter
- `url_checks.py` - URL validation utility
- `test.py` - Empty test file

**Source/Configuration Data (5 files):**
- `teams.csv` (52K) - Master team list
- `teams_msoc.csv` (225B) - msoc teams subset
- `d3teams.csv` (3.2K) - Division III teams
- `teams.json` (150K) - JSON version of teams
- `valid_items.json` (151K) - Validation data

**Large Intermediate JSON Files (5 files, ~23MB total):**
- `rosters_2024.json` (10M)
- `rosters_2025.json` (9.8M)
- `rosters_2025_I.json` (1.9M)
- `rosters_msoc.json` (1.0M)
- `rosters.json` (15K)

**Intermediate CSV Files (5 files, ~5MB total):**
- `rosters_2024.csv` (3.7M)
- `rosters_2025_I.csv` (686K)
- `rosters_msoc_2024.csv` (270K)
- `rosters_msoc_2025.csv` (270K)
- `rosters_msoc.csv` (255K)

**Incremental/Manual Additions (2 files):**
- `adds.csv` (9.1K) - Manual roster additions
- `d3adds.csv` (10K) - Division III additions

**Final Outputs (2 files):**
- `combined_rosters_2024.csv` (4.4M) - Final merged dataset
- `need_rosters.csv` (2.1K) - Teams still needing scraping

**Analysis Scripts (1 file):**
- `cleaning.qmd` - R/Quarto data merging and cleaning

**Documentation (2 files):**
- `README.md`
- `CLAUDE.md`

**Configuration (3 files):**
- `pyproject.toml`
- `uv.lock`
- `Pipfile.lock`

---

## Proposed Directory Structure

### Option A: Current Scrapers (Track 1 Only)

This structure works with existing 3 separate scrapers:

```
mens-soccer/
├── README.md
├── CLAUDE.md
├── WBB_SCRAPER_ADAPTATION_PLAN.md
├── REORGANIZATION_PLAN.md (this file)
├── pyproject.toml
├── uv.lock
├── .gitignore                    # Update with new structure
│
├── src/                          # Source code
│   ├── scrapers/
│   │   ├── rosters_main.py       # Sidearm platform
│   │   ├── roster_msoc.py        # msoc/index platform
│   │   ├── roster_msoc2.py       # data-label platform
│   │   └── rosters.py            # Legacy Selenium scraper (archive?)
│   ├── converters/
│   │   ├── json2csv.py
│   │   └── json2csv_msoc.py
│   └── utils/
│       └── url_checks.py
│
├── data/                         # Data directory (add to .gitignore)
│   ├── input/                    # Source data (version controlled)
│   │   ├── teams.csv             # Master team list
│   │   ├── teams.json            # JSON version for unified scraper
│   │   ├── teams_msoc.csv
│   │   ├── d3teams.csv
│   │   └── valid_items.json
│   ├── raw/                      # Raw scraper output (gitignored)
│   │   ├── json/
│   │   │   ├── rosters_2024.json
│   │   │   ├── rosters_2025.json
│   │   │   ├── rosters_2025_I.json
│   │   │   ├── rosters_msoc.json
│   │   │   └── rosters.json
│   │   └── csv/
│   │       ├── rosters_2024.csv
│   │       ├── rosters_2025_I.csv
│   │       ├── rosters_msoc_2024.csv
│   │       ├── rosters_msoc_2025.csv
│   │       └── rosters_msoc.csv
│   ├── additions/                # Manual additions (version controlled)
│   │   ├── adds.csv
│   │   └── d3adds.csv
│   ├── interim/                  # Intermediate processing (gitignored)
│   │   └── need_rosters.csv
│   └── output/                   # Final outputs (gitignored)
│       └── combined_rosters_2024.csv
│
├── analysis/                     # Analysis scripts
│   └── cleaning.qmd
│
├── tests/                        # Test files
│   └── test_field_extractors.py # Unit tests (to be created)
│
└── archive/                      # Deprecated/old code
    └── (old scrapers moved here after unification)
```

### Option B: Unified Scraper (Track 1 + Track 2)

This structure accommodates the unified WBB-style scraper:

```
mens-soccer/
├── README.md
├── CLAUDE.md
├── WBB_SCRAPER_ADAPTATION_PLAN.md
├── REORGANIZATION_PLAN.md (this file)
├── pyproject.toml
├── uv.lock
├── .gitignore
│
├── src/
│   ├── soccer_roster_scraper.py  # UNIFIED scraper (main entry point)
│   ├── soccer_config.py           # TeamConfig (200+ team configurations)
│   │
│   ├── core/                      # Core scraper components
│   │   ├── __init__.py
│   │   ├── models.py              # Player dataclass
│   │   ├── field_extractors.py   # Parsing utilities
│   │   ├── season_verifier.py    # Season validation
│   │   ├── url_builder.py        # URL construction
│   │   └── header_mapper.py      # Column name normalization
│   │
│   ├── scrapers/                  # Specialized scraper classes
│   │   ├── __init__.py
│   │   ├── base_scraper.py       # BaseScraper abstract class
│   │   ├── standard_scraper.py   # Sidearm Sports (StandardScraper)
│   │   ├── table_scraper.py      # Table-based sites (TableScraper)
│   │   └── javascript_scraper.py # JS-heavy sites (if needed)
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   └── url_checks.py         # URL validation utility
│   │
│   └── legacy/                    # Old scrapers (deprecated)
│       ├── rosters_main.py       # Keep for reference/validation
│       ├── roster_msoc.py
│       ├── roster_msoc2.py
│       ├── json2csv.py
│       └── json2csv_msoc.py
│
├── data/                          # Same as Option A
│   ├── input/
│   ├── raw/
│   ├── additions/
│   ├── interim/
│   └── output/
│
├── analysis/
│   └── cleaning.qmd
│
├── tests/
│   ├── __init__.py
│   ├── test_field_extractors.py
│   ├── test_scrapers.py
│   ├── test_url_builder.py
│   └── integration/
│       ├── test_sample_teams.py
│       └── test_data/
│
└── docs/
    ├── API.md                     # API documentation for unified scraper
    └── MIGRATION_GUIDE.md         # Guide for transitioning from old scrapers
```

**Recommendation:** Start with **Option A** (simpler, immediate wins), then migrate to **Option B** if/when you pursue the unified scraper approach.

---

## Implementation Steps

### Phase 1: Preparation (No changes to files yet)

1. **Review and backup**
   ```bash
   # Create a backup of current state
   git status
   git add -A
   git commit -m "Backup before reorganization"
   ```

2. **Update .gitignore** to exclude generated data:
   ```
   # Generated data files
   data/raw/
   data/interim/
   data/output/

   # Large intermediate files
   *.json
   !data/input/*.json

   # Python cache
   __pycache__/
   *.pyc
   .pytest_cache/

   # Virtual environments
   .venv/
   venv/

   # IDE
   .vscode/
   .idea/

   # R files
   .Rhistory
   .RData
   .Rproj.user/

   # Old dependency management
   Pipfile
   Pipfile.lock
   ```

### Phase 2: Create Directory Structure

```bash
# Create all directories
mkdir -p src/scrapers src/converters src/utils
mkdir -p data/input data/raw/json data/raw/csv data/additions data/interim data/output
mkdir -p analysis tests docs
```

### Phase 3: Move Source Code Files

```bash
# Move scrapers
mv rosters_main.py src/scrapers/
mv roster_msoc.py src/scrapers/
mv roster_msoc2.py src/scrapers/
mv rosters.py src/scrapers/

# Move converters
mv json2csv.py src/converters/
mv json2csv_msoc.py src/converters/

# Move utilities
mv url_checks.py src/utils/

# Move analysis
mv cleaning.qmd analysis/

# Move test file
mv test.py tests/
```

### Phase 4: Move Data Files

```bash
# Input data (keep in version control)
mv teams.csv data/input/
mv teams_msoc.csv data/input/
mv d3teams.csv data/input/
mv teams.json data/input/
mv valid_items.json data/input/

# Raw JSON outputs (gitignored)
mv rosters_2024.json data/raw/json/
mv rosters_2025.json data/raw/json/
mv rosters_2025_I.json data/raw/json/
mv rosters_msoc.json data/raw/json/
mv rosters.json data/raw/json/

# Raw CSV outputs (gitignored)
mv rosters_2024.csv data/raw/csv/
mv rosters_2025_I.csv data/raw/csv/
mv rosters_msoc_2024.csv data/raw/csv/
mv rosters_msoc_2025.csv data/raw/csv/
mv rosters_msoc.csv data/raw/csv/

# Manual additions (keep in version control)
mv adds.csv data/additions/
mv d3adds.csv data/additions/

# Interim processing files (gitignored)
mv need_rosters.csv data/interim/

# Final outputs (gitignored)
mv combined_rosters_2024.csv data/output/
```

### Phase 5: Update File References

After moving files, update all import statements and file paths:

**Files needing path updates:**

1. **src/scrapers/rosters_main.py**
   - Change: `file_path = 'teams.csv'`
   - To: `file_path = '../../data/input/teams.csv'`
   - Change: Output JSON paths to `../../data/raw/json/`

2. **src/scrapers/roster_msoc.py**
   - Update input CSV paths to `../../data/input/`
   - Update output JSON paths to `../../data/raw/json/`

3. **src/scrapers/roster_msoc2.py**
   - Update input CSV paths to `../../data/input/`
   - Update output CSV paths to `../../data/additions/`

4. **src/converters/json2csv.py**
   - Update input path: `../../data/raw/json/`
   - Update output path: `../../data/raw/csv/`

5. **src/converters/json2csv_msoc.py**
   - Update input path: `../../data/raw/json/`
   - Update output path: `../../data/raw/csv/`

6. **analysis/cleaning.qmd**
   - Update all read_csv paths to `../data/raw/csv/`, `../data/additions/`, etc.
   - Update write_csv paths to `../data/output/` and `../data/interim/`

7. **src/utils/url_checks.py**
   - Update teams.csv path to `../../data/input/teams.csv`

### Phase 6: Update Documentation

1. **Update CLAUDE.md** with new structure:
   - Add "Repository Structure" section
   - Update all command examples with new paths
   - Document which directories are version controlled vs. gitignored

2. **Update README.md** with:
   - New directory structure overview
   - Quick start guide with new paths
   - Note about data/ directory organization

### Phase 7: Testing

```bash
# Test each scraper with new paths
cd src/scrapers
python rosters_main.py  # Verify it reads/writes correctly

# Test converters
cd ../converters
python json2csv.py

# Test analysis
cd ../../analysis
quarto render cleaning.qmd

# Verify git status
git status  # Should show only tracked files, not data/raw or data/output
```

### Phase 8: Commit Changes

```bash
git add -A
git commit -m "Reorganize repository structure

- Move source code to src/ directory
- Organize data files by type (input/raw/additions/interim/output)
- Move analysis scripts to analysis/
- Update .gitignore to exclude generated data
- Update all file path references in code"
```

---

## Benefits of New Structure

### Track 1 Benefits (Reorganization Only)

#### 1. **Clear Separation of Concerns**
   - Source code is separated from data
   - Input data is separated from generated data
   - Manual additions are clearly identified

#### 2. **Better Version Control**
   - Only source code, input data, and manual additions are tracked
   - Large generated files (JSON, intermediate CSVs) are gitignored (~28MB not in repo)
   - Easier to see meaningful changes in git diffs
   - Faster git operations

#### 3. **Improved Discoverability**
   - New developers can quickly understand the project structure
   - Clear distinction between scrapers, converters, and utilities
   - Data pipeline is evident from directory structure

#### 4. **Scalability**
   - Easy to add new scrapers in `src/scrapers/`
   - Easy to add new analysis scripts in `analysis/`
   - Clear place for future test files

#### 5. **Standard Data Science Project Layout**
   - Follows common conventions (similar to Cookiecutter Data Science)
   - Familiar structure for data science practitioners
   - Easier to onboard new contributors

### Track 1 + Track 2 Benefits (Reorganization + Unified Scraper)

All Track 1 benefits PLUS:

#### 6. **Single Command Line Interface**
   - One command replaces 3 separate scraper runs
   - `python src/soccer_roster_scraper.py -season 2025 -division I`
   - No need to know which scraper to use

#### 7. **Automatic Scraper Selection**
   - Configuration-driven approach selects appropriate scraper
   - Adding new team = 1 line in config file

#### 8. **Season Verification**
   - Guarantees correct season is scraped
   - Prevents stale data issues
   - Auto-generates `failed_year_check.csv`

#### 9. **Comprehensive Error Tracking**
   - Auto-generates `zero_players.csv` for teams with no data
   - Auto-generates `failed_year_check.csv` for wrong seasons
   - Know exactly what needs manual review

#### 10. **Professional Code Quality**
   - Type hints throughout
   - Proper logging (not print statements)
   - Testable components
   - SOLID principles

#### 11. **Extensibility**
   - Easy to add coaches scraping (like WBB)
   - Easy to add women's soccer (reuse same code)
   - Easy to add new URL patterns or scraping strategies

---

## Decision Framework

### Should You Do Track 1 (Reorganization)?

**Do Track 1 if:**
- ✅ You want cleaner git history
- ✅ You're tired of 31 files in root directory
- ✅ You want to exclude large generated files from git
- ✅ You have 4-6 hours available
- ✅ You want immediate improvements with low risk

**Skip Track 1 if:**
- ❌ You're about to delete the entire repo and start over
- ❌ Current structure works perfectly for you
- ❌ You're planning Track 2 immediately (can reorganize as part of that)

**Risk Level:** Very Low - Can be reversed easily, doesn't break functionality

### Should You Do Track 2 (Unified Scraper)?

**Do Track 2 if:**
- ✅ You frequently add new teams (saves time long-term)
- ✅ You need to scrape multiple seasons per year
- ✅ Current 3-script approach feels painful
- ✅ You want season verification (prevent bad data)
- ✅ You plan to scrape women's soccer or coaches
- ✅ You have 24-32 hours available (can be done in chunks)
- ✅ You're comfortable with larger, more complex codebases

**Skip Track 2 if:**
- ❌ Current scrapers work fine for your needs
- ❌ You rarely add new teams
- ❌ You don't have time for the investment
- ❌ You prefer simple, separate scripts over unified systems
- ❌ You're planning to sunset this project soon

**Risk Level:** Medium - Requires validation, but old scrapers can remain as backup

### Recommended Sequences

#### Sequence 1: Reorganization Only (Low Risk, Quick Wins)
1. Do Track 1 (4-6 hours)
2. Stop here
3. Evaluate Track 2 in 3-6 months based on pain points

**Best for:** Stable projects with infrequent changes

#### Sequence 2: Reorganization Then Unification (Staged Approach)
1. Do Track 1 (4-6 hours)
2. Test and validate reorganized structure
3. Do Track 2 over 1-2 weeks (24-32 hours)
4. Keep old scrapers in `src/legacy/` until confident

**Best for:** Projects where you want improvements but need to validate each step

#### Sequence 3: Full Transformation (All-In Approach)
1. Do Track 1 + Track 2 concurrently (28-38 hours total)
2. Reorganize directly into Option B structure
3. Implement unified scraper from WBB architecture
4. Parallel validation with old scrapers

**Best for:** Projects with active development and clear need for improvements

---

## Alternative Considerations

### Simpler Reorganization (If Option A Feels Too Complex)

If the proposed structure feels too granular:

```
mens-soccer/
├── src/
│   ├── scrapers/
│   ├── converters/
│   └── utils/
├── data/
│   ├── input/
│   └── output/
└── analysis/
```

**Pros:** Simpler, fewer directories
**Cons:** No separation of raw/interim/additions, less clear data flow

### Keep Python in Root (Minimal Change)

If you want minimal disruption:

```
mens-soccer/
├── rosters_main.py
├── roster_msoc.py
├── ... (other scripts)
└── data/
    ├── input/
    ├── raw/
    └── output/
```

**Pros:** Scripts easier to run, minimal path changes
**Cons:** Root still cluttered, but better than current state

### Season-Based Organization (Alternative Paradigm)

Organize by season instead of file type:

```
mens-soccer/
├── src/
├── seasons/
│   ├── 2024/
│   │   ├── rosters.csv
│   │   └── rosters.json
│   └── 2025/
│       ├── rosters.csv
│       └── rosters.json
```

**Pros:** Good for historical comparisons
**Cons:** Duplicates structure for each season, harder to see current state

---

## Recommendation

### For Most Users: Sequence 2 (Staged Approach)

**Week 1: Do Track 1 (Reorganization)**
- 4-6 hours of work
- Immediate improvements to repository cleanliness
- Better git hygiene
- Low risk, easy to validate
- **Deliverable:** Organized directory structure (Option A)

**Evaluate: Does Current Scraper Approach Feel Painful?**
- If YES → Proceed to Track 2
- If NO → Stop here, revisit in 3-6 months

**Weeks 2-4: Do Track 2 (Unified Scraper) - If Needed**
- 24-32 hours over 1-2 weeks
- Can be done in chunks (2-4 hours per session)
- Phased rollout (D-I → D-II → D-III)
- Keep old scrapers in `src/legacy/` as backup
- **Deliverable:** Unified scraper with configuration-driven architecture

### Why This Approach Works

1. **Quick wins first:** Track 1 gives immediate benefits with minimal risk
2. **Informed decision:** After Track 1, you'll have better sense of whether Track 2 is needed
3. **Reversible:** Can stop after Track 1 if satisfied
4. **Validated:** Each track is tested independently
5. **Sustainable:** Improves both current state AND future scalability

### Alternative: Track 1 Only (If Time-Constrained)

If you don't have 24-32 hours for Track 2:

**Just do Track 1** (4-6 hours) and get:
- ✅ Cleaner repository structure
- ✅ Better git hygiene (~28MB excluded from git)
- ✅ Easier to find files
- ✅ Professional-looking structure

Then revisit Track 2 when:
- You need to add 10+ new teams
- You need to scrape multiple seasons
- You want to add women's soccer or coaches
- Current approach becomes too manual/painful

---

## Migration Checklist

### Track 1: Reorganization Checklist

**Preparation:**
- [ ] Review current state and commit backup
- [ ] Read through this plan and WBB_SCRAPER_ADAPTATION_PLAN.md
- [ ] Decide on Option A (current scrapers) or Option B (unified scraper)

**Implementation:**
- [ ] Update .gitignore with new patterns
- [ ] Create directory structure (Option A or B)
- [ ] Move source code files to src/
- [ ] Move data files to data/
- [ ] Move analysis files to analysis/
- [ ] Move or create test files in tests/

**Update File Paths:**
- [ ] Update file paths in rosters_main.py
- [ ] Update file paths in roster_msoc.py
- [ ] Update file paths in roster_msoc2.py
- [ ] Update file paths in json2csv.py
- [ ] Update file paths in json2csv_msoc.py
- [ ] Update file paths in url_checks.py
- [ ] Update file paths in cleaning.qmd

**Documentation:**
- [ ] Update CLAUDE.md with new structure
- [ ] Update README.md with quick start guide
- [ ] Add REORGANIZATION_PLAN.md to repo (this file)
- [ ] Add WBB_SCRAPER_ADAPTATION_PLAN.md to repo

**Testing:**
- [ ] Test rosters_main.py with new paths
- [ ] Test roster_msoc.py with new paths
- [ ] Test roster_msoc2.py with new paths
- [ ] Test json2csv converters
- [ ] Test cleaning.qmd analysis
- [ ] Verify .gitignore is working (check git status)
- [ ] Verify no large files (>1MB) in git

**Finalization:**
- [ ] Commit reorganization with descriptive message
- [ ] Delete Pipfile/Pipfile.lock if no longer needed
- [ ] Clean up any temporary files

**Decision Point:**
- [ ] Evaluate if Track 2 (unified scraper) is needed
- [ ] If yes, proceed to Track 2 checklist below
- [ ] If no, document decision and revisit in 3-6 months

### Track 2: Unified Scraper Checklist

(Only proceed if Track 1 is complete OR doing Sequence 3)

**Planning:**
- [ ] Review WBB_SCRAPER_ADAPTATION_PLAN.md in detail
- [ ] Analyze teams.csv to categorize URL patterns
- [ ] Create team categorization spreadsheet
- [ ] Decide on phased rollout (D-I first recommended)

**Phase 1: Data Structure (2-3 hours)**
- [ ] Create Player dataclass with soccer-specific fields
- [ ] Add major field extraction
- [ ] Test dataclass with sample data

**Phase 2: Field Extractors (3-4 hours)**
- [ ] Implement FieldExtractors class
- [ ] Update position extraction for soccer (GK/D/M/F)
- [ ] Update height extraction (imperial + metric)
- [ ] Update hometown parsing (international players)
- [ ] Add major field extraction
- [ ] Write unit tests for extractors

**Phase 3: URL Patterns (4-5 hours)**
- [ ] Analyze all teams in teams.csv
- [ ] Categorize by URL pattern (Sidearm/msoc/data-label)
- [ ] Create TeamConfig mappings
- [ ] Test URL construction for sample teams

**Phase 4: Scrapers (5-6 hours)**
- [ ] Implement BaseScraper class
- [ ] Implement StandardScraper (Sidearm)
- [ ] Implement TableScraper (msoc + data-label)
- [ ] Add SeasonVerifier integration
- [ ] Test with 5-10 teams per scraper type

**Phase 5: URL Builder (2-3 hours)**
- [ ] Implement URLBuilder class
- [ ] Add soccer-specific URL patterns
- [ ] Test URL generation for all pattern types

**Phase 6: CLI & Manager (2-3 hours)**
- [ ] Implement RosterManager class
- [ ] Implement ScraperFactory
- [ ] Create main() with argparse
- [ ] Add logging configuration
- [ ] Test CLI with various options

**Phase 7: Testing (5-6 hours)**
- [ ] Test Division I teams (sample of 10-20)
- [ ] Compare output with old scrapers
- [ ] Validate player counts match
- [ ] Check zero_players.csv generation
- [ ] Check failed_year_check.csv generation
- [ ] Test edge cases (no roster, wrong season, etc.)

**Phase 8: Migration (2-3 hours)**
- [ ] Move old scrapers to src/legacy/
- [ ] Update CLAUDE.md with unified scraper docs
- [ ] Create MIGRATION_GUIDE.md
- [ ] Update pyproject.toml dependencies if needed
- [ ] Run full scrape for one division
- [ ] Compare results with old approach
- [ ] Commit unified scraper

**Phase 9: Expansion (If Phased Rollout)**
- [ ] Add Division II teams to TeamConfig
- [ ] Test D-II teams
- [ ] Add Division III teams to TeamConfig
- [ ] Test D-III teams
- [ ] Full NCAA coverage achieved
- [ ] Deprecate old scrapers officially

**Optional Enhancements:**
- [ ] Add coach scraping capability
- [ ] Add women's soccer support
- [ ] Add Playwright support for JS-heavy sites
- [ ] Create comprehensive test suite
- [ ] Add API documentation

---

## Questions to Consider

1. **Should README.md have substantial content?** If empty, consider populating it with project overview.

2. **Is rosters.py still needed?** It uses Selenium (heavier dependency). If not used, consider moving to `archive/` directory.

3. **Should we keep multiple season files?** Consider archiving old seasons (2024) if 2025 is the focus.

4. **Should test.py be deleted?** It's currently empty. Delete or add actual tests.

5. **Keep Pipfile.lock?** Since the project now uses uv/pyproject.toml, consider removing Pipfile.lock.

---

## Timeline Estimates

### Track 1: Reorganization Only

| Phase | Task | Time |
|-------|------|------|
| 1 | Preparation & backup | 10 min |
| 2 | Create directory structure | 5 min |
| 3 | Move source code files | 10 min |
| 4 | Move data files | 10 min |
| 5 | Update file paths in 7 files | 60-90 min |
| 6 | Update documentation | 30 min |
| 7 | Testing all components | 45 min |
| 8 | Commit & cleanup | 10 min |
| **Total** | | **3-4 hours** |

**Can be done in:** One focused session, or split across 2 days

### Track 2: Unified Scraper

| Phase | Task | Time |
|-------|------|------|
| Phase 1 | Data Structure | 2-3 hours |
| Phase 2 | Field Extractors | 3-4 hours |
| Phase 3 | URL Patterns Analysis | 4-5 hours |
| Phase 4 | Scraper Classes | 5-6 hours |
| Phase 5 | URL Builder | 2-3 hours |
| Phase 6 | CLI & Manager | 2-3 hours |
| Phase 7 | Testing | 5-6 hours |
| Phase 8 | Migration | 2-3 hours |
| Phase 9 | Expansion (Optional) | 3-4 hours |
| **Total** | | **24-32 hours** |

**Can be done in:**
- 3-4 full days (8 hour sessions)
- 6-8 half days (4 hour sessions)
- 12-16 short sessions (2 hour sessions)
- 1-2 weeks working a few hours per day

### Combined Timeline (Both Tracks)

**Sequence 2 (Recommended):**
- Week 1: Track 1 (3-4 hours)
- Week 2-4: Track 2 (24-32 hours over 1-2 weeks)
- **Total: 27-36 hours across 3-4 weeks**

**Sequence 3 (All-In):**
- All phases concurrently
- Reorganize directly into Option B structure
- **Total: 28-38 hours (can be compressed to 1-2 weeks)**

---

## Summary: Two Paths Forward

This reorganization plan offers two complementary improvements to the mens-soccer repository:

### Path 1: Reorganization (Track 1) - Quick Wins

**What it does:**
- Organizes 31 scattered files into logical directories
- Separates code, data, and analysis
- Excludes ~28MB of generated files from git
- Professional-looking structure

**Time Investment:** 3-4 hours
**Risk Level:** Very Low
**When to do it:** Soon - immediate benefits with minimal risk

**Outcome:** Cleaner, more maintainable repository

### Path 2: Unified Scraper (Track 2) - Long-Term Scalability

**What it does:**
- Replaces 3 separate scrapers with 1 unified tool
- Configuration-driven (200+ teams via simple config)
- Automatic scraper selection
- Season verification prevents bad data
- Comprehensive error tracking

**Time Investment:** 24-32 hours (can be chunked)
**Risk Level:** Medium (validated with old scrapers as backup)
**When to do it:** After Track 1, if current approach feels painful

**Outcome:** Professional-grade, maintainable, extensible scraping system

### Recommended Next Steps

1. **Read WBB_SCRAPER_ADAPTATION_PLAN.md** to understand the unified scraper architecture
2. **Decide your approach:**
   - **Conservative:** Do Track 1 only → reassess in 3-6 months
   - **Balanced:** Do Track 1 → evaluate → then Track 2 if needed (Sequence 2)
   - **Aggressive:** Do both tracks together (Sequence 3)
3. **Start with Track 1** - it's low-risk and gives immediate wins
4. **Evaluate Track 2** after Track 1 is complete

### Success Metrics

**Track 1 Success:**
- ✅ All files in organized directories
- ✅ Git status shows only tracked files (no large generated files)
- ✅ All scrapers/converters work with new paths
- ✅ CLAUDE.md and README.md updated

**Track 2 Success:**
- ✅ Single command scrapes all teams
- ✅ 95%+ of teams scrape successfully
- ✅ zero_players.csv and failed_year_check.csv auto-generated
- ✅ Adding new team takes < 1 minute
- ✅ Old scrapers in src/legacy/ for reference

### Questions?

Refer to:
- This document for reorganization details
- WBB_SCRAPER_ADAPTATION_PLAN.md for unified scraper details
- CLAUDE.md for project-specific context

Both documents complement each other:
- This plan focuses on file organization
- WBB plan focuses on scraper architecture
- Together, they provide a complete modernization strategy

---

**Document Version:** 1.0 (Updated with WBB scraper integration)
**Last Updated:** 2025-10-24
**Related Documents:** WBB_SCRAPER_ADAPTATION_PLAN.md, CLAUDE.md

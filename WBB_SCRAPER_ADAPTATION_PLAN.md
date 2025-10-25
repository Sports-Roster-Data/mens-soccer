# WBB Scraper Adaptation Plan for Men's Soccer

## Executive Summary

The WBB (Women's Basketball) scraper is a **3,089-line production-grade web scraper** with a sophisticated modular architecture. Adapting it for men's soccer would replace the current three separate scrapers (`rosters_main.py`, `roster_msoc.py`, `roster_msoc2.py`) with a single, maintainable, and extensible solution.

**Recommendation:** Adapt the WBB scraper architecture for men's soccer. The upfront investment (~20-30 hours) will pay dividends in maintainability, reliability, and ease of adding new teams.

---

## Current State vs. WBB Architecture

### Current Men's Soccer Scrapers (3 separate scripts)

| Script | Lines | Approach | Limitations |
|--------|-------|----------|-------------|
| `rosters_main.py` | ~150 | Sidearm Sports platform, BeautifulSoup | No season verification, hardcoded in main(), no error tracking |
| `roster_msoc.py` | ~200 | Table-based scraping, BeautifulSoup | Multiple URL fallbacks, no verification |
| `roster_msoc2.py` | ~150 | Data-label attributes, BeautifulSoup | Manual CSV input/output, limited error handling |

**Total:** ~500 lines across 3 files, each with duplicated patterns

### WBB Scraper Architecture (single unified script)

| Component | Purpose | Benefits |
|-----------|---------|----------|
| **Player dataclass** | Structured data representation | Type safety, validation, easy serialization |
| **FieldExtractors** | Regex patterns for parsing | Reusable, tested patterns |
| **SeasonVerifier** | Validate scraped data is correct season | Prevents stale/wrong data |
| **JSTemplates** | JavaScript selectors for dynamic sites | Handles Vue.js, Nuxt.js, DataTables |
| **HeaderMapper** | Normalize column names | Handles inconsistent websites |
| **URLBuilder** | Construct roster URLs | Supports 10+ URL patterns |
| **TeamConfig** | Team-specific configurations | Easy to add new teams |
| **ScraperFactory** | Create appropriate scraper type | Extensible, follows SOLID principles |
| **4 Scraper Classes** | StandardScraper, TableScraper, JavaScriptScraper, VueDataScraper | Specialized for different platforms |
| **RosterManager** | Orchestrate scraping operations | Batch processing, error tracking |

**Total:** 3,089 lines in 1 file, but highly modular and extensible

---

## Key Architectural Improvements

### 1. **Configuration-Driven Approach**

**Current Soccer:**
```python
# Hardcoded in main loop
if '/mens-soccer' in row.get('url', ''):
    # Scrape with rosters_main.py
```

**WBB Pattern:**
```python
class TeamConfig:
    NUXT_JS_TEAMS = {71: 'https://bgsufalcons.com', ...}
    TABLE_BASED_TEAMS = {5: {'url_format': 'default'}, ...}
    CUSTOM_JS_TEAMS = {128: {'selector': 'nuxt_roster', ...}}

    @classmethod
    def get_config(cls, team_id: int) -> Dict:
        # Returns appropriate config for team
```

**Benefit:** Adding a new team is a single line in a config dict, not a new script.

### 2. **Factory Pattern for Scraper Selection**

**Current Soccer:** Separate scripts that must be run manually

**WBB Pattern:**
```python
config = TeamConfig.get_config(team['ncaa_id'])
scraper = ScraperFactory.create_scraper(config['type'])
players = scraper.scrape_roster(team, season, config['url_format'])
```

**Benefit:** Automatic scraper selection based on team configuration.

### 3. **Season Verification**

**Current Soccer:** No verification - you might scrape 2024 data when you wanted 2025

**WBB Pattern:**
```python
if not SeasonVerifier.verify_season_on_page(html, season, 'player'):
    logger.warning(f"Season verification failed for {team['team']}")
    return []
```

**Benefit:** Guarantees you're scraping the correct season's data.

### 4. **Structured Data with Dataclasses**

**Current Soccer:** Raw dictionaries with inconsistent keys

**WBB Pattern:**
```python
@dataclass
class Player:
    team_id: int
    team: str
    name: str
    year: str
    position: str
    # ... with type hints and validation
```

**Benefit:** Type safety, autocomplete in IDEs, easier to refactor.

### 5. **Comprehensive Error Tracking**

**Current Soccer:** Print statements, no structured error tracking

**WBB Pattern:**
```python
class RosterManager:
    def __init__(self):
        self.zero_player_teams = []
        self.failed_year_check_teams = []

    # Automatically generates CSV files with failures:
    # - rosters_2025_zero_players.csv
    # - rosters_2025_failed_year_check.csv
```

**Benefit:** Know exactly which teams failed and why.

### 6. **Flexible URL Construction**

**Current Soccer:**
```python
# rosters_main.py
roster_url = row['url'] + f'/roster/{season}'

# roster_msoc.py
# Try multiple patterns manually
url1 = f"{base_url}/2024-25/roster"
url2 = f"{base_url}/roster/2024"
```

**WBB Pattern:**
```python
class URLBuilder:
    @staticmethod
    def build_url(base_url, season, url_format, entity_type='player'):
        # Supports: default, season_path, season_first,
        #           iowa_table, clemson, direct, etc.
```

**Benefit:** Centralized URL logic, easy to add new patterns.

### 7. **Modular Field Extraction**

**Current Soccer:** Inline extraction in each scraper

**WBB Pattern:**
```python
class FieldExtractors:
    @staticmethod
    def extract_jersey_number(text: str) -> str:
        # Multiple regex patterns

    @staticmethod
    def extract_height(text: str) -> str:
        # Handles multiple formats: 6'2", 6′2″, "Height: 6-2"

    @staticmethod
    def parse_hometown_school(text: str) -> Dict:
        # Intelligently splits "City, State / High School / College"
```

**Benefit:** Reusable, testable, consistent across all scrapers.

---

## Adaptation Strategy

### Phase 1: Data Structure Adaptation (2-3 hours)

**Changes needed:**

1. **Update Player dataclass for soccer-specific fields:**

```python
@dataclass
class Player:
    team_id: int          # ncaa_id
    team: str             # team name
    player_id: Optional[str] = None
    name: str = ""
    year: str = ""        # academic_year/class
    hometown: str = ""
    high_school: str = ""
    previous_school: str = ""
    height: str = ""
    position: str = ""    # Soccer: GK, D, M, F (not G/F/C)
    jersey: str = ""
    url: str = ""
    season: str = ""
    major: str = ""       # ADD: Soccer sites often have this (basketball doesn't)
```

**Key difference:** Soccer rosters include `major` field, basketball doesn't.

### Phase 2: Field Extractor Adaptation (3-4 hours)

**Changes needed:**

1. **Update position extraction for soccer:**

```python
@staticmethod
def extract_position(text: str) -> str:
    """Extract position from text - SOCCER VERSION"""
    # Soccer positions: GK, D, M, F (or Goalkeeper, Defender, Midfielder, Forward)
    position_match = re.search(r'\b(GK|D|M|F|MF|DF|FW)\b', text, re.IGNORECASE)
    if position_match:
        return position_match.group(1).upper()

    # Full position names
    text_upper = text.upper()
    if 'GOALKEEPER' in text_upper or 'GOALIE' in text_upper:
        return 'GK'
    elif 'DEFENDER' in text_upper:
        return 'D'
    elif 'MIDFIELDER' in text_upper or 'MIDFIELD' in text_upper:
        return 'M'
    elif 'FORWARD' in text_upper:
        return 'F'

    return ''
```

2. **Add major field extraction (unique to soccer):**

```python
@staticmethod
def extract_major(element) -> str:
    """Extract major/academic program field"""
    major_element = element.find('span', class_='sidearm-roster-player-major')
    if major_element:
        return FieldExtractors.clean_text(major_element.get_text())
    return ''
```

### Phase 3: URL Pattern Analysis (4-5 hours)

**Task:** Analyze all teams in `teams.csv` and categorize by URL pattern

Current patterns identified in soccer:
- `/mens-soccer/roster/{season}` - Sidearm Sports (majority)
- `/msoc/2024-25/roster` or `/msoc/roster/2024` - msoc pattern
- `/sports/msoc/{season}/roster` - Alternative pattern
- Teams with `data-label` attributes - Table pattern

**Create TeamConfig mappings:**

```python
class TeamConfig:
    # Sidearm Sports teams (standard scraper)
    SIDEARM_TEAMS = {
        # ncaa_id: base_url
        123: 'https://goheels.com',
        456: 'https://virginiasports.com',
        # ... (majority of D-I teams)
    }

    # msoc/index pattern teams
    MSOC_TEAMS = {
        # ncaa_id: {'url_format': 'msoc_pattern'}
        789: {'url_format': 'msoc_pattern'},
        # ...
    }

    # Data-label table teams (mostly D-III)
    TABLE_TEAMS = {
        # ncaa_id: {'url_format': 'data_label'}
        999: {'url_format': 'data_label'},
        # ...
    }
```

**Time estimate:** Review all 300+ teams in teams.csv, test URLs, categorize.

### Phase 4: Scraper Class Adaptation (5-6 hours)

**1. StandardScraper → Adapt for Sidearm Soccer Sites**

Current WBB selectors work for Sidearm, but need to verify soccer-specific classes:

```python
# Basketball uses:
'li.sidearm-roster-player'
'span.sidearm-roster-player-jersey-number'
'span.sidearm-roster-player-position-long-short'

# Soccer likely uses same classes - verify and test
```

**Test with 5-10 representative soccer teams.**

**2. TableScraper → Adapt for msoc and data-label patterns**

Currently handles multiple table formats. Need to add:
- `msoc/index` table structure
- `data-label` attribute parsing (from `roster_msoc2.py`)

```python
def _parse_data_label_table(self, html, team, season):
    """Parse tables using data-label attributes (D-III schools)"""
    table = html.find('table')
    if not table:
        return []

    rows = table.find_all('tr')[1:]  # Skip header
    players = []

    for row in rows:
        player = Player(team_id=team['ncaa_id'], team=team['team'], season=season)

        # Find cells by data-label attribute
        for cell in row.find_all('td'):
            label = cell.get('data-label', '').strip()
            value = cell.get_text(strip=True)

            if label in ['No.', 'Number', '#']:
                player.jersey = value
            elif label == 'Name':
                # Extract name and URL...
            # ... etc

        if player.name:
            players.append(player)

    return players
```

**3. JavaScriptScraper → Test if needed for soccer**

Some soccer sites may use Vue.js/Nuxt.js like basketball. Test and adapt if necessary.

### Phase 5: URL Builder Adaptation (2-3 hours)

Add soccer-specific URL patterns:

```python
class URLBuilder:
    @staticmethod
    def build_url(base_url: str, season: str, url_format: str,
                  entity_type: str = 'player', sport: str = 'msoc') -> str:
        """Build roster URL - now with sport parameter"""

        if url_format == 'msoc_pattern':
            # Try 2024-25 format first
            return f"{base_url}/msoc/{season}/roster"

        elif url_format == 'msoc_fallback':
            # Try just year format
            year = season.split('-')[0]
            return f"{base_url}/msoc/roster/{year}"

        elif url_format == 'default':
            # Standard Sidearm: /mens-soccer/roster/{season}
            return f"{base_url}/mens-soccer/roster/{season}"

        # ... other patterns
```

### Phase 6: Command-Line Interface (1-2 hours)

Update argument parsing for soccer context:

```python
def main():
    parser = argparse.ArgumentParser(description='NCAA Men\'s Soccer Roster Scraper')
    parser.add_argument('-season', required=True, help='Season (e.g., "2024" or "2024-25")')
    parser.add_argument('-teams', nargs='*', type=int, help='Specific team IDs')
    parser.add_argument('-team', type=int, help='Single team ID')
    parser.add_argument('-division', choices=['I', 'II', 'III'], help='Filter by division')
    parser.add_argument('-output', help='Output CSV file path')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
```

### Phase 7: Testing & Validation (5-6 hours)

**Test suite:**

1. **Sample teams from each scraper type:**
   - 5 Sidearm teams (StandardScraper)
   - 5 msoc/index teams (TableScraper)
   - 5 data-label teams (TableScraper)

2. **Edge cases:**
   - Teams with no roster data
   - Teams with wrong season on page
   - Teams with missing fields
   - International player names with special characters

3. **Compare output:**
   - Run new scraper on same teams as old scrapers
   - Compare player counts
   - Compare field values
   - Validate no data loss

4. **Division filtering:**
   - Test scraping only D-I, D-II, or D-III

### Phase 8: Migration & Documentation (2-3 hours)

1. **Create `rosters_unified.py`** (adapted WBB scraper)
2. **Update CLAUDE.md** with new architecture
3. **Create migration guide** for users
4. **Deprecate old scrapers** (move to `archive/` directory)

---

## Detailed File Mapping

### Files to Create

```
src/scrapers/
├── soccer_roster_scraper.py    # Main unified scraper (adapted from WBB)
└── soccer_config.py             # TeamConfig split out for maintainability
```

### Code Organization

```python
# soccer_roster_scraper.py structure:

# 1. Imports and setup (lines 1-40)
# 2. Player dataclass (lines 42-65)
# 3. FieldExtractors class (lines 67-220)
# 4. SeasonVerifier class (lines 221-305)
# 5. JSTemplates class (lines 307-1248) - may be smaller for soccer
# 6. HeaderMapper class (lines 1250-1281)
# 7. URLBuilder class (lines 1283-1350)
# 8. TeamConfig class (lines 1352-1712) → Move to soccer_config.py
# 9. BaseScraper class (lines 1714-1779)
# 10. StandardScraper class (lines 1781-2235)
# 11. TableScraper class (lines 2237-2476)
# 12. JavaScriptScraper class (lines 2478-2618) - may not need for soccer
# 13. VueDataScraper class (lines 2620-2714) - may not need for soccer
# 14. ScraperFactory class (lines 2716-2732)
# 15. RosterManager class (lines 2734-2942)
# 16. main() function (lines 2944-3089)
```

**Estimated soccer version:** ~2,000-2,500 lines (slightly smaller since soccer may not need all JS patterns)

---

## Benefits Summary

### Immediate Benefits

1. **Single Command Line Interface**
   ```bash
   # Old way (3 separate commands):
   python rosters_main.py
   python roster_msoc.py
   python roster_msoc2.py

   # New way (1 command):
   python soccer_roster_scraper.py -season 2025 -division I
   ```

2. **Automatic Scraper Selection**
   - No need to know which scraper to use
   - Configuration handles it automatically

3. **Season Verification**
   - Prevents scraping wrong season's data
   - Automatic validation

4. **Error Tracking**
   - Generates `zero_players.csv` for failed teams
   - Generates `failed_year_check.csv` for wrong seasons
   - Know exactly what needs manual review

### Long-Term Benefits

1. **Easier to Add New Teams**
   ```python
   # Old way: Modify script logic, test, debug

   # New way: Add one line to TeamConfig
   SIDEARM_TEAMS[999] = 'https://newschool.com'
   ```

2. **Easier to Add New Patterns**
   ```python
   # Just add new URL format to URLBuilder
   # Just add new scraper class if needed
   # Config-based, not script-based
   ```

3. **Better Maintainability**
   - Clear separation of concerns
   - Each class has single responsibility
   - Easy to test individual components

4. **Extensibility**
   - Want to scrape coaches too? Already built in (like WBB)
   - Want to scrape women's soccer? Reuse same code
   - Want to add new fields? Update dataclass

5. **Professional Code Base**
   - Type hints throughout
   - Logging instead of print statements
   - Proper error handling
   - Follows Python best practices

---

## Risk Assessment

### Low Risk

- **Data loss:** We can run old and new scrapers side-by-side to validate
- **Breaking changes:** Old scrapers remain until validation is complete

### Medium Risk

- **Time investment:** 20-30 hours upfront for ~500 teams
  - **Mitigation:** Start with Division I only (~200 teams), validate, then expand

### High Value

- **ROI:** After initial investment, adding teams takes minutes instead of hours
- **Sustainability:** Much easier to maintain going forward
- **Reliability:** Season verification prevents bad data

---

## Implementation Timeline

| Phase | Hours | Tasks |
|-------|-------|-------|
| Phase 1: Data Structure | 2-3 | Adapt Player dataclass for soccer |
| Phase 2: Field Extractors | 3-4 | Soccer positions, major field, height/hometown parsing |
| Phase 3: URL Patterns | 4-5 | Analyze teams.csv, categorize URL patterns, create config |
| Phase 4: Scrapers | 5-6 | Adapt StandardScraper, TableScraper, test patterns |
| Phase 5: URL Builder | 2-3 | Add soccer URL patterns |
| Phase 6: CLI | 1-2 | Update command-line interface |
| Phase 7: Testing | 5-6 | Test sample teams, validate output, edge cases |
| Phase 8: Migration | 2-3 | Documentation, deprecation, cleanup |
| **Total** | **24-32 hours** | |

### Phased Rollout Approach

**Week 1: Division I Only**
- Implement core architecture
- Configure ~200 D-I teams
- Validate against current scrapers
- **Deliverable:** Working scraper for D-I

**Week 2: Division II**
- Add D-II teams (~150 teams)
- Handle any new patterns discovered
- **Deliverable:** D-I + D-II coverage

**Week 3: Division III**
- Add D-III teams (most complex, various patterns)
- Complete TableScraper with data-label support
- **Deliverable:** Full NCAA coverage

**Week 4: Polish & Documentation**
- Error handling improvements
- Documentation
- Deprecate old scrapers
- **Deliverable:** Production-ready unified scraper

---

## Alternative: Incremental Adaptation

If 20-30 hours feels like too much upfront, consider **incremental adaptation:**

### Minimal Viable Adaptation (8-10 hours)

1. **Keep current scrapers** as-is
2. **Add architectural improvements** to existing code:
   - Add Player dataclass
   - Add SeasonVerifier
   - Add FieldExtractors utility class
   - Add logging
   - Add error tracking (zero_player_teams list)

3. **Don't** build full TeamConfig/Factory pattern yet

**Benefits:**
- Immediate improvements to existing code
- Less upfront time
- Can evolve to full WBB pattern later

**Drawbacks:**
- Still maintain 3 separate scripts
- Still manually decide which scraper to use
- Less elegant architecture

---

## Recommendation

**Full Adaptation with Phased Rollout** is the best approach:

1. **Why not minimal?** The 20-30 hour investment pays for itself quickly:
   - Adding new teams: 30 seconds vs. 15 minutes
   - Debugging: Centralized vs. scattered across 3 files
   - Future features: Much easier to add

2. **Why phased rollout?**
   - Validate early and often (D-I first)
   - Catch issues before full migration
   - Can abort/adjust if problems arise

3. **When to do it?**
   - If you're actively scraping and need to add many new teams: **Do it now**
   - If you're between seasons with time available: **Do it now**
   - If you're happy with current setup: **Wait until pain points emerge**

---

## Code Example: Before & After

### Before (Current - 3 separate scripts)

**Running scrapers:**
```bash
# Step 1: Figure out which teams use which scraper
# Step 2: Edit each script to set season
# Step 3: Run each script separately

python rosters_main.py  # Sidearm teams
python json2csv.py

python roster_msoc.py   # msoc teams
python json2csv_msoc.py

python roster_msoc2.py  # D-III teams
# Already outputs CSV
```

**Adding a new team:**
```python
# 1. Manually test URL to determine which scraper to use
# 2. Verify the team is in teams.csv
# 3. Manually verify URL pattern matches expected
# 4. Run appropriate scraper
# 5. Hope it works
```

### After (Unified WBB-style scraper)

**Running scraper:**
```bash
# One command does everything
python soccer_roster_scraper.py -season 2025 -division I -output rosters_2025_D1.csv

# Output includes:
# - rosters_2025_D1.csv (all successful scrapes)
# - rosters_2025_D1_zero_players.csv (teams that returned no players)
# - rosters_2025_D1_failed_year_check.csv (teams with wrong season)
```

**Adding a new team:**
```python
# 1. Add team to teams.csv (or teams.json)
# 2. Test URL pattern: python soccer_roster_scraper.py -team 999 -url https://newschool.com/mens-soccer/roster -season 2025
# 3. If it works, add to appropriate TeamConfig dict:
#    SIDEARM_TEAMS[999] = 'https://newschool.com'
# 4. Done - team now scraped automatically with others
```

**Code quality comparison:**

```python
# BEFORE (rosters_main.py excerpt)
print(f"Scraping {team_name}...")
if response.status_code == 200:
    soup = BeautifulSoup(response.content, 'html.parser')
    # ... scraping logic inline ...
else:
    print(f"Failed. Status: {response.status_code}")

# AFTER (soccer_roster_scraper.py excerpt)
logger.info(f"Scraping {team['team']} (ID: {team['ncaa_id']})")
html = self.fetch_html(url)
if not html:
    logger.error(f"Failed to fetch HTML for {team['team']}")
    return []

if not SeasonVerifier.verify_season_on_page(html, season, 'player'):
    logger.warning(f"Season verification failed for {team['team']}")
    self.failed_year_check_teams.append({'team_id': team['ncaa_id'], ...})
    return []

players = self._extract_players(html, team, season)
logger.info(f"Found {len(players)} players for {team['team']}")
return players
```

---

## Next Steps

### To Proceed with Full Adaptation:

1. **Decision:** Confirm you want to proceed with full adaptation
2. **Backup:** Commit current state to git
3. **Phase 1:** Start with data structure and field extractors
4. **Phase 3:** Analyze and categorize teams in teams.csv
5. **Phase 4:** Build scrapers
6. **Phase 7:** Validate with side-by-side comparison
7. **Phase 8:** Deprecate old scrapers

### To Proceed with Incremental Adaptation:

1. **Add FieldExtractors** utility class to existing scrapers
2. **Add SeasonVerifier** to validate season
3. **Add Player dataclass** for structured data
4. **Add error tracking** lists
5. **Add logging** instead of print statements
6. **Evaluate:** After these improvements, reassess full adaptation

### Questions to Answer:

1. **How often do you add new teams?** (If frequently, full adaptation is more valuable)
2. **How many seasons do you scrape per year?** (If multiple, automation helps)
3. **Do you plan to scrape women's soccer?** (If yes, unified architecture is essential)
4. **How comfortable are you with larger codebases?** (If very comfortable, full adaptation is easier)
5. **What's your timeline?** (If you need results next week, incremental is safer)

---

## Appendix A: Soccer-Specific Considerations

### Position Abbreviations

Basketball uses: G, F, C (Guard, Forward, Center)
Soccer uses: GK, D, M, F (Goalkeeper, Defender, Midfielder, Forward)

Some sites use variations:
- GK / Goalkeeper / Goalie
- D / Defender / Def
- M / Midfielder / Mid / MF
- F / Forward / Fwd / FW
- Hybrid: D/M, M/F, etc.

**Solution:** FieldExtractors.extract_position() needs soccer-specific logic

### Height Formats

Soccer often uses metric alongside imperial:
- "6'2\"" (basketball standard)
- "6-2"
- "1.88m" (metric)
- "6'2\" / 1.88m" (both)

**Solution:** FieldExtractors.extract_height() should handle both

### Academic Year Variations

Soccer may use different terminology:
- Basketball: Fr, So, Jr, Sr, Gr
- Soccer: Same, but also "1st Year", "2nd Year", etc. (especially international players)

**Solution:** FieldExtractors.normalize_academic_year() may need expansion

### International Players

Soccer rosters have more international players:
- Hometown: "London, England" (not "City, State")
- High school: May be blank or international
- Previous school: Often international clubs

**Solution:** FieldExtractors.parse_hometown_school() should handle country names

### Major Field

Soccer sites often include academic major (basketball sites don't):
- Need to extract from `<span class="sidearm-roster-player-major">`
- Add to Player dataclass
- Include in CSV output

**Solution:** Add major extraction to StandardScraper._extract_player_data()

---

## Appendix B: Team URL Pattern Analysis

Based on current soccer scrapers, expected distribution:

| Pattern | Est. Teams | Scraper | Example |
|---------|-----------|---------|---------|
| Sidearm `/mens-soccer/roster/` | ~60% | StandardScraper | goheels.com/mens-soccer/roster/2024-25 |
| msoc `/msoc/` pattern | ~25% | TableScraper | school.edu/msoc/2024-25/roster |
| data-label tables | ~10% | TableScraper | school.edu/sports/msoc/roster |
| Custom/Other | ~5% | Various | Needs individual testing |

**Action:** Review all teams in teams.csv to verify distribution

---

## Appendix C: Testing Checklist

### Unit Tests (Recommended but not required)

```python
# test_field_extractors.py
def test_extract_position_soccer():
    assert FieldExtractors.extract_position("GK") == "GK"
    assert FieldExtractors.extract_position("Midfielder") == "M"
    assert FieldExtractors.extract_position("Forward/Midfielder") == "F"

def test_extract_height():
    assert FieldExtractors.extract_height("6'2\"") == "6'2\""
    assert FieldExtractors.extract_height("1.88m") == "1.88m"

def test_parse_hometown_international():
    result = FieldExtractors.parse_hometown_school("London, England / Arsenal Academy")
    assert result['hometown'] == "London, England"
    assert result['high_school'] == "Arsenal Academy"
```

### Integration Tests (Required)

**Test teams (representative sample):**

1. **Sidearm - Standard**
   - UNC (457): https://goheels.com/sports/mens-soccer/roster/2024-25
   - Virginia (746): https://virginiasports.com/sports/mens-soccer/roster/2024-25

2. **Sidearm - Variations**
   - Team with major field
   - Team with international players
   - Team with metric heights

3. **msoc/index pattern**
   - Test both URL patterns (/2024-25/roster and /roster/2024)

4. **data-label tables**
   - D-III team with data-label attributes

5. **Edge cases**
   - Team with no current roster
   - Team with wrong season displayed
   - Team with incomplete player data

### Validation Tests (Required)

Compare output from old scrapers vs. new scraper:

```bash
# Old
python rosters_main.py  # Output: rosters_2025.json
python json2csv.py      # Output: rosters_2025.csv

# New
python soccer_roster_scraper.py -season 2024-25 -output rosters_2025_new.csv

# Compare
diff <(sort rosters_2025.csv) <(sort rosters_2025_new.csv)
# Should be identical or explicable differences only
```

---

## Conclusion

The WBB scraper represents a **significant architectural upgrade** over the current men's soccer scrapers. While it requires 20-30 hours of upfront investment, the long-term benefits in maintainability, reliability, and extensibility make it worthwhile.

**Recommended approach:** Full adaptation with phased rollout, starting with Division I teams.

**When to start:** When you have 2-3 consecutive days to focus on the migration, or when you need to add many new teams and the current process feels too manual.

**Success criteria:**
- Single command-line tool replaces 3 separate scripts
- 95%+ of teams scrape successfully
- Zero players and failed year checks are tracked automatically
- Adding new teams takes < 1 minute


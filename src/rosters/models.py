"""Player data model and the canonical CSV field order."""
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict

from .extractors import FieldExtractors

# Canonical roster CSV column order. analysis/cleaning.qmd depends on this
# exact set/order for its 2025 roster read; do not reorder without updating it.
CSV_FIELDS = [
    "ncaa_id", "team", "season", "division", "jersey", "name", "position",
    "height", "class", "major", "hometown", "high_school", "previous_school", "url",
]


@dataclass
class Player:
    """Player data structure for NCAA men's soccer rosters"""
    team_id: int
    team: str
    season: str
    division: str = ""
    player_id: Optional[str] = None
    name: str = ""
    jersey: str = ""
    position: str = ""
    height: str = ""
    year: str = ""  # Academic year (class)
    major: str = ""  # Soccer rosters often include major (basketball doesn't)
    hometown: str = ""
    high_school: str = ""
    previous_school: str = ""
    url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for CSV output"""
        d = asdict(self)

        # Clean string fields to remove excessive whitespace/newlines before output
        for k, v in list(d.items()):
            if isinstance(v, str):
                d[k] = FieldExtractors.clean_text(v)

        # Map 'year' field to 'class' for CSV output (matches existing schema)
        d['class'] = d.pop('year', '')
        # Map team_id to ncaa_id (matches existing schema)
        d['ncaa_id'] = d.pop('team_id')
        # Remove player_id from CSV output (internal use only)
        d.pop('player_id', None)
        return d

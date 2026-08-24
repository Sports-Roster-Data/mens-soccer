"""Pytest setup: make the package importable and expose the fixtures dir."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))

FIXTURES = Path(__file__).resolve().parent / 'fixtures'

import csv
import json

from rosters.models import Player, CSV_FIELDS
from rosters.run import _write_csv, _write_json


def _player(team_id, name):
    return Player(team_id=team_id, team='T', season='2025', division='I', name=name,
                  jersey='1', position='GK').to_dict()


def test_csv_header_and_field_order(tmp_path):
    path = tmp_path / 'r.csv'
    _write_csv(path, [_player(1, 'A')], replace_ids=None)
    with open(path, newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
    assert header == CSV_FIELDS


def test_csv_full_overwrite(tmp_path):
    path = tmp_path / 'r.csv'
    _write_csv(path, [_player(1, 'A'), _player(2, 'B')], replace_ids=None)
    _write_csv(path, [_player(3, 'C')], replace_ids=None)
    with open(path, newline='') as f:
        rows = list(csv.DictReader(f))
    assert [r['name'] for r in rows] == ['C']


def test_csv_merge_preserves_other_teams(tmp_path):
    path = tmp_path / 'r.csv'
    _write_csv(path, [_player(1, 'A'), _player(2, 'B')], replace_ids=None)
    # Re-scrape only team 1; team 2's row must survive.
    _write_csv(path, [_player(1, 'A2')], replace_ids={1})
    with open(path, newline='') as f:
        rows = list(csv.DictReader(f))
    names = {r['ncaa_id']: r['name'] for r in rows}
    assert names == {'1': 'A2', '2': 'B'}


def test_no_tempfile_left_behind(tmp_path):
    path = tmp_path / 'r.csv'
    _write_csv(path, [_player(1, 'A')], replace_ids=None)
    assert not (tmp_path / 'r.csv.tmp').exists()


def test_json_merge(tmp_path):
    path = tmp_path / 'r.json'
    _write_json(path, [_player(1, 'A'), _player(2, 'B')], replace_ids=None)
    _write_json(path, [_player(1, 'A2')], replace_ids={1})
    data = json.loads(path.read_text())
    names = {r['ncaa_id']: r['name'] for r in data}
    assert names == {1: 'A2', 2: 'B'}

import pytest

from rosters.extractors import FieldExtractors as FE

fe_position = FE.extract_position
fe_year = FE.normalize_academic_year
fe_height = FE.extract_height
fe_jersey = FE.extract_jersey_number


@pytest.mark.parametrize('text,expected', [
    ('GK', 'GK'), ('Goalkeeper', 'GK'), ('G', 'GK'),
    ('D', 'D'), ('Defender', 'D'), ('CB', 'D'), ('Back', 'D'),
    ('M', 'M'), ('Midfielder', 'M'), ('CDM', 'M'),
    ('F', 'F'), ('Forward', 'F'), ('Striker', 'F'), ('Winger', 'F'),
    ('', ''),
])
def test_extract_position(text, expected):
    assert fe_position(text) == expected


@pytest.mark.parametrize('text,expected', [
    ('Fr', 'Freshman'), ('Fr.', 'Freshman'), ('FR', 'Freshman'),
    ('So', 'Sophomore'), ('Jr.', 'Junior'), ('SR', 'Senior'),
    ('Gr', 'Graduate'), ('R-Fr', 'Redshirt Freshman'), ('R-Sr.', 'Redshirt Senior'),
    ('1st', 'Freshman'), ('4th', 'Senior'), ('', ''),
])
def test_normalize_academic_year(text, expected):
    assert fe_year(text) == expected


@pytest.mark.parametrize('text,expected', [
    ('6\'2"', '6\'2"'),
    ('6-2', '6-2'),
    ('1.88m', '1.88m'),
    ('', ''),
])
def test_extract_height(text, expected):
    assert fe_height(text) == expected


@pytest.mark.parametrize('text,expected', [
    ('#10', '10'),
    ('No. 7', '7'),
    ('23', '23'),
    ('', ''),
])
def test_extract_jersey_number(text, expected):
    assert fe_jersey(text) == expected


def test_clean_text_strips_labels_and_trailers():
    assert FE.clean_text('  Class:  Junior  Full Bio') == 'Junior'


def test_clean_field_labels():
    assert FE.clean_field_labels('Hometown: Chicago, IL') == 'Chicago, IL'


def test_parse_hometown_school_domestic():
    r = FE.parse_hometown_school('Chicago, IL / Whitney Young HS')
    assert r['hometown'] == 'Chicago, IL'
    assert r['high_school'] == 'Whitney Young HS'


def test_parse_hometown_school_previous_college():
    r = FE.parse_hometown_school('Toronto, Canada / Some University')
    assert r['hometown'] == 'Toronto, Canada'
    assert r['previous_school'] == 'Some University'


def test_parse_hometown_school_plain():
    r = FE.parse_hometown_school('Berlin, Germany')
    assert r['hometown'] == 'Berlin, Germany'
    assert r['high_school'] == ''

from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_source_identity import name_relation, match_base_fingerprint


@pytest.mark.parametrize('a,b', [('Dani Carvajal','Daniel Carvajal'),
    ('Gianluigi Donnarumma','G. Donnarumma'), ('Jørgen Strand Larsen','J. Strand Larsen'),
    ('Ferdi Kadıoğlu','Ferdi Kadioğlu'), ('Adrián','Adrián San Miguel'),
    ('Joe Willock','Joseph Willock'), ('Jean-Philippe Mateta','Jean Mateta'),
    ('Jan Paul van Hecke','JP van Hecke'), ('Ben Gannon-Doak','Ben Doak')])
def test_explicit_abbreviations(a,b):
    assert name_relation(a,b)
    assert name_relation(b,a)


def test_similar_surnames_or_reused_id_are_not_identity():
    assert not name_relation('David Lopez','Diego Lopez')
    assert not name_relation('Benoit Aimee','Nicolas Jackson')
    owner=dict(base_id=7,name='A. Player',age=24,height=180,foot=0,position=1,country=42,fingerprint='locked')
    candidate=SimpleNamespace(player_id=7,name='Andrew Player')
    bio=dict(age=25,height=181,foot=0,position=2,country=42,row_sha256='source')
    assert match_base_fingerprint(owner,candidate,bio)
    for change in (dict(age=40),dict(height=195),dict(foot=1),dict(position=0),dict(country=99)):
        assert not match_base_fingerprint(owner,candidate,dict(bio,**change))
    assert not match_base_fingerprint(owner,SimpleNamespace(player_id=8,name='Andrew Player'),bio)


def test_nationality_change_needs_full_name_and_biography():
    owner=dict(base_id=7,name='Mouctar Diakhaby',age=29,height=192,foot=0,position=1,country=65,fingerprint='locked')
    candidate=SimpleNamespace(player_id=7,name=owner['name'])
    bio=dict(age=28,height=192,foot=0,position=1,country=208,row_sha256='source')
    evidence=match_base_fingerprint(owner,candidate,bio)
    assert evidence['same_country'] is False
    assert evidence['canonical_fingerprint']=='locked'

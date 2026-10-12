"""Offline repair keeps native gaps and avoids fragment-heavy triangle cuts."""
import sys
from pathlib import Path
import pytest

pytest.importorskip('shapely', minversion='2.1', reason='Offline apron repair requires local Shapely 2.1')
from shapely import Polygon, box, union_all
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from stadium_apron_geometry import repair_polygons


def test_union_preserves_native_uncovered_corner_and_floor_area():
    native=[list(box(-60,-40,60,20).exterior.coords)[:-1],
            list(box(-60,20,40,40).exterior.coords)[:-1]]
    faces={'floor':[(-70,-50),(70,-50),(70,50),(-70,50)]}
    triangles=repair_polygons(native, faces)['floor']
    actual=union_all([Polygon(t) for t in triangles])
    expected=Polygon(faces['floor']).difference(union_all([Polygon(t) for t in native]))
    assert actual.symmetric_difference(expected).area<1e-7
    assert actual.covers(box(45,25,55,35)) # native floor has no upper-right corner
    assert sum(Polygon(t).area for t in triangles)==pytest.approx(actual.area)


def test_floor_union_avoids_internal_subdivision_seams():
    native=[]
    for x in range(-60,60,5):
        for y in range(-40,40,5):
            native.extend([[(x,y),(x+5,y),(x+5,y+5)],[(x,y),(x+5,y+5),(x,y+5)]])
    faces={'crossing':[(-70,-50),(70,-50),(0,65)],'inside':[(-1,-1),(1,-1),(0,1)],
           'absent':[(80,0),(90,0),(80,10)]}
    result=repair_polygons(native,faces)
    assert result['inside']==[] and 'absent' not in result
    assert len(result['crossing'])<16 # 768 native triangles must not multiply the shell
    assert union_all([Polygon(t) for t in result['crossing']]).intersection(box(-60,-40,60,40)).area<1e-7

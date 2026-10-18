import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from audit_realface_pose_bounds import rig_globals,pose_points


def bone(name,parent=-1,translation=(0,0,0),rotation=(0,0,0,1)):
    return dict(name=name,parent=parent,trs=[*rotation,*translation,1,1,1])


def test_compensated_bind_coordinates_are_not_false_runtime_outliers():
    native=rig_globals([bone('root'),bone('head',0,(0,0,170))])
    cooked=rig_globals([bone('root',translation=(0,170,-170)),bone('head',0,(0,0,170))])
    mesh=dict(vertices=[(0,170,0),(3,170,10)],weights=[{'root':1},{'head':.5,'root':.5}])
    points=pose_points(mesh,native,cooked)
    np.testing.assert_allclose(points,[(0,0,170),(3,0,180)],atol=1e-8)


def test_rotation_child_hierarchy_and_bad_contracts():
    rig=rig_globals([bone('root',rotation=(0,0,2**-.5,2**-.5)),bone('head',0,(1,0,0))])
    np.testing.assert_allclose(rig['head'][:3,3],(0,1,0),atol=1e-8)
    with pytest.raises(ValueError,match='Singular'):
        rig_globals([bone('root',rotation=(0,0,0,0))])
    with pytest.raises(ValueError,match='Invalid reference'):
        rig_globals([bone('root',parent=0)])
    with pytest.raises(ValueError,match='skin weights'):
        pose_points(dict(vertices=[(0,0,0)],weights=[{'root':.5}]),rig,rig)
    with pytest.raises(ValueError,match='ownership'):
        pose_points(dict(vertices=[(0,0,0)],weights=[{'root':1}]),rig,{'root':rig['root']})

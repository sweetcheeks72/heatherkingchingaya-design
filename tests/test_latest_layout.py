"""Latest layout: requested clearances, usable openings and negative geometry checks."""
import copy
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('plan',ROOT/'scripts/build_floor_plan.py')
plan=importlib.util.module_from_spec(spec);spec.loader.exec_module(plan)
m=json.loads((ROOT/'assets/brand/floor-plan-model.json').read_text())
items={x['id']:x for k in ('spaces','openings','fixtures','furniture') for x in m[k]}
b=lambda id:items[id]['bounds']
assert plan.validate_model(m)[0]
sofa,table,rug=map(b,['FURN_LIVING_SECTIONAL','FURN_LIVING_COFFEE_TABLE','FURN_LIVING_RUG'])
assert table['x']-(sofa['x']+2.8)>=1.5-1e-6
assert table['y']-(sofa['y']+2.8)>=1.5-1e-6
assert abs(table['x']+table['width']/2-rug['x']-rug['width']/2)<1e-6
assert abs(table['y']+table['height']/2-rug['y']-rug['height']/2)<1e-6
assert items['OP_PANTRY_DOOR']['wall_id']=='W_INT_PANTRY_S'
assert b('FIX_KITCHEN_COUNTER_W')['y']+b('FIX_KITCHEN_COUNTER_W')['height']==9.5
assert all(items[id]['type']=='pocket_door' for id in ('OP_COAT_DOOR','OP_LAUNDRY_DOOR'))
assert items['OP_WIN_PRIMARY_BATH_N']['wall_id']=='W_EXT_N'
assert items['OP_LIVING_COURT_SLIDER']['width_ft']/24>.9
assert b('second_guest_bedroom')['width']==13 and b('laundry_utility')['width']==7.5
assert all(items[id]['rotation_deg']==180 for id in ('FURN_GUEST_BED','FURN_GUEST2_BED'))
assert b('FIX_GUEST_CLOSET')['width']==b('guest_bedroom')['width']
assert b('FIX_GUEST_CLOSET')['y']==b('guest_bedroom')['y']
assert 'FURN_GUEST_DESK' not in items
assert all(b(id)['y']>48.5 for id in ('FURN_SITTING_CHAIR_1','FURN_SITTING_CHAIR_2'))
bad=copy.deepcopy(m)
next(x for x in bad['furniture'] if x['id']=='FURN_LIVING_COFFEE_TABLE')['bounds']['x']-=.25
assert any('18 inches' in e for e in plan.validate_model(bad)[1])
bad=copy.deepcopy(m)
next(x for x in bad['openings'] if x['id']=='OP_COAT_DOOR')['offset_ft']=2
assert any('retract completely' in e for e in plan.validate_model(bad)[1])
print('PASS: latest layout, 18-inch clearance, centered rug, pocket lengths, guest storage and negative geometry checks')

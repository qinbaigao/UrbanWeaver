"""Bounded rooftop briefs: agent/authored overrides with an offline default."""
import hashlib

PROFILES={'quiet','mechanical','solar','garden','mixed'}


def roof_seed(key):
    return int.from_bytes(hashlib.blake2b(key.encode(),digest_size=4).digest(),'big')


def roof_profile(building):
    explicit=building.metadata.get('roof_program',{}).get('profile')
    if explicit:
        if explicit not in PROFILES:raise ValueError(f'Unknown roof profile: {explicit}')
        return explicit
    seed=roof_seed(building.id)
    if len(building.floors)>=12:
        choices=['mechanical','mechanical','mixed','solar','quiet']
    elif building.function=='residential':
        choices=['quiet','quiet','solar','solar','garden','mixed']
    elif building.function=='public_service':
        choices=['solar','garden','mixed','quiet','mechanical']
    else:
        choices=['mechanical','mechanical','mixed','solar','quiet','garden']
    return choices[seed%len(choices)]


def zone_brief(profile, area, lower=False):
    kinds={'quiet':['equipment'], 'mechanical':['equipment','equipment','equipment'],
           'solar':['solar','solar','equipment'], 'garden':['garden','terrace','equipment'],
           'mixed':['equipment','solar','garden']}[profile]
    if profile=='mixed' and lower:kinds=['garden','terrace','equipment']
    if area<100:return ['equipment']
    if area<300:return kinds[:1]
    if area>1100 and profile!='quiet':return kinds+[kinds[0]]
    return kinds

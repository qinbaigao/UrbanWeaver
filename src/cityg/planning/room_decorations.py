"""Bounded decoration requests, separate from occupant/furniture inventory."""
import re


def validate_decorations(requests):
    if not isinstance(requests, list) or len(requests) > 12:
        raise ValueError('Room decorations must be a list of at most 12 requests')
    seen = set()
    for request in requests:
        if not isinstance(request, dict):
            raise ValueError('Invalid decoration request')
        kind = request.get('kind')
        keys = {'id', 'kind', 'asset_id'}
        keys |= {'anchor_member_id'} if kind == 'rug' else {'walls'}
        if kind not in {'floor_asset', 'wall_asset', 'rug'} or set(request) != keys:
            raise ValueError('Unsupported decoration kind or fields')
        name = request['id']
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,47}', name) or name in seen:
            raise ValueError('Decoration IDs must be safe and unique within the room')
        seen.add(name)
        if not isinstance(request['asset_id'], str) or not request['asset_id']:
            raise ValueError('Decorations require a pinned asset ID')
        if kind == 'rug':
            if not isinstance(request['anchor_member_id'], str) or not request['anchor_member_id']:
                raise ValueError('Rug requires a furniture member anchor')
        elif (not isinstance(request['walls'], list) or not request['walls']
              or len(request['walls']) > 4 or len(set(request['walls'])) != len(request['walls'])
              or any(s not in {'north','south','east','west'} for s in request['walls'])):
            raise ValueError('Decoration wall preferences must be unique cardinal sides')

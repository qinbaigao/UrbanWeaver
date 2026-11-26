"""Size-aware outdoor briefs; geometry remains the final placement authority."""

SIZES = {'garden': (16., 10.), 'terrace': (16., 10.),
         'arrival': (13., 9.), 'cycle': (13., 9.), 'kiosk': (13., 9.),
         'grove': (26., 20.), 'pavilion': (26., 18.), 'promenade': (30., 18.),
         'pocket': (8., 6.)}
PROGRAMS = {
    'residential': ['garden', 'cycle', 'arrival', 'garden'],
    'commercial': ['terrace', 'arrival', 'cycle', 'terrace'],
    'civic': ['arrival', 'garden', 'terrace', 'cycle'],
    'mixed_use': ['terrace', 'cycle', 'kiosk', 'garden'],
}


def citywide_programs(city):
    """Include every ordinary parcel, retaining explicitly reserved worksites."""
    reserved = {r['parcel_id'] for r in city.metadata.get('construction_sites', {}).get('sites', [])}
    result = {}
    for district in city.districts:
        for parcel in district.parcels:
            if parcel.id in reserved:
                continue
            function = parcel.buildings[0].function if parcel.buildings else district.function
            theme = {'public_service': 'civic'}.get(function, function)
            result[parcel.id] = {'theme': theme if theme in PROGRAMS else 'mixed_use',
                                 'adaptive': True}
    return result


def adaptive_features(theme, free_area, seed):
    """Large assemblies only on spacious sites, never scaled-up street furniture.

    This area test is an initial brief, not a fit test. The compiler checks the
    complete oriented envelope and pedestrian access, then falls back in size.
    """
    basic = list(PROGRAMS[theme])
    if free_area < 500:
        return ['pocket', 'pocket']
    if free_area < 1800:
        return basic[:3] + ['pocket']
    large = {'residential': ['grove', 'pavilion'],
             'commercial': ['pavilion', 'promenade'],
             'civic': ['promenade', 'grove'],
             'mixed_use': ['pavilion', 'grove']}[theme]
    first = large[seed % len(large)]
    if free_area < 4000:
        return [first, *basic, 'pocket']
    return [first, large[(seed+1) % len(large)], *basic, 'kiosk', 'pocket']


def feature_fallbacks(kind):
    return {'grove': ['grove', 'garden', 'pocket'],
            'pavilion': ['pavilion', 'kiosk', 'pocket'],
            'promenade': ['promenade', 'arrival', 'pocket']}.get(kind, [kind, 'pocket'] if kind != 'pocket' else [kind])

"""Camera-background policy; leave authored city geometry and world light alone."""

DISPLAY_BACKDROPS = ('distant_land_backdrop', 'asset_instances_distant_land')


def configure_background(scene, transparent=False):
    scene.render.film_transparent = transparent
    scene.render.image_settings.color_mode = 'RGBA' if transparent else 'RGB'
    hidden = []
    for name in DISPLAY_BACKDROPS:
        obj = scene.objects.get(name)
        if obj is not None:
            obj.hide_render = transparent
            if transparent:
                hidden.append(name)
    return {'transparent': transparent, 'color_mode': scene.render.image_settings.color_mode,
            'hidden_display_backdrops': hidden, 'world_lighting_preserved': True}

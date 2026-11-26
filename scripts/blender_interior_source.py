"""Inspect/export explicitly selected meshes from a downloaded Blender source.

Run with Blender --background --factory-startup --disable-autoexec. Source files
are never saved. Exported glTF remains a candidate, not an approved runtime asset.
"""
import argparse
import json
from pathlib import Path
import sys

import bpy


def bake_materials(objects, output_dir, resolution):
    """Bake shader-node composition, not a heuristic choice of an image input.

    Poly Haven books compose covers, page textures and wear through node groups.
    glTF's automatic graph traversal otherwise mistakes a mask for base color.
    CPU Cycles makes the static appearance portable without executing scripts.
    """
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 1
    scene.render.bake.use_clear = True
    scene.render.bake.margin = 8
    baked_objects = []
    for original in objects:
        bpy.ops.object.select_all(action="DESELECT")
        original.hide_set(False); original.hide_viewport = False; original.select_set(True)
        bpy.context.view_layer.objects.active = original
        bpy.ops.object.convert(target="MESH")
        obj = bpy.context.view_layer.objects.active
        if len(obj.data.materials) != 1 or not obj.data.uv_layers:
            raise ValueError(f"Baking requires one material and authored UVs: {obj.name}")
        obj.data.uv_layers.active_index = 0
        obj.data.uv_layers[0].active_render = True
        material = obj.data.materials[0].copy()
        obj.data.materials[0] = material
        tree = material.node_tree
        shaders = [n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"]
        outputs = [n for n in tree.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output]
        if len(shaders) != 1 or len(outputs) != 1:
            raise ValueError(f"Ambiguous material graph: {obj.name}")
        shader, surface = shaders[0], outputs[0].inputs["Surface"]
        old_output = surface.links[0].from_socket
        emission = tree.nodes.new("ShaderNodeEmission")
        image_node = tree.nodes.new("ShaderNodeTexImage")
        tree.nodes.active = image_node
        images = {}
        for label, socket_name in (("color", "Base Color"), ("roughness", "Roughness"), ("normal", None)):
            image = bpy.data.images.new(f"{obj.name}_{label}", width=resolution, height=resolution, alpha=False)
            image.colorspace_settings.name = "sRGB" if label == "color" else "Non-Color"
            image_node.image = image
            if socket_name:
                source = shader.inputs[socket_name]
                for link in list(emission.inputs["Color"].links): tree.links.remove(link)
                if source.is_linked:
                    tree.links.new(source.links[0].from_socket, emission.inputs["Color"])
                else:
                    value = source.default_value
                    emission.inputs["Color"].default_value = (value, value, value, 1) if isinstance(value, float) else value
                tree.links.new(emission.outputs[0], surface)
                bpy.ops.object.bake(type="EMIT")
            else:
                tree.links.new(old_output, surface)
                bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT")
            image.filepath_raw = str(output_dir/f"{obj.name}_{label}.png")
            image.file_format = "PNG"
            image.save()
            images[label] = image
        portable = bpy.data.materials.new(f"{obj.name}_baked")
        portable.use_nodes = True
        nodes, links = portable.node_tree.nodes, portable.node_tree.links
        principled = nodes.get("Principled BSDF")
        for label, socket_name in (("color", "Base Color"), ("roughness", "Roughness"), ("normal", "Normal")):
            texture = nodes.new("ShaderNodeTexImage"); texture.image = images[label]
            value = texture.outputs["Color"]
            if label == "normal":
                normal = nodes.new("ShaderNodeNormalMap")
                links.new(value, normal.inputs["Color"]); value = normal.outputs["Normal"]
            links.new(value, principled.inputs[socket_name])
        obj.data.materials[0] = portable
        baked_objects.append(obj)
        print("Baked authored material:", obj.name, flush=True)
    return baked_objects


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--object", action="append", default=[])
    parser.add_argument("--bake-materials", action="store_true")
    parser.add_argument("--resolution", type=int, default=1024)
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    source = args.source.resolve()
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    meshes = sorted((o for o in bpy.data.objects if o.type == "MESH"), key=lambda o: o.name)
    if not args.object:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({"source": str(source), "objects": [
            {"name": o.name, "dimensions": list(o.dimensions), "polygons": len(o.data.polygons),
             "materials": [m.name if m else None for m in o.data.materials],
             "modifiers": [m.type for m in o.modifiers]} for o in meshes]}, indent=2))
        return
    selected = [o for o in meshes if o.name in args.object]
    if len(selected) != len(set(args.object)):
        raise ValueError("Unknown/duplicate source object selection")
    for image in bpy.data.images:
        if image.source == "FILE" and not image.packed_file and image.filepath:
            path = Path(bpy.path.abspath(image.filepath)).resolve()
            if not path.is_relative_to(source.parent) or not path.is_file():
                raise ValueError(f"Unresolved or out-of-bundle image: {image.name}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.bake_materials:
        selected = bake_materials(selected, args.output.parent, args.resolution)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in selected:
        obj.hide_set(False); obj.hide_viewport = False; obj.select_set(True)
    bpy.context.view_layer.objects.active = selected[0]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(args.output.resolve()), export_format="GLTF_SEPARATE",
        use_selection=True, export_apply=True, export_yup=True, export_animations=False,
        export_cameras=False, export_lights=False)


if __name__ == "__main__":
    main()

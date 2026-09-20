"""Convert a validated glTF intermediate to an Unreal-oriented FBX.

Run this file with Blender, not the system Python::

    blender.exe --background --python tools/blender_export_ue_fbx.py -- \
        --input face_high.gltf --output face_high.fbx

The glTF is expected to use metres numerically as centimetres and the standard
Y-up glTF coordinate system. Blender converts that to Z-up; a scene unit scale
of 0.01 then tells the FBX exporter and Unreal that one numeric unit is 1 cm.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector


def parse_args() -> argparse.Namespace:
    try:
        separator = sys.argv.index("--")
    except ValueError as error:
        raise SystemExit("Blender arguments must follow --") from error
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument(
        "--additional-input",
        action="append",
        default=[],
        type=Path,
        help="Additional compatible glTF whose skinned meshes join the primary rig",
    )
    parser.add_argument(
        "--include-material",
        action="append",
        default=[],
        help=(
            "Only export skinned meshes using one of these material names; "
            "repeat for multiple materials"
        ),
    )
    parser.add_argument(
        "--include-mesh",
        action="append",
        default=[],
        help="Only export skinned meshes with one of these object names; repeat as needed",
    )
    parser.add_argument(
        "--flip-faces",
        action="store_true",
        help="Reverse polygon winding (use --recompute-normals for custom normals)",
    )
    parser.add_argument(
        "--recompute-normals",
        action="store_true",
        help="Rebuild smooth shading normals from the final polygon winding",
    )
    parser.add_argument(
        "--rotate-z-degrees",
        default=0.0,
        type=float,
        help="Rotate selected mesh geometry around the target pivot bone",
    )
    parser.add_argument(
        "--rotation-pivot-bone",
        default="sk_head",
        help="Armature bone used as the geometry-rotation pivot",
    )
    parser.add_argument(
        "--fit-island", action="append", nargs=8, default=[],
        metavar=("MATERIAL", "SORT_AXIS", "INDEX", "SCALE", "DX", "DY", "DZ", "COUNT"),
        help=("Fit one connected component of a single-material mesh after rotation; "
              "sort components by world X/Y/Z center, use a zero-based index, "
              "uniform scale and centimetre translation, and assert component COUNT"),
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--runtime-bind-reference", nargs=2, type=Path,
                        metavar=("NATIVE_RIG", "COOKED_RIG"),
                        help="Compensate native follower skinning using audited cooked rig JSONs instead of a rigid geometry rotation")
    parser.add_argument("--runtime-mirror-x", action="store_true",
                        help="Preserve the established runtime left/right convention when compensating the bind pose")
    parser.add_argument("--tuck-lower-neck", action="store_true",
                        help="Inset only the lower chest flare of the small skin/neck mesh beneath the shirt collar")
    parser.add_argument("--lower-chest-cm", type=float, default=0.0,
                        help="Lower the chest attachment smoothly without narrowing the neck")
    return parser.parse_args(sys.argv[separator + 1 :])


def rig_globals(bones):
    result = {}
    ordered = []
    for i, bone in enumerate(bones):
        parent, values = bone["parent"], bone["trs"]
        if not -1 <= parent < i or len(values) != 10 or not all(math.isfinite(v) for v in values):
            raise ValueError("Invalid audited reference skeleton")
        if bone["name"] in result:
            raise ValueError("Duplicate reference bone")
        x, y, z, w = values[:4]
        matrix = Matrix.LocRotScale(Vector(values[4:7]), Quaternion((w, x, y, z)), Vector(values[7:10]))
        if parent >= 0:
            matrix = ordered[parent] @ matrix
        ordered.append(matrix)
        result[bone["name"]] = matrix
    return result


def compensate_runtime_bind(obj, native, cooked, mirror_x=False):
    """Solve weighted follower skinning, not a rigid rotation of the neck.

    Input vertices are native desired rest positions in centimetres. This
    pipeline's FBX import reflects Blender Y in cooked position buffers.
    Solve (sum w * native_global * cooked_global^-1) * cooked_position
    = desired_position per vertex. Audit the cooked rig again after import.
    """
    if obj.data.shape_keys or native.keys() != cooked.keys():
        raise ValueError("Runtime bind compensation requires matching rigs and no shape keys")
    transforms = {name: native[name] @ cooked[name].inverted() for name in native}
    reflect = Matrix.Diagonal((1.0, -1.0, 1.0, 1.0))
    inverse_world = obj.matrix_world.inverted()
    maximum_error = 0.0
    for vertex in obj.data.vertices:
        memberships = [(obj.vertex_groups[g.group].name, g.weight) for g in vertex.groups if g.weight > 0]
        total = sum(weight for _, weight in memberships)
        if total <= 0 or any(name not in transforms for name, _ in memberships):
            raise ValueError("Vertex has missing or unmapped skin weights")
        blended = Matrix([[sum(transforms[name][r][c] * weight / total for name, weight in memberships)
                           for c in range(4)] for r in range(4)])
        desired = obj.matrix_world @ vertex.co
        if mirror_x:
            desired.x = -desired.x
        cooked_position = blended.inverted() @ desired
        maximum_error = max(maximum_error, (blended @ cooked_position - desired).length)
        vertex.co = inverse_world @ (reflect @ cooked_position)
    obj.data.update()
    return {"vertices": len(obj.data.vertices), "max_reconstructed_error_cm": maximum_error}


def tuck_lower_neck(obj, center_y=5.43, bottom_z=154.0, top_z=161.0, scale=0.52):
    """Smoothly narrow the donor's chest flare; retain eye socket and upper neck."""
    if not 0 < scale <= 1 or not bottom_z < top_z or obj.data.shape_keys:
        raise ValueError("Invalid lower-neck inset")
    inverse = obj.matrix_world.inverted()
    changed = 0
    for vertex in obj.data.vertices:
        point = obj.matrix_world @ vertex.co
        if point.z >= top_z:
            continue
        t = max(0.0, min(1.0, (top_z - point.z) / (top_z - bottom_z)))
        t = t * t * (3.0 - 2.0 * t)
        factor = 1.0 - (1.0 - scale) * t
        point.x *= factor
        point.y = center_y + (point.y - center_y) * factor
        vertex.co = inverse @ point
        changed += 1
    obj.data.update()
    return {"vertices": changed, "bottom_z_cm": bottom_z,
            "top_z_cm": top_z, "scale": scale}


def lower_chest_attachment(obj, distance, bottom_z=154.0, top_z=161.0):
    """Move the chest below the collar while preserving neck circumference."""
    if not math.isfinite(distance) or not 0 < distance <= 3 or obj.data.shape_keys:
        raise ValueError("Chest lowering requires a finite distance in (0, 3] cm")
    inverse = obj.matrix_world.inverted()
    changed = 0
    for vertex in obj.data.vertices:
        point = obj.matrix_world @ vertex.co
        if point.z >= top_z:
            continue
        t = max(0.0, min(1.0, (top_z - point.z) / (top_z - bottom_z)))
        point.z -= distance * t * t * (3.0 - 2.0 * t)
        vertex.co = inverse @ point
        changed += 1
    obj.data.update()
    return {"vertices": changed, "lower_cm": distance,
            "bottom_z_cm": bottom_z, "top_z_cm": top_z}


def fit_mesh_island(obj, axis: str, index: int, scale: float, offset, count: int):
    """Fit exactly one component; leave UVs, normals, skin weights and peers intact."""
    if axis not in ("X", "Y", "Z"):
        raise ValueError("Island sort axis must be X, Y or Z")
    if len(offset) != 3 or not all(math.isfinite(v) for v in (scale, *offset)) or scale <= 0:
        raise ValueError("Island fit requires a positive finite scale and finite XYZ offset")
    if obj.data.shape_keys:
        raise ValueError("Cannot fit islands on a mesh with shape keys")
    adjacent = {v.index: set() for v in obj.data.vertices}
    for edge in obj.data.edges:
        a, b = edge.vertices
        adjacent[a].add(b)
        adjacent[b].add(a)
    unseen = set(adjacent)
    islands = []
    while unseen:
        pending = [unseen.pop()]
        island = []
        while pending:
            vertex = pending.pop()
            island.append(vertex)
            for neighbor in adjacent[vertex]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    pending.append(neighbor)
        islands.append(island)
    if len(islands) != count or not 0 <= index < count:
        raise ValueError(f"Island count/index mismatch: actual={len(islands)}, expected={count}, index={index}")
    points = [obj.matrix_world @ v.co for v in obj.data.vertices]
    def center(island):
        return Vector([(min(points[i][k] for i in island) + max(points[i][k] for i in island)) / 2 for k in range(3)])
    islands.sort(key=lambda island: center(island)["XYZ".index(axis)])
    selected = islands[index]
    pivot = center(selected)
    inverse = obj.matrix_world.inverted()
    for i in selected:
        obj.data.vertices[i].co = inverse @ (pivot + (points[i] - pivot) * scale + Vector(offset))
    obj.data.update()
    return {"vertices": len(selected), "center_cm": list(pivot), "scale": scale,
            "offset_cm": list(offset), "index": index, "sort_axis": axis, "count": count}


def rebuild_smooth_normals(obj) -> None:
    """Discard stale custom normals while preserving topology, UVs and skinning.

    Replacing an object's mesh also clears its vertex groups in Blender, so
    preserve group names and memberships explicitly, including unused groups.
    This is for the static bind-pose intermediates, not morph-target assets.
    """
    old = obj.data
    if old.shape_keys:
        raise ValueError("Cannot rebuild normals on a mesh with shape keys")
    group_names = [group.name for group in obj.vertex_groups]
    weights = [[(g.group, g.weight) for g in v.groups] for v in old.vertices]
    rebuilt = bpy.data.meshes.new(old.name + "_smooth")
    rebuilt.from_pydata(
        [tuple(v.co) for v in old.vertices], [],
        [tuple(p.vertices) for p in old.polygons],
    )
    for material in old.materials:
        rebuilt.materials.append(material)
    for before, after in zip(old.polygons, rebuilt.polygons):
        after.material_index = before.material_index
        after.use_smooth = True
    for layer in old.uv_layers:
        target = rebuilt.uv_layers.new(name=layer.name)
        for before, after in zip(layer.data, target.data):
            after.uv = before.uv
    rebuilt.uv_layers.active_index = old.uv_layers.active_index
    obj.data = rebuilt
    obj.vertex_groups.clear()
    for name in group_names:
        obj.vertex_groups.new(name=name)
    for index, groups in enumerate(weights):
        for group, weight in groups:
            obj.vertex_groups[group].add([index], weight, "REPLACE")
    rebuilt.update()


def main() -> int:
    args = parse_args()
    source = args.input.resolve()
    additional_sources = [path.resolve() for path in args.additional_input]
    output = args.output.resolve()
    report = (args.report or output.with_suffix(".fbx.json")).resolve()
    if not source.is_file() or source.suffix.casefold() != ".gltf":
        raise FileNotFoundError(f"validated .gltf input not found: {source}")
    for additional_source in additional_sources:
        if not additional_source.is_file() or additional_source.suffix.casefold() != ".gltf":
            raise FileNotFoundError(
                f"validated additional .gltf input not found: {additional_source}"
            )
    if output.suffix.casefold() != ".fbx":
        raise ValueError("--output must end in .fbx")
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.length_unit = "METERS"
    bpy.context.scene.unit_settings.scale_length = 1.0
    bpy.ops.import_scene.gltf(filepath=str(source), import_pack_images=False)
    # glTF numeric coordinates were deliberately authored in centimetres.
    # Import while Blender is at 1 metre/unit so it does not rescale them,
    # then describe the same numeric values as centimetres for FBX/Unreal.
    primary_armatures = [
        obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"
    ]
    if len(primary_armatures) != 1:
        raise RuntimeError(
            f"primary glTF expected one armature, found {len(primary_armatures)}"
        )
    primary_armature = primary_armatures[0]
    primary_bones = [bone.name for bone in primary_armature.data.bones]
    for additional_source in additional_sources:
        existing = set(bpy.context.scene.objects)
        bpy.ops.import_scene.gltf(
            filepath=str(additional_source), import_pack_images=False
        )
        imported = [obj for obj in bpy.context.scene.objects if obj not in existing]
        imported_armatures = [obj for obj in imported if obj.type == "ARMATURE"]
        if len(imported_armatures) != 1:
            raise RuntimeError(
                f"{additional_source} expected one armature, found "
                f"{len(imported_armatures)}"
            )
        imported_armature = imported_armatures[0]
        if [bone.name for bone in imported_armature.data.bones] != primary_bones:
            raise RuntimeError(
                f"{additional_source} skeleton differs from primary input"
            )
        for obj in imported:
            if obj.type != "MESH":
                continue
            for modifier in obj.modifiers:
                if modifier.type == "ARMATURE" and modifier.object == imported_armature:
                    modifier.object = primary_armature
            if obj.parent == imported_armature:
                world = obj.matrix_world.copy()
                obj.parent = primary_armature
                obj.matrix_world = world
        bpy.data.objects.remove(imported_armature, do_unlink=True)

    bpy.context.scene.unit_settings.length_unit = "CENTIMETERS"
    bpy.context.scene.unit_settings.scale_length = 0.01

    all_meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    included_materials = set(args.include_material)
    included_meshes = set(args.include_mesh)
    meshes = sorted(
        (
            obj
            for obj in all_meshes
            if obj.vertex_groups
            and any(modifier.type == "ARMATURE" for modifier in obj.modifiers)
            and (not included_meshes or obj.name in included_meshes)
            and (
                not included_materials
                or any(slot.name in included_materials for slot in obj.data.materials)
            )
        ),
        key=lambda obj: obj.name,
    )
    armatures = sorted(
        (obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"),
        key=lambda obj: obj.name,
    )
    if not meshes:
        raise RuntimeError("glTF import produced no skinned mesh objects")
    if len(armatures) != 1:
        raise RuntimeError(f"expected one armature, found {len(armatures)}")
    armature = armatures[0]
    neck_report = None
    if args.tuck_lower_neck and args.lower_chest_cm:
        raise ValueError("Choose neck inset or chest lowering, not both")
    if args.tuck_lower_neck or args.lower_chest_cm:
        targets = [obj for obj in meshes if len(obj.data.vertices) == 236
                   and [material.name for material in obj.data.materials] == ["fox_skin_mat"]]
        if len(targets) != 1:
            raise ValueError("Lower-neck inset requires the audited 236-vertex mesh")
        neck_report = (lower_chest_attachment(targets[0], args.lower_chest_cm)
                       if args.lower_chest_cm else tuck_lower_neck(targets[0]))
    if args.runtime_bind_reference and args.rotate_z_degrees:
        raise ValueError("Runtime bind compensation replaces rigid geometry rotation")
    if args.runtime_mirror_x and not args.runtime_bind_reference:
        raise ValueError("Runtime mirror convention requires audited bind references")
    bind_report = []
    if args.runtime_bind_reference:
        native, cooked = [rig_globals(json.loads(path.read_text())) for path in args.runtime_bind_reference]
        for obj in meshes:
            bind_report.append({"mesh": obj.name, **compensate_runtime_bind(obj, native, cooked, args.runtime_mirror_x)})
    if args.rotate_z_degrees:
        pivot_bone = armature.data.bones.get(args.rotation_pivot_bone)
        if pivot_bone is None:
            raise RuntimeError(
                f"rotation pivot bone not found: {args.rotation_pivot_bone}"
            )
        pivot = pivot_bone.matrix_local.translation
        transform = (
            Matrix.Translation(pivot)
            @ Matrix.Rotation(args.rotate_z_degrees * 0.017453292519943295, 4, "Z")
            @ Matrix.Translation(-pivot)
        )
        for obj in meshes:
            obj.data.transform(transform)
            obj.data.update()
    island_fits = []
    for material, axis, index, scale, dx, dy, dz, count in args.fit_island:
        targets = [obj for obj in meshes if any(slot.name == material for slot in obj.data.materials)]
        if len(targets) != 1 or len(targets[0].data.materials) != 1:
            raise ValueError(f"Island fit requires exactly one single-material mesh: {material}")
        fit = fit_mesh_island(targets[0], axis, int(index), float(scale),
                              [float(dx), float(dy), float(dz)], int(count))
        island_fits.append({"material": material, **fit})
    if args.flip_faces:
        for obj in meshes:
            obj.data.flip_normals()
    if args.recompute_normals:
        for obj in meshes:
            rebuild_smooth_normals(obj)
    # UE4.22 strips Blender's synthetic armature node only when it is named
    # "Armature". A custom name becomes an unwanted 30th root bone.
    armature.name = "Armature"
    armature.data.name = "Armature"
    armature_name = armature.name
    discarded_helper_meshes = sorted(obj.name for obj in all_meshes if obj not in meshes)

    for obj in bpy.context.scene.objects:
        obj.select_set(obj == armature or obj in meshes)
    bpy.context.view_layer.objects.active = armature
    result = bpy.ops.export_scene.fbx(
        filepath=str(output),
        check_existing=False,
        use_selection=True,
        global_scale=1.0,
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        use_space_transform=True,
        bake_space_transform=False,
        object_types={"ARMATURE", "MESH"},
        use_mesh_modifiers=True,
        use_mesh_modifiers_render=True,
        mesh_smooth_type="OFF",
        use_subsurf=False,
        use_mesh_edges=False,
        use_tspace=True,
        use_custom_props=True,
        add_leaf_bones=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        use_armature_deform_only=False,
        armature_nodetype="NULL",
        bake_anim=False,
        path_mode="COPY",
        embed_textures=True,
        batch_mode="OFF",
        axis_forward="-Y",
        axis_up="Z",
    )
    if "FINISHED" not in result or not output.is_file():
        raise RuntimeError(f"FBX export failed: {result}")

    def mesh_summary(obj):
        coordinates = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
        minimum = [min(point[axis] for point in coordinates) for axis in range(3)]
        maximum = [max(point[axis] for point in coordinates) for axis in range(3)]
        obj.data.calc_loop_triangles()
        opposed = sum(
            sum(obj.data.corner_normals[i].vector.dot(tri.normal) for i in tri.loops) < 0
            for tri in obj.data.loop_triangles
        )
        return {
            "name": obj.name,
            "vertices": len(obj.data.vertices),
            "polygons": len(obj.data.polygons),
            "materials": [slot.name for slot in obj.data.materials],
            "vertex_groups": len(obj.vertex_groups),
            "bounds_cm": {"min": minimum, "max": maximum},
            "opposed_shading_normals": opposed,
        }

    expected_meshes = [mesh_summary(obj) for obj in meshes]
    expected_bones = [bone.name for bone in armature.data.bones]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.length_unit = "CENTIMETERS"
    bpy.context.scene.unit_settings.scale_length = 0.01
    bpy.ops.import_scene.fbx(filepath=str(output), use_anim=False)
    imported_armatures = [
        obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"
    ]
    imported_meshes = sorted(
        (
            obj
            for obj in bpy.context.scene.objects
            if obj.type == "MESH"
            and obj.vertex_groups
            and any(modifier.type == "ARMATURE" for modifier in obj.modifiers)
        ),
        key=lambda obj: obj.name,
    )
    if len(imported_armatures) != 1:
        raise RuntimeError(
            f"FBX round-trip expected one armature, found {len(imported_armatures)}"
        )
    imported_bones = [bone.name for bone in imported_armatures[0].data.bones]
    if imported_bones != expected_bones:
        raise RuntimeError("FBX round-trip changed the target skeleton")
    roundtrip_meshes = [mesh_summary(obj) for obj in imported_meshes]
    if [mesh["vertices"] for mesh in roundtrip_meshes] != [
        mesh["vertices"] for mesh in expected_meshes
    ]:
        raise RuntimeError("FBX round-trip changed mesh vertex counts")
    if args.recompute_normals and any(
        mesh["opposed_shading_normals"] > max(2, mesh["polygons"] // 100)
        for mesh in roundtrip_meshes
    ):
        raise RuntimeError(
            "FBX round-trip retained opposed shading normals: "
            + json.dumps({"before": expected_meshes, "after": roundtrip_meshes})
        )

    payload = {
        "input": str(source),
        "additional_inputs": [str(path) for path in additional_sources],
        "included_materials": sorted(included_materials),
        "included_meshes": sorted(included_meshes),
        "flipped_faces": args.flip_faces,
        "recomputed_normals": args.recompute_normals,
        "rotation_z_degrees": args.rotate_z_degrees,
        "rotation_pivot_bone": args.rotation_pivot_bone,
        "island_fits": island_fits,
        "runtime_bind_compensation": bind_report,
        "runtime_mirror_x": args.runtime_mirror_x,
        "lower_neck_inset": neck_report,
        "output": str(output),
        "output_bytes": output.stat().st_size,
        "scene_unit_scale": bpy.context.scene.unit_settings.scale_length,
        "armature": armature_name,
        "bones": expected_bones,
        "meshes": expected_meshes,
        "discarded_helper_meshes": discarded_helper_meshes,
        "roundtrip": {
            "armatures": len(imported_armatures),
            "bones": len(imported_bones),
            "meshes": roundtrip_meshes,
        },
    }
    report.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Flatten primary diffuse hair/accessory atlases for the native mobile shader.

This is an explicit approximation policy, not a port of the PC Hair2 shader.
Preserve primary albedo/alpha, UV tiling and HairColor. Secondary atlas blending,
PC specular/normal/translucency effects are excluded and recorded. Mesh positions,
topology and weights are untouched. Every input texture belongs to this player.
"""
from __future__ import annotations
import copy
import math
from pathlib import Path

from PIL import Image


def primary_role(material):
    textures = dict(material.textures)
    base = textures.get('Base_Tex_SRGB')
    name = Path(base.filename).stem.lower() if base else ''
    hair = material.technique.startswith('pes3DDF_Hair')
    accessory = material.technique == 'pes3DDF_Skin_Face' and name.startswith(('hair_', 'cap_'))
    return base if hair or accessory else None


def build_atlas(models, textures, output):
    groups, audit = {}, []
    for model in models.values():
        for mesh in model.meshes:
            material = mesh.materialInstance
            base = primary_role(material)
            if not base:
                continue
            params = dict(material.parameters)
            tint = tuple(params.get('HairColor', (1, 1, 1, 1)))
            if len(tint) != 4 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in tint):
                raise ValueError('Unsupported source hair tint')
            name = Path(base.filename).stem + '.png'
            path = textures / name
            uv_channel = 0
            if not path.is_file():
                secondary = dict(material.textures).get('Base_Tex_2_SRGB')
                alternative = textures / (Path(secondary.filename).stem + '.png') if secondary else None
                if (not material.technique.startswith('pes3DDF_Hair2') or
                        alternative is None or not alternative.is_file() or
                        any(len(v.uv)!=2 for v in mesh.vertices)):
                    raise ValueError('Missing primary hair/accessory texture: ' + name)
                # The explicit second diffuse belongs to the same source
                # material and uses its second UV set. Never borrow another
                # player's texture or apply this atlas to the missing UV0 map.
                path=alternative;name=path.name;uv_channel=1
            key = (name, tint, uv_channel)
            row = groups.setdefault(key, dict(path=path, meshes=[], tint=tint,uv_channel=uv_channel))
            row['meshes'].append(mesh)
    if not groups:
        return None, []
    # Equal-size horizontal cells allow deterministic affine UV remapping. Each
    # cell repeats its own image across the actual integer UV extent, so UVs
    # crossing a wrap seam remain continuous rather than wrapping each vertex.
    width_cells = 0
    height_cells = 1
    for row in groups.values():
        uv = [v.uv[row['uv_channel']] for mesh in row['meshes'] for v in mesh.vertices]
        if any(not math.isfinite(c) for v in uv for c in (v.u,v.v)):
            raise ValueError('Non-finite hair UV')
        bounds = [math.floor(min(v.u for v in uv)), math.floor(min(v.v for v in uv)),
                  math.ceil(max(v.u for v in uv)), math.ceil(max(v.v for v in uv))]
        if bounds[2] <= bounds[0]: bounds[2] = bounds[0] + 1
        if bounds[3] <= bounds[1]: bounds[3] = bounds[1] + 1
        w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
        if w > 4 or h > 4:
            raise ValueError('Hair UV repeat exceeds supported atlas extent')
        row.update(bounds=bounds, column=width_cells, columns=w, rows=h)
        width_cells += w
        height_cells = max(height_cells, h)
    if width_cells > 8:
        raise ValueError('Hair atlas requires more than eight source tiles')
    cell = 256
    width = 1 << (width_cells * cell - 1).bit_length()
    height = 1 << (height_cells * cell - 1).bit_length()
    atlas = Image.new('RGBA', (width, height))
    changed_materials = set()
    changed_vertices = {}
    for row in groups.values():
        with Image.open(row['path']) as source:
            tile = source.convert('RGBA').resize((cell, cell), Image.Resampling.LANCZOS)
        if row['tint'] != (1, 1, 1, 1):
            bands = [channel.point([round(v * factor) for v in range(256)])
                     for channel, factor in zip(tile.split(), row['tint'])]
            tile = Image.merge('RGBA', bands)
        for y in range(row['rows']):
            for x in range(row['columns']):
                atlas.paste(tile, ((row['column'] + x) * cell, y * cell))
        for mesh in row['meshes']:
            # FMDL V and image row both increase downward in the intermediate.
            for vertex in mesh.vertices:
                if id(vertex) in changed_vertices:
                    if changed_vertices[id(vertex)] is not row:
                        raise ValueError('Shared source vertex requires conflicting atlas mappings')
                    continue
                changed_vertices[id(vertex)] = row
                old = vertex.uv[row['uv_channel']]
                new = copy.copy(old)
                new.u = (old.u - row['bounds'][0] + row['column']) * cell / width
                new.v = (old.v - row['bounds'][1]) * cell / height
                vertex.uv = [new, *vertex.uv[1:]]
            material = mesh.materialInstance
            if id(material) in changed_materials:
                continue
            changed_materials.add(id(material))
            prior = dict(material.textures)
            audit.append(dict(material=material.name, technique=material.technique,
                              primary_texture=prior['Base_Tex_SRGB'].filename,
                              selected_texture=row['path'].name,source_uv_channel=row['uv_channel'],
                              diffuse_policy='own_secondary_diffuse_uv1' if row['uv_channel'] else 'own_primary_diffuse_uv0',
                              omitted_secondary_texture=getattr(prior.get('Base_Tex_2_SRGB'), 'filename', None) if not row['uv_channel'] else None,
                              tint=row['tint'], uv_bounds=row['bounds'], native_shader='hair_parts_tablet_ss'))
            texture = copy.copy(prior['Base_Tex_SRGB'])
            texture.filename = 'native_hair_bsm_alp.dds'
            material.textures = [(k, texture if k == 'Base_Tex_SRGB' else v)
                                 for k, v in material.textures if k != 'Base_Tex_2_SRGB']
            # Accessory skin shader uses the same primary diffuse/alpha route.
            material.technique = 'pes3DDF_Hair2'
    output.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(output)
    return output, audit

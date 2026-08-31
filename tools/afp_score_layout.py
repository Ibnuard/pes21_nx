"""Same-size PES21 AP2 scoreboard timeline patch, no bytecode rewriting.

Format research: DragonMinded/bemaniutils (afp/swf.py and container.py).
The title's AP2 v11 extends the documented image records with dimensions.
Only verified transform/color fields are edited. AS3, strings, tag sizes,
frame labels, imports and byteswap descriptors remain byte-identical.
"""
from dataclasses import dataclass
import hashlib
import struct

from scoreboard_geometry import timeline_targets

SCORE_MOVIE_SHA256 = '1c7b3e5319fb8cfb6f12247c8e142342b6d15c8f3e17057fde542e9bd1542f5a'


def swap_fields(data, info):
    output = bytearray(data)
    cursor = 0
    if len(info) % 2:
        raise ValueError('unaligned AP2 byteswap descriptor')
    for (word,) in struct.iter_unpack('<H', info):
        if not word:
            break
        cursor += (word & 127) * 2
        kind, repeat = word >> 13, ((word >> 7) & 63) + 1
        if kind == 0:
            cursor += 256 * (repeat - 1)
            continue
        if kind not in (1, 2, 3):
            raise ValueError('unsupported AP2 byteswap type')
        size = 1 << kind
        for _ in range(repeat):
            if cursor + size > len(output):
                raise ValueError('AP2 byteswap outside movie')
            output[cursor:cursor+size] = output[cursor:cursor+size][::-1]
            cursor += size
    return bytes(output)


@dataclass
class Movie:
    name: str
    offset: int
    size: int
    info: bytes
    data: bytes


def read_movies(container):
    base = container.index(b'TXP2')
    txp = container[base:]
    # Bind to the exact table schema observed in this title, not arbitrary AFP.
    if struct.unpack_from('>II', txp, 16) != (108, 0x37fdf):
        raise ValueError('unsupported TXP2 header/schema')
    count, table = struct.unpack_from('>II', txp, 76)
    info_table = struct.unpack_from('>I', txp, 104)[0]
    result = []
    for i in range(count):
        name, size, offset = struct.unpack_from('>III', txp, table+12*i)
        zero, info_size, info_offset = struct.unpack_from('>III', txp, info_table+12*i)
        if zero or offset+size > len(txp) or info_offset+info_size > len(txp):
            raise ValueError('invalid AP2 range')
        name = txp[name:txp.index(b'\0', name)].decode('ascii')
        info = txp[info_offset:info_offset+info_size]
        raw = txp[offset:offset+size]
        decoded = swap_fields(raw, info)
        if swap_fields(decoded, info) != raw:
            raise ValueError('AP2 endian roundtrip failed')
        result.append(Movie(name, base+offset, size, info, decoded))
    return result


def strings(data):
    start, size = struct.unpack_from('<II', data, 48)
    decoded = bytes((value-128-i) & 255 for i, value in enumerate(data[start:start+size]))
    result, cursor = {}, 0
    for part in decoded.split(b'\0'):
        if part:
            result[cursor] = part.decode('utf8')
        cursor += len(part)+1
    return result


def placements(data):
    if data[:4] != b'\x0b\xb2\xd0\xc1' or struct.unpack_from('<I', data, 4)[0] != len(data):
        raise ValueError('unsupported PES21 AP2 movie')
    names = strings(data)
    result = []
    visited = set()

    def parse(base, parent):
        if base in visited:
            raise ValueError('recursive AP2 section')
        visited.add(base)
        _, _, frames, count, _, frame_table, tag_table = struct.unpack_from('<HHIIIII', data, base)
        cursor = base+tag_table
        frame_map = {}
        for frame in range(frames):
            word = struct.unpack_from('<I', data, base+frame_table+4*frame)[0]
            frame_map.update({(word & 0xfffff)+i: frame for i in range(word >> 20)})
        for i in range(count):
            head = struct.unpack_from('<I', data, cursor)[0]
            code, size = head >> 22, head & 0x3fffff
            start = cursor+4
            if start+size > len(data):
                raise ValueError('truncated AP2 tag')
            if code == 0x79:
                flags, ident = struct.unpack_from('<HH', data, start)
                nested = start+struct.unpack_from('<I', data, start+4)[0] if flags & 1 else start+4
                parse(nested, ident)
            elif code == 0x7f:
                flags, depth, ident = struct.unpack_from('<IHH', data, start)
                p = start+8
                if flags & 0x80000000:
                    flags |= struct.unpack_from('<I', data, p)[0] << 32
                    p += 4
                item = dict(parent=parent, depth=depth, offset=start, size=size,
                            frame=frame_map.get(i), flags=flags, object_id=ident)
                for bit, name in ((2, 'source'), (0x10, 'label'), (0x20, 'name'), (0x40, 'unknown')):
                    if flags & bit:
                        value = struct.unpack_from('<H', data, p)[0]
                        item[name] = names[value] if name == 'name' else value
                        p += 2
                if flags & 0x20000:
                    p += 1
                p = start+((p-start+3) & ~3)
                for bit, name, fmt, divisor in ((0x100, 'scale', 'ii', 1024),
                                                (0x200, 'rotation', 'ii', 1024),
                                                (0x400, 'translate', 'ii', 20),
                                                (0x800, 'mult16', '4h', 1),
                                                (0x1000, 'add16', '4h', 1),
                                                (0x2000, 'mult8', 'I', 1),
                                                (0x4000, 'add8', 'I', 1)):
                    if flags & bit:
                        item[name] = tuple(v/divisor for v in struct.unpack_from('<'+fmt, data, p))
                        item[name+'_offset'] = p
                        p += struct.calcsize('<'+fmt)
                # Late compact scale occurs only after optional filters/etc.
                # Expose it only when none of those intervening fields exist.
                if flags & 0x40000 and not flags & (0x80 | 0x10000 | 0x3000000 | 0x200000000):
                    item['scale16'] = tuple(v/32768 for v in struct.unpack_from('<hh', data, p))
                    item['scale16_offset'] = p
                    p += 4
                if p > start+size:
                    raise ValueError('AP2 placement fields exceed tag')
                result.append(item)
            cursor += 4+((size+3) & ~3)
    parse(struct.unpack_from('<I', data, 36)[0], None)
    return result


def patch_layout(container):
    movies = read_movies(container)
    movie = next(m for m in movies if m.name == 'game2d_score')
    if hashlib.sha256(movie.data).hexdigest() != SCORE_MOVIE_SHA256:
        raise ValueError('score movie is not the verified stock revision')
    records = placements(movie.data)
    # Verify named nodes before using their title-specific parent/depth values.
    expected = {14: 'time_set', 33: 'losstime_progress_set', 61: 'teamName_away',
                63: 'teamName_home', 65: 'teamScore_away', 67: 'teamScore_home',
                69: 'teamColor_away', 75: 'teamColor_home'}
    for depth, name in expected.items():
        matches = [r for r in records if r['parent'] == 28 and r['depth'] == depth and r['frame'] == 0]
        if len(matches) != 1 or matches[0].get('name') != name:
            raise ValueError(f'unexpected scoreboard node {name}')
    changes = []
    output = bytearray(movie.data)

    def write(offset, fmt, values, label):
        old = bytes(output[offset:offset+struct.calcsize('<'+fmt)])
        new = struct.pack('<'+fmt, *values)
        if old != new:
            changes.append(dict(offset=offset, before=old.hex(), after=new.hex(), field=label))
            output[offset:offset+len(new)] = new

    # Every translated keyframe receives the same delta. Visibility, ease,
    # update semantics, labels, duration and data bindings are untouched.
    deltas = {}
    for depth, target in timeline_targets().items():
        initial = [r for r in records if r['parent'] == 28 and
                   r['depth'] == depth and r['frame'] == 0]
        if len(initial) != 1 or 'translate' not in initial[0]:
            raise ValueError(f'missing initial transform at depth {depth}')
        old_x, old_y = initial[0]['translate']
        deltas[depth] = (target[0] - old_x, target[1] - old_y)
    for r in records:
        if r['parent'] != 28:
            continue
        depth = r['depth']
        if depth in deltas and 'translate' in r:
            dx, dy = deltas[depth]
            x, y = r['translate']
            write(r['translate_offset'], 'ii', (round((x+dx)*20), round((y+dy)*20)), f'depth{depth}.translate')
        if depth in (14, 33):
            # The stock clock lives below plateMain in the display list. A
            # fully opaque custom background therefore covered its digits even
            # though the clock was translated into the correct field. Lift the
            # two clock states into unused depths between teamColor (75) and
            # the suppressed old logo (81), preserving every frame/update.
            new_depth = 77 if depth == 14 else 78
            write(r['offset']+4, 'H', (new_depth,), f'depth{depth}.clock_display_depth')
        if depth == 60 and 'scale' in r:
            # The native region is physically 4 px wide and its timeline scale
            # is about 96x. Relocating it to a 384 px region therefore requires
            # the reciprocal 96x compensation. V4 divided by only three and the
            # physical region was still clipped across the whole viewport.
            # Preserve all 17 ease keyframes while restoring the intended
            # approximately 384 px single-row plate.
            x, y = r['scale']
            write(r['scale_offset'], 'ii', (round(x*(1/96)*1024), round(y*1024)), 'depth60.physical_region_scale')
        if depth in (61, 63) and 'scale' in r:
            x, y = r['scale']
            write(r['scale_offset'], 'ii', (round(x*(2/3)*1024), round(y*1024)), f'depth{depth}.text_bounds')
        if depth in (61, 63, 65, 67):
            # UIR uses multiplicative ARGB timeline color. Its steady-state
            # placement records carry the color-update flag (0x8) without a
            # payload, which resets tinted text to white. Retain the native
            # fade records, tint every explicit multiplier, and remove only
            # those payload-less resets. The final fade-in keyframe is promoted
            # from 224 to 255 alpha because its following reset no longer does
            # that promotion for us.
            target_rgb = 0xe6e600 if depth in (61, 63) else 0x000064
            if 'mult16' in r or 'add16' in r or 'add8' in r:
                raise ValueError('unexpected scoreboard text color encoding')
            if 'mult8' in r:
                value = int(r['mult8'][0])
                alpha = value & 255
                final_fade_frame = 30 if depth in (61, 63) else 24
                if r['frame'] == final_fade_frame and alpha == 224:
                    alpha = 255
                write(r['mult8_offset'], 'I', ((target_rgb << 8) | alpha,), f'depth{depth}.text_color')
            elif r['flags'] & 0x8:
                write(r['offset'], 'I', (r['flags'] & ~0x8,), f'depth{depth}.preserve_text_color')
        if depth == 81:
            # EF10 logo is baked into the bar atlas. Suppress only this local
            # PES logo instance, not its shared texture used elsewhere.
            if 'mult8' in r:
                write(r['mult8_offset'], 'I', (int(r['mult8'][0]) & ~255,), 'old_logo.alpha')
            if 'scale16' in r:
                write(r['scale16_offset'], 'hh', (1, 1), 'old_logo.initial_scale')
    if len(changes) < 100:
        raise ValueError('unexpectedly few scoreboard edits')
    if len(output) != len(movie.data):
        raise ValueError('AP2 length changed')
    # Reparse and verify movie-level shape/count/field boundaries.
    after_records = placements(bytes(output))
    if len(after_records) != len(records):
        raise ValueError('AP2 placement count changed')
    final = bytearray(container)
    final[movie.offset:movie.offset+movie.size] = swap_fields(output, movie.info)
    check = read_movies(bytes(final))
    for before, after in zip(movies, check):
        if before.name != 'game2d_score' and before.data != after.data:
            raise ValueError('unrelated UI movie changed')
    report = {'movie': movie.name, 'movie_size_unchanged': True,
              'other_movies_unchanged': len(movies)-1, 'placement_count': len(records),
              'edits': changes, 'as3_and_bindings_unchanged': True}
    return bytes(final), report

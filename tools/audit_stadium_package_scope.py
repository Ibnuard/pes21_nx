"""Read-only local PAK audit: addon packages must not override native assets.

Lists package entries with repak; never extracts, recooks or installs payloads.
Use the files actually installed on the device for a device-specific conclusion.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess


PREFIX = ('PesMobile', 'Content', 'FootballNX', 'Stadiums')


def inspect_names(names):
    outside, namespaces = [], set()
    canonical = []
    for name in names:
        parts = PurePosixPath(name.replace('\\', '/')).parts
        if (len(parts) != 6 or parts[:4] != PREFIX or '..' in parts or
                PurePosixPath(parts[-1]).suffix not in {'.uasset', '.uexp', '.ubulk'}):
            outside.append(name)
        else:
            namespaces.add(parts[4])
        canonical.append('/'.join(parts).casefold())
    duplicates = sorted({n for n in canonical if canonical.count(n) > 1})
    return dict(entries=len(names), namespaces=sorted(namespaces),
                outside_addon_namespace=outside, duplicate_entries=duplicates,
                passed=bool(names) and len(namespaces) == 1 and not outside and not duplicates)


def audit(paks, repak):
    rows, owners, overlaps = [], {}, []
    for pak in paks:
        pak = Path(pak).resolve(strict=True)
        names = subprocess.check_output([str(repak), 'list', str(pak)], text=True).splitlines()
        row = inspect_names(names)
        with pak.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        row.update(path=str(pak), bytes=pak.stat().st_size, sha256=digest)
        rows.append(row)
        for name in names:
            key = name.replace('\\', '/').casefold()
            if key in owners:
                overlaps.append(dict(entry=name, packages=[owners[key], str(pak)]))
            owners[key] = str(pak)
    return dict(packages=rows, overlaps=overlaps,
                passed=bool(rows) and all(r['passed'] for r in rows) and not overlaps,
                limitation='Namespace isolation only; not device visibility, active mount verification or FPS.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pak', type=Path, action='append', required=True)
    p.add_argument('--repak', default='repak')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    report = audit(a.pak, a.repak)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(output=str(a.output), passed=report['passed'], packages=len(report['packages']))))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

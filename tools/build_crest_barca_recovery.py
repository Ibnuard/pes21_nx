"""Retain working Madrid kits; restore native Barca descriptors and crest aliases."""
import argparse
import json
from pathlib import Path
from build_pesdb_famous_teams_candidate import member_payload, package_outer_obb, validate_outer_obb
from build_barca_real_madrid_mobile_kit_canary import cpk_inventory, package_cpk

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-obb', type=Path, required=True)
    p.add_argument('--native-dt200', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    if out.exists():
        raise FileExistsError(out)
    out.mkdir(parents=True)
    report, replacements = {}, {}
    for label in ('dt200', 'dt240'):
        outer = f'Expansion/{label}_mobile_all.cpk'
        base = out/f'base-{label}.cpk'
        base.write_bytes(member_payload(a.base_obb, outer))
        inventory = cpk_inventory(base)
        payloads = {}
        if label == 'dt200':
            for kind in ('1st', '2nd', 'GK1st'):
                name = f'common/etc/uniform/team/108/108_DEF_{kind}_realUni.bin'
                payloads[name] = member_payload(a.native_dt200, name)
                if len(payloads[name]) != 120:
                    raise ValueError('invalid native descriptor')
        else:
            # Team 109 now selects real uniforms. Provide both licensed and
            # fallback crest names, using the exact same approved PNG bytes.
            for suffix in ('', '_l', '_s'):
                src = f'common/render/symbol/flag/e_000109_f{suffix}.png'
                dst = f'common/render/symbol/flag/e_000109_r{suffix}.png'
                payloads[dst] = member_payload(base, src)
        actions = {n: 'replace' if n in inventory else 'add' for n in payloads}
        paths = {}
        for i, (n, data) in enumerate(payloads.items()):
            target = out/f'{label}-{i}.bin'
            target.write_bytes(data)
            paths[n] = str(target)
        report[label] = package_cpk(ROOT, out, label, base, actions, payloads, paths)
        replacements[outer] = Path(report[label]['candidate'])
    obb = out/a.base_obb.name
    mode, _ = package_outer_obb(a.base_obb, obb, replacements)
    report['obb'] = validate_outer_obb(a.base_obb, obb, replacements, packaging_mode=mode)
    report['runtime_tested'] = False
    report['scope'] = 'Madrid crest aliases + native Barca descriptors only; no input changes'
    (out/'validation-report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report['obb'], indent=2), flush=True)


if __name__ == '__main__':
    main()

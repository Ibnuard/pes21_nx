"""Record explicitly inspected league sheets without granting final acceptance.

This CLI never inspects images on the reviewer's behalf. Call ``record`` only
after actually viewing each named sheet. Current cooked/prepared keys, renderer,
completed batch hashes and image proofs are checked before recording evidence.
"""
import argparse
from pathlib import Path
import time

from realface_batch_inventory import read, write
from realface_pipeline import sha

HERE = Path(__file__).resolve().parent
PREPARED = ('prepared', 'prepared_cached')
VERIFIED = ('validated', 'validated_cached')


def context(config):
    work = Path(config['work_dir']).resolve()
    prepared = read(work/'prepare-report.json')
    verified = read(work/'verify-report.json')
    rows = {r['base_id']: r for r in verified if r['status'] in VERIFIED}
    if len(rows) != sum(r['status'] in VERIFIED for r in verified):
        raise ValueError('Duplicate cooked review identities')
    old = {r['base_id']: r for r in prepared if r['status'] in PREPARED}
    for base, row in rows.items():
        previous = old.get(base)
        if not previous or any(row[k] != previous[k] for k in
                               ('native_player_id', 'fingerprint', 'cache_key')):
            raise ValueError('Prepared/cooked review identity differs')
    path = work/'VISUAL-REVIEW-PROGRESS.json'
    progress = read(path) if path.exists() else dict(
        phase='partial_visual_inspection', complete=False, images=[], sheets=[],
        pending_detail_base_ids=[], findings=[])
    return work, rows, progress


def image_proof(work, rows, path, base, view):
    path = Path(path).resolve()
    if not path.is_relative_to(work/'review') or base not in rows:
        raise ValueError('Review image is outside the current cooked cohort')
    row = rows[base]
    expected = dict(prepared_key=row['cache_key'], cooked_key=row['cooked_cache_key'],
                    renderer_sha256=sha(HERE/'blender_preview_realface.py'), view=view,
                    image_sha256=sha(path))
    if read(path.with_suffix('.json')) != expected:
        raise ValueError('Review image has stale or non-cooked provenance')
    return dict(base_id=base, path=str(path), sha256=expected['image_sha256'], view=view)


def current_images(work, rows, progress):
    valid, stale = {}, []
    for item in progress['images']:
        path = Path(item['path'])
        view = item.get('view') or path.stem.rsplit('-', 1)[-1]
        try:
            proof = image_proof(work, rows, path, item['base_id'], view)
            if item['sha256'] != proof['sha256']:
                raise ValueError('Inspected image bytes changed')
        except (ValueError, KeyError, OSError):
            stale.append(item)
        else:
            valid[(item['base_id'], view)] = dict(item, **proof)
    return valid, stale


def sheet_images(work, rows, sheet):
    sheet = Path(sheet).resolve()
    if not sheet.is_relative_to(work/'review') or not sheet.name.startswith('sheet-'):
        raise ValueError('Select a generated current review sheet')
    folder = sheet.parent
    stamp = read(folder/'PREVIEW-COMPLETE.json')
    hashes = stamp.get('hashes', {})
    if not hashes or hashes.get(str(sheet)) != sha(sheet):
        raise ValueError('Sheet is not a completed batch output')
    for path, digest in hashes.items():
        resolved = Path(path).resolve()
        if resolved.parent != folder or sha(resolved) != digest:
            raise ValueError('Completed review batch changed')
    provenance = read(folder/'PROVENANCE.json')
    if provenance.get('stage') != 'cooked' or str(sheet) not in provenance['sheets']:
        raise ValueError('Cooked review sheet required')
    views = provenance['views']
    if not views or len(set(views)) != len(views) or not set(views) <= {'front', 'left', 'right', 'above'}:
        raise ValueError('Invalid review views')
    columns = max(1, 8//len(views))
    start = provenance['sheets'].index(str(sheet))*columns*6
    heads = provenance['players'][start:start+columns*6]
    if not heads:
        raise ValueError('Sheet has no current heads')
    result = [image_proof(work, rows, folder/(str(p['base_id'])+'-'+view+'.png'),
                          p['base_id'], view) for p in heads for view in views]
    return result, dict(path=str(sheet), sha256=sha(sheet),
                        base_ids=[p['base_id'] for p in heads], views=views,
                        inspection='contact_sheet')


def record(config, sheets, finding, pending=(), source_pending=()):
    if not sheets or not finding.strip():
        raise ValueError('Explicitly inspected sheets and a finding are required')
    work, rows, progress = context(config)
    pending_ids = set(progress.get('pending_detail_base_ids', [])) | set(pending)
    source_ids = set(progress.get('source_comparison_pending_base_ids', [])) | set(source_pending)
    invalid = (pending_ids | source_ids) - rows.keys()
    if invalid:
        raise ValueError('Pending review identities outside cooked cohort: '+str(sorted(invalid, key=str)))
    valid, stale = current_images(work, rows, progress)
    stamps = {s['path']: s for s in progress['sheets']}
    for path in sheets:
        images, stamp = sheet_images(work, rows, path)
        for image in images:
            valid[(image['base_id'], image['view'])] = dict(image,
                inspection='contact_sheet', final_decision_pending=True)
        stamps[stamp['path']] = stamp
    progress.update(phase='partial_visual_inspection', complete=False, updated_at=time.time(),
        prepare_sha256=sha(work/'prepare-report.json'), verify_sha256=sha(work/'verify-report.json'),
        images=sorted(valid.values(), key=lambda r: (r['base_id'], r['view'])),
        sheets=list(stamps.values()),
        pending_detail_base_ids=sorted(pending_ids),
        source_comparison_pending_base_ids=sorted(source_ids))
    if stale:
        progress.setdefault('superseded_images', []).extend(stale)
    progress['findings'].append(finding.strip())
    write(work/'VISUAL-REVIEW-PROGRESS.json', progress)
    return dict(inspected_front_heads=sum(view == 'front' for _, view in valid),
                inspected_images=len(valid), superseded_images=len(stale), final_acceptance=False)


def status(config):
    work, rows, progress = context(config)
    invalid = (set(progress.get('pending_detail_base_ids', [])) |
               set(progress.get('source_comparison_pending_base_ids', []))) - rows.keys()
    valid, stale = current_images(work, rows, progress)
    unseen = []
    for path in sorted((work/'review').glob('*/*/sheet-*.png')):
        if not (path.parent/'PREVIEW-COMPLETE.json').is_file():
            continue
        try:
            # Most completed sheets have already been explicitly inspected.
            # Read their small manifest first instead of rehashing every PNG
            # and decoded texture just to discover there is no new evidence.
            manifest = read(path.parent/'PROVENANCE.json')
            if all((p['base_id'], view) in valid for p in manifest['players']
                   for view in manifest['views']):
                continue
            images, _ = sheet_images(work, rows, path)
        except (ValueError, KeyError, OSError):
            continue
        pending = [i for i in images if (i['base_id'], i['view']) not in valid]
        if pending:
            unseen.append(dict(sheet=str(path), uninspected_images=len(pending),
                               base_ids=sorted({i['base_id'] for i in pending})))
    return dict(cooked_heads=len(rows), inspected_front_heads=sum(v == 'front' for _, v in valid),
                inspected_images=len(valid), stale_inspection_images=len(stale),
                invalid_pending_base_ids=sorted(invalid, key=str),
                source_comparison_pending_base_ids=progress.get('source_comparison_pending_base_ids', []),
                pending_sheets=unseen, final_acceptance=False)


def render_details(config):
    """Render flagged views only after acquiring the same serial runner lock."""
    from realface_batch import key_of
    from realface_league_balanced import exclusive
    from realface_league_preview import preview
    from realface_preview_cache import index_views, seed_views
    from realface_preview_process import PreviewProcess
    work = Path(config['work_dir']).resolve()
    with exclusive(work):
        work, rows, progress = context(config)
        pending = sorted(set(progress['pending_detail_base_ids']))
        if not set(pending) <= rows.keys():
            raise ValueError('Pending detail identity is outside the cooked cohort')
        heads = [rows[b] for b in pending]
        views = ('front', 'left', 'right', 'above')
        renderer = sha(HERE/'blender_preview_realface.py')
        cached = index_views(work/'review', heads, renderer)
        sheets = []
        with PreviewProcess(config['blender']) as worker:
            for start in range(0, len(heads), 12):
                chunk = heads[start:start+12]
                key = key_of(dict(kind='flagged_review',
                    keys=[(r['cache_key'], r['cooked_cache_key']) for r in chunk],
                    views=views, renderer=renderer,
                    preview_tool=sha(HERE/'realface_league_preview.py')))[:16]
                output = work/'review/flagged'/key
                seed_views(output, chunk, views, cached)
                preview(config, stage='cooked', selected={r['base_id'] for r in chunk},
                        limit=len(chunk), views=views, output=output, render_worker=worker)
                complete = output/'PREVIEW-COMPLETE.json'
                files = [p for p in output.iterdir() if p.suffix in ('.json', '.png') and p != complete]
                write(complete, dict(hashes={str(p.resolve()): sha(p) for p in files}))
                sheets.extend(read(output/'PROVENANCE.json')['sheets'])
        return dict(sheets=sheets, flagged_heads=len(heads),
                    final_acceptance=False, inspected_automatically=False)


def render_comparisons(config, selected=()):
    """Batch original/prepared diagnostics; these never satisfy cooked review."""
    from realface_batch import key_of
    from realface_league_balanced import exclusive
    from realface_league_preview import preview
    from realface_lite import sources
    from realface_preview_cache import index_views
    from realface_preview_process import PreviewProcess
    from realface_reference_preview_cache import (header, owners, index_references,
                                                  seed_references, seal_references)
    work = Path(config['work_dir']).resolve()
    with exclusive(work):
        work, rows, progress = context(config)
        pending = sorted(set(selected or progress.get('source_comparison_pending_base_ids', [])))
        if not pending or not set(pending) <= rows.keys():
            raise ValueError('Select pending source comparisons inside the cooked cohort')
        catalogue = {r['base_id']: r for r in sources(config)}
        if not set(pending) <= catalogue.keys():
            raise ValueError('Comparison source identity is unavailable')
        for base in pending:
            if any(rows[base][k] != catalogue[base][k] for k in ('native_player_id', 'fingerprint')):
                raise ValueError('Comparison source identity differs')
        cooked_views = index_views(work/'review', [rows[b] for b in pending],
                                   sha(HERE/'blender_preview_realface.py'))
        if any((base, 'front') not in cooked_views for base in pending):
            raise ValueError('Current cooked front preview required for comparison')
        references = [image_proof(work, rows, cooked_views[(b, 'front')], b, 'front') for b in pending]
        renderer = sha(HERE/'blender_preview_realface.py')
        preview_tool = sha(HERE/'realface_league_preview.py')
        all_owners = {stage: owners(stage, [rows[b] for b in pending], catalogue)
                      for stage in ('source', 'prepared')}
        headers = {stage: header(config, stage, renderer, preview_tool) for stage in all_owners}
        reference_root = work/'texture-diagnostic/flagged-comparisons'
        caches = {stage: index_references(reference_root, headers[stage], all_owners[stage])
                  for stage in all_owners}
        results = []
        with PreviewProcess(config['blender']) as worker:
            for start in range(0, len(pending), 12):
                chunk = pending[start:start+12]
                key = key_of(dict(kind='source_comparison',
                    sources=[(b, catalogue[b]['input_hashes']) for b in chunk],
                    prepared=[rows[b]['cache_key'] for b in chunk],
                    renderer=sha(HERE/'blender_preview_realface.py'),
                    preview_tool=sha(HERE/'realface_league_preview.py')))[:16]
                output = work/'texture-diagnostic/flagged-comparisons'/key
                for stage in ('source', 'prepared'):
                    selected_owners = {base: all_owners[stage][base] for base in chunk}
                    seed_references(output/stage, selected_owners, caches[stage])
                    preview(config, stage=stage, selected=set(chunk), limit=len(chunk),
                            views=('front',), output=output/stage, render_worker=worker)
                    seal_references(output/stage, headers[stage], selected_owners)
                    results.append(dict(base_ids=chunk, stage=stage,
                        sheets=read(output/stage/'PROVENANCE.json')['sheets']))
        receipt = dict(comparisons=results, current_cooked_fronts=references, inspected_automatically=False,
                       final_acceptance=False, valid_for_cooked_acceptance=False)
        write(work/'texture-diagnostic/SOURCE-COMPARISON-INDEX.json', receipt)
        return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('action', choices=('status', 'record', 'render-details', 'render-source-comparisons'))
    parser.add_argument('--sheet', action='append', default=[])
    parser.add_argument('--finding', default='')
    parser.add_argument('--pending-detail', type=int, action='append', default=[])
    parser.add_argument('--source-comparison', type=int, action='append', default=[])
    parser.add_argument('--player', type=int, action='append', default=[])
    args = parser.parse_args()
    config = read(args.config)
    from realface_league_balanced import local_output
    local_output(config['work_dir'])
    if args.action == 'record':
        result = record(config, args.sheet, args.finding, args.pending_detail, args.source_comparison)
    elif args.action == 'render-details':
        result = render_details(config)
    elif args.action == 'render-source-comparisons':
        result = render_comparisons(config, args.player)
    else:
        result = status(config)
    import json
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

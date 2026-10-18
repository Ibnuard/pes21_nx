"""Verify exact front-screen evidence before selecting a TEST package.

Passing this check means the included candidates were screened for obvious
front-view defects. It does not approve their other views, animation or FPS.
"""
from pathlib import Path

from realface_batch_inventory import read
from realface_pipeline import sha


def require_screened(rows, specifications):
    checked = {}; evidence = []
    for specification in specifications:
        report = Path(specification['report']); screen = Path(specification['screen_dir'])
        snapshot = read(report); review_path = screen / 'REVIEW.json'; review = read(review_path)
        if review.get('input_sha256') != sha(report):
            raise ValueError('Front-screen candidate snapshot changed')
        if len({r['base_id'] for r in snapshot}) != len(snapshot):
            raise ValueError('Duplicate front-screen snapshot identity')
        page_proofs = []
        for number, page in review['pages'].items():
            number = int(number)
            if number < 1:
                raise ValueError('Invalid front-screen page')
            expected = snapshot[(number - 1) * 36:number * 36]
            if [(r['base_id'], r['cache_key']) for r in page['players']] != [
                    (r['base_id'], r['cache_key']) for r in expected] or not expected:
                raise ValueError('Front-screen page differs from its candidate snapshot')
            sheet = screen / ('sheet-%02d.png' % number)
            if page['sheet_sha256'] != sha(sheet):
                raise ValueError('Front-screen contact sheet changed')
            for item in page['players']:
                base = item['base_id']; image = screen / (str(base) + '.png')
                stamp = read(image.with_suffix('.json'))
                if (stamp.get('view') != 'front' or stamp.get('candidate_key') != item['cache_key'] or
                        stamp.get('image_sha256') != item['image_sha256'] or sha(image) != item['image_sha256']):
                    raise ValueError('Front-screen image/provenance changed')
                identity = (base, item['cache_key'])
                if identity in checked and checked[identity] != item:
                    raise ValueError('Conflicting front-screen evidence')
                checked[identity] = item
            page_proofs.append(dict(page=number, sheet_sha256=page['sheet_sha256'], heads=len(expected)))
        evidence.append(dict(report=str(report.resolve()), input_sha256=sha(report),
                             review=str(review_path.resolve()), review_sha256=sha(review_path), pages=page_proofs))
    selected = []
    for row in rows:
        item = checked.get((row['base_id'], row['cache_key']))
        if not item:
            raise ValueError('Included candidate has no current front-screen review: ' + str(row['base_id']))
        if item.get('front_major_defect_observed') is not False:
            raise ValueError('Observed front-screen defect is still selected: ' + str(row['base_id']))
        selected.append(item)
    return dict(scope='front_screen_only', selected_heads=len(selected), players=selected,
                evidence=evidence, full_visual_approval=False, hardware_profiled=False)

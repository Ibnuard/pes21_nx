"""Record observed front-view defects against immutable local candidate images.

This records a human/agent visual screen; it does not infer appearance approval
from counts or pixels. Existing exact-key rejections are never silently cleared.
"""
import argparse
from pathlib import Path

from realface_batch_inventory import read, write
from realface_pipeline import sha


def record(report, screen, rejects_path, page, notes):
    report, screen, rejects_path = Path(report), Path(screen), Path(rejects_path)
    if page < 1:
        raise ValueError('Page numbers start at one')
    snapshot = read(report)
    if len({r['base_id'] for r in snapshot}) != len(snapshot):
        raise ValueError('Candidate snapshot contains duplicate identities')
    rows = snapshot[(page - 1) * 36:page * 36]
    if not rows or not set(notes) <= {r['base_id'] for r in rows}:
        raise ValueError('Review/rejection must refer to this exact page')
    if any(not reason.strip() for reason in notes.values()):
        raise ValueError('A visible defect requires a reason')
    old = read(rejects_path) if rejects_path.exists() else []
    rejected = {r['base_id']: r for r in old}
    if len(rejected) != len(old):
        raise ValueError('Duplicate visual rejection identities')
    review_path = screen / 'REVIEW.json'
    review = read(review_path) if review_path.exists() else dict(pages={}, approved=False)
    report_hash = sha(report)
    if review.get('input_sha256', report_hash) != report_hash:
        raise ValueError('Review candidate snapshot changed')
    sheet = screen / ('sheet-%02d.png' % page)
    sheet_hash = sha(sheet)
    checks = []
    for row in rows:
        base = row['base_id']
        proof = read(screen / (str(base) + '.json'))
        image_hash = sha(screen / (str(base) + '.png'))
        if proof['candidate_key'] != row['cache_key'] or proof['image_sha256'] != image_hash:
            raise ValueError('Rendered image no longer matches the candidate')
        if base in notes:
            if base in rejected and rejected[base]['cache_key'] != row['cache_key']:
                raise ValueError('Existing rejection belongs to a different candidate')
            rejected[base] = dict(base_id=base, name=row['name'], cache_key=row['cache_key'],
                                  reason=notes[base].strip(), review=str(sheet.resolve()), hardware_capture=False)
        known = rejected.get(base, {})
        checks.append(dict(base_id=base, cache_key=row['cache_key'], image_sha256=image_hash,
                           front_major_defect_observed=known.get('cache_key') == row['cache_key'],
                           full_visual_approval=False))
    review['pages'][str(page)] = dict(sheet_sha256=sheet_hash, players=checks)
    review.update(input_sha256=report_hash, approved=False,
                  screened=sum(len(p['players']) for p in review['pages'].values()))
    # All checks above finish before either mutable report is published.
    write(rejects_path, sorted(rejected.values(), key=lambda r: r['base_id']))
    write(review_path, review)
    return dict(screened=review['screened'], known_visual_rejects=len(rejected), approved=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True)
    parser.add_argument('--screen-dir', required=True)
    parser.add_argument('--reject-file', required=True)
    parser.add_argument('--page', type=int, required=True)
    parser.add_argument('--reject', action='append', default=[], metavar='BASE_ID=REASON')
    args = parser.parse_args()
    notes = {}
    for item in args.reject:
        base, reason = item.split('=', 1)
        if int(base) in notes:
            raise ValueError('Duplicate rejection in this review')
        notes[int(base)] = reason
    print(record(args.report, args.screen_dir, args.reject_file, args.page, notes))

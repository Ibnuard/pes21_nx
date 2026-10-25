"""Diagnose a complete skin audit from released-texture and native evidence.

This read-only report queues new cooked-texture reviews. It never authorizes a
patch, invents missing rows, or calls a nearest colour device acceptance.
"""
from __future__ import annotations

from collections import Counter

from realface_skin_batch import classify, unique
from realface_skin_provenance import matching_identity


def effective_body_skin(selector):
    if type(selector) is not int or not 0 <= selector <= 7:
        raise ValueError('Expected a native three-bit body selector')
    return max(1, min(6, selector))


def diagnose_scope(audit, provenance, native, palette, staged, protected):
    if (audit['state'] != 'audit_complete' or
            provenance['state'] != 'provenance_complete' or
            native['state'] != 'native_body_default_and_missing_row_diagnosed'):
        raise ValueError('Incomplete audit, provenance or native diagnosis')
    if native['body_static_semantics'] != {'0': 1, '7': 6}:
        raise ValueError('Native body consumer evidence differs')
    audited = unique(audit['players'], 'base_id')
    proofs = unique(provenance['players'], 'base_id')
    if set(proofs) != set(audited) or len(proofs) != provenance['players_checked']:
        raise ValueError('Provenance does not cover the exact audited scope')
    current = unique(staged, 'base_id')
    if not set(current) <= set(audited):
        raise ValueError('Staged policy escapes audited scope')
    missing = unique(native['missing_players'], 'base_id')
    results = []
    for base, row in sorted(audited.items()):
        proof = proofs[base]
        matching_identity(row, proof)
        if (not row.get('fingerprint') or type(base) is not int or base <= 0 or
                type(row.get('native_player_id')) is not int or
                proof['status'] != 'provenance_verified' or
                row['profile_sha256'] != proof['source_profile_sha256'] or
                row['texture_sha256'] != proof['source_texture_sha256']):
            raise ValueError('Invalid own identity/profile/texture provenance')
        item = {k: row[k] for k in ('base_id', 'native_player_id', 'fingerprint', 'name')}
        item.update(original_status=row['status'], automatic_patch=False,
                    runtime_material_selection_observed=False, device_accepted=False)
        if row['status'] == 'held_missing_appearance':
            evidence = missing.get(base)
            if evidence is None:
                raise ValueError('Missing row has no native schema diagnosis')
            matching_identity(row, evidence)
            keys = evidence['diagnostic_keys']
            if (evidence['diagnosis'] != 'terminal_current_schema_no_existing_canonical_or_native_masked_appearance_row'
                    or not evidence['identity_exact'] or evidence['appearance_present']
                    or evidence['row_manufacture_allowed']
                    or any(keys[k]['appearance_present'] for k in
                           ('exact_native', 'base_id', 'editwork_actual_keymask_f007ffff'))):
                raise ValueError('Missing appearance diagnosis is not terminal for this schema')
            item.update(status='held_native_missing_appearance', terminal=True,
                        reason=evidence['specific_reason'])
        else:
            selector = row['current_skin']
            effective = effective_body_skin(selector)
            neck = proof['neck']
            source = classify(neck['source_rgb'], palette, effective)
            cooked = classify(neck['cooked_rgb'], palette, effective)
            item.update(selector_before=selector, effective_body_skin=effective,
                        source=source, cooked=cooked,
                        source_cooked_max_delta_e76=neck['max_delta_e76'],
                        source_cooked_error_limit=neck['error_limit'],
                        source_recommendation_stable=neck['palette_recommendation_stable'])
            if base in current:
                old = current[base]
                matching_identity(row, old)
                if base in protected or old['skin'] != cooked['nearest_skin']:
                    raise ValueError('Staged correction conflicts with protected/cooked evidence')
                item.update(status='staged_reviewed_correction', terminal=True,
                            skin_after=old['skin'], reason=old['reason'])
            elif base in protected:
                item.update(status='preserved_explicit_policy', terminal=True,
                            reason='Previously accepted own-player skin policy; no override authorized')
            elif effective == cooked['nearest_skin']:
                item.update(status='retained_effective_nearest', terminal=True,
                            reason=f'Native body selector {selector} resolves to palette {effective}; '
                                   'the actual cooked neck has the lowest mean distance to that palette')
            elif cooked['improvement'] < 4:
                item.update(status='retained_bounded_palette_difference', terminal=True,
                            reason=f'Actual cooked neck suggests palette {cooked["nearest_skin"]} '
                                   f'but gain is only {cooked["improvement"]:.3f} Lab units over '
                                   f'effective palette {effective}; retain the existing row rather '
                                   'than infer a material mismatch from this small colour distance')
            else:
                item.update(status='pending_cooked_palette_review', terminal=False,
                            reason='Compare own source atlas and actual released cooked neck with '
                                   'native palettes; old source-only recommendations are insufficient')
        results.append(item)
    return dict(state='scope_diagnosed_pending_cooked_review', players=results,
                audited=len(results), counts=dict(Counter(x['status'] for x in results)),
                pending=sum(not x['terminal'] for x in results),
                scope_terminal=all(x['terminal'] for x in results),
                automatic_patch=False, device_accepted=False)

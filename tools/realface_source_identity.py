"""Resolve local face identities using BaseId plus independent biography.

Names can be abbreviated and nationality can change across snapshots. Neither
a similar name nor a reused numeric storage slot is sufficient evidence.
"""
import re
import unicodedata


def tokens(name):
    name = name.casefold().translate(str.maketrans({'ı':'i', 'ø':'o', 'ł':'l', 'đ':'d'}))
    name = ''.join(c for c in unicodedata.normalize('NFKD', name) if not unicodedata.combining(c))
    return re.findall(r'[a-z0-9]+', name)


def name_relation(a, b):
    a, b = tokens(a), tokens(b)
    if not a or not b:
        return None
    if a == b or sorted(a) == sorted(b):
        return 'full_name'
    given_variants = ({'joe','joseph'}, {'eddie','edward'}, {'tom','thomas'},
                      {'kostas','konstantinos'}, {'odysseas','odisseas'}, {'dorde','djordje'})
    if len(a)==len(b) and len(a)>=2 and a[1:]==b[1:]:
        if any({a[0],b[0]}<=pair for pair in given_variants):
            return 'given_name_variant'
    # Preserve the full surname (including multi-token surnames) while
    # allowing explicit initials or a prefix of the given name.
    if len(a) == len(b) and len(a) >= 2 and a[1:] == b[1:]:
        short, long = sorted((a[0], b[0]), key=len)
        if long.startswith(short) and (len(short) == 1 or len(short) >= 3):
            return 'given_name_abbreviation'
    # Full given/family tokens survive an omitted middle name or surname.
    short, long = sorted((a,b),key=len)
    if len(short)>=2 and len(short)<len(long):
        rest=iter(long)
        subsequence=all(any(token==value for value in rest) for token in short)
        if subsequence and short[-1]==long[-1] and (short[0]==long[0] or short==long[-len(short):]):
            return 'omitted_middle_name'
        # Two initials may be joined, e.g. JP van Hecke / Jan Paul van Hecke.
        if (len(short[0])==2 and short[1:]==long[2:] and
                short[0]==long[0][0]+long[1][0]):
            return 'joined_given_initials'
    # Display mononyms may be a complete token of a fuller registered name.
    # This is used only with the same BaseId and all biography checks below.
    if min(len(a), len(b)) == 1:
        short, long = sorted((a,b),key=len)
        if len(short[0]) >= 4 and short[0] in long:
            return 'expanded_display_name'
    return None


def match_base_fingerprint(owner, candidate, bio):
    if candidate.player_id != owner['base_id'] or not bio:
        return None
    relation = name_relation(owner['name'], candidate.name)
    if not relation:
        return None
    same_country = owner['country'] == bio['country']
    evidence = dict(name_relation=relation, same_country=same_country,
                    height_delta_cm=bio['height']-owner['height'],
                    age_delta=bio['age']-owner['age'], same_foot=bio['foot']==owner['foot'],
                    same_goalkeeper_class=(bio['position']==0)==(owner['position']==0))
    if (abs(evidence['height_delta_cm']) > 3 or abs(evidence['age_delta']) > 3
            or not evidence['same_foot'] or not evidence['same_goalkeeper_class']):
        return None
    # A changed nationality requires the entire name, not an initial/alias.
    if not same_country and relation != 'full_name':
        return None
    return dict(policy='base_id_name_biography_v1', base_id=owner['base_id'],
                canonical_fingerprint=owner['fingerprint'], source_row_sha256=bio['row_sha256'], **evidence)

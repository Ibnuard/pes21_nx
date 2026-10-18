"""Amortize UE startup for already bounded mobile heads, preserving stock checks.

The general factory's 32-head limit protects dense source FBXs. Strict mobile
FBXs contain at most 2,000 triangles, so this scoped adapter combines up to
128 such profiles per editor lifetime. General/dense imports are unchanged.
"""
from pathlib import Path

import realface_batch_release as factory
from realface_batch import key_of
from realface_batch_inventory import read
from realface_mobile import PROFILE_POLICY
from realface_pipeline import sha


def cook(config):
    rows=read(Path(config['work_dir'])/'prepare-report.json')
    for row in rows:
        if row['status'] not in ('prepared','prepared_cached'):raise ValueError('Strict import requires prepared heads')
        proof=read(Path(row['folder'])/'simplification.json')
        profile=read(Path(row['folder'])/'ue-profile.json')
        if (not 0<proof['total_triangles']<=2000 or
                any(profile.get(k)!=v for k,v in PROFILE_POLICY.items())):
            raise ValueError('Large import group is restricted to strict two-section mobile heads')
    original_import,original_command,original_engine=factory.import_chunk,factory.command,factory.engine_key
    group=[];context=None
    def flush():
        nonlocal context
        if not group:return
        conf,project,batch,index=context
        # The original importer still checks its completion marker and every
        # per-player report. A partial/crashed editor never counts as cooked.
        original_import(conf,project,batch,list(group),index)
        group.clear();context=None
    def collect(conf,project,batch,profiles,index):
        nonlocal context
        if context is None:context=(conf,project,batch,index)
        elif context[1:3]!=(project,batch):raise ValueError('Cannot combine different UE projects')
        group.extend(profiles)
        if len(group)>=128:flush()
    def command(args,log):
        if '-run=cook' in args:flush()
        return original_command(args,log)
    factory.import_chunk=collect;factory.command=command
    factory.engine_key=lambda conf:key_of(dict(standard=original_engine(conf),strict_import_adapter=sha(__file__),maximum_profiles=128))
    try:return factory.cook(dict(config,import_chunk_size=32))
    finally:
        factory.import_chunk=original_import;factory.command=original_command;factory.engine_key=original_engine

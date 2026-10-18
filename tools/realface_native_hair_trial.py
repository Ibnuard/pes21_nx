"""Identity-pinned native-style hair trials, isolated from approved heads.

This is an incremental review factory, not a release command. Outputs remain
quality-held until the composite scalp/cards pass a visual and cooked audit.
"""
import argparse
from pathlib import Path
import shutil
import subprocess

from PIL import Image
from realface_batch import command,key_of,output_hashes,valid_cache,valid_prepared_cache
from realface_batch_inventory import read,write
from realface_league_progress import indexed,owner_matches
from realface_pipeline import sha
from realface_native_hair_cards import composite_ok

HERE=Path(__file__).resolve().parent
CODE=('realface_native_hair_trial.py','blender_realface_native_hair_worker.py','realface_native_hair_cards.py',
      'realface_mobile_geometry.py','blender_realface_lite.py','blender_fit_realface.py',
      'blender_realface_face_rebake.py','blender_realface_mobile.py','blender_realface_hair_volume.py',
      'blender_realface_hair_rebake.py','blender_realface_source_quality.py',
      'blender_realface_native_hair_detail.py','blender_export_ue_fbx.py',
      'blender_realface_hair_reduce.py','blender_realface_native_hair_bake.py',
      'realface_triangle_audit.py','realface_cook_policy.py')


def trial(config,report,players,work,opaque_base_triangles=0,base_mode='alpha_volume',colour_mode='relative_normals',closing_steps=3):
    if opaque_base_triangles and not 100<=opaque_base_triangles<=500:
        raise ValueError('Opaque scalp base must have a bounded 100..500 triangle allocation')
    work=Path(work).resolve();root=HERE.parent
    if (not work.is_relative_to(root/'local-debug') or work==root/'local-debug' or
            work==Path(config['work_dir']).resolve()):
        raise ValueError('Native-style trial needs a separate ignored review directory')
    owners=indexed(read(config['source_profiles']),'sources');prepared=indexed(read(report),'prepared')
    rows=[]
    for base in sorted(set(players)):
        owner=owners.get(base,{});face=prepared.get(base,{})
        if not owner or not owner_matches(face,owner):raise ValueError('Trial requires a verified source/face identity')
        if face.get('reuse_cooked'):raise ValueError('Accepted inherited head cannot be replaced by this trial')
        if face.get('status') not in ('prepared','prepared_cached') or not valid_prepared_cache(Path(face['folder']),face['cache_key']):
            raise ValueError('Trial face must pass the current prepared-cache audit')
        for path,digest in owner['input_hashes'].items():
            if sha(path)!=digest:raise ValueError('Pinned player source changed')
        original=read(owner['profile']);folder=Path(face['folder']);ue=read(folder/'ue-profile.json')
        if original.get('native_player_id')!=owner['native_player_id'] or original.get('hair_skin_materials'):
            raise ValueError('Native-style hair requires the verified source identity and separately classified hair')
        count=read(folder/'simplification.json')['face']['total'];budget=2000-count
        if budget<2:raise ValueError('No complete-head remainder for detail cards')
        code={name:sha(HERE/name) for name in CODE}
        key=key_of(dict(owner={k:owner[k] for k in ('base_id','native_player_id','fingerprint')},
            source=owner['input_hashes'],source_profile=original,face=face['cache_key'],code=code,
            tools={k:sha(config[k]) for k in ('blender','native_rig','cooked_rig','fast_raster')},head_cap=2000,
            opaque_base_triangles=opaque_base_triangles,base_mode=base_mode,colour_mode=colour_mode,closing_steps=closing_steps))
        out=work/(str(base)+'-'+key[:16]);out.mkdir(parents=True,exist_ok=True)
        entry={k:owner[k] for k in ('base_id','native_player_id','fingerprint','name')}
        entry.update(folder=str(out),cache_key=key,source_face_key=face['cache_key'],recipe_source_sha256=code)
        if (out/'failure.json').exists():
            failure=read(out/'failure.json')
            if failure.get('cache_key')!=key:raise ValueError('Hair trial failure provenance differs')
            rows.append(dict(entry,status='held_conversion',reason=failure['reason'],cached=True))
            write(work/'trial-report.json',rows);print(dict(base_id=base,status='held_conversion_cached'),flush=True)
            continue
        if not valid_cache(out,key):
            if (out/'complete.json').exists():raise ValueError('Trial outputs changed; choose a fresh work directory')
            write(out/'job.json',dict(folder=str(out),face_folder=str(folder),source_profile=original,
                base_id=base,native_player_id=owner['native_player_id'],face_triangles=count,hair_budget=budget,
                fingerprint=owner['fingerprint'],recipe_source_sha256=code,
                opaque_base_triangles=opaque_base_triangles,
                base_mode=base_mode,
                colour_mode=colour_mode,
                closing_steps=closing_steps,
                **{k:config[k] for k in ('native_rig','cooked_rig','fast_raster')}))
            with Image.open(original['hair_texture']) as image:
                image.convert('RGBA').resize((128,128),Image.Resampling.LANCZOS).save(out/'hair-cards.png')
            shutil.copy2(folder/'face.fbx',out/'face.fbx')
            try:
                command([config['blender'],'--background','--threads','2','--python-exit-code','1','--python',
                         HERE/'blender_realface_native_hair_worker.py','--',out/'job.json'],out/'prepare.log')
            except subprocess.CalledProcessError:
                if {name:sha(HERE/name) for name in CODE}!=code:raise ValueError('Trial code changed while preparing')
                log=(out/'prepare.log').read_text(errors='replace')
                reason=next((line for line in reversed(log.splitlines()) if line.startswith(('ValueError:','RuntimeError:','IndexError:','TypeError:'))),
                            'Blender conversion failed; inspect prepare.log')
                write(out/'failure.json',dict(cache_key=key,reason=reason))
                rows.append(dict(entry,status='held_conversion',reason=reason))
                write(work/'trial-report.json',rows);print(dict(base_id=base,status='held_conversion',reason=reason),flush=True)
                continue
            if {name:sha(HERE/name) for name in CODE}!=code:raise ValueError('Trial code changed while preparing')
            if not opaque_base_triangles and sha(out/'face.fbx')!=sha(folder/'face.fbx'):
                raise ValueError('Accepted source face geometry changed')
            write(out/'ue-profile.json',dict(ue,face_fbx=str(out/'face.fbx'),hair_fbx=str(out/'hair.fbx'),
                face_texture=str(out/'opaque-atlas.png'),hair_texture=str(out/'hair-cards.png')))
            proof=read(out/'native-hair-proof.json')
            write(out/'recipe.json',dict(eye={},source=owner,native_hair_candidate=True,mobile_v35=True))
            write(out/'simplification.json',dict(face=dict(total=proof['face_triangles']),
                hair=dict(total=proof['hair_triangles']),total_triangles=proof['total_triangles'],
                base_id=base,native_player_id=owner['native_player_id'],hardware_accepted=False))
            write(out/'QUALITY-HOLD.json',dict(approved=False,reason='Native-style composite appearance and cooked validation pending'))
            write(out/'complete.json',dict(cache_key=key,outputs=output_hashes(out)))
        proof=read(out/'native-hair-proof.json')
        geometry_ok=composite_ok(proof.get('composite_scalp_projection'))
        status='candidate_visual_hold' if geometry_ok else 'held_composite_geometry'
        rows.append(dict(entry,triangles=proof['total_triangles'],status=status,composite_geometry_pass=geometry_ok))
        print(dict(base_id=base,triangles=proof['total_triangles'],status=status),flush=True)
        write(work/'trial-report.json',rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True);parser.add_argument('--face-report',required=True)
    parser.add_argument('--player',action='append',type=int,required=True);parser.add_argument('--work-dir',required=True)
    parser.add_argument('--opaque-base-triangles',type=int,default=0)
    parser.add_argument('--base-mode',choices=('alpha_volume','source_surface'),default='alpha_volume')
    parser.add_argument('--colour-mode',choices=('relative_normals','cycles_relief'),default='relative_normals')
    parser.add_argument('--closing-steps',type=int,choices=(0,1,2,3),default=3)
    args=parser.parse_args();trial(read(args.config),args.face_report,args.player,args.work_dir,args.opaque_base_triangles,args.base_mode,args.colour_mode,args.closing_steps)

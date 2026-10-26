"""Stage the v95 Manager mixer-route candidate without changing recordings.

The v94 device journal admits all requests but the listener hears no sound.
Use the native music bank's explicit MasterOut=0 / BUS8=1 sends instead of
the unverified direct-MasterOut route. Device audibility remains unproven.
The original bounded bank stays sealed; no global category/playlist edits.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from stage_indonesia_commentary import Utf, fnv64
from stage_player_commentary import rebuild_utf
from stage_trophy_music import row_copy

ROOT=Path(__file__).resolve().parents[1]
SOURCE_SHA="84bade692c7e577fecacb769988d4be9f2b2dcba08cbe99cc6ee207a5e242318"
ASSET="Audio/manager-league-v95.acb"


def repair(blob):
    if hashlib.sha256(blob).hexdigest()!=SOURCE_SHA:
        raise ValueError("sealed v94 bank identity differs")
    top=Utf(blob);strings=top.child("StringValueTable").rows
    if strings[1:3]!=[{"StringValue":"MasterOut"},{"StringValue":"BUS8"}]:
        raise ValueError("native bus string indices differ")
    commands=top.child("SeqCommandTable");rows=[]
    for i in range(len(commands.rows)):
        command=commands.blob(i,"Command")
        if len(command)!=14 or command[:3]!=bytes.fromhex("004404"):
            raise ValueError("v94 cue command envelope differs")
        if command[7:]!=struct.pack(">HBHH",0x6f,4,1,10000):
            raise ValueError("v94 direct-MasterOut route differs")
        rows.append({"Command":command[:7]+struct.pack(">HBHHHBHH",0x6f,4,1,0,0x6f,4,2,10000)})
    row=row_copy(top,0)
    row["SeqCommandTable"]=rebuild_utf(commands,rows,compact_blobs=True)
    row["Name"]="FNX_MANAGER_LEAGUE_V95"
    row["AcbGuid"]=hashlib.sha256(b"FNX_MANAGER_V95_ROUTE"+blob).digest()[:16]
    result=rebuild_utf(top,[row],compact_blobs=True)
    changed=Utf(result)
    for field in ("AwbFile","WaveformTable","WaveformExtensionDataTable","CueTable",
                  "CueNameTable","SequenceTable","TrackTable","SynthTable","TrackEventTable",
                  "StringValueTable","AcfMd5Hash"):
        if changed.blob(0,field)!=top.blob(0,field):
            raise ValueError("protected recording/graph/ACF changed: "+field)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--catalog",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if not out.is_relative_to(ROOT/"local-debug") or out.exists():
        p.error("choose a new ignored local-debug directory")
    blob=a.input.read_bytes();bank=repair(blob)
    header=a.catalog.read_text()
    if str(len(blob))+"u" not in header or f"0x{fnv64(blob):016x}" not in header:
        p.error("sealed catalog differs")
    header=header.replace('"Audio/manager-league-v94.acb"','"'+ASSET+'"')
    header=header.replace(f"{len(blob)}u",f"{len(bank)}u").replace(f"0x{fnv64(blob):016x}",f"0x{fnv64(bank):016x}")
    (out/ASSET).parent.mkdir(parents=True)
    (out/ASSET).write_bytes(bank);(out/"manager_league_audio_catalog.h").write_text(header)
    report={"asset":ASSET,"bank_bytes":len(bank),"sha256":hashlib.sha256(bank).hexdigest(),
        "source_sha256":SOURCE_SHA,"recordings_and_graph_exact":True,
        "native_bus_sends":{"MasterOut":0,"BUS8":1},"cue_local_gains_unchanged":True,
        "global_category_or_playlist_changes":False,"device_audibility_verified":False}
    (out/"AUDIO-REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":main()

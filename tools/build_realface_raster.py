"""Build the optional offline Windows raster helper with local Clang/Binutils."""
import argparse
from pathlib import Path
import subprocess
import sys

from realface_batch_inventory import write
from realface_pipeline import sha


def build(destination,clang='clang',linker='ld'):
    folder=Path(destination).resolve();folder.mkdir(parents=True,exist_ok=True)
    source=Path(__file__).with_name('realface_raster.c')
    obj=folder/'realface_raster.obj';dll=folder/'realface_raster.dll'
    subprocess.run([clang,'--target=x86_64-pc-windows-msvc','-O2','-ffp-contract=off',
                    '-fno-stack-protector','-c',str(source),'-o',str(obj)],check=True)
    subprocess.run([linker,'-mi386pep','--dll','--export-all-symbols','--entry','0',str(obj),'-o',str(dll)],check=True)
    write(folder/'build.json',dict(source_sha256=sha(source),dll_sha256=sha(dll),
        compile_flags=['-O2','-ffp-contract=off'],purpose='offline checks only'))
    return dll


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args();print(build(args.output))

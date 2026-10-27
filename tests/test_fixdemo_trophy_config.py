"""Production bootstrap I/O regression; synthetic fixtures, no proprietary data."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    "missing-marker", "valid-and-abi", "production-archive", "baseline", "marker-invalid",
    "marker-open", "marker-read", "marker-close",
    *(f"hash-mismatch-{i}" for i in range(4)),
    "asset-open", "asset-read", "asset-close", "asset-empty", "asset-size",
    "journal-create", "prior-open", "prior-seek", "prior-tell", "prior-close",
    "prior-remove", "prior-rename", "header-write", "header-close",
    "append-open", "append-seek", "append-tell", "append-write", "append-close",
    "two-boots", "journal-oversized", "journal-bounds", "event-bounds",
    "no-wait-writer", "hash-limit-clears",
]


@pytest.fixture(scope="module")
def bootstrap_executable(tmp_path_factory):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler required")
    build_dir = tmp_path_factory.mktemp("trophy-bootstrap-build")
    header = build_dir / "switch/crypto/sha256.h"
    header.parent.mkdir(parents=True)
    header.write_text(
        "#ifndef TEST_LIBNX_SHA256_H\n#define TEST_LIBNX_SHA256_H\n"
        "#include <stddef.h>\n"
        "typedef struct { unsigned char tag; int mixed; size_t bytes; } Sha256Context;\n"
        "void sha256ContextCreate(Sha256Context *);\n"
        "void sha256ContextUpdate(Sha256Context *, const void *, size_t);\n"
        "void sha256ContextGetHash(Sha256Context *, void *);\n"
        "#endif\n",
        encoding="utf-8",
    )
    executables = {}
    build_identity = build_dir / "build_identity.h"
    build_identity.write_text(
        '#define PESNX_BUILD_ID "0123456789abcdef0123456789abcdef01234567"\n',
        encoding="utf-8",
    )
    for identity in ("explicit", "unavailable"):
        executable = build_dir / f"trophy-bootstrap-{identity}.exe"
        flags = ["-include", build_identity.name] if identity == "explicit" else []
        build = subprocess.run(
            [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", *flags,
             "-I", str(build_dir), "-I", str(ROOT / "source"),
             str(ROOT / "tests/test_fixdemo_trophy_config.c"), "-o", str(executable)],
            capture_output=True, text=True, timeout=30,
        )
        assert build.returncode == 0, build.stdout + build.stderr
        executables[identity] = executable
    return executables


@pytest.mark.parametrize("scenario", CASES)
def test_bootstrap_actual_include(bootstrap_executable, tmp_path, scenario):
    (tmp_path / "LooseCpk").mkdir()
    (tmp_path / "PesMobile/Content/Paks").mkdir(parents=True)
    if scenario=='production-archive':
        import sys
        sys.path.insert(0,str(ROOT/'tools'))
        from pack_runtime_assets import pack_entries
        config=('PESNX_TROPHY_RUNTIME_V1\ncpk_sha256=3c2bc88b75211f08356f777d56b11e3430d3ea81815b4d165e35418da634c9a2\n'
            'manifest_sha256=123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0\n'
            'pak_sha256=18ac86c560e360b8a7f3caf4b4cff1200f0ad6a03ce0d4b92ed3976e12301d31\n').encode()
        pack_entries({'Runtime/trophy.cfg':config},tmp_path/'FootballNX.assets')
    result = subprocess.run(
        [str(bootstrap_executable["explicit"]), scenario], cwd=tmp_path,
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == f"trophy bootstrap actual include: {scenario} pass"


def test_missing_build_macro_reports_unavailable(bootstrap_executable, tmp_path):
    result = subprocess.run(
        [str(bootstrap_executable["unavailable"]), "missing-marker"], cwd=tmp_path,
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "build=unavailable" in (tmp_path / "scene-runtime.log").read_text()

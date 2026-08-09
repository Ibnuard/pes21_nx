#!/usr/bin/env python3
"""Build the offline HTTP fixtures from a user-supplied PES 2021 APK.

The APK remains the source for the original 48 JSON response schemas. This
tool applies the three small, project-owned compatibility overrides required
by PES 2021 NX, then emits the encrypted ``.bin`` files consumed by the JNI
HTTP shim. No APK response payload is stored in this repository.
"""

from __future__ import annotations

import argparse
import base64
import copy
import gzip
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

import msgpack
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, modes

try:
    from cryptography.hazmat.decrepit.ciphers.algorithms import Blowfish
except ImportError:  # cryptography < 43
    from cryptography.hazmat.primitives.ciphers.algorithms import Blowfish


APK_RESPONSE_PREFIX = "assets/responses/"
RESPONSE_KEY = bytes.fromhex(
    "a2df2319c1e5ec1e206a724b5709de77b728609eedbbfaaa939ab3d7bb4d7f77"
    "c135147cb76b4c2efa0249fad843a9d5cc38cae19cc41c90"
)

# The tested APK contains 48 response documents. The wrapper validates these
# encrypted sizes before loading libUE4, catching a wrong APK or stale output.
EXPECTED_PAYLOAD_SIZES = {
    "CMD_GET_SERVER_ENV.bin": 1608,
    "CmdCheckString.bin": 80,
    "CmdCreateUser.bin": 208,
    "CmdExtendMyclubCoach.bin": 120,
    "CmdExtendMyclubGameplayer.bin": 120,
    "CmdGetCountryList.bin": 2384,
    "CmdGetMaintenanceInfo.bin": 128,
    "CmdGetMyclubAchievementlist.bin": 176,
    "CmdGetMyclubAgentBoxInfo.bin": 144,
    "CmdGetMyclubAgentlist.bin": 376,
    "CmdGetMyclubCoachContractNorma.bin": 200,
    "CmdGetMyclubCommentaryInfo.bin": 440,
    "CmdGetMyclubEntryInfo.bin": 2520,
    "CmdGetMyclubMainmenuInfo.bin": 1272,
    "CmdGetMyclubMarketAgentlist.bin": 176,
    "CmdGetMyclubMatchStats.bin": 120,
    "CmdGetMyclubPresentlist.bin": 112,
    "CmdGetMyclubProcurableGameplayerlist.bin": 272,
    "CmdGetMyclubVscomOpponent.bin": 248,
    "CmdGetProductList.bin": 448,
    "CmdGetServerEnv.bin": 1608,
    "CmdLogin.bin": 2544,
    "CmdRecoverEnergy.bin": 112,
    "CmdSendDownloadStatsData.bin": 88,
    "CmdSendHeartbeat.bin": 96,
    "CmdSendMatchTeamInfo.bin": 112,
    "CmdSendPlaylog.bin": 72,
    "CmdSetDevicetoken.bin": 80,
    "CmdSetMatchResult.bin": 312,
    "CmdSetMyclubEntryInfo.bin": 2520,
    "CmdSetMyclubLanguage.bin": 80,
    "CmdSetMyclubLockGameplayer.bin": 104,
    "CmdSetMyclubMainSquad.bin": 96,
    "CmdSetMyclubSeasonUpdateInfo.bin": 104,
    "CmdSetMyclubSquadInfo.bin": 96,
    "CmdSetMyclubSquadName.bin": 96,
    "CmdSetMyclubTutorialAchievementInfo.bin": 104,
    "CmdSetMyclubUserInfo.bin": 88,
    "CmdSetUserUpdateInfo.bin": 80,
    "CmdStartMatch.bin": 216,
    "CmdUseMyclubAgent.bin": 632,
    "generic.bin": 56,
    "get_myclub_coaches_norma.bin": 200,
    "get_myclub_commentary_info.bin": 440,
    "get_myclub_mainmenu_info.bin": 1272,
    "get_product_list.bin": 448,
    "GetCountryList.bin": 2384,
    "set_myclub_entry_info.bin": 2520,
}


def build_formation_data() -> str:
    """Create the fixed-size neutral formation used by the stable baseline."""

    return base64.b64encode(bytes(792)).decode("ascii")


def load_apk_responses(apk: Path) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(apk) as archive:
        for info in archive.infolist():
            if not info.filename.startswith(APK_RESPONSE_PREFIX):
                continue
            name = info.filename.removeprefix(APK_RESPONSE_PREFIX)
            if "/" in name or not name.endswith(".json"):
                continue
            documents[name] = json.loads(archive.read(info).decode("utf-8"))
    if len(documents) != 48:
        raise RuntimeError(
            f"expected 48 response JSON files in the tested APK, found {len(documents)}"
        )
    return documents


def build_existing_account_entry(
    documents: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    # Keep the exact Liverpool/GetEntry schema used by working-baseline-0051.
    # The native ModeEntry patch drops the obsolete season-change/profile
    # event without replacing this stable command layout with the crash-prone
    # Barcelona Login fixture.
    entry = copy.deepcopy(documents["CmdGetMyclubEntryInfo.json"]["entry_info"])
    coach = entry["coach_list"][0]
    coach["formation_data"] = build_formation_data()
    coach["is_locked"] = "NO"

    # An empty default list marks this as an existing account. Leaving the APK
    # default here reopens the initial-manager onboarding flow.
    entry["default_coach_list"] = []
    entry["default_coach_list_num"] = 0
    players = entry["gameplayer_list"]
    entry["gameplayer_list_num"] = len(players)
    entry["total_get_player_num"] = len(players)
    first_serial = players[0]["gameplayer_id"]["serial"]
    for index, player in enumerate(players):
        player["gameplayer_id"]["serial"] = first_serial + index
    return entry


def add_preconfigured_user_agreements(login: dict[str, Any]) -> None:
    """Mark the bundled offline account's title agreements as complete.

    ``CmdLoginResult`` carries these values separately from ``entry_info``.
    The stock offline-server fixture omits them, so the native unpacker leaves
    ``ParameterCommon``'s Term-of-Use and Privacy-Policy flags false and opens
    the obsolete WebView agreement flow on every fresh installation.  Keep the
    normal login/profile initialization path while only setting the two fields
    consumed by ``ConvertUserAgreementsStatusFrom``.  Do not synthesize
    ``user_eula_info`` here: its nested wire layout varies by server revision,
    and an incorrect shape corrupts the native MsgPack result object.
    """

    login["user_agreements_status"] = {
        "term_of_use": "YES",
        "privacy_policy": "YES",
    }


def apply_compatibility_overrides(documents: dict[str, dict[str, Any]]) -> None:
    entry = build_existing_account_entry(documents)
    documents["CmdGetMyclubEntryInfo.json"]["entry_info"] = copy.deepcopy(entry)

    # Login and GetEntry must describe the same account. The stock APK mixes a
    # Barcelona login fixture with a malformed Liverpool GetEntry fixture.
    login = copy.deepcopy(documents["CmdGetMyclubEntryInfo.json"])
    login["msgid"] = "CMD_LOGIN"
    add_preconfigured_user_agreements(login)
    documents["CmdLogin.json"] = login

    # Profile edits use either spelling depending on the endpoint route.  A
    # stock SetEntry response would reintroduce the default-manager onboarding
    # record immediately after the corrected Login/GetEntry import.
    for name in ("CmdSetMyclubEntryInfo.json", "set_myclub_entry_info.json"):
        documents[name]["entry_info"] = copy.deepcopy(entry)


def encode_response(name: str, value: dict[str, Any]) -> bytes:
    packed = msgpack.packb(value, use_bin_type=True, use_single_float=False)
    compressed = gzip.compress(packed, compresslevel=6, mtime=0)
    iv = hashlib.sha256(name.encode("utf-8") + compressed).digest()[:8]
    padder = padding.PKCS7(Blowfish.block_size).padder()
    padded = padder.update(compressed) + padder.finalize()
    encryptor = Cipher(Blowfish(RESPONSE_KEY), modes.CBC(iv)).encryptor()
    return iv + encryptor.update(padded) + encryptor.finalize()


def write_responses(
    documents: dict[str, dict[str, Any]], output: Path, keep_json: bool
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    generated: dict[str, int] = {}
    for source_name in sorted(documents):
        value = documents[source_name]
        payload_name = f"{Path(source_name).stem}.bin"
        payload = encode_response(source_name, value)
        (output / payload_name).write_bytes(payload)
        generated[payload_name] = len(payload)
        if keep_json:
            (output / source_name).write_text(
                json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    if generated != EXPECTED_PAYLOAD_SIZES:
        mismatches = []
        for name in sorted(set(generated) | set(EXPECTED_PAYLOAD_SIZES)):
            actual = generated.get(name)
            expected = EXPECTED_PAYLOAD_SIZES.get(name)
            if actual != expected:
                mismatches.append(f"{name}: expected {expected}, generated {actual}")
        raise RuntimeError("response validation failed:\n  " + "\n  ".join(mismatches))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("apk", type=Path, help="legally obtained PES21.apk")
    parser.add_argument("output", type=Path, help="runtime assets/responses folder")
    parser.add_argument(
        "--keep-json",
        action="store_true",
        help="also keep the patched JSON documents for local debugging",
    )
    args = parser.parse_args()

    if not args.apk.is_file():
        parser.error(f"APK not found: {args.apk}")
    documents = load_apk_responses(args.apk)
    apply_compatibility_overrides(documents)
    write_responses(documents, args.output, args.keep_json)
    print(f"Generated and validated {len(documents)} offline responses in {args.output}")


if __name__ == "__main__":
    main()

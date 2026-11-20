"""Install the integrity-pinned official standalone CLI without npm/install scripts."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import tarfile
import tempfile
import urllib.request
from pathlib import Path

VERSION = "1.0.16"
INTEGRITY = (
    "Ksi06xvJSJcdhmfoDbpAnA84K4/pF+SkLsa5ZLvNruUc3e2EpoGaI6FcJXKTODvB/"
    "evprfy5pdRzW3lVazqfkA=="
)
BUNDLE_SHA256 = "194a66eb84094f3d8ee20fac0a2d6cae10a405cd59ac100b7e7880ebc97297da"
DESTINATION = Path(__file__).resolve().parents[2] / ".tools/flyai"


def main() -> None:
    url = f"https://registry.npmjs.org/@fly-ai/flyai-cli/-/flyai-cli-{VERSION}.tgz"
    with urllib.request.urlopen(url, timeout=30) as response:
        archive = response.read(2 * 1024 * 1024 + 1)
    if len(archive) > 2 * 1024 * 1024:
        raise RuntimeError("CLI archive exceeded installation limit.")
    if base64.b64encode(hashlib.sha512(archive).digest()).decode() != INTEGRITY:
        raise RuntimeError("CLI archive integrity mismatch.")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
        selected = {}
        for name in ("package/package.json", "package/dist/flyai-bundle.cjs"):
            member = package.getmember(name)
            if not member.isfile() or member.size > 1024 * 1024:
                raise RuntimeError("Invalid CLI package member.")
            stream = package.extractfile(member)
            if stream is None:
                raise RuntimeError("CLI package member is missing.")
            selected[name] = stream.read()
        metadata = json.loads(selected["package/package.json"])
        if metadata.get("name") != "@fly-ai/flyai-cli" or metadata.get("version") != VERSION:
            raise RuntimeError("CLI package identity mismatch.")
    bundle = selected["package/dist/flyai-bundle.cjs"]
    if hashlib.sha256(bundle).hexdigest() != BUNDLE_SHA256:
        raise RuntimeError("CLI bundle integrity mismatch.")

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".flyai-install-", dir=DESTINATION.parent) as temp:
        staging = Path(temp)
        staged_metadata = staging / "package.json"
        staged_bundle = staging / "dist/flyai-bundle.cjs"
        staged_bundle.parent.mkdir(parents=True)
        staged_metadata.write_bytes(selected["package/package.json"])
        staged_bundle.write_bytes(bundle)

        (DESTINATION / "dist").mkdir(parents=True, exist_ok=True)
        os.replace(staged_metadata, DESTINATION / "package.json")
        os.replace(staged_bundle, DESTINATION / "dist/flyai-bundle.cjs")
    print(
        f"Official FlyAI CLI {VERSION} installed; archive SHA-512 and bundle SHA-256 verified; "
        "no query executed."
    )


if __name__ == "__main__":
    main()

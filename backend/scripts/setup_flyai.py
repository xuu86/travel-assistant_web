"""Install the integrity-pinned official standalone CLI without npm/install scripts."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import tarfile
import urllib.request
from pathlib import Path

VERSION = "1.0.16"
INTEGRITY = (
    "Ksi06xvJSJcdhmfoDbpAnA84K4/pF+SkLsa5ZLvNruUc3e2EpoGaI6FcJXKTODvB/"
    "evprfy5pdRzW3lVazqfkA=="
)
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
        for name, body in selected.items():
            target = DESTINATION / name.removeprefix("package/")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
    print(f"Official FlyAI CLI {VERSION} installed; SHA-512 verified; no query executed.")


if __name__ == "__main__":
    main()

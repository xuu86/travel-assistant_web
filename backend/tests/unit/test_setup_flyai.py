from __future__ import annotations

import base64
import hashlib
import io
import json
import tarfile

import pytest

from app.modules.transport.providers import flyai
from scripts import setup_flyai


def package_archive(bundle: bytes) -> bytes:
    entries = {
        "package/package.json": json.dumps(
            {"name": "@fly-ai/flyai-cli", "version": setup_flyai.VERSION}
        ).encode(),
        "package/dist/flyai-bundle.cjs": bundle,
    }
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, body in entries.items():
            member = tarfile.TarInfo(name)
            member.size = len(body)
            archive.addfile(member, io.BytesIO(body))
    return output.getvalue()


def install_from_archive(monkeypatch, archive: bytes, destination, bundle: bytes) -> None:
    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(setup_flyai, "DESTINATION", destination)
    monkeypatch.setattr(setup_flyai, "BUNDLE_SHA256", hashlib.sha256(bundle).hexdigest())
    monkeypatch.setattr(
        setup_flyai,
        "INTEGRITY",
        base64.b64encode(hashlib.sha512(archive).digest()).decode(),
    )
    monkeypatch.setattr(
        setup_flyai.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: Response(archive),
    )


def test_installer_and_runtime_bundle_pins_match():
    assert setup_flyai.BUNDLE_SHA256 == flyai.CLI_SHA256


def test_installer_verifies_and_installs_pinned_bundle(tmp_path, monkeypatch, capsys):
    bundle = b"verified CLI bundle"
    archive = package_archive(bundle)
    destination = tmp_path / ".tools/flyai"
    install_from_archive(monkeypatch, archive, destination, bundle)

    setup_flyai.main()

    assert (destination / "package.json").is_file()
    assert (destination / "dist/flyai-bundle.cjs").read_bytes() == bundle
    assert "bundle SHA-256 verified" in capsys.readouterr().out
    assert not list(destination.parent.glob(".flyai-install-*"))


def test_installer_rejects_unpinned_bundle_without_replacing_existing(tmp_path, monkeypatch):
    original = b"previous valid bundle"
    archive_bundle = b"unexpected bundle"
    archive = package_archive(archive_bundle)
    destination = tmp_path / ".tools/flyai"
    target = destination / "dist/flyai-bundle.cjs"
    target.parent.mkdir(parents=True)
    target.write_bytes(original)
    install_from_archive(monkeypatch, archive, destination, b"different pinned bundle")

    with pytest.raises(RuntimeError, match="CLI bundle integrity mismatch"):
        setup_flyai.main()

    assert target.read_bytes() == original
    assert not (destination / "package.json").exists()

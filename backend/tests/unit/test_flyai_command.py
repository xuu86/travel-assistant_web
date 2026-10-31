from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess

import pytest

from app.modules.transport.contracts import FareQuery
from app.modules.transport.providers import flyai
from app.modules.transport.providers.base import TransportProviderError

KEY = "synthetic-flyai-key-never-log"


def query():
    return FareQuery.model_validate(
        {
            "origin": {"display_name": "上海"},
            "destination": {"display_name": "杭州"},
            "mode": "rail",
            "travel_date": "2026-11-01",
            "passenger_count": 1,
        }
    )


NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(
    NODE is None, reason="Node runtime is required for CLI isolation tests"
)


def test_command_passes_credentials_only_in_minimal_environment(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle.cjs"
    bundle.write_bytes(b"synthetic bundle")
    guard = tmp_path / "guard.cjs"
    guard.write_text(
        """let text=''; process.stdin.on('data',c=>text+=c);
process.stdin.on('end',()=>{
 const q=JSON.parse(text);
 const safe=process.argv.length===2 && q.origin==='上海' && q.date==='2026-11-01' &&
   !!process.env.FLYAI_API_KEY && !process.env.NODE_OPTIONS && !process.env.OTHER_SERVICE_SECRET &&
   !process.env.HTTPS_PROXY;
 console.log(JSON.stringify({safe}));
 console.error('FLYAI_APP_AUDIT='+JSON.stringify({fetch_count:1,authorization_matches:true,http_status:200}));
});""",
        encoding="utf-8",
    )
    monkeypatch.setattr(flyai, "_BUNDLE", bundle)
    monkeypatch.setattr(flyai, "CLI_SHA256", hashlib.sha256(bundle.read_bytes()).hexdigest())
    monkeypatch.setattr(flyai, "_GUARD", guard)
    monkeypatch.setenv("OTHER_SERVICE_SECRET", "private-test-secret")
    monkeypatch.setenv("NODE_OPTIONS", "--invalid-node-option")
    monkeypatch.setenv("HTTPS_PROXY", "https://invalid.test")
    output = flyai.FlyAICommand().run(query(), key=KEY, timeout=1, limit=1024)
    assert json.loads(output.stdout) == {"safe": True}
    assert output.http_status == 200 and output.authenticated and output.request_count == 1


def test_command_rejects_bundle_tampering_before_process_start(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle.cjs"
    bundle.write_bytes(b"changed")
    monkeypatch.setattr(flyai, "_BUNDLE", bundle)
    with pytest.raises(TransportProviderError):
        flyai.FlyAICommand().run(query(), key=KEY, timeout=1, limit=1024)


@pytest.mark.parametrize(
    "script",
    [
        "console.log('x'.repeat(10000))",
        "console.error('x'.repeat(70000))",
        "console.log(process.env.FLYAI_API_KEY)",
    ],
)
def test_bounded_process_output_never_exposes_secret(script, tmp_path, monkeypatch):
    guard = tmp_path / "guard.cjs"
    guard.write_text(script)
    monkeypatch.setattr(flyai, "_GUARD", guard)
    with pytest.raises(TransportProviderError):
        flyai.FlyAICommand._execute(NODE, {"FLYAI_API_KEY": KEY}, b"{}", KEY, 1, 1024)


def test_timeout_kills_and_reaps_process(monkeypatch, tmp_path):
    guard = tmp_path / "guard.cjs"
    guard.write_text("setInterval(()=>{},1000)")
    monkeypatch.setattr(flyai, "_GUARD", guard)
    # Exercise the real cleanup path immediately, independent of the 5-second production grace.
    original_wait = subprocess.Popen.wait
    timed_out = []

    def wait(process, timeout=None):
        if not timed_out:
            timed_out.append(process)
            raise subprocess.TimeoutExpired("synthetic", 0)
        return original_wait(process, timeout=timeout)

    monkeypatch.setattr(subprocess.Popen, "wait", wait)
    with pytest.raises(TransportProviderError):
        flyai.FlyAICommand._execute(NODE, {}, b"{}", KEY, 1, 1024)
    assert timed_out[0].poll() is not None


def test_concurrency_limit_rejects_without_launching(tmp_path, monkeypatch):
    bundle = tmp_path / "bundle"
    bundle.write_bytes(b"test")
    monkeypatch.setattr(flyai, "_BUNDLE", bundle)
    monkeypatch.setattr(flyai, "CLI_SHA256", hashlib.sha256(b"test").hexdigest())
    flyai._SLOTS.acquire()
    flyai._SLOTS.acquire()
    try:
        with pytest.raises(TransportProviderError) as exc:
            flyai.FlyAICommand().run(query(), key=KEY, timeout=1, limit=1024)
        assert exc.value.status == "rate_limited"
    finally:
        flyai._SLOTS.release()
        flyai._SLOTS.release()


@pytest.mark.parametrize("mode", ["valid", "wrong-host", "wrong-key", "retry", "oversized"])
def test_node_guard_enforces_network_boundary_with_fake_cli(mode, tmp_path):
    folder = tmp_path / "backend/app/modules/transport/providers"
    folder.mkdir(parents=True)
    guard = folder / "flyai_runner.cjs"
    shutil.copyfile(flyai._GUARD, guard)
    bundle_dir = tmp_path / ".tools/flyai/dist"
    bundle_dir.mkdir(parents=True)
    bundle = bundle_dir / "flyai-bundle.cjs"
    bundle.write_text(
        """const mode=process.env.TEST_MODE;
const url=mode==='wrong-host'?'https://invalid.test/mcp':'https://flyai.open.fliggy.com/mcp';
const authKey=mode==='wrong-key'?'bad':process.env.FLYAI_API_KEY;
const options={method:'POST',headers:{Authorization:'Bearer '+authKey},
body:JSON.stringify({method:'tools/call',params:{name:'search_domestic_train',arguments:{origin:'上海',destination:'杭州',depDate:'2026-11-01'}}})};
(async()=>{try {
 const result=await fetch(url,options);
 if(mode==='retry') await fetch(url,options);
 console.log(await result.text());
} catch { process.exitCode=1; }})();""",
        encoding="utf-8",
    )
    preload = tmp_path / "fake-fetch.cjs"
    preload.write_text("""globalThis.fetch=async(url,options)=>{
 if(options.redirect!=='error'||!options.signal) throw Error('boundary options');
 return new Response(process.env.TEST_MODE==='oversized'?'x'.repeat(2000):'{}',{status:200});
};""")
    result = subprocess.run(
        [NODE, "--require", str(preload), str(guard)],
        input=json.dumps({"origin": "上海", "destination": "杭州", "date": "2026-11-01"}).encode(),
        capture_output=True,
        timeout=5,
        env={
            **os.environ,
            "FLYAI_API_KEY": KEY,
            "FLYAI_APP_TIMEOUT_MS": "1000",
            "FLYAI_APP_MAX_RESPONSE_BYTES": "1024",
            "TEST_MODE": mode,
        },
    )
    assert KEY.encode() not in result.stdout + result.stderr
    audit = json.loads(result.stderr.decode().strip().removeprefix("FLYAI_APP_AUDIT="))
    if mode == "valid":
        assert result.returncode == 0 and audit["fetch_count"] == 1
        assert audit["authorization_matches"] and audit["http_status"] == 200
    else:
        assert result.returncode != 0

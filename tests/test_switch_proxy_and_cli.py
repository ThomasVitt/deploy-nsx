import json
import textwrap

import requests

from nsx_testkit import run
from nsx_testkit.switch import Mode, NSXSwitch


class TestProxyAndCli:
    def test_corporate_proxy_settings_do_not_hijack_fake_traffic(self, monkeypatch):
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")  # dead proxy
        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
        with NSXSwitch(Mode.FAKE):
            assert requests.patch("https://nsx.example/policy/api/v1/infra/x", json={}).status_code == 200

    def test_cli_runs_unmodified_script(self, tmp_path, monkeypatch):
        script = tmp_path / "my_deploy.py"
        script.write_text(textwrap.dedent("""
            import sys, requests
            s = requests.Session()
            s.patch("https://nsx.example/policy/api/v1/infra/services/" + sys.argv[1], json={"a": 1})
        """))
        record = tmp_path / "calls.json"
        run.main(["--mode", "fake", "--record", str(record), str(script), "svc1"])
        assert json.loads(record.read_text())[0]["path"] == "/policy/api/v1/infra/services/svc1"

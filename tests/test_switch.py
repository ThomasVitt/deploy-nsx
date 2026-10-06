import json

import pytest
import requests

from nsx_testkit.mocks import MockRegistry
from nsx_testkit.switch import Mode, NSXSwitch

REAL_HOST = "https://nsx-mgr.corp.example"
GROUPS = "/policy/api/v1/infra/domains/default/groups"


@pytest.fixture
def mock_file(tmp_path):
    path = tmp_path / "gets.json"
    path.write_text(json.dumps({"mocks": [
        {"path": GROUPS, "status": 200, "body": {"results": [{"id": "legacy"}], "cursor": "c2"}},
        {"path": GROUPS, "query": {"cursor": "c2"}, "body": {"results": [{"id": "legacy2"}]}},
        {"path": "/api/v1/cluster/status", "responses": [
            {"status": 200, "body": {"state": "STABLE"}},
            {"status": 503, "body": {"error": "busy"}},
        ]},
    ]}))
    return path


class TestFakeMode:
    def test_unmodified_requests_code_is_redirected_and_recorded(self, tmp_path, mock_file):
        record = tmp_path / "calls.json"
        with NSXSwitch(Mode.FAKE, record_to=record, mocks=[mock_file]):
            session = requests.Session()  # "existing code" targeting a real hostname
            session.auth = ("admin", "pw")
            assert session.patch(f"{REAL_HOST}{GROUPS}/new", json={"display_name": "new"}).status_code == 200
            assert requests.get(f"{REAL_HOST}{GROUPS}").json()["results"] == [{"id": "legacy"}]

        calls = json.loads(record.read_text())
        assert [(c["method"], c["path"]) for c in calls] == [("GET", GROUPS), ("PATCH", f"{GROUPS}/new")]

    def test_query_specific_and_sequenced_mocks(self, mock_file):
        with NSXSwitch(Mode.FAKE, mocks=[mock_file]):
            assert requests.get(f"{REAL_HOST}{GROUPS}", params={"cursor": "c2"}).json() == {"results": [{"id": "legacy2"}]}
            statuses = [requests.get(f"{REAL_HOST}/api/v1/cluster/status").status_code for _ in range(3)]
        assert statuses == [200, 503, 503]

    def test_get_falls_back_to_objects_deployed_in_same_run(self):
        with NSXSwitch(Mode.FAKE):
            requests.patch(f"{REAL_HOST}{GROUPS}/g1", json={"display_name": "g1"})
            assert requests.get(f"{REAL_HOST}{GROUPS}/g1").json()["display_name"] == "g1"
            assert requests.get(f"{REAL_HOST}{GROUPS}").json()["result_count"] == 1
            assert requests.get(f"{REAL_HOST}/nothing/here").status_code == 404

    def test_from_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("NSX_MODE", "fake")
        monkeypatch.setenv("NSX_RECORD_FILE", str(tmp_path / "c.json"))
        with NSXSwitch.from_env():
            requests.delete(f"{REAL_HOST}{GROUPS}/x")
        assert json.loads((tmp_path / "c.json").read_text())[0]["method"] == "DELETE"


class TestRealModeCapture:
    def test_real_get_responses_are_captured_as_mocks(self, tmp_path, mock_file):
        # A second fake plays the "real" manager here; capture must not redirect anything.
        from nsx_testkit.fake_nsx import FakeNSX
        captured = tmp_path / "captured.json"
        with FakeNSX(MockRegistry.load(mock_file)) as upstream:
            with NSXSwitch(Mode.REAL, capture_gets=captured):
                requests.get(upstream.url + GROUPS, params={"cursor": "c2"})
                requests.patch(upstream.url + GROUPS + "/p", json={})  # not captured
        data = json.loads(captured.read_text())["mocks"]
        assert len(data) == 1 and data[0]["query"] == {"cursor": "c2"}
        assert data[0]["responses"][0]["body"] == {"results": [{"id": "legacy2"}]}
        MockRegistry.load(captured)  # round-trips

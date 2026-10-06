import os
from pathlib import Path

import pytest

from example.deploy import NSXDeployer
from nsx_testkit.compare import RecordingDiff
from nsx_testkit.fake_nsx import FakeNSX
from nsx_testkit.recording import Recording


class TestDeploySnapshot:
    SNAPSHOT = Path(__file__).parent / "snapshots" / "deploy.json"

    @pytest.fixture
    def nsx(self):
        with FakeNSX() as server:
            yield server

    def test_deploy_api_calls_unchanged(self, nsx):
        NSXDeployer(nsx.url).deploy()
        assert len(nsx.calls) == 500
        current = Recording.from_raw(nsx.calls)

        if os.environ.get("UPDATE_SNAPSHOT") or not self.SNAPSHOT.exists():
            current.save(self.SNAPSHOT)
            return

        diff = RecordingDiff.between(Recording.load(self.SNAPSHOT), current)
        assert not diff.differs, "API calls changed vs snapshot:\n" + diff.report()

import os

from example.deploy import deploy
from nsx_testkit.compare import load, report
from nsx_testkit.normalize import normalize
from nsx_testkit.record import save

SNAPSHOT = os.path.join(os.path.dirname(__file__), "snapshots", "deploy.json")


def test_deploy_api_calls_unchanged(nsx):
    deploy(nsx.url)
    assert len(nsx.calls) == 500

    if os.environ.get("UPDATE_SNAPSHOT") or not os.path.exists(SNAPSHOT):
        save(nsx.calls, SNAPSHOT)
        return

    text, differs = report(load(SNAPSHOT), normalize(nsx.calls))
    assert not differs, "API calls changed vs snapshot:\n" + text

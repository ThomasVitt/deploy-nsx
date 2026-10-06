# deploy-nsx test kit

Run existing `requests`-based NSX deployment code against a fake NSX manager, record every
API call as JSON, and compare recordings between code versions.

## Switching between real and fake (no code changes)

```bash
# fake NSX: calls are redirected locally, all transmitted calls land in calls.json
python -m nsx_testkit.run --mode fake --record calls.json --mocks gets.json deploy.py --your args

# real NSX, and capture every GET response as a reusable mock file
python -m nsx_testkit.run --mode real --capture-gets gets.json deploy.py --your args
```

Or in code / pytest:

```python
from nsx_testkit.switch import NSXSwitch, Mode

with NSXSwitch(Mode.FAKE, record_to="calls.json", mocks=["gets.json"]):
    run_my_deployment()          # unchanged code, any hostname

with NSXSwitch.from_env():       # NSX_MODE=real|fake, NSX_RECORD_FILE, NSX_GET_MOCKS, NSX_CAPTURE_GETS
    run_my_deployment()
```

Interception is done on `requests.Session.get_adapter`, so `requests.get(...)`, sessions and
custom sessions are all covered. TLS and proxy settings are bypassed for fake traffic.
Not covered: code that bypasses `requests` (raw `urllib3`, `httpx`, ...).

## Mocking GET responses

`gets.json` (capture it with `--capture-gets`, or write it by hand):

```json
{"mocks": [
  {"path": "/policy/api/v1/infra/domains/default/groups",
   "body": {"results": [], "cursor": "c2"}},
  {"path": "/policy/api/v1/infra/domains/default/groups", "query": {"cursor": "c2"},
   "body": {"results": []}},
  {"method": "GET", "path": "/api/v1/cluster/status", "responses": [
     {"status": 200, "body": {"state": "STABLE"}},
     {"status": 503, "body": {"error": "busy"}}]}
]}
```

* A mock with a `query` matches only that exact query; one without matches any query.
* `responses` are served in order, the last repeats (polling, eventual consistency).
* Any method can be mocked via `"method"`.
* Without a mock, a GET is answered from objects PUT/PATCHed earlier in the same run
  (collections return `{"results": [...]}`), otherwise 404. Unanswered requests are
  logged as warnings.
* Captured files contain real response bodies: review them before committing.

## Comparing recordings

```bash
python -m nsx_testkit.compare old_calls.json new_calls.json   # exit code 1 if different
```

The snapshot test in `tests/test_deploy_snapshot.py` does this automatically
(`UPDATE_SNAPSHOT=1 pytest` accepts a new baseline).

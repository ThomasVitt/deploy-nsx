"""Turn raw captured calls into a stable, diff-friendly form."""
import json

# Fields NSX (or the fake) generates; they change per run and are noise in a diff.
VOLATILE_KEYS = {
    "_revision", "_create_time", "_create_user", "_last_modified_time",
    "_last_modified_user", "_system_owned", "_protection", "unique_id",
}


def scrub(value):
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in sorted(value.items()) if k not in VOLATILE_KEYS}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def normalize(calls, ordered=False):
    """Scrub volatile fields. Unless ordered=True, sort so that concurrency or
    reordering in the deploy code does not produce false diffs."""
    out = [
        {
            "method": c["method"],
            "path": c["path"],
            "query": dict(sorted(c.get("query", {}).items())),
            "body": scrub(c.get("body")),
            "status": c["status"],
        }
        for c in calls
    ]
    if not ordered:
        out.sort(key=lambda c: (c["path"], c["method"], canonical(c["query"]), canonical(c["body"])))
    return out

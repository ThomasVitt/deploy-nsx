"""Compare two recordings.  Usage: python -m nsx_testkit.compare old.json new.json"""
import difflib
import json
import sys
from collections import defaultdict

from .normalize import canonical


def load(path):
    with open(path) as f:
        return json.load(f)


def _index(calls):
    seen = defaultdict(int)
    out = {}
    for c in calls:
        key = (c["method"], c["path"], canonical(c["query"]))
        out[key + (seen[key],)] = c
        seen[key] += 1
    return out


def diff_calls(old, new):
    """Return (added, removed, changed) lists of calls keyed by method+path(+query)."""
    a, b = _index(old), _index(new)
    added = [b[k] for k in b.keys() - a.keys()]
    removed = [a[k] for k in a.keys() - b.keys()]
    changed = [(a[k], b[k]) for k in a.keys() & b.keys() if a[k] != b[k]]
    return added, removed, changed


def report(old, new):
    added, removed, changed = diff_calls(old, new)
    lines = [f"calls: {len(old)} -> {len(new)}  (+{len(added)} -{len(removed)} ~{len(changed)})"]
    for c in sorted(added, key=lambda c: c["path"]):
        lines.append(f"+ {c['method']} {c['path']}")
    for c in sorted(removed, key=lambda c: c["path"]):
        lines.append(f"- {c['method']} {c['path']}")
    for o, n in sorted(changed, key=lambda p: p[0]["path"]):
        lines.append(f"~ {n['method']} {n['path']}")
        d = difflib.unified_diff(
            json.dumps(o, indent=2, sort_keys=True).splitlines(),
            json.dumps(n, indent=2, sort_keys=True).splitlines(),
            lineterm="", n=1,
        )
        lines.extend("    " + x for x in list(d)[2:])
    return "\n".join(lines), bool(added or removed or changed)


if __name__ == "__main__":
    text, differs = report(load(sys.argv[1]), load(sys.argv[2]))
    print(text)
    sys.exit(1 if differs else 0)

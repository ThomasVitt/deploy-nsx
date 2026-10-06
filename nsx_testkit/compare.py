"""Compare two recordings.  Usage: python -m nsx_testkit.compare old.json new.json"""
import difflib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass

from .normalize import CallNormalizer
from .recording import Recording


@dataclass(frozen=True)
class RecordingDiff:
    """Calls added, removed or changed, keyed by method + path + query."""
    old_count: int
    new_count: int
    added: list[dict]
    removed: list[dict]
    changed: list[tuple[dict, dict]]

    @classmethod
    def between(cls, old: Recording, new: Recording) -> "RecordingDiff":
        a, b = cls._index(old.calls), cls._index(new.calls)
        return cls(
            old_count=len(old),
            new_count=len(new),
            added=[b[k] for k in b.keys() - a.keys()],
            removed=[a[k] for k in a.keys() - b.keys()],
            changed=[(a[k], b[k]) for k in a.keys() & b.keys() if a[k] != b[k]],
        )

    @staticmethod
    def _index(calls: list[dict]) -> dict:
        seen = defaultdict(int)
        out = {}
        for c in calls:
            key = (c["method"], c["path"], CallNormalizer.canonical(c["query"]))
            out[key + (seen[key],)] = c
            seen[key] += 1
        return out

    @property
    def differs(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    def report(self) -> str:
        lines = [f"calls: {self.old_count} -> {self.new_count}  "
                 f"(+{len(self.added)} -{len(self.removed)} ~{len(self.changed)})"]
        lines += [f"+ {c['method']} {c['path']}" for c in sorted(self.added, key=lambda c: c["path"])]
        lines += [f"- {c['method']} {c['path']}" for c in sorted(self.removed, key=lambda c: c["path"])]
        for old, new in sorted(self.changed, key=lambda p: p[0]["path"]):
            lines.append(f"~ {new['method']} {new['path']}")
            diff = difflib.unified_diff(
                json.dumps(old, indent=2, sort_keys=True).splitlines(),
                json.dumps(new, indent=2, sort_keys=True).splitlines(),
                lineterm="", n=1,
            )
            lines.extend("    " + line for line in list(diff)[2:])
        return "\n".join(lines)


def main(argv=None) -> int:
    old_path, new_path = (argv or sys.argv[1:])[:2]
    diff = RecordingDiff.between(Recording.load(old_path), Recording.load(new_path))
    print(diff.report())
    return 1 if diff.differs else 0


if __name__ == "__main__":
    sys.exit(main())

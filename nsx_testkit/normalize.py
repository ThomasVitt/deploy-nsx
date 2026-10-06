"""Turn raw captured calls into a stable, diff-friendly form."""
import json
from typing import Any


class CallNormalizer:
    """Scrubs volatile fields and (optionally) sorts calls so diffs show real changes only."""

    # Fields NSX (or the fake) generates; they change per run and are noise in a diff.
    VOLATILE_KEYS = frozenset({
        "_revision", "_create_time", "_create_user", "_last_modified_time",
        "_last_modified_user", "_system_owned", "_protection", "unique_id",
    })

    def __init__(self, ordered: bool = False, volatile_keys=None):
        """ordered=False sorts calls, so concurrency or reordering in the deploy
        code does not produce false diffs. Use ordered=True if call order matters."""
        self.ordered = ordered
        self.volatile_keys = frozenset(volatile_keys) if volatile_keys else self.VOLATILE_KEYS

    def scrub(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self.scrub(v) for k, v in sorted(value.items()) if k not in self.volatile_keys}
        if isinstance(value, list):
            return [self.scrub(v) for v in value]
        return value

    @staticmethod
    def canonical(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    def normalize(self, calls: list[dict]) -> list[dict]:
        out = [
            {
                "method": c["method"],
                "path": c["path"],
                "query": dict(sorted(c.get("query", {}).items())),
                "body": self.scrub(c.get("body")),
                "status": c["status"],
            }
            for c in calls
        ]
        if not self.ordered:
            out.sort(key=lambda c: (c["path"], c["method"],
                                    self.canonical(c["query"]), self.canonical(c["body"])))
        return out

"""A normalized, persistable set of recorded API calls."""
import json
from dataclasses import dataclass
from pathlib import Path

from .normalize import CallNormalizer


@dataclass(frozen=True)
class Recording:
    calls: list[dict]

    @classmethod
    def from_raw(cls, raw_calls, normalizer: CallNormalizer | None = None) -> "Recording":
        return cls((normalizer or CallNormalizer()).normalize(list(raw_calls)))

    @classmethod
    def load(cls, path) -> "Recording":
        return cls(json.loads(Path(path).read_text()))

    def save(self, path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.calls, indent=2, sort_keys=True) + "\n")

    def __len__(self) -> int:
        return len(self.calls)

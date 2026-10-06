"""Canned responses (e.g. real GET responses captured from NSX) for the fake NSX.

File format (JSON)::

    {"mocks": [
      {"method": "GET",
       "path": "/policy/api/v1/infra/domains/default/groups",
       "query": {"cursor": "abc"},            # optional; omitted = matches any query
       "responses": [                          # served in order, the last one repeats
         {"status": 200, "body": {"results": []}, "headers": {"X-Foo": "bar"}}
       ]}
    ]}

``"status"``/``"body"`` directly on the mock is shorthand for a single response.
An entry whose ``query`` equals the request's query wins over an entry without one.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class MockResponse:
    status: int = 200
    body: object = None
    headers: dict = field(default_factory=dict)


@dataclass
class Mock:
    method: str
    path: str
    query: dict | None
    responses: list[MockResponse]
    served: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "Mock":
        raw = data.get("responses") or [{k: data[k] for k in ("status", "body", "headers") if k in data}]
        return cls(
            method=data.get("method", "GET").upper(),
            path=data["path"],
            query=data.get("query"),
            responses=[MockResponse(**r) for r in raw],
        )

    def to_dict(self) -> dict:
        out = {"method": self.method, "path": self.path,
               "responses": [{"status": r.status, "body": r.body, **({"headers": r.headers} if r.headers else {})}
                             for r in self.responses]}
        if self.query is not None:
            out["query"] = self.query
        return out

    def next_response(self) -> MockResponse:
        response = self.responses[min(self.served, len(self.responses) - 1)]
        self.served += 1
        return response


class MockRegistry:
    """Holds mocks and matches incoming requests against them."""

    def __init__(self, mocks: list[Mock] | None = None):
        self.mocks: list[Mock] = list(mocks or [])
        self.unmatched: list[tuple[str, str, dict]] = []  # requests no mock answered

    @classmethod
    def load(cls, *paths) -> "MockRegistry":
        registry = cls()
        for path in paths:
            data = json.loads(Path(path).read_text())
            registry.mocks += [Mock.from_dict(m) for m in data["mocks"]]
        return registry

    def save(self, path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"mocks": [m.to_dict() for m in self.mocks]}, indent=2) + "\n")

    def add(self, method: str, path: str, query: dict, response: MockResponse) -> None:
        """Append a response; repeated identical requests become an ordered sequence."""
        for mock in self.mocks:
            if (mock.method, mock.path, mock.query) == (method, path, query):
                mock.responses.append(response)
                return
        self.mocks.append(Mock(method, path, query, [response]))

    def match(self, method: str, path: str, query: dict) -> MockResponse | None:
        candidates = [m for m in self.mocks if m.method == method and m.path == path]
        exact = [m for m in candidates if m.query == query]
        wildcard = [m for m in candidates if m.query is None]
        for mock in exact + wildcard:
            return mock.next_response()
        return None

    def note_unmatched(self, method: str, path: str, query: dict) -> None:
        self.unmatched.append((method, path, query))

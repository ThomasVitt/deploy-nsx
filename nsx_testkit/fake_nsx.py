"""A minimal fake NSX manager that records every request it receives."""
import socket
import threading
import time

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from .mocks import MockRegistry


class FakeNSXApp:
    """The FastAPI application: answers from mocks or its object store, records raw calls."""

    POLICY_PREFIX = "/policy/api/v1"

    def __init__(self, mocks: MockRegistry | None = None):
        self.mocks = mocks or MockRegistry()
        self.objects: dict[str, dict] = {}  # policy path -> stored object
        self.calls: list[dict] = []         # raw recorded requests, in arrival order
        self._lock = threading.Lock()
        self.api = FastAPI(title="Fake NSX")
        self.api.add_api_route(
            "/{path:path}", self.handle,
            methods=["GET", "PUT", "PATCH", "POST", "DELETE"],
        )

    def reset(self) -> None:
        with self._lock:
            self.calls.clear()
            self.objects.clear()

    async def handle(self, path: str, request: Request):
        raw = await request.body()
        try:
            body = await request.json() if raw else None
        except ValueError:
            return JSONResponse({"error_code": 500, "error_message": "invalid JSON"}, status_code=400)

        full_path = "/" + path
        query = dict(request.query_params)
        with self._lock:
            status, payload, headers = self._answer(request.method, full_path, query, body)
            self.calls.append({
                "method": request.method, "path": full_path,
                "query": query, "body": body, "status": status,
            })

        if payload is None:
            return Response(status_code=status, headers=headers)
        return JSONResponse(payload, status_code=status, headers=headers)

    def _answer(self, method: str, full_path: str, query: dict, body):
        """Return (status, payload or None, headers). Mocks take priority over the store."""
        mocked = self.mocks.match(method, full_path, query)
        if mocked is not None:
            return mocked.status, mocked.body, mocked.headers

        key = full_path.removeprefix(self.POLICY_PREFIX)
        if method in ("PUT", "PATCH"):
            obj = dict(body or {})
            obj["path"] = key
            obj["id"] = key.rsplit("/", 1)[-1]
            obj["_revision"] = self.objects.get(key, {}).get("_revision", -1) + 1
            self.objects[key] = obj
            return 200, (obj if method == "PUT" else None), {}
        if method == "GET":
            if key in self.objects:
                return 200, self.objects[key], {}
            children = [o for k, o in self.objects.items() if k.rsplit("/", 1)[0] == key]
            if children:  # behave like an NSX collection GET
                return 200, {"results": children, "result_count": len(children)}, {}
            self.mocks.note_unmatched(method, full_path, query)
            return 404, {"error_code": 600, "error_message": f"{full_path} not found"}, {}
        if method == "DELETE":
            self.objects.pop(key, None)
        else:
            self.mocks.note_unmatched(method, full_path, query)
        return 200, None, {}


class FakeNSX:
    """Runs FakeNSXApp on a real localhost port. Use as a context manager."""

    def __init__(self, mocks: MockRegistry | None = None):
        self.app = FakeNSXApp(mocks)
        self.url: str | None = None
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def calls(self) -> list[dict]:
        return self.app.calls

    @property
    def mocks(self) -> MockRegistry:
        return self.app.mocks

    def reset(self) -> None:
        self.app.reset()

    def start(self) -> "FakeNSX":
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        self.url = f"http://127.0.0.1:{sock.getsockname()[1]}"
        self._server = uvicorn.Server(uvicorn.Config(self.app.api, log_level="warning"))
        self._thread = threading.Thread(target=self._server.run, kwargs={"sockets": [sock]}, daemon=True)
        self._thread.start()
        while not self._server.started:
            time.sleep(0.01)
        return self

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)

    def __enter__(self) -> "FakeNSX":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

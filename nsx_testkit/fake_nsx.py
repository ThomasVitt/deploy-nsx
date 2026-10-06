"""A minimal fake NSX Policy manager that records every request it receives."""
import socket
import threading
import time

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse


class FakeNSXApp:
    """The FastAPI application: stores objects and records raw calls."""

    API_PREFIX = "/policy/api/v1"

    def __init__(self):
        self.objects: dict[str, dict] = {}  # path -> stored object
        self.calls: list[dict] = []         # raw recorded requests, in arrival order
        self._lock = threading.Lock()
        self.api = FastAPI(title="Fake NSX")
        self.api.add_api_route(
            self.API_PREFIX + "/{path:path}", self.handle,
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

        key = "/" + path
        with self._lock:
            status, payload = self._apply(request.method, key, body)
            self.calls.append({
                "method": request.method,
                "path": f"{self.API_PREFIX}/{path}",
                "query": dict(request.query_params),
                "body": body,
                "status": status,
            })

        if payload is None:
            return Response(status_code=status)
        return JSONResponse(payload, status_code=status)

    def _apply(self, method: str, key: str, body):
        """Mutate the store; return (status, response payload or None)."""
        if method in ("PUT", "PATCH"):
            obj = dict(body or {})
            obj["path"] = key
            obj["id"] = key.rsplit("/", 1)[-1]
            obj["_revision"] = self.objects.get(key, {}).get("_revision", -1) + 1
            self.objects[key] = obj
            return 200, (obj if method == "PUT" else None)
        if method == "GET":
            if key in self.objects:
                return 200, self.objects[key]
            return 404, {"error_code": 600, "error_message": f"{self.API_PREFIX}{key} not found"}
        if method == "DELETE":
            self.objects.pop(key, None)
        return 200, None


class FakeNSX:
    """Runs FakeNSXApp on a real localhost port. Use as a context manager."""

    def __init__(self):
        self.app = FakeNSXApp()
        self.url: str | None = None
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def calls(self) -> list[dict]:
        return self.app.calls

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

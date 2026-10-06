"""A minimal fake NSX Policy manager that records every request it receives."""
import socket
import threading
import time
from contextlib import contextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

API_PREFIX = "/policy/api/v1"


def create_app():
    app = FastAPI(title="Fake NSX")
    app.state.objects = {}  # path -> stored object
    app.state.calls = []    # raw recorded requests, in arrival order
    lock = threading.Lock()

    @app.api_route(API_PREFIX + "/{path:path}", methods=["GET", "PUT", "PATCH", "POST", "DELETE"])
    async def policy(path: str, request: Request):
        raw = await request.body()
        try:
            body = await request.json() if raw else None
        except ValueError:
            return JSONResponse({"error_code": 500, "error_message": "invalid JSON"}, status_code=400)

        full = f"{API_PREFIX}/{path}"
        method = request.method
        store = app.state.objects
        status, payload = 200, None

        with lock:
            if method in ("PUT", "PATCH"):
                obj = dict(body or {})
                obj["path"] = "/" + path
                obj["id"] = path.rsplit("/", 1)[-1]
                obj["_revision"] = store.get("/" + path, {}).get("_revision", -1) + 1
                store["/" + path] = obj
                payload = obj if method == "PUT" else None
            elif method == "GET":
                if "/" + path in store:
                    payload = store["/" + path]
                else:
                    status = 404
                    payload = {"error_code": 600, "error_message": f"{full} not found"}
            elif method == "DELETE":
                store.pop("/" + path, None)

            app.state.calls.append({
                "method": method,
                "path": full,
                "query": dict(request.query_params),
                "body": body,
                "status": status,
            })

        if payload is None:
            return Response(status_code=status)
        return JSONResponse(payload, status_code=status)

    return app


class FakeNSX:
    def __init__(self):
        self.app = create_app()
        self.url = None
        self._server = None
        self._thread = None

    @property
    def calls(self):
        return self.app.state.calls

    def reset(self):
        self.app.state.calls.clear()
        self.app.state.objects.clear()

    def start(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        self.url = f"http://127.0.0.1:{sock.getsockname()[1]}"
        self._server = uvicorn.Server(uvicorn.Config(self.app, log_level="warning"))
        self._thread = threading.Thread(target=self._server.run, kwargs={"sockets": [sock]}, daemon=True)
        self._thread.start()
        while not self._server.started:
            time.sleep(0.01)
        return self

    def stop(self):
        self._server.should_exit = True
        self._thread.join(timeout=5)


@contextmanager
def fake_nsx():
    nsx = FakeNSX().start()
    try:
        yield nsx
    finally:
        nsx.stop()

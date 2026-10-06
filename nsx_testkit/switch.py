"""Switch existing ``requests``-based NSX code between the real manager and the fake.

Nothing in the deployment code has to change: while an ``NSXSwitch`` is active,
every ``requests`` call (``requests.get``, ``Session.patch`` ...) is intercepted at
the adapter level.

* ``Mode.REAL``  – requests go to the real NSX unchanged. Optionally every GET
  response is captured into a mock file (``capture_gets``), ready to be replayed.
* ``Mode.FAKE``  – requests are redirected to a local FakeNSX, GETs are answered from
  the mock file, and all transmitted calls are written to ``record_to`` as JSON.
"""
import enum
import logging
import os
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qsl, urlsplit

import requests

from .fake_nsx import FakeNSX
from .mocks import MockRegistry, MockResponse
from .normalize import CallNormalizer
from .recording import Recording

log = logging.getLogger("nsx_testkit")


class Mode(enum.Enum):
    REAL = "real"
    FAKE = "fake"


class AdapterProxy:
    """Wraps a session's real transport adapter; subclasses hook ``send``."""

    def __init__(self, adapter):
        self._adapter = adapter

    def send(self, request, **kwargs):
        return self._adapter.send(request, **kwargs)

    def __getattr__(self, name):
        return getattr(self._adapter, name)


class RedirectAdapter(AdapterProxy):
    """Rewrites scheme+host of every request to the fake server, keeping path and query."""

    def __init__(self, adapter, target_url: str):
        super().__init__(adapter)
        self._target = urlsplit(target_url)

    def send(self, request, **kwargs):
        parts = urlsplit(request.url)
        request.url = parts._replace(scheme=self._target.scheme, netloc=self._target.netloc).geturl()
        kwargs["proxies"] = {}  # proxy settings were resolved for the real host; the fake is local
        return super().send(request, **kwargs)


class GetCaptureAdapter(AdapterProxy):
    """Passes requests to the real NSX and stores each GET response as a mock."""

    def __init__(self, adapter, registry: MockRegistry):
        super().__init__(adapter)
        self._registry = registry

    def send(self, request, **kwargs):
        response = super().send(request, **kwargs)
        if request.method == "GET":
            parts = urlsplit(request.url)
            try:
                body = response.json()
            except ValueError:
                body = None
            self._registry.add("GET", parts.path, dict(parse_qsl(parts.query)),
                               MockResponse(status=response.status_code, body=body))
        return response


class NSXSwitch:
    """Context manager that activates the chosen mode around your deployment code."""

    def __init__(self, mode: Mode = Mode.FAKE, record_to=None, mocks=(), capture_gets=None,
                 normalizer: CallNormalizer | None = None):
        self.mode = Mode(mode)
        self.record_to = Path(record_to) if record_to else None
        self.mock_files = [Path(m) for m in mocks]
        self.capture_gets = Path(capture_gets) if capture_gets else None
        self.normalizer = normalizer or CallNormalizer()
        self.fake: FakeNSX | None = None
        self.captured = MockRegistry()
        self._patch = None

    @classmethod
    def from_env(cls) -> "NSXSwitch":
        """NSX_MODE=real|fake (default real), NSX_RECORD_FILE, NSX_GET_MOCKS (os.pathsep
        separated), NSX_CAPTURE_GETS."""
        mocks = os.environ.get("NSX_GET_MOCKS", "")
        return cls(
            mode=Mode(os.environ.get("NSX_MODE", "real")),
            record_to=os.environ.get("NSX_RECORD_FILE"),
            mocks=[m for m in mocks.split(os.pathsep) if m],
            capture_gets=os.environ.get("NSX_CAPTURE_GETS"),
        )

    def __enter__(self) -> "NSXSwitch":
        original = requests.Session.get_adapter
        if self.mode is Mode.FAKE:
            self.fake = FakeNSX(MockRegistry.load(*self.mock_files)).start()
            wrap = lambda adapter: RedirectAdapter(adapter, self.fake.url)  # noqa: E731
        elif self.capture_gets:
            wrap = lambda adapter: GetCaptureAdapter(adapter, self.captured)  # noqa: E731
        else:
            return self
        self._patch = mock.patch.object(
            requests.Session, "get_adapter", lambda session, url: wrap(original(session, url)))
        self._patch.start()
        return self

    def __exit__(self, *exc) -> None:
        if self._patch:
            self._patch.stop()
        if self.fake:
            self.fake.stop()
            if self.record_to:
                Recording.from_raw(self.fake.calls, self.normalizer).save(self.record_to)
                log.info("wrote %d API calls to %s", len(self.fake.calls), self.record_to)
            for method, path, query in self.fake.mocks.unmatched:
                log.warning("no mock for %s %s %s", method, path, query or "")
        if self.capture_gets and self.captured.mocks:
            self.captured.save(self.capture_gets)
            log.info("captured GET responses to %s", self.capture_gets)

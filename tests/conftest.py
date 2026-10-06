import pytest

from nsx_testkit.fake_nsx import fake_nsx


@pytest.fixture
def nsx():
    with fake_nsx() as server:
        yield server

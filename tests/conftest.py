from __future__ import annotations

import pytest

from ddpe.connect import TokenCache


@pytest.fixture(autouse=True)
def clear_token_cache():
    TokenCache.clear()
    yield
    TokenCache.clear()

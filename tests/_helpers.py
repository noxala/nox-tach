# tests/_helpers.py
from __future__ import annotations

import re

import pytest


def assert_raises_msg[E: BaseException](
    exception: type[E], message: str
) -> pytest.RaisesExc[E]:
    """Match a literal message fragment, preserving the extracted tests' contract."""
    return pytest.raises(exception, match=re.escape(message))

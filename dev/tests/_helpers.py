# dev/tests/_helpers.py
from __future__ import annotations

import json
import re

import pytest


def assert_raises_msg[E: BaseException](
    exception: type[E], message: str
) -> pytest.RaisesExc[E]:
    """Match a literal message fragment, preserving the extracted tests' contract."""
    return pytest.raises(exception, match=re.escape(message))


def tach_text(*modules: tuple[str, list[str]]) -> str:
    body = "\n".join(
        f"""\
[[modules]]
path = {json.dumps(module_path)}
depends_on = {json.dumps(dependencies)}
"""
        for module_path, dependencies in modules
    )
    return f"""\
source_roots = ["."]
exact = true
root_module = "forbid"

{body}
"""

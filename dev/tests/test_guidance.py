# dev/tests/test_guidance.py
from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

_ROOT = Path(__file__).resolve().parents[2]
_LINK = re.compile(r"\[[^\]\n]+\]\(([^\s)]+)\)")
_FENCE = re.compile(r"^```[^\n]*\n.*?^```[ \t]*$", re.MULTILINE | re.DOTALL)


def _prose(path: Path) -> str:
    return _FENCE.sub("", path.read_text(encoding="utf-8"))


def _anchors(path: Path) -> set[str]:
    headings = re.findall(r"^#{1,6} (.+)$", _prose(path), re.MULTILINE)
    return {
        re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        for heading in headings
    }


def test_guidance_budget_and_local_links() -> None:
    agents = _ROOT / "AGENTS.md"
    words = len(agents.read_text(encoding="utf-8").split())
    assert words <= 450, f"AGENTS.md has {words} words; route detail to focused guides"

    documents = [
        agents,
        _ROOT / "README.md",
        *sorted((_ROOT / "docs").rglob("*.md")),
        *sorted((_ROOT / ".noxala").glob("*.md")),
    ]
    failures: list[str] = []
    for document in documents:
        for match in _LINK.finditer(_prose(document)):
            destination = match.group(1)
            url = urlsplit(destination)
            if url.scheme or url.netloc:
                continue
            target = (
                (document.parent / unquote(url.path)).resolve()
                if url.path
                else document
            )
            origin = document.relative_to(_ROOT)
            if not target.is_relative_to(_ROOT) or not target.exists():
                failures.append(f"{origin}: missing local target {destination}")
            elif url.fragment and (
                target.suffix != ".md" or unquote(url.fragment) not in _anchors(target)
            ):
                failures.append(f"{origin}: missing heading {destination}")

    assert not failures, "\n".join(failures)

"""Tests du chargement des prompts versionnés (ADR-010)."""

from pathlib import Path

import pytest

from app.core.llm import load_prompt


def _write(tmp_path: Path, agent: str, version: int, text: str) -> None:
    d = tmp_path / agent
    d.mkdir(exist_ok=True)
    (d / f"v{version}.md").write_text(text, encoding="utf-8")


def test_derniere_version_par_defaut(tmp_path: Path) -> None:
    _write(tmp_path, "hr_score", 1, "prompt v1")
    _write(tmp_path, "hr_score", 2, "prompt v2")
    _write(tmp_path, "hr_score", 10, "prompt v10")  # tri numérique, pas lexical

    text, version = load_prompt("hr_score", base_dir=tmp_path)
    assert (text, version) == ("prompt v10", 10)


def test_version_explicite(tmp_path: Path) -> None:
    _write(tmp_path, "hr_score", 1, "prompt v1")
    _write(tmp_path, "hr_score", 2, "prompt v2")

    text, version = load_prompt("hr_score", version=1, base_dir=tmp_path)
    assert (text, version) == ("prompt v1", 1)


def test_agent_sans_prompt(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("inconnu", base_dir=tmp_path)

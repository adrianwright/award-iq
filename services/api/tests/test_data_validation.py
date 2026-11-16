from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from data.fabric.funding_ops.generate import generate
from tools.validate_consistency import _source_url_allowed, validate_funding_ops, validate_synthetic_provenance


def test_synthetic_source_urls_require_https_and_funding_host() -> None:
    assert _source_url_allowed("https://award-iq.example.invalid/funding/notice")
    assert not _source_url_allowed("http://award-iq.example.invalid/funding/notice")
    assert not _source_url_allowed("https://award-iq.example.invalid.attacker.test/notice")
    assert not _source_url_allowed("https://example.com/notice")


def test_funding_generator_uses_canonical_lf_endings(tmp_path: Path) -> None:
    generate(tmp_path)
    for path in tmp_path.glob("*.csv"):
        assert b"\r\n" not in path.read_bytes()


def test_funding_package_is_self_contained() -> None:
    assert validate_funding_ops() == []
    assert validate_synthetic_provenance() == []

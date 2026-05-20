"""Unit tests for the persist module — focus on hash logic since DB tests need a live Postgres."""

from insurance_intel.persist import content_hash, normalize_for_hash


def test_normalize_collapses_whitespace():
    s = "Hello\n  World\t\tFoo"
    assert normalize_for_hash(s) == "hello world foo"


def test_normalize_strips_outer():
    assert normalize_for_hash("   X   ") == "x"


def test_hash_is_deterministic():
    assert content_hash("Same Content") == content_hash("same\ncontent")


def test_hash_differs_for_different_content():
    assert content_hash("a") != content_hash("b")


def test_hash_is_64_char_hex():
    h = content_hash("anything")
    assert len(h) == 64
    int(h, 16)  # hex-decodable

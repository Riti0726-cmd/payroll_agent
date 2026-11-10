from pathlib import Path

from triage.processed import LocalProcessedMailStore


def test_local_processed_roundtrip(tmp_path: Path):
    store = LocalProcessedMailStore(tmp_path, specialist_id="demo")
    assert store.is_processed("m1") is False
    store.mark_processed("m1")
    assert store.is_processed("m1") is True


def test_local_processed_persists(tmp_path: Path):
    store = LocalProcessedMailStore(tmp_path, specialist_id="demo")
    store.mark_processed("m2")
    store2 = LocalProcessedMailStore(tmp_path, specialist_id="demo")
    assert store2.is_processed("m2") is True

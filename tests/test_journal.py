from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from gitea_forgejo_migrator.journal import (
    GENESIS_HASH,
    Journal,
    JournalEntry,
    JournalIntegrityError,
)


def test_empty_journal_has_no_entries() -> None:
    journal = Journal.empty()
    assert len(journal) == 0
    assert list(journal) == []


def test_first_entry_links_to_genesis() -> None:
    journal = Journal.empty()
    entry = journal.record(stage="audit", action="load")
    assert entry.seq == 0
    assert entry.prev_hash == GENESIS_HASH
    assert len(entry.entry_hash) == 64
    assert entry.stage == "audit"
    assert entry.action == "load"


def test_subsequent_entries_chain_to_previous() -> None:
    journal = Journal.empty()
    first = journal.record(stage="audit", action="load")
    second = journal.record(stage="audit", action="evaluate", repo_count=12)
    assert second.seq == 1
    assert second.prev_hash == first.entry_hash
    assert second.metadata["repo_count"] == 12


def test_metadata_round_trips_with_various_types() -> None:
    journal = Journal.empty()
    journal.record(
        stage="backup",
        action="manifest",
        paths=["/etc/gitea", "/var/lib/gitea"],
        bytes_total=1024 * 1024,
        compress=True,
        ratio=None,
    )
    entry = journal[0]
    assert entry.metadata["paths"] == ["/etc/gitea", "/var/lib/gitea"]
    assert entry.metadata["bytes_total"] == 1024 * 1024
    assert entry.metadata["compress"] is True
    assert entry.metadata["ratio"] is None


def test_dump_then_load_preserves_chain(tmp_path: Path) -> None:
    journal_path = tmp_path / "journal.json"
    journal = Journal.empty()
    journal.record(stage="audit", action="load", source="vm100")
    journal.record(stage="compatibility", action="assess")
    journal.record(stage="gate", action="decision", allowed=True)

    journal.dump(journal_path)

    loaded = Journal.load(journal_path)
    assert len(loaded) == 3
    loaded.verify_chain()
    assert [entry.stage for entry in loaded] == [
        "audit", "compatibility", "gate",
    ]
    assert loaded[2].metadata["allowed"] is True


def test_verify_chain_detects_tampered_metadata(tmp_path: Path) -> None:
    journal_path = tmp_path / "tampered-journal.json"
    journal = Journal.empty()
    journal.record(stage="audit", action="load")
    journal.record(stage="audit", action="evaluate", notes="original")

    payload = copy.deepcopy(journal.to_dict())
    payload["entries"][1]["metadata"]["notes"] = "tampered"
    journal_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = Journal.load(journal_path)
    with pytest.raises(JournalIntegrityError, match="Tampered"):
        loaded.verify_chain()


def test_verify_chain_detects_broken_prev_link(tmp_path: Path) -> None:
    journal_path = tmp_path / "broken-chain.json"
    journal = Journal.empty()
    journal.record(stage="audit", action="load")
    journal.record(stage="audit", action="evaluate")

    payload = copy.deepcopy(journal.to_dict())
    payload["entries"][1]["prev_hash"] = "ff" * 32
    journal_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = Journal.load(journal_path)
    with pytest.raises(JournalIntegrityError, match="hash chain"):
        loaded.verify_chain()


def test_load_rejects_unknown_version(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(
        json.dumps({"version": 99, "entries": []}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unsupported journal version"):
        Journal.load(bad_path)


def test_load_rejects_payload_missing_entries(tmp_path: Path) -> None:
    bad_path = tmp_path / "no-entries.json"
    bad_path.write_text(json.dumps({"version": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="entries"):
        Journal.load(bad_path)


def test_iteration_yields_entries_in_order() -> None:
    journal = Journal.empty()
    journal.record(stage="a", action="first")
    journal.record(stage="b", action="second")
    journal.record(stage="c", action="third")
    seqs = [entry.seq for entry in journal]
    actions = [entry.action for entry in journal]
    assert seqs == [0, 1, 2]
    assert actions == ["first", "second", "third"]


def test_journal_is_immutable_after_record(tmp_path: Path) -> None:
    """Once a journal entry is appended, its fields must not change."""

    journal = Journal.empty()
    entry = journal.record(stage="audit", action="load", frozen_check=True)
    with pytest.raises(Exception):
        # frozen=True dataclass refuses setattr.
        entry.stage = "tampered"  # type: ignore[misc]

    # Confirm the underlying tuple is immutable.
    with pytest.raises(Exception):
        journal._entries = ()  # type: ignore[misc]


def test_journal_entry_dataclass_construction_directly() -> None:
    """JournalEntry can be constructed without going through Journal.record."""

    entry = JournalEntry(
        seq=7,
        timestamp=0.0,
        stage="audit",
        action="load",
        metadata={"k": "v"},
        prev_hash=GENESIS_HASH,
        entry_hash="abc",
    )
    assert entry.seq == 7
    assert entry.stage == "audit"
    assert entry.metadata == {"k": "v"}

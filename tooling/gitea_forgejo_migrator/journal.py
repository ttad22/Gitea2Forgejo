from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator


GENESIS_HASH = "0" * 64


def _short_hash(payload: str) -> str:
    """Return the lowercase hex SHA-256 digest of ``payload``."""

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical_payload(*, seq: int, timestamp: float, stage: str, action: str,
                       metadata: dict[str, Any], prev_hash: str) -> str:
    """Build the canonical string used as input to the entry hash.

    The canonical form is compact JSON with sorted keys so that an entry can be
    reconstructed and re-hashed by :meth:`Journal.verify_chain` independently
    of any in-memory state.
    """

    return json.dumps(
        {
            "seq": seq,
            "timestamp": timestamp,
            "stage": stage,
            "action": action,
            "metadata": metadata,
            "prev_hash": prev_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass(frozen=True, slots=True)
class JournalEntry:
    seq: int
    timestamp: float
    stage: str
    action: str
    metadata: dict[str, Any] = field(default_factory=dict)
    prev_hash: str = GENESIS_HASH
    entry_hash: str = GENESIS_HASH

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class JournalIntegrityError(ValueError):
    """Raised when a loaded journal's hash chain does not verify."""


class Journal:
    """Append-only, hash-chained journal of migration actions.

    Each :meth:`record` call appends a :class:`JournalEntry` and links it to the
    previous entry's hash. :meth:`verify_chain` walks every entry and re-derives
    each ``entry_hash`` from the canonical payload to detect tampering or
    out-of-order writes. The journal serializes to disk in a versioned JSON
    envelope so future revisions can stay backward-compatible.
    """

    _VERSION = 1
    __slots__ = ("_entries", "_mutating")

    def __init__(self, entries: tuple[JournalEntry, ...] = ()) -> None:
        object.__setattr__(self, "_mutating", True)
        object.__setattr__(self, "_entries", entries)
        object.__setattr__(self, "_mutating", False)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_entries" and not getattr(self, "_mutating", False):
            raise AttributeError("Journal entries are append-only and cannot be reassigned directly.")
        object.__setattr__(self, name, value)

    @classmethod
    def empty(cls) -> "Journal":
        return cls()

    @classmethod
    def load(cls, path: str | Path) -> "Journal":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        version = payload.get("version")
        if version != cls._VERSION:
            raise ValueError(
                f"Unsupported journal version: {version!r} (expected {cls._VERSION})"
            )
        raw_entries = payload.get("entries")
        if not isinstance(raw_entries, list):
            raise ValueError("Journal payload is missing a list 'entries' key.")
        entries = tuple(JournalEntry(**raw) for raw in raw_entries)
        return cls(entries)

    def dump(self, path: str | Path) -> None:
        payload = {
            "version": self._VERSION,
            "entries": [entry.to_dict() for entry in self._entries],
        }
        Path(path).write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def record(self, *, stage: str, action: str, **metadata: Any) -> JournalEntry:
        prev_hash = self._entries[-1].entry_hash if self._entries else GENESIS_HASH
        seq = len(self._entries)
        timestamp = time.time()
        canonical = _canonical_payload(
            seq=seq,
            timestamp=timestamp,
            stage=stage,
            action=action,
            metadata=metadata,
            prev_hash=prev_hash,
        )
        entry = JournalEntry(
            seq=seq,
            timestamp=timestamp,
            stage=stage,
            action=action,
            metadata=dict(metadata),
            prev_hash=prev_hash,
            entry_hash=_short_hash(canonical),
        )
        object.__setattr__(self, "_mutating", True)
        try:
            self._entries = self._entries + (entry,)
        finally:
            object.__setattr__(self, "_mutating", False)
        return entry

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[JournalEntry]:
        return iter(self._entries)

    def __getitem__(self, index: int) -> JournalEntry:
        return self._entries[index]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self._VERSION,
            "entries": [entry.to_dict() for entry in self._entries],
        }

    def verify_chain(self) -> None:
        expected_prev_hash = GENESIS_HASH
        expected_seq = 0
        for entry in self._entries:
            if entry.seq != expected_seq:
                raise JournalIntegrityError(
                    f"Out-of-order seq at entry seq={entry.seq}: "
                    f"expected {expected_seq}"
                )
            if entry.prev_hash != expected_prev_hash:
                raise JournalIntegrityError(
                    f"Broken hash chain at seq={entry.seq}: "
                    f"prev_hash={entry.prev_hash!r} expected={expected_prev_hash!r}"
                )
            canonical = _canonical_payload(
                seq=entry.seq,
                timestamp=entry.timestamp,
                stage=entry.stage,
                action=entry.action,
                metadata=entry.metadata,
                prev_hash=entry.prev_hash,
            )
            if entry.entry_hash != _short_hash(canonical):
                raise JournalIntegrityError(
                    f"Tampered journal entry at seq={entry.seq}"
                )
            expected_seq += 1
            expected_prev_hash = entry.entry_hash


__all__ = [
    "GENESIS_HASH",
    "Journal",
    "JournalEntry",
    "JournalIntegrityError",
]

from __future__ import annotations

"""Print a small reproduction of a migration-action journal trace.

Used by ``make journal-demo`` so reviewers can verify the journal module is
working without invoking pytest. Exit code ``0`` is returned only after
:meth:`verify_chain` passes, so this script also doubles as a smoke test for
the journal integrity guarantee.
"""

from gitea_forgejo_migrator.journal import Journal


def main() -> int:
    journal = Journal.empty()
    for stage, action in (
        ("audit", "load"),
        ("audit", "evaluate"),
        ("compatibility", "assess"),
        ("backup", "manifest"),
        ("gate", "decision"),
    ):
        journal.record(stage=stage, action=action)

    journal.verify_chain()

    print(f"journal entries: {len(journal)}")
    for entry in journal:
        print(
            f"  seq={entry.seq} stage={entry.stage:<14} "
            f"action={entry.action:<10} hash={entry.entry_hash[:12]}..."
        )

    print(f"\nchain tail: {journal[-1].entry_hash[:16]}...")
    print("verify_chain: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

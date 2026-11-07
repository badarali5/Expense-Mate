"""
migrate_db.py — Repeatable migration procedure
-----------------------------------------------
Usage:  python src/migrate_db.py [path/to/expensemate.db]

Steps: 1) back up the file  2) snapshot the original columns of every
transaction  3) apply pending migrations  4) verify the snapshot is unchanged.
Exit code 0 = verified, 1 = records changed or migration failed.
"""

import hashlib
import os
import shutil
import sqlite3
import sys

from database import DEFAULT_DB_PATH
from migrations import LATEST_VERSION, get_schema_version, migrate

ORIGINAL_COLUMNS = "id, type, amount, category_id, date, description"


def snapshot(conn: sqlite3.Connection) -> dict:
    """Row count and a checksum over the Assignment 01 columns only."""
    rows = conn.execute(
        f"SELECT {ORIGINAL_COLUMNS} FROM transactions ORDER BY id").fetchall()
    digest = hashlib.sha256(repr([tuple(r) for r in rows]).encode("utf-8")).hexdigest()
    return {"count": len(rows), "checksum": digest}


def run_migration(db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        before_version = get_schema_version(conn)
        has_data = conn.execute(
            "SELECT name FROM sqlite_master WHERE name = 'transactions'").fetchone()
        backup_path = None
        if has_data and before_version < LATEST_VERSION:
            backup_path = f"{db_path}.bak-v{before_version}"
            shutil.copyfile(db_path, backup_path)
        before = snapshot(conn) if has_data else {"count": 0, "checksum": ""}
        applied = migrate(conn)
        after = snapshot(conn)
        verified = (not has_data) or before == after
        return {"before_version": before_version, "after_version": get_schema_version(conn),
                "applied": applied, "backup": backup_path,
                "before": before, "after": after, "verified": verified}
    finally:
        conn.close()


def main(argv: list) -> int:
    db_path = argv[1] if len(argv) > 1 else DEFAULT_DB_PATH
    if not os.path.exists(db_path):
        print(f"No database at {db_path} - it will be created at v{LATEST_VERSION} on first run.")
        return 0
    report = run_migration(db_path)
    print(f"Schema version: v{report['before_version']} -> v{report['after_version']}")
    print(f"Migrations applied: {report['applied'] or 'none (already up to date)'}")
    print(f"Backup: {report['backup'] or 'not needed'}")
    print(f"Transactions before: {report['before']['count']} | after: {report['after']['count']}")
    print("Record check:", "OK - original columns unchanged" if report["verified"] else "FAILED")
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

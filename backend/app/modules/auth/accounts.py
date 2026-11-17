from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from app.modules.auth.credentials import TestAccount, hash_password


class AccountStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS accounts ("
                "username TEXT PRIMARY KEY COLLATE NOCASE, owner_id TEXT NOT NULL UNIQUE, "
                "display_name TEXT NOT NULL, password_hash TEXT NOT NULL)"
            )

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    def get(self, username: str) -> TestAccount | None:
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT username, owner_id, display_name, password_hash "
                "FROM accounts WHERE username = ?",
                (username,),
            ).fetchone()
        return TestAccount(*row) if row else None

    def create(self, username: str, password: str) -> bool:
        encoded = hash_password(password)
        try:
            with closing(self.connect()) as db, db:
                db.execute(
                    "INSERT INTO accounts VALUES (?, ?, ?, ?)",
                    (username, "account-" + uuid4().hex, username, encoded),
                )
        except sqlite3.IntegrityError:
            return False
        return True

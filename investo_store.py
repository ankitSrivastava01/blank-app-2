"""SQLite storage for private workspaces and last successful provider responses."""

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import BoundedSemaphore


SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    name TEXT PRIMARY KEY, payload TEXT NOT NULL, fetched TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workspaces (owner TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS email_accounts (
    email TEXT PRIMARY KEY, owner TEXT UNIQUE NOT NULL REFERENCES workspaces(owner),
    salt BLOB NOT NULL, password_hash BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY, owner TEXT NOT NULL REFERENCES workspaces(owner),
    symbol TEXT NOT NULL, alias TEXT NOT NULL, name TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity > 0),
    price_paise INTEGER NOT NULL CHECK(price_paise > 0), purchased TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS watchlist (
    owner TEXT NOT NULL REFERENCES workspaces(owner), symbol TEXT NOT NULL, alias TEXT NOT NULL, name TEXT NOT NULL,
    direction TEXT CHECK(direction IN ('At or above', 'At or below')),
    target REAL CHECK(target > 0), PRIMARY KEY(owner, symbol)
);
CREATE INDEX IF NOT EXISTS purchases_owner ON purchases(owner);
"""
PASSWORD_HASH_SLOT = BoundedSemaphore()


@contextmanager
def database():
    path = Path(os.getenv("INVESTO_DB_PATH", ".cache/investo.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(SCHEMA)
        with db:
            yield db
    finally:
        db.close()


def snapshot(name, payload=None):
    with database() as db:
        if payload is not None:
            fetched = datetime.now(timezone.utc).isoformat()
            db.execute("""INSERT INTO snapshots VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET payload=excluded.payload, fetched=excluded.fetched
                WHERE excluded.fetched >= snapshots.fetched""", (name, json.dumps(payload, allow_nan=False), fetched))
            return payload, fetched
        row = db.execute("SELECT payload, fetched FROM snapshots WHERE name=?", (name,)).fetchone()
        return (json.loads(row["payload"]), row["fetched"]) if row else (None, None)


def private_owner(code):
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def password_hash(password, salt):
    if not PASSWORD_HASH_SLOT.acquire(timeout=2):
        raise ValueError("Sign-in is busy. Try again in a moment.")
    try:
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**17, r=8, p=1, maxmem=256 * 1024**2)
    finally:
        PASSWORD_HASH_SLOT.release()


def create_email_account(email, password):
    email = email.strip().casefold()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Enter a valid email address.")
    if not 12 <= len(password) <= 128:
        raise ValueError("Use a password between 12 and 128 characters.")
    owner = private_owner(secrets.token_urlsafe(32))
    salt = secrets.token_bytes(16)
    digest = password_hash(password, salt)
    try:
        with database() as db:
            db.execute("INSERT INTO workspaces VALUES (?)", (owner,))
            db.execute("INSERT INTO email_accounts VALUES (?, ?, ?, ?)", (email, owner, salt, digest))
    except sqlite3.IntegrityError:
        raise ValueError("Unable to create this account. If you already have an account, sign in.") from None
    return owner


def sign_in_email(email, password):
    if not 12 <= len(password) <= 128 or len(email) > 254:
        return None
    with database() as db:
        row = db.execute("SELECT owner, salt, password_hash FROM email_accounts WHERE email=?",
                         (email.strip().casefold(),)).fetchone()
    digest = password_hash(password, row["salt"] if row else bytes(16))
    matches = hmac.compare_digest(digest, row["password_hash"] if row else bytes(64))
    return row["owner"] if row and matches else None


def create_workspace():
    code = secrets.token_urlsafe(32)
    with database() as db:
        db.execute("INSERT INTO workspaces VALUES (?)", (private_owner(code),))
    return code


def unlock_workspace(code):
    if len(code) != 43:
        return None
    owner = private_owner(code)
    with database() as db:
        return owner if db.execute("SELECT 1 FROM workspaces WHERE owner=?", (owner,)).fetchone() else None


def purchases(owner):
    with database() as db:
        return [dict(row) for row in db.execute(
            "SELECT id, symbol, alias, name, quantity, price_paise, purchased FROM purchases WHERE owner=? ORDER BY purchased, id",
            (owner,))]


def add_purchase(owner, symbol, alias, name, quantity, price_paise, purchased):
    with database() as db:
        db.execute("INSERT INTO purchases (owner, symbol, alias, name, quantity, price_paise, purchased) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (owner, symbol, alias, name, quantity, price_paise, purchased))


def remove_purchase(owner, purchase_id):
    with database() as db:
        db.execute("DELETE FROM purchases WHERE owner=? AND id=?", (owner, purchase_id))


def watchlist(owner):
    with database() as db:
        return [dict(row) for row in db.execute(
            "SELECT symbol, alias, name, direction, target FROM watchlist WHERE owner=? ORDER BY symbol", (owner,))]


def save_watch(owner, symbol, alias, name, direction, target):
    with database() as db:
        db.execute("""INSERT INTO watchlist VALUES (?, ?, ?, ?, ?, ?)
                  ON CONFLICT(owner, symbol) DO UPDATE SET alias=excluded.alias, name=excluded.name,
                  direction=excluded.direction, target=excluded.target""", (owner, symbol, alias, name, direction, target))


def remove_watch(owner, symbol):
    with database() as db:
        db.execute("DELETE FROM watchlist WHERE owner=? AND symbol=?", (owner, symbol))

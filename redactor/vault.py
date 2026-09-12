# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Redactor contributors
"""Authenticated encrypted vault. No plaintext originals are written to disk."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import tempfile
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

AAD = b"Redactor vault v1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def vault_directory() -> Path:
    from .portable import directory
    return directory("data/vaults")


def account_path(directory: Path, username: str) -> Path:
    return directory / (hashlib.sha256(username.strip().casefold().encode()).hexdigest() + ".vault")


def derive(password: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=32, n=2**17, r=8, p=1).derive(password.encode("utf-8"))


def check_password(password: str) -> None:
    if len(password) < 12:
        raise ValueError("Use a password or passphrase with at least 12 characters.")
    if len(password) > 1024:
        raise ValueError("Password must be 1,024 characters or fewer.")


class Vault:
    def __init__(self, path: Path, key: bytes, salt: bytes, data: dict):
        self.path, self.key, self.salt, self.data = path, key, salt, data
        self._saved_mappings = copy.deepcopy(data.get("mappings", []))

    @classmethod
    def create(cls, directory: Path, username: str, password: str) -> "Vault":
        username = username.strip()
        if not username or len(username) > 80:
            raise ValueError("Enter a username between 1 and 80 characters.")
        check_password(password)
        path = account_path(directory, username)
        if path.exists():
            raise ValueError("This username already has a vault. Sign in instead.")
        salt = os.urandom(16)
        vault = cls(path, derive(password, salt), salt, {
            "username": username, "password_changed": now(), "remind": True,
            "mappings": [], "audit": [], "created": now(),
        })
        vault.audit("account_created")
        vault.save()
        return vault

    @classmethod
    def open(cls, directory: Path, username: str, password: str) -> "Vault":
        try:
            path = account_path(directory, username)
            if path.stat().st_size > 100_000_000:
                raise ValueError("Vault exceeds the supported size.")
            envelope = json.loads(path.read_bytes())
            if envelope["version"] != 1:
                raise ValueError("Unsupported vault version.")
            salt = base64.b64decode(envelope["salt"], validate=True)
            nonce = base64.b64decode(envelope["nonce"], validate=True)
            key = derive(password, salt)
            data = json.loads(AESGCM(key).decrypt(nonce, base64.b64decode(envelope["data"]), AAD))
            if data["username"].casefold() != username.strip().casefold():
                raise ValueError("Account mismatch.")
            return cls(path, key, salt, data)
        except (FileNotFoundError, InvalidTag, KeyError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("Unable to unlock. Check the username and password, or restore an intact vault backup.") from error

    def save(self) -> None:
        nonce = os.urandom(12)
        encrypted = AESGCM(self.key).encrypt(nonce, json.dumps(self.data, ensure_ascii=False).encode(), AAD)
        envelope = {"version": 1, "salt": base64.b64encode(self.salt).decode(),
                    "nonce": base64.b64encode(nonce).decode(), "data": base64.b64encode(encrypted).decode()}
        if len(json.dumps(envelope).encode()) > 100_000_000:
            raise ValueError("R005: Encrypted account exceeds 100 MB. Export and retire completed databases or purge retained audit history before adding more data.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".redactor-", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(envelope, stream)
                stream.flush()
                os.fsync(stream.fileno())
            from .portable import atomic_replace
            atomic_replace(temporary, self.path)
            self._saved_mappings = copy.deepcopy(self.data.get("mappings", []))
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def commit(self, action: str, **details) -> None:
        self.audit(action, **details)
        self.save()

    def audit(self, action: str, **details) -> None:
        before = {m.get("id", str(i)): m for i, m in enumerate(self._saved_mappings)}
        after = {m.get("id", str(i)): m for i, m in enumerate(self.data.get("mappings", []))}
        changes = [{"mapping_id": key, "before": before.get(key), "after": after.get(key)}
                   for key in sorted(before.keys() | after.keys()) if before.get(key) != after.get(key)]
        touched = [copy.deepcopy(m) for m in self.data.get("mappings", []) if m.get("id") in details.get("mapping_ids", [])]
        events = self.data.setdefault("audit", [])
        database = {"id": getattr(self, 'database_id', 'main'), "title": self.data.get('title', 'Main database')}
        event = {"at": now(), "user": self.data["username"], "action": action,
                 "database": database,
                 "affected_databases": details.pop('affected_databases', [{**database, 'access': 'modified' if changes else 'read/operation'}]),
                 "changes": changes, "touched": touched, **details,
                 "previous_hash": events[-1].get("hash", "") if events else ""}
        event["hash"] = hashlib.sha256(json.dumps(event, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        events.append(event)

    def export_exchange(self, path: Path, password: str):
        check_password(password)
        if path.resolve() == self.path.resolve():
            raise ValueError("R009: An export cannot overwrite the active vault.")
        self.commit("exchange_export_prepared", mapping_ids=[m["id"] for m in self.data["mappings"]], destination=str(path))
        salt, nonce = os.urandom(16), os.urandom(12)
        payload = {"format": "Redactor exchange", "version": 1, "exported_utc": now(),
                   "source_database": {"id":getattr(self,'database_id','main'),"title":self.data.get('title','Main database'),"user":self.data['username']},
                   "source_user": self.data["username"], "mappings": self.data["mappings"], "audit": [*self.data.get("imported_audit", []), *self.data["audit"]]}
        encrypted = AESGCM(derive(password, salt)).encrypt(nonce, json.dumps(payload, ensure_ascii=False).encode(), b"Redactor exchange v1")
        envelope = {"version": 1, "salt": base64.b64encode(salt).decode(), "nonce": base64.b64encode(nonce).decode(), "data": base64.b64encode(encrypted).decode()}
        from .exchange import bundle
        bundle(json.dumps(envelope).encode(), path)

    @classmethod
    def read_exchange(cls, path: Path, password: str):
        try:
            if path.stat().st_size > 100_000_000: raise ValueError("File too large")
            from .exchange import unpack
            envelope = json.loads(unpack(path))
            if envelope['version'] != 1: raise ValueError("Unsupported version")
            salt = base64.b64decode(envelope['salt'], validate=True)
            nonce = base64.b64decode(envelope['nonce'], validate=True)
            ciphertext = base64.b64decode(envelope['data'], validate=True)
            key = derive(password, salt)
            try:
                payload = json.loads(AESGCM(key).decrypt(nonce, ciphertext, b"Redactor exchange v1"))
            except InvalidTag:
                payload = json.loads(AESGCM(key).decrypt(nonce, ciphertext, AAD))  # legacy encrypted backup
            from .engine import validate_mappings
            validate_mappings(payload['mappings'])
            if len({m['id'] for m in payload['mappings']}) != len(payload['mappings']): raise ValueError('Duplicate IDs')
            if not isinstance(payload['audit'], list): raise ValueError('Invalid audit')
        except Exception as exc:
            if str(exc).startswith(("R011:", "R005:")): raise
            raise ValueError("R009: Cannot import exchange or backup. Check its password, integrity and format.") from exc
        return payload

    @classmethod
    def import_exchange(cls, path: Path, password: str, directory: Path, username: str, local_password: str):
        payload = cls.read_exchange(path,password)
        vault = cls.create(directory, username, local_password)
        vault.data['mappings'] = copy.deepcopy(payload['mappings'])
        vault.data['imported_audit'] = payload['audit']
        vault.commit('exchange_import', source_user=payload.get('source_user', payload.get('username')),
                     source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                     mapping_ids=[m['id'] for m in payload['mappings']])
        return vault

    def change_password(self, current: str, new: str) -> None:
        check_password(new)
        if derive(current, self.salt) != self.key:
            raise ValueError("Current password is incorrect.")
        if current == new:
            raise ValueError("Choose a different password.")
        old_key, old_salt, old_data = self.key, self.salt, copy.deepcopy(self.data)
        self.salt = os.urandom(16)
        self.key = derive(new, self.salt)
        self.data["password_changed"] = now()
        try:
            self.commit("password_changed", affected_databases=[{'id':'main','title':'Main database','access':'re-encrypted'},
                        *[{'id':key,'title':value.get('title','Database'),'access':'re-encrypted'} for key,value in self.data.get('databases',{}).items()]])
        except Exception:
            self.key, self.salt, self.data = old_key, old_salt, old_data
            raise

    @property
    def password_age(self) -> int:
        return max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(self.data["password_changed"])).days)

    def close(self) -> None:
        self.data.clear()
        self._saved_mappings.clear()
        self.key = b""

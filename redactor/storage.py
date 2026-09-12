# SPDX-License-Identifier: GPL-3.0-or-later
"""Database-specific storage with hashed user folders and encrypted payloads."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

LIMIT = 100_000_000


def user_hash(username):
    return hashlib.sha256(username.strip().casefold().encode('utf-8')).hexdigest()


def main_id(username):
    return hashlib.sha256(('Redactor main database v1:' + user_hash(username)).encode()).hexdigest()[:32]


def database_path(directory, database_id, username):
    if not re.fullmatch(r'[0-9a-f]{32}', database_id):
        raise ValueError('R009: Invalid local database identifier.')
    directory = Path(directory).resolve()
    path = directory / database_id / user_hash(username) / 'database.vault'
    if not path.resolve().is_relative_to(directory):
        raise ValueError('R008: A database storage link points outside the database directory.')
    return path


def database_aad(database_id, username):
    return ('Redactor database v2:' + database_id + ':' + user_hash(username)).encode()


def seal(data, key, aad, salt=None):
    nonce = os.urandom(12)
    encrypted = AESGCM(key).encrypt(nonce, json.dumps(data, ensure_ascii=False).encode(), aad)
    envelope = {'version': 1 if salt is not None else 2,
                'nonce': base64.b64encode(nonce).decode(), 'data': base64.b64encode(encrypted).decode()}
    if salt is not None: envelope['salt'] = base64.b64encode(salt).decode()
    blob = json.dumps(envelope).encode()
    if len(blob) > LIMIT: raise ValueError('R005: Encrypted database exceeds 100 MB.')
    return blob


def read_database(path, key, aad):
    if path.stat().st_size > LIMIT: raise ValueError('R005: Encrypted database exceeds 100 MB.')
    envelope = json.loads(path.read_bytes())
    if envelope['version'] != 2: raise ValueError('R009: Unsupported local database format.')
    nonce = base64.b64decode(envelope['nonce'], validate=True)
    encrypted = base64.b64decode(envelope['data'], validate=True)
    return json.loads(AESGCM(key).decrypt(nonce, encrypted, aad))


def write_blob(path, blob):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix='.redactor-', suffix='.tmp')
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(blob); stream.flush(); os.fsync(stream.fileno())
        from .portable import atomic_replace
        atomic_replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def check_capacity(data):
    # Bound the total unlocked workspace, including all database audit histories.
    if len(json.dumps(data, ensure_ascii=False).encode()) * 4 // 3 > LIMIT:
        raise ValueError('R005: Authorized databases exceed the 100 MB workspace limit. Export and retire completed data or purge retained audit history.')

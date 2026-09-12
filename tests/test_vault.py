# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Redactor contributors
import json
import os
import pytest
from cryptography.exceptions import InvalidTag
from redactor.vault import Vault, account_path

PASSWORD = "A long local passphrase!"


def test_vault_encrypted_roundtrip_and_wrong_password(tmp_path):
    vault = Vault.create(tmp_path, "Alice", PASSWORD)
    vault.data["mappings"] = [{"original": "TOP SECRET 123-45-6789", "replacement": "Leia"}]
    vault.save()
    raw = vault.path.read_bytes()
    assert b"TOP SECRET" not in raw and b"123-45-6789" not in raw and PASSWORD.encode() not in raw
    opened = Vault.open(tmp_path, "alice", PASSWORD)
    assert opened.data["mappings"][0]["original"] == "TOP SECRET 123-45-6789"
    with pytest.raises(ValueError): Vault.open(tmp_path, "Alice", "wrong password")


def test_tampered_ciphertext_rejected(tmp_path):
    vault = Vault.create(tmp_path, "Alice", PASSWORD)
    envelope = json.loads(vault.path.read_text())
    ciphertext = envelope["data"]
    envelope["data"] = ("A" if ciphertext[0] != "A" else "B") + ciphertext[1:]
    vault.path.write_text(json.dumps(envelope))
    with pytest.raises(ValueError): Vault.open(tmp_path, "Alice", PASSWORD)


def test_password_change_reencrypts_and_preserves_mappings(tmp_path):
    vault = Vault.create(tmp_path, "Alice", PASSWORD)
    vault.data["mappings"] = [{"original": "secret"}]
    vault.change_password(PASSWORD, "Another much longer passphrase")
    with pytest.raises(ValueError): Vault.open(tmp_path, "Alice", PASSWORD)
    assert Vault.open(tmp_path, "Alice", "Another much longer passphrase").data["mappings"] == [{"original": "secret"}]
    assert vault.password_age == 0


def test_password_change_disk_failure_rolls_back(tmp_path, monkeypatch):
    vault = Vault.create(tmp_path, "Alice", PASSWORD)
    old_key = vault.key
    def fail(): raise OSError("Disk full")
    monkeypatch.setattr(vault, "save", fail)
    with pytest.raises(OSError): vault.change_password(PASSWORD, "Another much longer passphrase")
    assert vault.key == old_key
    assert Vault.open(tmp_path, "Alice", PASSWORD)


def test_separate_accounts_and_duplicate_protection(tmp_path):
    alice = Vault.create(tmp_path, "Alice", PASSWORD)
    bob = Vault.create(tmp_path, "Bob", PASSWORD)
    assert alice.path != bob.path
    with pytest.raises(ValueError): Vault.create(tmp_path, " ALICE ", PASSWORD)
    with pytest.raises(ValueError): Vault.create(tmp_path, "Eve", "short")


def test_ciphertext_changes_every_save_and_atomic_failure(tmp_path, monkeypatch):
    vault = Vault.create(tmp_path, "Alice", PASSWORD)
    first = vault.path.read_bytes()
    vault.save()
    second = vault.path.read_bytes()
    assert first != second
    def fail(*args): raise OSError("Replace failed")
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError): vault.save()
    assert vault.path.read_bytes() == second
    assert not list(tmp_path.glob("*.tmp"))


def test_backup_is_portable(tmp_path):
    import shutil
    source, target = tmp_path / "source", tmp_path / "target"
    source.mkdir(); target.mkdir()
    vault = Vault.create(source, "Alice", PASSWORD)
    shutil.copyfile(vault.path, account_path(target, "Alice"))
    assert Vault.open(target, "Alice", PASSWORD).data == vault.data

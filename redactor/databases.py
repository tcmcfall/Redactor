# SPDX-License-Identifier: GPL-3.0-or-later
"""Multiple logical databases encrypted under one authenticated local account."""
import copy
import os
import re
import uuid
from .vault import Vault, now
from .storage import database_path, database_aad, check_capacity, seal, write_blob


class Database(Vault):
    def __init__(self, account, database_id):
        Vault.validate_ownership(account.data)
        self.account, self.database_id = account, database_id
        location = database_path(account.storage_root, database_id, account.data['username'])
        super().__init__(location, account._database_keys[database_id], account.salt, copy.deepcopy(account.data['databases'][database_id]))

    def save(self):
        old = copy.deepcopy(self.account.data['databases'][self.database_id])
        is_new = self.database_id not in self.account._persisted_database_ids
        try:
            self.account.data['databases'][self.database_id] = copy.deepcopy(self.data)
            Vault.validate_ownership(self.account.data)
            check_capacity(self.account.data)
            write_blob(self.path, seal(self.data, self.key, database_aad(self.database_id, self.account.data['username'])))
            if is_new:
                # Publish authorization only after the new encrypted database is durable.
                self.account.save()
            self._saved_mappings = copy.deepcopy(self.data['mappings'])
        except Exception:
            self.account.data['databases'][self.database_id] = old
            if is_new and self.path.exists(): self.path.unlink()
            raise

    def close(self):
        super().close()

    @property
    def password_age(self): return self.account.password_age

    def change_password(self, current, new):
        self.account.change_password(current,new)
        self.salt = self.account.salt


def add_database(account, name, payload=None):
    name = name.strip()
    if not name or len(name)>100: raise ValueError('R010: Database title must be 1–100 characters.')
    database_id = uuid.uuid4().hex
    if payload:
        source_id = payload.get('source_database',{}).get('storage_id') or payload.get('source_database',{}).get('id','')
        if re.fullmatch(r'[0-9a-f]{32}', source_id) and source_id != account.path.parents[1].name and source_id not in account.data.get('databases',{}) and not database_path(account.storage_root, source_id, account.data['username']).exists():
            database_id = source_id
    data = {'username':account.data['username'], 'creator_username':account.data['username'], 'title':name,'created':now(),
            'source_creator':payload.get('source_creator') or payload.get('source_database',{}).get('creator_username',payload.get('source_user',payload.get('username'))) if payload else None,
            'password_changed':account.data['password_changed'],'remind':False,
            'mappings':copy.deepcopy(payload['mappings']) if payload else [], 'audit':[],
            'imported_audit':copy.deepcopy(payload.get('audit',[])) if payload else []}
    account.data.setdefault('databases',{})[database_id] = data
    account._database_keys[database_id] = os.urandom(32)
    database = Database(account,database_id)
    try:
        database.commit('database_imported' if payload else 'database_created',
                        source_user=payload.get('source_user',payload.get('username')) if payload else None,
                        affected_databases=([{**payload.get('source_database',{'id':'legacy','title':'Imported database'}),'access':'read'}] if payload else []) +
                        [{'id':database_id,'title':name,'access':'created'}],
                        mapping_ids=[m['id'] for m in data['mappings']])
    except Exception:
        account.data['databases'].pop(database_id,None)
        account._database_keys.pop(database_id,None)
        raise
    return database


def merge_mappings(target, incoming, decisions=None):
    """Return a validated proposal; conflicts require an explicit per-original decision."""
    from .engine import validate_mappings
    proposed = copy.deepcopy(target)
    by_original = {m['original']:m for m in proposed}
    decisions = decisions or {}
    for index, source in enumerate(incoming):
        old = by_original.get(source['original'])
        if old and (old['replacement'] != source['replacement'] or old['kind'] != source['kind']):
            choice = decisions.get(f"{index}:{source['original']}", decisions.get(source['original']))
            if choice not in ('keep','incoming'):
                raise ValueError(f"R012: Merge conflict for {source['original']!r}: {old['replacement']!r} versus {source['replacement']!r}. Choose keep or incoming after review.")
            if choice == 'keep': continue
            old['aliases'] = list(dict.fromkeys([*old.get('aliases',[]),old['replacement'],*source.get('aliases',[])]))
            old['replacement'] = source['replacement']
            old['kind'] = source['kind']
            old['aliases'] = [v for v in old['aliases'] if v != old['replacement']]
        elif not old:
            new = copy.deepcopy(source); new['id'] = uuid.uuid4().hex
            origin = new.pop('_source_database', None)
            if origin: new.setdefault('provenance', []).append(origin)
            proposed.append(new); by_original[new['original']] = new
        elif old:
            old['aliases'] = list(dict.fromkeys([*old.get('aliases',[]),*source.get('aliases',[])]))
            old['aliases'] = [v for v in old['aliases'] if v != old['replacement']]
    validate_mappings(proposed,strict=True)
    return proposed

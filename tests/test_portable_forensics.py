# SPDX-License-Identifier: GPL-3.0-or-later
import json
import zipfile
import pytest
from redactor.engine import detect, prepare_mappings, replace_candidates, restore, Candidate
from redactor.forensics import prefixes, validate_relationships
from redactor.vault import Vault
from redactor.exchange import unpack
from redactor.operations import audit_text, bulk_proposal


def test_shared_domains_ips_lengths_and_roundtrip():
    text = 'alice@abc.gov bob@abc.gov server.abc.gov abc.gov 10.2.3.4 10.2.3.5 10.2.8.9 11.5.8.7'
    candidates = detect(text, [])
    mappings, conversions = prepare_mappings(candidates, [], text, strict=True)
    assert all(len(a)==len(b) for a,b in conversions.items())
    assert conversions['alice@abc.gov'].split('@')[1] == conversions['bob@abc.gov'].split('@')[1]
    assert conversions['server.abc.gov'].endswith(conversions['abc.gov'])
    ips = [m for m in mappings if m['kind']=='IP address']
    for a in ips:
        for b in ips: assert prefixes(a['original'],b['original'])==prefixes(a['replacement'],b['replacement'])
    output,counts=replace_candidates(text,candidates,conversions)
    assert counts and restore(output,mappings)[0]==text


def test_relationship_edits_rejected():
    mappings=[{'original':'a@abc.gov','replacement':'x@def.xyz','kind':'Email'}, {'original':'b@abc.gov','replacement':'y@ghi.xyz','kind':'Email'}]
    with pytest.raises(ValueError,match='R003'): validate_relationships(mappings,True)


@pytest.mark.parametrize('suffix',['.zip','.tar','.7z','.zip7'])
def test_encrypted_exchange_hashes_import_and_wrong_password(tmp_path,suffix):
    vault=Vault.create(tmp_path,'Alice','Very long local password')
    mappings,_=prepare_mappings([Candidate('ZQC','Business','XYZ','manual')],[],'ZQC',strict=True)
    vault.data['mappings']=mappings
    audit_text(vault,'redacted','ZQC','XYZ',mapping_ids=[mappings[0]['id']])
    path=tmp_path/('exchange'+suffix)
    vault.export_exchange(path,'Different export password')
    payload=unpack(path)
    assert b'"original": "ZQC"' not in payload and b'Very long' not in payload
    imported=Vault.import_exchange(path,'Different export password',tmp_path,'Bob','Bobs secure local password')
    assert imported.data['mappings']==mappings
    event = imported.data['imported_audit'][-2]
    assert event['input_text'] == 'ZQC' and event['output_text'] == 'XYZ'
    reconstructed = event['input_text']
    for change in reversed(event['text_changes']):
        assert event['input_text'][change['input_start']:change['input_end']] == change['before']
        reconstructed = reconstructed[:change['input_start']] + change['after'] + reconstructed[change['input_end']:]
    assert reconstructed == event['output_text']
    assert imported.data['audit'][-1]['user']=='Bob'
    with pytest.raises(ValueError,match='R009'): Vault.import_exchange(path,'Wrong password',tmp_path,'Eve','Eves secure local password')
    assert Vault.open(tmp_path,'Alice','Very long local password')


def test_hash_mismatch_and_archive_traversal_rejected(tmp_path):
    path=tmp_path/'bad.zip'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('database.redactor',b'changed');z.writestr('SHA256SUMS',b'bad');z.writestr('SHA512SUMS',b'bad')
    with pytest.raises(ValueError,match='checksum'): unpack(path)
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('../database.redactor',b'changed');z.writestr('SHA256SUMS',b'bad');z.writestr('SHA512SUMS',b'bad')
    with pytest.raises(ValueError,match='members'): unpack(path)


def test_detailed_audit_and_bulk_update(tmp_path):
    vault=Vault.create(tmp_path,'Analyst','Very long local password')
    mappings,_=prepare_mappings([Candidate('Secret','Custom','Public','manual')],[],'Secret',strict=True)
    vault.data['mappings']=mappings; audit_text(vault,'redacted','Secret','Public',mapping_ids=[mappings[0]['id']])
    event=vault.data['audit'][-1]
    assert event['user']=='Analyst' and event['at'].endswith('+00:00')
    assert event['changes'][0]['after']['original']=='Secret'
    assert event['input_text']=='Secret' and event['output_text']=='Public'
    replay=event['input_text']
    for change in reversed(event['text_changes']):replay=replay[:change['input_start']]+change['after']+replay[change['input_end']:]
    assert replay=='Public'
    assert b'Secret' not in vault.path.read_bytes()
    proposed=bulk_proposal(mappings,{mappings[0]['id']},'replacement','Public','Hidden')
    assert proposed[0]['aliases']==['Public']


def test_no_candidates_is_valid(tmp_path):
    from redactor.formats import read_file
    path=tmp_path/'plain.txt'; path.write_text('nothing private here',encoding='utf-8')
    assert read_file(path).text=='nothing private here'
    assert detect(read_file(path).text,[])==[]
    path.write_text('',encoding='utf-8')
    assert read_file(path).text==''


def test_multiple_databases_encrypted_and_merge_atomic(tmp_path):
    from redactor.databases import add_database, Database, merge_mappings
    account=Vault.create(tmp_path,'Analyst','Very long local password')
    first=add_database(account,'Case A')
    first.data['mappings'],_=prepare_mappings([Candidate('ZQC','Business','XYZ','manual')],[],'ZQC',strict=True)
    first.commit('test')
    second=add_database(account,'Case B')
    second.data['mappings']=merge_mappings([],first.data['mappings']);second.commit('merge')
    assert second.data['mappings'][0]['id']!=first.data['mappings'][0]['id']
    conflicting=[{**first.data['mappings'][0],'replacement':'DEF'}]
    with pytest.raises(ValueError,match='R012'):merge_mappings(second.data['mappings'],conflicting)
    assert second.data['mappings'][0]['replacement']=='XYZ'
    result=merge_mappings(second.data['mappings'],conflicting,{'ZQC':'incoming'})
    assert result[0]['replacement']=='DEF' and result[0]['aliases']==['XYZ']
    raw=account.path.read_bytes();assert b'"original": "ZQC"' not in raw and b'Case A' not in raw
    reopened=Vault.open(tmp_path,'Analyst','Very long local password')
    restored=Database(reopened,first.database_id)
    assert restored.data['mappings']==first.data['mappings']
    account.change_password('Very long local password','Changed account password')
    with pytest.raises(ValueError):Vault.open(tmp_path,'Analyst','Very long local password')
    assert Vault.open(tmp_path,'Analyst','Changed account password').data['databases']


def test_terminal_table_edit_roundtrip():
    from redactor.terminal import table_text,table_candidates
    values=[Candidate('A\tB\nC','Custom','X\tY\nZ','manual',True,{0,20})]
    parsed=table_candidates(table_text(values))[0]
    assert parsed.original==values[0].original and parsed.included_starts=={0,20}


def test_merge_repeated_conflicts_use_individual_decisions():
    from redactor.databases import merge_mappings
    base={'id':'one','original':'ZQC','replacement':'ABC','kind':'Business','aliases':[],'created':'2026'}
    incoming=[{**base,'replacement':'DEF'},{**base,'replacement':'GHI'}]
    result=merge_mappings([base],incoming,{'0:ZQC':'incoming','1:ZQC':'keep'})
    assert result[0]['replacement']=='DEF' and result[0]['aliases']==['ABC']
def test_creator_only_password_and_imported_copy_ownership(tmp_path):
    from redactor.databases import add_database, Database
    import copy
    alice = Vault.create(tmp_path, 'Alice', 'Alice creator password')
    bob = Vault.create(tmp_path, 'Bob', 'Bob creator password')
    case = add_database(alice, 'Alice investigation')
    case.data['mappings'], _ = prepare_mappings([Candidate('ZQC','Business','XYZ','manual')], [], 'ZQC', strict=True)
    case.commit('mapping_created')
    with pytest.raises(ValueError): Vault.open(tmp_path, 'Alice', 'Bob creator password')
    exchange = tmp_path / 'exchange.zip'
    case.export_exchange(exchange, 'Separate export password')
    imported = add_database(bob, 'Imported investigation', Vault.read_exchange(exchange, 'Separate export password'))
    assert imported.data['creator_username'] == 'Bob'
    assert imported.data['source_creator'] == 'Alice'
    bob.close()
    with pytest.raises(ValueError): Vault.open(tmp_path, 'Bob', 'Alice creator password')
    with pytest.raises(ValueError): Vault.open(tmp_path, 'Bob', 'Separate export password')
    reopened = Vault.open(tmp_path, 'Bob', 'Bob creator password')
    assert Database(reopened, imported.database_id).data['mappings'][0]['original'] == 'ZQC'
    reopened.data['databases']['foreign'] = copy.deepcopy(case.data)
    with pytest.raises(ValueError, match='another creator'): reopened.save()
def test_database_folders_hash_users_and_keep_separate_encrypted_copies(tmp_path):
    import base64, json
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from redactor.databases import add_database, Database
    from redactor.storage import user_hash
    from redactor.vault import AAD
    alice = Vault.create(tmp_path, 'Alice', 'Alice creator password')
    bob = Vault.create(tmp_path, 'Bob', 'Bob creator password')
    case = add_database(alice, 'Investigation')
    case.data['mappings'], _ = prepare_mappings([Candidate('Secret','Custom','Hidden','manual')], [], 'Secret', strict=True)
    case.commit('saved')
    export = tmp_path / 'handoff.zip'
    case.export_exchange(export, 'Independent export password')
    imported = add_database(bob, 'Imported', Vault.read_exchange(export, 'Independent export password'))
    assert case.path.parents[1] == imported.path.parents[1]
    assert case.path.parent.name == user_hash('Alice')
    assert imported.path.parent.name == user_hash('Bob')
    assert case.path != imported.path and case.path.exists() and imported.path.exists()
    assert b'Secret' not in case.path.read_bytes() and b'Secret' not in imported.path.read_bytes()
    envelope = json.loads(alice.path.read_bytes())
    index = json.loads(AESGCM(alice.key).decrypt(base64.b64decode(envelope['nonce']), base64.b64decode(envelope['data']), AAD))
    assert case.database_id in index['authorized_databases']
    assert 'databases' not in index and 'Secret' not in json.dumps(index)
    bob.change_password('Bob creator password','Changed Bob password')
    with pytest.raises(ValueError): Vault.open(tmp_path, 'Bob', 'Bob creator password')
    reopened = Vault.open(tmp_path, 'Bob', 'Changed Bob password')
    assert Database(reopened, imported.database_id).data['mappings'][0]['original'] == 'Secret'


def test_failed_new_database_authorization_preserves_existing_storage(tmp_path, monkeypatch):
    from redactor.databases import add_database, Database
    from redactor import storage
    account = Vault.create(tmp_path, 'Analyst', 'Original user password')
    first = add_database(account, 'Existing')
    original_write = storage.write_blob
    def fail_account(path, data):
        if path == account.path: raise OSError('Simulated account write failure')
        return original_write(path, data)
    monkeypatch.setattr(storage, 'write_blob', fail_account)
    with pytest.raises(OSError): add_database(account, 'Unpublished')
    assert set(account.data['databases']) == {first.database_id}
    assert len(list(tmp_path.rglob('*.vault'))) == 2
    with pytest.raises(OSError): account.change_password('Original user password','Changed user password')
    reopened = Vault.open(tmp_path, 'Analyst', 'Original user password')
    assert Database(reopened, first.database_id).data['title'] == 'Existing'
    with pytest.raises(ValueError): Vault.open(tmp_path, 'Analyst', 'Changed user password')


def test_readable_generated_network_labels_and_valid_suffixes():
    from redactor.forensics import generate, TLDS, WORDS
    rows=[]
    originals=['tavi@quill.gov','neri@quill.gov','server.quill.gov','quill.gov']
    for original in originals:
        kind='Email' if '@' in original else 'Hostname'
        value=generate(original,kind,rows,[' '.join(originals)])
        assert len(value)==len(original)
        assert value.rsplit('.',1)[-1] in TLDS
        assert value.rsplit('.',1)[-1]!='gov'
        rows.append({'original':original,'replacement':value,'kind':kind})
    validate_relationships(rows,True)
    local = rows[0]['replacement'].split('@')[0].lower()
    boundaries = {0}
    for end in range(1, len(local)+1):
        if any(local[start:end] in WORDS for start in boundaries.copy()): boundaries.add(end)
    assert len(local) in boundaries
    assert rows[0]['replacement'].split('@')[1]==rows[1]['replacement'].split('@')[1]
    assert restore(' '.join(m['replacement'] for m in rows),rows)[0]==' '.join(originals)


def test_email_local_part_is_not_detected_as_hostname():
    candidates=detect('neri.mosswick@example.invalid',[])
    assert not any(c.original=='neri.mosswick' for c in candidates)


def test_audit_is_encrypted_in_all_databases_and_password_change(tmp_path):
    from redactor.databases import add_database, Database
    password='Synthetic audit password one'
    account=Vault.create(tmp_path,'Audit owner',password)
    database=add_database(account,'Second case')
    for target in [account,database]:
        audit_text(target,'test_audit','PRIVATE AUDIT ORIGINAL','FICTIONAL AUDIT OUTPUT')
    for path in tmp_path.rglob('*.vault'):
        data=path.read_bytes()
        assert b'PRIVATE AUDIT ORIGINAL' not in data and b'FICTIONAL AUDIT OUTPUT' not in data and b'Audit owner' not in data
    new_password='Synthetic audit password two'
    account.change_password(password,new_password)
    with pytest.raises(ValueError): Vault.open(tmp_path,'Audit owner',password)
    reopened=Vault.open(tmp_path,'Audit owner',new_password)
    child=Database(reopened,database.database_id)
    for target in [reopened,child]:
        assert any(e.get('input_text')=='PRIVATE AUDIT ORIGINAL' for e in target.data['audit'])
    child.close(); reopened.close(); database.close(); account.close()

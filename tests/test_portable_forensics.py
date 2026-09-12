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
    mappings,_=prepare_mappings([Candidate('IBM','Business','XYZ','manual')],[],'IBM',strict=True)
    vault.data['mappings']=mappings
    audit_text(vault,'redacted','IBM','XYZ',mapping_ids=[mappings[0]['id']])
    path=tmp_path/('exchange'+suffix)
    vault.export_exchange(path,'Different export password')
    payload=unpack(path)
    assert b'IBM' not in payload and b'Very long' not in payload
    imported=Vault.import_exchange(path,'Different export password',tmp_path,'Bob','Bobs secure local password')
    assert imported.data['mappings']==mappings
    assert imported.data['imported_audit'][-2]['text_changes'][0]['before']=='IBM'
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
    first.data['mappings'],_=prepare_mappings([Candidate('IBM','Business','XYZ','manual')],[],'IBM',strict=True)
    first.commit('test')
    second=add_database(account,'Case B')
    second.data['mappings']=merge_mappings([],first.data['mappings']);second.commit('merge')
    assert second.data['mappings'][0]['id']!=first.data['mappings'][0]['id']
    conflicting=[{**first.data['mappings'][0],'replacement':'DEF'}]
    with pytest.raises(ValueError,match='R012'):merge_mappings(second.data['mappings'],conflicting)
    assert second.data['mappings'][0]['replacement']=='XYZ'
    result=merge_mappings(second.data['mappings'],conflicting,{'IBM':'incoming'})
    assert result[0]['replacement']=='DEF' and result[0]['aliases']==['XYZ']
    raw=account.path.read_bytes();assert b'IBM' not in raw and b'Case A' not in raw
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
    base={'id':'one','original':'IBM','replacement':'ABC','kind':'Business','aliases':[],'created':'2026'}
    incoming=[{**base,'replacement':'DEF'},{**base,'replacement':'GHI'}]
    result=merge_mappings([base],incoming,{'0:IBM':'incoming','1:IBM':'keep'})
    assert result[0]['replacement']=='DEF' and result[0]['aliases']==['ABC']
def test_creator_only_password_and_imported_copy_ownership(tmp_path):
    from redactor.databases import add_database, Database
    import copy
    alice = Vault.create(tmp_path, 'Alice', 'Alice creator password')
    bob = Vault.create(tmp_path, 'Bob', 'Bob creator password')
    case = add_database(alice, 'Alice investigation')
    case.data['mappings'], _ = prepare_mappings([Candidate('IBM','Business','XYZ','manual')], [], 'IBM', strict=True)
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
    assert Database(reopened, imported.database_id).data['mappings'][0]['original'] == 'IBM'
    reopened.data['databases']['foreign'] = copy.deepcopy(case.data)
    with pytest.raises(ValueError, match='another creator'): reopened.save()

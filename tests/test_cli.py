# SPDX-License-Identifier: GPL-3.0-or-later
import json
from redactor import cli, portable
from redactor.vault import Vault, vault_directory


def test_cli_review_roundtrip_and_second_database(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(portable,'root',lambda:tmp_path)
    monkeypatch.setattr(cli,'getpass',lambda prompt:'Very long local password')
    vault=Vault.create(vault_directory(),'Analyst','Very long local password');vault.close()
    (tmp_path/'input.txt').write_text('IBM IBM',encoding='utf-8')
    def run(*parts):
        cli.run(cli.parser().parse_args(['--user','Analyst',*parts]))
        return capsys.readouterr().out
    run('scan',str(tmp_path/'input.txt'),'review.json')
    plan=json.loads((tmp_path/'review.json').read_text(encoding='utf-8'))
    assert len(plan['candidates'])==1
    run('review','review.json','--original','IBM','--replacement','XYZ')
    run('redact','review.json','output.txt','--reviewed')
    assert (tmp_path/'output.txt').read_text()=='XYZ XYZ'
    run('restore',str(tmp_path/'output.txt'),'restored.txt','--reviewed')
    assert (tmp_path/'restored.txt').read_text()=='IBM IBM'
    run('export-db','analyst.zip')
    info=json.loads(run('import-db',str(tmp_path/'analyst.zip'),'--title','Imported'))
    database_id=info['opened_database']
    listings=json.loads(run('databases'))
    assert len(listings)==2
    rows=json.loads(run('--database',database_id,'lookup','--json'))
    assert rows[0]['original']=='IBM'
    account=Vault.open(vault_directory(),'Analyst','Very long local password')
    event=account.data['databases'][database_id]['audit'][-1]
    assert event['database']['id']==database_id and event['user']=='Analyst'


def test_portable_output_rejects_external_and_symlink(tmp_path,monkeypatch):
    import pytest
    monkeypatch.setattr(portable,'root',lambda:tmp_path/'app')
    (tmp_path/'app').mkdir()
    assert portable.output_path('file.txt')==tmp_path/'app/file.txt'
    with pytest.raises(ValueError,match='R008'):portable.output_path(tmp_path/'outside.txt')
def test_export_password_replaces_local_password_only_for_chosen_external_copy(tmp_path, monkeypatch, capsys):
    import pytest
    monkeypatch.setattr(portable, 'root', lambda: tmp_path / 'application')
    account = Vault.create(vault_directory(), 'Owner', 'Local owner password')
    account.close()
    destination = tmp_path / 'handoff' / 'Chosen database name.zip'
    answers = iter(['Local owner password','Required export password','Required export password'])
    monkeypatch.setattr(cli, 'getpass', lambda prompt: next(answers))
    cli.run(cli.parser().parse_args(['--user','Owner','export-db',str(destination)]))
    assert destination.exists()
    assert Vault.read_exchange(destination, 'Required export password')['source_user'] == 'Owner'
    with pytest.raises(ValueError): Vault.read_exchange(destination, 'Local owner password')
    reopened = Vault.open(vault_directory(), 'Owner', 'Local owner password')
    reopened.close()
    with pytest.raises(ValueError): Vault.open(vault_directory(), 'Owner', 'Required export password')
    answers = iter(['Local owner password','',''])
    with pytest.raises(ValueError, match='at least 12'):
        cli.run(cli.parser().parse_args(['--user','Owner','export-db',str(tmp_path/'missing.zip')]))
    assert not (tmp_path/'missing.zip').exists()

# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline command-line counterpart. Passwords are read from terminal prompts."""
import argparse
import copy
import hashlib
import json
import sys
from dataclasses import asdict
from getpass import getpass
from pathlib import Path
from .portable import configure, directory, output_path
from .vault import Vault, vault_directory
from .engine import Candidate, detect, find_similar_values, prepare_mappings, replace_candidates, restore, replace_exact, KINDS
from .formats import read_file, export_file, NOTICE
from .operations import audit_text, bulk_proposal, save_mappings


def parser():
    p = argparse.ArgumentParser(prog='redactor-cli', description='Portable offline Redactor. No network or internet communication. Passwords are prompted, never command arguments.')
    p.add_argument('--user', help='Local analyst username')
    p.add_argument('--database', default='main', help='Database ID from databases; default main')
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('create', help='Create a local account')
    sub.add_parser('databases', help='List databases under the current account')
    newdb=sub.add_parser('new-db'); newdb.add_argument('title')
    workspace=sub.add_parser('workspace',help='Editable terminal workspace'); workspace.add_argument('--input')
    merge=sub.add_parser('merge'); merge.add_argument('sources',nargs='+'); merge.add_argument('--ids',nargs='*'); merge.add_argument('--kind',choices=KINDS); merge.add_argument('--conflict',choices=['reject','keep','incoming'],default='reject'); merge.add_argument('--apply',action='store_true')
    copy_=sub.add_parser('copy-mappings');copy_.add_argument('output');copy_.add_argument('--ids',nargs='*');copy_.add_argument('--kind',choices=KINDS)
    paste=sub.add_parser('paste-mappings');paste.add_argument('input');paste.add_argument('--conflict',choices=['reject','keep','incoming'],default='reject');paste.add_argument('--apply',action='store_true')
    sub.add_parser('info', help='Account, storage and password age')
    sub.add_parser('password', help='Change local account password')
    remind = sub.add_parser('reminder'); remind.add_argument('state', choices=['on', 'off'])
    help_ = sub.add_parser('help-doc'); help_.add_argument('document', choices=['user', 'errors', 'cli', 'license'])
    imp = sub.add_parser('import-db', help='Open exchange/legacy backup as another database under the active account'); imp.add_argument('input'); imp.add_argument('--title')
    exp = sub.add_parser('export-db', help='Export encrypted database using a separate password'); exp.add_argument('output')
    imp = sub.add_parser('import', help='Extract editable text, even with zero detections'); imp.add_argument('input'); imp.add_argument('output')
    scan = sub.add_parser('scan', help='Save a sensitive review plan; no automatic near-match corrections'); scan.add_argument('input'); scan.add_argument('plan')
    review = sub.add_parser('review', help='Edit candidate inclusion, custom replacement or manual value in plan')
    review.add_argument('plan'); review.add_argument('--original'); review.add_argument('--kind', choices=KINDS)
    review.add_argument('--replacement'); review.add_argument('--regenerate',action='store_true'); review.add_argument('--state', choices=['sensitive','insensitive'])
    review.add_argument('--starts', help='Comma-separated zero-based source offsets; omit to affect all occurrences')
    review.add_argument('--add', action='store_true')
    near = sub.add_parser('near', help='Explicitly confirm/edit/deny a possible original match in a plan')
    near.add_argument('plan'); near.add_argument('imported'); near.add_argument('original'); near.add_argument('decision', choices=['confirm','edit','deny']); near.add_argument('--value')
    redact = sub.add_parser('redact', help='Apply reviewed plan'); redact.add_argument('plan'); redact.add_argument('output'); redact.add_argument('--reviewed', action='store_true', required=True)
    res = sub.add_parser('restore'); res.add_argument('input'); res.add_argument('output'); res.add_argument('--reviewed', action='store_true', required=True)
    res.add_argument('--ids', nargs='*'); res.add_argument('--kind', choices=KINDS)
    lookup = sub.add_parser('lookup'); lookup.add_argument('--query', default=''); lookup.add_argument('--kind', choices=KINDS); lookup.add_argument('--sort', choices=['original','replacement','kind','created'], default='original'); lookup.add_argument('--descending', action='store_true'); lookup.add_argument('--json',action='store_true')
    audit = sub.add_parser('audit'); audit.add_argument('--output')
    delete = sub.add_parser('delete'); delete.add_argument('--ids', nargs='+'); delete.add_argument('--kind', choices=KINDS); delete.add_argument('--confirm', choices=['DELETE'], required=True)
    flush = sub.add_parser('flush'); flush.add_argument('--confirm', choices=['FLUSH'], required=True)
    purge = sub.add_parser('purge-history'); purge.add_argument('--confirm', choices=['PURGE'], required=True)
    edit = sub.add_parser('batch-update'); edit.add_argument('--ids', nargs='*'); edit.add_argument('--kind', choices=KINDS)
    edit.add_argument('--field', choices=['original','replacement','kind'], default='replacement'); edit.add_argument('--find', required=True); edit.add_argument('--replace', required=True); edit.add_argument('--apply', action='store_true')
    ob = sub.add_parser('obfuscate', help='Apply selected saved mappings'); ob.add_argument('input'); ob.add_argument('output'); ob.add_argument('--ids', nargs='*'); ob.add_argument('--kind', choices=KINDS); ob.add_argument('--reviewed', action='store_true', required=True)
    return p


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def write_json(path, value):
    path = output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def read_plan(path, vault):
    path = output_path(path)
    if path.stat().st_size > 20_000_000: raise ValueError('R005: Review plan too large.')
    plan = json.loads(path.read_text(encoding='utf-8'))
    if plan['user'] != vault.data['username']: raise ValueError('R010: Plan belongs to another account.')
    if plan.get('database','main') != getattr(vault,'database_id','main'):raise ValueError('R010: Plan belongs to another database.')
    return plan


def new_password(prompt):
    password = getpass(prompt)
    if password != getpass('Repeat password: '): raise ValueError('Passwords do not match.')
    return password


def selected(vault, args):
    ids, kind = getattr(args, 'ids', None), getattr(args, 'kind', None)
    return [m for m in vault.data['mappings'] if (ids is None or m['id'] in ids) and (kind is None or m['kind'] == kind)]


def run(args):
    if args.command == 'help-doc':
        from importlib.resources import files
        name = {'user':'User-Guide.md', 'errors':'Error-Guide.md', 'cli':'Portable-Forensics-CLI.md', 'license':'License.md'}[args.document]
        print(files('redactor').joinpath('resources/'+name).read_text(encoding='utf-8')); return
    if not args.user: raise ValueError('R001: Supply --user before the command.')
    if args.command == 'create':
        vault = Vault.create(vault_directory(), args.user, new_password('New account password: ')); vault.close(); emit({'created':args.user}); return
    account = Vault.open(vault_directory(), args.user, getpass('Account password: '))
    vault = account
    try:
        from .databases import Database, add_database
        account.commit('account_unlocked',interface='cli')
        if args.command == 'databases':
            emit([{'id':'main','title':'Main database','creator_username':account.data['username']}, *[{'id':key,'title':value['title'],'creator_username':value.get('creator_username',account.data['username'])} for key,value in account.data.get('databases',{}).items()]]); return
        if args.command == 'new-db':
            db=add_database(account,args.title);emit({'id':db.database_id,'title':args.title});db.close();return
        if args.command == 'import-db':
            payload=Vault.read_exchange(Path(args.input),getpass('Export / backup password: '))
            db=add_database(account,args.title or Path(args.input).stem,payload);emit({'opened_database':db.database_id});db.close();return
        if args.database != 'main':
            if args.database not in account.data.get('databases',{}):raise ValueError('R010: Unknown database ID.')
            vault=Database(account,args.database)
        execute(vault, args)
    except Exception as exc:
        from .errors import record
        record(exc, vault)
        raise
    finally:
        vault.close()
        if vault is not account: account.close()


def execute(vault, args):
    command = args.command
    if command == 'workspace':
        from .terminal import workspace
        workspace(vault,args.input);return
    if command == 'copy-mappings':
        rows=[{**m,'_source_database':{'id':getattr(vault,'database_id','main'),'title':vault.data.get('title','Main database')}} for m in selected(vault,args)];write_json(args.output,{'redactor_mappings':rows});vault.commit('mappings_copied',mapping_ids=[m['id'] for m in rows]);return
    if command in ('merge','paste-mappings'):
        from .databases import merge_mappings
        account=getattr(vault,'account',vault)
        rows=[]
        if command=='paste-mappings':
            path=output_path(args.input)
            if path.stat().st_size>10_000_000:raise ValueError('R005: Mapping file too large.')
            rows=json.loads(path.read_text(encoding='utf-8'))['redactor_mappings']
        else:
            for source in args.sources:
                if source==args.database:raise ValueError('R012: Source and destination databases must differ.')
                data=account.data if source=='main' else account.data.get('databases',{}).get(source)
                if data is None:raise ValueError('R012: Unknown source database ID.')
                rows.extend({**m,'_source_database':{'id':source,'title':data.get('title','Main database')}} for m in data['mappings'] if (args.ids is None or m['id'] in args.ids) and (args.kind is None or m['kind']==args.kind))
        decisions={m['original']:args.conflict for m in rows}
        proposed=merge_mappings(vault.data['mappings'],rows,decisions)
        emit({'before':vault.data['mappings'],'after':proposed,'incoming':rows})
        if args.apply:
            old=copy.deepcopy(vault.data)
            try:
                vault.data['mappings']=proposed
                origins=list({json.dumps(m['_source_database'],sort_keys=True):m['_source_database'] for m in rows if m.get('_source_database')}.values())
                vault.commit('databases_merged',incoming=rows,decisions=decisions,affected_databases=[{**o,'access':'read'} for o in origins]+[{'id':args.database,'title':vault.data.get('title','Main database'),'access':'modified'}])
            except Exception:vault.data=old;raise
        return
    if command == 'info':
        emit({'user':args.user,'vault':str(vault.path),'password_age_days':vault.password_age,'reminder':vault.data.get('remind',True)}); return
    if command == 'password':
        vault.change_password(getpass('Current password again: '), new_password('New password: ')); return
    if command == 'reminder':
        vault.data['remind'] = args.state == 'on'; vault.commit('reminder_preference_changed', enabled=vault.data['remind']); return
    if command == 'export-db':
        vault.export_exchange(output_path(args.output), new_password('Separate export password: ')); return
    if command == 'lookup':
        rows = [m for m in selected(vault,args) if args.query.casefold() in json.dumps(m,ensure_ascii=False).casefold()]
        vault.commit('lookup', mapping_ids=[m['id'] for m in rows])
        rows=sorted(rows,key=lambda m:m[args.sort],reverse=args.descending)
        if args.json:emit(rows)
        else:
            headings=['ID','Sensitive value','Replacement','Type']
            cells=[[m['id'],m['original'],m['replacement'],m['kind']] for m in rows]
            widths=[min(48,max([len(headings[i]),*[len(row[i]) for row in cells]])) for i in range(4)]
            print(' | '.join(headings[i].ljust(widths[i]) for i in range(4)))
            print('-+-'.join('-'*w for w in widths))
            for row in cells:print(' | '.join(row[i].replace('\n','\\n').ljust(widths[i]) for i in range(4)))
        return
    if command == 'audit':
        data = {'audit':vault.data['audit'],'imported_audit':vault.data.get('imported_audit',[])}
        if args.output: write_json(args.output,data)
        else: emit(data)
        return
    if command in ('delete','flush','batch-update'):
        if command == 'delete' and not args.ids and not args.kind: raise ValueError('R010: Select IDs or type; use flush for all mappings.')
        rows = selected(vault,args); ids = {m['id'] for m in rows}
        if command == 'batch-update':
            proposed = bulk_proposal(vault.data['mappings'],ids,args.field,args.find,args.replace)
            emit([{'before':a,'after':b} for a,b in zip(vault.data['mappings'],proposed) if a != b])
            if not args.apply: return
        else: proposed = [m for m in vault.data['mappings'] if m['id'] not in ids]
        save_mappings(vault,proposed,command,ids); return
    if command == 'purge-history':
        vault.data['audit'] = []; vault.data.pop('imported_audit',None); vault.commit('history_purged'); return
    if command in ('review','near','redact'):
        plan = read_plan(args.plan,vault)
        if command == 'review':
            if args.add:
                if not args.original or args.original not in plan['text']: raise ValueError('R010: Manual value must exist in input.')
                from .engine import suggest
                kind = args.kind or 'Custom'
                replacement = args.replacement or suggest(kind,[plan['text']],args.original,vault.data['mappings'])
                plan['candidates'].append(asdict(Candidate(args.original,kind,replacement,'Manual')))
            else:
                for c in plan['candidates']:
                    if args.original and c['original'] != args.original: continue
                    if args.kind and c['kind'] != args.kind: continue
                    if args.replacement is not None: c['replacement'] = args.replacement
                    if args.regenerate:
                        from .engine import suggest
                        c['replacement']=suggest(c['kind'],[plan['text'],c['replacement']],c['original'],[m for m in vault.data['mappings'] if m['original']!=c['original']])
                    if args.state:
                        if args.starts:
                            from .engine import candidate_occurrences
                            starts = set(map(int,args.starts.split(',')))
                            current = set(c['included_starts']) if c.get('included_starts') is not None else {a for a,b in candidate_occurrences(plan['text'],Candidate(**c))} if c['selected'] else set()
                            c['included_starts'] = sorted(current | starts if args.state == 'sensitive' else current - starts)
                            c['selected'] = bool(c['included_starts'])
                        else: c['selected'] = args.state == 'sensitive'; c['included_starts'] = None
            write_json(args.plan,plan); return
        if command == 'near':
            before = plan['text']
            if args.decision != 'deny':
                value = args.original if args.decision == 'confirm' else args.value
                if not value: raise ValueError('R010: Edit requires --value.')
                plan['text'] = replace_exact(before,{args.imported:value})[0]
                plan['candidates'] = [asdict(c) for c in detect(plan['text'],vault.data['mappings'])]
            audit_text(vault,'similar_'+args.decision,before,plan['text'])
            write_json(args.plan,plan); return
        text = plan['text']
        candidates = [Candidate(**c) for c in plan['candidates']]
        mappings, conversions = prepare_mappings(candidates,vault.data['mappings'],text,strict=True)
        result, counts = replace_candidates(text,candidates,conversions)
        old = copy.deepcopy(vault.data)
        try:
            existing_ids={m['id'] for m in old['mappings']}
            mappings=[m for m in mappings if m['id'] in existing_ids or m['original'] in counts]
            vault.data['mappings'] = mappings
            audit_text(vault,'redacted',text,result,mapping_ids=[m['id'] for m in mappings if m['original'] in counts])
        except Exception: vault.data = old; raise
        export_file(output_path(args.output),result); emit({'occurrences':sum(counts.values())}); return
    text = read_file(Path(args.input)).text
    vault.commit('document_import',input_text=text,source=str(Path(args.input)),input_sha256=hashlib.sha256(text.encode()).hexdigest())
    if command == 'import':
        export_file(output_path(args.output),text); emit({'characters':len(text),'notice':NOTICE}); return
    if command == 'scan':
        candidates = detect(text,vault.data['mappings'])
        write_json(args.plan,{'user':vault.data['username'],'database':getattr(vault,'database_id','main'),'text':text,'candidates':[asdict(c) for c in candidates],'similar':[asdict(m) for m in find_similar_values(text,vault.data['mappings'])]})
        emit({'candidates':len(candidates),'notice':'No sensitive values identified. Edit the input or add manual values.' if not candidates else 'Review the plan; it contains sensitive originals.'}); return
    rows = selected(vault,args)
    if command == 'restore': result,counts,_ = restore(text,rows)
    else:
        from .engine import validate_mappings
        validate_mappings(rows,strict=True)
        result,counts = replace_exact(text,{m['original']:m['replacement'] for m in rows})
    audit_text(vault,command,text,result,mapping_ids=[m['id'] for m in rows],occurrences=sum(counts.values()))
    export_file(output_path(args.output),result)


def main(argv=None):
    configure()
    import os
    os.environ.setdefault('QT_QPA_PLATFORM','windows' if sys.platform == 'win32' else 'offscreen')
    from PySide6.QtGui import QGuiApplication
    gui_runtime=QGuiApplication.instance() or QGuiApplication([])
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    args = parser().parse_args(argv)
    from PySide6.QtCore import QLockFile
    lock = QLockFile(str(vault_directory().parent / 'redactor.lock')); lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        print('R007: Close the other Redactor session before using CLI.',file=sys.stderr); return 2
    try:
        run(args); return 0
    except Exception as exc:
        from .errors import record
        info = record(exc)
        print(info['code'] + ': ' + str(exc) + '\nRecommended action: ' + info['recommended_action'] + '\nHelp: ' + info['help'],file=sys.stderr)
        return 2
    finally: lock.unlock()


if __name__ == '__main__':
    sys.exit(main())

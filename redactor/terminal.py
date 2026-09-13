# SPDX-License-Identifier: GPL-3.0-or-later
"""Editable full-screen terminal workspace, sharing GUI transformation services."""
import csv
import io
import copy
from .engine import Candidate, detect, find_similar_values, prepare_mappings, replace_candidates, restore, replace_exact
from .operations import audit_text
from .portable import output_path
from .formats import read_file, export_file


def table_text(candidates):
    stream=io.StringIO(); writer=csv.writer(stream,delimiter='\t',lineterminator='\n')
    writer.writerow(['Use','Type','Original','Replacement','Included offsets (blank=all)'])
    for c in candidates:writer.writerow(['yes' if c.selected else 'no',c.kind,c.original,c.replacement,','.join(map(str,sorted(c.included_starts))) if c.included_starts is not None else ''])
    return stream.getvalue()


def table_candidates(text):
    rows=list(csv.reader(io.StringIO(text),delimiter='\t'))
    candidates=[]
    for row in rows[1:]:
        if not row:continue
        if len(row)!=5 or row[0].casefold() not in ('yes','no'):raise ValueError('R010: Each substitution row needs five tab-separated columns; Use must be yes or no.')
        starts=set(map(int,row[4].split(','))) if row[4] else None
        candidates.append(Candidate(row[2],row[1],row[3],'Terminal review',row[0].casefold()=='yes',starts))
    return candidates


def workspace(vault, input_file=None):
    from prompt_toolkit import Application
    from prompt_toolkit.layout import Layout, HSplit, VSplit
    from prompt_toolkit.widgets import TextArea, Frame, Label
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style
    from prompt_toolkit.layout.processors import TabsProcessor
    from prompt_toolkit.shortcuts import yes_no_dialog, message_dialog, radiolist_dialog, input_dialog
    source=TextArea(text=read_file(__import__('pathlib').Path(input_file)).text if input_file else '',scrollbar=True,line_numbers=True)
    output=TextArea(read_only=True,scrollbar=True)
    table=TextArea(text=table_text([]),scrollbar=True,input_processors=[TabsProcessor(tabstop=16,char1=' ',char2=' ')])
    destination=TextArea(text='exports/work.txt',height=1,multiline=False)
    status=TextArea(text='Tab / Shift-Tab: move focus. Edit input, then F5 to scan. Table is editable TSV. Ctrl-Q exits and locks.',read_only=True,height=3)
    state={'ready':False}
    def invalidate(_):state['ready']=False;output.text=''
    source.buffer.on_text_changed+=invalidate
    table.buffer.on_text_changed+=invalidate
    bindings=KeyBindings()
    @bindings.add('tab')
    def focus_next(event):event.app.layout.focus_next()
    @bindings.add('s-tab')
    def focus_previous(event):event.app.layout.focus_previous()
    @bindings.add('c-t')
    def insert_tab(event):
        if event.app.layout.current_control==table.control:table.buffer.insert_text('\t')
    @bindings.add('c-q')
    def quit_(event):event.app.exit()
    async def modal(dialog):
        result=await dialog.run_async()
        app.renderer.reset();app.invalidate()
        return result
    async def failure(exc):
        from .errors import record
        info=record(exc,vault)
        status.text=info['code']+': '+str(exc)+'\n'+info['recommended_action']+'\nHelp: F1 → '+info['help']
        await modal(message_dialog(title=info['title'],text=status.text))
    @bindings.add('f3')
    async def import_(event):
        path=await modal(input_dialog(title='Import local file',text='Filename:'))
        if not path:return
        try:
            imported=read_file(__import__('pathlib').Path(path))
            vault.commit('document_import',source=path,input_text=imported.text)
            source.text=imported.text;table.text=table_text([]);status.text=imported.note+' F5 scans; input remains editable.'
        except Exception as exc:await failure(exc)
    @bindings.add('f4')
    async def manual(event):
        from .engine import suggest,KINDS
        value=await modal(input_dialog(title='Manual sensitive value',text='Exact value from input:'))
        if not value:return
        try:
            if value not in source.text:raise ValueError('R010: Manual value must appear in input.')
            kind=await modal(radiolist_dialog(title='Sensitive type',text='Choose a type:',values=[(k,k) for k in KINDS]))
            if kind is None:return
            candidates=table_candidates(table.text)
            replacement=suggest(kind,[source.text],value,vault.data['mappings'])
            candidates=[c for c in candidates if c.original!=value]+[Candidate(value,kind,replacement,'Manual')]
            table.text=table_text(candidates)
        except Exception as exc:await failure(exc)
    @bindings.add('f5')
    async def scan(event):
        try:
            text=source.text
            for match in find_similar_values(text,vault.data['mappings']):
                decision=await modal(radiolist_dialog(title='Possible saved original',text=f'{match.imported}\nSaved original: {match.original}\n{match.reason}',values=[('deny','Deny; keep text'),('confirm','Confirm saved spelling'),('edit','Edit value')]))
                if decision is None:break
                replacement=match.original
                if decision=='edit':replacement=await modal(input_dialog(title='Edit imported value',text='Corrected text:',default=match.imported))
                revised=replace_exact(text,{match.imported:replacement})[0] if decision!='deny' and replacement else text
                audit_text(vault,'similar_'+decision,text,revised);text=revised
            source.text=text
            candidates=detect(text,vault.data['mappings']);table.text=table_text(candidates)
            status.text=f'{len(candidates)} values. Edit Use/type/original/replacement/offsets, then F6 after review.' if candidates else 'No sensitive information identified. Input remains editable; add manual rows or edit and rescan.'
        except Exception as exc:await failure(exc)
    @bindings.add('f6')
    async def redact(event):
        previous=copy.deepcopy(vault.data)
        try:
            candidates=table_candidates(table.text)
            mappings,conversions=prepare_mappings(candidates,vault.data['mappings'],source.text,strict=True)
            result,counts=replace_candidates(source.text,candidates,conversions)
            vault.data['mappings']=mappings;audit_text(vault,'redacted',source.text,result,mapping_ids=[m['id'] for m in mappings if m['original'] in counts])
            output.text=result;state['ready']=True;status.text=f'Replaced {sum(counts.values())} occurrences. Inspect output. F2 exports to the filename below.'
        except Exception as exc:vault.data=previous;await failure(exc)
    @bindings.add('f7')
    async def restore_(event):
        if not await modal(yes_no_dialog(title='Restore sensitive originals?',text='Restored output contains sensitive originals. Continue?')):return
        try:
            result,counts,unknown=restore(source.text,vault.data['mappings'])
            audit_text(vault,'restored',source.text,result)
            output.text=result;state['ready']=True;status.text=f'Restored {sum(counts.values())} occurrences; {len(unknown)} unresolved markers. Review before export.'
        except Exception as exc:await failure(exc)
    @bindings.add('f2')
    async def save(event):
        try:
            if not state['ready']:raise ValueError('R010: Generate a reviewed result first; edits invalidate old output.')
            path=output_path(destination.text)
            if path.exists() and not await modal(yes_no_dialog(title='Replace existing output?',text=str(path))):return
            export_file(path,output.text);vault.commit('export_output',destination=str(path),output_text=output.text)
            status.text='Exported '+str(path)
        except Exception as exc:await failure(exc)
    @bindings.add('f1')
    async def help_(event):
        from importlib.resources import files
        await modal(message_dialog(title='Redactor Error Guide',text=files('redactor').joinpath('resources/Error-Guide.md').read_text(encoding='utf-8')[:16000]))
    body=HSplit([Label('R/ Redactor  |  Offline local workspace  |  '+vault.data['username']+' / '+vault.data.get('title','Main database'),style='class:brand'),
                 Label('F1 Help  F2 Export  F3 Import  F4 Manual  F5 Scan  F6 Apply  F7 Restore  Ctrl-Q Exit'),
                 VSplit([Frame(source,'INPUT'),Frame(output,'WORK PRODUCT')],padding=1),
                 Frame(table,'SUGGESTED SUBSTITUTIONS — editable TSV; use yes/no; add rows for manual values'),
                 Frame(destination,'Export filename inside portable folder'),status])
    app=Application(layout=Layout(body,focused_element=source),key_bindings=bindings,full_screen=True,mouse_support=True,
                    style=Style.from_dict({'':'bg:#f5f6f2 #203b37','brand':'bg:#245b48 #ffffff bold','frame.label':'#245b48 bold'}))
    app.run()

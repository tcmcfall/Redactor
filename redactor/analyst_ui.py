# SPDX-License-Identifier: GPL-3.0-or-later
"""Analyst exchange and batch review dialogs."""
import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QInputDialog, QLineEdit, QMessageBox, QDialog, QVBoxLayout, QTextEdit
from .portable import directory, output_path, database_export_path
from .vault import Vault
from .operations import bulk_proposal, save_mappings, audit_text
from .engine import restore, replace_exact, validate_mappings


def import_account_dialog(parent, directory_path):
    from .app import error
    path, _ = QFileDialog.getOpenFileName(parent, 'Import encrypted database', str(directory('exports')), 'Encrypted databases (*.zip *.tar *.7z *.zip7 *.rar *.redactor *.vault)')
    if not path: return None
    fields = []
    for title, prompt, secret in [('Export password', 'Password protecting this file:', True), ('Local analyst username', 'New local username; existing accounts cannot be overwritten:', False), ('Local password', 'New local account passphrase (12+ characters):', True), ('Confirm local password', 'Repeat the new local passphrase:', True)]:
        value, ok = QInputDialog.getText(parent, title, prompt, QLineEdit.EchoMode.Password if secret else QLineEdit.EchoMode.Normal)
        if not ok: return None
        fields.append(value)
    try:
        if fields[2] != fields[3]: raise ValueError('Passwords do not match.')
        return Vault.import_exchange(Path(path), fields[0], directory_path, fields[1], fields[2])
    except Exception as exc: error(parent, exc)
    return None


class AnalystActions:
    def backup(self):
        from .app import error
        path, selected_format = QFileDialog.getSaveFileName(self, 'Choose exported database name and location', str(directory('exports') / 'analyst.zip'), 'ZIP (*.zip);;Compressed TAR (*.tar);;7z / zip7 (*.7z);;RAR - portable utility required (*.rar)')
        if not path: return
        suffix={ 'ZIP':'.zip', 'Compressed':'.tar', '7z':'.7z', 'RAR':'.rar' }[selected_format.split()[0]]
        if Path(path).suffix.lower()!=suffix: path=str(Path(path).with_suffix(suffix))
        password, ok = QInputDialog.getText(self, 'Required export password', 'Password for this exported copy (12+ characters). This replaces the local database password for the exported copy only:', QLineEdit.EchoMode.Password)
        if not ok: return
        repeat, ok = QInputDialog.getText(self, 'Confirm export password', 'Repeat the export passphrase:', QLineEdit.EchoMode.Password)
        if not ok: return
        try:
            if password != repeat: raise ValueError('Passwords do not match.')
            destination = database_export_path(path)
            self.vault.export_exchange(destination, password)
            QMessageBox.information(self, 'Exchange saved', f'Exported database: {destination}\n\nThis copy requires the export password you supplied. The original local database keeps its current password. Communicate the export password separately. Importing analysts protect their local copies with their own account passwords.')
        except Exception as exc: error(self, exc)

    def import_database(self):
        from .app import error
        from .databases import add_database
        path, _ = QFileDialog.getOpenFileName(self, 'Open exported database', str(directory('exports')), 'Encrypted databases (*.zip *.tar *.7z *.zip7 *.rar *.redactor *.vault)')
        if not path: return
        password, ok = QInputDialog.getText(self, 'Export password', 'Password set when this database was exported:', QLineEdit.EchoMode.Password)
        if not ok: return
        name, ok = QInputDialog.getText(self, 'Database tab title', 'Title for this database:', text=Path(path).stem)
        if not ok: return
        try:
            payload = Vault.read_exchange(Path(path),password)
            database = add_database(self.account_vault,name,payload)
            self.open_databases.append(database); index = self.database_tabs.addTab(name)
            self.database_tabs.setCurrentIndex(index)
        except Exception as exc: error(self,exc)

    def new_database(self):
        from .databases import add_database
        from .app import error
        name,ok=QInputDialog.getText(self,'New database','Title:')
        if not ok: return
        try:
            self.open_databases.append(add_database(self.account_vault,name))
            self.database_tabs.setCurrentIndex(self.database_tabs.addTab(name))
        except Exception as exc: error(self,exc)

    def switch_database(self,index):
        if index < 0 or index == self.active_database: return
        if self.busy:
            self.database_tabs.blockSignals(True); self.database_tabs.setCurrentIndex(self.active_database); self.database_tabs.blockSignals(False); return
        import copy
        self.workspace_states[self.active_database] = {'input':self.source.toPlainText(),'output':self.output.toPlainText(),
             'candidates':copy.deepcopy(self.candidates),'mode':self.mode,'has_output':self.has_output,'input_path':self.input_path}
        self.vault = self.open_databases[index]; self.active_database=index
        self.denied_similar.clear()
        state=self.workspace_states.get(index,{})
        self.switch_mode(state.get('mode','redact'))
        self.source.setPlainText(state.get('input',''))
        self.candidates=state.get('candidates',[]); self.fill_candidates()
        self.output.setPlainText(state.get('output','')); self.has_output=state.get('has_output',False)
        self.input_path=state.get('input_path'); self.update_actions(); self.refresh_vault(); self.refresh_audit(); self.update_age()
        self.notice.setText('Active database: '+self.database_tabs.tabText(index)+'. Local creator: '+self.vault.data.get('creator_username',self.account_vault.data['username'])+'. Only this creator’s account password unlocks the local copy. Use copy/paste or Merge to combine values.')

    def vault_menu_actions(self, menu, column):
        menu.addSeparator()
        menu.addAction('Copy selected rows', self.copy_mappings)
        menu.addAction('Paste rows into this database…', self.paste_mappings)
        menu.addAction('Copy selected column values', lambda: self.copy_cells(column))
        if column in (0, 1, 2):
            menu.addAction('Paste into selected column values…', lambda: self.paste_cells(column))
        menu.addAction('Edit selected values…', self.edit_mapping)
        menu.addAction('Delete selected rows…', self.delete_selected)

    def vault_context_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        item = self.vault_table.itemAt(pos)
        if item is None: return
        if not item.isSelected(): self.vault_table.setCurrentItem(item)
        menu = QMenu(self.vault_table)
        menu.addAction('Copy this cell', lambda: self.copy_cells(item.column(), [item.row()]))
        if item.column() in (0, 1, 2):
            menu.addAction('Paste into this cell…', lambda: self.paste_cells(item.column(), [item.row()]))
        self.vault_menu_actions(menu, item.column())
        menu.exec(self.vault_table.viewport().mapToGlobal(pos))

    def copy_cells(self, column, rows=None):
        from PySide6.QtWidgets import QApplication
        from .app import confirm
        if rows is None: rows = sorted({i.row() for i in self.vault_table.selectionModel().selectedRows() if not self.vault_table.isRowHidden(i.row())})
        if not rows: return
        if not confirm(self, 'Copy sensitive values?', 'Copy the selected values to the clipboard? Clipboard history and other applications may retain them.'): return
        text = '\n'.join(self.vault_table.item(row, column).text() for row in rows)
        self.vault.commit('mapping_cells_copied', mapping_ids=[self.mapping_at(row)['id'] for row in rows], column=column)
        QApplication.clipboard().setText(text); self.owned_clipboard=text; self.clipboard_timer.start(60000)

    def paste_cells(self, column, rows=None):
        import copy
        from PySide6.QtWidgets import QApplication
        from .app import error, confirm
        if column not in (0, 1, 2): return
        if rows is None: rows = sorted({i.row() for i in self.vault_table.selectionModel().selectedRows() if not self.vault_table.isRowHidden(i.row())})
        if not rows: return
        try:
            text = QApplication.clipboard().text()
            if not text or len(text)>1_000_000: raise ValueError('R010: Clipboard must contain nonempty text within one million characters.')
            values = text.splitlines()
            if len(values)==1: values *= len(rows)
            if len(values)!=len(rows): raise ValueError('R010: Paste one value for all selected rows or one line per selected row.')
            field = ['original', 'replacement', 'kind'][column]
            updates = {self.mapping_at(row)['id']: value for row,value in zip(rows,values)}
            proposed=copy.deepcopy(self.vault.data['mappings'])
            changes=[]
            for mapping in proposed:
                if mapping['id'] not in updates: continue
                old=mapping[field]; new=updates[mapping['id']]
                if not new.strip(): raise ValueError('R010: Values cannot be blank.')
                if field=='replacement' and old!=new:
                    mapping['aliases']=list(dict.fromkeys([*mapping.get('aliases',[]),old]))
                    mapping['aliases']=[a for a in mapping['aliases'] if a!=new]
                mapping[field]=new; changes.append(f'{old} → {new}')
            validate_mappings(proposed, strict=True)
            if not confirm(self,'Review pasted changes', '\n'.join(changes)+'\n\nApply these exact changes? Original edits alter restoration targets; replacement edits retain prior aliases.'): return
            save_mappings(self.vault,proposed,'mapping_cells_pasted',set(updates))
            self.invalidate(); self.candidates=[]; self.fill_candidates(); self.refresh_vault()
        except Exception as exc: error(self,exc)

    def copy_mappings(self):
        from .app import confirm
        from PySide6.QtWidgets import QApplication
        ids=self.selected_mapping_ids()
        if not ids: return
        if not confirm(self,'Copy sensitive mappings?','This copies originals and replacements to the clipboard for pasting into another database. Continue?'): return
        rows=[m for m in self.vault.data['mappings'] if m['id'] in ids]
        self.vault.commit('mappings_copied',mapping_ids=sorted(ids))
        origin={'id':getattr(self.vault,'database_id','main'),'title':self.database_tabs.tabText(self.active_database)}
        text=json.dumps({'redactor_mappings':[{**m,'_source_database':origin} for m in rows]},ensure_ascii=False)
        QApplication.clipboard().setText(text); self.owned_clipboard=text; self.clipboard_timer.start(60000)

    def paste_mappings(self):
        from .app import error
        from PySide6.QtWidgets import QApplication
        try:
            text=QApplication.clipboard().text()
            if len(text)>10_000_000: raise ValueError('R005: Clipboard mapping limit exceeded.')
            rows=json.loads(text)['redactor_mappings']
            self.review_merge(rows,'Clipboard')
        except Exception as exc: error(self,exc)

    def review_merge(self,rows,source):
        from .databases import merge_mappings
        from .app import confirm, error
        decisions={}
        existing={m['original']:m for m in self.vault.data['mappings']}
        for index, row in enumerate(rows):
            old=existing.get(row['original'])
            if old and (old['replacement']!=row['replacement'] or old['kind']!=row['kind']):
                choice,ok=QInputDialog.getItem(self,'Merge conflict',f"Original: {row['original']}\nCurrent: {old['replacement']} ({old['kind']})\nIncoming: {row['replacement']} ({row['kind']})\nChoose the target value:",['Keep current','Use incoming and retain current alias'],0,False)
                if not ok: return
                decisions[f"{index}:{row['original']}"]='keep' if choice=='Keep current' else 'incoming'
                if choice=='Keep current':continue
            existing[row['original']]=row
        try:
            proposed=merge_mappings(self.vault.data['mappings'],rows,decisions)
            box=QMessageBox(self);box.setWindowTitle('Review merge before saving')
            box.setText(f'Merge {len(rows)} chosen mappings from {source} into {self.database_tabs.tabText(self.active_database)}? Source databases remain unchanged. Expand details to review the full proposal.')
            box.setDetailedText(json.dumps({'decisions':decisions,'incoming':rows,'result':proposed},indent=2,ensure_ascii=False))
            box.setStandardButtons(QMessageBox.StandardButton.Ok|QMessageBox.StandardButton.Cancel);box.setDefaultButton(QMessageBox.StandardButton.Cancel)
            if box.exec()!=QMessageBox.StandardButton.Ok: return
            old_data=__import__('copy').deepcopy(self.vault.data)
            try:
                self.vault.data['mappings']=proposed
                sources=list({json.dumps(m['_source_database'],sort_keys=True):m['_source_database'] for m in rows if m.get('_source_database')}.values())
                affected=[{**origin,'access':'read'} for origin in sources]+[{'id':getattr(self.vault,'database_id','main'),'title':self.database_tabs.tabText(self.active_database),'access':'modified'}]
                self.vault.commit('databases_merged',source=source,incoming=rows,decisions=decisions,mapping_ids=[m['id'] for m in proposed],affected_databases=affected)
            except Exception:
                self.vault.data=old_data;raise
            self.invalidate();self.candidates=[];self.fill_candidates();self.refresh_vault()
        except Exception as exc: error(self,exc)

    def merge_databases(self):
        from PySide6.QtWidgets import QTreeWidget,QTreeWidgetItem,QDialogButtonBox
        dialog=QDialog(self);dialog.setWindowTitle('Choose databases and mappings to merge');dialog.resize(900,650)
        layout=QVBoxLayout(dialog);tree=QTreeWidget();tree.setHeaderLabels(['Database / original','Replacement','Type'])
        for index,db in enumerate(self.open_databases):
            if index==self.active_database: continue
            parent=QTreeWidgetItem(tree,[self.database_tabs.tabText(index),'',''])
            parent.setFlags(parent.flags()|Qt.ItemFlag.ItemIsAutoTristate|Qt.ItemFlag.ItemIsUserCheckable);parent.setCheckState(0,Qt.CheckState.Unchecked)
            for mapping in db.data['mappings']:
                child=QTreeWidgetItem(parent,[mapping['original'],mapping['replacement'],mapping['kind']])
                child.setFlags(child.flags()|Qt.ItemFlag.ItemIsUserCheckable);child.setCheckState(0,Qt.CheckState.Unchecked)
                child.setData(0,Qt.ItemDataRole.UserRole,{**mapping,'_source_database':{'id':getattr(db,'database_id','main'),'title':self.database_tabs.tabText(index)}})
        layout.addWidget(tree);tree.expandAll();tree.resizeColumnToContents(0)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        rows=[]
        for i in range(tree.topLevelItemCount()):
            parent=tree.topLevelItem(i)
            for j in range(parent.childCount()):
                child=parent.child(j)
                if child.checkState(0)==Qt.CheckState.Checked:rows.append(child.data(0,Qt.ItemDataRole.UserRole))
        if rows:self.review_merge(rows,'selected database tabs')

    def mapping_at(self, row):
        item = self.vault_table.item(row, 0)
        if not item: return None
        return next((m for m in self.vault.data['mappings'] if m['id'] == item.data(Qt.ItemDataRole.UserRole)), None)

    def select_visible_vault(self):
        self.vault_table.clearSelection()
        for row in range(self.vault_table.rowCount()):
            if not self.vault_table.isRowHidden(row):
                for col in range(self.vault_table.columnCount()): self.vault_table.item(row, col).setSelected(True)

    def selected_mapping_ids(self):
        return {self.mapping_at(i.row())['id'] for i in self.vault_table.selectionModel().selectedRows() if not self.vault_table.isRowHidden(i.row())}

    def bulk_update(self):
        from .app import error
        ids = self.selected_mapping_ids()
        if not ids: return error(self, 'R010: Select visible vault rows first.')
        field, ok = QInputDialog.getItem(self, 'Batch update', 'Field:', ['replacement', 'original', 'kind'], 0, False)
        if not ok: return
        find, ok = QInputDialog.getText(self, 'Batch update', 'Exact text to find (case-sensitive):')
        if not ok: return
        replacement, ok = QInputDialog.getText(self, 'Batch update', 'Replace with:')
        if not ok: return
        try:
            proposed = bulk_proposal(self.vault.data['mappings'], ids, field, find, replacement)
            changes = [(a, b) for a, b in zip(self.vault.data['mappings'], proposed) if a != b]
            if not changes: return error(self, 'R010: No selected values contain the requested text.')
            box = QMessageBox(self); box.setWindowTitle('Review exact batch changes')
            box.setText(f'Update {len(changes)} mappings? Original edits change historical restoration targets. Replacement edits retain older aliases. Expand details to review every change.')
            box.setDetailedText('\n\n'.join(f"{a[field]} → {b[field]}" for a, b in changes))
            box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            box.setDefaultButton(QMessageBox.StandardButton.Cancel)
            if box.exec() != QMessageBox.StandardButton.Ok: return
            save_mappings(self.vault, proposed, 'bulk_mapping_update', ids)
            self.invalidate(); self.candidates = []; self.fill_candidates(); self.refresh_vault()
        except Exception as exc: error(self, exc)

    def transform_selected(self, restoring):
        from .app import error, confirm
        ids = self.selected_mapping_ids()
        if not ids: return error(self, 'R010: Select vault rows first.')
        if not confirm(self, 'Transform selected mappings?', 'Apply only selected mappings to current input? Other values remain unchanged. Review before export.'): return
        mappings = [m for m in self.vault.data['mappings'] if m['id'] in ids]
        text = self.source.toPlainText()
        try:
            if restoring:
                result, counts, _ = restore(text, mappings)
            else:
                validate_mappings(mappings, strict=True)
                result, counts = replace_exact(text, {m['original']: m['replacement'] for m in mappings})
            audit_text(self.vault, 'bulk_restore' if restoring else 'bulk_obfuscate', text, result, mapping_ids=sorted(ids), occurrences=sum(counts.values()))
            self.switch_mode('restore' if restoring else 'redact')
            self.output.setPlainText(result); self.has_output = True; self.update_actions(); self.show_page(0)
            self.notice.setText(f'Applied {sum(counts.values())} occurrences. Other values remain unchanged; review before sharing.')
        except Exception as exc: error(self, exc)

    def audit_detail(self, item):
        from .app import button
        event = item.data(Qt.ItemDataRole.UserRole)
        dialog = QDialog(self); dialog.setWindowTitle('Sensitive audit detail'); dialog.resize(900, 650)
        layout = QVBoxLayout(dialog); viewer = QTextEdit(); viewer.setReadOnly(True)
        viewer.setPlainText(json.dumps(event, indent=2, ensure_ascii=False)); layout.addWidget(viewer)
        layout.addWidget(button('Close', dialog.accept)); dialog.exec()

# SPDX-License-Identifier: GPL-3.0-or-later
"""Stable error references; diagnostic files never contain raw document values."""
import json
from .portable import directory
from .vault import now

CATALOG = {
 'R001': ('Unlock or password problem', 'Check account spelling, password and keyboard layout. Import an intact encrypted backup if needed. Passwords cannot be recovered.'),
 'R002': ('Ambiguous substitutions', 'Review overlapping rows together. Use distinct replacements, or restore already-obfuscated input before scanning again.'),
 'R003': ('Forensic constraint conflict', 'Review the named length/domain/IP constraint. Regenerate a complete related group in a fresh project vault, or correct the custom substitute. Do not use misleading output.'),
 'R004': ('Unsupported or damaged document', 'Use a supported modern format. Save a local UTF-8 text copy or re-export the source document and retry.'),
 'R005': ('Document size or processing limit', 'Split the document into smaller files or pages; reduce oversized images. Retry each part.'),
 'R006': ('Portable OCR unavailable', 'Use a native portable package containing tools/tesseract and English tessdata. Check the executable and language files; retry a clearer image.'),
 'R007': ('Storage or permissions problem', 'Check free space, folder write permissions and media connection. Close other Redactor processes. Keep your existing vault intact and retry.'),
 'R008': ('Portable output location required', 'Choose a file within the Redactor folder. Move the entire folder when transferring work to another device.'),
 'R009': ('Exchange file rejected', 'Check the export password and file integrity. Use a new local analyst username. Do not overwrite a live account; export again from the source if necessary.'),
 'R010': ('Input or selection needs review', 'Check the selected rows, nonempty values and requested action. Review the full error detail and correct the input.'),
 'R011': ('Database archive or checksum problem', 'Choose ZIP, TAR or 7z; RAR needs a licensed native tool inside tools/rar. For checksum mismatch, obtain a fresh intact export. SHA-256/SHA-512 detect corruption; AES-GCM authenticates the encrypted contents.'),
 'R012': ('Database merge conflict', 'Review conflicting original/replacement pairs. Keep the destination or choose incoming explicitly. Resolve domain/IP/length conflicts as a complete group. Preview again before applying.'),
 'R999': ('Unexpected failure', 'Keep the original files. Retry once with a synthetic sample; consult the diagnostic event and Error Guide. Report the error code and app version without sensitive material.'),
}


def explain(message):
    text = str(message)
    code = next((c for c in CATALOG if c in text), None)
    if not code:
        groups = [('R001', ('password','unlock','username')), ('R002', ('overlap','duplicat','existing replacement','already appears')),
                  ('R006', ('ocr','tesseract')), ('R005', ('limit','exceeds','too large','timeout')),
                  ('R007', ('permission','disk','denied','read-only','no space','replace failed')),
                  ('R004', ('format','utf-','zip','pdf','document')), ('R010', ('empty','choose','select','value'))]
        code = next((c for c, words in groups if any(w in text.lower() for w in words)), 'R999')
    title, action = CATALOG[code]
    return {'code': code, 'title': title, 'recommended_action': action, 'help': f'Error-Guide.md — {code}'}


def record(message, vault=None):
    info = explain(message)
    event = {'at': now(), **info}
    # Outside encrypted storage record only categories, never exception text or usernames.
    try:
        with (directory('data/logs') / 'errors.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(event) + '\n')
    except OSError:
        pass
    if vault and vault.key:
        try:
            vault.commit('error', **info)  # not raw exception strings, which may contain passwords
        except Exception:
            pass
    return info

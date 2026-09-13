# Redactor User Guide — version 0.2.2

Redactor substitutes reviewed sensitive values locally and restores unchanged substitutes later. The desktop and CLI share the same encrypted databases and conversion rules. Detection is heuristic: review the entire input, not just suggested fields.

## Quick start

1. Open Redactor.exe (Windows), Redactor.app (macOS), or Redactor (RHEL) from the portable folder. Create a local username and password of at least 12 characters. Keep the password securely; there is no recovery service.
2. Import a supported document or paste text into INPUT. A file with no detected sensitive values remains editable. Select overlooked text and choose Mark selection sensitive; review or customize its suggested replacement.
3. Review each suggested occurrence. Use column header filters, Shift/Ctrl selection and Sensitive/Insensitive buttons. Choose whether changes apply to all same values or just selected occurrences. Repeated selected originals share one replacement.
4. Review the full source, then choose Replace selected values. Inspect WORK PRODUCT for omissions before copying or exporting it to an online AI tool yourself. Redactor never sends data to that tool.
5. Ask the AI to retain substituted values exactly, including capitalization and spelling. Copy the completed work into INPUT, select Restore work product, restore the saved originals. Compare with source evidence and the mapping lookup before reporting.
6. Complete required audits and retention work, then remove mappings/history that are no longer needed. Deletion can make outstanding obfuscated work unrestorable.

## Formats and educational examples

Import: TXT, Markdown, CSV, TSV, JSON, XML, HTML, LOG, PDF, DOCX, XLSX, PPTX, RTF, ODT, ODS, ODP, PNG, JPEG, TIFF, BMP and WebP. Export: TXT, Markdown, CSV, TSV, PDF, DOCX, XLSX, PPTX, RTF, ODT, ODS, ODP and text rendered as PNG/JPEG/TIFF/BMP/WebP. Only TIFF supports multi-page image output. DOC/XLS/PPT must be converted locally to modern formats first.

Exports are fresh content-only files. They do not preserve source layout, figures, formulas, metadata, embedded objects or original edit history. Excel formulas are read as cached values; missing caches cannot be inferred. PDF image-only pages and standalone images use bundled English OCR; Office embedded-image text and mixed-content PDF imagery require separate visual review. Text is UTF-8/UTF-16. See Error Guide for limits and recovery.

Help → Practice examples contains synthetic corporate notes, personal identifiers, government-style reports, email/network evidence and structured data. Use a separate Training database. Help → Practice workbook explains expected review decisions and exact round-trip checks. Practice false positives, manually mark an overlooked value, compare repeated replacements, edit a returned token and observe exact restoration limits, then practice export/import and a selected-row merge between two training databases. Never substitute these exercises for reviewing real evidence.

# Portable analysis, database management and CLI reference

This reference covers portable storage, forensic substitutions, database exchange, audit records and command-line operation.

## Portable folder and launch

On Windows, open **Redactor.exe** in the root folder. **Redactor-cli.exe** is the console alternative. Keep `_internal`, `tools`, `data` and the executable together. No installation or account registration is needed. Move or copy the entire folder while all Redactor sessions are closed. The current project checkout uses the same layout, with the latest executable directly in its root. A Git source checkout alone is not a compiled application: download the native portable binary package or build it.

On macOS, keep Redactor.app and its sibling data/tools folders together in one writable folder; application data is outside the signed .app bundle but inside the portable folder. On RHEL, run `./Redactor` or `./Redactor-cli` from the extracted folder. Native builds are platform/architecture specific. A Windows executable cannot run on macOS or RHEL. Linux still requires compatible OS desktop libraries and drivers; a native build is not a replacement for the operating system. macOS and RHEL native validation must be completed on those systems before calling their binaries verified.

The program creates `data/databases`, `data/logs`, `data/tmp` and `exports` beneath its portable root. Work-product and plaintext audit exports stay within that root, including resolved symlink targets. Password-protected database exchanges may be saved to any filename and writable location you choose, including a removable drive or a folder outside Redactor. Import can read a local file from another folder without changing it. There is no automatic download, telemetry, update check, remote authentication, or network lookup. Build/dependency acquisition and Git publishing are separate developer operations that use the network. Using a network-mounted folder causes operating-system filesystem traffic: use a local disk or removable drive for a physically offline workflow. The application itself does not initiate network communication. Its license URL is displayed for copying, not automatically opened.

Use password-protected database exports for analyst handoffs. Preserve the export until the imported copy has been verified.

## Import and review

Imports with no sensitive matches are successful. The text stays editable and an informational notice invites manual selection or editing. A readable but empty document opens an empty workspace for manual entry. Unsupported, unreadable or oversized files still receive actionable errors. If detection cannot make a valid forensic replacement, the imported text remains available for review; no misleading output is produced.

Each suggestion occurrence has a row. Highlight rows using Shift/Ctrl (Command on macOS where applicable), then use the Sensitive/Insensitive buttons. **Scope** defaults to asking whether to affect all same values or only selected occurrences. Choose an explicit scope in the dropdown to avoid repeated prompts. Excluded occurrences remain in the output unchanged. Merely highlighting rows is not redaction approval.

Right-click column headers to sort or filter values. Filters combine across columns; the right-aligned Clear filters button shows all rows again. Double-click Type to choose a built-in type or enter a custom label (up to 80 characters). Edits apply to highlighted rows and repeated occurrences of the same original. Custom types do not infer network-specific constraints; retain Email, Hostname or IP address when those checks are needed. Drag column dividers horizontally or the border above suggested substitutions vertically to resize panes. The logo scales to its available area, and small windows allow workspace scrolling. Hidden values retain their existing inclusion states.

## Forensic relationships and length

New generated replacements have the same number of Unicode characters as their originals. This is character count, not UTF-8 byte count, glyph width, font metrics or Excel cell display width. Document export remains content-only; matching lengths do not recreate the source document's formatting, graphics, formulas or slide layout.

Email domains and hostname suffixes are mapped consistently. If `alice@abc.gov`, `bob@abc.gov`, `server.abc.gov` and `abc.gov` appear, the substituted domain is shared across all of them. Separate original suffixes cannot collapse into the same substitute. Dot-separated label structure is preserved. Domain relationships are literal DNS suffix relationships; the program does not infer registrable domains from a downloaded suffix list, resolve DNS, or infer that an email local part identifies a separately named person.

For IPv4 and IPv6, the program preserves address equality, IP version and pairwise common binary prefix lengths. Thus membership relationships for every prefix length within the processed addresses are retained. IPv4 octet character widths and IPv6 textual group/compression shape are preserved. Address ordering, numeric distances, geolocation, ownership, routability and associations absent from the input are **not inferred or guaranteed**. Port numbers and timestamps are not altered unless explicitly selected. Use a separate project vault to avoid connecting unrelated cases.

Preserving topology and length intentionally reveals structural information. The generated addresses/domains may name real endpoints because reserved documentation ranges cannot satisfy every original length and prefix constraint. They are labels for offline analysis: never use them as live network targets. The program never contacts them. To preserve an additional relationship, encode and review it explicitly rather than assuming it was inferred.

Length, uniqueness and a previously fixed prefix can conflict. **R003** blocks the conversion; it does not relax forensic accuracy. A new project vault allows the related group to be regenerated together. Custom edits are validated against the same rules. Generated names prefer fictional people, places and businesses of the required length. Other alphabetic values use English words or complete-word compounds where possible; numeric identifiers retain their required shape. Domain endings are chosen from a bundled offline list of valid suffixes, with the same length and consistent suffix relationships. If no valid combination exists, R003 requests a custom correction rather than silently changing the constraints. The curated suffix list was verified against [IANA](https://data.iana.org/TLD/tlds-alpha-by-domain.txt); the application never fetches it or contacts generated domains. No implementation can guarantee unlimited distinct replacements for a finite short field.

## Vault filtering and mass actions

Click any vault header for ascending/descending sorting. Right-click a header for sorting, individual value filters and clipboard actions. Use Shift/Ctrl-click for multiple rows or Ctrl+A to select the visible set. Clear filters is right-aligned. Sorting uses stable mapping IDs for edits and deletion, so a row's position is never its identity.

Double-click one selected row to edit it; double-click with multiple rows selected, or choose Edit selected values from the context menu, to apply an exact case-sensitive find/replace to replacement, original or type. For example, replace `.com` with `.net` for all selected related fields. The entire proposal is validated before saving; changing only part of a domain group is refused. Expand the confirmation details to inspect every old/new value. Replacement edits retain old aliases; original edits alter the target of historical restoration. Cancel makes no changes. Batch operations are atomic with respect to the encrypted vault save.

**Delete selected** and **Flush all** require typed confirmation. **Obfuscate selected in input** and **Restore selected in input** apply only the selected saved mappings to the current workspace input, preserving other text. They prompt before running and produce a reviewable output. They do not silently delete mappings or modify source files.

## Analyst database exchange and hash verification

Use **Account & security → Export password-protected database**. Choose the exported database name and destination folder, then ZIP, compressed TAR, 7z (also called zip7), or RAR. Enter and repeat a required export passphrase of at least 12 characters. This password replaces the local database password for the exported copy only. The original local database keeps its current account password. The destination may be outside the portable folder. Exchange contents include current mappings, aliases and detailed audit history, encrypted with AES-GCM and a fresh scrypt-derived key, salt and nonce.

Every archive contains exactly three members: `database.redactor` (encrypted), `SHA256SUMS`, and `SHA512SUMS`. The checksum files use conventional hex-digest/two-space/filename lines. SHA-256 and SHA-512 are standardized SHA-2 algorithms; this does not assert FIPS certification of the application or runtime. TAR uses gzip compression and is automatically recognized on import. 7z uses the bundled Python archive implementation. RAR creation requires a compatible licensed `tools/rar/rar.exe` (Windows) or `tools/rar/rar` (macOS/RHEL); the proprietary encoder is not supplied. An unavailable RAR choice explains this and recommends a built-in format. Archives are compressed after encrypting, so size reduction will be small.

Import verifies both hashes before decrypting. It rejects extra members, path traversal, oversized contents and corrupted hashes. Checksums detect corruption; they are not signatures and do not prove who supplied the file. AES-GCM validates the encrypted content using the password. Communicate that password through a separate channel.

While signed in, choose **Open exported database**. Supply the export password and a title. The current user owns access to the new database tab; no new analyst account is created. Each database has its own encrypted file in a database-specific folder with a hashed user subfolder. Its authorization key is protected by the active user’s account password. Changing that password atomically updates the protection of all authorized database keys. Original exporter identity is retained in imported history; new activity identifies the current user. Close the application to lock all databases.

Switch tabs to review independent workspaces. **Copy selected rows** / **Paste rows** in a vault header or cell context menu (Ctrl+C/Ctrl+V in the vault table) transfer selected mappings with a sensitive-clipboard confirmation. Input fields support normal text copy/paste. Pasted mappings are validated and previewed before saving.

**Merge…** opens a tree of other databases. Check a database to select all its mappings, or expand it to check individual entries. You may select multiple databases. The current tab is the destination. Conflicting originals prompt Keep current or Use incoming (retain old alias); an incompatible prefix, suffix, duplicate token or length blocks the whole proposal. Expand the final details to review incoming and resulting mappings. Cancel makes no changes. Source databases are unchanged. Mapping provenance and conflict choices are recorded in the destination audit; prior source audit histories remain available in their source tabs. A merge does not establish that two similarly named people or systems are the same real-world entity.

Create a local account before opening a password-protected database export. Accounts never need to be shared with another analyst.


## Detailed audit and retirement

Audit records include UTC timestamps with offset, the authenticated local username, operation, mapping IDs, before/after mapping snapshots, and exact touched input/output text for transformations. Text-change offsets use Unicode character indices. Import events record the extracted text and source filename. Errors record stable categories and recommended actions; diagnostic files exclude raw exception text, usernames and document values. Right-click an audit header to sort or filter; double-click any audit row to inspect the correct event, including after sorting.

The detailed audit, including imported audit history, is encrypted inside each database and protected by the active account password. Changing that password updates access to all local database audit records. Exporting it as JSON exposes sensitive originals and requires confirmation. Hash-linked events support detecting accidental chain edits; a person with the vault password can rewrite the vault, so this is not an externally trusted or certified forensic chain of custody. Passwords are not recorded.

After final restoration, reporting and required audit/retention work, remove completed-project mappings to reduce correlations from repeated substitutes. **Detailed history may still contain the deleted originals.** Purge history separately when retention rules allow, or retire and remove the complete closed project vault and its backups. Deletion is logical removal, not certified media erasure. Do not destroy the only mappings needed by outstanding obfuscated work. Editing substitutes retains aliases and is not a substitute for data retirement.

## Command-line reference

Windows: `Redactor-cli.exe`. macOS/RHEL: `./Redactor-cli`. From source: `.venv/bin/python -m redactor.cli` (Windows: `.venv/Scripts/python.exe`). Commands prompt for passwords without echo. Never put passwords in arguments, scripts or terminal history. Close the GUI before using CLI; both use the same exclusive lock. Every CLI session closes its vault on exit, providing the equivalent of lock/logout.

Global `--user NAME` and optional `--database ID` precede the command. The default database is `main`; obtain other IDs with `databases`. `--help` and `COMMAND --help` describe arguments. Successful commands return 0, failures return 2 with an error code and recommended action. Standard output can contain sensitive values; do not redirect it outside the portable folder. JSON plans and audit exports are plaintext sensitive files and must remain protected in the folder.

```text
Redactor-cli --user Analyst create
Redactor-cli --user Analyst info
Redactor-cli --user Analyst password
Redactor-cli --user Analyst reminder on
Redactor-cli --user Analyst import evidence.docx exports/editable.txt
Redactor-cli --user Analyst scan exports/editable.txt exports/review.json
Redactor-cli --user Analyst review exports/review.json --kind Email --state sensitive
Redactor-cli --user Analyst review exports/review.json --original ZQC --replacement XYZ
Redactor-cli --user Analyst review exports/review.json --original ZQC --set-kind "Case label"
Redactor-cli --user Analyst review exports/review.json --original ZQC --state insensitive --starts 42
Redactor-cli --user Analyst review exports/review.json --add --original ABC --kind Custom --replacement DEF
Redactor-cli --user Analyst near exports/review.json "tavi quill" "Tavi Quill" confirm
Redactor-cli --user Analyst near exports/review.json "Tavi Qulil" "Tavi Quill" edit --value "Tavi Quill"
Redactor-cli --user Analyst near exports/review.json "Tavi Qulil" "Tavi Quill" deny
Redactor-cli --user Analyst redact exports/review.json exports/obfuscated.docx
Redactor-cli --user Analyst restore exports/returned.txt exports/report.docx
Redactor-cli --user Analyst lookup --kind Email --sort replacement --descending
Redactor-cli --user Analyst batch-update --kind Email --find .com --replace .net
Redactor-cli --user Analyst batch-update --kind Email --find .com --replace .net --apply
Redactor-cli --user Analyst obfuscate exports/input.txt exports/subset.txt --kind Email
Redactor-cli --user Analyst restore exports/subset.txt exports/restored.txt --ids MAPPING_ID
Redactor-cli --user Analyst delete --ids MAPPING_ID --confirm DELETE
Redactor-cli --user Analyst flush --confirm FLUSH
Redactor-cli --user Analyst audit --output exports/audit.json
Redactor-cli --user Analyst purge-history --confirm PURGE
Redactor-cli --user Analyst export-db exports/analyst.zip
Redactor-cli --user Analyst import-db exports/analyst.zip --title "Second investigation"
Redactor-cli --user Analyst databases
Redactor-cli --user Analyst new-db "New case"
Redactor-cli --user Analyst --database DATABASE_ID lookup
Redactor-cli --user Analyst --database DATABASE_ID merge SOURCE_ID OTHER_ID --conflict keep
Redactor-cli --user Analyst --database DATABASE_ID merge SOURCE_ID OTHER_ID --conflict keep --apply
Redactor-cli --user Analyst copy-mappings exports/rows.json --kind Email
Redactor-cli --user Analyst --database DATABASE_ID paste-mappings exports/rows.json --apply
Redactor-cli --user Analyst workspace --input exports/editable.txt
Redactor-cli help-doc errors
```

Review plans contain editable candidate objects with `original`, `kind`, `replacement`, `selected`, and optional `included_starts` arrays. Offsets are zero-based Unicode positions in the plan's text; changing the text invalidates your positional review, so scan again. A `near` confirmation or edit rescans the revised text, resetting candidate review. Use `deny` to leave text unchanged. You may directly edit plan JSON in a local editor, but redact validates it before use. No review-attestation checkbox or flag is required. The optional `--reviewed` CLI flag remains accepted for script compatibility and does not alter behavior. Inspect the full source and output before sharing.

Use `batch-update` without `--apply` to review exact proposed changes first. Select IDs or type for subset operations; omission means all current mappings except that delete requires an explicit selector. Export formats are selected by output suffix and use the same adapters as the GUI.

## RHEL man page

From the portable folder run `man ./redactor.1`; from source run `man ./redactor/resources/redactor.1`. No installation into `/usr/share/man` is required. The man page contains the CLI synopsis, commands, storage, archive formats and error references. Full guidance is also available offline with `Redactor-cli help-doc cli`.

## Editable terminal workspace

`Redactor-cli --user Analyst workspace` opens a full-screen terminal UI with INPUT, WORK PRODUCT and SUGGESTED SUBSTITUTIONS panels. Tab/Shift-Tab moves focus; the terminal mouse can move the cursor. Edit the lower table as tab-separated columns: Use (yes/no), Type, Original, Replacement, and optional comma-separated occurrence offsets. Use F4 to add a manual value, or add a row directly. Ctrl-T inserts a tab separator in the table; Tab moves focus. Use F3 to import, F4 to add a manual value, F5 to scan, F6 to apply the current substitutions, F7 to restore, F2 to export to the filename field, F1 for error guidance, and Ctrl-Q to exit and lock. Editing source or substitutions invalidates the prior output. The terminal's own copy/paste shortcuts remain available (often Ctrl-Shift-C/V); exact keys depend on the host terminal.

Lookup defaults to a readable column table; `lookup --json` retains machine-readable results. Terminal workspace panels adapt to the available terminal size; increase the terminal window for more columns. It is a text interface rather than a graphical window manager. Full-screen terminal support is required; redirected/noninteractive jobs should use the individual commands. No password is saved in review plans.

## Database audit attribution

Every new event names its database ID and title. Cross-database merges record each source database as read and the destination as modified, along with selected incoming values, conflict decisions and exact before/after mappings. Copy/paste carries source database provenance. Changing the account password lists every authorized database whose unlock-key protection was updated. Imported history retains its original attribution.


## Creator-only local database access

Each local database belongs to the analyst who created its local copy and is encrypted using only that analyst’s current account password. A different local user’s password cannot unlock it. Database ownership is checked before opening or saving an account. Changing the creator’s password updates protection of their local database keys; it does not change any exported archive.

An imported exchange becomes a new local database owned by the importing analyst. Its at-rest protection changes to that analyst’s account password after import. The export password is used only to decrypt the exchange; the original creator’s account password is never required or shared. Original creator identity remains in provenance and imported audit history. The CLI databases command lists each local creator.

Before publishing source or binary packages, purge all saved databases and database exchange archives from the release workspace. Account containers also contain mappings and audit history; deleting them removes those records and requires creating a new account at the next launch. This is separate from normal case retirement and should only be done when explicitly authorized. Never commit databases, passwords, exports or investigation work to Git. Deleting files does not guarantee forensic erasure from backups, snapshots or storage media.


## Database-specific folders and hashed user folders

Local storage uses this layout; database identifiers and user hashes are opaque hexadecimal values, not database titles or usernames:

```text
data/databases/
  <database-id>/
    <sha256-user-hash>/
      database.vault
```

The hash is SHA-256 of the normalized, case-insensitive local username. A hash avoids plaintext names in folder paths; it is not a guarantee that a guessable username cannot be inferred. Different analysts can have separately encrypted copies under the same database identifier, each in their own user-hash folder. Importing the same database again into one account creates a separate copy instead of overwriting its existing tab.

Each imported database uses a fresh random encryption key. The active user’s main database holds the encrypted authorization keys for that user’s database list. Their account password protects those keys; the export password is not stored or reused as the local database password. Changing the account password updates that protection atomically.

Move the entire portable folder, or preserve the complete data/databases tree for local recovery. Do not rename, move or transfer individual internal database.vault files: the main database contains authorization keys needed to open the other files. Use Export password-protected database to create a standalone handoff copy, with your chosen password, name and destination. After import, that copy belongs to the active user and is protected through that user’s account password.

## Clipboard edits and repository security

Right-click a vault cell to copy or paste that individual value, or right-click its column header to copy/paste that column for selected rows. One pasted line applies to all selected rows; multiple lines must match the selected row count. Original, replacement and Type are editable; aliases and creation time are read-only. Pasted edits validate the whole mapping set and display exact changes before saving. Copying rows preserves database provenance for merging. Delete selected rows is available in the context menu with its existing confirmation.

Databases, user accounts, audit logs, exports and backups must never be synced to an online repository. Git ignore rules cover the standard storage folders, encrypted vault files and audit exports. These rules do not protect renamed, moved or force-added copies. The uploading user is responsible for all security issues resulting from mishandling sensitive data. The Account & Security page displays this notice prominently. Plaintext audit exports are explicit, confirmed copies; they are not the encrypted at-rest audit store. Avoid uploading them or redirecting sensitive CLI output into tracked files.

Buttons show brief function descriptions on hover. Sign-in defaults to unlocking an existing account; select Create a new local account only when creating one. Merge is the rightmost database action. Use the pane borders for resizing rather than a separate expand control.

# Redactor 0.2 User Guide supplement: portable analysis and command line

This supplement replaces earlier instructions about installed locations, backups, network surrogates and summary-only audit records.

## Portable folder and launch

On Windows, open **Redactor.exe** in the root folder. **Redactor-cli.exe** is the console alternative. Keep `_internal`, `tools`, `data` and the executable together. No installation or account registration is needed. Move or copy the entire folder while all Redactor sessions are closed. The current project checkout uses the same layout, with the latest executable directly in its root. A Git source checkout alone is not a compiled application: download the native portable binary package or build it.

On macOS, keep Redactor.app and its sibling data/tools folders together in one writable folder; application data is outside the signed .app bundle but inside the portable folder. On RHEL, run `./Redactor` or `./Redactor-cli` from the extracted folder. Native builds are platform/architecture specific. A Windows executable cannot run on macOS or RHEL. Linux still requires compatible OS desktop libraries and drivers; a native build is not a replacement for the operating system. macOS and RHEL native validation must be completed on those systems before calling their binaries verified.

The program creates `data/vaults`, `data/logs`, `data/tmp` and `exports` beneath its portable root. Export destinations must remain within that root, including resolved symlink targets. Import can read a local file from another folder without changing it. There is no automatic download, telemetry, update check, remote authentication, or network lookup. Build/dependency acquisition and Git publishing are separate developer operations that use the network. Using a network-mounted folder causes operating-system filesystem traffic: use a local disk or removable drive for a physically offline workflow. The application itself does not initiate network communication. Its license URL is displayed for copying, not automatically opened.

Older installed vaults are not discovered through a hidden fallback. Import an old encrypted `.vault` using its old password, or move the closed application's vaults into `data/vaults`. Do not overwrite an existing analyst account. Preserve your only copy until the imported data has been verified.

## Import and review

Imports with no sensitive matches are successful. The text stays editable and an informational notice invites manual selection or editing. A readable but empty document opens an empty workspace for manual entry. Unsupported, unreadable or oversized files still receive actionable errors. If detection cannot make a valid forensic replacement, the imported text remains available for review; no misleading output is produced.

Each suggestion occurrence has a row. Highlight rows using Shift/Ctrl (Command on macOS where applicable), then use the Sensitive/Insensitive buttons. **Scope** defaults to asking whether to affect all same values or only selected occurrences. Choose an explicit scope in the dropdown to avoid repeated prompts. Excluded occurrences remain in the output unchanged. Merely highlighting rows is not redaction approval.

Use the type dropdown or right-click a column header to filter values. Filters are combined across columns. Clear filters to see all rows again. Drag column dividers horizontally and pane splitters vertically; **Expand review** gives the suggested substitutions more height. Resize the sidebar to gain table width. Hidden values are not automatically made insensitive; review their existing inclusion states before export.

## Forensic relationships and length

New generated replacements have the same number of Unicode characters as their originals. This is character count, not UTF-8 byte count, glyph width, font metrics or Excel cell display width. Document export remains content-only; matching lengths do not recreate the source document's formatting, graphics, formulas or slide layout.

Email domains and hostname suffixes are mapped consistently. If `alice@abc.gov`, `bob@abc.gov`, `server.abc.gov` and `abc.gov` appear, the substituted domain is shared across all of them. Separate original suffixes cannot collapse into the same substitute. Dot-separated label structure is preserved. Domain relationships are literal DNS suffix relationships; the program does not infer registrable domains from a downloaded suffix list, resolve DNS, or infer that an email local part identifies a separately named person.

For IPv4 and IPv6, the program preserves address equality, IP version and pairwise common binary prefix lengths. Thus membership relationships for every prefix length within the processed addresses are retained. IPv4 octet character widths and IPv6 textual group/compression shape are preserved. Address ordering, numeric distances, geolocation, ownership, routability and associations absent from the input are **not inferred or guaranteed**. Port numbers and timestamps are not altered unless explicitly selected. Use a separate project vault to avoid connecting unrelated cases.

Preserving topology and length intentionally reveals structural information. The generated addresses/domains may name real endpoints because reserved documentation ranges cannot satisfy every original length and prefix constraint. They are labels for offline analysis: never use them as live network targets. The program never contacts them. To preserve an additional relationship, encode and review it explicitly rather than assuming it was inferred.

Length, uniqueness and a previously fixed prefix can conflict. **R003** blocks the conversion; it does not relax forensic accuracy. A new project vault allows the related group to be regenerated together. Custom edits are validated against the same rules. Old 0.1 replacements can still restore exactly, but they must be regenerated before use in a new strict-length conversion. Whimsical names are chosen where a suitable same-length choice exists; other values use format-shaped fictional strings. No implementation can guarantee unlimited distinct replacements for a finite short field.

## Vault filtering and mass actions

Click any vault header for ascending/descending sorting. Right-click a header for individual value filters, or select a type from the dropdown. **Select visible rows** selects the filtered set. Individual selection remains available. Sorting uses stable mapping IDs for edits and deletion, so a row's position is never its identity.

**Batch update** accepts an exact case-sensitive find/replace on replacement, original or type. For example, replace `.com` with `.net` for all selected related fields. The entire proposal is validated before saving; changing only part of a domain group is refused. Expand the confirmation details to inspect every old/new value. Replacement edits retain old aliases; original edits alter the target of historical restoration. Cancel makes no changes. Batch operations are atomic with respect to the encrypted vault save.

**Delete selected** and **Flush all** require typed confirmation. **Obfuscate selected in input** and **Restore selected in input** apply only the selected saved mappings to the current workspace input, preserving other text. They prompt before running and produce a reviewable output. They do not silently delete mappings or modify source files.

## Analyst database exchange and hash verification

Use **Account & security → Export password-protected database**. Choose ZIP, compressed TAR, 7z (also called zip7), or RAR. Enter and repeat a separate export passphrase of at least 12 characters. This passphrase does not change your account password. Exchange contents include current mappings, aliases and detailed audit history, encrypted with AES-GCM and a fresh scrypt-derived key, salt and nonce.

Every archive contains exactly three members: `database.redactor` (encrypted), `SHA256SUMS`, and `SHA512SUMS`. The checksum files use conventional hex-digest/two-space/filename lines. SHA-256 and SHA-512 are standardized SHA-2 algorithms; this does not assert FIPS certification of the application or runtime. TAR uses gzip compression and is automatically recognized on import. 7z uses the bundled Python archive implementation. RAR creation requires a compatible licensed `tools/rar/rar.exe` (Windows) or `tools/rar/rar` (macOS/RHEL); the proprietary encoder is not supplied. An unavailable RAR choice explains this and recommends a built-in format. Archives are compressed after encrypting, so size reduction will be small.

Import verifies both hashes before decrypting. It rejects extra members, path traversal, oversized contents and corrupted hashes. Checksums detect corruption; they are not signatures and do not prove who supplied the file. AES-GCM validates the encrypted content using the password. Communicate that password through a separate channel.

While signed in, choose **Open exported database**. Supply the export password and a title. The current user owns access to the new database tab; no new analyst account is created. Every database is stored inside the same encrypted account container and protected at rest by the current local account password. Changing that password re-encrypts all of its databases. Original exporter identity is retained in imported history; new activity identifies the current user. Close the application to lock all databases.

Switch tabs to review independent workspaces. **Copy rows** / **Paste rows** (Ctrl+C/Ctrl+V in the vault table) transfer selected mappings with a sensitive-clipboard confirmation. Input fields support normal text copy/paste. Pasted mappings are validated and previewed before saving.

**Merge…** opens a tree of other databases. Check a database to select all its mappings, or expand it to check individual entries. You may select multiple databases. The current tab is the destination. Conflicting originals prompt Keep current or Use incoming (retain old alias); an incompatible prefix, suffix, duplicate token or length blocks the whole proposal. Expand the final details to review incoming and resulting mappings. Cancel makes no changes. Source databases are unchanged. Mapping provenance and conflict choices are recorded in the destination audit; prior source audit histories remain available in their source tabs. A merge does not establish that two similarly named people or systems are the same real-world entity.

Raw legacy encrypted `.vault` and `.redactor` files can be opened in the same way using their old password; they lack the archive checksum files. New users first create their local account, then open the export. Existing accounts never need to be shared with another analyst.


## Detailed audit and retirement

Audit records include UTC timestamps with offset, the authenticated local username, operation, mapping IDs, before/after mapping snapshots, and exact touched input/output text for transformations. Text-change offsets use Unicode character indices. Import events record the extracted text and source filename. Errors record stable categories and recommended actions; diagnostic files exclude raw exception text, usernames and document values. Double-click an audit row to inspect its full JSON.

The detailed audit is encrypted inside the vault. Exporting it as JSON exposes sensitive originals and requires confirmation. Hash-linked events support detecting accidental chain edits; a person with the vault password can rewrite the vault, so this is not an externally trusted or certified forensic chain of custody. Passwords are not recorded. History predating version 0.2 may lack exact changes and usernames; missing facts cannot be reconstructed.

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
Redactor-cli --user Analyst review exports/review.json --original IBM --replacement XYZ
Redactor-cli --user Analyst review exports/review.json --original IBM --state insensitive --starts 42
Redactor-cli --user Analyst review exports/review.json --add --original ABC --kind Custom --replacement DEF
Redactor-cli --user Analyst near exports/review.json "jane smith" "Jane Smith" confirm
Redactor-cli --user Analyst near exports/review.json "Jane Smiht" "Jane Smith" edit --value "Jane Smith"
Redactor-cli --user Analyst near exports/review.json "Jane Smiht" "Jane Smith" deny
Redactor-cli --user Analyst redact exports/review.json exports/obfuscated.docx --reviewed
Redactor-cli --user Analyst restore exports/returned.txt exports/report.docx --reviewed
Redactor-cli --user Analyst lookup --kind Email --sort replacement --descending
Redactor-cli --user Analyst batch-update --kind Email --find .com --replace .net
Redactor-cli --user Analyst batch-update --kind Email --find .com --replace .net --apply
Redactor-cli --user Analyst obfuscate exports/input.txt exports/subset.txt --kind Email --reviewed
Redactor-cli --user Analyst restore exports/subset.txt exports/restored.txt --ids MAPPING_ID --reviewed
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

Review plans contain editable candidate objects with `original`, `kind`, `replacement`, `selected`, and optional `included_starts` arrays. Offsets are zero-based Unicode positions in the plan's text; changing the text invalidates your positional review, so scan again. A `near` confirmation or edit rescans the revised text, resetting candidate review. Use `deny` to leave text unchanged. You may directly edit plan JSON in a local editor, but redact validates it before use. `--reviewed` records your deliberate review acknowledgment; it is not an automatic guarantee of safe output.

Use `batch-update` without `--apply` to review exact proposed changes first. Select IDs or type for subset operations; omission means all current mappings except that delete requires an explicit selector. Export formats are selected by output suffix and use the same adapters as the GUI.

## RHEL man page

From the portable folder run `man ./redactor.1`; from source run `man ./redactor/resources/redactor.1`. No installation into `/usr/share/man` is required. The man page contains the CLI synopsis, commands, storage, archive formats and error references. Full guidance is also available offline with `Redactor-cli help-doc cli`.

## Editable terminal workspace

`Redactor-cli --user Analyst workspace` opens a full-screen terminal UI with INPUT, WORK PRODUCT and SUGGESTED SUBSTITUTIONS panels. Tab/Shift-Tab moves focus; the terminal mouse can move the cursor. Edit the lower table as tab-separated columns: Use (yes/no), Type, Original, Replacement, and optional comma-separated occurrence offsets. Use F4 to add a manual value, or add a row directly. Ctrl-T inserts a tab separator in the table; Tab moves focus. Use F3 to import, F4 to add a manual value, F5 to scan, F6 to apply after confirming review, F7 to restore, F2 to export to the filename field, F1 for error guidance, and Ctrl-Q to exit and lock. Editing source or substitutions invalidates the prior output. The terminal's own copy/paste shortcuts remain available (often Ctrl-Shift-C/V); exact keys depend on the host terminal.

Lookup defaults to a readable column table; `lookup --json` retains machine-readable results. Terminal workspace panels adapt to the available terminal size; increase the terminal window for more columns. It is a text interface rather than a graphical window manager. Full-screen terminal support is required; redirected/noninteractive jobs should use the individual commands. No password is saved in review plans.

## Database audit attribution

Every new event names its database ID and title. Cross-database merges record each source database as read and the destination as modified, along with selected incoming values, conflict decisions and exact before/after mappings. Copy/paste carries source database provenance. Changing the account password lists every contained database as re-encrypted. Older imported history retains its original attribution and may lack fields introduced in this version.

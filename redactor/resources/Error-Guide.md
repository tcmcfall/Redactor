# Redactor Error Guide and recovery procedures

This guide covers the application's defined error families, import/export limits and fallback handling for unexpected failures. Operating systems and third-party document libraries can produce additional messages; no finite document can enumerate every possible external failure. Those receive R999 or the closest category, retain the diagnostic reference, and recommend a next step.

## First response

1. Read the error code, the exact message and Recommended action. Expand Details for the help reference.
2. Keep source evidence intact. Do not delete a vault to fix a conversion error.
3. Check which database tab and which rows are active. Clear filters to expose hidden conflicting rows.
4. Correct the selection, value or storage problem and retry. A failed conversion does not publish output.
5. If needed, reproduce using a synthetic example and report the code/action/version. Never send sensitive evidence, passwords, vaults or detailed audit exports with a public bug report.

The desktop popup has an Open Error Guide button. CLI errors print the code and recommended action and return 2. F1 opens guidance in the terminal workspace. Sanitized diagnostics are stored in data/logs/errors.jsonl with UTC time, category and recommended action. Detailed operational changes are encrypted inside the account database. If storage itself is unavailable, a diagnostic cannot be guaranteed to reach disk; the visible error remains available.

## Overlapping sensitive data: concrete repair

Two different situations used to receive similar messages:

- **Selected span overlaps an excluded span.** Example: `IBM Corp` is selected but the `IBM` inside it is excluded. Replacing the larger phrase would violate your explicit exclusion. The new error names both values and character locations. Find those rows, then either include both (the longest selected phrase is applied once), or exclude the larger phrase and include only the smaller value you actually want replaced. The scope dropdown controls whether the edit affects this occurrence or all identical values.
- **Replacement collides with an original or another replacement.** The new message identifies the replacement, its original and the conflicting sensitive value. Inspect Conversion vault as well as the current suggestion list. Edit the replacement or generate a fresh suggestion. An incidental fragment inside a word is no longer treated as a complete sensitive-value overlap. Consistent nested domain replacements are permitted and validated as a group.

Redundant automatic heuristic suggestions entirely contained in a longer value should be reviewed together; selecting both is valid and uses the longer value. Automatically selecting two values is not by itself an error. Do not deselect values randomly until output succeeds: that can leave originals visible.

## No matches is not an error

A supported import with no sensitive matches stays open and editable. Add manual selections or edit the source text. An empty but readable import permits manual entry. Failure to read a corrupt/unsupported file is a different condition and still reports an error.

## R001 — Unlock or password problem

**Recommended action:** Check account spelling, password and keyboard layout. Import an intact encrypted backup if needed. Passwords cannot be recovered.

## R002 — Ambiguous substitutions

**Recommended action:** Review overlapping rows together. Use distinct replacements, or restore already-obfuscated input before scanning again.

## R003 — Forensic constraint conflict

**Recommended action:** Review the named length/domain/IP constraint. Regenerate a complete related group in a fresh project vault, or correct the custom substitute. Do not use misleading output.

## R004 — Unsupported or damaged document

**Recommended action:** Use a supported modern format. Save a local UTF-8 text copy or re-export the source document and retry.

## R005 — Document size or processing limit

**Recommended action:** Split the document into smaller files or pages; reduce oversized images. Retry each part.

## R006 — Portable OCR unavailable

**Recommended action:** Use a native portable package containing tools/tesseract and English tessdata. Check the executable and language files; retry a clearer image.

## R007 — Storage or permissions problem

**Recommended action:** Check free space, folder write permissions and media connection. Close other Redactor processes. Keep your existing vault intact and retry.

## R008 — Portable output location required

**Recommended action:** Choose a file within the Redactor folder. Move the entire folder when transferring work to another device.

## R009 — Exchange file rejected

**Recommended action:** Check the export password and file integrity. Open the export as another database tab under your existing account; export again from the source if necessary.

## R010 — Input or selection needs review

**Recommended action:** Check the selected rows, nonempty values and requested action. Review the full error detail and correct the input.

## R011 — Database archive or checksum problem

**Recommended action:** Choose ZIP, TAR or 7z; RAR needs a licensed native tool inside tools/rar. For checksum mismatch, obtain a fresh intact export. SHA-256/SHA-512 detect corruption; AES-GCM authenticates the encrypted contents.

## R012 — Database merge conflict

**Recommended action:** Review conflicting original/replacement pairs. Keep the destination or choose incoming explicitly. Resolve domain/IP/length conflicts as a complete group. Preview again before applying.

## R999 — Unexpected failure

**Recommended action:** Keep the original files. Retry once with a synthetic sample; consult the diagnostic event and Error Guide. Report the error code and app version without sensitive material.

## Limits and format-specific recovery

- Input file: 50 MB; extracted text: one million characters; PDF: 500 pages; image: 100 frames. Split larger evidence into traceable parts.
- Office archive expansion: 150 MB and 20,000 members. Re-export or simplify an oversized document; do not disable the limit on untrusted files.
- Exchange archive/encrypted vault: 100 MB. Detailed audit text can grow quickly; export/retire completed projects under your retention policy before approaching this limit.
- Unsupported legacy Office files: convert DOC/XLS/PPT locally to DOCX/XLSX/PPTX. Password-protected/macro-enabled source containers are not supported by these adapters.
- Text decoding: save UTF-8 or UTF-16 locally. OCR: use a clearer scan and check the bundled English tessdata. Mixed-content PDF images and embedded Office pictures may not be OCRed automatically; review visual evidence separately.
- Spreadsheet cell/sheet overflow: export TXT/CSV or divide the data. Multi-page image output: choose TIFF/PDF, not a single-page format.
- Same length means Unicode characters, not font width. A document layout mismatch requires local formatting review; it is not repaired by relaxing the length check.
- Unknown/altered returned substitute: lookup the original mapping, compare the source and correct the returned token explicitly. Restoration never fuzzy-guesses a replacement.
- RAR unavailable: use ZIP/TAR/7z or place a licensed native RAR encoder inside tools/rar. Do not rename a ZIP file to .rar.
- Import password rejected: use the export password, not the current local account password. The local account must already be unlocked. A legacy raw backup uses the password active when it was saved.
- Merge conflict: select fewer rows or choose a conflict policy after reviewing both versions. A proposed .com to .net change must cover every related suffix. Separate source databases remain intact if the destination validation fails.

## Locked files, permissions and interruption

Only one Redactor process can use an account folder at a time. Close GUI before CLI and vice versa. After a crash, ensure there is no remaining Redactor process before investigating a stale lock; never remove a live lock. Work from a writable, connected local folder. Ensure the full portable package was copied, including _internal and tools. Restore a known intact backup only after preserving the damaged file for diagnosis. A failed atomic vault replace preserves the previous on-disk vault. An export error can occur after a successful mapping save; keep that database and retry export instead of generating inconsistent replacements.

## Encryption, audit and checksum boundaries

The closed account container includes every logical database and is AES-GCM encrypted. A local username/password is required to open it. Exported databases use the separately chosen export password. SHA-256/SHA-512 verify the encrypted file bytes; a changed checksum file is not a trusted signature. Authentication failure is never bypassed. Lost passwords have no recovery service.

Exact audit records contain sensitive originals. Deleting mappings does not erase their historical snapshots. After required restoration and retention work, separately purge history or retire the complete project container and backups. Neither filesystem deletion nor flushing guarantees forensic secure erasure of a storage device. Hash-linked local audit is not an independently certified chain of custody.

## Defined message inventory

The following inventory is generated from application raise statements. Variable portions may contain the exact value/location that caused the error, shown only in the local interface. The referenced family supplies the recovery procedure.

- **R001**: Passwords do not match.
- **R001**: Passwords do not match.
- **R005**: R005: Clipboard mapping limit exceeded.
- **R010**: The sensitive value must appear exactly in the current input.
- **R001**: New passwords do not match.
- **R005**: R005: Review plan too large.
- **R010**: R010: Plan belongs to another account.
- **R010**: R010: Plan belongs to another database.
- **R001**: Passwords do not match.
- **R001**: R001: Supply --user before the command.
- **R010**: R010: Select IDs or type; use flush for all mappings.
- **R010**: R010: Unknown database ID.
- **R005**: R005: Mapping file too large.
- **R012**: R012: Source and destination databases must differ.
- **R012**: R012: Unknown source database ID.
- **R010**: R010: Manual value must exist in input.
- **R010**: R010: Edit requires --value.
- **R010**: R010: Database title must be 1–100 characters.
- **R012**: R012: Merge conflict for {value}: {value} versus {value}. Choose keep or incoming after review.
- **R999**: No unambiguous replacement available. Use a custom replacement.
- **R999**: Each exact original must have one mapping.
- **R002**: R002: Selected {value} at character {value} overlaps excluded {value} at character {value}. In Suggested substitutions, either mark both sensitive (the longest value wins), or mark the larger value insensitive and select only the part you intend to replace. Use All same values only if that scope is intended.
- **R010**: A sensitive value cannot be empty.
- **R002**: A suggested replacement already appears in the input. Generate another replacement.
- **R010**: Replacements must be nonempty single lines up to 300 characters, without outer spaces.
- **R002**: R002: Replacement {value} for {value} overlaps sensitive value {value}. Edit that replacement or generate another suggestion. The conflicting rows may be in the saved vault as well as the current input.
- **R002**: The input contains an existing replacement. Use Restore first to avoid ambiguous or double substitutions.
- **R002**: Replacements overlap or are duplicated. Choose distinct values for exact restoration.
- **R005**: R005: Database archive exceeds 100 MB.
- **R011**: R011: Database checksum mismatch. Obtain an intact export; do not import this file.
- **R011**: R011: Invalid archive members or size.
- **R011**: R011: Invalid TAR members or size.
- **R011**: R011: Unsupported database archive.
- **R011**: R011: Choose .zip, .tar, .rar or .7z (.zip7).
- **R011**: R011: Invalid 7z members or size.
- **R011**: R011: Place a native RAR utility in tools/rar or ask for ZIP export.
- **R011**: R011: RAR creation requires a licensed native rar utility in tools/rar. Choose ZIP, TAR or 7z instead.
- **R011**: R011: Portable RAR utility failed. Check its platform and license or choose ZIP.
- **R011**: R011: Invalid RAR members or size.
- **R003**: R003: No distinct same-length substitute fits the reviewed group. Correct the selection or start a fresh project vault.
- **R003**: R003: Domain label count must stay unchanged.
- **R003**: R003: Replacement character length differs from original. Generate a same-length substitute.
- **R003**: R003: Existing IP mappings have incompatible prefixes.
- **R003**: R003: IPv6 length conflicts with saved prefix relationships.
- **R003**: R003: Email must retain its local part and domain structure.
- **R003**: R003: No same-length IP fits existing prefix relationships. Start a new related group in a fresh vault.
- **R003**: R003: Shared domain suffixes have inconsistent substitutes. Update all related values together.
- **R003**: R003: Distinct original domains cannot collapse into the same substitute.
- **R003**: R003: Replacement must be a valid IP of the same version.
- **R003**: R003: IP common-prefix relationships changed. Regenerate the related group in a fresh vault.
- **R003**: R003: IPv6 compression conflicts with saved prefix relationships.
- **R006**: Image/scanned-page import needs local Tesseract OCR. See Help → User Guide for your platform's setup instructions. No data was uploaded.
- **R006**: Local OCR failed. Check Tesseract and its English language data.
- **R004**: Unsupported format. Convert legacy .doc/.xls/.ppt files to .docx/.xlsx/.pptx in Office first.
- **R005**: Import limit is 50 MB per file. Split the document first.
- **R005**: Extracted text exceeds one million characters. Split the document first.
- **R004**: Choose one of the supported export formats.
- **R005**: This document expands beyond the 150 MB safety limit.
- **R005**: PDF limit is 500 pages. Split the document first.
- **R005**: PDF page is too large to rasterize safely. Resize it before importing.
- **R005**: Worksheet exceeds the import limit.
- **R005**: Text exceeds Excel's cell or sheet limits. Export as TXT instead.
- **R004**: Save the text file as UTF-8 or UTF-16 before importing.
- **R005**: Image limit is 100 frames.
- **R004**: Text needs multiple image pages. Export as TIFF or PDF to retain all content.
- **R005**: Image export limit is 100 pages. Export as PDF or TXT instead.
- **R010**: R010: Invalid field.
- **R010**: R010: Enter nonempty text to find.
- **R008**: R008: Choose an output inside the portable Redactor folder. Move the entire folder to move its data.
- **R010**: R010: Each substitution row needs five tab-separated columns; Use must be yes or no.
- **R010**: R010: Generate a reviewed result first; edits invalidate old output.
- **R001**: Use a password or passphrase with at least 12 characters.
- **R001**: Password must be 1,024 characters or fewer.
- **R001**: Enter a username between 1 and 80 characters.
- **R001**: This username already has a vault. Sign in instead.
- **R009**: R009: An export cannot overwrite the active vault.
- **R001**: Current password is incorrect.
- **R001**: Choose a different password.
- **R005**: Vault exceeds the supported size.
- **R999**: Unsupported vault version.
- **R999**: Account mismatch.
- **R001**: Unable to unlock. Check the username and password, or restore an intact vault backup.
- **R005**: File too large
- **R999**: Unsupported version
- **R002**: Duplicate IDs
- **R999**: Invalid audit
- **R009**: R009: Cannot import exchange or backup. Check its password, integrity and format.

## Creator ownership mismatch (R001)

A local database cannot be moved into another account by copying its decrypted internal records. Sign in as its creator, export it with a separate password, then import that exchange while signed in as the receiving analyst. The imported local copy belongs to that analyst. Never share the creator’s account password.

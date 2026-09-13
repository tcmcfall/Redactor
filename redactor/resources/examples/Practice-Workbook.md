# Redactor practice workbook

All scenarios are invented. Public company names illustrate detection only. SSN-shaped values use invalid ranges and payment strings are training/checksum examples, never real payment details. None of the files represents a real person, incident, client or government record.

Create a separate local account named **Training** with your own password before these exercises. Generated substitutes are intentionally random, so expected results are described by behavior rather than a fixed fictional name.

Open samples from **Help → Practice examples**. The same files are included in the application resources and source package.

## Exercise A — Corporate investigation

All people and organizations in these exercises are invented training labels.

Load `01-corporate-investigation.txt`. Scan and check that Tavi Quill, Orin Bramble, Zephyr Quill Company, ZQC, MossQuill, QZRA, hostnames and 10.24.8.12 have suggestions. Nimbus Lantern Corporation should be suggested by the organization-suffix heuristic; review all business rows for accuracy.

Manually mark `Project Paper Lantern` and `CASE-DEMO-2048`. Reject any headings incorrectly flagged as names or business abbreviations. Generate output and verify that both occurrences of 10.24.8.12 share a replacement. All occurrences of Tavi Quill must share a replacement as well.

In Conversion vault, search `Tavi Quill`, then search her generated replacement. Both searches should locate the same pair. Clear the filter and inspect the remaining mappings.

## Exercise B — Government-style narrative

Load `02-government-style-report.txt`. Verify the fictional agency, its abbreviation, both people, the hostname and both address types. Mark the program name, file number and room/location manually. Decide whether the date should be protected in your exercise.

Generate an obfuscated summary request. Review the prose as a whole: a unique role, date or location can be sensitive even if no simple detector flags it. This exercise does not represent a classified or official document.

## Exercise C — Personal record and numeric validation

Load `03-personal-records.txt`. Expected suggestions include the email, invalid SSN-shaped examples, nine-digit identifier and two checksum-valid card sequences. The invalid card sequence should not be suggested as a Credit card; mark it yourself if you want all payment-like strings protected.

Manually mark the fictional address, account code and free text if your reporting context treats them as sensitive. This demonstrates why “not detected” does not mean “not sensitive.”

Generate output. SSN/card replacements must contain letters and must not be plausible usable numbers. Restore the work and verify exact spaces and hyphens return to each original sequence.

## Exercise D — Technical JSON and custom values

Import `04-technical-configuration.json`. Check IPv4, IPv6, loopback, qualified and hyphenated hostnames, email, person and business suggestions. Mark `localhost`, `DEMO-SECRET-NOT-A-REAL-CREDENTIAL` and `Project Glass Comet` manually.

Redactor reads JSON as literal text. It does not execute it or guarantee schema validation after arbitrary custom replacements. Use ordinary quote-free suggestions if you want the output to remain syntactically valid JSON. Export as TXT and compare the text before renaming or importing it into another tool.

## Exercise E — Unicode, boundaries and overlaps

Load `05-unicode-and-overlaps.txt`. Mark non-English names, lowercase `tavi quill`, the project name and the two-line project text manually where needed. A replacement must be a single line even when the sensitive original spans multiple lines.

After generation and restoration, compare the whole text with the source. The leading emoji must not shift the highlighted name. Tavi Quill must not replace the start of Tavi Quillson. Selecting ZQC must not change ZQCx. Exact capitalization is preserved through separate mappings. For this exercise, use TXT export to avoid image-font rendering differences.

## Exercise F — False positives and contextual review

Load `06-false-positives-and-context.txt`. Expect some headings and uppercase words to appear as possible names or abbreviations. Uncheck them when appropriate. The invalid IP and checksum-invalid card should not pass their respective validation rules. The nine-digit order identifier may be suggested as an SSN-shaped value even though the narrative labels it an order ID.

Manually mark the invented project name. Discuss what the uniquely identifying narrative would reveal in a real situation and whether broader rewriting would be needed before external sharing. Redactor substitutes selected literal text; it does not assess all contextual disclosure risks.

## Exercise G — Complete restoration without an online tool

1. Use one of the preceding examples to generate a reviewed work product.
2. Copy it into a local text editor.
3. Add `Review completed. Additional investigation is recommended.` without changing any substitute.
4. Paste that text into Redactor's Restore input, acknowledge sensitive output and restore.
5. Compare the result with the original. Every unchanged substitute should return to its exact original. Your added sentence should remain.
6. Export a local TXT report. To practice different formats, also export DOCX, PDF or XLSX from the same generated result and inspect the content-only behavior.

No internet access is needed for this exercise.

## Exercise H — An AI changed a substitute

Take a generated person replacement from Exercise G. In the local editor, deliberately remove its unique suffix or change its capitalization. Restore again.

Expected result: the altered occurrence remains unchanged. Redactor may flag a remaining ID-shaped marker if one is still present; removing the ID may eliminate that clue. It must not guess a person. Find the exact original replacement through Conversion vault, correct the simulated returned text after verifying the intended pair, and restore again.

## Exercise I — Change a replacement and keep old work

Save an obfuscated text example locally. In Conversion vault, edit one replacement to a new, distinct value while leaving its original unchanged. Confirm that the old replacement appears in Older aliases.

Restore the previously saved text. The old alias must still restore correctly. Then process fresh original text and check that the current replacement is used. Editing the original instead changes all aliases' restoration target and should be treated as a different, consequential action.

## Exercise J — Backup, deletion and password change

Use only the Training account:

1. Export some obfuscated work and create an encrypted vault backup.
2. Delete one selected mapping by typing DELETE. The corresponding substitute should now remain unresolved during restoration.
3. Close the app and recover the training vault using the User Guide's backup procedure. Restoration should work again.
4. Change the account password. Check that the active vault opens with the new password and not the old one.
5. Remember that the earlier backup still requires its old password.
6. If desired, flush the Training account's mappings by typing FLUSH. Confirm that the data is no longer available in its lookup view.

Do not perform destructive training exercises in an account containing work you need.

## Record your observations

For each sample, record which candidates were correct, which were false positives, which values required manual marking, how many occurrences changed, whether a text round trip matched exactly, and any export-format differences. There is no fixed substitute answer key because each vault generates its own unique fictional values.

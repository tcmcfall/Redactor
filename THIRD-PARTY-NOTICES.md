# Third-party components

Redactor includes or uses the following independently licensed components. Preserve their distributed license files. This inventory is not a substitute for those licenses.

| Component | License family / distribution note |
| --- | --- |
| Python | Python Software Foundation |
| PySide6 / Qt / Shiboken | LGPL/GPL/commercial options; inspect the exact modules distributed |
| cryptography | Apache-2.0 or BSD-3-Clause |
| pypdfium2 / PDFium | Apache-2.0 / BSD-3-Clause; preserve the included PDFium third-party notices |
| python-docx, python-pptx, openpyxl | MIT |
| Pillow | HPND-style |
| odfpy | Apache/GPL/LGPL options; retain upstream license |
| striprtf | BSD-3-Clause |
| Tesseract (portable tools/tesseract) | Apache-2.0; bundled dependencies have their own licenses |
| prompt_toolkit / wcwidth | BSD-style / MIT |
| py7zr and archive helpers | LGPL/BSD/MIT as distributed; preserve their notices |
| rarfile | ISC; RAR encoder is not included |
| OCR libiconv / JBIG-KIT | LGPL / GPL; corresponding source archives accompany the Windows release |
| PyInstaller bootloader | GPL with distribution exception |

Redactor's own application source is licensed GPL-3.0-or-later. See `LICENSE` for the full terms and `SOURCE-DISTRIBUTION.md` for the source-package process. PyMuPDF is not used or bundled. Third-party dependencies retain their own licenses; the Redactor GPL notice does not relicense them.

For binary redistribution, retain all dependency notices and satisfy the source/relinking requirements of the particular Qt/PySide libraries you convey. Native builds use dynamic Qt libraries, not an intentionally locked-down static build. Upstream Qt and PySide source archives for the exact installed version are listed in the generated dependency source manifest. A link alone is not a substitute for conveying corresponding source where a dependency's license requires it; release distributors must accompany their binaries with the required source materials or another permitted source-delivery mechanism.

Fictional character and company names are illustrative pseudonyms. Their presence does not imply affiliation or endorsement by their creators or rights holders.

The Windows portable OCR runtime is Tesseract v5.4.0.20240606 with Leptonica 1.84.1. Only the executable and dependent DLLs are staged; system uninstallers and training utilities are omitted. The native source bundle includes the vendor Tesseract tag, matching libiconv 1.17 and JBIG-KIT 2.1 sources, Leptonica sources, and historical MSYS2 build recipes. The GPL exception for GCC runtime libraries and the licenses of image/compression libraries remain applicable. See the packaged native source manifest and preserved upstream notices.

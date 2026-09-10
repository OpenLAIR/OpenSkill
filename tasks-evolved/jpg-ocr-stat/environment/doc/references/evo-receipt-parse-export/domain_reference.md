# Domain Reference for evo-receipt-parse-export

**Responsibility**: Date extraction with multiple format support and ISO formatting, total amount extraction using prioritized keyword matching with exclusion rules and fallback logic, Excel file creation with openpyxl including proper sheet naming and null handling

**Key functions to implement**: extract_date, extract_total_amount, parse_receipt_text, write_results_to_excel

---

## 4. openpyxl API for Writing Excel Files


Storing the extracted structured data into `.xlsx` formats requires precise interactions with `openpyxl` 3.1.5. A recurring pitfall in Python-to-Excel pipelines is Excel's aggressive auto-conversion of text into generic numbers or dates, leading to warnings like "Numbers stored as text" [cite: 16, 17].

## 5. Date Extraction Patterns from OCR Text


Optical Character Recognition regularly hallucinates characters based on visual similarity. When extracting dates, OCR engines frequently substitute the digit `0` with the uppercase letter `O` or `D`, and the digit `1` with lowercase `l`, uppercase `I`, or pipe `|` [cite: 21, 22].

## 6. Total Amount Extraction from OCR Text


Monetary amounts suffer from decimal point hallucinations (read as commas or dropped entirely) and currency symbol artifacts. Expressions like `$ 1,234.56` or `RM47.70` are ubiquitous [cite: 21, 24].

## 7. Line-by-Line Text Processing Patterns


A monolithic regex search over the entire OCR string can yield false positives. A deterministic approach involves partitioning the OCR output by newline characters `\n` and iterating sequentially [cite: 25, 27]. This facilitates spatial context awareness.

## 8. Common Pitfalls and Mitigation Strategies


When architecting OCR pipelines, developers routinely encounter silent failures and encoding bottlenecks [cite: 29]. The following mitigations address these exact friction points.

1.  **Pytesseract Garbage Characters:** Tesseract frequently returns excessive whitespace, page breaks (`\x0c`), or arbitrary ASCII artifacts. Mitigation requires `text.strip().replace('\x0c', '')` and utilizing `re.sub(r'[^\x20-\x7E]', '', text)` to strip non-printable characters [cite: 29].
2.  **Pillow Image Mode Issues (RGBA vs RGB vs L):** Tesseract expects RGB or Grayscale (L). Passing an RGBA (Alpha channel) image from a `.png` file can corrupt the binarization algorithms [cite: 2, 30]. Always enforce `image.convert('RGB')` or `image.convert('L')` before passing to `image_to_string` [cite: 2].
3.  **Silent Failures and Empty Strings:** If `pytesseract` returns an empty string, the issue is universally tied to either PSM configuration (using single-line mode on a full page) or image resolution. If `img.size` is too small, upscale it [cite: 6, 9].
4.  **`os.listdir()` Arbitrary Sorting:** `os.listdir()` relies on the OS file system layout and does not return files alphanumerically [cite: 31]. Iterating over un-sorted files breaks chronological processing. Always wrap it: `sorted(os.listdir(path))`.
5.  **Low OCR Confidence on Thermal Paper:** Thermal receipts fade. Applying Pillow's `ImageEnhance.Contrast` is mandatory. Additionally, checking confidence via `pytesseract.image_to_data()` allows you to programmatically discard gibberish below a 60% confidence threshold.
6.  **Encoding Issues in Openpyxl:** Passing UTF-8 decoded strings into Openpyxl can sometimes trigger `UnicodeDecodeError` if not handled correctly [cite: 29]. Python 3 natively handles unicode, but ensuring the script runs in a UTF-8 environment on Ubuntu 24.04 avoids OS-level locale discrepancies.
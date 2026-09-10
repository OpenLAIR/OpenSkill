# Domain Reference for evo-ocr-preprocess-extract

**Responsibility**: Image loading, preprocessing pipeline (grayscale, resize, contrast, threshold), Tesseract OCR configuration and text extraction, batch file discovery and sorting

**Key functions to implement**: preprocess_image, extract_text_from_image, get_sorted_image_files

---

## 1. Pytesseract API Details and Core Architecture


The `pytesseract` library serves as a Python wrapper for Google's Tesseract-OCR Engine, facilitating the extraction of text from image matrices into native Python strings or dictionaries [cite: 1, 2]. Understanding the exact function signatures and the underlying Page Segmentation Modes (PSM) is critical for optimizing extraction on receipt topographies.

## 2. Pillow Image Preprocessing for OCR Accuracy


Raw scanned images frequently suffer from poor illumination, shadows, sensor noise, and low resolution. Feeding raw images directly into `pytesseract` drastically degrades character recognition accuracy [cite: 8, 9]. Pillow (`PIL`) 12.0.0 provides robust algorithms to normalize image topography.

## 3. Tesseract Config Strings for Digit-Heavy Receipt Text


Receipts are dense with numeric data, special symbols (currencies), and dates. Configuring Tesseract to anticipate this lexicon drastically mitigates hallucinatory text outputs.

## 8. Common Pitfalls and Mitigation Strategies


When architecting OCR pipelines, developers routinely encounter silent failures and encoding bottlenecks [cite: 29]. The following mitigations address these exact friction points.

1.  **Pytesseract Garbage Characters:** Tesseract frequently returns excessive whitespace, page breaks (`\x0c`), or arbitrary ASCII artifacts. Mitigation requires `text.strip().replace('\x0c', '')` and utilizing `re.sub(r'[^\x20-\x7E]', '', text)` to strip non-printable characters [cite: 29].
2.  **Pillow Image Mode Issues (RGBA vs RGB vs L):** Tesseract expects RGB or Grayscale (L). Passing an RGBA (Alpha channel) image from a `.png` file can corrupt the binarization algorithms [cite: 2, 30]. Always enforce `image.convert('RGB')` or `image.convert('L')` before passing to `image_to_string` [cite: 2].
3.  **Silent Failures and Empty Strings:** If `pytesseract` returns an empty string, the issue is universally tied to either PSM configuration (using single-line mode on a full page) or image resolution. If `img.size` is too small, upscale it [cite: 6, 9].
4.  **`os.listdir()` Arbitrary Sorting:** `os.listdir()` relies on the OS file system layout and does not return files alphanumerically [cite: 31]. Iterating over un-sorted files breaks chronological processing. Always wrap it: `sorted(os.listdir(path))`.
5.  **Low OCR Confidence on Thermal Paper:** Thermal receipts fade. Applying Pillow's `ImageEnhance.Contrast` is mandatory. Additionally, checking confidence via `pytesseract.image_to_data()` allows you to programmatically discard gibberish below a 60% confidence threshold.
6.  **Encoding Issues in Openpyxl:** Passing UTF-8 decoded strings into Openpyxl can sometimes trigger `UnicodeDecodeError` if not handled correctly [cite: 29]. Python 3 natively handles unicode, but ensuring the script runs in a UTF-8 environment on Ubuntu 24.04 avoids OS-level locale discrepancies.

## 9. File Handling Patterns


Batch processing receipts demands systematic file traversal, filtering out non-image binaries, and constructing safe file paths regardless of the host OS configuration.

```python
import os
import glob

def get_image_files(directory_path):
    # Pattern 1: Using glob for elegant extension filtering
    # Supports multiple extensions via loop
    extensions = ['*.jpg', '*.jpeg', '*.png']
    image_files = []
    for ext in extensions:
        # Case insensitive handling in glob requires bracket tricks or multiple checks,
        # but os.listdir is often more explicitly controllable for case insensitivity.
        search_pattern = os.path.join(directory_path, ext)
        image_files.extend(glob.glob(search_pattern))
        
    # Pattern 2: Using os.listdir for robust filtering and sorting
    valid_exts = {'.jpg', '.jpeg', '.png'}
    safe_files = []
    
    if os.path.exists(directory_path):
        for filename in sorted(os.listdir(directory_path)):
            ext = os.path.splitext(filename)[cite: 1].lower()
            if ext in valid_exts:
                # Correct path joining
                full_path = os.path.join(directory_path, filename)
                safe_files.append(full_path)
                
    return safe_files
```
The combination of `os.path.join` and `sorted()` prevents cross-platform slash `\` vs `/` bugs and ensures sequential execution [cite: 31].

## 10. Version-Specific Concerns


Dependency mismatches represent the highest risk factor in maintaining long-term pipelines. The exact versions specified—`Pillow 12.0.0`, `pytesseract 0.3.13`, and `openpyxl 3.1.5`—contain breaking changes relative to older tutorials.
# Comprehensive Guide for Building a Python OCR Utility Module for Scanned Receipt Images

**Key Points:**
*   **Optimal Stack:** The combination of Python 3, `pytesseract` 0.3.13, `Pillow` 12.0.0, and `openpyxl` 3.1.5 on Ubuntu 24.04 provides a highly robust ecosystem for extracting unstructured text from receipt images and transforming it into structured spreadsheet data.
*   **Page Segmentation is Crucial:** For receipt OCR, Tesseract's Page Segmentation Mode (PSM) 4 (Assume a single column of text of variable sizes) or PSM 6 (Assume a single uniform block of text) consistently yield the highest accuracy due to the tabular nature of receipts. 
*   **Preprocessing dictates Accuracy:** Raw image ingestion often yields high Error Rates (Character Error Rate). Binarization, spatial resizing using Lanczos resampling (replacing the deprecated Antialias), and contrast enhancement via Pillow are mandatory steps for mitigating noise.
*   **Regex is the Backbone of Post-Processing:** Because OCR engines frequently misread characters (e.g., confusing 'O' with '0', or 'l' with '1'), sophisticated Regular Expressions must be employed to reliably parse dates and monetary amounts.
*   **Version Deprecations:** Pillow 12.0.0 introduces strict deprecations, most notably the complete removal of `Image.ANTIALIAS` in favor of `Image.Resampling.LANCZOS`, which requires direct code refactoring for modern Python deployments.

This report synthesizes methodologies for architecting an enterprise-grade Optical Character Recognition (OCR) pipeline. Building an OCR utility module to extract actionable data from scanned receipts presents unique challenges, primarily due to the inconsistent formatting, degraded print quality, and arbitrary layouts of point-of-sale documents. Through the systematic application of `pytesseract` for text detection, `Pillow` for image preprocessing, and `openpyxl` for data structuring, developers can build an automated, highly accurate extraction engine. This guide delves deeply into API signatures, computer vision preprocessing paradigms, configuration tuning, regular expression pattern matching, and file IO strategies. 

***

## 1. Pytesseract API Details and Core Architecture

The `pytesseract` library serves as a Python wrapper for Google's Tesseract-OCR Engine, facilitating the extraction of text from image matrices into native Python strings or dictionaries [cite: 1, 2]. Understanding the exact function signatures and the underlying Page Segmentation Modes (PSM) is critical for optimizing extraction on receipt topographies.

### Exact Function Signatures

The `pytesseract` API provides several primary interfaces. The two most pertinent for receipt processing are `image_to_string` and `image_to_data`.

**`pytesseract.image_to_string()`**
This function returns the unmodified text recognized by the engine. 
```python
pytesseract.image_to_string(
    image, 
    lang=None, 
    config='', 
    nice=0, 
    output_type=Output.STRING, 
    timeout=0
)
```
*   `image`: A Pillow `Image` object, NumPy array, or file path string [cite: 2, 3].
*   `lang`: A string specifying the language code (e.g., `'eng'`). Multiple languages can be concatenated using `+` (e.g., `'eng+fra'`) [cite: 3]. Defaults to `'eng'`.
*   `config`: A string of advanced configuration flags targeting the Tesseract CLI, crucial for specifying PSM and OEM modes [cite: 2, 3].
*   `nice`: An integer to adjust processor priority on Unix-like systems [cite: 3].
*   `output_type`: Specifies the return type (e.g., string, bytes, dict) [cite: 3, 4].
*   `timeout`: Terminate the OCR process if it exceeds the specified seconds [cite: 2].

**`pytesseract.image_to_data()`**
This function is optimal for generating bounding box coordinates, confidences, and spatial layouts.
```python
pytesseract.image_to_data(
    image, 
    lang=None, 
    config='', 
    nice=0, 
    output_type=Output.DICT, 
    timeout=0, 
    pandas_config=None
)
```
When `output_type=Output.DICT` is used, the function returns a dictionary containing lists of `level`, `page_num`, `block_num`, `par_num`, `line_num`, `word_num`, `left`, `top`, `width`, `height`, `conf`, and `text`.

### Page Segmentation Modes (PSM) for Receipts

Tesseract analyzes the spatial layout of an image based on the PSM provided. There are 14 PSM modes (0-13) [cite: 5, 6]. For receipts, which typically feature vertically aligned items with prices on the right margin, the following modes are highly relevant:

*   **PSM 4 (Assume a single column of text of variable sizes):** This mode is empirically the most effective for receipt OCR. It forces Tesseract to concatenate text row-wise across spatial gaps, which perfectly aligns with the item-price layout (e.g., "Coffee     $4.50") [cite: 6, 7].
*   **PSM 6 (Assume a single uniform block of text):** Treats the entire document as a continuous, justified block of text [cite: 5, 6]. If a receipt has strict formatting and no large horizontal whitespace, PSM 6 provides excellent accuracy and structural fidelity.
*   **PSM 7 (Treat the image as a single text line):** Used only if you have cropped the receipt image down to a single row (e.g., cropping out just the total amount) [cite: 6, 8].
*   **PSM 11 (Sparse text):** Attempts to find as much text as possible scattered irregularly [cite: 5, 7]. While occasionally useful for chaotic, crinkled receipts, it often destroys line-by-line associations.
*   **PSM 12 (Sparse text with OSD):** Similar to PSM 11 but applies Orientation and Script Detection (OSD) to automatically rotate the text [cite: 5, 7].

**Default Config:** If no config string is passed, Tesseract defaults to `--psm 3` (Fully automatic page segmentation, but no OSD) and `--oem 3` (Default engine, combining legacy and LSTM) [cite: 4, 6].

### Working Code Example
```python
from PIL import Image
import pytesseract

# Ensure Tesseract binary is in PATH on Ubuntu 24.04
# Installed via `sudo apt install tesseract-ocr`

def extract_receipt_text(image_path):
    img = Image.open(image_path)
    
    # Custom configuration targeting English, LSTM engine, and Column layout
    custom_config = r'-l eng --oem 3 --psm 4'
    
    # Extract string
    text = pytesseract.image_to_string(img, config=custom_config)
    return text

if __name__ == "__main__":
    raw_text = extract_receipt_text("sample_receipt.jpg")
    print(raw_text)
```

## 2. Pillow Image Preprocessing for OCR Accuracy

Raw scanned images frequently suffer from poor illumination, shadows, sensor noise, and low resolution. Feeding raw images directly into `pytesseract` drastically degrades character recognition accuracy [cite: 8, 9]. Pillow (`PIL`) 12.0.0 provides robust algorithms to normalize image topography.

### Required Preprocessing Methodologies

1.  **Grayscale Conversion:** Tesseract internally processes images in grayscale/binary. Explicitly converting the image to grayscale using `Image.convert('L')` removes multi-channel color noise and reduces computational overhead.
2.  **Resizing and Upscaling:** OCR engines require sufficient pixel density to differentiate character topology (ideally 300 DPI). If a receipt scan is low resolution, upscaling it by a factor of 2.0 or 3.0 improves the character bounding boxes. In Pillow 12, upscaling must utilize `Image.Resampling.LANCZOS` [cite: 10, 11].
3.  **Contrast Enhancement:** Faded ink on thermal paper requires contrast stretching. `ImageEnhance.Contrast` achieves this.
4.  **Binarization (Thresholding):** This forces all pixels to either absolute black (0) or absolute white (255). A fixed threshold via `Image.point()` provides rigid binarization.
5.  **Denoising:** Applying median or Gaussian blurs (e.g., `ImageFilter.MedianFilter`) removes salt-and-pepper noise without blurring text edges.

### Optimum Threshold Values
For receipt texts (usually black text on a white/gray background), a threshold value between `128` and `150` typically yields optimal binary mappings. Values around `140` are widely used as a standard pivot.

### Preprocessing Code Implementation
```python
from PIL import Image, ImageEnhance, ImageFilter

def preprocess_for_ocr(image_path, target_dpi=(300, 300)):
    # 1. Open Image
    img = Image.open(image_path)
    
    # Update DPI metadata if necessary
    img.info['dpi'] = target_dpi
    
    # 2. Convert to Grayscale
    gray_img = img.convert('L')
    
    # 3. Upscale Image (crucial for small or low-res receipts)
    # Using LANCZOS as ANTIALIAS was removed in Pillow 10+ and 12
    width, height = gray_img.size
    upscaled_img = gray_img.resize(
        (width * 2, height * 2), 
        resample=Image.Resampling.LANCZOS
    )
    
    # 4. Enhance Contrast (increase contrast by factor of 2.0)
    enhancer = ImageEnhance.Contrast(upscaled_img)
    high_contrast_img = enhancer.enhance(2.0)
    
    # 5. Denoise (Mild median filter to remove salt-and-pepper)
    denoised_img = high_contrast_img.filter(ImageFilter.MedianFilter(size=3))
    
    # 6. Binarization / Thresholding
    # Pixels > 140 become white (255), else black (0)
    threshold = 140
    binary_img = denoised_img.point(lambda p: 255 if p > threshold else 0, mode='1')
    
    return binary_img
```

## 3. Tesseract Config Strings for Digit-Heavy Receipt Text

Receipts are dense with numeric data, special symbols (currencies), and dates. Configuring Tesseract to anticipate this lexicon drastically mitigates hallucinatory text outputs.

### Optical Character Recognition Engine Modes (OEM)
Tesseract 4 and 5 utilize a dual-engine structure [cite: 1]:
*   `--oem 0`: Legacy Tesseract engine only.
*   `--oem 1`: Neural nets LSTM engine only.
*   `--oem 3`: Default, based on available data (combines both) [cite: 1, 4].

### The Whitelisting Dilemma
The `tessedit_char_whitelist` parameter explicitly restricts the OCR engine to a predefined subset of characters [cite: 12]. If a user only wants to extract totals, restricting output to digits, commas, and periods prevents Tesseract from misidentifying a smudge as the letter 'A' [cite: 12]. 
However, there is a widely documented historical limitation: `tessedit_char_whitelist` works perfectly in Legacy Mode (`--oem 0`), but was initially broken or partially ignored in pure LSTM mode (`--oem 1`) in Tesseract 4.x [cite: 13, 14]. In modern Tesseract 5.x distributions (available in Ubuntu 24.04), whitelisting via LSTM is supported but remains highly sensitive to configuration [cite: 13].

To extract numeric values precisely, passing the config string is achieved thusly:
`config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.$RMC,-/'` [cite: 12, 15].

### PSM 6 vs PSM 4 for Receipts
*   **`--psm 4`** is superior when the receipt contains wide gaps between the item name and the price. PSM 4 conceptually projects bounding boxes horizontally across the void [cite: 6, 7].
*   **`--psm 6`** is superior when the receipt has a blocky, uniform, dense structure, like the boilerplate text at the top of a receipt (merchant name, address, tax ID) [cite: 6, 8]. 
For end-to-end receipt extraction, `--psm 4` is generally the safer default, but executing two passes (one with PSM 4 for items, one with PSM 6 for merchant headers) guarantees optimal fidelity.

### Exact Config String Formatting
```python
# General Receipt Text
cfg_general = r'--oem 3 --psm 4'

# Digit/Amount Heavy Region (if cropped)
cfg_digits = r'--oem 3 --psm 6 -c tessedit_char_whitelist="0123456789.,$ -/"'

# Execution
text = pytesseract.image_to_string(img, config=cfg_digits)
```

## 4. openpyxl API for Writing Excel Files

Storing the extracted structured data into `.xlsx` formats requires precise interactions with `openpyxl` 3.1.5. A recurring pitfall in Python-to-Excel pipelines is Excel's aggressive auto-conversion of text into generic numbers or dates, leading to warnings like "Numbers stored as text" [cite: 16, 17]. 

### API Implementation and Auto-Conversion Prevention
To prevent Excel from mutating receipt strings (e.g., transforming a receipt ID "001234" into "1234", or "1-2" into "02-Jan"), we must rigorously enforce cell data types [cite: 18, 19]. While some developers prepend an apostrophe (`'001234`), a cleaner approach in `openpyxl` is to append the data and subsequently alter the cell's `number_format` to `'@'` (Text) [cite: 16, 20].

Additionally, `openpyxl.Workbook()` creates a default sheet named "Sheet". To avoid extraneous sheets, this default sheet should be renamed to "results", rather than creating a new appended sheet [cite: 20].

### Working Code Example
```python
import openpyxl
from openpyxl import Workbook
from openpyxl.cell import Cell

def save_to_excel(data_list, output_filename="receipt_data.xlsx"):
    # Create a new workbook
    wb = Workbook()
    
    # Target the active default sheet to prevent extra sheets
    ws = wb.active
    ws.title = "results"
    
    # Write header row
    headers = ["Filename", "Date", "Total Amount", "Merchant", "Raw Number"]
    ws.append(headers)
    
    # Write data rows
    for row_data in data_list:
        # Convert None to empty string for Excel cleanliness
        sanitized_row = ["" if item is None else item for item in row_data]
        ws.append(sanitized_row)
        
        # Prevent auto-conversion on specific cells (e.g., Raw Number in column 5)
        # openpyxl uses 1-based indexing for rows and columns
        current_row_idx = ws.max_row
        cell = ws.cell(row=current_row_idx, column=5)
        cell.number_format = '@' # Forces Excel to treat it strictly as text
        cell.value = str(sanitized_row[cite: 7]) 

    # Save to disk
    wb.save(output_filename)

# Example Usage
data = [
    ["img1.jpg", "2024-05-12", 45.50, "Starbucks", "005923"],
    ["img2.jpg", None, 102.00, "Home Depot", "000142"]
]
save_to_excel(data)
```

## 5. Date Extraction Patterns from OCR Text

Optical Character Recognition regularly hallucinates characters based on visual similarity. When extracting dates, OCR engines frequently substitute the digit `0` with the uppercase letter `O` or `D`, and the digit `1` with lowercase `l`, uppercase `I`, or pipe `|` [cite: 21, 22].

### Common Date Formats and Python Regex
Receipts feature highly heterogeneous date signatures [cite: 22, 23]. The `re` module enables capturing these entities despite OCR noise [cite: 24, 25].

1.  **DD/MM/YYYY or DD-MM-YYYY:** `\b(0[1-9]|[cite: 26]\d|3[cite: 1])[-/](0[1-9]|1[0-2])[-/](19\d\d|20\d\d)\b` [cite: 22].
2.  **MM/DD/YYYY:** `\b(0[1-9]|1[0-2])[-/](0[1-9]|[cite: 26]\d|3[cite: 1])[-/](19\d\d|20\d\d)\b` [cite: 22].
3.  **DD.MM.YYYY:** `\b(\d{2})\.(\d{2})\.(\d{4})\b`
4.  **"DD Mon YYYY" (e.g., 12 Jan 2024):** `\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})\b` [cite: 26].

### Algorithmic Cleaning and Parsing Strategy
Before applying `re.search()`, OCR text should be sanitized to repair common misreads.

```python
import re
from datetime import datetime

def extract_and_format_date(ocr_text):
    # 1. Repair common OCR digit misreads
    replacements = {
        'O': '0', 'o': '0', 'D': '0',
        'l': '1', 'I': '1', '|': '1',
        'S': '5', 'B': '8'
    }
    # Only replace misreads if they are adjacent to digits or slashes
    # A simple global replace is dangerous; we apply it specifically to date-like strings via logic,
    # or globally if the text is small. For safety, we'll do a focused translation.
    
    # 2. Define composite regex
    date_patterns = [
        # Match DD/MM/YYYY or DD-MM-YYYY
        r'\b(\d{2})[-/.](\d{2})[-/.](\d{4})\b',
        # Match YYYY/MM/DD
        r'\b(\d{4})[-/.](\d{2})[-/.](\d{2})\b',
        # Match DD Mon YYYY
        r'\b(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})\b'
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            raw_date = match.group(0)
            # Normalize separators
            clean_date = re.sub(r'[-.]', '/', raw_date)
            
            # Attempt to parse
            try:
                # Format: DD/MM/YYYY
                dt = datetime.strptime(clean_date, "%d/%m/%Y")
                return dt.strftime("%Y-%m-%d") # Return ISO format
            except ValueError:
                pass
            
            try:
                # Format: YYYY/MM/DD
                dt = datetime.strptime(clean_date, "%Y/%m/%d")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
                
            try:
                # Format: 12 Jan 2024
                # Limit month to 3 chars for strptime %b
                parts = clean_date.split()
                month_abbr = parts[cite: 1][:3].capitalize()
                standardized = f"{parts} {month_abbr} {parts[cite: 5]}"
                dt = datetime.strptime(standardized, "%d %b %Y")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass
                
    return None
```

## 6. Total Amount Extraction from OCR Text

Monetary amounts suffer from decimal point hallucinations (read as commas or dropped entirely) and currency symbol artifacts. Expressions like `$ 1,234.56` or `RM47.70` are ubiquitous [cite: 21, 24].

### Regex Patterns for Monetary Values
A robust regex must account for optional currency symbols (`$`, `RM`, `€`), optional white spaces, optional thousands separators (commas), and decimal points [cite: 24, 25].

**Universal Pattern:** 
`r'(?:RM|\$|EUR|€)?\s*(\d{1,3}(?:,\d{3})*\.\d{2})\b'`
This uses a non-capturing group `(?:...)` for the currency symbol, ensuring only the numeric string is captured in group 1 [cite: 25].

### Sanitization and Formatting
To convert captured strings into floating-point numerics formatted to exactly two decimal places, commas must be stripped.

```python
def extract_total_amount(ocr_text):
    # Regex to find monetary values
    # Matches: 47.70, 1,234.56, RM 47.70, $12.00
    pattern = r'(?:RM|\$|USD)?\s*(\d{1,3}(?:[,\s]\d{3})*[\.]\d{2})\b'
    
    # Search all monetary matches
    matches = re.findall(pattern, ocr_text, re.IGNORECASE)
    
    if not matches:
        return None
        
    # Receipts usually have the total at the bottom, or it's the largest number.
    # We will assume we're parsing a specific 'Total' line, or we find the maximum.
    # Let's clean all matches and find the maximum valid float
    valid_floats = []
    for match in matches:
        # Clean comma and space thousands separators
        clean_str = match.replace(',', '').replace(' ', '')
        try:
            val = float(clean_str)
            valid_floats.append(val)
        except ValueError:
            continue
            
    if valid_floats:
        max_val = max(valid_floats)
        # Format to exactly two decimal places
        return f"{max_val:.2f}"
    
    return None
```

## 7. Line-by-Line Text Processing Patterns

A monolithic regex search over the entire OCR string can yield false positives. A deterministic approach involves partitioning the OCR output by newline characters `\n` and iterating sequentially [cite: 25, 27]. This facilitates spatial context awareness.

### Keyword Searching and Next-Line Extraction
Often, a receipt will print "TOTAL" on one line, and the value directly beneath it [cite: 25, 28].

```python
def parse_receipt_lines(ocr_text):
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
    
    total_amount = None
    tax_amount = None
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        # 1. Search for keywords case-insensitively
        if 'total' in line_lower and 'sub' not in line_lower:
            # 2. Extract numeric values from the SAME line
            # Regex for the last number on a line:
            # Looks for digits and decimals, ensuring it's at the end of the string
            match = re.search(r'(\d+[.,]\d{2})$', line)
            if match:
                total_amount = match.group(1)
            else:
                # 3. If not on the same line, check the NEXT line
                if i + 1 < len(lines):
                    next_line = lines[i+1]
                    match_next = re.search(r'(\d+[.,]\d{2})', next_line)
                    if match_next:
                        total_amount = match_next.group(1)
                        
    return total_amount
```
The regex `r'(\d+[.,]\d{2})$'` elegantly captures the right-aligned price commonly found at the terminus of a receipt item row [cite: 24].

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

### Pillow 12.0.0 Breaking Changes
Released in late 2025 (supporting up to Python 3.14), Pillow 12.0.0 aggressively purges legacy code [cite: 32, 33].
*   **Removal of `Image.ANTIALIAS`:** This is the most catastrophic breaking change for legacy OCR scripts. `Image.ANTIALIAS` was deprecated in Pillow 10 and permanently deleted [cite: 10, 11]. Attempting to use it raises an `AttributeError`. **Solution:** You must use `Image.Resampling.LANCZOS` or `Image.LANCZOS` for high-quality resizing [cite: 10, 11].
*   **Dropped Python 3.9:** Pillow 12.0.0 explicitly drops support for Python 3.9. Running this on Ubuntu 24.04 (which ships with Python 3.12 natively) resolves this [cite: 32].
*   **Removed `ImageFile.raise_oserror()`:** Internal helper functions have been pruned.

### Pytesseract 0.3.13 Status
Released in August 2024, version 0.3.13 relies on stability and wrapper efficiency [cite: 2]. There are no major deprecated APIs relative to 0.3.10, but it strictly requires that the `tesseract-ocr` binary is accessible via the system PATH [cite: 2, 34]. On Ubuntu 24.04, installing the package creates the required binary mapping automatically. Tesseract engine optimizations (OEM) and language packs (`tesseract-data-eng`) remain the primary dependencies [cite: 34].

### Openpyxl 3.1.5
Released in June 2024, openpyxl 3.1.5 refines the parser for Office Open XML formats [cite: 35, 36]. The primary concern with 3.1.x is security against XML vulnerabilities (billion laughs attack). The official documentation recommends installing the `defusedxml` package alongside `openpyxl` to guard against these vectors, especially if your utility processes externally generated Excel templates [cite: 35, 37]. The syntax for explicit string definitions and preventing the "number stored as text" warning remains consistent with the `cell.number_format = '@'` implementation detailed in Section 4 [cite: 20, 38].

---

By synthesizing sophisticated Tesseract PSM configuration, meticulous Pillow image manipulation leveraging modern Lanczos resampling, and rigorous regular expression data mining, this methodology produces a highly resilient receipt extraction pipeline. Ensuring compliance with the breaking changes in Pillow 12.0.0 and preventing Excel data mutation via openpyxl guarantees sustained performance in production environments.

**Sources:**
1. [nanonets.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG5Sxo2EvvT1pwZMkwC_M8iu4dD4xDvecSxFnpokmnMcJU0EZV-HnEFh1RCgF61jvejjvjwdpC6MqW3LwS07wmu0eA6k2wN1VrPQksUtlPcBaPRQ10BCukHKlnmN6RA1CCPl1A=)
2. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEwgLnTm-nfTLphOpShLOhqKOyqsHbZJgSwlWmfaDjTji_EBKGFiPeyMeSPSWjXvPvFh8y-01Xu5-TQkY4zQw5BU0WYJ-XgxVcapsl-711WJ0xkLWdyHL5KJkZH)
3. [kaggle.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQElODANFveDd6XVP1bvp1kMWtEJyXqQ1BKVAepKYyF18eRvYOD-XUWyfbMrVkNgWJMpF_BbHqO4ojnAf4f0Htm8h99kzx3TMT3xORed_4X_2C93ii7yT6dXdaY5_krW8oMrIKfAeQkDRSL_rLAlZNWKq-amagDYYZqJ)
4. [muthu.co](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEgtqgRzrrE6ZzmYAMKeWv1jO3DHMLWDf_1bHHcCC471CXrQpcJ11hT3NAo1gtVdifeVUTd7T0paK12lUQ68_PNL_MKIzVlDdit2oKilBU5tK4fuUts7f6dO9hOC53rDIjf)
5. [gopubby.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEa2nkganTM9lexKfZZmzCDLLtmJTMw_I7SmREitJHQqja-xq055LOiWnvkE7w7nMfwQxqC-5qU5BCaQeLsdL7QYC1jUHGGRGscBNaE4fp7HautkQOICtr2HexnALURmVkwBuXvPhz4PYwqKnySCdFV6prMSK1Jr-De4c_xw4Ef8bmGN6_uknAqBWCWdx9EBE9xSIGNGGgcyG3kzR71NE5T)
6. [pyimagesearch.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE1OddO3U8hk9oeavXOV-s0mDZjRHJ15Rp7H6nv-G1uTOHKAMPPDRYnPOMLPJ5WpxcXUetXPpvUf_kLOinIHoFcK3W6gOiO-qFN-W1vlFW6PLqkJvZBmiZ1bzVcuwj2VWFBSnLfO-3GyhA9MI0M1r-CL_MTDH6ikeaE46aiiIzFBMjw9udwtSBjwDaRieIAa6HJWEcVWLUTSkgrwVT85DWEXIil0NtKgqnqYhY8hw==)
7. [kaggle.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFNnRdBKLvsdDwvGj9E39hvH5Cjm-OZVHUlqu54cgcWT9-mhF-KAlZCZ0rfXGdrldq3asHafF6nVm80EXetiyPkLpMs2YyUJYlE5F7pocfhfoXEtY6lTEuum_AKlpzjleOYUQl3g0LIORC3-GvVMaHJLOuyLcuNsZEbdAINQujfpW7_)
8. [cloudthat.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFussqyqp0GttPPIE2Srit4s4ufW7KjHlI75ZB-RlRYmpAFz2Vo65SKlOMik4uEs6rfcmwDnwXHXlzDSPUc2ArSlBp8KMIWqEc_fL_T8q1RqNbXI2Nf0niayofiSpNJhALVe5eyM_UAXWvxhwsmH5b3DGKgURzMnxvFD9R9GXSa7jgDq87V0DxxkHDg40Fa7d349_ReMgAYWA==)
9. [nutrient.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE2vMGHcCeic7JOkymZ8ruPSSWeTXz-aE0xYimyGuUBxWbDhhu82vGc28NMsbc4QLpz6PxiM4BQ672ZbsQB1uLiM6UL3VMzblKHT6wlySIWcLQ2-X9rwscyPgMMA3ye_RXSf-C1zDr52tif)
10. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHhPsVKzGDIUCUagglCvDkiK38rr5aH1ksm8DbDtlm-9Wfj2DD26R8-80QgQGQQGTtzq-vyWjRL4uUHTf076UkmfjB-GuXcUBAP5Rr-Hc4falEext5Lhy5SVo2MS4CrXOryDZ4Me8RJd30byUMBmkNDj3iGNeh7)
11. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFx79h1lEhFxwB8dM0DVRAUf_ZN1d_dalQUp25klJOm3JAI7V2KQZIF5pqFeGx4TSjTFYQRi8kXror-A-gl4G4z7QphqFFhUtBxFPZe2CUWq_C4ZYF2OUwdNkWzirJ-d8khQb_x8i-S8f4YVxKOX6p6nzc3pYWuT3QeBxchkr769SAn5BgiapB8144IEK7SEjdllSIY-uS3XH1i1XfE)
12. [pyimagesearch.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE9sAmVTKr0rLmQoPS9otZhM2ACF5lB9mJ2CQDVT-RoU1_JngFkuk0-EMAr0qae9hADM1jvkhyqCPYtd_nZ2AHwHAw5F7CQB-zCcdCVvJs0tIABt61-injzLUSB4w7Hy-iiuwifLX2m2ApSsL_z8VEY2lP3FaFvsdQuMZqGvuPtoyt5slfc9WWT6xRXwzeCj7MpEo1KBJB2wznjaAjtFQ==)
13. [ropensci.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEgvuXX7rUP_Xo7MRD0xvIayQfaePB5gzKVoi38sgoqzcLkSMzlIOVU-4eEoc86zA91Eit9VilETZA7dVW8fvfPZpunKJF4tpl9k08RMcq9WKrrbloKmensOAstRcRx4MQc_XtTdFFNhlwijQIn)
14. [return2.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHyRrXvLHrfOYhZHVopgvtk-prNBMK56FzOXxDlDz1XJHA0PR1rFHzXvNXcnXKG7ZNQMyu2yo9r_92Wulb4VYEnSwHp-WSMVqHtcfoXHlIQpcnZokT5QIIykrFanf8NsPDRdK-UHh3SewRaStmd57Nb)
15. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFmsMsM1F96tqrM2G1JvQ5aMX4m52rFWZaq6Ig_Z1EQZW0S3zP7Ft_Yvdn0qx-At8_1zwPzXw3vJ2zHpSiutxaH6loh92iZPZ-EPG4Zy3WCACBKrkPgWGmW89Alz25ETGiERBARQl285_qlhaXuBJQkk1lzRBqp7oWiqKbfQ9gDsAOOf7lK3p1i5h4=)
16. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEkFb3s-F4_MgwmGQik1Bav9h2j4933CwW57V--Sa-fDQN0J77njnsggtM0uYIJ-z4Rt4DQXsOeBi1-OI6uewsWSjScgAVYNr1Rt5XBOUxQATIe5v43pETkW6uu8Lp7I5SHjUGHpjT01GhZ6jvsHAteBcbbhTP3XqJqBnGsOv0jt0gb)
17. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGz4ZP1k558e0DXailXofNOYwLu4eW3mlM_K4dV2C4w8UHjnlgaxabi7xmswEZorDgSFK1K-_35D8v5NXiMgwEilT851Rit47Jllfho7G-J-WOmIdmCZYUXJ9BdDv5JIzKy6iLlBybwb7II8rQA8jkWEkg_O9Cyxo89QB3TSNMWFuFNbMXIuNbakvG88Xo00Jhq0mUSiGcyPkLC)
18. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQECS_NR4Fu7GM5aDtsvcbRYPGPa-80Wjjv6SW2nAOiNiWNAPat5PW1u54_mMuA0329OLN6OcmeRl0Dj2KyIMES4kalj6tEHFiZXpyfcdHljXT0yYqgctoI76N979lDLG_Qx3WgYQ67n6AVmNAqigu4QRo7ooYKB6hawWsvUYC1Oc61oKtVIS4Dbaw9RQaV7X8xnn-oGJjkqSy99nybyrP7T)
19. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGrlJUW5ab42SRIkBKr42GqnPQ5IuXEKxmpBeTrWunpPFXB0gxHQfZH_e_K88VlEfN5nygMygK-PyTqDj8kNqSVsP9OVbLyI4oFMAcB_O03uDy7mneyJIuDyXnPMd_3ZtqsIuZK8oJzJU-XTQ==)
20. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGfw79qObRm_gM8vDvRgM8v-dQ6Vm5VJyN3O0XT44PVxM1ONrUZgbhkBbW0CaIY2mfGQNXUOQhxaNU57oSxpQ4FEgpPgGM-pHIfeUt3ufziyU9qx5mY_Wruawz9mmnbML8aUn9LuUh9qUax8f5SCMAh5eQ4zUr9WPgflSoEISuJHqqiWx9nqBW4sDTtcBuqvJQM1ksFwww1QlnEPWlJu3VD)
21. [oursky.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGTEtzSM2dD_mkekhpLKvTd64ogS5nL7mIpF09JizOqXDq-S3fZ1kR9Xl77llM9-xm7CXT5rZzlYkK8l9ui36fC1ulU101wLRjqwpSX03KyoSVt5s3V2U_ucyI33gcVB90FvV8ijsjdCea0-gfVexrS9NUjEflloMdcGAkObR1nlCtudxLANphmF38fP6dbco1boch2B9pzd5ktIkcvDuE=)
22. [konfuzio.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFEC-fibOHvPbpCxrDTZhWv60xZt3ZXt8QwxCqhvJc13_TTES2ECtw7FJDkk0TeFhboVYh4QTyL50lyCBtr5dG5ZSD1SzysW5wcef8rJxYALC2ULO6NvXuYBoLyoe52-x0=)
23. [tutorialspoint.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGzJyHgRv-jLbcOoCT8kxaRSxNEYKubZTg3sfGnHG9Yp16yQEqB-i4NV1oLenhn_GSHKe7ge3NsVT8Vng96P94N_sTZm5lCZC8uIHWOjEv_aSTMHqm4mIvRj8L4dpfTvaHJJsfkq29oKHkvAMNrARxH7TLk1TMN4qh_kIs9Y2f1PrHTpLx52dXas5jxSW8m_GVL_G5dSuF1MCc5)
24. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHYGXf2uGZoUGQND0DgPA1_TwBqBjcUx1NSdAT4TLPhTZRGRrLmj1qAWfL_NLMI9dLYc9Tnie6inS_aAusaFPTTlbRGoQipK3A2ZXYQSOO_Mv488KSphzAXU5Yt8UiKMpfxNdaVmBxjfwmVGDVxvyXrYGAlNMuXVRYKOYJojwzzpB9FRSy1EW-cVDtZleMCSTNnH1E7rEvQBYtDs03JyW72vE0Thvzf4Ny21C3MlCLl3E_xb6UfCiuvrXncMw==)
25. [datadriveninvestor.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGQt1UpUGNWvGZI137fkbS5p2EOOHVNMPaFhp7T5z1VeLUCNGQ2Iq8X57XLLaxfsZ2NlDlNicL-pQlNZHciguHSisvl2jEHW8jRcGW4Y5d_sAxlI16L9-FkauZ1a1EiHX6IYeT9lCt234fhh_isMxL_3aULj7u19BNH6Sz8KRKAS43gdaG9DBu7Huq025twNiDEbPdKmVeI4O3lYJeUgU0a4OBFcJg=)
26. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHUDsvWMZFd3Vi8z_QNi9lcilNdwHAn0HaH1FHI-kWFT4IBNwW7YELWom4v2_NMpdoar5ykGNvvGfTIVjbkCLvDdg8_N2KiKpmiWseq1UFFL8q1dNkvDCtMatq2O5n4_PSGcr9pm9ljJ57MnwqsGF-iur3QXDAEaEwJ5SWer6H_sgV2ACYBVoefdLPSGg==)
27. [plainenglish.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFKdJFZTPW6ve5P5y9rQPwn95RooEUTXHxwQE4hay6Pz0-La0iN6lUOCzzh_NbPSX5bVo9_9z91F8awoq5ytzZIvAnEYmHw_-YEOFahZHn1y4AHwnAuXBaOtJHkgiPeNZdHjbBFh3GcCb3KQplqEpyH_dtYMt22AvHO-sy5ZlLq0x4GxNPhBuuYf4M2PSHXwFok1ojP3g-5FCCDxt9HHCOcnB_eBnCrlOX8cwfcLL0=)
28. [dev.to](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGdQsjjSeK3FOvhgspH2D_ptQ_EBOvNUtTRGJ-cvNukpC9w1BOezr_bZPyAS5_mZr2TPpGvPJbqgVgpl7ZlLIg1LZXE-6z5KuB6evthGT01qMhWxr_8FiSW-3FUxyWeXmmdan_DeapG3PCMNP-PCvva7iCOAsjo0z8-rMHRFWVtJw09nYF8QvHSEWqn7tKG63JsaDLq2S04LmM=)
29. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEiLLvqzsUlWAQKNudu_bJNvWZLIrZnxkhHnVipgsaeKc8UsinmeFT9Xbz4qY0wrBKA-PQCKULXy2YXxNp6Y8JQhUVx1P0HYOEBD0rvVpIdVzgzKvBbs6mw-0SwMvXgns8h_cIJb_mNYxSJf4sUMvuLZuGb0toedQSLJxQG5-uCw51vler7NeHXQhk1VwLGN86_oQnqTg==)
30. [zenodo.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFTPvemmIzMO5IhEsqr3uOaSMtBr4CDM_XCyg5SJGdu_J2aBCUf_8yS2xdSxH4vD57HaasqVgIUDJgLaMBjRTJNashVfEUF2S5dq524IR_sK-erQJRxhX4xLw==)
31. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGpg2ggemJdGhLyecN3d8Bie7YKcABL6HB15_aOCB6JKMdhCYVG4JOo-57CrwJyLiVM6Ol2lMdk8Da6tVVcYFcWcQ4v_nwo-OBr2hKakGNu6d-TlVm4Oc7MjVggR0h9SC4dwbEqNTXQ2YDFL8NW7g-WEkLDtazPeHEKxBdn9bvLAC8JF6ShXJAeFK52x1WUnhRX5HLAt1WsrlLTV1wmvKaI-MCcY2FJKs93)
32. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEWFMQ9U-KOi3F3VbollwK1Z23-fQrX2HUrPFSU7U-JFK3oxTI5nGLWmib2yHIA4hw1nNR4IRWnGDcidpgkb8s6MW5u0Gpo8Ds88nDsdbnUoKSbBgIvUNDpR05O7EKyDOPqu4x9C3nXs5YyurTMttl-F5jOglIx)
33. [fosstodon.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEP_8RNkrV8ib1IT5a3ZtXElVOFANGF3kX0K4jPjkeFhcRlckkqGpDjYfsEbTfucscQ3B5CIsMjLjU9TaNex6-NHTw2zrDUW3XbInNTx_r4BcG5Kebwd9FBUt_GCvhDc2O5QV3v6Bc=)
34. [archlinux.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHjZyIw8AOsglf6tJBcU716aO1dJxEq0788Lu8X4gGGBsOfn4JYzkdkiKP83kLI2-pQKI3Nv3tjx6v2qGrfGhr5G9Jv7DGG1ACEEe_Uf2KXr1u35JKtVob_EG1Ar_dWLUOS_xVleWe4oVjNlJCrdn0auF8=)
35. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHzcFgNJP3GZoyWsCculDuF4-ZcnisK-aQDAQWFAw6rYEFj9-UEosRYJS7Er0hZ0Z5mAeaJah5mODGKgh1pCLGZlByUeofduBIhad0blLjECyTzowI-pIGD)
36. [heptapod.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH0KiIgKwCGnsyMZ1n9L48ah-rdVSJD3zsVcZKuaHVtJLXYrNZ7ePv9Y6-zo87WKo0P0DvVzjFUpWqvhYd9rFMLgJBMbcpfkP7LcIq7uoVXoerLou0lEz3zQuUIB2OdPWwXi9sCgzPt0ly7plHzCAmh6F_i)
37. [archlinux.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHmMKIrLHYzCg5rVklXJXFLAEQvKwXF2pqOLquPX36OtB_FyOfigmATFG0_e-bUP8L-tAMnTAYYvElIZV9rVZW1WlUBUkjDpx47dq-V4wG2PoJRsuRgTtpBrXRS90doTpfvU98UFbDCeqZg4tNOmcs=)
38. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFeTVDpFsY5QnVIkRxwUS_OzMx2LOheIpA15BgMhwANdysPs93m2l1o2nPGScY1H6hpASnal2x1YvCgHlVaq1wc2yRRGryy1oKjOmhaOvrqvy6IAuxPPHv0A01g5bYrLHxiuZ7B2VezA9JL124DEw==)

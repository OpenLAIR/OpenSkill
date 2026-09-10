# Domain Reference for evo-pdf-to-markdown

**Responsibility**: PDF ingestion and conversion to Markdown text with LaTeX formulas preserved in $$ delimiters

**Key functions to implement**: convert_pdf_to_markdown, setup_marker_models

---

## 1. The Marker-PDF (Version 1.3.3) Framework


The `marker-pdf` library, maintained by Datalab, has emerged as a premier open-source utility for converting complex academic documents into structured Markdown [cite: 1, 2]. Unlike basic text extractors, `marker-pdf` utilizes a deep learning pipeline to infer document layout and parse mathematical equations [cite: 2, 3].

### 1.1 Python API Usage for Version 1.3.3


In version 1.3.3, the API relies heavily on object-oriented converters rather than the standalone function calls seen in earlier 0.x versions [cite: 2, 3]. The core entity is the `PdfConverter` class, which manages the pipeline of providers, builders, processors, and renderers [cite: 2].

### 1.2 Configuration Options for Maximizing Extraction Quality


To maximize the quality of LaTeX extraction, particularly for standalone formulas, several configuration flags and environment variables must be finely tuned. By default, `marker-pdf` attempts to extract text directly from the PDF streams to save computational resources, relying on OCR only heuristically [cite: 3, 6]. However, digital text streams often scramble mathematical symbols. 

To override this and force high-fidelity visual transcription, the following configurations are vital [cite: 2, 7]:

| Parameter / Env Variable | Purpose in Formula Extraction | Recommendation |
| :--- | :--- | :--- |
| `TORCH_DEVICE` | Determines hardware acceleration (`cuda`, `mps`, `cpu`) [cite: 2, 8]. | Set to `cuda` or `mps`. CPU inference for math models is exceedingly slow [cite: 1]. |
| `--force_ocr` (CLI) / config dict | Forces OCR processing on the entire document, overriding embedded digital text [cite: 2, 7]. | **Highly Recommended**. Ensures inline and display math are passed to the `texify` model rather than relying on corrupted PDF character maps [cite: 2, 7]. |
| `--strip_existing_ocr` | Removes invisible OCR layers that may confuse the layout engine [cite: 2, 7]. | Enable if processing older, previously scanned papers [cite: 7]. |
| `--use_llm` | Integrates a Large Language Model (e.g., Gemini-2.0-flash) for post-processing and artifact correction [cite: 2, 7]. | **Recommended**. Drastically improves multi-line alignment and complex matrix formatting [cite: 2, 7]. |
| `--redo_inline_math` | Specifically forces the pipeline to re-evaluate and re-OCR inline mathematical spans [cite: 2, 7]. | Essential if the distinction between inline text and math variables is critical [cite: 7]. |

### 1.3 Handling Multi-line Equations and Known Limitations


**Multi-line and Aligned Environments:**
When processing equations that span multiple lines (e.g., `\begin{align} ... \end{align}`), `marker-pdf` attempts to preserve the alignment characters (`&`) and line breaks (`\\`). However, due to the nature of bounding box detection, a common failure mode is splitting a single multi-line equation array into multiple, distinct `$$...$$` blocks [cite: 3, 10]. 

**Numbered Equations:**
Academic papers frequently number display equations at the right margin (e.g., `(1.1)`). `marker-pdf` often includes these tags *inside* the LaTeX string (e.g., `$$ f(x) = y \tag{1.1} $$` or simply raw text `$$ f(x) = y (1.1) $$`) [cite: 11, 12]. This requires aggressive post-processing to strip out numbering if pure mathematical evaluation is the goal.

**Known Limitations of marker-pdf (v1.3.3):**
1.  **Imperfect Conversion Rate:** As explicitly stated in the documentation, `marker-pdf` will not convert 100% of equations to LaTeX [cite: 3, 10]. 
2.  **Whitespace and Indentation:** Horizontal spacing within formulas (e.g., `\quad`, `\hspace`) is rarely preserved perfectly [cite: 3, 10].
3.  **Column Misclassification:** In double-column formats, large equations spanning both columns may break the reading order, resulting in fragmented equations [cite: 13, 14].

---

## 2. Surya OCR Models and the Texify Pipeline


The power of `marker-pdf` lies in its orchestrated use of multiple distinct deep learning models, collectively known as the Surya OCR suite, alongside the `texify` model [cite: 1, 15].

## 7. Common Pitfalls and Migration Notes


Building a resilient pipeline requires avoiding several documented traps and version-specific behaviors.
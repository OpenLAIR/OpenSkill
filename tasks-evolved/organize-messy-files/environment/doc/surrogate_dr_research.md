To verify the correctness of the document classification skill, you can implement a `pytest` suite that relies on the following invariants and reference points.

### 1. Independently Computable Reference Values
You can use the arXiv identifiers and file names provided in the `Dockerfile` as ground-truth anchors. Since these are public scientific papers, their subjects are fixed and verifiable via their arXiv metadata or content.

*   **Reference Mapping (Hard-coded Assertions):**
    *   `arxiv:2310.00034v2.pdf` → **LLM** (Title: "PB-LLM: Partially Binarized Large Language Models")
    *   `arxiv:2402.11651v2.pdf` → **LLM** (Title: "Learning From Failure: Integrating Negative Examples when Fine-tuning Large Language Models")
    *   `arxiv:2312.10793v3.pdf` → **LLM** (Title: "Demystifying Instruction Mixing for Fine-tuning Large Language Models")
    *   `DAMOP.pptx` → **trapped_ion_and_qc** (DAMOP is the Division of Atomic, Molecular, and Optical Physics, which frequently hosts trapped ion and quantum computing research).

### 2. Dataset-Level Statistical Invariants
These assertions ensure the integrity of the sorting process:

*   **Completeness Constraint:** The sum of files in all 5 target folders must equal the total number of input files (100 papers + 3 artifacts = 103 files).
    ```python
    assert sum(len(os.listdir(folder)) for folder in target_folders) == 103
    ```
*   **Exclusivity Constraint:** No file should exist in more than one folder.
    ```python
    all_files = [f for folder in target_folders for f in os.listdir(folder)]
    assert len(all_files) == len(set(all_files))
    ```
*   **Zero-Loss Constraint:** The number of files in the source directory (`/root/papers/all`) must be 0 after the operation.

### 3. Cross-Validation Approaches
To verify the classification logic independently of your implementation:

*   **Keyword-Based Verification:** Use a simple grep-based check to verify that the classification logic aligns with domain-specific terminology.
    *   **LLM:** `grep -ri "transformer" "LLM/" | wc -l` (Should be high)
    *   **Trapped Ion:** `grep -ri "qubit" "trapped_ion_and_qc/" | wc -l` (Should be high)
    *   **Black Hole:** `grep -ri "event horizon" "black_hole/" | wc -l` (Should be high)
*   **Alternative Tooling:** You can use `pdftotext` (installed in the environment) to extract text from a sample file and compare it against the expected subject keywords.
    ```bash
    # Example check for a known LLM paper
    pdftotext arxiv:2310.00034v2.pdf - | grep -i "language model"
    ```

### 4. Benchmarks and Reference Implementations
*   **Subject Keywords (Oracle):**
    *   **LLM:** "Large Language Model", "Transformer", "Fine-tuning", "Instruction tuning"
    *   **Trapped Ion and QC:** "Trapped ion", "Qubit", "Quantum computing", "DAMOP", "Atomic physics"
    *   **Black Hole:** "Event horizon", "Singularity", "General relativity", "Astrophysics"
    *   **DNA:** "Genomics", "Nucleotide", "CRISPR", "DNA sequencing"
    *   **Music History:** "Musicology", "Composer", "Symphony", "Musical notation"

You can hard-code these keywords into your `pytest` suite to perform a "sanity check" on the contents of the sorted folders, ensuring that files in the `LLM` folder actually contain LLM-related terminology.
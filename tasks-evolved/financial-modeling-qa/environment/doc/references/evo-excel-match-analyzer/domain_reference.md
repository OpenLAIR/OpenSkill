# Domain Reference for evo-excel-match-analyzer

**Responsibility**: Excel data ingestion, index-parity slicing with correct 0-indexed vs 1-indexed mapping, reset_index alignment for vectorized comparison, win/loss tallying, and strict output formatting.

**Key functions to implement**: load_excel_data, split_by_parity, compare_paired_matches, compute_win_difference, write_answer

---

## 2. Advanced Ingestion of Large Excel Files


The Office Open XML (OOXML) format, represented by `.xlsx` extensions, is essentially a zipped archive containing highly structured XML documents [cite: 1]. Parsing XML is notoriously memory-intensive. For large Excel files (e.g., 400KB+ to multi-gigabyte files with hundreds of thousands of rows), naive instantiation of a Document Object Model (DOM) tree in memory can result in severe memory bloat—often requiring up to 50 times the original file size in Random Access Memory (RAM) [cite: 2].

### 2.1 The `pandas.read_excel()` Signature and Engine Delegation


In pandas 2.2.3, the `pd.read_excel()` function serves as a top-level wrapper that delegates parsing to underlying engines [cite: 3, 4, 5]. For modern `.xlsx` files, `openpyxl` is the standard engine [cite: 5].

The exact API signature and relevant parameters are as follows:

```python
import pandas as pd
import numpy as np

### 2.2 Retrieving Workbook Sheet Names


To process multi-sheet workbooks where data may be distributed across varying tabs, identifying the underlying sheet names is a necessary first step. This can be achieved natively via pandas or via `openpyxl`.

**Using pandas `ExcelFile` Context Manager:**
The `pd.ExcelFile` class provides direct access to workbook metadata without loading all sheet data into memory [cite: 11].

```python
import pandas as pd

def get_sheet_names_pandas(filepath: str) -> list:
    """Extracts sheet names using pandas."""
    with pd.ExcelFile(filepath, engine='openpyxl') as xls:
        return xls.sheet_names  # Returns list of strings [cite: 11, 12]
```

**Using `openpyxl` Directly:**
If bypassing pandas for lower-level operations, `openpyxl` handles this natively via the `sheetnames` attribute [cite: 13].

```python
import openpyxl

def get_sheet_names_openpyxl(filepath: str) -> list:
    """Extracts sheet names using openpyxl directly."""
    wb = openpyxl.load_workbook(filename=filepath, read_only=True)
    sheets = wb.sheetnames
    wb.close() # Always explicitly close read-only workbooks [cite: 14]
    return sheets
```

### 2.3 Handling Multi-Sheet Workbooks


In financial modeling, data is often partitioned horizontally across sheets (e.g., "Q1_Data", "Q2_Data"). To ingest this smoothly, utilize `sheet_name=None` to load all sheets into an ordered dictionary [cite: 5].

```python
def load_and_concat_all_sheets(filepath: str) -> pd.DataFrame:
    """Loads all sheets and concatenates them into a single continuous DataFrame."""
    # sheet_name=None returns Dict[str, pd.DataFrame]
    all_sheets_dict = pd.read_excel(
        filepath, 
        sheet_name=None, 
        engine='openpyxl'
    )
    
    # Concatenate while preserving the origin sheet name as a new index level or column
    df_combined = pd.concat(all_sheets_dict, axis=0, ignore_index=False)
    
    # Reset index to make the sheet name a standard column (usually becomes 'level_0')
    df_combined = df_combined.reset_index(level=0).rename(columns={'level_0': 'Source_Sheet'})
    return df_combined
```

## 4. Game/Match Comparison: Analytical Patterns and Index Parity


A classic scenario in financial, gaming, or sporting data analysis requires evaluating sequences of paired events (e.g., comparing Player 1 vs Player 2, or "Bid" vs "Ask" spread on alternating rows).

Given a tabular dataset where rows represent individual participant results, and two sequential rows represent one complete match (e.g., Row 1 is Player 1, Row 2 is Player 2 in Match 1; Row 3 is Player 1, Row 4 is Player 2 in Match 2), isolating and comparing these entities requires strict index-parity filtering.

### 4.1 The 1-Indexed vs 0-Indexed Pitfall

The most profound source of logical bugs in paired-row analysis stems from human vs. programmatic counting:
*   **Human (1-Indexed):** Game 1 corresponds to rows 1 and 2. Game 2 corresponds to rows 3 and 4. Player 1 is the "odd" row (1, 3, 5), Player 2 is the "even" row (2, 4, 6).
*   **Pandas (0-Indexed):** The first row rests at index `0`. The second row rests at index `1`.

Thus, when a prompt requests filtering "odd numbered games" or "Player 1 from the odd game", the mapping translates mathematically as:
*   **Player 1 (Human Odd):** Pandas Indices `0, 2, 4, 6...` (Mathematically Even Indices).
*   **Player 2 (Human Even):** Pandas Indices `1, 3, 5, 7...` (Mathematically Odd Indices).

### 4.2 Slicing by Parity Using `iloc`


Pandas provides the `.iloc` indexer, which enables slice notation `[start:stop:step]`.

```python
import pandas as pd

### 4.3 The Critical `reset_index(drop=True)` Alignment Pattern


If one attempts to execute a vectorized boolean comparison directly:
```python

## 5. Determining Match Winners and Edge Case Handling


Once the dataset is structurally partitioned and aligned, vectorized operations can determine overall aggregate statistics.

### 5.1 Vectorized Comparison and Tie Handling


To tally the number of times Player 1 won, we calculate the sum of the boolean mask. In Python, `True` evaluates to `1` and `False` evaluates to `0`.

```python

### 5.2 Pitfalls in Row Filtering and Comparisons


In developing automated financial pipelines, several common data inconsistencies can trigger fatal errors during pairwise comparison:

1.  **Odd Number of Total Rows (Dangling Pairs):**
    If the dataset contains 7 rows, `player1_df` will have 4 rows (indices 0, 2, 4, 6) while `player2_df` will have 3 rows (indices 1, 3, 5). 
    After `reset_index(drop=True)`, comparing a length-4 Series against a length-3 Series will still cause pandas to append a `NaN` to the shorter Series [cite: 31], potentially skewing calculations.
    *Mitigation*: Truncate to the minimum length of the two sets.
    ```python
    min_length = min(len(p1_scores), len(p2_scores))
    p1_scores = p1_scores.iloc[:min_length]
    p2_scores = p2_scores.iloc[:min_length]
    ```

2.  **Excel String Coercion (Data Type Issues):**
    Excel datasets often include cell formatting that coerces numeric scores into strings (e.g., `' 10'` or `"15 points"`). Pandas might evaluate string comparisons lexicographically, where `"9" > "10"` equates to `True`.
    *Mitigation*: Force numeric coercion using `pd.to_numeric()`.
    ```python
    p1_scores = pd.to_numeric(p1_scores, errors='coerce') # Invalid parsing becomes NaN
    ```

3.  **NaN Propagation:**
    If an Excel cell is empty, pandas parses it as `NaN` [cite: 5, 36]. In Python, `NaN > 5` is `False`, and `NaN < 5` is `False`.
    *Mitigation*: Drop or fill NaNs before comparison.
    ```python
    p1_scores = p1_scores.fillna(0)
    ```

4.  **Header Row Shifting:**
    If an Excel file contains a "Report Title" on row 0, and actual column headers on row 1, `pd.read_excel(header=0)` will consume the title as the header and the real headers as row 0 (which is Player 1 in our logic).
    *Mitigation*: Explicitly define the integer index of the header row utilizing `header=1` or `skiprows=1` [cite: 3, 6, 37].

***

## 6. Output Formatting and Data Serialization


After algorithmic analysis yields a singular scalar value (e.g., `p1_total_wins`), it is frequently required to serialize this output strictly for programmatic verification or ingestion by downstream C++/Java systems.

Python's built-in `print()` or standard file `write()` operations naturally introduce formatting artifacts, such as trailing newline characters (`\n`).

### 6.1 Writing Exact Characters Without Newlines


To ensure exactly and only the characters of the result are written to the file system, the context manager `with open()` is utilized alongside string casting [cite: 7].

```python
def write_exact_result(result: int, output_filepath: str = 'answer.txt'):
    """
    Writes a singular result to a text file with zero formatting or trailing newlines.
    """
    with open(output_filepath, 'w', encoding='utf-8') as f:
        # Cast to string to prevent TypeError, write purely the string characters
        f.write(str(result))
```
By explicitly bypassing `print(..., file=f)` or `f.writelines()`, we guarantee the file terminates precisely after the final digit of the integer string.

***

## 7. Synthesis: A Comprehensive Reusable Utility Class


To concretize these isolated APIs, the following block constructs a robust, enterprise-grade utility class that orchestrates the entire workflow: Reading an Excel file efficiently, slicing parity indices correctly, managing missing edge cases, executing vectorized comparisons, and outputting to disk.

```python
import pandas as pd
import numpy as np
import openpyxl
from pathlib import Path

class MatchAnalysisEngine:
    """
    Reusable utility class for orchestrating data extraction and paired 
    row analysis from Excel datasets.
    """
    
    def __init__(self, filepath: str, sheet_name=0):
        self.filepath = Path(filepath)
        self.sheet_name = sheet_name
        self.df = pd.DataFrame()
        
    def load_data(self):
        """Loads data handling memory optimizations and engine mapping."""
        if not self.filepath.exists():
            raise FileNotFoundError(f"File {self.filepath} missing.")
            
        # Implementation of memory-safe load [cite: 5, 6]
        self.df = pd.read_excel(
            io=self.filepath,
            sheet_name=self.sheet_name,
            engine='openpyxl',
            engine_kwargs={'data_only': True} # Discards formulas for raw values [cite: 17]
        )
        
    def calculate_player_one_wins(self, score_column: str) -> int:
        """
        Calculates match wins for Player 1 (Odd human rows / Even Python indices).
        """
        if score_column not in self.df.columns:
            raise KeyError(f"Column '{score_column}' not found in dataset.")
            
        # 1. Clean the target column to numeric [cite: 36]
        cleaned_scores = pd.to_numeric(self.df[score_column], errors='coerce').fillna(0)
        
        # 2. Extract parity slices (0-indexed logic)
        # Player 1 = Indices 0, 2, 4...
        p1_series = cleaned_scores.iloc[0::2].reset_index(drop=True)
        # Player 2 = Indices 1, 3, 5...
        p2_series = cleaned_scores.iloc[1::2].reset_index(drop=True)
        
        # 3. Handle Dangling Pair edge case
        min_len = min(len(p1_series), len(p2_series))
        p1_series = p1_series.iloc[:min_len]
        p2_series = p2_series.iloc[:min_len]
        
        # 4. Vectorized Comparison (Ties evaluate to False automatically) [cite: 30, 32]
        p1_wins_mask = p1_series > p2_series
        
        return int(p1_wins_mask.sum())
        
    def write_result(self, result: int, filename: str = 'answer.txt'):
        """Serializes result strictly to file."""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(str(result))
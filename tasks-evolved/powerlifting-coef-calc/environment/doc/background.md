# An Exhaustive Analysis of the DOTS Scoring System in Powerlifting and Data Processing using Python's openpyxl Library

**Key Points:**
*   **The DOTS Formula** is an advanced relative-strength metric introduced to correct statistical biases in the older Wilks coefficient. It uses a fourth-degree polynomial denominator derived from drug-tested, raw powerlifting competition data.
*   **Coefficients** differ by sex. For males: \(A = -0.000001093\), \(B = 0.0007391293\), \(C = -0.1918759221\), \(D = 24.0900756\), \(E = -307.75076\). For females: \(A = -0.0000010706\), \(B = 0.0005158568\), \(C = -0.1126655495\), \(D = 13.6175032\), \(E = -57.96288\). 
*   **Data Handling:** In the OpenPowerlifting dataset, negative lifting values indicate failed attempts and must be treated as disqualifications (bombs) for the purpose of computing a total. 
*   **The `Mx` category**, established for non-binary athletes, convention dictates the utilization of the male polynomial coefficients to ensure standardized calculations.
*   **Python's `openpyxl`** library is a powerful tool for automating Excel calculations. However, it only stores formula strings, not computed values. Version 3.1.5 exhibits specific edge-case bugs related to `BytesIO` objects, corrupted charts, and `kwargs` handling in parallel data-processing frameworks.

In competitive powerlifting, comparing athletes across vastly different body weights requires mathematical normalization to determine relative, pound-for-pound strength. For decades, the Wilks coefficient dominated the sport, but its reliance on historical, single-ply equipment data led to statistical biases [cite: 1, 2]. The Dynamic Objective Team Scoring System (DOTS) was developed to provide a fairer, more modern evaluation system [cite: 3, 4]. Managing massive amounts of competition data, such as the open-source OpenPowerlifting dataset, requires programmatic tools. This report provides an exhaustive, academic breakdown of the exact mathematical DOTS formula, the edge-case handling of powerlifting datasets, the construction of equivalent Microsoft Excel logic, and automated data processing utilizing the Python library `openpyxl`.

---

## 1. The Mathematical Framework of the DOTS Scoring System

The DOTS formula was developed in 2019 by Tim Konertz, a German powerlifter and statistician affiliated with the German Powerlifting Federation (BVDK) [cite: 5]. Konertz engineered the formula to rectify documented systemic biases in the original Wilks equation, which tended to statistically over-score male middleweight lifters and female super-heavyweights [cite: 2, 5]. By analyzing competitive powerlifting records between 2010 and 2018, Konertz utilized polynomial regression to derive a normalized, smoothed curve that more accurately models modern athletic capabilities across weight classes [cite: 6].

### 1.1 The Exact DOTS Formula and Coefficients

At its core, the DOTS system is defined by multiplying an athlete's total successfully lifted weight by a bodyweight-dependent coefficient. The coefficient is calculated by dividing 500 by a fourth-degree polynomial based on the athlete's bodyweight in kilograms (BW) [cite: 4, 7]. 

The primary formula is expressed as:
\[ \text{DOTS Score} = \text{TotalKg} \times \left( \frac{500}{A \cdot BW^4 + B \cdot BW^3 + C \cdot BW^2 + D \cdot BW + E} \right) \]

To ensure the calculation scales correctly for the physiological differences between biological sexes, two distinct sets of polynomial constants are employed. 

**Exact Coefficients for Male Lifters:**
*   **\(A\)** = -0.000001093
*   **\(B\)** = 0.0007391293
*   **\(C\)** = -0.1918759221
*   **\(D\)** = 24.0900756
*   **\(E\)** = -307.75076

**Exact Coefficients for Female Lifters:**
*   **\(A\)** = -0.0000010706
*   **\(B\)** = 0.0005158568
*   **\(C\)** = -0.1126655495
*   **\(D\)** = 13.6175032
*   **\(E\)** = -57.96288

*Note on formula variations:* While certain unofficial online calculators implement a fifth-degree polynomial for DOTS (sometimes erroneously conflating it with the older Wilks equations) [cite: 5, 8], the official, drop-in mathematical definition of DOTS as utilized by OpenPowerlifting and its underlying Rust coefficients crate (`crates/coefficients/src/dots.rs`) relies strictly on the precise fourth-degree polynomial constants provided above [cite: 1, 7].

### 1.2 Valid Bodyweight Bounds and Edge Cases

Because the DOTS formula is built upon a polynomial regression of real-world lifting data, utilizing the equation outside of the statistical limits of human bodyweight produces nonsensical mathematical artifacts. Tim Konertz explicitly defined the valid bounds of the DOTS formula to prevent severe extrapolation errors [cite: 5]:
*   **Men:** The formula is valid for bodyweights ranging from **40.0 kg to 210.0 kg** (88 to 463 lbs) [cite: 5].
*   **Women:** The formula is valid for bodyweights ranging from **40.0 kg to 150.0 kg** (88 to 331 lbs) [cite: 5]. 

The upper boundary for female lifters is lower because the global dataset for competitive female lifters exceeding 150 kg was determined to be too statistically sparse to anchor a reliable curve [cite: 5]. If a lifter's weight falls outside of these bounds, applying the DOTS formula will yield an unsupported extrapolation, although standard calculators and dataset analyzers generally proceed to calculate the value anyway.

---

## 2. OpenPowerlifting Data Schema and Input Variable Handling

The OpenPowerlifting project is a comprehensive, open-source archive of global powerlifting data spanning millions of records [cite: 9, 10]. Calculating the DOTS score from this dataset requires a nuanced understanding of its data schema.

### 2.1 Essential Schema Columns for DOTS
To compute a DOTS score dynamically, only six core columns from the dataset are required [cite: 11]:
1.  `Name`: The athlete's identifier.
2.  `Sex`: Recorded as `M` (Male), `F` (Female), or `Mx` (Gender-neutral/Non-binary) [cite: 1, 11].
3.  `BodyweightKg`: The official scale weight of the athlete at the meet.
4.  `Best3SquatKg`: The highest successful squat attempt.
5.  `Best3BenchKg`: The highest successful bench press attempt.
6.  `Best3DeadliftKg`: The highest successful deadlift attempt.

*(Note: While equipment type—such as Raw, Single-ply, Multi-ply—is recorded, the standard DOTS formula itself does not require an equipment variable modifier, as it natively operates on raw lifting data norms [cite: 12].)*

### 2.2 Computing TotalKg and Handling Negative Values
The DOTS formula requires a valid `TotalKg` metric. The `TotalKg` is defined as the sum of `Best3SquatKg`, `Best3BenchKg`, and `Best3DeadliftKg` [cite: 1]. 

Crucially, in the OpenPowerlifting schema, **negative numeric values indicate a failed attempt** (e.g., an athlete failing to lift a weight) [cite: 9, 11]. The dataset retains these negative numbers to allow for statistical analysis of failure rates [cite: 9]. 
*   **Rule of Computation:** A negative "best" lift means the lifter failed all three attempts in that discipline—colloquially known as "bombing out." If any of the `Best3...` variables are negative, the lifter is disqualified from registering a total. 
*   **Treatment:** Negative best lifts must **never** be treated as zero, nor should they be added algebraically to positive lifts. Doing so would artificially reduce a total [cite: 11, 13]. Instead, the lifter must be entirely excluded from the DOTS calculation, and their `TotalKg` must be left empty or undefined [cite: 1].

### 2.3 Edge Cases: Disqualifications and the Mx Category
*   **Disqualifications (DQ, DD, NS):** If an athlete is marked as `DQ` (Disqualified due to procedure or bombing out), `DD` (Doping Disqualification), or `NS` (No-Show), they have no valid total. Their DOTS score must be left blank [cite: 1].
*   **The Mx Category:** The `Mx` sex category is provided as a dedicated competition space for non-binary and transitioning athletes across certain federations like the USAPL [cite: 1, 14]. When computing mathematical coefficients like Wilks or DOTS for an `Mx` competitor, the widely accepted convention—and the standard applied within the OpenPowerlifting codebase—is to route them through the **Male coefficient formula** across the board [cite: 15].

---

## 3. Microsoft Excel Formula Implementation

Processing powerlifting data in Excel requires careful syntax to handle the conditional math, negative failure flags, and precision rounding inherently demanded by the sport.

### 3.1 The `TotalKg` Formula
Assume your spreadsheet has the following columns: `Best3SquatKg` in `D2`, `Best3BenchKg` in `E2`, and `Best3DeadliftKg` in `F2`. To calculate `TotalKg` in cell `G2`, we must ensure no cell is empty and no cell contains a negative value (representing a failed discipline).

**Excel Formula for `TotalKg` (Cell G2):**
```excel
=IF(OR(ISBLANK(D2), ISBLANK(E2), ISBLANK(F2), D2<=0, E2<=0, F2<=0), "", D2+E2+F2)
```
*Explanation:* This ensures that if any of the mandatory lifts are missing or are negative (a failed attempt resulting in bombing out), the total is returned as a blank string `""`.

### 3.2 The `DOTS` Formula
Assuming `Sex` is in `B2`, `BodyweightKg` is in `C2`, and the calculated `TotalKg` is in `G2`. To output a DOTS score rounded to three decimal places (the standard precision in powerlifting scorekeeping), we must nest the polynomial evaluation within a conditional statement that switches coefficients based on sex. We must also ensure the `Mx` category utilizes the male coefficients [cite: 15].

**Excel Formula for `DOTS` (Cell H2):**
```excel
=IF(OR(G2="", C2=""), "", ROUND(G2 * 500 / IF(OR(B2="M", B2="Mx"), (-0.000001093*C2^4 + 0.0007391293*C2^3 - 0.1918759221*C2^2 + 24.0900756*C2 - 307.75076), (-0.0000010706*C2^4 + 0.0005158568*C2^3 - 0.1126655495*C2^2 + 13.6175032*C2 - 57.96288)), 3))
```
*Explanation:* The outer `IF` checks for missing total or bodyweight. The inner `IF` routes any `M` or `Mx` inputs to the male fourth-degree polynomial denominator, and all others (effectively `F`) to the female denominator. The resulting calculation is rounded to three decimal places.

---

## 4. Programmatic Data Processing Using Python's `openpyxl`

When dealing with datasets featuring tens of thousands of powerlifting meets, manual Excel input becomes impossible. The Python library `openpyxl` is the industry standard for programmatically interacting with `.xlsx` workbooks [cite: 16]. 

Below is a complete, executable Python script establishing several vital workflows:
1. Loading an Excel workbook with multiple sheets.
2. Copying specific columns from one sheet to a new layout while preserving order.
3. Programmatically writing the Excel `TotalKg` and `DOTS` formulas as strings.
4. Saving the workbook while retaining all sheets intact.

### 4.1 Working Python Implementation

```python
import os
from openpyxl import load_workbook, Workbook

def process_powerlifting_data(input_file, output_file):
    # Workflow 1: Load the workbook
    # Note: We do not use data_only=True here because we want to preserve 
    # any existing formulas on the sheet if we modify them.
    wb = load_workbook(input_file)
    
    # Assume the raw data is on a sheet named 'RawData'
    if 'RawData' not in wb.sheetnames:
        raise ValueError("The workbook must contain a sheet named 'RawData'")
    
    source_sheet = wb['RawData']
    
    # Create a new sheet to hold the copied columns and new computed formulas
    # Existing empty sheets are preserved by default in openpyxl.
    if 'DOTS_Calculations' in wb.sheetnames:
        del wb['DOTS_Calculations'] # Clean up if running multiple times
    
    dest_sheet = wb.create_sheet(title='DOTS_Calculations')
    
    # Define the columns we want to copy from the source
    headers_to_copy = ['Name', 'Sex', 'BodyweightKg', 'Best3SquatKg', 'Best3BenchKg', 'Best3DeadliftKg']
    
    # Find the column indices in the source sheet
    source_headers = {cell.value: idx for idx, cell in enumerate(source_sheet[cite: 17], 1)}
    
    # Write headers to the destination sheet
    for col_idx, header in enumerate(headers_to_copy, 1):
        dest_sheet.cell(row=1, column=col_idx, value=header)
        
    # Append the headers for our calculated columns
    dest_sheet.cell(row=1, column=7, value="TotalKg")
    dest_sheet.cell(row=1, column=8, value="DotsScore")
    
    # Workflow 2: Copy specific columns row by row
    max_row = source_sheet.max_row
    for row in range(2, max_row + 1):
        for col_idx, header in enumerate(headers_to_copy, 1):
            source_col = source_headers.get(header)
            if source_col:
                source_value = source_sheet.cell(row=row, column=source_col).value
                dest_sheet.cell(row=row, column=col_idx, value=source_value)
                
        # Workflow 3: Writing Excel formulas using openpyxl
        # openpyxl requires formulas to be written exactly as they would appear in Excel (starting with '=')
        # We construct dynamic string references (e.g., D2, E2, F2)
        
        # TotalKg formula (Columns: D=Squat, E=Bench, F=Deadlift)
        total_formula = f'=IF(OR(ISBLANK(D{row}), ISBLANK(E{row}), ISBLANK(F{row}), D{row}<=0, E{row}<=0, F{row}<=0), "", D{row}+E{row}+F{row})'
        dest_sheet.cell(row=row, column=7, value=total_formula)
        
        # DOTS formula (Columns: B=Sex, C=Bodyweight, G=TotalKg)
        dots_formula = (
            f'=IF(OR(G{row}="", C{row}=""), "", ROUND(G{row} * 500 / '
            f'IF(OR(B{row}="M", B{row}="Mx"), '
            f'(-0.000001093*C{row}^4 + 0.0007391293*C{row}^3 - 0.1918759221*C{row}^2 + 24.0900756*C{row} - 307.75076), '
            f'(-0.0000010706*C{row}^4 + 0.0005158568*C{row}^3 - 0.1126655495*C{row}^2 + 13.6175032*C{row} - 57.96288)), 3))'
        )
        dest_sheet.cell(row=row, column=8, value=dots_formula)

    # Workflow 4: Saving the workbook
    # The source 'RawData' sheet remains untouched, and our new sheet is successfully appended.
    wb.save(output_file)
    print(f"File successfully saved to {output_file}")

# Example usage:
# process_powerlifting_data('openpowerlifting_extract.xlsx', 'openpowerlifting_scored.xlsx')
```

---

## 5. Advanced Mechanics and Pitfalls in `openpyxl` (Focusing on Version 3.1.5)

While `openpyxl` is robust, programmatic manipulation of Excel files introduces several edge cases, execution quirks, and specific bugs associated with version 3.1.5, which developers must navigate carefully.

### 5.1 Formula Evaluation and the `data_only=True` Paradigm
One of the most misunderstood aspects of `openpyxl` is its relationship with formula evaluation. `openpyxl` **does not possess an internal calculation engine** [cite: 17, 18]. When you write a formula (e.g., `=A1+B1`) into a cell, `openpyxl` simply writes the literal text string into the underlying XML architecture of the file [cite: 18]. 

If you subsequently load that workbook using `load_workbook('file.xlsx')`, querying that cell will return the formula string, not the calculated number.
*   To retrieve the actual computed result, you must use `load_workbook('file.xlsx', data_only=True)` [cite: 17].
*   **Crucial caveat:** `data_only=True` relies on a cached value that Microsoft Excel calculates and saves the *last time the file was manually opened and saved by a human in the Excel GUI*. If you generate a file with formulas via Python, save it, and immediately reopen it with `data_only=True` via Python, the cells will return `None` because Excel has not yet had an opportunity to launch its calculation engine to generate the cached values [cite: 18].

### 5.2 Handling of Worksheets
By default, `openpyxl` preserves all data, macros (if using `keep_vba=True`), and empty sheets present in a loaded workbook. If a workbook is instantiated fresh (`wb = Workbook()`), it generates a single default sheet named `Sheet`. Empty sheets will remain upon saving unless explicitly deleted utilizing `del wb['SheetName']`.

### 5.3 Version-Specific Quirks in `openpyxl` 3.1.5
Version 3.1.5 introduced several well-documented bugs and operational anomalies that can disrupt production environments:

1.  **The `BytesIO` and `data_only=True` Exception:**
    When utilizing serverless cloud architectures (like AWS Lambda or Docker instances), engineers frequently pass Excel files as in-memory byte buffers rather than writing to physical disk space (utilizing `io.BytesIO`) [cite: 19]. In version 3.1.5, combining a `BytesIO` buffer with the `data_only=True` flag causes a critical failure, generating a `Bad offset for central directory` exception [cite: 17]. This happens because the ZIP file parser inside `openpyxl` mishandles the stream pointer when stripping formulas. The known workaround is to save the buffer to a temporary disk location (`NamedTemporaryFile`) instead of keeping it purely in memory when `data_only=True` is strictly required [cite: 19].

2.  **Chart and Graph Corruption:**
    Saving an existing Excel file that contains 3D charts, bar graphs, or mapping widgets using `openpyxl` 3.1.5 frequently corrupts the visual elements [cite: 20, 21]. The library mistakenly alters the XML tags managing `AppVersion` and border radius logic, leading to charts displaying with rounded corners unexpectedly, overlaid text missing its axes, or the charts vanishing completely [cite: 20, 21]. Users heavily reliant on Excel graphing are generally advised to downgrade to version 3.1.3 to avoid this specific mutation [cite: 21].

3.  **Pandas/Modin `engine_kwargs` Disconnect:**
    When utilizing high-performance dataframe wrappers like `pandas` or `modin` to read Excel files, developers can pass arguments to the underlying engine: `pd.read_excel('file.xlsx', engine='openpyxl', engine_kwargs={'data_only': True})` [cite: 18]. In version 3.1.5, a bug prevents these `engine_kwargs` from routing correctly through to the `openpyxl` reader in multi-threaded environments like Dask or Ray, resulting in the dataframe importing the literal formula strings rather than the evaluated data [cite: 18].

4.  **External Link Corruption:**
    Version 3.1.5 possesses an unresolved bug when processing Excel files linked to external data sources. The `Workbook.save` function fails to write multiple entries of the `Relationship` tags correctly in the underlying XML structure, creating a corrupt and un-openable `.xlsx` file if the original spreadsheet contained complex external data references [cite: 22]. The current workaround requires manual patching of the `openpyxl` source code [cite: 22].

---

## 6. Conclusion

The DOTS scoring system provides a mathematically robust, unweighted metric for analyzing pound-for-pound strength in powerlifting. By leveraging a fourth-degree polynomial coefficient—with precise decimal constants tailored to physiological variances between sexes—the formula successfully minimizes statistical biases seen in older models. Handling data to compute these scores programmatically demands rigorous logic constraints: negative, failed attempts must trigger disqualification events, and the `Mx` demographic maps to the male biological constants to ensure fair, normalized comparison. While utilizing Python's `openpyxl` provides immense flexibility in generating these calculations natively as Excel formulas, understanding the string-only evaluation mechanics and the specific version 3.1.5 engine bugs is paramount to building resilient, automated powerlifting analytics tools.

**Sources:**
1. [gitlab.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEQjzqLioXZJPow8DXr_NGgWaP2SL5gRNGoLj9MdhP0LhPwC_oU9Z05XCrOl6rYSEERo-Kn8jHFElKGMgmwc0GZtYiGHl1Mc41Y1zF_rhqO-8NuNECnVR7umpZp1kWzpyeVACiv-jIRjQaynLRy0FaV8wuz)
2. [turtlestrength.com.au](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHcPpqL5fJdAcEM4gLrqEFFRPzR0feniEb5JLKPJB4Ww-PGcce6FYRsFlWZ5aS5fF2nayGOlXsk-OvJ9XFm8yoXR7vxXywRKpkk1mKBsBuTbGeAsEFlWHMs0wmfHBDqr_DC7yCZI4Ou2MlrgC9KtxUOLyIwHU0nQSttQ8c9UgsAoVHBmoACBQbjNsezbzwjuyCq5uzWmrU5KVU=)
3. [powerliftpro.app](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE21oqHKJOCXTc8g__9o1jwtLba4wZLMk7l0mnw1tCqCLabNSClppBQYrRdc2Jm9Oyrxf_0VhiPbVQjHFJmcyP5s7mVnnBa6BeeVuUI7mmb4LPuPxYXf9-oMEAX9DMiDb4lPIOJLqbYm7kJu02EuRLXPqMjB_7JLG8F6o3nEo32AQCVRfpx8roZykiDjKkrzlKNUw==)
4. [weightliftcalculator.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFh7WkwGJ4fhVE18QKOhXmbJ2Nt652GdTqFTc6Qj9Y-eo9aL69TYb6qHM0nroPJaI9aq3CalfETVaDA0oDDB4W6gwgHjunW0XMQCxGc3nn7pF4TV490VxJ4USpuogXS4kjYbwrT7YLgOmIRTQeZZ6bwmiK_9bUc)
5. [concalculator.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHnMUwkN75OKTKXbLjxYXjIcRVsrmnp3Pvi-6yI-szguZp1KulVW0BPSA7QGOIWxYoUsS0_u4JCR9PT03iGRrzH2AxdUfnPM0iwY-vQC4jxCL--EBCc7NKZ6ZVMDmeMwik=)
6. [calculatorkaro.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE20uVonVb19FmCzN3UEJgxgnWM_MKdM0BsK-yYI5QflLerDASZA1jcDQizT7A61CpQQ62k16jZrCtJRVeh2hpIRUBxdvjYnE0wCj43UX8MYYQobcPdaoyrrijOgXZHRrjA)
7. [tommyodland.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFEy4DDO-pKtx-wUlG46itSofXSeNqucbfQ_RTIu7YDV7fMOpOmUJkz7GdYU8qLw4zdgnhSRCRcEEEHHeZrZq9UOd4EGhGweJbGzfuY7cgw9rc44j0CrvjFG_9Adi1XUEno1XNU4w0x-wAv7KsJA2MjwViII6yjG174V1vtqSLldY8O7Clc2BKNMfxM413YR3SP4U4=)
8. [dotscalculator.online](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHPIgrZoudhDcBm83jRV9MVtvCyiBzONUOq2zz-lnAUijlLWxkq3ThxLGqs4hakHMFUFLTCcsBtPHTZZdU2TWaRXk4RqSQcPw21D1wy60xvrtQC4iM=)
9. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF4amp1vcdkqL8Ye28kswmE6pTOoS0ucLZ0SuOq6zvfnBz0kYvMeGuOsLTbaet6-bVG3tLTZ5OkLLI95s0STfCmnUhBZsn9mQTNLYdsUVTDuOswyjrkrynD4_iGVJoVWroW5XXHpKmAD-iV1289GcnTCu8dwJkdhvkFqas2QrPmez-UKFlIFQ==)
10. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFW1gdPsZ_QlcGX3QmUSwfhAXM0-bqqKBIi0SGym0temS05O6HeX0fFWh5GOO_snt1eK9b5lJFwwVwn3OqG6Lprm_dv3igwiSZjHltEZRVQg59PCKZlw_SBNDV-_sWy3PDBrQ==)
11. [inngest.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHYZROJ5KYQH04nlZE25WwDGYA8FdhIMr0eTO8R2lrLx76xBiR0OqFw-Q7FGFZNgwooMuDT71jlL9d52qK4c_pvaaVvQjivRABKNB3gqUgqRhvzNX-vtsapdBa8jEB9NSkokQE9o-x6Vg6jJIwh5KZIhUhMHypZ3IqR_zVS)
12. [maxrep.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEndY-glLzCFUvbLvtEOQeM2_6Ri_6gursUDz41lFUrknRlKm68sDRg14vZ0PY0MZK3HzylYm1NVYN55aqaysLqbqKqeq4pZQAv1EcwKqKSQZrWQ4BnEkn-7hfi)
13. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEuiVjNP8a_2Wy_Q7CdV5gG3RbG90DiXd57GSkRjUZs51wzzLAL2zHCd3HlsLCZXmAukmfGosRwUconSgI5rX7ep0RrqCAgsV343sQ3z6AUlMadsyRPD4cfCN-dw4g_7JX7qUU_ZIWSYwGwVDyleDTA44UEX7OjABgw2BRB4CYXTqk7_uGaq2P1EA==)
14. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH0Dcb3RyNhCtQCx7DvIr_sZTbt_ajKFm8r7slbiJWv_yfDaRxwuI0jopjIj8BY_buh3YBPDUhCv5rNr8SXj_Om0TGftVaKmj2HNPuwFALhZNRZdsQLszNw_HjQHua6jumhTAGE349HMn-m4JP8JlVKK36AKcANDR2nIBd6rcX9vCTxqlsMGKTVVRBI95lHl5NSceFDuPQeMscXhqkX)
15. [observablehq.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFJvcLdLKKl_OXZNlQgNNScSyfgVYz8bY4JjuoJS3yLV4OIsAs_Q2RbdmAbvNrYCpKcWwnI2b_k9Ir-Vw3zGRgQIgxk3iL2vq7KLqdFttqbgbpvy4odab75wrXkqq_cpMb1g-nJYe2O)
16. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGQPfcD9iOt-QP0MFTYyaoK_QdUnbFQc27wslphd78wPgzBllxp5VTzylLvVdbHcmKO6nMfg95xQethPLJKxdZ6bAXJrCDzp4PRALZnBDByZUt-cRgAVMaX)
17. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE070qxe506jgkm3C13_9atgan5SqA2VPbZgtK2n98J2sGJNpON6ls_hghsn8afm4h9-a4yFgkksUkkB8FrLPqqrL2ExUpuOh-isFbiU_UDI-BNzCK5LL-1si30aHkNyBMgzteRlmipU3SngHS3xZUnlNHFu0uKt9q7oyBQ2CiTbL8jfRNQk27HjnLU1bXuEUckWespaCOUDkUY_pUXg-t3kSCg2Q==)
18. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFsu__lJbmJuvhk-VLbDYytb7A9po-u3RiOr8oWpfKNTpgV4eYQvWEwPgs_bTQRx5xXJcmQvN6OD-CzrO9g3afBO2IJIkMvrgUKQIvpkTDGdlSF9qhcGywth6xbYg9Ve-fPXSwlgkdZ4A==)
19. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEij_646BOCADdMgWjEp2prdVNzI0dmf2SvQPizhz8t44E5Zu-6Qc4eJO4sYNMfx8i4Z-z-GolOlJnLP2J600J1rkRMnwed0gCcfI4o0ggABeDpjRgPQPYwFWpIkxH74nl8uSiepxqwuv0mNq5Hyk3w1wR_Cs0hpE4fsm9Qu5UaUvnI3dSg0y_aqo61NN3kmm3a3j2wBoTqktnm)
20. [heptapod.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGSUhtnCQkL1LUNQA6soU9-5IgPm7g_Hk-gXviDBsw5aSxYqecH_7eloU7vc7OCJKnxyRHVe1ndpvULStuoaNxDx7gxKR-xQ-Yj4LmGBscMFSgQXs5JjZnor3UNoLPTzq9n818U7I_DDd77vr5URyI=)
21. [google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEswHVYZG66TF0f2auh3ZGH8khieDvvYS8LN3wNzdkdzHZIcVQaxNLHJHyGZ8b3G0FD9OYfj00lwtf5b0vjBxerOCrEq99pUgrrVNZLGNg35I_RXzh_05pWTN56-hNpwbfSsIqn0f3rnloE7e8rhA==)
22. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGj8LTn5UuXTvZFiV4K7whdJnBpSeKENI9RbUSNeKzNG5OjOUEiMpRb4mtdlvFEtZKU6d7DRsZGzvjV0ubhwq4H080xmCXU61c8rW23nYLxHVkJlF2UFu2aXB_3hQ015LP2_4Sebp1CDoo-5y54rg6CRUMshqz06GyTI8OvtloifkMg26QithdoT2-52eb8rHkia6KVnVHqsf8ZVfTJ6GnGL3gmM1KttSjw-g==)

# Domain Reference for evo-powerlifting-dots-formula

**Responsibility**: Domain knowledge: DOTS formula definition, male/female coefficients, valid input handling (negative best lifts, blank values, Mx sex category mapping to male coefficients), required columns from OpenPowerlifting schema (Name, Sex, BodyweightKg, Best3SquatKg, Best3BenchKg, Best3DeadliftKg), and precision requirements (3 decimal places).

**Key functions to implement**: get_dots_coefficients, build_totalkg_excel_formula, build_dots_excel_formula, get_required_columns

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
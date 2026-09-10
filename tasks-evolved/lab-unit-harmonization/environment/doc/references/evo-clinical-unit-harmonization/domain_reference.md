# Domain Reference for evo-clinical-unit-harmonization

**Responsibility**: Define analyte-specific conversion factors, physiological range thresholds for US and SI units, implement boundary-based auto-detection algorithm, and provide per-analyte harmonization functions that convert values outside expected US ranges using appropriate conversion factors.

**Key functions to implement**: get_analyte_config, detect_and_convert_value, harmonize_column, build_conversion_registry, harmonize_all_features

---

## 1. Complete Reference of US Conventional Units and Conversion Factors


The harmonization of a clinical dataset requires an exact mapping of the biological analyte to its respective conventional unit, SI unit, and the mathematical constant governing their relationship. The conversion factor (CF) bridges gravimetric units and molar units based on the molecular weight (MW) of the analyte [cite: 1].

The mathematical relationship is defined as:
\[ \text{SI Unit} = \text{US Conventional Unit} \times \text{Conversion Factor (CF)} \]
\[ \text{US Conventional Unit} = \text{SI Unit} \div \text{Conversion Factor (CF)} \]

### 1.1 CKD-Relevant Analytes: Physiological Ranges and Conversion Factors


The following delineates the critical analytes present in comprehensive CKD panels (often expanding to 62+ features in machine learning datasets). The ranges provided reflect both the normal physiological baseline and the extended pathological ranges plausibly observed in advanced CKD, End-Stage Renal Disease (ESRD), or Acute Kidney Injury (AKI) [cite: 3, 4].

#### 1.1.1 Renal Function Biomarkers


*   **Serum Creatinine (SCr):**
    *   **US Unit:** mg/dL
    *   **SI Unit:** µmol/L
    *   **Clarification on Conversion Factor:** The user query asks whether the factor is 0.0113 or 88.4. Both are correct depending on the direction of conversion. The molecular weight of creatinine is 113.12 g/mol. To convert from mg/dL to µmol/L, multiply by 88.4 [cite: 5, 6]. To convert from SI (µmol/L) back to US Conventional (mg/dL), you *divide* by 88.4, which is mathematically equivalent to multiplying by 0.0113 [cite: 5, 6].
    *   **Normal Range (US):** 0.6 – 1.2 mg/dL [cite: 7].
    *   **Pathological Range (CKD):** 1.3 – 15.0+ mg/dL (Values above 20 mg/dL are exceedingly rare but possible in untreated ESRD).

*   **Blood Urea Nitrogen (BUN):**
    *   **US Unit:** mg/dL
    *   **SI Unit:** mmol/L (Often reported internationally simply as "Urea")
    *   **Conversion Factor:** To convert BUN (mg/dL) to Urea (mmol/L), multiply by 0.357 [cite: 8]. To convert Urea (mmol/L) to BUN (mg/dL), divide by 0.357 (or multiply by 2.8) [cite: 5, 9]. This factor accounts for the fact that BUN measures only the nitrogen content (MW 28), whereas SI measures the whole urea molecule [cite: 8, 10].
    *   **Normal Range (US):** 7 – 20 mg/dL [cite: 8].
    *   **Pathological Range (CKD):** 21 – 150+ mg/dL (Uremic syndrome typically manifests severely at >100 mg/dL) [cite: 8].

*   **Estimated Glomerular Filtration Rate (eGFR):**
    *   **Unit:** mL/min/1.73m²
    *   **Conversion:** eGFR is a standardized calculated metric globally; no unit conversion is required.
    *   **Normal Range:** > 90 mL/min/1.73m² [cite: 3, 11].
    *   **Pathological Range:** 0 – 89 mL/min/1.73m² (CKD stages 2 through 5; <15 indicates kidney failure/ESRD) [cite: 4, 11].

#### 1.1.2 Proteins and Metabolites


*   **Albumin (Serum):**
    *   **US Unit:** g/dL
    *   **SI Unit:** g/L
    *   **Conversion Factor:** Multiply g/dL by 10 to get g/L [cite: 1, 6]. Multiply g/L by 0.1 to get g/dL [cite: 5].
    *   **Normal Range (US):** 3.5 – 5.0 g/dL [cite: 12, 13].
    *   **Pathological Range:** 1.5 – 3.4 g/dL (Hypoalbuminemia is common in nephrotic syndrome and malnutrition) [cite: 14, 15].

*   **Total Protein:**
    *   **US Unit:** g/dL
    *   **SI Unit:** g/L
    *   **Conversion Factor:** Multiply g/dL by 10 to get g/L [cite: 6, 16].
    *   **Normal Range (US):** 6.0 – 8.3 g/dL.
    *   **Pathological Range:** 4.0 – 10.0 g/dL.

*   **Uric Acid:**
    *   **US Unit:** mg/dL
    *   **SI Unit:** µmol/L
    *   **Conversion Factor:** Multiply mg/dL by 59.48 to get µmol/L [cite: 17]. Multiply µmol/L by 0.0168 to get mg/dL.
    *   **Normal Range (US):** 2.5 – 8.0 mg/dL [cite: 17].
    *   **Pathological Range:** 8.1 – 18.0 mg/dL (Hyperuricemia exacerbates CKD and causes gout) [cite: 14, 17].

*   **Bilirubin (Total):**
    *   **US Unit:** mg/dL
    *   **SI Unit:** µmol/L
    *   **Conversion Factor:** Multiply mg/dL by 17.1 to get µmol/L [cite: 6, 16]. Multiply µmol/L by 0.0585 to get mg/dL [cite: 18].
    *   **Normal Range (US):** 0.1 – 1.2 mg/dL [cite: 13].
    *   **Pathological Range:** 1.3 – 30.0+ mg/dL (Hepatic impairment).

#### 1.1.3 Electrolytes and Minerals


A critical pitfall involves the equivalency of mEq/L and mmol/L. **For monovalent ions (valency of 1) such as Sodium (Na+), Potassium (K+), Chloride (Cl-), and Bicarbonate (HCO3-), 1 mEq/L is exactly equivalent to 1 mmol/L** [cite: 6, 16]. No conversion is necessary. However, for divalent ions like Calcium (Ca2+) and Magnesium (Mg2+), the units diverge. In the US, however, Ca and Mg are typically reported in mg/dL, avoiding the mEq/L confusion entirely [cite: 2, 16].

*   **Sodium (Na), Potassium (K), Chloride (Cl), Bicarbonate (HCO3):**
    *   **US Unit:** mEq/L (numerically identical to SI mmol/L) [cite: 6, 16].
    *   **Pathological Ranges:**
        *   Na: 110 – 160 mEq/L (Normal: 135-145) [cite: 19].
        *   K: 2.0 – 8.0 mEq/L (Normal: 3.5-5.0. Hyperkalemia > 5.5 is a life-threatening CKD complication) [cite: 14, 20].
        *   Cl: 80 – 120 mEq/L (Normal: 96-106) [cite: 7].
        *   HCO3: 10 – 40 mEq/L (Normal: 22-29. Metabolic acidosis < 21 is common in CKD) [cite: 7, 14].

*   **Calcium (Total):**
    *   **US Unit:** mg/dL
    *   **SI Unit:** mmol/L
    *   **Conversion Factor:** Multiply mg/dL by 0.25 to get mmol/L [cite: 5, 6]. Multiply mmol/L by 4 to get mg/dL [cite: 5].
    *   **Normal Range (US):** 8.4 – 10.6 mg/dL [cite: 7].
    *   **Pathological Range:** 5.0 – 14.0 mg/dL.

*   **Phosphorus / Phosphate:**
    *   **US Unit:** mg/dL
    *   **SI Unit:** mmol/L
    *   **Conversion Factor:** Multiply mg/dL by 0.323 to get mmol/L [cite: 6]. Multiply mmol/L by 3.1 to get mg/dL [cite: 5].
    *   **Normal Range (US):** 2.5 – 4.5 mg/dL.
    *   **Pathological Range:** 4.6 – 12.0 mg/dL (Hyperphosphatemia drives CKD-Mineral and Bone Disorder) [cite: 14].

#### 1.1.4 Glycemic Indices


*   **Glucose (Fasting/Random):**
    *   **US Unit:** mg/dL
    *   **SI Unit:** mmol/L
    *   **Conversion Factor:** Multiply mg/dL by 0.0555 to get mmol/L [cite: 1, 6]. Multiply mmol/L by 18 to get mg/dL [cite: 5, 21].
    *   **Normal Range (US):** 70 – 99 mg/dL.
    *   **Pathological Range:** 40 – 1000+ mg/dL.

*   **HbA1c (Glycated Hemoglobin):**
    *   **US Unit:** % (NGSP Standard)
    *   **SI Unit:** mmol/mol (IFCC Standard)
    *   **Conversion Factor:** The conversion is not a simple multiplier. 
        *   SI (mmol/mol) = 10.929 × (US % - 2.15) [cite: 21, 22].
        *   US (%) = (SI mmol/mol × 0.0915) + 2.15 [cite: 23, 24].
    *   **Normal Range (US):** 4.0% – 5.6% [cite: 25, 26].
    *   **Pathological Range:** 5.7% – 18.0% [cite: 25].

#### 1.1.5 Lipids


*   **Cholesterol (Total, HDL, LDL):**
    *   **US Unit:** mg/dL
    *   **SI Unit:** mmol/L
    *   **Conversion Factor:** Multiply mg/dL by 0.0259 to get mmol/L [cite: 1, 5, 6]. Multiply mmol/L by 38.67 to get mg/dL [cite: 27, 28].
    *   **Normal Range (US):** < 200 mg/dL (Total) [cite: 7].
    *   **Pathological Range:** up to 600+ mg/dL.

*   **Triglycerides:**
    *   **US Unit:** mg/dL
    *   **SI Unit:** mmol/L
    *   **Conversion Factor:** Multiply mg/dL by 0.0113 (or precisely 0.01129) to get mmol/L [cite: 28, 29]. Multiply mmol/L by 88.57 to get mg/dL [cite: 27, 28].
    *   **Normal Range (US):** < 150 mg/dL.
    *   **Pathological Range:** up to 2000+ mg/dL.

#### 1.1.6 Hematology


*   **Hemoglobin (Hgb):**
    *   **US Unit:** g/dL
    *   **SI Unit:** g/L
    *   **Conversion Factor:** Multiply g/dL by 10 to get g/L [cite: 1, 6].
    *   **Normal Range (US):** 12.0 – 18.0 g/dL [cite: 20].
    *   **Pathological Range:** 5.0 – 20.0 g/dL (Anemia of CKD frequently pushes Hgb below 10 g/dL) [cite: 14].

*   **Red Blood Cell (RBC), White Blood Cell (WBC), Platelet Counts:**
    *   **Conventions:** The US conventionally uses scientific notation variants per microliter ($10^3/\mu L$ for WBC/Platelets, $10^6/\mu L$ for RBC). The SI system uses per Liter ($10^9/L$ for WBC/Platelets, $10^{12}/L$ for RBC) [cite: 6, 30]. 
    *   **Conversion Factor:** Numerically, these systems are identical. A WBC of $5.0 \times 10^3/\mu L$ is exactly $5.0 \times 10^9/L$ [cite: 6]. Auto-detection modules generally do not need to convert numerical values for these, only format the string representations of the units.

#### 1.1.7 Iron Studies


*   **Iron & Total Iron Binding Capacity (TIBC):**
    *   **US Unit:** µg/dL
    *   **SI Unit:** µmol/L
    *   **Conversion Factor:** Multiply µg/dL by 0.179 to get µmol/L [cite: 6, 31]. Multiply µmol/L by 5.587 to get µg/dL [cite: 6].
    *   **Normal Range (US):** 50 – 150 µg/dL [cite: 31].
    *   **Pathological Range:** 10 – 300 µg/dL.

*   **Ferritin:**
    *   **US Unit:** ng/mL
    *   **SI Unit:** µg/L or pmol/L
    *   **Conversion Factor:** ng/mL and µg/L are numerically identical (1:1) [cite: 6, 16]. 
    *   **Normal Range (US):** 11 – 300 ng/mL [cite: 13].
    *   **Pathological Range:** 5 – 2000+ ng/mL (Inflammation in CKD severely elevates ferritin).

---

## 2. Algorithm and Strategy for Automatic Unit Detection


To build an automated clinical unit harmonization module, deterministic programming must be paired with heuristic boundary logic. When aggregating databases from disparate institutions (where units may be missing or wrongly labelled [cite: 32]), a boundary-based statistical approach is best.

### 2.1 The Boundary-Based Auto-Detection Logic


For a given feature column representing a known analyte (e.g., Creatinine), we establish the absolute plausible physiological bounds in US units. Let this be $R_{US} = [L_{US}, U_{US}]$.

1.  **Direct Match:** If the value $X \in R_{US}$, the value is assumed to be in US units.
2.  **Conversion Match:** If $X \notin R_{US}$, but applying the SI-to-US conversion factor $C_{SI \to US}$ yields $(X \times C_{SI \to US}) \in R_{US}$, the value is assumed to be in SI units and is converted.
3.  **Ambiguity Handling:** If the transformed value and the raw value both fall outside plausible ranges, or if both fall *inside* due to overlapping ranges, the row is flagged for imputation or dropped.

### 2.2 Constructing the Discriminatory Thresholds


The viability of auto-detection relies on the absence of overlap between the pathological US range and the pathological SI range. 

**Highly Discriminatory Analytes (No Overlap):**
*   **Creatinine:** US Range = [0.2, 20.0]. SI Range = [17, 1700+]. Threshold: Any value > 25 is unambiguously in SI units (µmol/L) and must be multiplied by 0.0113 [cite: 5, 6].
*   **BUN:** US Range = [cite: 1]. SI Range = [0.7, 53]. While there is minor overlap at the low end (e.g., a value of 10 could be 10 mg/dL US or 10 mmol/L SI), high values discriminate well. Threshold: Values < 3.0 are almost certainly SI [cite: 8]. Values > 60 are likely US.
*   **Glucose:** US Range = [cite: 33]. SI Range = [1.6, 55]. Threshold: Values < 30 are unconditionally SI [cite: 5, 6].
*   **Hemoglobin:** US Range = [4.0, 20.0] g/dL. SI Range = [cite: 30] g/L. Threshold: Any value > 25 is SI (g/L) and must be divided by 10 [cite: 1, 6].

**Ambiguous Analytes (Significant Overlap):**
*   **Total Cholesterol:** US Range  mg/dL. SI Range [2.5, 10.0] mmol/L. Detection is relatively safe; values < 20 are SI [cite: 5, 6].
*   **HbA1c:** US % Range [4.0, 18.0]. SI mmol/mol Range [cite: 34]. Threshold: Any value > 20 is unambiguously IFCC mmol/mol [cite: 22, 25, 26].

### 2.3 Handling Edge Cases


What happens when a value falls in a zone where it could plausibly belong to either unit system?
*   *Example:* An Albumin value of `4.0`. Is this 4.0 g/dL (normal US) or 4.0 g/L (severely low SI)? 
*   *Solution 1 (Distributional Analysis):* Calculate the column mean or median. If the median of the entire column across an institution is 40.0, the unit is g/L [cite: 32]. 
*   *Solution 2 (Multivariate Correlation):* Check concurrent variables. If Albumin is ambiguously low, check Total Protein. If Total Protein is 6.5 (US), Albumin is likely US. 

---

### 4.1 Valency and Electrolyte Equivalence

A common mathematical error is assuming that `mEq/L` and `mmol/L` are always identical or always different. The relationship is governed by the valency (charge) of the ion:
*   $\text{mEq/L} = \text{mmol/L} \times \text{Valency}$
*   For Monovalent ions ($Na^+$, $K^+$, $Cl^-$, $HCO_3^-$), the valency is 1. Therefore, `mEq/L = mmol/L` [cite: 6].
*   For Divalent ions ($Ca^{2+}$, $Mg^{2+}$), the valency is 2. Therefore, 1 mmol/L = 2 mEq/L. **However**, the US standard for Calcium is `mg/dL`, not `mEq/L`. Therefore, mapping must strictly rely on the specific mg/dL to mmol/L conversion factor (mg/dL * 0.25 = mmol/L) [cite: 5, 6, 16].

### 4.2 Handling of Percentage-Based Measurements

Tests like Hematocrit (Hct) and HbA1c are represented as percentages (%). In SI conventions, Hct is represented as a volume fraction (L/L) where 45% = 0.45 L/L [cite: 6]. HbA1c, as noted earlier, requires an algebraically distinct conversion $(y = mx + b)$ rather than simple scaling, because the IFCC mmol/mol standard measures a chemically specific fraction of the hemoglobin compared to the older NGSP percentage [cite: 21, 22, 43].

### 4.3 Zero, Negative Values, and Outliers

Calculated fields (e.g., base excess) can be negative [cite: 6], but primary analyte concentrations (e.g., creatinine, glucose) absolutely cannot [cite: 32]. The module must assert that `if val <= 0: return np.nan` prior to processing, as a zero value in a denominator downstream (like an eGFR calculation or BUN/Creatinine ratio) will trigger division-by-zero runtime errors or yield infinite limits [cite: 10, 36].

## 5. CKD Feature Description Conventions and Abbreviations


Real-world EHR datasets (like MIMIC-III, MIMIC-IV, and UCI CKD datasets) utilize highly abbreviated column names [cite: 15, 45, 46, 47, 48]. To automate harmonization, your utility module should utilize a dictionary mapping these abbreviations to standard LOINC nomenclature.

| Common Abbreviation | Full Analyte Name | Standard US Unit |
| :--- | :--- | :--- |
| **sc**, **Scr**, **CR** | Serum Creatinine | mg/dL [cite: 14, 20, 45, 49, 50] |
| **bun**, **Bu**, **Urea** | Blood Urea Nitrogen | mg/dL [cite: 8, 14, 45, 46, 49] |
| **hgb**, **Hemo**, **Hb** | Hemoglobin | g/dL [cite: 14, 45, 46, 47] |
| **alb**, **Al** | Serum Albumin | g/dL [cite: 14, 45] |
| **ua**, **Uric** | Uric Acid | mg/dL [cite: 14] |
| **tp** | Total Protein | g/dL [cite: 49] |
| **glu**, **Su** | Glucose (Blood Sugar) | mg/dL [cite: 45, 49] |
| **wbc**, **Wbcc** | White Blood Cell Count | $10^3/\mu L$ [cite: 20, 45, 46, 50] |
| **rbc**, **Rbcc** | Red Blood Cell Count | $10^6/\mu L$ [cite: 20, 45] |
| **plt**, **Plt** | Platelet Count | $10^3/\mu L$ [cite: 50] |
| **sod**, **Na** | Sodium | mEq/L [cite: 20, 45, 46] |
| **pot**, **K** | Potassium | mEq/L [cite: 20, 45] |
| **bicarb**, **HCO3** | Bicarbonate | mEq/L [cite: 14, 20, 46] |
| **ca** | Calcium (Total) | mg/dL [cite: 14, 46] |
| **p**, **phos** | Phosphorus / Phosphate | mg/dL [cite: 14, 49] |
| **tc**, **Chol** | Total Cholesterol | mg/dL [cite: 14, 50] |
| **tg**, **Trig** | Triglycerides | mg/dL [cite: 50] |
| **ldlc**, **hdlc** | LDL / HDL Cholesterol | mg/dL [cite: 50] |
| **acr**, **uACR** | Urine Albumin-to-Creatinine Ratio | mg/g [cite: 11, 14, 51] |
| **sg** | Specific Gravity (Urine) | Unitless (Ratio) [cite: 45] |
| **egfr** | Estimated Glomerular Filtration Rate| mL/min/1.73m² [cite: 3, 11, 45] |

Building a robust `rename(columns=dict)` preprocessing step allows the module to standardize headers before attempting detection and conversion, ensuring scalability across different hospital systems.

---
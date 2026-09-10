# Skill Creation Plan

**Task**: Detect an exoplanet transit period in a TESS light curve by filtering data, removing stellar variability, and running a transit periodogram.

**Rationale**: The task naturally splits into light curve preprocessing/detrending and transit period detection; these are distinct concerns with reusable utilities.

**Number of skills**: 2

---

## Skill 1: evo-tess-lightcurve-preprocessing

**Description**: Load TESS text-format light curves and prepare them for transit detection by applying quality flag filtering, NaN removal, outlier rejection, normalization, and Savitzky-Golay flattening to remove stellar variability.

**Responsibility**: Data ingestion, cleaning, and stellar-activity detrending to produce a flattened, normalized light curve ready for periodogram analysis.

**Key functions**: `load_tess_lightcurve`, `filter_quality_and_nans`, `remove_outliers`, `estimate_rotation_period`, `flatten_lightcurve`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-tess-lightcurve-preprocessing/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-transit-period-detection

**Description**: Run BLS and/or Transit Least Squares (TLS) periodograms on a cleaned, flattened light curve to identify the exoplanet orbital period, and write the result to a properly formatted output file.

**Responsibility**: Periodogram-based transit period detection and formatted output of the best-fit period.

**Key functions**: `detect_transit_tls`, `detect_transit_bls`, `save_period`

**Depends on**: evo-tess-lightcurve-preprocessing


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-transit-period-detection/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.

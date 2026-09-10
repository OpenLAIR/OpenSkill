# Domain Reference for evo-reflow-handbook-parser

**Responsibility**: Parse the handbook PDF and return structured dictionaries of all process thresholds, formulas, and compliance limits needed by downstream analysis. No CSV processing or computation.

**Key functions to implement**: extract_pdf_text, parse_preheat_params, parse_tal_params, parse_peak_temp_params, parse_conveyor_speed_params, get_all_handbook_params

---

## 1. PDF Text Extraction in Python 3.11


Automated parsing of technical handbooks—which dictate the operational parameters of reflow soldering machines—presents a significant computational challenge. Technical PDFs frequently embed data in complex layouts, utilizing tables, multi-column text, and vector graphics.

## 2. Reflow Soldering Thermal Profile Domain Knowledge


The reflow soldering process is a highly sensitive thermodynamic operation designed to mechanically and electrically bond surface-mount technology (SMT) components to printed circuit boards (PCBs). This process is governed by stringent international standards, most notably the **IPC/JEDEC J-STD-020** standard for Moisture/Reflow Sensitivity Classification [cite: 9, 10]. The standard delineates the process into four primary zones: Preheat, Soak (Thermal Equalization), Reflow (Time Above Liquidus), and Cooling [cite: 11, 12].
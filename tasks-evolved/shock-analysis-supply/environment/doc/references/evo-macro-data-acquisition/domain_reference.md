# Domain Reference for evo-macro-data-acquisition

**Responsibility**: Download PWT Excel file and extract rnna, emp, labsh, hc for Georgia; scrape/download IMF WEO real GDP level (NGDP_R) and growth rate (NGDP_RPCH) for 2000-2027; download ECB CFC data for Georgia; populate sheets PWT, WEO_Data, and CFC data in test-supply.xlsx

**Key functions to implement**: download_pwt_data, extract_pwt_georgia_variables, fetch_imf_weo_data, fetch_ecb_cfc_data, populate_data_sheets

---

## 1. Database Structures and Programmatic Acquisition


Constructing a macroeconomic model for a small open economy requires harmonized historical data. Three primary databases are utilized: the Penn World Table (PWT), the IMF World Economic Outlook (WEO), and the ECB Statistical Data Warehouse (SDW).

### 1.1 Penn World Table (PWT) Database Structure


The Penn World Table (currently version 10.x) provides purchasing power parity (PPP) adjusted national accounts data designed for cross-country comparisons of relative income, output, inputs, and productivity [cite: 1, 2]. For Georgia, the exact country identifier is the ISO 3166-1 alpha-3 code **GEO** [cite: 1, 3]. 

The exact variable names and codes required for a Cobb-Douglas production function are as follows:

| Variable Code | Description | Application in Modeling |
| :--- | :--- | :--- |
| **rnna** | Capital stock at constant 2017 national prices (in millions of 2017 USD). | This is the absolute level of the capital stock (\(K\)) used in the production function [cite: 1, 4]. |
| **rkna** | Capital services at constant 2017 national prices (2017 = 1). | This is an index of capital services, suitable for growth accounting but less optimal for level-based Cobb-Douglas estimations [cite: 1, 4]. |
| **emp** | Number of persons engaged (in millions). | Represents the labor input (\(L\)) [cite: 1, 3]. |
| **labsh** | Share of labor compensation in GDP at current national prices. | Used to calibrate the labor share (\(1-\alpha\)) [cite: 4, 5]. |
| **hc** | Human capital index. | Based on years of schooling and returns to education, used to augment raw labor into effective labor (\(L \cdot hc\)) [cite: 1]. |

**Metadata Sheet**: The PWT dataset includes a "Data Information" or metadata sheet. This sheet defines the concepts, details the construction of the data variables, and provides a binary or categorical flag indicating whether a specific data point (like relative price data or exchange rates) is benchmarked, interpolated, or extrapolated [cite: 1, 6]. It allows researchers to gauge the statistical capacity and reliability of the data for specific countries.

**URL Structure and Download**: The PWT data is hosted by the Groningen Growth and Development Centre (GGDC). Programmatic downloads can directly target the Excel or Stata files hosted on the DataverseNL repository or the GGDC URL endpoint. The URL structure typically follows `https://www.rug.nl/ggdc/productivity/pwt/` for the landing page [cite: 7], with direct file downloads routed through their specific release subdirectories.

### 1.2 IMF World Economic Outlook (WEO) Database


The IMF WEO database is updated biannually (April and October) and contains macroeconomic projections for up to five years into the future [cite: 8, 9]. Starting with recent vintages, the IMF transitioned to a new Data Portal, replacing three-digit IFS codes with standard three-letter ISO codes (e.g., **GEO** for Georgia) [cite: 10].

| WEO Subject Code | Subject Descriptor | Unit |
| :--- | :--- | :--- |
| **NGDP_R** | Gross domestic product, constant prices | Billions of national currency [cite: 11, 12]. |
| **NGDP_RPCH** | Gross domestic product, constant prices | Percent change (Annual year-on-year) [cite: 11, 12]. |

**Format and Access**: The traditional WEO data format provided bulk downloads in tab-separated values (TSV) disguised with an `.xls` extension, though the modern IMF Data Portal provides true CSV and SDMX-JSON APIs [cite: 10, 13]. Programmatically, researchers can use Python to parse the CSV file, filter for `WEO Country Code == 'GEO'`, and pivot the data to create a time-series panel [cite: 13].

### 1.3 ECB Statistical Data Warehouse (SDW)


While the ECB primarily focuses on the Euro Area, it maintains an International Data Cooperation (IDCM) dataset containing national accounts for non-EU countries, including Georgia [cite: 14, 15].

**Data Series Key**: In the ECB SDW SDMX format, series keys are concatenated dimensions. For "Consumption of fixed capital" (CFC), the ESA2010 transaction code is **P51C** [cite: 16]. The annual series key for Georgia's CFC follows the pattern:
`IDCM.A.N.GE.W2.S1.S1.D.P51C.N1G._T._Z.XDC.V.N` [cite: 15, 17, 18].

*   `IDCM`: International Data Cooperation dataset [cite: 15].
*   `A`: Annual frequency.
*   `GE`: Georgia (Eurostat/ECB 2-letter geographical code).
*   `P51C`: Consumption of fixed capital [cite: 16].
*   `XDC`: Domestic currency.

**Units**: The data is reported in domestic currency (Georgian Lari - GEL) at current prices [cite: 18, 19].
# Domain Reference for evo-usgs-flood-detection

**Responsibility**: End-to-end pipeline: parse station list file (preserving leading zeros), fetch daily values and historical statistics via dataretrieval.nwis, compute flood-day counts via percentile threshold comparison, and write filtered results to CSV.

**Key functions to implement**: load_stations, get_station_flood_thresholds, detect_floods_for_site, run_flood_detection_pipeline

---

## USGS dataretrieval Python Package (v1.0.10) API


The `dataretrieval` package interfaces directly with USGS web services, formatting complex REST API queries, handling JSON or RDB (Relational Database) responses, and returning highly performant `pandas` DataFrames [cite: 2, 7]. Understanding the specific syntax, imports, and return types of the v1.0.10 API is fundamental to pipeline construction.

## Defining "Flooding" from Streamflow Data


Detecting a "flood" programmatically requires defining what constitutes flood-level flow. In operational hydrology, this definition varies based on available data and the specific requirements of the forecasting agency.

## Reading a Stations List File


In operational pipelines, target stations are rarely hardcoded. They are read from external configuration files, such as `michigan_stations.txt`.

## Pipeline Development and Automation Patterns


To transition from abstract definitions to a resilient data processing pipeline, the code must handle scale, network volatility, index alignment, and output generation.

## Comprehensive Code Implementation


Below is the complete, modular, and copy-pasteable Python script integrating all theoretical concepts discussed thus far.

```python
import pandas as pd
from dataretrieval import nwis
import logging
from typing import List

## Common Pitfalls and Troubleshooting


Architecting highly dependable integrations with external APIs exposes developers to several recurring obstacles. Below are the most critical pitfalls specific to this stack and their respective mitigations.
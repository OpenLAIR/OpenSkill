from __future__ import annotations


def map_task_ranges():
    years = ['H', 'I', 'J', 'K', 'L']
    exports_rows = list(range(12, 18))
    imports_rows = list(range(19, 25))
    gdp_rows = list(range(26, 32))
    ratio_rows = list(range(35, 41))
    summary_rows = {
        'min': 43,
        'max': 44,
        'median': 45,
        'mean': 46,
        'p25': 47,
        'p75': 48,
        'weighted_mean': 50,
    }
    source_row_map = {
        12: 26, 13: 21, 14: 22, 15: 24, 16: 23, 17: 25,
        19: 33, 20: 28, 21: 29, 22: 31, 23: 30, 24: 32,
        26: 40, 27: 35, 28: 36, 29: 38, 30: 37, 31: 39,
    }
    return {
        'year_cols': years,
        'exports_rows': exports_rows,
        'imports_rows': imports_rows,
        'gdp_rows': gdp_rows,
        'ratio_rows': ratio_rows,
        'summary_rows': summary_rows,
        'source_row_map': source_row_map,
    }


def build_two_key_lookup_formula(task_row: int, year_col: str) -> str:
    src_row = map_task_ranges()['source_row_map'][task_row]
    # Workbook-specific stable INDEX+MATCH against the exact source row and year header.
    return f'=INDEX(Data!$I${src_row}:$M${src_row},1,MATCH({year_col}$9,Data!$I$4:$M$4,0))'


def build_lookup_formula_map() -> dict[str, str]:
    ranges = map_task_ranges()
    formula_map: dict[str, str] = {}
    for col in ranges['year_cols']:
        for row in ranges['exports_rows'] + ranges['imports_rows'] + ranges['gdp_rows']:
            formula_map[f'{col}{row}'] = build_two_key_lookup_formula(row, col)
    return formula_map


def build_net_exports_pct_formula(ratio_row: int, year_col: str) -> str:
    export_row = 12 + (ratio_row - 35)
    import_row = 19 + (ratio_row - 35)
    gdp_row = 26 + (ratio_row - 35)
    return f'=IF(OR({year_col}{gdp_row}="",{year_col}{gdp_row}=0),"",({year_col}{export_row}-{year_col}{import_row})/{year_col}{gdp_row})'


def build_summary_stat_formulas(year_col: str) -> dict[str, str]:
    rows = map_task_ranges()['summary_rows']
    data_range = f'{year_col}$35:{year_col}$40'
    return {
        f'{year_col}{rows["min"]}': f'=MIN({data_range})',
        f'{year_col}{rows["max"]}': f'=MAX({data_range})',
        f'{year_col}{rows["median"]}': f'=MEDIAN({data_range})',
        f'{year_col}{rows["mean"]}': f'=AVERAGE({data_range})',
        f'{year_col}{rows["p25"]}': f'=PERCENTILE.INC({data_range},0.25)',
        f'{year_col}{rows["p75"]}': f'=PERCENTILE.INC({data_range},0.75)',
    }


def build_weighted_mean_formula(year_col: str) -> str:
    ratios = f'{year_col}$35:{year_col}$40'
    weights = f'{year_col}$26:{year_col}$31'
    return f'=IF(SUM({weights})=0,0,SUMPRODUCT({ratios},{weights})/SUM({weights}))'


def build_formula_map() -> dict[str, str]:
    ranges = map_task_ranges()
    formula_map = build_lookup_formula_map()
    for col in ranges['year_cols']:
        for row in ranges['ratio_rows']:
            formula_map[f'{col}{row}'] = build_net_exports_pct_formula(row, col)
        formula_map.update(build_summary_stat_formulas(col))
        formula_map[f'{col}{ranges["summary_rows"]["weighted_mean"]}'] = build_weighted_mean_formula(col)
    return formula_map

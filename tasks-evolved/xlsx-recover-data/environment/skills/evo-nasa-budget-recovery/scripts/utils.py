"""
evo-nasa-budget-recovery: Domain logic for recovering missing ??? values.
"""
import math
import sys
sys.path.insert(0, '/app/environment/skills/evo-excel-io/scripts')
from excel_io import (
    load_workbook_safe, find_missing_cells, get_cell_value_safe,
    write_recovered_value, save_workbook_safe, is_numeric, is_missing
)


def solve_row_with_one_unknown(ws, row, data_cols, total_col):
    total_val = get_cell_value_safe(ws, row, total_col)
    if is_missing(total_val):
        known_sum = 0
        all_known = True
        for c in data_cols:
            v = get_cell_value_safe(ws, row, c)
            if is_numeric(v):
                known_sum += v
            else:
                all_known = False
                break
        if all_known:
            if isinstance(known_sum, float) and known_sum == int(known_sum):
                known_sum = int(known_sum)
            return (total_col, known_sum)
        return None
    if not is_numeric(total_val):
        return None
    unknowns = []
    known_sum = 0
    for c in data_cols:
        v = get_cell_value_safe(ws, row, c)
        if is_numeric(v):
            known_sum += v
        elif is_missing(v):
            unknowns.append(c)
    if len(unknowns) == 1:
        recovered = total_val - known_sum
        if isinstance(recovered, float) and recovered == int(recovered):
            recovered = int(recovered)
        return (unknowns[0], recovered)
    return None


def recover_yoy_value(budget_ws, yoy_ws, yoy_row, yoy_col):
    # YoY row 4=FY2016, budget row 5=FY2016, row 4=FY2015
    budget_current_row = yoy_row + 1
    budget_prev_row = yoy_row
    cur = get_cell_value_safe(budget_ws, budget_current_row, yoy_col)
    prev = get_cell_value_safe(budget_ws, budget_prev_row, yoy_col)
    if is_numeric(cur) and is_numeric(prev) and prev != 0:
        return round((cur - prev) / prev * 100, 2)
    return None


def recover_budget_from_yoy(budget_ws, yoy_ws, budget_row, budget_col):
    yoy_row = budget_row - 1
    yoy_val = get_cell_value_safe(yoy_ws, yoy_row, budget_col)
    prev_val = get_cell_value_safe(budget_ws, budget_row - 1, budget_col)
    if is_numeric(yoy_val) and is_numeric(prev_val):
        recovered = prev_val * (1 + yoy_val / 100)
        return round(recovered)
    return None


def recover_share_value(budget_ws, shares_ws, share_row, share_col):
    budget_val = get_cell_value_safe(budget_ws, share_row, share_col)
    total_val = get_cell_value_safe(budget_ws, share_row, 11)
    if is_numeric(budget_val) and is_numeric(total_val) and total_val != 0:
        return round(budget_val / total_val * 100, 2)
    return None


def recover_growth_analysis(wb):
    gs = wb['Growth Analysis']
    bs = wb['Budget by Directorate']
    results = []
    for col in range(2, 11):
        # FY2019 Budget (row 5)
        if is_missing(get_cell_value_safe(gs, 5, col)):
            bv = get_cell_value_safe(bs, 8, col)
            if is_numeric(bv):
                results.append(('Growth Analysis', 5, col, bv))
        # 5-Year Change (row 7) = FY2024 - FY2019
        if is_missing(get_cell_value_safe(gs, 7, col)):
            fy19 = get_cell_value_safe(gs, 5, col)
            if is_missing(fy19):
                fy19 = get_cell_value_safe(bs, 8, col)
            fy24 = get_cell_value_safe(gs, 6, col)
            if is_numeric(fy19) and is_numeric(fy24):
                ch = fy24 - fy19
                if isinstance(fy19, int) and isinstance(fy24, int):
                    ch = int(ch)
                results.append(('Growth Analysis', 7, col, ch))
        # Avg Annual (row 8) = avg of FY2019-FY2024
        if is_missing(get_cell_value_safe(gs, 8, col)):
            vals = []
            for r in range(8, 14):
                bv = get_cell_value_safe(bs, r, col)
                if is_numeric(bv):
                    vals.append(bv)
            if len(vals) == 6:
                results.append(('Growth Analysis', 8, col, round(sum(vals)/6, 1)))
        # CAGR (row 4)
        if is_missing(get_cell_value_safe(gs, 4, col)):
            fy19 = get_cell_value_safe(gs, 5, col)
            if is_missing(fy19):
                fy19 = get_cell_value_safe(bs, 8, col)
            fy24 = get_cell_value_safe(gs, 6, col)
            if is_numeric(fy19) and is_numeric(fy24) and fy19 > 0:
                cagr = round(((fy24/fy19)**(1/5) - 1)*100, 2)
                results.append(('Growth Analysis', 4, col, cagr))
    return results


def run_recovery_pipeline(input_path, output_path):
    wb = load_workbook_safe(input_path)
    missing = find_missing_cells(wb)
    print(f"Found {len(missing)} missing cells")
    bs = wb['Budget by Directorate']
    ys = wb['YoY Changes (%)']
    ss = wb['Directorate Shares (%)']
    data_cols = list(range(2, 11))
    for iteration in range(10):
        resolved = 0
        # Budget row sums
        for row in range(4, 14):
            result = solve_row_with_one_unknown(bs, row, data_cols, 11)
            if result:
                col, val = result
                if is_missing(get_cell_value_safe(bs, row, col)):
                    write_recovered_value(bs, row, col, val)
                    print(f"  Budget ({row},{col}) = {val}")
                    resolved += 1
        # Budget from YoY
        for row in range(4, 14):
            for col in data_cols + [11]:
                if is_missing(get_cell_value_safe(bs, row, col)):
                    val = recover_budget_from_yoy(bs, ys, row, col)
                    if val is not None:
                        write_recovered_value(bs, row, col, val)
                        print(f"  Budget from YoY ({row},{col}) = {val}")
                        resolved += 1
        # YoY percentages
        for row in range(4, 13):
            for col in range(2, 12):
                if is_missing(get_cell_value_safe(ys, row, col)):
                    val = recover_yoy_value(bs, ys, row, col)
                    if val is not None:
                        write_recovered_value(ys, row, col, val)
                        print(f"  YoY ({row},{col}) = {val}")
                        resolved += 1
        # Shares
        for row in range(4, 14):
            for col in range(2, 11):
                if is_missing(get_cell_value_safe(ss, row, col)):
                    val = recover_share_value(bs, ss, row, col)
                    if val is not None:
                        write_recovered_value(ss, row, col, val)
                        print(f"  Share ({row},{col}) = {val}")
                        resolved += 1
        # Growth
        for sn, r, c, v in recover_growth_analysis(wb):
            ws = wb[sn]
            if is_missing(get_cell_value_safe(ws, r, c)):
                write_recovered_value(ws, r, c, v)
                print(f"  Growth ({r},{c}) = {v}")
                resolved += 1
        print(f"  Iteration {iteration}: resolved {resolved}")
        if resolved == 0:
            break
    remaining = find_missing_cells(wb)
    if remaining:
        print(f"WARNING: {len(remaining)} unresolved")
        for m in remaining:
            print(f"  {m['sheet']} {m['coordinate']}")
    else:
        print("All recovered!")
    save_workbook_safe(wb, output_path)
    return wb

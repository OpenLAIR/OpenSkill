"""
Utility functions for the evo-protein-expression-analysis skill.

Populates an Excel workbook with proteomics computed values:
  1. 2D lookups for protein expression across samples (numeric values)
  2. AVERAGE / STDEV group statistics for Control vs Treated (numeric values)
  3. Log2 Fold Change and linear Fold Change (numeric values)

CRITICAL: All values are computed in Python and written as numeric floats.
openpyxl does NOT evaluate Excel formulas. If you write formula strings,
they will appear as None when read back with data_only=True.

Key domain notes:
  - Data is already log2-transformed.
  - Log2FC = Treated_Mean - Control_Mean
  - Fold Change = 2^(Log2FC)
  - Use sample standard deviation (statistics.stdev, i.e., ddof=1).
  - Setting cell.value preserves existing cell formatting (fill, font, border).
"""

import statistics
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


# ---------------------------------------------------------------------------
# Workbook I/O
# ---------------------------------------------------------------------------

def load_workbook_preserving(path):
    """Load an xlsx workbook preserving formulas and formatting.

    Uses data_only=False (default) to keep existing content intact.
    Does NOT set keep_vba=True since the task forbids macros.
    """
    return load_workbook(path, data_only=False, keep_vba=False)


def save_workbook_safely(wb, path):
    """Save workbook with informative error if path is locked."""
    try:
        wb.save(path)
    except PermissionError as e:
        raise PermissionError(
            f"Cannot save to {path} (file may be open in Excel): {e}"
        )


# ---------------------------------------------------------------------------
# Data index builder
# ---------------------------------------------------------------------------

def build_data_index(ws_data):
    """Build a nested dict {protein_id: {sample_name: float_value}} from the Data sheet.

    Data sheet layout:
      - Row 1: headers. Column A = "Protein_ID", columns D onward = sample names
      - Rows 2+: Column A = protein ID, columns D onward = expression values

    Returns a dict for O(1) lookup by protein_id and sample_name.
    """
    data_index = {}

    # Find the actual extent of sample columns in row 1
    # Column A=1 (Protein_ID), B=2 (Gene_Symbol), C=3 (Description), D=4+ (samples)
    sample_cols = {}  # {col_index: sample_name}
    for c in range(1, ws_data.max_column + 1):
        val = ws_data.cell(row=1, column=c).value
        if val is not None and c >= 4:
            sample_cols[c] = str(val).strip()

    # Build the index from data rows
    for r in range(2, ws_data.max_row + 1):
        protein_id = ws_data.cell(row=r, column=1).value
        if protein_id is None or str(protein_id).strip() == "":
            continue
        protein_id = str(protein_id).strip()
        data_index[protein_id] = {}
        for c, sample_name in sample_cols.items():
            val = ws_data.cell(row=r, column=c).value
            if val is not None:
                try:
                    data_index[protein_id][sample_name] = float(val)
                except (ValueError, TypeError):
                    pass  # Skip non-numeric values

    return data_index


# ---------------------------------------------------------------------------
# Group classification
# ---------------------------------------------------------------------------

def classify_group_columns(ws, group_row=9, start_col=3, end_col=12):
    """Return {'Control': [col_indices...], 'Treated': [...]} from labels in group_row.

    Reads text values in the specified row. Handles whitespace and case variations.
    Returns column indices (integers), not letters.
    """
    groups = {'Control': [], 'Treated': []}
    for c in range(start_col, end_col + 1):
        raw = ws.cell(row=group_row, column=c).value
        if raw is None:
            continue
        normalized = str(raw).strip().title()
        if normalized in groups:
            groups[normalized].append(c)

    if not groups['Control']:
        raise ValueError(
            f"No 'Control' labels found in row {group_row}, cols {start_col}-{end_col}."
        )
    if not groups['Treated']:
        raise ValueError(
            f"No 'Treated' labels found in row {group_row}, cols {start_col}-{end_col}."
        )
    return groups


# ---------------------------------------------------------------------------
# Step 1: Fill expression values
# ---------------------------------------------------------------------------

def fill_expression_values(ws_task, data_index,
                           protein_rows=None,
                           sample_cols=None,
                           sample_header_row=10,
                           protein_id_col=1):
    """Write numeric expression values into Task!C11:L20.

    For each target protein (col A, rows 11-20) and each sample (row 10, cols C-L),
    look up the expression value from data_index and write the float.

    Parameters
    ----------
    ws_task : Worksheet
        The Task sheet.
    data_index : dict
        {protein_id: {sample_name: float_value}} from build_data_index().
    protein_rows : range or list
        Rows containing target protein IDs (default 11-20).
    sample_cols : range or list
        Columns for sample expression values (default 3-12, i.e. C-L).
    sample_header_row : int
        Row in Task sheet containing sample names (default 10).
    protein_id_col : int
        Column containing protein IDs (default 1 = A).
    """
    if protein_rows is None:
        protein_rows = range(11, 21)
    if sample_cols is None:
        sample_cols = range(3, 13)  # C=3 through L=12

    for r in protein_rows:
        protein_id = ws_task.cell(row=r, column=protein_id_col).value
        if protein_id is None:
            continue
        protein_id = str(protein_id).strip()

        protein_data = data_index.get(protein_id, {})

        for c in sample_cols:
            sample_name = ws_task.cell(row=sample_header_row, column=c).value
            if sample_name is None:
                continue
            sample_name = str(sample_name).strip()

            val = protein_data.get(sample_name)
            if val is not None:
                ws_task.cell(row=r, column=c).value = val


# ---------------------------------------------------------------------------
# Step 2: Compute group statistics
# ---------------------------------------------------------------------------

def compute_group_stats(ws_task,
                        groups=None,
                        protein_rows=None,
                        stats_start_col=2,
                        control_mean_row=24,
                        control_stdev_row=25,
                        treated_mean_row=26,
                        treated_stdev_row=27):
    """Compute and write AVERAGE / STDEV statistics into B24:K27.

    Column B (col index 2) corresponds to the first protein (row 11);
    Column K (col index 11) corresponds to the last protein (row 20).

    For each protein, reads the expression values from the protein's row,
    splits by Control/Treated group columns, computes mean and sample stdev,
    and writes the numeric results.

    Parameters
    ----------
    ws_task : Worksheet
        The Task sheet (must already have expression values filled in rows 11-20).
    groups : dict or None
        {'Control': [col_indices...], 'Treated': [col_indices...]}
        If None, auto-detects from row 9.
    protein_rows : range or list
        Rows with target proteins (default 11-20).
    stats_start_col : int
        First column for statistics output (default 2 = B).
    """
    if protein_rows is None:
        protein_rows = range(11, 21)

    if groups is None:
        groups = classify_group_columns(ws_task, group_row=9, start_col=3, end_col=12)

    control_cols = groups['Control']
    treated_cols = groups['Treated']

    for i, r in enumerate(protein_rows):
        stats_col = stats_start_col + i

        # Gather numeric values for this protein from control columns
        ctrl_vals = []
        for c in control_cols:
            val = ws_task.cell(row=r, column=c).value
            if val is not None:
                try:
                    ctrl_vals.append(float(val))
                except (ValueError, TypeError):
                    pass

        # Gather numeric values for this protein from treated columns
        trt_vals = []
        for c in treated_cols:
            val = ws_task.cell(row=r, column=c).value
            if val is not None:
                try:
                    trt_vals.append(float(val))
                except (ValueError, TypeError):
                    pass

        # Control Mean (row 24)
        if ctrl_vals:
            ctrl_mean = statistics.mean(ctrl_vals)
            ws_task.cell(row=control_mean_row, column=stats_col).value = ctrl_mean
        else:
            ctrl_mean = None

        # Control StdDev (row 25) — sample standard deviation
        if len(ctrl_vals) >= 2:
            ctrl_stdev = statistics.stdev(ctrl_vals)
            ws_task.cell(row=control_stdev_row, column=stats_col).value = ctrl_stdev

        # Treated Mean (row 26)
        if trt_vals:
            trt_mean = statistics.mean(trt_vals)
            ws_task.cell(row=treated_mean_row, column=stats_col).value = trt_mean
        else:
            trt_mean = None

        # Treated StdDev (row 27) — sample standard deviation
        if len(trt_vals) >= 2:
            trt_stdev = statistics.stdev(trt_vals)
            ws_task.cell(row=treated_stdev_row, column=stats_col).value = trt_stdev


# ---------------------------------------------------------------------------
# Step 3: Compute fold changes
# ---------------------------------------------------------------------------

def compute_fold_changes(ws_task,
                         protein_rows=None,
                         fc_start_row=32,
                         log2_fc_col=3,
                         fold_change_col=4,
                         stats_start_col=2,
                         control_mean_row=24,
                         treated_mean_row=26):
    """Compute and write fold-change values into C32:D41.

    Row 32 corresponds to first protein (row 11) → stats column B.
    Row 41 corresponds to last protein (row 20) → stats column K.

    Column C = Log2 FC = Treated Mean − Control Mean
    Column D = Fold Change = 2^(Log2 FC)

    Parameters
    ----------
    ws_task : Worksheet
        The Task sheet (must already have statistics in rows 24-27).
    protein_rows : range or list
        Rows with target proteins (default 11-20).
    fc_start_row : int
        First row for fold change output (default 32).
    log2_fc_col : int
        Column for Log2 FC (default 3 = C).
    fold_change_col : int
        Column for linear Fold Change (default 4 = D).
    stats_start_col : int
        First column of statistics (default 2 = B).
    control_mean_row : int
        Row containing control means (default 24).
    treated_mean_row : int
        Row containing treated means (default 26).
    """
    if protein_rows is None:
        protein_rows = range(11, 21)

    for i, _ in enumerate(protein_rows):
        fc_row = fc_start_row + i
        stats_col = stats_start_col + i

        ctrl_mean = ws_task.cell(row=control_mean_row, column=stats_col).value
        trt_mean = ws_task.cell(row=treated_mean_row, column=stats_col).value

        if ctrl_mean is not None and trt_mean is not None:
            try:
                ctrl_mean_f = float(ctrl_mean)
                trt_mean_f = float(trt_mean)
                log2_fc = trt_mean_f - ctrl_mean_f
                fold_change = 2.0 ** log2_fc

                # Column C = Log2 Fold Change
                ws_task.cell(row=fc_row, column=log2_fc_col).value = log2_fc
                # Column D = Fold Change
                ws_task.cell(row=fc_row, column=fold_change_col).value = fold_change
            except (ValueError, TypeError):
                pass


# ---------------------------------------------------------------------------
# One-shot convenience function
# ---------------------------------------------------------------------------

def populate_protein_expression_task(path):
    """Apply all three steps to the protein_expression.xlsx file (in place).

    Steps:
      1. Look up expression values from Data sheet and write numeric values (C11:L20)
      2. Compute group statistics and write numeric values (B24:K27)
      3. Compute fold changes and write numeric values (C32:D41)

    All values are computed in Python and written as floats — openpyxl does NOT
    evaluate Excel formulas, so formula-based approaches would produce None
    when the file is read back with data_only=True.

    Returns the file path for convenience.
    """
    wb = load_workbook_preserving(path)

    # Validate required sheets exist
    required_sheets = ['Task', 'Data']
    for sheet_name in required_sheets:
        if sheet_name not in wb.sheetnames:
            raise ValueError(
                f"Required sheet '{sheet_name}' not found. "
                f"Available sheets: {wb.sheetnames}"
            )

    ws_task = wb['Task']
    ws_data = wb['Data']

    # Build lookup index from Data sheet
    data_index = build_data_index(ws_data)

    # Detect Control/Treated groups from row 9 labels
    groups = classify_group_columns(ws_task, group_row=9, start_col=3, end_col=12)

    # Step 1: Fill expression values (numeric)
    fill_expression_values(ws_task, data_index)

    # Step 2: Compute and write group statistics (numeric)
    compute_group_stats(ws_task, groups=groups)

    # Step 3: Compute and write fold changes (numeric)
    compute_fold_changes(ws_task)

    save_workbook_safely(wb, path)
    return path
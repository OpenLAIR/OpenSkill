"""
Utilities for writing financial calculations into Excel workbooks.
Computes values in Python and writes them directly as numbers.
Also writes Excel formulas where needed for cross-sheet references.
"""
import math
import statistics
import openpyxl
import subprocess
import os
import shutil

def compute_log_returns(prices):
    """Compute log returns as percentages from a list of prices.
    Returns list of (index, value) where index is 0-based position.
    Formula: ln(P_t / P_{t-1}) * 100"""
    returns = []
    for i in range(1, len(prices)):
        if prices[i] is not None and prices[i-1] is not None and prices[i-1] > 0 and prices[i] > 0:
            lr = math.log(prices[i] / prices[i-1]) * 100
            returns.append((i, lr))
        else:
            returns.append((i, None))
    return returns

def compute_rolling_stdev(values, window):
    """Compute rolling sample standard deviation (STDEV.S equivalent).
    values: list where index matches log_returns index.
    Returns list of (index, stdev_value)."""
    result = []
    for i in range(len(values)):
        if i < window - 1:
            result.append((i, None))
            continue
        window_vals = [values[j] for j in range(i - window + 1, i + 1) if values[j] is not None]
        if len(window_vals) >= 2:
            result.append((i, statistics.stdev(window_vals)))
        else:
            result.append((i, None))
    return result

def recalculate_with_libreoffice(filepath):
    """Force recalculation using LibreOffice headless."""
    abs_path = os.path.abspath(filepath)
    outdir = os.path.dirname(abs_path)
    basename = os.path.basename(abs_path)
    
    # Copy to temp name to avoid overwrite issues
    tmp_name = 'tmp_recalc.xlsx'
    tmp_path = os.path.join(outdir, tmp_name)
    shutil.copy2(abs_path, tmp_path)
    
    try:
        result = subprocess.run(
            ['libreoffice', '--headless', '--calc', '--convert-to',
             'xlsx:Calc MS Excel 2007 XML', tmp_path, '--outdir', outdir],
            capture_output=True, text=True, timeout=120
        )
        # Output will be tmp_recalc.xlsx in outdir (overwriting itself)
        if os.path.exists(tmp_path):
            shutil.move(tmp_path, abs_path)
        return result.returncode == 0
    except Exception as e:
        print(f'LibreOffice error: {e}')
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False


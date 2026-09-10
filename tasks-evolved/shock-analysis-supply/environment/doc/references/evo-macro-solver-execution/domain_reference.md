# Domain Reference for evo-macro-solver-execution

**Responsibility**: Run the HP filter optimization either via LibreOffice UNO Solver API or scipy.optimize to find smoothed LnZ trend values that minimize the HP filter objective with lambda=6.25; recalculate all formulas via LibreOffice headless mode; save final results to test-supply.xlsx

**Key functions to implement**: run_libreoffice_solver, run_scipy_hp_filter, recalculate_workbook, write_solver_results

---

### 3.1 The Objective Function and Lambda (\(\lambda\))


The filter operates by minimizing a two-part objective function. The first part penalizes the variance of the cyclical component (Goodness-of-fit), and the second part penalizes variations in the growth rate of the trend component (Degree of smoothness) [cite: 25, 26]. 

Excel Solver must minimize the following function by changing the values of \(\tau_t\):
\[ \min_{\tau_t} \sum_{t=1}^{T} (y_t - \tau_t)^2 + \lambda \sum_{t=2}^{T-1} [(\tau_{t+1} - \tau_t) - (\tau_t - \tau_{t-1})]^2 \]

**The Standard Lambda Value**:
The smoothing parameter \(\lambda\) determines the strictness of the trend. For quarterly data, a value of \(1600\) is universally accepted [cite: 26]. However, for annual data, there is significant debate:
*   **\(\lambda = 100\)**: The traditional value suggested by Hodrick and Prescott (1997) and Backus and Kehoe (1992) [cite: 27, 28].
*   **\(\lambda = 6.25\)**: Suggested by Ravn and Uhlig (2002). They demonstrated mathematically via both time domain and frequency domain analyses that \(\lambda\) should be adjusted by the fourth power of the frequency ratio [cite: 29]. Since there are four quarters in a year, the adjustment is \(1600 / 4^4 = 1600 / 256 = 6.25\) [cite: 28, 30]. Research strongly suggests that \(\lambda = 6.25\) yields a trend for annual data that perfectly matches the aggregated quarterly trend [cite: 29].

## 5. LibreOffice Calc Solver via Command Line and Python-UNO


To automatically solve the HP filter objective function directly within a spreadsheet file without manual intervention, one can invoke LibreOffice Calc's Solver engine via a headless Python script using the UNO (Universal Network Objects) bridge [cite: 40, 41, 42].

### 5.1 Invoking LibreOffice UNO


LibreOffice must be started in a headless listening mode:
```bash
soffice --headless --accept="socket,host=localhost,port=2002;urp;StarOffice.ComponentContext" --calc
```
From Python, the `uno` module connects to this socket [cite: 41, 43].

### 5.2 Programmatic Solver Implementation


The `com.sun.star.sheet.Solver` service provides access to LibreOffice's optimization algorithms [cite: 44]. The following Python code demonstrates how to bridge to LibreOffice, configure the non-linear solver for the HP Filter, and execute it:

```python
import uno
from com.sun.star.beans import PropertyValue

def run_hp_filter_solver(file_url, sheet_name, objective_cell_name, variable_cells_range):
    # Connect to the headless LibreOffice instance
    local_ctx = uno.getComponentContext()
    smgr_local = local_ctx.ServiceManager
    resolver = smgr_local.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local_ctx)
    ctx = resolver.resolve("uno:socket,host=localhost,port=2002;urp;StarOffice.ComponentContext")
    smgr = ctx.ServiceManager

    # Open Document
    desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    doc = desktop.loadComponentFromURL(file_url, "_blank", 0, ())
    
    # Get Sheet and Cells
    sheets = doc.getSheets()
    sheet = sheets.getByName(sheet_name)
    objective_cell = sheet.getCellRangeByName(objective_cell_name).getCellAddress()
    variable_cells = sheet.getCellRangeByName(variable_cells_range).getRangeAddress()

    # Initialize Solver
    solver = smgr.createInstanceWithContext("com.sun.star.sheet.Solver", ctx)
    solver.Document = doc
    solver.Objective = objective_cell
    solver.Variables = (variable_cells,)
    solver.Maximize = False # We want to minimize the HP filter objective

    # Use SCO evolutionary algorithm for non-linear HP filter objective
    # Alternatively, use "com.sun.star.comp.Calc.CoinMPSolver" for LP
    solver.SolverEngine = "com.sun.star.comp.Calc.NLPSolver.SCOSolverImpl"

    # Execute Solver
    solver.solve()
    
    if solver.Success:
        # Save changes if successful
        doc.store()
        print(f"Solver achieved objective value: {solver.ResultValue}")
    else:
        print("Solver failed to converge.")
        
    doc.dispose()
```
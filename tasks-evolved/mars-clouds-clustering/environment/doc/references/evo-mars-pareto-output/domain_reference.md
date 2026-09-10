# Domain Reference for evo-mars-pareto-output

**Responsibility**: Takes the filtered grid search results DataFrame, applies paretoset to identify Pareto-optimal points with sense=['max', 'min'] for F1 and delta respectively, formats and rounds columns per specification, and writes /root/pareto_frontier.csv.

**Key functions to implement**: compute_pareto_frontier, format_and_save_pareto_csv

---

## 4. Pareto Frontier Computation using `paretoset` 1.2.3


In a hyperparameter optimization grid, multiple configurations will yield varying results. When seeking to simultaneously optimize conflicting objectives—for instance, maximizing the F1 score while minimizing the complexity or variance—the `paretoset` library allows for the robust identification of the Pareto frontier [cite: 21, 22].

## 5. pandas 2.2.2 Patterns for the Pipeline


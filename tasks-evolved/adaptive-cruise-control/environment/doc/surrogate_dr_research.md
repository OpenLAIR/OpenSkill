To verify the Adaptive Cruise Control (ACC) simulation, you can implement a surrogate test suite using the following independently derived anchors and invariants.

### 1. Independently Computable Reference Values
These values allow you to verify the core logic of the PID controller and ACC mode selection without running the full simulation.

*   **PID Controller (Discrete Time)**:
    *   **Formula**: $u_k = K_p e_k + K_i \sum_{i=0}^{k} e_i \Delta t + K_d \frac{e_k - e_{k-1}}{\Delta t}$
    *   **Test Case**: Given $K_p=0.1, K_i=0.01, K_d=0.0$, $dt=0.1$, and a constant error $e=10.0$:
        *   $t=0.1$: $e_0=10.0$. $u_0 = 0.1(10) + 0.01(10 \times 0.1) + 0 = 1.01$
        *   $t=0.2$: $e_1=10.0$. $u_1 = 0.1(10) + 0.01(20 \times 0.1) + 0 = 1.02$
*   **TTC (Time-To-Collision)**:
    *   **Formula**: $TTC = \frac{distance}{v_{ego} - v_{lead}}$ (for $v_{ego} > v_{lead}$)
    *   **Test Case**: If $distance=30m$, $v_{ego}=30m/s$, $v_{lead}=20m/s$:
        *   $TTC = 30 / (30 - 20) = 3.0s$.
        *   *Assertion*: If $TTC \le 3.0s$, the system must trigger 'emergency' mode.

### 2. Dataset-Level Statistical Invariants
These invariants must hold true for the `simulation_results.csv` output:

*   **Monotonicity/Bounds**:
    *   `ego_speed` must be $\ge 0$ and $\le 30.0$ (set speed).
    *   `acceleration_cmd` must be clamped within $[-8.0, 3.0] m/s^2$.
*   **Completeness**:
    *   The output must contain exactly 1501 rows (corresponding to $t=0.0$ to $t=150.0$ with $dt=0.1$).
    *   `time` column must be strictly increasing by $0.1$.
*   **Safety**:
    *   `distance` must never be less than the `min_distance` (10.0m) unless the system is in 'emergency' mode (and even then, it should be strictly positive).

### 3. Cross-Validation Approaches
You can use `pandas` to perform independent verification of the simulation output:

```python
import pandas as pd
import pytest

def test_simulation_invariants():
    df = pd.read_csv('simulation_results.csv')
    
    # Verify row count
    assert len(df) == 1501
    
    # Verify acceleration limits
    assert df['acceleration_cmd'].between(-8.0, 3.0).all()
    
    # Verify steady-state speed (last 10 seconds, t > 140)
    steady_state = df[df['time'] >= 140.0]['ego_speed']
    assert (steady_state.mean() - 30.0) < 0.5  # Steady-state error < 0.5 m/s
    
    # Verify minimum distance
    assert df['distance'].min() >= 10.0
```

### 4. Benchmarks and Reference Implementations
*   **PID Anti-Windup**: Ensure your implementation uses **clamping** (conditional integration). The integral term must stop accumulating when the acceleration command hits the saturation limits $[-8.0, 3.0]$.
*   **Reference Logic**: The ACC system should follow the "Minimum Acceleration" selection logic:
    *   $a_{cmd} = \min(a_{cruise}, a_{follow})$
    *   This ensures that if the distance-keeping requirement demands a lower acceleration than the speed-keeping requirement, the system defaults to the safer (lower) acceleration.
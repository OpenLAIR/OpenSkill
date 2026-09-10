# Manufacturing Production Planning: Flexible Job-Shop Scheduling Optimization with Machine Downtime Constraints and Policy Budgets in Python

**Key Points:**
- **Flexible Job-Shop Scheduling Problem (FJSP)** is a well-known strongly NP-hard combinatorial optimization problem [cite: 1, 2]. It extends the classical Job-Shop Scheduling Problem (JSP) by allowing operations to be processed on any machine from a designated set of eligible machines, thus introducing a routing sub-problem alongside the sequencing sub-problem [cite: 3].
- **Machine downtime constraints** model real-world manufacturing unavailability, such as preventive maintenance, breakdowns, or shifts. Operations cannot overlap with these predefined windows, making the calculation of the earliest feasible start time more complex [cite: 4, 5].
- **Policy budgets** in manufacturing rescheduling represent stability constraints. When a schedule is disrupted, planners need to repair it with minimal deviation from the baseline schedule. This is quantified using limits on start-time deviations (L1 shift) or machine reassignment counts [cite: 6].
- Implementing algorithms in **pure Python** (without external C-backed solvers like OR-Tools or CPLEX) requires heavily optimized data structures, efficient interval management for downtimes, and careful heuristic design (like greedy insertion or Simulated Annealing) to stay within typical computational timeframes (~15 minutes) [cite: 7, 8].
- **Input data parsing** often involves historical text formats (e.g., Brandimarte, Hurink), where 1-based indexing and varying whitespace must be carefully translated into 0-based Python structures [cite: 9, 10]. Output formatting must guarantee that standard JSON serializers appropriately handle specific data types like `numpy.int64`.

The development of a robust, reusable Python skill module for the Flexible Job-Shop Scheduling Problem (FJSP) with machine downtime constraints and policy budgets requires a comprehensive understanding of mathematical modeling, algorithmic design, and careful data engineering. Manufacturing environments rely on deterministic, feasible, and stable schedules. This exhaustive report addresses problem formulation, input parsing, efficient algorithm implementation, edge-case handling for downtimes, feasibility validation, and output formatting.

---

## 1. Problem Formulation and Mathematical Modeling

The standard Flexible Job-Shop Scheduling Problem (FJSP) models a manufacturing floor where a set of independent jobs must be processed by a set of available machines. Unlike the classical Job-Shop Scheduling Problem (JSP) where each operation is permanently assigned to a single specific machine [cite: 11], the FJSP allows each operation to be assigned to one machine out of a set of alternative, eligible machines [cite: 12, 13]. The processing time of the operation is dependent on the machine chosen.

### 1.1 Mathematical Definitions and Sets

To formally define the mathematical model, we introduce the following sets, indices, and parameters [cite: 13, 14]:

**Sets and Indices:**
- Let \( J = \{J_1, J_2, \dots, J_n\} \) be a set of \( n \) independent jobs [cite: 11].
- Let \( M = \{M_1, M_2, \dots, M_m\} \) be a set of \( m \) machines [cite: 11].
- Let \( O_{j} \) denote the set of operations belonging to job \( J_j \). The total number of operations in job \( j \) is \( h_j \).
- Let \( o_{j, k} \) represent the \( k \)-th operation of job \( j \), where \( 1 \leq k \leq h_j \) [cite: 13].
- Let \( M_{j, k} \subseteq M \) represent the set of eligible machines that are capable of processing operation \( o_{j, k} \) [cite: 13].

**Parameters:**
- \( p_{j, k, i} \): The deterministic processing time of operation \( o_{j, k} \) if it is executed on machine \( i \in M_{j, k} \) [cite: 11].
- \( D_{i} = \{(ds_{i, 1}, de_{i, 1}), (ds_{i, 2}, de_{i, 2}), \dots\} \): A set of predefined downtime windows for machine \( i \), where \( ds \) and \( de \) represent the start and end times of the downtime period, respectively [cite: 5, 15].

### 1.2 Decision Variables

We utilize a Mixed-Integer Linear Programming (MILP) variable structure to represent scheduling decisions [cite: 12, 16, 17]:
- \( x_{j, k, i} \in \{0, 1\} \): A binary variable that equals 1 if operation \( o_{j, k} \) is assigned to machine \( i \), and 0 otherwise [cite: 18].
- \( S_{j, k} \geq 0 \): A continuous (or integer) variable representing the start time of operation \( o_{j, k} \) [cite: 13].
- \( C_{j, k} \geq 0 \): A continuous (or integer) variable representing the completion time of operation \( o_{j, k} \) [cite: 13].
- \( Y_{j, k, j', k', i} \in \{0, 1\} \): A binary sequence variable that equals 1 if operation \( o_{j, k} \) is processed before operation \( o_{j', k'} \) on machine \( i \).

### 1.3 Objective Function

The most common objective in FJSP is the minimization of the maximum completion time, known as the **makespan** (\( C_{\max} \)) [cite: 12, 14].
\[ \min C_{\max} \]
Subject to:
\[ C_{\max} \geq C_{j, h_j} \quad \forall j \in \{1, \dots, n\} \]
The makespan represents the moment the last operation of the last job is fully completed [cite: 13].

### 1.4 System Constraints

The model is constrained by manufacturing physics and logic:

**1. Machine Assignment Constraints:**
Each operation must be assigned to exactly one eligible machine [cite: 2, 13].
\[ \sum_{i \in M_{j, k}} x_{j, k, i} = 1 \quad \forall j \in \{1, \dots, n\}, \forall k \in \{1, \dots, h_j\} \]

**2. Duration and Completion Constraints:**
The completion time of an operation is exactly its start time plus its machine-dependent processing time [cite: 13].
\[ C_{j, k} = S_{j, k} + \sum_{i \in M_{j, k}} (p_{j, k, i} \cdot x_{j, k, i}) \quad \forall j, k \]

**3. Precedence Constraints:**
Operations within the same job must be processed in their designated strict sequential order [cite: 2, 11].
\[ S_{j, k+1} \geq C_{j, k} \quad \forall j \in \{1, \dots, n\}, \forall k \in \{1, \dots, h_j-1\} \]

**4. Machine Disjunctive (Non-Overlap) Constraints:**
A machine can process at most one operation at a time. If two operations are assigned to the same machine, one must strictly precede the other [cite: 11, 13].
Let \( \mathbb{M} \) be a sufficiently large number (Big-M formulation). For any two distinct operations \( o_{j, k} \) and \( o_{j', k'} \):
\[ S_{j, k} \geq C_{j', k'} - \mathbb{M} \cdot (3 - x_{j, k, i} - x_{j', k', i} - Y_{j, k, j', k', i}) \]
\[ S_{j', k'} \geq C_{j, k} - \mathbb{M} \cdot (2 - x_{j, k, i} - x_{j', k', i} + Y_{j, k, j', k', i}) \]

**5. Machine Downtime Constraints:**
No operation can overlap with any downtime window \( (ds_{i, d}, de_{i, d}) \) of its assigned machine [cite: 15]. For any operation \( o_{j, k} \) assigned to machine \( i \), and for every downtime window \( d \) on machine \( i \):
Either the operation ends before the downtime starts, or the operation starts after the downtime ends.
\[ C_{j, k} \leq ds_{i, d} \quad \text{OR} \quad S_{j, k} \geq de_{i, d} \]
In MILP, this is typically handled by introducing another binary variable for the disjunction [cite: 7].

### 1.5 Policy Budgets in Rescheduling Contexts

In real-world manufacturing, schedules are rarely executed perfectly. Breakdowns, delays, or new urgent orders trigger a need for rescheduling [cite: 19]. When rescheduling, planners face a trade-off between schedule efficiency (makespan) and schedule stability (deviation from the baseline schedule) [cite: 19]. To manage this, "policy budgets" are introduced [cite: 6].

A **policy budget** acts as an upper limit on how much the new schedule can deviate from the original baseline schedule. Two common metrics are:

1. **Machine Change Budget (\( B_M \)):** The maximum allowed number of operations that are assigned to a machine different from their baseline assignment [cite: 6].
   \[ \sum_{j, k} \mathbb{I}(x_{j, k, i}^{new} \neq x_{j, k, i}^{base}) \leq B_M \]
2. **Start-Time Shift Budget (\( B_S \)):** The maximum allowed sum of absolute deviations (L1 norm) in start times compared to the baseline [cite: 6].
   \[ \sum_{j, k} |S_{j, k}^{new} - S_{j, k}^{base}| \leq B_S \]

When building our python skill module, validating and adhering to these policy budgets is essential for generating output that is practically viable for human planners on the factory floor [cite: 6].

---

## 2. Input Data Parsing Patterns

Data engineering and parsing form the bedrock of scheduling algorithms. We must extract information from standardized text files, CSVs, and JSON files [cite: 11]. 

### 2.1 Parsing Standard FJSP Instance Files (Brandimarte, Hurink, Dauzère-Pérès)

The benchmark instances provided by researchers like Brandimarte (1993), Hurink et al. (1994), and Dauzère-Pérès and Paulli (1994) share a common schema, though specific formatting (like the presence of a third number on the first line or excessive whitespace) varies [cite: 9, 10, 20].

**Format Schema:**
- **First Line:** `<number of jobs> <number of machines> [<average number of eligible machines per operation (optional)>]` [cite: 9, 10]
- **Subsequent Lines (one per job):** `<number of operations>` followed by data for each operation sequentially [cite: 9].
- **Operation Data Format:** `<number of eligible machines>` followed by pairs of `<machine_id> <processing_time>` [cite: 9, 10].

**Note on Indexing:**
Most standard benchmarks use 1-based indexing for machines (i.e., machines are numbered 1 to M) [cite: 9]. In Python, it is standard practice to map these to 0-based indices to allow for direct array/list lookups.

**Python Implementation:**
```python
import re

def parse_fjsp_instance(filepath: str):
    """
    Parses standard FJSP benchmark files (Brandimarte, Hurink, etc.).
    Returns jobs list and num_machines.
    
    jobs = [
        [ # Job 0
            {0: 4, 2: 5}, # Operation 0: {machine_id: proc_time}
            {1: 2}        # Operation 1
        ],
        ...
    ]
    """
    with open(filepath, 'r') as f:
        data = f.read().strip()
    
    # Use regex to split by any whitespace (spaces, tabs, newlines)
    tokens = re.split(r'\s+', data)
    if not tokens or not tokens:
        raise ValueError("Empty or invalid file.")
    
    num_jobs = int(tokens)
    num_machines = int(tokens[cite: 4])
    
    # Some formats include a third token on the first line (avg eligible machines).
    # To reliably find the start of job data, we rely on the token consumption loop.
    # However, if the third token is a float or we just skip it based on logical structure:
    # Actually, the safest way is to read line by line because the first line is distinct.
    
    # Safer Line-by-Line Parsing Approach:
    with open(filepath, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
        
    first_line_tokens = lines.split()
    num_jobs = int(first_line_tokens)
    num_machines = int(first_line_tokens[cite: 4])
    
    jobs = []
    # Combine remaining lines into a single stream of integers to ignore arbitrary line breaks
    # Sometimes a single job's operations span multiple lines in certain datasets.
    stream = []
    for line in lines[1:]:
        stream.extend([int(float(x)) for x in line.split()])
        
    ptr = 0
    for j in range(num_jobs):
        if ptr >= len(stream):
            break
        num_ops = stream[ptr]
        ptr += 1
        
        operations = []
        for o in range(num_ops):
            num_eligible = stream[ptr]
            ptr += 1
            
            eligible_machines = {}
            for _ in range(num_eligible):
                # Convert 1-based machine ID from file to 0-based for Python
                machine_id = stream[ptr] - 1 
                proc_time = stream[ptr+1]
                eligible_machines[machine_id] = proc_time
                ptr += 2
                
            operations.append(eligible_machines)
        jobs.append(operations)
        
    return jobs, num_machines
```

### 2.2 Parsing Machine Downtime Windows from CSV

Machine downtimes represent intervals where a machine is unavailable [cite: 4, 5]. They are usually provided in a tabular format.

```python
import pandas as pd
from collections import defaultdict

def parse_downtimes_csv(filepath: str):
    """
    Parses machine downtimes from a CSV file.
    Expected columns: 'machine', 'start', 'end'
    Returns a dict: {machine_id: [[start1, end1], [start2, end2], ...]}
    """
    df = pd.read_csv(filepath)
    
    # Basic validation
    required_cols = {'machine', 'start', 'end'}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"CSV must contain columns: {required_cols}")
        
    downtimes = defaultdict(list)
    
    for _, row in df.iterrows():
        machine_id = int(row['machine'])
        start_time = int(row['start'])
        end_time = int(row['end'])
        
        # Validate interval
        if end_time <= start_time:
            continue # Or raise ValueError depending on strictness
            
        downtimes[machine_id].append([start_time, end_time])
        
    # Crucial Step: Sort the intervals by start time for each machine
    for m in downtimes:
        downtimes[m].sort(key=lambda x: x)
        
    return dict(downtimes)
```

### 2.3 Parsing Policy Budget Constraints from JSON

Policy budgets define the limits of flexibility [cite: 6]. A JSON structure allows dynamic schema definition.

```python
import json

def parse_policy_budgets(filepath: str):
    """
    Parses policy budgets from a JSON file.
    Example JSON:
    {
        "max_machine_changes": 10,
        "max_start_time_shift": 500
    }
    """
    with open(filepath, 'r') as f:
        budgets = json.load(f)
        
    # Apply default infinite budget if not specified
    return {
        'max_machine_changes': budgets.get('max_machine_changes', float('inf')),
        'max_start_time_shift': budgets.get('max_start_time_shift', float('inf'))
    }
```

### 2.4 Parsing the Baseline Schedule

The baseline schedule is the reference point for calculating policy budget consumption [cite: 6].

```python
def parse_baseline_schedule(filepath: str):
    """
    Parses baseline schedule from CSV.
    Expected columns: 'job', 'op', 'machine', 'start', 'end', 'dur'
    Returns a dict keyed by (job_id, op_id) -> {machine, start, end, dur}
    """
    df = pd.read_csv(filepath)
    baseline = {}
    for _, row in df.iterrows():
        job_id = int(row['job'])
        op_id = int(row['op'])
        baseline[(job_id, op_id)] = {
            'machine': int(row['machine']),
            'start': int(row['start']),
            'end': int(row['end']),
            'dur': int(row['dur'])
        }
    return baseline
```

---

## 3. Handling Machine Downtime Windows Correctly

One of the most complex elements of pure Python scheduling is the logic to calculate the earliest feasible start time for an operation on a machine, considering both previously scheduled operations and fixed downtime windows [cite: 7, 15].

### 3.1 The `find_earliest_start` Algorithm

To insert an operation onto a machine, we must find the earliest continuous block of time (a "gap") that is greater than or equal to the operation's duration, and which begins on or after the operation's earliest possible start time (dictated by the completion of the predecessor operation).

The algorithm must handle several edge cases:
- The required duration spans across multiple contiguous downtime windows.
- Downtime starts exactly at time 0.
- Adjacent downtime windows that effectively form a larger single window.
- Zero-duration gaps (e.g., a downtime ends at 10, another starts at 10).

**Python Implementation:**

```python
def find_earliest_start(machine: int, earliest_time: int, duration: int, 
                        downtimes: dict, scheduled_ops: dict) -> int:
    """
    Finds the earliest start time >= earliest_time on the specified machine 
    where an operation of `duration` can fit without overlapping downtimes 
    or scheduled operations.
    """
    # 1. Gather all occupied intervals for the machine
    occupied = []
    
    if machine in downtimes:
        # Deepcopy to prevent mutating original data
        occupied.extend([[start, end] for start, end in downtimes[machine]])
        
    if machine in scheduled_ops:
        # Assuming scheduled_ops is dict: machine -> list of dicts with 'start', 'end'
        for op in scheduled_ops[machine]:
            occupied.append([op['start'], op['end']])
            
    # If the machine is completely empty, we can just start at earliest_time
    if not occupied:
        return earliest_time

    # 2. Sort intervals strictly by start time
    occupied.sort(key=lambda x: x)
    
    # 3. Merge overlapping and directly adjacent intervals
    merged = []
    for interval in occupied:
        if not merged:
            merged.append(interval)
        else:
            prev_start, prev_end = merged[-1]
            curr_start, curr_end = interval
            # If current interval overlaps or touches the previous one
            if curr_start <= prev_end:
                # Merge them by extending the end time
                merged[-1][cite: 4] = max(prev_end, curr_end)
            else:
                merged.append(interval)
                
    # 4. Search for a suitable gap
    current_time = earliest_time
    
    for start_occ, end_occ in merged:
        # If the occupied interval ends before or exactly when our current_time starts, 
        # it doesn't affect us.
        if end_occ <= current_time:
            continue
            
        # Check if the gap between current_time and the start of the occupied interval 
        # is large enough to fit our duration.
        if current_time + duration <= start_occ:
            return current_time
            
        # The operation cannot fit in the gap (or there is no gap). 
        # We must push the current_time to the end of this occupied interval.
        current_time = max(current_time, end_occ)
        
    # If we pass through all occupied intervals and haven't returned,
    # the operation can be scheduled safely at the end of the last occupied interval.
    return current_time
```

### 3.2 Complexity and Optimization

The complexity of `find_earliest_start` is \( O(K \log K) \) where \( K \) is the total number of downtimes and scheduled operations on the machine, due to the sorting step. In an inner loop of an optimization algorithm (like a Genetic Algorithm evaluating thousands of individuals), this can become a bottleneck. 
To optimize for pure Python implementation:
- Maintain the `merged` list dynamically as operations are inserted, rather than re-computing and re-sorting it every time. Using the `bisect` module allows \( O(K) \) insertion into a sorted list.

---

## 4. Scheduling Algorithms for Python Implementation

Without utilizing solvers like CPLEX or Google OR-Tools [cite: 7], we must rely on heuristic and metaheuristic algorithms that can generate high-quality solutions within the computational budget (~15 minutes).

### 4.1 Greedy Dispatching Heuristic (Constructive Phase)

A greedy algorithm serves as an excellent baseline and initialization method. It iterates through operations sequentially (ensuring precedence) and places each operation on the machine that allows it to finish at the earliest possible time (Earliest Completion Time - ECT heuristic) [cite: 21].

```python
def greedy_dispatching(jobs: list, num_machines: int, downtimes: dict):
    """
    Constructs a valid schedule using the Earliest Completion Time (ECT) rule.
    """
    # Track the completion time of the previous operation for each job
    # job_id -> completion time of last scheduled op
    job_completion = {j: 0 for j in range(len(jobs))}
    
    # Track scheduled operations on each machine
    # machine_id -> [{'start': s, 'end': e, 'job': j, 'op': o}]
    scheduled_ops = {m: [] for m in range(num_machines)}
    
    schedule_output = []
    
    # Create a list of all operations with their topological order
    # For a job shop, processing operations in order of their operation index guarantees precedence.
    # We can process job by job, or round-robin across jobs.
    # Round-robin helps balance machine loads better than doing all of Job 1, then Job 2.
    
    max_ops = max(len(job) for job in jobs)
    
    for op_idx in range(max_ops):
        for job_idx, job in enumerate(jobs):
            if op_idx >= len(job):
                continue # Job has finished all its operations
                
            eligible_machines = job[op_idx]
            earliest_available_time = job_completion[job_idx]
            
            best_machine = -1
            best_start = float('inf')
            best_end = float('inf')
            best_duration = 0
            
            # Find the machine that offers the earliest completion time
            for machine_id, proc_time in eligible_machines.items():
                start_time = find_earliest_start(
                    machine=machine_id, 
                    earliest_time=earliest_available_time, 
                    duration=proc_time, 
                    downtimes=downtimes, 
                    scheduled_ops=scheduled_ops
                )
                end_time = start_time + proc_time
                
                if end_time < best_end:
                    best_end = end_time
                    best_start = start_time
                    best_machine = machine_id
                    best_duration = proc_time
                    
            # Assign to the best machine found
            op_record = {
                'job': job_idx,
                'op': op_idx,
                'machine': best_machine,
                'start': best_start,
                'end': best_end,
                'dur': best_duration
            }
            
            scheduled_ops[best_machine].append(op_record)
            schedule_output.append(op_record)
            
            # Update job completion time for precedence
            job_completion[job_idx] = best_end
            
    return schedule_output
```

### 4.2 Constraint-Based Repair / Rescheduling Algorithm

When dealing with a policy budget, we often receive an infeasible baseline (e.g., due to newly added downtime). We need to "repair" the schedule. The rule is: *never start earlier than the baseline, keep modifications small, respect precedence, and respect downtimes* [cite: 6].

```python
def repair_schedule(jobs: list, num_machines: int, downtimes: dict, baseline: dict, policy_budgets: dict):
    job_completion = {j: 0 for j in range(len(jobs))}
    scheduled_ops = {m: [] for m in range(num_machines)}
    new_schedule = []
    
    changes_made = 0
    shift_made = 0
    
    for job_idx, job in enumerate(jobs):
        for op_idx, eligible_machines in enumerate(job):
            base_info = baseline[(job_idx, op_idx)]
            base_start = base_info['start']
            base_machine = base_info['machine']
            
            # Anchor time: maximum of baseline start and actual completion of previous op
            anchor_time = max(base_start, job_completion[job_idx])
            
            best_machine = -1
            best_start = float('inf')
            best_score = float('inf')
            best_dur = 0
            
            for m_id, proc_time in eligible_machines.items():
                st = find_earliest_start(m_id, anchor_time, proc_time, downtimes, scheduled_ops)
                
                # Evaluate policy impact
                machine_change = 1 if m_id != base_machine else 0
                start_shift = abs(st - base_start)
                
                # Check if this choice violates budget remaining
                if changes_made + machine_change > policy_budgets['max_machine_changes']:
                    continue
                if shift_made + start_shift > policy_budgets['max_start_time_shift']:
                    continue
                    
                # Lexicographic scoring [cite: 6]
                score = (machine_change, start_shift, st, m_id)
                if score < best_score:
                    best_score = score
                    best_machine = m_id
                    best_start = st
                    best_dur = proc_time
            
            if best_machine == -1:
                raise ValueError(f"Infeasible to schedule Job {job_idx} Op {op_idx} within policy budgets.")
                
            changes_made += (1 if best_machine != base_machine else 0)
            shift_made += abs(best_start - base_start)
            
            op_record = {
                'job': job_idx, 'op': op_idx, 'machine': best_machine,
                'start': best_start, 'end': best_start + best_dur, 'dur': best_dur
            }
            scheduled_ops[best_machine].append(op_record)
            new_schedule.append(op_record)
            job_completion[job_idx] = best_start + best_dur
            
    return new_schedule
```

### 4.3 Simulated Annealing (SA) / Local Search

For optimization within 15 minutes, pure Python relies heavily on simple representation arrays. The FJSP can be represented by two arrays (chromosomes): 
1. **Operation Sequence (OS):** An array containing job IDs. The \( n \)-th occurrence of job ID \( j \) represents the \( n \)-th operation of job \( j \) [cite: 21].
2. **Machine Selection (MS):** An array mapping each operation to a machine index from its eligible set [cite: 21].

**Neighborhood Moves:**
- **N1 (Machine Mutation):** Randomly select an operation and change its assigned machine in the MS array to another eligible machine.
- **N2 (Sequence Mutation):** Swap two adjacent operations in the OS array, provided they belong to different jobs.

```python
import random
import math

def decode_schedule(os_array, ms_array, jobs, num_machines, downtimes):
    """
    Translates OS and MS arrays into a concrete schedule using active scheduling generation.
    Returns makespan and the schedule.
    """
    job_op_counters = {j: 0 for j in range(len(jobs))}
    job_completion = {j: 0 for j in range(len(jobs))}
    scheduled_ops = {m: [] for m in range(num_machines)}
    schedule = []
    
    # Iterate through the operation sequence
    for job_idx in os_array:
        op_idx = job_op_counters[job_idx]
        job_op_counters[job_idx] += 1
        
        # Get machine selection
        ms_idx = ms_array[job_idx][op_idx]
        
        # Dictionary of eligible machines
        eligible = jobs[job_idx][op_idx]
        # In a strict implementation, MS array stores the actual machine ID
        machine_id = ms_idx 
        proc_time = eligible[machine_id]
        
        earliest_time = job_completion[job_idx]
        start_time = find_earliest_start(machine_id, earliest_time, proc_time, downtimes, scheduled_ops)
        
        op_record = {
            'job': job_idx, 'op': op_idx, 'machine': machine_id,
            'start': start_time, 'end': start_time + proc_time, 'dur': proc_time
        }
        scheduled_ops[machine_id].append(op_record)
        schedule.append(op_record)
        job_completion[job_idx] = start_time + proc_time
        
    makespan = max(job_completion.values())
    return makespan, schedule

def simulated_annealing_fjsp(jobs, num_machines, downtimes, max_iterations=5000):
    # Initialize OS (Operation Sequence)
    os_array = []
    for j, job in enumerate(jobs):
        os_array.extend([j] * len(job))
    random.shuffle(os_array)
    
    # Initialize MS (Machine Selection)
    ms_array = []
    for job in jobs:
        job_ms = []
        for op in job:
            # Pick a random eligible machine
            job_ms.append(random.choice(list(op.keys())))
        ms_array.append(job_ms)
        
    best_makespan, best_schedule = decode_schedule(os_array, ms_array, jobs, num_machines, downtimes)
    current_os, current_ms = list(os_array), [list(job_ms) for job_ms in ms_array]
    current_makespan = best_makespan
    
    T = 100.0
    alpha = 0.99
    
    for i in range(max_iterations):
        # Generate Neighbor
        neighbor_os = list(current_os)
        neighbor_ms = [list(job_ms) for job_ms in current_ms]
        
        move_type = random.choice(['swap_os', 'mutate_ms'])
        
        if move_type == 'swap_os':
            # Swap two different jobs in OS
            idx1, idx2 = random.sample(range(len(neighbor_os)), 2)
            neighbor_os[idx1], neighbor_os[idx2] = neighbor_os[idx2], neighbor_os[idx1]
        else:
            # Mutate MS
            j = random.randrange(len(jobs))
            o = random.randrange(len(jobs[j]))
            eligible = list(jobs[j][o].keys())
            if len(eligible) > 1:
                eligible.remove(neighbor_ms[j][o])
                neighbor_ms[j][o] = random.choice(eligible)
                
        neighbor_makespan, neighbor_schedule = decode_schedule(neighbor_os, neighbor_ms, jobs, num_machines, downtimes)
        
        # Acceptance logic
        delta = neighbor_makespan - current_makespan
        if delta < 0 or random.random() < math.exp(-delta / T):
            current_os, current_ms = neighbor_os, neighbor_ms
            current_makespan = neighbor_makespan
            
            if current_makespan < best_makespan:
                best_makespan = current_makespan
                best_schedule = neighbor_schedule
                
        T *= alpha
        
    return best_schedule
```

---

## 5. Policy Budget Constraints

In production environments, a complete re-optimization of a schedule is often highly undesirable due to the physical setup already in place (e.g., tools loaded, materials staged) [cite: 19]. When disruptions occur, schedules are repaired using a limited "Policy Budget" [cite: 6].

### 5.1 Formal Budget Definitions

1. **Maximum Machine Changes:** 
   The total number of operations processed on a different machine in the new schedule compared to the baseline schedule must be \( \leq B_M \) [cite: 6].
2. **Maximum Start-Time Shift (L1 Norm):**
   The sum of absolute differences between the start times in the new schedule and the baseline schedule must be \( \leq B_S \) [cite: 6].

### 5.2 Ensuring "No Worse Policy Budgets"

When running heuristic improvements, any candidate schedule must be validated against the budget. If a local search move violates the budget, the move is strictly rejected, enforcing a rigid boundary on the search space.

```python
def validate_policy_budgets(new_schedule: list, baseline: dict, budgets: dict) -> bool:
    machine_changes = 0
    start_shift = 0
    
    for op in new_schedule:
        j = op['job']
        o = op['op']
        m_new = op['machine']
        s_new = op['start']
        
        base = baseline.get((j, o))
        if not base:
            # If the operation wasn't in baseline, it might be new, handle logic accordingly
            continue
            
        m_base = base['machine']
        s_base = base['start']
        
        if m_new != m_base:
            machine_changes += 1
            
        start_shift += abs(s_new - s_base)
        
    if machine_changes > budgets.get('max_machine_changes', float('inf')):
        return False
    if start_shift > budgets.get('max_start_time_shift', float('inf')):
        return False
        
    return True
```

---

## 6. Feasibility Validation

Schedule validation is absolutely critical. An automated validator ensures the heuristic output complies with all mathematical constraints of the FJSP.

### 6.1 Python Validator Class

The validator checks:
1. All operations are present.
2. Machine capacity limits (no overlapping tasks).
3. Operation duration correctness relative to machine choice.
4. Precedence rules.
5. No overlap with machine downtimes.

```python
class FJSPValidator:
    def __init__(self, jobs, num_machines, downtimes):
        self.jobs = jobs
        self.num_machines = num_machines
        self.downtimes = downtimes

    def validate(self, schedule: list) -> bool:
        # Convert schedule list to easier structures
        machine_timelines = {m: [] for m in range(self.num_machines)}
        job_timelines = {j: {} for j in range(len(self.jobs))}
        
        for op in schedule:
            j, o, m, s, e, d = op['job'], op['op'], op['machine'], op['start'], op['end'], op['dur']
            
            # Check duration math
            if e - s != d:
                print(f"Duration mismatch for Job {j} Op {o}: {e} - {s} != {d}")
                return False
                
            # Check eligibility and correct duration from instance data
            if m not in self.jobs[j][o]:
                print(f"Machine {m} is not eligible for Job {j} Op {o}")
                return False
            if self.jobs[j][o][m] != d:
                print(f"Wrong processing time for Job {j} Op {o} on M{m}. Expected {self.jobs[j][o][m]}, got {d}")
                return False
                
            machine_timelines[m].append((s, e, j, o))
            job_timelines[j][o] = (s, e)
            
        # Check Precedence & Completeness
        for j, job_ops in enumerate(self.jobs):
            if len(job_timelines[j]) != len(job_ops):
                print(f"Job {j} is incomplete.")
                return False
            for o in range(len(job_ops) - 1):
                end_curr = job_timelines[j][o][cite: 4]
                start_next = job_timelines[j][o+1]
                if start_next < end_curr:
                    print(f"Precedence violation in Job {j}: Op {o+1} starts at {start_next} but Op {o} ends at {end_curr}")
                    return False
                    
        # Check Overlaps on Machines
        for m, tasks in machine_timelines.items():
            tasks.sort(key=lambda x: x)
            for i in range(len(tasks) - 1):
                if tasks[i][cite: 4] > tasks[i+1]:
                    print(f"Machine overlap on M{m} between {tasks[i]} and {tasks[i+1]}")
                    return False
                    
        # Check Overlaps with Downtimes
        for m, tasks in machine_timelines.items():
            if m not in self.downtimes:
                continue
            dts = self.downtimes[m]
            for s, e, j, o in tasks:
                for ds, de in dts:
                    # Overlap condition: max(s, ds) < min(e, de)
                    if max(s, ds) < min(e, de):
                        print(f"Downtime overlap on M{m}: Task ({s}, {e}) overlaps Downtime ({ds}, {de})")
                        return False
                        
        return True

    def calculate_makespan(self, schedule: list) -> int:
        return max(op['end'] for op in schedule)
```

---

## 7. Output Formatting

Interoperability in modern tech stacks requires outputting results in strictly formatted JSON and CSV files. A major pitfall in pure-Python processing when combining with numerical data (like Pandas or NumPy) is that JSON cannot natively serialize `numpy.int64` objects.

### 7.1 JSON Export with Custom Encoder

```python
import json
import numpy as np

class NpEncoder(json.JSONEncoder):
    """ Custom encoder to handle numpy data types safely """
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)

def export_solution_json(schedule: list, makespan: int, status: str, filepath: str):
    """
    Schema: {"status": "...", "makespan": N, "schedule": [...]}
    """
    output = {
        "status": status,
        "makespan": makespan,
        "schedule": schedule
    }
    with open(filepath, 'w') as f:
        json.dump(output, f, cls=NpEncoder, indent=4)
```

### 7.2 CSV Export using Pandas

```python
import pandas as pd

def export_solution_csv(schedule: list, filepath: str):
    """
    Generates CSV with columns: job, op, machine, start, end, dur
    """
    df = pd.DataFrame(schedule)
    # Ensure exact column order
    df = df[['job', 'op', 'machine', 'start', 'end', 'dur']]
    df.to_csv(filepath, index=False)
```

---

## 8. Common Pitfalls and Solutions

When developing FJSP algorithms from scratch, developers frequently encounter specific logic and data bugs:

1. **0-based vs 1-based Indexing:**
   Benchmark instance text files traditionally represent jobs, operations, and machines starting at index 1 [cite: 9, 10]. Python arrays naturally start at 0. Failing to subtract `1` from machine IDs during parsing will cause `IndexError` exceptions during execution. All internal algorithms should strictly use 0-based indexing, and formatting to 1-based indexing should occur only during UI rendering or logging.

2. **Unsorted Downtime Windows:**
   The `find_earliest_start` function fundamentally relies on processing intervals from earliest to latest. Passing an unsorted list of downtime windows will cause the interval-merging step to fail, leading to algorithms incorrectly identifying overlaps as free gaps. **Always `sort()` downtimes by start time upon parsing [cite: 15].**

3. **Varying Processing Times (Flexible vs Classical JSP):**
   In standard JSP, an operation's duration is fixed. In FJSP, it changes based on the selected machine [cite: 11, 22]. A common pitfall is caching the processing time at the *operation* level rather than reading it from the `eligible_machines` dictionary during the active machine selection phase.

4. **Ignoring Downtimes During Local Search Moves:**
   A simple swapping mechanism in a Simulated Annealing algorithm (e.g., swapping two operations on the same machine) might place an operation directly over a downtime window. If the algorithm updates start/end times via a naive addition without routing through `find_earliest_start`, the schedule immediately becomes structurally infeasible [cite: 21].

5. **Serialization Errors (`TypeError: Object of type int64 is not JSON serializable`):**
   If parsing inputs via Pandas (e.g., reading baseline schedules or downtimes), integer fields are automatically converted to `numpy.int64`. The standard Python `json.dump()` crashes on this type. Applying the custom `NpEncoder` shown above completely resolves this issue.

---

## 9. Best Pure-Python Approaches (Within 15 Min Compute Budget)

Because external solvers (OR-Tools, CPLEX, Gurobi) are restricted in this module's setup, pure-Python optimizations are crucial [cite: 7, 8, 17]. The best approach for high-quality FJSP results within a 15-minute Python execution window encompasses the following strategy:

1. **Greedy Initialization Population:**
   Instead of purely random generation, instantiate your initial population (for SA or GA) using variations of the Greedy Dispatching heuristic. By sorting jobs differently (e.g., Shortest Processing Time first, Longest Processing Time first, or random shuffling) before applying the Earliest Completion Time rule, you generate a highly diverse but fundamentally feasible and fast starting point [cite: 19].

2. **Efficient Data Structures:**
   Python dictionaries have an \( O(1) \) lookup, but the constant overhead is higher than list indexing. Where possible, represent the schedule state using pre-allocated lists (e.g., `job_completion =  * num_jobs`).

3. **Algorithm Choice - Simulated Annealing over Genetic Algorithm:**
   In pure Python, managing the crossover operators of a Genetic Algorithm (like the Precedence Preserving Order-Based Crossover or POX) requires extensive list slicing and validation, which is computationally expensive in Python [cite: 23]. Simulated Annealing requires only a single state vector and minimal memory allocation per iteration. SA with efficient neighborhood moves (OS swapping, MS mutation) combined with the optimized `decode_schedule` routine will yield millions of evaluations within 15 minutes, converging to a near-optimal or highly competitive makespan [cite: 2, 19].

4. **JIT Compilation Alternatives:**
   While not part of the standard library, writing the core `find_earliest_start` loop and `decode_schedule` function in a way that avoids complex object-oriented overhead ensures maximum speed.

By adhering to these patterns, a Python skill module will successfully parse industry-standard datasets, rapidly generate feasible machine assignments, seamlessly route around machine breakdowns/maintenance windows, strictly enforce business policy budgets during rescheduling, and output validated data structures ready for factory-floor deployment.

**Sources:**
1. [utep.edu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHY1KS1uKt4VF78VsKKwAMQHWM-6IKwta0aQidBhs8y7h8i9JuS8Fk_WQ2viF_a8sV_vo5flWAsdtf8vKTCL_lc1UYAab8Ndn81dPl1hpSoXlVmGhF9mddVsHnXgymNAzrlxajpmkWdqWrQP0DWCwPTomdJMQzH00hn7AZ8TYnD65uYqvpt)
2. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH36ITLsoBw07nu1OPG2gAb6Z6CmFlC4x8hX9Qe0KQEsr69uTQOBA5v7eVccBLMevlYKoTzXTETvv5C10Cc5Y2GPFq_ibFXaU1Q4uXTPZYYKtJVsAtX6w==)
3. [eudoxuspress.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF3S0P_EE9fLCBsQ0NB-AIULqfKtHUTlJQr6RWnjcc-8g7dunwe_S17_Re1EAKCdKwcOzAanMSoxbd0SSupzvPyxHH-rHK6D5XwlnOPDIqhBi9EqpGsRDO2p9Qo1lOR7nfJJnjnIySQF6YbRHjEMdzj31Sx_aSlxwP_hqOijW-dFA==)
4. [scribd.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHPYPWh0RKSlo8M4POsRX9mK5ZtnyOxS0fqxFQ78Bq2WYjo74SJCKapco_UclBpOv2TaKxGr6ruXCdfiAr6EPnTWYhKOoKcMudKHu0QurQIEKd4RAPh4MredLZjeT-TFQzHxQQAiK6YyiDo0caQpFckfQ_mBCrK5BI=)
5. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHjBAQM2Gyz82jU2MYb6oeEjh7JHcMJV90xy5D3aIIKODZCnd0r70JK58YFadsJWWmsiVlyd5HmMHqR2l5o_UP-JiSIJ29qzmRQ-PDucNzthTmxvw-8-LD8ERuaq0EbaBDf98tEFmqmP1IBV9xFqgHcYsaxWHHLG5Lj0hb_GZXGHM2CsYyEUryt9wOOxUt3YW_ImcOpnjxwaTEuhwjnxajwconcH7G6ICj2cnJM_RucSHGTWAxq8qrmGixkKhdOPUJTZ5oVBw==)
6. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFCgGaFcVsBR--eM1pgPvFQCGTQ9C86Y_Fft-k9SvG-oaVJoVuk8sI9MJIsQmA2wioE9LX6LLiAtoORzS_Oyx0h5sGsGnbPE8gkDjPyQW_YBAIPqRTA70TCTDNuk76WlgQ3g-F07nUbXqVKBAAib0xcuc-VTYnOhbnCz3BZ5SBrv8kYlGJGnF90jPQsuGdc3NkjWzmsQNQhnjDtWIqmLUvUVSl_s8lAi5F4p6sZb5z1pC7KGFSLyQb7LhkraYppw_ShNf_Yz7LygJ88X_g8FcI2YI37aAciIzFbXXbw)
7. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHaaGwg-MYjZpzMlsxRZkGOZ2VJ1ylbmqc8j08Q-6tqOiiPNphyZkp0VWNnqyttmxW1Ho3O5LYv1A21_4hUsAUqK1xqMc0_Iny1g1ETQ9i1hg-lzfP1uA==)
8. [uu.nl](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF7B_RuTrr2gyx5lORq9gMCPMMVky90z9JXqfdAmDOBwbCnbkRyS9cAmjYyA4b0V0ryD2F4RaUvNeioj7zQs9qxFct67huiFz_G5ySSktNxx5MVQ8Lc6oqNZJNp6Tk2fgqkPveO0BraBIIJuXMbqZ5x9mC8Gpljj-9JU2fgK48u1Uf6Vv25u3DaHfvn6WkbyW6StxQFJvd7leOIobPQtp8OUyaUej2zB5NLaoeaZkmwE4PR)
9. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEKHUdSpjpfUdHNI0NzgeXARvFvcssGcwHUBznCM-GaOKTR8yAhGwmjeGJBcJuvx46ObbyGThsLE5S4uSA-Pq6kef2AUq2TlVTFWMlxVT8KRGxjfwnj0ct1Ncv4jWSIBSNDfr5Ksw==)
10. [hexaly.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGf45-giw9bu0M5X3upaS_J1UivWc6E3X0_NzpKJIFamqpKHbSSVmt06YOSFy8W9maQ3nOjf2WQLACi4jNcwVR_PlelVbprIMqKY3ZUxWZsfCPHaV5yndgpJ3DwshXLunIW4jVoiHw9CcfEsi4naqvEUWIVn_c=)
11. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG6d_tNoi9CXGdXeetkmlX_ENl5d2ngqFDJoB3ciEWB-5DCVsbWIhDT47mgQQdpb3BiwcsKReCAmVv8IK_Gl6qJTo-elq98ecJZPcYaaksfsEUR_cradw==)
12. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFhZt2i8A9oHEPCTnXliR3nNVKPzp-WbmTlSSjZcVtOMhO8pi7rkon4QC8ciUXZ1ZF5hYXuDN3pqaYVSv44EILQuBJCMl1ywJpocnRrXjj4panw3cfEfbJTKf2b9sC7)
13. [nih.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG0qIjYFdSGRntzNl_JOMbgoKu3uLnsFlTE4uUBp5RnxCURC3JaiEHuUua_n_u8GJbRXBjH2J-KzjL8Rxg8KS7YSLXau8WRLndDvQxpF4n5Mm7FmhEwrH1Hz1ofX9caEQCLNwPOQCE-AA==)
14. [waset.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEg0Fd64JB4kc9AWo-jLDe3G_Uy_jLa3SMAMUQR8wnoRj1BH8MFtbxNwCADLcxKkLnWuWbi_0aWTfVljow_wp7pSZZK2uCs05YnB_889tVhsfLowpgJ8F5l_exvYK7OchUHqoh2hD_5cMeTmlJwj6wiv80nVRk65DGxCO__IWbPgcg32v_Evsnlk8MNGPwZ_uxfmMiXj-vNcSabopF8J2Xe1FHpsJ3kOv5dbXdXfyvF)
15. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHNiQEFa_6qTmagc1EIAErVLAIpcKjEXcSR4YYinTV8-rmKaCLveSS2qRNLt1aYLf-I7wddwer5-MBq_smhYRwV26NkJTCMC8bSWKhBV49tfy93lXgDjmeP-CoR32kbEttsRjrqM34GbzH2nw_VrfPhFfjzwvouoyPa9GdF73L7twTjklAsT8b5p0SsWEty3Qmxq79HRhaVntgByC1kthI=)
16. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGMmPF4t91O9mRUurmsl40mss-RlkZaUXKlrZVfKO1U31haZBsdOQZ3T5BINhBNJ51Y3tWkV0dHGMhxz9LP8nUEUWJEtxkS8cu_Ta0PWb9IT863Z-dT6_ZGro4A0ek=)
17. [hexaly.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHZosZ4U7TSk65tSccUHoTKXTxf5u-E7lXzOZSZdLZkcUtmaW82_iafLHSRIo_SEnhVkvwI2WH67g4Ilxh-ZYrCdQPNXPRuRGyJ1A3XtvCqSjA0ghyVJCQVR7xhZtXc-mjuUdb_BCjF8PLaYEkOsTy2uppGB-pTWkEekgd8ErxIjqD799mKksa0vGCNB7si6TVt6w==)
18. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHBl9nZowfbDGGVSA7oaFBrwb6H5WX8ZtsvQa7TnX_BgVntUqCRjp4KTihZn1ldNGwhNCeTBRXb8bBo7nAMBsBF--w2DEn6VFLCOQ5kgGks81ldHD2N4mmp_TjPp6A=)
19. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEmTjT3XTOnbPT-VThSCtCBn3qKXrpDCZ3jajAys59LwP6xRdufb4bat7nGTpnVeBYRNnmoWaz3kThfxH8rciHhfot3XK_zhXA1wxYjkU8J_bW4I4I49d2K0mOUPnbW7dTOPQmb6vZHLl_hzxBI3bQ1WsmVYnWXPI_RJ2GgbR09UtUdI10WX-pCN940sms4epniyLm3itK3EPgo2094FFCz-fShaBKmPHrkMNDT7YgXaEjikRCsxvvGYf-i3BwM7zoNMSCBnFpHXL8yzYGVabBO4Nz-zODrlg==)
20. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFMfUzKasULwfpokPLg1tHZhY1PNzIhIRWu3327TXY2YvavlOr_Av5NcWgxnui-JfodARIBEO3qmTqsDAj9i-ifYQE64yjGyIZ562MbJRY0Wyz_0VvsrGqHKm920iMJx94-tZPQgaE=)
21. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHb_0c4B0DHy4BJ4havdDuPiPbo5R3MZfNYs7bX3Btl2Mzud6FXwTO35WpGSskPLRm_dYe-dRZt9wWYbM7GqE28BQkUdcwhyAW5H_1Wp7-x7z5fDfd_MpRo9WPnxFSM)
22. [techscience.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHgfEwEUWPKf62Zg9renlti7o21VS_0o5Xgm_h1kStHqyXVMwtPe6rmhr4MdU90_TVrLzYaPh14Ie6mRahCErIFKgg3xYmz5594YXS6TYUSC8Gz8vSCRTyMNquKd95D9C9EaS929Q==)
23. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEZaWL_HW-MMv9VxOv79vQJqstnnndg_0Iv96KBjDXvJKKztRzejkSLs5F3qurEOV7q2Bqe_LjF3zaRyoDw3oIyHQMWIWs0b6a709nTpYGSIHeRWdrvVHEFWHfPX_I=)

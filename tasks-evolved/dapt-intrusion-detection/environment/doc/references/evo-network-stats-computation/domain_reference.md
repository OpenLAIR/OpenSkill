# Domain Reference for evo-network-stats-computation

**Responsibility**: Take extracted feature arrays and compute every metric: protocol counts, duration, packets-per-minute buckets (avg/max/min), size stats, Shannon entropy (IPs and ports), unique ports, directed graph metrics (nodes/edges/density/degree), IAT mean/variance/CV, producer-consumer ratio, flow counts (unique/tcp/udp/bidirectional), and analysis flags. Read the CSV template preserving comment lines, fill in values, and write back.

**Key functions to implement**: compute_protocol_counts, compute_time_series_stats, compute_size_stats, compute_shannon_entropy, compute_graph_metrics, compute_iat_metrics, compute_pcr_metrics, compute_flow_metrics, compute_analysis_flags, read_csv_preserving_comments, write_csv_preserving_comments

---

## 4. Shannon Entropy Computation


Shannon entropy is a measure of uncertainty or randomness in a dataset. In network analysis, high entropy in destination ports implies horizontal port scanning, while low entropy in payload sizes may suggest automated beaconing.

The formula for Shannon entropy in bits is:
\[ H(X) = - \sum_{i=1}^{n} p(x_i) \log_2(p(x_i)) \]
where \( p(x_i) \) is the probability of occurrence of the \( i \)-th unique value.

## 5. Pandas 2.2.2 CSV Handling: Preserving Comments


A common issue when parsing external datasets or metric logs involves comment strings representing metadata (e.g., `# Capture Start: 2023`).

## 6. Time Bucketing for `packets_per_minute`


Time bucketing transforms a continuous stream of packets into discrete time-series windows, critical for anomaly detection.

## 7. Inter-Arrival Time (IAT) Calculations


The Inter-Arrival Time (IAT) is the temporal difference between consecutive packet observations.

## 8. Network Density Formula


Network density quantifies how highly connected a network is, represented mathematically through graph theory. 
For a **directed graph** (where A -> B is distinct from B -> A), the standard mathematical formula for maximum possible edges is \( |V|(|V| - 1) \), where \(V\) is the number of nodes (IP addresses).

Thus, the standard formula for Directed Graph Density is:
\[ D = \frac{|E|}{|V|(|V| - 1)} \]
This confirms that **we do not divide by 2** for directed graphs. Dividing by 2 applies strictly to undirected graphs where an edge (A,B) and (B,A) are conceptually identical, meaning max edges are \( \frac{|V|(|V|-1)}{2} \). In IP networking, communication flows are inherently directional, meaning the standard non-divided formula applies.

---

## 9. Bidirectional Flow Counting


A network flow is fundamentally a logical session between two endpoints. 
*   **Unidirectional flow**: Defined strictly by the 5-tuple: `(src_ip, dst_ip, src_port, dst_port, protocol)`.
*   **Bidirectional flow (BiFlow)**: Consolidates both the forward (`A -> B`) and backward (`B -> A`) unidirectional packets into a single cohesive session record [cite: 23, 24].

## 10. DAPT2020 Dataset Characteristics & Analysis Context


The **DAPT2020 (Dataset for Advanced Persistent Threats 2020)** is an extensive benchmark dataset carefully simulating an APT attack within a cloud network infrastructure over an uninterrupted five-day span [cite: 25, 26, 27, 28, 29].
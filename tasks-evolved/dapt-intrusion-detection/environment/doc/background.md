# Comprehensive Guide to Building a Reusable PCAP Analysis Utility Module Using Scapy 2.5.0, Pandas, and NumPy

### Leading Summary
*   **Scapy PCAP Processing**: Large PCAP files should be processed using `PcapReader` as a generator rather than `rdpcap()` to prevent out-of-memory errors. A 32MB PCAP can consume hundreds of megabytes if loaded entirely as Scapy objects.
*   **Layer Access and Lengths**: Scapy allows precise layer detection via `haslayer()`. Packet length on the wire is best retrieved using `packet.wirelen`, while `len(packet)` gives the reconstructed byte length. 
*   **Timestamp Precision**: Scapy 2.5.0 uses `EDecimal` for `packet.time`, preserving precision but breaking standard float arithmetic. Casting via `float(packet.time)` is required.
*   **Protocol Pitfalls**: Checking `haslayer(TCP)` is more reliable than checking `IP.proto == 6`. ARP packets do not contain IP layers. ICMP packets are encapsulated within IP layers.
*   **Statistical Analysis**: Inter-arrival time (IAT) variance should be calculated using sample variance (`ddof=1` in NumPy) because a PCAP is typically a sample of an ongoing network state.
*   **Data Handling**: Pandas `read_csv` with `comment='#'` discards comment lines completely. Custom I/O wrapper functions are required to preserve metadata comments.
*   **DAPT2020 Dataset**: This dataset encompasses complex Advanced Persistent Threat (APT) stages (reconnaissance, foothold establishment, lateral movement, data exfiltration) and necessitates heuristic detection strategies for multi-stage anomalous behavior.

The analysis of network traffic requires robust instrumentation, precise protocol dissection, and rigorous statistical aggregations. While standard libraries such as Scapy, Pandas, and NumPy offer high-level abstractions for network feature extraction, nuanced API behaviors—such as the difference between sample and population variance, memory allocation in file parsing, or Pythonic typing shifts in timestamp formats—can fundamentally alter the validity of an intrusion detection pipeline. The following sections provide an exhaustive academic and practical framework for constructing a PCAP analysis utility module.

---

## 1. Reading PCAP Files with Scapy

The fundamental operation in offline network traffic analysis is the ingestion of raw Packet Capture (PCAP) or PCAPNG files. Scapy provides multiple utilities for this task, but their memory footprints and operational paradigms vary drastically.

### The `rdpcap()` Function vs. `PcapReader`
The `rdpcap(filename)` function is the most commonly referenced method in basic Scapy tutorials. When invoked as `rdpcap("file.pcap")`, it returns a `PacketList` object containing the fully parsed hierarchical representation of every packet in the file [cite: 1, 2]. 
While convenient for small traces, `rdpcap()` forces the Python interpreter to instantiate complex object structures for every packet, layer, and field simultaneously. 

For a file size of ~32MB, the physical size on disk is deceptive. A 32MB PCAP file could easily contain between 50,000 and 150,000 packets depending on the average payload size. Because Python objects possess significant overhead (a single Scapy IP/TCP packet can consume several kilobytes of RAM in object attributes, dictionaries, and protocol definitions), loading a 32MB PCAP file via `rdpcap()` could command hundreds of megabytes, or even over a gigabyte, of memory [cite: 1].

The superior approach for building scalable utilities is the `PcapReader` class. `PcapReader` operates as a Python generator, reading and yielding packets sequentially on demand [cite: 1, 2]. The file is not completely loaded into memory, which allows even multi-gigabyte PCAP files to be processed within a strictly bounded memory footprint [cite: 1].

### Working Code Example: Efficient PCAP Iteration
```python
from scapy.all import PcapReader, IP

def process_pcap_efficiently(file_path):
    packet_count = 0
    total_bytes = 0
    
    # Using PcapReader as a context manager ensures the file handler closes safely
    with PcapReader(file_path) as pcap:
        for packet in pcap:
            packet_count += 1
            # Perform per-packet operations here
            # Objects are garbage-collected after each iteration unless stored
            
    return packet_count
```

By streaming the file sequentially, memory is only allocated for the current packet being processed, avoiding exhaustion regardless of the original file size [cite: 3].

---

## 2. Packet Layer Access in Scapy 2.5.0

Accessing individual headers and fields accurately is critical for feature engineering in machine learning models.

### Checking for Specific Layers
To verify if a packet contains a specific protocol, the `haslayer()` method is preferred. For instance:
*   `packet.haslayer(TCP)`
*   `packet.haslayer(UDP)`
*   `packet.haslayer(ICMP)`
*   `packet.haslayer(ARP)`
*   `packet.haslayer(IP)`

Alternatively, the `in` operator is syntactically equivalent and highly readable (e.g., `TCP in packet`).

**Import Paths:**
Using `from scapy.all import *` imports every Scapy component into the global namespace. While acceptable for interactive sessions, it pollutes the namespace and increases module load times. Best practice dictates explicit imports from specific protocol namespaces:
```python
from scapy.layers.inet import IP, TCP, UDP, ICMP
from scapy.layers.l2 import ARP, Ether
from scapy.utils import PcapReader
```

### Retrieving Packet Length
There are crucial distinctions between packet length properties:
1.  `len(packet)`: Returns the integer length of the reconstructed packet within Scapy. If Scapy successfully dissects the packet, this gives the total byte length of the headers and payload.
2.  `packet[IP].len`: Extracts the explicitly declared `Total Length` field strictly from the IPv4 header. This indicates the size of the IP header and its payload.
3.  `packet.wirelen`: Introduced and populated when reading from PCAP files, this attribute specifies the raw frame length of the packet **as it appeared on the wire**, regardless of how much of the packet was truncated (e.g., due to a `snaplen` constraint during capture) [cite: 4, 5]. If you require the exact total bytes transmitted over the network for bandwidth calculations, `wirelen` is the most accurate representation [cite: 4, 6].

### Extracting IP Addresses and Ports
IP addresses and ports can be accessed via bracket notation, treating layers as dictionaries. 
*   `packet[IP].src` and `packet[IP].dst` return standard Python string representations of the addresses (e.g., `'192.168.1.5'`).
*   `packet[TCP].sport` and `packet[TCP].dport` (or `[UDP]`) return integers representing the port.

**Pitfall**: If you attempt to access `packet[TCP].sport` on a packet that only contains UDP, Scapy will raise an `IndexError: Layer [TCP] not found`. Always conditionally check `haslayer()` before accessing layer-specific properties.

### Handling Timestamps in Scapy 2.5.0
A critical update in recent Scapy versions (including 2.5.0) involves how timestamps are parsed. Historically, `packet.time` was a standard Python `float`. However, to prevent floating-point precision loss during high-resolution captures, Scapy introduced the `EDecimal` (Enhanced Decimal) type for timestamps [cite: 7, 8].

**Pitfall**: The `EDecimal` type does not inherently support direct arithmetic operations with standard floats, often raising a `TypeError: unsupported operand type(s) for *: 'float' and 'EDecimal'` [cite: 7, 9]. 

For inter-arrival time (IAT) calculations, you must explicitly cast `packet.time` to a float (which represents seconds since the Unix epoch):
```python
current_time = float(packet.time)
```

### Determining Protocol Numbers
The `IP.proto` field contains the integer identifying the next encapsulated protocol. Standard IANA mappings apply:
*   TCP = 6
*   UDP = 17
*   ICMP = 1

---

## 3. Protocol Detection Pitfalls in Scapy

### ARP vs. IP Layer Dynamics
Can a packet have both ARP and IP layers? **No.**
ARP (Address Resolution Protocol) operates at the Data Link Layer (Layer 2) to map MAC addresses to IP addresses. While ARP packets carry IP addresses within their payload data structure (Target/Sender Protocol Addresses), they are encapsulated directly inside Ethernet frames, bypassing the standard IPv4 (`IP()`) header [cite: 10]. Consequently, `packet.haslayer(ARP)` will be `True`, but `packet.haslayer(IP)` will be `False`.

### Counting Protocols: `haslayer(TCP)` vs. `IP.proto == 6`
For tracking "protocol_tcp", it is overwhelmingly more reliable to check `packet.haslayer(TCP)` than to check `packet[IP].proto == 6`. 
If an IP packet is deeply fragmented, or if the PCAP `snaplen` truncated the payload before the TCP header could be fully captured, the `IP.proto` will accurately state `6`, but Scapy will not generate a TCP layer because the bytes are missing. Counting based on `IP.proto == 6` tells you what the packet *intended* to be, whereas `haslayer(TCP)` tells you if the packet data is actually available for deep-packet extraction.

### ICMP and IP Encapsulation
Do ICMP packets have an IP layer? **Yes.** 
ICMP is an auxiliary protocol to IP and is encapsulated within an IP header (with `IP.proto == 1`). Therefore, any metric titled `protocol_ip_total` should indeed include ICMP packets, as well as TCP and UDP packets [cite: 10, 11].

### IP Packets without TCP/UDP/ICMP
A packet can certainly contain an `IP` layer but lack TCP, UDP, or ICMP. Network traffic includes dozens of other protocols riding over IP, such as IGMP (Protocol 2), ESP (Protocol 50), AH (Protocol 51), OSPF (Protocol 89), or SCTP (Protocol 132). If your logic assumes `haslayer(IP)` guarantees L4 ports, it will crash on these packets.

---

## 4. Shannon Entropy Computation

Shannon entropy is a measure of uncertainty or randomness in a dataset. In network analysis, high entropy in destination ports implies horizontal port scanning, while low entropy in payload sizes may suggest automated beaconing.

The formula for Shannon entropy in bits is:
\[ H(X) = - \sum_{i=1}^{n} p(x_i) \log_2(p(x_i)) \]
where \( p(x_i) \) is the probability of occurrence of the \( i \)-th unique value.

### Working Code Example (NumPy and Python `Counter`)
```python
import numpy as np
from collections import Counter

def compute_shannon_entropy(data_list):
    """
    Computes Shannon entropy (in bits) of a list of values (e.g., IPs, Ports).
    """
    if not data_list:
        return 0.0
    
    # Calculate frequencies using collections.Counter
    counts = Counter(data_list)
    total_elements = len(data_list)
    
    # Calculate probabilities
    probabilities = np.array([count / total_elements for count in counts.values()])
    
    # Handle the edge case of 0 probability, though Counter only yields counts >= 1
    # For a single unique value, p = 1.0, log2(1.0) = 0, H = 0.
    entropy = -np.sum(probabilities * np.log2(probabilities))
    
    # Prevent negative zero outputs caused by floating point precision
    return max(0.0, entropy)

# Example:
ports = [cite: 12]
print(f"Entropy: {compute_shannon_entropy(ports):.4f} bits") 
# Edge case:
print(f"Entropy (Single value): {compute_shannon_entropy()} bits") # Output: 0.0
```

---

## 5. Pandas 2.2.2 CSV Handling: Preserving Comments

A common issue when parsing external datasets or metric logs involves comment strings representing metadata (e.g., `# Capture Start: 2023`).

### The `comment='#'` Pitfall
If you use `pd.read_csv("data.csv", comment='#')`, Pandas will completely skip and discard all text on any line following the `#` character [cite: 12, 13, 14]. This means the comment lines are lost in memory and cannot be preserved when writing the DataFrame back to a file. Pandas is designed exclusively for structured tabular data and drops unstructured metadata natively [cite: 15].

### Best Approach: Custom I/O Wrapper
To preserve the exact format with comments, you must decouple the file reading/writing process from Pandas' native CSV ingestion engine [cite: 15, 16].

**Working Code Pattern:**
```python
import pandas as pd
from io import StringIO

def read_csv_with_comments(filepath):
    comments = []
    data_lines = []
    
    with open(filepath, 'r') as f:
        for line in f:
            if line.startswith('#'):
                comments.append(line)
            else:
                data_lines.append(line)
                
    # Read the valid data into Pandas using an in-memory buffer
    df = pd.read_csv(StringIO(''.join(data_lines)))
    return df, comments

def write_csv_with_comments(df, comments, filepath):
    with open(filepath, 'w') as f:
        # Write comments first
        for comment in comments:
            f.write(comment)
    
    # Append the DataFrame content without altering the comments
    df.to_csv(filepath, mode='a', index=False)

# Usage
# df, preserved_comments = read_csv_with_comments('metrics.csv')
# df['value'] = df['value'] * 2  # Modify metric rows
# write_csv_with_comments(df, preserved_comments, 'metrics_updated.csv')
```
This algorithm ensures that zero metadata is destroyed during the analysis loop [cite: 15, 16, 17].

---

## 6. Time Bucketing for `packets_per_minute`

Time bucketing transforms a continuous stream of packets into discrete time-series windows, critical for anomaly detection.

### Methodology
To bucket packets into 60-second intervals based on their float timestamp:
1.  Select an anchor time (e.g., the timestamp of the first packet, `t0`).
2.  For every packet timestamp `t`, calculate the bucket index: `bucket_id = int((t - t0) // 60)`.
3.  Store metrics (counts, lengths) inside a hash map or array indexed by `bucket_id`.

```python
from collections import defaultdict
import numpy as np

time_buckets = defaultdict(list)
t0 = None

for pkt in packets: # Assuming efficient PcapReader loop
    ts = float(pkt.time)
    if t0 is None:
        t0 = ts
        
    bucket_id = int((ts - t0) // 60)
    time_buckets[bucket_id].append(pkt.wirelen if hasattr(pkt, 'wirelen') else len(pkt))

# Calculate stats per bucket
for b_id, sizes in time_buckets.items():
    pkt_count = len(sizes)
    avg_size = np.mean(sizes)
```

### The Partial Bucket Dilemma
At the end of a PCAP file, the final temporal bucket may represent only a fraction of a 60-second window (e.g., capturing ends at second 45). Including this bucket in rate calculations (like `packets_per_minute`) will artificially depress the rate, creating a false anomaly drop at the end of the time series.
**Standard Approach**: In rigorous traffic analysis, the final, unclosed partial bucket is typically **discarded** when evaluating continuous rates, or mathematically normalized up to a 60-second equivalent if total volume accounting is required.

---

## 7. Inter-Arrival Time (IAT) Calculations

The Inter-Arrival Time (IAT) is the temporal difference between consecutive packet observations. 

### Calculation and Statistical Dispersion
1.  Extract all timestamps and cast to `float`.
2.  Sort the timestamps chronologically (if the PCAP capture was asynchronous or multiplexed).
3.  Calculate consecutive differences: `iats = np.diff(timestamps)`.

Once the array of IATs is collected, metrics such as mean, variance, and the Coefficient of Variation (CV = standard deviation / mean) are computed to characterize traffic flow.

### Sample Variance vs. Population Variance (`ddof`)
When computing variance, a crucial statistical decision arises regarding Delta Degrees of Freedom (`ddof`). 
*   NumPy's `np.var()` defaults to `ddof=0` (Population Variance) [cite: 18, 19, 20]. This formula divides the squared deviations by \(N\).
*   Pandas' `df.var()` defaults to `ddof=1` (Sample Variance) [cite: 18, 20]. This formula divides the squared deviations by \(N - 1\) (Bessel's correction) [cite: 18, 21].

**Which is standard for network analysis?**
A packet capture file represents a *finite sample* drawn from a continuous, hypothetically infinite population of network traffic generation [cite: 18, 21]. Therefore, the unbiased estimator for the variance of the underlying network behavior must utilize **sample variance** (`ddof=1`) [cite: 21, 22]. Using population variance (`ddof=0`) will systematically underestimate the true variance of the network's IAT generator [cite: 21].

```python
import numpy as np

iats = np.diff(sorted_timestamps)
mean_iat = np.mean(iats)
# Correct usage for network sampling: ddof=1
var_iat = np.var(iats, ddof=1)
std_iat = np.std(iats, ddof=1)
cv_iat = std_iat / mean_iat if mean_iat > 0 else 0
```

---

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

### How are BiFlows Counted?
In standardized network flow analysis (such as IPFIX/NetFlow modifications), if traffic exists where Endpoint A sends to Endpoint B, and Endpoint B responds to Endpoint A on the mirrored ports, this is represented as **one (1) bidirectional flow** [cite: 23, 24].

To implement this programmatically, one standardizes the 5-tuple key to be directionless by sorting the IP addresses and ports to guarantee a deterministic hash key regardless of the packet's origin direction [cite: 23].
```python
def get_biflow_key(pkt):
    ip_a, ip_b = sorted([pkt[IP].src, pkt[IP].dst])
    port_a, port_b = sorted([pkt[TCP].sport, pkt[TCP].dport])
    proto = pkt[IP].proto
    return (ip_a, ip_b, port_a, port_b, proto)

# Flows A->B and B->A will result in the exact same biflow_key
# The length of the unique keys determines the count of bidirectional flows.
```

---

## 10. DAPT2020 Dataset Characteristics & Analysis Context

The **DAPT2020 (Dataset for Advanced Persistent Threats 2020)** is an extensive benchmark dataset carefully simulating an APT attack within a cloud network infrastructure over an uninterrupted five-day span [cite: 25, 26, 27, 28, 29].

### Traffic Topologies
Unlike older, simplistic datasets, DAPT2020 encompasses public-to-private and internal lateral movement traffic [cite: 27, 30]. 
Day 1 encapsulates benign, normal baseline behavior. Days 2 through 5 meticulously map out successive APT attack stages:
1.  **Reconnaissance**: Initial scans to map the network structure [cite: 25, 29, 31].
2.  **Foothold Establishment**: Bruteforcing or exploiting identified vulnerabilities to gain access [cite: 25, 28, 31].
3.  **Lateral Movement**: The attacker moves from the compromised entry node to internal servers (SMB, SSH) [cite: 25, 31, 32].
4.  **Data Exfiltration**: Extracting sensitive payload data to external Command & Control (C&C) servers [cite: 25, 28, 31].

### Signatures and Analytical Thresholds
The dataset is notorious for containing port scanning, Denial of Service (DoS), and beaconing mechanisms, representing advanced attacker toolsets (like Nmap, Metasploit, PyExfil) [cite: 25, 26, 29]. Detecting these requires precise metric thresholding using your Scapy toolset:

1.  **Port Scanning (Reconnaissance Phase)**:
    *   **Indicator**: A solitary source IP initiating connections to an abnormally large number of unique destination IPs (Horizontal Scan) or destination ports on a single IP (Vertical Scan) within a condensed temporal bucket.
    *   **Detection Strategy**: High Shannon entropy on destination IPs/Ports. A standard rule sets an alert if a single source hits >100 distinct ports on a target within 60 seconds.

2.  **Denial of Service (DoS)**:
    *   **Indicator**: Severe spikes in unidirectional packet transmission rates (packets/sec) targeting a specific node or service [cite: 25, 26].
    *   **Detection Strategy**: Calculate volume per time bucket. If `packets_per_minute` exceeds the baseline mean by more than 3 standard deviations (z-score > 3), a volumetric DoS signature is registered.

3.  **Beaconing Behavior (C&C Communication)**:
    *   **Indicator**: Automated malware "calling home" creates network requests at highly regular intervals, minimizing variance in IAT. 
    *   **Detection Strategy**: Calculate the Inter-Arrival Time (IAT) Coefficient of Variation (CV). Human-driven traffic is "bursty" (CV > 1.0). Automated beaconing yields incredibly consistent timing, resulting in an abnormally low IAT CV (e.g., CV < 0.1). Combining low IAT variance with consistent byte-sized payloads serves as a definitive beaconing indicator.

Constructing a Python-based utility leveraging Scapy, Pandas, and NumPy necessitates strict adherence to these statistical truths and memory management practices. Proper application of these concepts will yield an industrial-grade threat hunting framework capable of decoding datasets as intricate as DAPT2020.

**Sources:**
1. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGw-HDOKOg3nq2N7fhYxYOIM2-ngEe8MUwUmUJuW_vYN34akAGmf63O_YJl0fYYlKJp-cCa54olCJ2lU90M_FbrchrcumDuW56V4hhLqQfn-WhDCNBvE9QyPQPnUx58T960I3_Nxvy-C_hkgqPNo8tH_nuQZ-k4qIFNiw==)
2. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH_Wdujw4B8ItSMo6mrgGtALz40Fi1sVLI7yveDQnr1mbvAAlHhRXXoXzx4Ya8XlLPqrNrsMwGISkyUYOFCeXt-NvDP0ttQAmQ0AOOLo6jhc1xw5_PhZcPTj3pjrMwofn3lxj6zJNrdF-2F5Gb-82QPpeIN0TQ7vNncwPEBezTCzumrjFMFcRO8s73yl9sNFwnW1IIlMnvv1aakVuf6mVwO)
3. [oneuptime.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQECU-TFwdKj70A2pyzekt2FTeAInvkqzT6hygcKTMBqWHCVPSeU9mJ43hhZHK6Fbp3DlorJ0NG8TR7-5BKFW8FPxaNgx_ZHlrlW76VgUiBGWWPUe3q3Nh2eg1MNylZ7kI5ap8GHVZ8BuMjE9VhwdgbHbvOUHuWhlzQZ3zTQ)
4. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEOaT9GXSA47Od6SsloVteglMTowkfGAkOEYM1CUNY__K7VIqKH6pJRv2__sLBbZWLQoi9awS-m7haEHo72hY1R3QJHTPZUkOfS-3pxizjM6qbhaNbHJC7C5LyoVHBJpCKx96wf0m_5AGlWEd1dqNUa)
5. [cisco.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGhKl3q0yg-IR9-wVMqhzdia94OUCMNdixIYq1hyImIxdflGiMRtXw_dRUk2z9f3gHwK_qhj4fZF1wkQyec1zkR5XzNBWuGdHq0amkp74OM50v6IBtNvkSG4KZEotGHO6vrxKSRf9OzITKbIQ-U2ZG-oVbYBU2FyXdo)
6. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFATLcneS6jL0wj4hCqKvOLVawyv16Y_y8O-fbGw9VmGRpaNuxyG5OYOOf445J00_et3DXTbFZ8IVvQK2l5ZXR70a8dzeZ5vfW6qix0XdmpFT_k1PgfnStTcxeETVKvnFP7CjtFrgt3J7hs8hQ01y3bUZlCWzAv1C8jHPc=)
7. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHzBd0VErYfaSefAo0q_J2y22MNg12eXJ5dg2SyvEpDuw2purDa3pQTTZEEXeNO2YZdIzJhmIiIESuqcgWOVcG-HOQU5JcGKwIFXkuJI0ZrV8xbMGAQLuFsdFeLuFI-Ui4=)
8. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE2hFvP9C1ULY1PSfxzLtso2nZkI9SH0pMVfgJiQ8o-3lKJUuuWVXi6qpp6SrGu1wJhTQqwd_OWnWqZ_kZ1vfJ0S6pRi9tv4ma91_mMz7QuIcNbcgKwgQxyHPVu7Dm_IUgl-2lqwOpM)
9. [gitlab.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFoXIvQ-XLy8I08fVFtxr4ointQnMc0Ghl6vkgch6nQgVg_sEsifG5AeHbXF8s44iFnhe1ELsSqHOC5tnPw8fFXyMwnR4gBER3jSARTzgYBur7_dRRDvlu6TDwKoHtaSKnshRVqG1Kd)
10. [dev.to](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHmkUVPy1ZB89ewy-DJIEgAHFihgKK8S8TIrm59a8xgPaVmXIb9-wAOKojbkZqSbX3Pd6kvojZm8YtALh223sAOr8podL6veCL905iL-gPHzfbgutf7q1PIUxOSEwBLHDLyTjXiMQENMHo3D5ZZZm69gldWONSgYmOXvEvQxr9xZwK0ugoHSSvZyGyPZ66u0isLcXkhGweOYMooFrMFr3A06werFVFObg==)
11. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEuRZXksHHszroYnlIyjJq7S6InDsPQl6lrzmuraEJa8-HjDzMbnDPl9tC05ItdHQUAEFmmrFJP8lxSWVzNltm1wQaTvlK1vzkO7uKuQ-fs-gyrueqG9MgA5J2OX6ONf-0_obdINH0=)
12. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFS9THbO2lZdA5NtSP_1-1VsJJDdG8myGHccFIPYmt3yyrfi3hht8ildybxnz3wa2z1WonqT-9Jboj6Pf_Ko0szqy0X508w5q5az8208f64MfNXdsNUUtJnfB-oz0WrJsgHvExRo2_6y7f-OiEAhywTDl3R2aoW)
13. [towardsdatascience.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFniPofgAKjUhu2ruQ7fegbR-m3YmYmGZekS0UOVU67Nu4ziMjbXkNArjEl3YDFxs4Q5pJ-ABfGy-OaLrIQCGeetguo3vjzktSQ25wcJ7TSM-mHLD5mDjKrD2wl0coMz1NBHQ0XL5Q7xThkeG-1ckptBis12WTaqrWKQ_T6Ew==)
14. [pydata.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGhVhL5RNOz20WByf-DOGL9OajhTOaVR5I1N2tYIpS9TjLlqJSPmPUFTIQeZeyfbcrkXPcNCG3aqzaydwzZXcG1o3WLikm5iTkul7skdD5jugk2afp0kduG-6J-iA23J8steLMFpHcoIoP8qGbfJUXZ_AzhOHhRZ23uDqoC-3vbAMD1zTsTx9Q5bw==)
15. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEVRIKCiZKYIl7mRBlptu91Woa7G1VpvwU4edcUmchZySlV23vqvlZBKo0HeSoKapnA7Eie3tjL52x2DD60XHYsCS_oVJZHcshcwHeY2M60A_iXN-MTmjp9PaWKuV88WuOz9OytynEhUbkQg4854AFxnq3d1KJDNr1AcruUvNP3SPIvD8uFywIC)
16. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF2iVDXax6773ICSGXSzleOBzzUWk2GMVVxtqnPxBB_7UxO480qdyERZ5ttS55omEN5AsfoTJSdTG-W5x0rjnn49zPkb0VMjxWoLA9bnL2f9KgV5D-7Tgib5Jjer2KFvAJ368IQiEpZHRacr4ZeCpFc7uyPvV2oM7qMAbxQoDDQDYKYPugnUhyg)
17. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHxoCCND9GV4KvIrGIsdO28o0rH_wF7lVqtM8k_K8N8MFczZCsLi9L1nqcewF_1dKXbRPpCPYN_Sw-uezrQ-05Ca3rixbdnzRhwYTbftPgUdC3wLq0-3EmuzspbHlBpi1BPgqiRtYH9WvWNfYyv2tVcsWej90tZHhVfs3mIg6zm-dFFCObi79X7QJw1sopQTpUpCZxV)
18. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF9pr7T-2lP8cllIeISWjZ661HiqN677tu-aMIOMHMVHcfmCNukz9U372vRE2_7w5Tdi8WSSntP6Z4XruZvd83-bwFvdm1q3CKnwlj6__7LUmCx2iER88fQ_Ar3xY9itkdzq3NsrBBIwlag284htKxP778Fupn6efU2iz1ru9XI3g==)
19. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG8MDNo0W7PP7a515RZbSiuvUYlW2a5_HlNxOQXbdRzGklPjsyAkh07xv-OpRlSl_1e4MNhaZWhLWRznWgCcypv3DU7P01njSv9mNd7Dagg5jh5KD_PEqreaNug0Z3yY9djOT3kVkp2va8KsJOeUNwF5CQtXHHHWPCwZZ-Oa0ucnTA74X_RWM9Rn0LFpYL3JZQvykR_8O0rdYI-Vk-29aZgxb0Q8q4y1VO_jADN)
20. [sderev.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHJxeTrpHLCn-58Dpl-STZAkWJStmpBml8CKmcWM-FhjWmbGoAVGIoTZ3E7uDkAr0QnkrLWzRiYE1GdpE4Lwf7yOfC3ThzI6scipFSeSMcjZzy5)
21. [mortada.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGdiflAsT6cZyvgi-KnF8q56bRuJYsH3cUD5Z5Qw5He_ZrxkeJS-MykVGHsEJX9ZF7bpy0LU4LigA80gSD5urzNZC07fkNKRtY_9Loj_IJf2D4G-qv-0CZ4hG_7mTdjbpRurDLg92VFanwr7lmTqdEm7eMiKDtSnALa)
22. [reddit.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEzjq5qrBWfz6LB6fJEjZEAutUglj10EM0YaNDKBPYPzHnoXROoSIWx0nMbcmjrD21eBC1tq-Snm-7bxdKBq15k0L75CDVxPlCy7xlQGF3XG_yCyHmQwlRfc5TQvlrsr6SBtM_NONvxy0Ahid8la7HOpskmATqr1QC4gbtGbviZuaZb0rPeLzEZ1Q-JVAN9KKgPVzK1tdM3qbn59OU=)
23. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFDvunE9JXfu3IWbsw_WHOAuliBrUkuQabZwhbMmTLIfU7rDQpax843TmkyOtvNhJJdYStXOQtmhByMMybufUVahliywe9QiNThera4969sbOIsihJG1HEN)
24. [muni.cz](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFknwEQPdGumz2HFNLlxMyZKyh4X3Z_xO1XkEJNnmjRY8-4oSnDVHxVy6o_6Wflm5ki3Jg81YrgmyT_N4Sb4M5Ymiulv9e7xMOqR_bn2JvqsnVHUTpPpjTt4IJoiQ==)
25. [nih.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHjJ1qAbcDgxOnx2FDwMoQJ00XTPHWN7ifBvvrgmWDOkifGF1WhhdVu10bflrgb-QDVqaWXfXpITIiKc5gmwMSbtRkP4S_cREsTzqWKt6-Zsx1imqdWOsV1KIkwI7FGtBSzQWavF-dP)
26. [kaggle.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE58jCG5VN1kiR5PExzitxvwiZBlC_1KjThTt5cVt_czFCd_FR5xn1Sn8-y3IegsuO7-RhTuYC4KdEEtYo_vo7JJ4LaBhPISPD6f1GC_CT0ZsET_u3o3prCrZTpFGZcRJJYNtkOvbXAbXEe)
27. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHokS4CWI8o-zCs7yXVjqFkYGqmIISw2gOBSurYBolX6KjG4ZMhf2xvmjgUt5ccN6XSkZCjPO_VhvPcGoajtUDkvNhofQAZ-Y_Up2yovG_bmgBwG_Qfq9cpKY_6MemdbR4V9rcj2WR2CwjBGZjWNY3Rj09be6evZCyNjjYfxaTluhy5pzwo_ViylTAT0o7XCxH_ZKR__-tE3NDGCQhog8IoJ0w5JpF8dM67AUCVJt8pTOEr-iU=)
28. [nih.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHTECMd961zIZ7W95HjKxi0MW98PO8kYn_1A4NDiugD9P6R8IkOd8jVUT-uIrxkeLyQpY6en3z9YD47oMA6Vbx7lpbA8Rr264CJBv5I7X2Ickeis_kFONxDKpl45RjTlT_Sqdg6za_r)
29. [uark.edu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHwgkZvCg6NGZdNz_lzEQXtc2e6jnAk3oYRWDGjjg2mxoIlumyVBMThilMFGDIhKU37pskRb6KxTV1Qd5ET3Wptopo7dR5Ui4ChqS_HNMzlRYBA8Gmp-QoavNaple6ZatQjMFlpkTMTgiONqvZtxSIOFXuPjyBwgX8VViyw2Hvf)
30. [semanticscholar.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGUD9d6VjYCrIl5QO5fY98Amx8T5dwtnR1GWRoRp_Z4kHoG6uKbU7j6fJE5bSTnfoV8w4rN9QYJqNCO3L9f7llOhYj-uU8HaTGCz50RewfV8k0L8KKN2N65F6eRzNx9MqPfPiggQaSoV6cpemx0hxV-VKWWHYRv4OEitFItCkkKPhFVsPVZIsGRJmzdrQeeQhiT4SgfFlWqeQSALPWDlsRe1DmjZyRbybI41o5z5Rb0VKN4_Wcc1UZXNmBFrk0flRBqGtXO)
31. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH0y6YmfLJuqPi327OiqPi6sgIZxZfUejIYjB1myGRou-TmHSanUHwAdigD1UOXsCszBhvSYsmdaqgL12mG_MVl6T2JYdEArmtTKvt6fGXcZN2-mTkoF5n9BpkB1q46G84C8aaPljV5jYTj6wlV)
32. [nist.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHKTlHFmeGC6JRSaZgFD4VcNoeoAe7Bcnggj30B3_ys9yRrQqhK8uPNeFfRLrVqEaMnYoz69-QKj-hFJ4xUl4MCNN1CJZFSvQOPZenyI9PR3LmCmE-DWIZmvZYR-KWQDMsXBnpCTNu_Y7GBjevNzGF8OZo=)

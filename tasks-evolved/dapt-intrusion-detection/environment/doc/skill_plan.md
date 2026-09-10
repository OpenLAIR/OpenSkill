# Skill Creation Plan

**Task**: Parse packets.pcap with Scapy, compute ~35 network statistics (protocol counts, timing, sizes, entropy, graph metrics, flows, analysis flags), and fill in the value column of /root/network_stats.csv while preserving comment lines.

**Rationale**: The task involves three distinct concerns: (1) efficient single-pass PCAP parsing and feature extraction into structured data, (2) computing diverse statistical metrics from the extracted data, and (3) writing results back to the CSV while preserving its comment-line format. Since the PCAP parsing is the performance bottleneck and all metrics derive from the same extracted features, a two-skill decomposition separates data extraction from metric computation+output, keeping skills focused and reusable.

**Number of skills**: 2

---

## Skill 1: evo-pcap-feature-extraction

**Description**: Efficiently reads a PCAP file using Scapy's PcapReader in a single streaming pass, extracting per-packet features (timestamp, length, protocol flags, IPs, ports) into lists/dicts suitable for downstream statistical computation.

**Responsibility**: Single-pass PCAP ingestion: iterate packets via PcapReader, detect layers (TCP/UDP/ICMP/ARP/IP) using haslayer(), extract timestamps (cast EDecimal to float), packet lengths (len(packet)), source/destination IPs and ports. Return a structured dict of lists containing all raw feature arrays needed for every metric category.

**Key functions**: `extract_packet_features`, `get_packet_length`, `get_protocol_type`, `get_ip_port_fields`


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-pcap-feature-extraction/domain_reference.md`. Read it before implementing this skill's scripts.


## Skill 2: evo-network-stats-computation

**Description**: Computes all required network statistics from extracted packet features and writes results into the CSV template, preserving comment lines. Covers protocol counts, time bucketing, size stats, Shannon entropy, directed graph metrics, IAT stats, PCR, flow analysis, and boolean analysis flags.

**Responsibility**: Take extracted feature arrays and compute every metric: protocol counts, duration, packets-per-minute buckets (avg/max/min), size stats, Shannon entropy (IPs and ports), unique ports, directed graph metrics (nodes/edges/density/degree), IAT mean/variance/CV, producer-consumer ratio, flow counts (unique/tcp/udp/bidirectional), and analysis flags. Read the CSV template preserving comment lines, fill in values, and write back.

**Key functions**: `compute_protocol_counts`, `compute_time_series_stats`, `compute_size_stats`, `compute_shannon_entropy`, `compute_graph_metrics`, `compute_iat_metrics`, `compute_pcr_metrics`, `compute_flow_metrics`, `compute_analysis_flags`, `read_csv_preserving_comments`, `write_csv_preserving_comments`

**Depends on**: evo-pcap-feature-extraction


> **Reference**: Domain-specific knowledge for this skill is in `references/evo-network-stats-computation/domain_reference.md`. Read it before implementing this skill's scripts.


---

## Instructions for Agent

1. Create skills in the order listed above (dependencies first).

2. For each skill, read its reference file in `references/<skill-name>/` FIRST.

3. Follow the responsibility boundaries strictly — do NOT overlap functionality.

4. Each skill must have YAML frontmatter (name, description) in its SKILL.md.

5. Write utility functions in each skill's `scripts/` directory.

6. After creating all skills, write a main script that imports from all skills.

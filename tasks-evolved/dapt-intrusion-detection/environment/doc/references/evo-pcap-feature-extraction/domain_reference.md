# Domain Reference for evo-pcap-feature-extraction

**Responsibility**: Single-pass PCAP ingestion: iterate packets via PcapReader, detect layers (TCP/UDP/ICMP/ARP/IP) using haslayer(), extract timestamps (cast EDecimal to float), packet lengths (len(packet)), source/destination IPs and ports. Return a structured dict of lists containing all raw feature arrays needed for every metric category.

**Key functions to implement**: extract_packet_features, get_packet_length, get_protocol_type, get_ip_port_fields

---

## 1. Reading PCAP Files with Scapy


The fundamental operation in offline network traffic analysis is the ingestion of raw Packet Capture (PCAP) or PCAPNG files. Scapy provides multiple utilities for this task, but their memory footprints and operational paradigms vary drastically.

## 2. Packet Layer Access in Scapy 2.5.0


Accessing individual headers and fields accurately is critical for feature engineering in machine learning models.

## 3. Protocol Detection Pitfalls in Scapy


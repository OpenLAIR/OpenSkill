---
name: evo-pcap-feature-extraction
description: Reads PCAP via Scapy PcapReader, extracts per-packet features into numpy arrays.
---
# evo-pcap-feature-extraction
## Usage
```python
import sys
sys.path.insert(0, '/app/environment/skills/evo-pcap-feature-extraction/scripts')
from utils import parse_pcap_to_features
features = parse_pcap_to_features('/root/packets.pcap')
```
Returns dict with: timestamps, lengths, src_ips, dst_ips, src_ports, dst_ports, has_tcp/udp/icmp/arp/ip, protocol_strs

import numpy as np
from scapy.utils import PcapReader
from scapy.layers.inet import IP, TCP, UDP, ICMP
from scapy.layers.l2 import ARP

def safe_get_ips(pkt):
    if pkt.haslayer(IP):
        return pkt[IP].src, pkt[IP].dst
    elif pkt.haslayer(ARP):
        return pkt[ARP].psrc, pkt[ARP].pdst
    return None, None

def safe_get_ports(pkt):
    if pkt.haslayer(TCP):
        return pkt[TCP].sport, pkt[TCP].dport
    elif pkt.haslayer(UDP):
        return pkt[UDP].sport, pkt[UDP].dport
    return None, None

def extract_packet_record(pkt):
    rec = {}
    rec['timestamp'] = float(pkt.time)
    rec['length'] = len(pkt)
    rec['src_ip'], rec['dst_ip'] = safe_get_ips(pkt)
    rec['src_port'], rec['dst_port'] = safe_get_ports(pkt)
    has_ip = pkt.haslayer(IP)
    rec['has_ip'] = has_ip
    rec['has_tcp'] = pkt.haslayer(TCP) and has_ip
    rec['has_udp'] = pkt.haslayer(UDP) and has_ip
    rec['has_icmp'] = pkt.haslayer(ICMP) and has_ip
    rec['has_arp'] = pkt.haslayer(ARP)
    if rec['has_tcp']: rec['protocol_str'] = 'TCP'
    elif rec['has_udp']: rec['protocol_str'] = 'UDP'
    elif rec['has_icmp']: rec['protocol_str'] = 'ICMP'
    elif rec['has_arp']: rec['protocol_str'] = 'ARP'
    else: rec['protocol_str'] = 'OTHER'
    return rec

def parse_pcap_to_features(filepath):
    ts=[]; ln=[]; si=[]; di=[]; sp=[]; dp=[]
    ht=[]; hu=[]; hi=[]; ha=[]; hip=[]; ps=[]
    with PcapReader(filepath) as reader:
        for pkt in reader:
            r = extract_packet_record(pkt)
            ts.append(r['timestamp']); ln.append(r['length'])
            si.append(r['src_ip']); di.append(r['dst_ip'])
            sp.append(r['src_port']); dp.append(r['dst_port'])
            ht.append(r['has_tcp']); hu.append(r['has_udp'])
            hi.append(r['has_icmp']); ha.append(r['has_arp'])
            hip.append(r['has_ip']); ps.append(r['protocol_str'])
    return {
        'timestamps': np.array(ts, dtype=np.float64),
        'lengths': np.array(ln, dtype=np.int64),
        'src_ips': si, 'dst_ips': di,
        'src_ports': sp, 'dst_ports': dp,
        'has_tcp': np.array(ht), 'has_udp': np.array(hu),
        'has_icmp': np.array(hi), 'has_arp': np.array(ha),
        'has_ip': np.array(hip), 'protocol_strs': ps,
    }

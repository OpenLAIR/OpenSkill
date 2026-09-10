import numpy as np
from collections import Counter, defaultdict

def compute_protocol_counts(features):
    return {
        'protocol_tcp': int(np.sum(features['has_tcp'])),
        'protocol_udp': int(np.sum(features['has_udp'])),
        'protocol_icmp': int(np.sum(features['has_icmp'])),
        'protocol_arp': int(np.sum(features['has_arp'])),
        'protocol_ip_total': int(np.sum(features['has_ip'])),
    }

def compute_time_stats(timestamps):
    if len(timestamps) == 0:
        return {'duration_seconds': 0.0}
    ts = np.sort(timestamps)
    return {'duration_seconds': float(ts[-1] - ts[0])}

def compute_ppm_buckets(timestamps, interval=60):
    if len(timestamps) == 0:
        return np.array([0])
    ts = np.sort(timestamps)
    t0 = ts[0]
    bucket_indices = np.floor((ts - t0) / interval).astype(int)
    max_bucket = bucket_indices[-1]
    ppm = np.bincount(bucket_indices, minlength=max_bucket + 1)
    return ppm

def compute_size_stats(lengths):
    if len(lengths) == 0:
        return {'total_bytes': 0, 'avg_packet_size': 0.0, 'min_packet_size': 0, 'max_packet_size': 0}
    return {
        'total_bytes': int(np.sum(lengths)),
        'avg_packet_size': float(np.mean(lengths)),
        'min_packet_size': int(np.min(lengths)),
        'max_packet_size': int(np.max(lengths)),
    }

def compute_shannon_entropy(values):
    if len(values) == 0:
        return 0.0
    _, counts = np.unique(values, return_counts=True)
    probs = counts / len(values)
    return float(-np.sum(probs * np.log2(probs)))

def compute_graph_metrics(src_ips, dst_ips):
    edges = set()
    out_map = defaultdict(set)
    in_map = defaultdict(set)
    nodes = set()
    for s, d in zip(src_ips, dst_ips):
        if s is not None and d is not None:
            nodes.add(s)
            nodes.add(d)
            edges.add((s, d))
            out_map[s].add(d)
            in_map[d].add(s)
    n = len(nodes)
    e = len(edges)
    density = e / (n * (n - 1)) if n >= 2 else 0.0
    max_out = max((len(v) for v in out_map.values()), default=0)
    max_in = max((len(v) for v in in_map.values()), default=0)
    return {
        'num_nodes': n, 'num_edges': e,
        'network_density': float(density),
        'max_outdegree': max_out, 'max_indegree': max_in,
    }

def compute_iat_metrics(timestamps):
    if len(timestamps) < 2:
        return {'iat_mean': 0.0, 'iat_variance': 0.0, 'iat_cv': 0.0}
    ts = np.sort(timestamps)
    iat = np.diff(ts)
    mean = float(np.mean(iat))
    var = float(np.var(iat, ddof=1)) if len(iat) > 1 else 0.0
    std = float(np.std(iat, ddof=1)) if len(iat) > 1 else 0.0
    cv = std / mean if mean > 0 else 0.0
    return {'iat_mean': mean, 'iat_variance': var, 'iat_cv': cv}

def compute_pcr_metrics(src_ips, dst_ips, lengths):
    sent = defaultdict(int)
    recv = defaultdict(int)
    for i in range(len(src_ips)):
        s, d = src_ips[i], dst_ips[i]
        l = int(lengths[i])
        if s is not None:
            sent[s] += l
        if d is not None:
            recv[d] += l
    all_ips = set(sent.keys()) | set(recv.keys())
    producers = 0
    consumers = 0
    for ip in all_ips:
        s = sent.get(ip, 0)
        r = recv.get(ip, 0)
        total = s + r
        if total == 0:
            continue
        pcr = (s - r) / total
        if pcr > 0.2:
            producers += 1
        if pcr < -0.2:
            consumers += 1
    return {'num_producers': producers, 'num_consumers': consumers}

def compute_flow_metrics(features):
    flows = set()
    for i in range(len(features['src_ips'])):
        s = features['src_ips'][i]
        d = features['dst_ips'][i]
        sp = features['src_ports'][i]
        dp = features['dst_ports'][i]
        pr = features['protocol_strs'][i]
        if s is None or d is None:
            sp = sp if sp is not None else 0
            dp = dp if dp is not None else 0
            s = s if s is not None else ''
            d = d if d is not None else ''
        else:
            sp = sp if sp is not None else 0
            dp = dp if dp is not None else 0
        flows.add((s, d, sp, dp, pr))
    tcp_flows = sum(1 for f in flows if f[4] == 'TCP')
    udp_flows = sum(1 for f in flows if f[4] == 'UDP')
    bidir = 0
    for f in flows:
        rev = (f[1], f[0], f[3], f[2], f[4])
        if rev in flows:
            bidir += 1
    bidir = bidir // 2
    return {
        'unique_flows': len(flows),
        'tcp_flows': tcp_flows,
        'udp_flows': udp_flows,
        'bidirectional_flows': bidir,
    }

def determine_analysis_flags(stats, features):
    flags = {}
    has_scan = stats.get('max_outdegree', 0) > 10
    dst_ent = stats.get('dst_port_entropy', 0)
    if dst_ent > 4.0:
        has_scan = True
    flags['has_port_scan'] = has_scan
    ppm_max = stats.get('packets_per_minute_max', 0)
    ppm_avg = stats.get('packets_per_minute_avg', 1)
    flags['has_dos_pattern'] = ppm_max > 5 * ppm_avg if ppm_avg > 0 else False
    iat_cv = stats.get('iat_cv', 999)
    flags['has_beaconing'] = iat_cv < 0.5 and iat_cv > 0
    is_benign = not (flags['has_port_scan'] or flags['has_dos_pattern'])
    flags['is_traffic_benign'] = is_benign
    return {k: str(v).lower() for k, v in flags.items()}

def write_stats_csv(filepath, stats_dict):
    lines = []
    with open(filepath, 'r') as f:
        for line in f:
            if line.startswith('#'):
                lines.append(line)
            else:
                parts = line.strip().split(',')
                key = parts[0]
                if key == 'metric':
                    lines.append(line)
                elif key in stats_dict:
                    val = stats_dict[key]
                    if isinstance(val, float):
                        lines.append(f'{key},{val}\n')
                    else:
                        lines.append(f'{key},{val}\n')
                else:
                    lines.append(line)
    with open(filepath, 'w') as f:
        f.writelines(lines)

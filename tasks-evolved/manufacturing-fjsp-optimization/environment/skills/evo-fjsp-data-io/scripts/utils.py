import re, json, os
import pandas as pd
from collections import defaultdict
import numpy as np

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        return super().default(obj)

def parse_fjsp_instance(filepath):
    with open(filepath) as f:
        lines = [l.strip() for l in f if l.strip()]
    toks = lines[0].split()
    num_jobs, num_machines = int(toks[0]), int(toks[1])
    stream = []
    for line in lines[1:]:
        stream.extend([int(float(x)) for x in line.split()])
    ptr, jobs, all_mids = 0, [], []
    for j in range(num_jobs):
        num_ops = stream[ptr]; ptr += 1
        ops = []
        for o in range(num_ops):
            ne = stream[ptr]; ptr += 1
            em = {}
            for _ in range(ne):
                mid, pt = stream[ptr], stream[ptr+1]; ptr += 2
                em[mid] = pt; all_mids.append(mid)
            ops.append(em)
        jobs.append(ops)
    if all_mids and max(all_mids) >= num_machines:
        jobs = [[{m-1:p for m,p in op.items()} for op in job] for job in jobs]
    return jobs, num_machines

def parse_downtimes_csv(filepath):
    df = pd.read_csv(filepath)
    dt = defaultdict(list)
    for _, r in df.iterrows():
        m, s, e = int(r['machine']), int(r['start']), int(r['end'])
        if e > s: dt[m].append([s, e])
    for m in dt: dt[m].sort(key=lambda x: x[0])
    return dict(dt)

def parse_policy_budgets(filepath):
    with open(filepath) as f: return json.load(f)

def parse_baseline_schedule(filepath):
    with open(filepath) as f: data = json.load(f)
    bl = {}
    for op in data['schedule']:
        bl[(int(op['job']), int(op['op']))] = {
            'machine': int(op['machine']), 'start': int(op['start']),
            'end': int(op['end']), 'dur': int(op['dur'])}
    return bl, int(data['makespan']), data['schedule']

def export_solution_json(schedule, makespan, status, filepath):
    cs = [{'job':int(o['job']),'op':int(o['op']),'machine':int(o['machine']),
           'start':int(o['start']),'end':int(o['end']),'dur':int(o['dur'])} for o in schedule]
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath,'w') as f:
        json.dump({'status':status,'makespan':int(makespan),'schedule':cs}, f, cls=NpEncoder, indent=2)

def export_solution_csv(schedule, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    cs = [{'job':int(o['job']),'op':int(o['op']),'machine':int(o['machine']),
           'start':int(o['start']),'end':int(o['end']),'dur':int(o['dur'])} for o in schedule]
    pd.DataFrame(cs)[['job','op','machine','start','end','dur']].to_csv(filepath, index=False)

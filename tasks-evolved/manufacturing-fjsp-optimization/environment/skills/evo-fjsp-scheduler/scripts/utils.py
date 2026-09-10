import random, math, copy

def find_earliest_start(machine, earliest_time, duration, downtimes, scheduled_ops):
    occupied = []
    if machine in downtimes:
        occupied.extend([list(x) for x in downtimes[machine]])
    if machine in scheduled_ops:
        for op in scheduled_ops[machine]:
            occupied.append([op['start'], op['end']])
    if not occupied:
        return earliest_time
    occupied.sort(key=lambda x: x[0])
    merged = []
    for iv in occupied:
        if not merged:
            merged.append(iv)
        elif iv[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], iv[1])
        else:
            merged.append(iv)
    ct = earliest_time
    for s, e in merged:
        if e <= ct: continue
        if ct + duration <= s: return ct
        ct = max(ct, e)
    return ct

def greedy_dispatching(jobs, num_machines, downtimes):
    jc = {j: 0 for j in range(len(jobs))}
    so = {m: [] for m in range(num_machines)}
    schedule = []
    max_ops = max(len(j) for j in jobs)
    for oi in range(max_ops):
        for ji, job in enumerate(jobs):
            if oi >= len(job): continue
            em = job[oi]
            eat = jc[ji]
            bm, bs, be, bd = -1, float('inf'), float('inf'), 0
            for mid, pt in em.items():
                st = find_earliest_start(mid, eat, pt, downtimes, so)
                et = st + pt
                if et < be:
                    be, bs, bm, bd = et, st, mid, pt
            rec = {'job':ji,'op':oi,'machine':bm,'start':bs,'end':be,'dur':bd}
            so[bm].append(rec)
            schedule.append(rec)
            jc[ji] = be
    return schedule

def validate_policy_budgets(new_schedule, baseline, policy):
    cb = policy.get('change_budget', {})
    max_mc = cb.get('max_machine_changes', float('inf'))
    max_ss = cb.get('max_total_start_shift_L1', float('inf'))
    mc, ss = 0, 0
    for op in new_schedule:
        j, o = op['job'], op['op']
        base = baseline.get((j, o))
        if not base: continue
        if op['machine'] != base['machine']: mc += 1
        ss += abs(op['start'] - base['start'])
    return mc <= max_mc and ss <= max_ss, mc, ss

def repair_schedule(jobs, num_machines, downtimes, baseline, policy):
    freeze = policy.get('freeze', {})
    freeze_enabled = freeze.get('enabled', False)
    freeze_until = freeze.get('freeze_until', 0) if freeze_enabled else 0
    lock_fields = freeze.get('lock_fields', []) if freeze_enabled else []
    cb = policy.get('change_budget', {})
    max_mc = cb.get('max_machine_changes', float('inf'))
    max_ss = cb.get('max_total_start_shift_L1', float('inf'))
    
    # Sort baseline ops by job then op
    all_ops = []
    for j in range(len(jobs)):
        for o in range(len(jobs[j])):
            all_ops.append((j, o))
    
    jc = {j: 0 for j in range(len(jobs))}
    so = {m: [] for m in range(num_machines)}
    schedule = []
    changes, shift = 0, 0
    
    # Process in job-op order
    for j in range(len(jobs)):
        for o in range(len(jobs[j])):
            em = jobs[j][o]
            base = baseline.get((j, o), {})
            bm = base.get('machine', -1)
            bstart = base.get('start', 0)
            eat = jc[j]
            
            # Check if frozen
            frozen = False
            if freeze_enabled and bstart < freeze_until:
                frozen = True
            
            if frozen and 'machine' in lock_fields and 'start' in lock_fields:
                # Keep exact baseline assignment
                mid = bm
                pt = em[mid]
                st = bstart
                rec = {'job':j,'op':o,'machine':mid,'start':st,'end':st+pt,'dur':pt}
                so[mid].append(rec)
                schedule.append(rec)
                jc[j] = st + pt
                continue
            
            # Try baseline machine first, then others
            candidates = []
            if bm in em:
                candidates.append(bm)
            for mid in em:
                if mid != bm:
                    candidates.append(mid)
            
            best_rec = None
            best_score = (float('inf'),) * 4
            for mid in candidates:
                pt = em[mid]
                mc_cost = 1 if mid != bm else 0
                if changes + mc_cost > max_mc: continue
                st = find_earliest_start(mid, eat, pt, downtimes, so)
                ss_cost = abs(st - bstart)
                if shift + ss_cost > max_ss: continue
                score = (mc_cost, ss_cost, st + pt, mid)
                if score < best_score:
                    best_score = score
                    best_rec = {'job':j,'op':o,'machine':mid,'start':st,'end':st+pt,'dur':pt}
            
            if best_rec is None:
                # Fallback: just pick best end time ignoring budgets
                for mid in candidates:
                    pt = em[mid]
                    st = find_earliest_start(mid, eat, pt, downtimes, so)
                    rec = {'job':j,'op':o,'machine':mid,'start':st,'end':st+pt,'dur':pt}
                    if best_rec is None or rec['end'] < best_rec['end']:
                        best_rec = rec
            
            mc_cost = 1 if best_rec['machine'] != bm else 0
            changes += mc_cost
            shift += abs(best_rec['start'] - bstart)
            so[best_rec['machine']].append(best_rec)
            schedule.append(best_rec)
            jc[j] = best_rec['end']
    
    return schedule

def decode_schedule(os_array, ms_array, jobs, num_machines, downtimes):
    joc = {j: 0 for j in range(len(jobs))}
    jc = {j: 0 for j in range(len(jobs))}
    so = {m: [] for m in range(num_machines)}
    schedule = []
    for ji in os_array:
        oi = joc[ji]; joc[ji] += 1
        mid = ms_array[ji][oi]
        pt = jobs[ji][oi][mid]
        st = find_earliest_start(mid, jc[ji], pt, downtimes, so)
        rec = {'job':ji,'op':oi,'machine':mid,'start':st,'end':st+pt,'dur':pt}
        so[mid].append(rec)
        schedule.append(rec)
        jc[ji] = st + pt
    return max(jc.values()), schedule

def simulated_annealing_fjsp(jobs, num_machines, downtimes, baseline=None, policy=None, max_iter=8000):
    # Init with greedy
    init_sched = greedy_dispatching(jobs, num_machines, downtimes)
    best_ms = max(op['end'] for op in init_sched)
    best_sched = init_sched
    # Build OS/MS from greedy
    os_arr = [op['job'] for op in init_sched]
    ms_arr = [[0]*len(job) for job in jobs]
    for op in init_sched:
        ms_arr[op['job']][op['op']] = op['machine']
    cur_os, cur_ms = list(os_arr), [list(x) for x in ms_arr]
    cur_ms_val = best_ms
    T, alpha = 100.0, 0.995
    for i in range(max_iter):
        nos = list(cur_os)
        nms = [list(x) for x in cur_ms]
        if random.random() < 0.5:
            i1, i2 = random.sample(range(len(nos)), 2)
            nos[i1], nos[i2] = nos[i2], nos[i1]
        else:
            j = random.randrange(len(jobs))
            o = random.randrange(len(jobs[j]))
            elig = list(jobs[j][o].keys())
            if len(elig) > 1:
                elig2 = [m for m in elig if m != nms[j][o]]
                nms[j][o] = random.choice(elig2)
        nmsv, nsched = decode_schedule(nos, nms, jobs, num_machines, downtimes)
        # Check policy if provided
        if baseline and policy:
            ok, _, _ = validate_policy_budgets(nsched, baseline, policy)
            if not ok:
                continue
        delta = nmsv - cur_ms_val
        if delta < 0 or (T > 0.01 and random.random() < math.exp(-delta/max(T,0.01))):
            cur_os, cur_ms, cur_ms_val = nos, nms, nmsv
            if nmsv < best_ms:
                best_ms = nmsv
                best_sched = nsched
        T *= alpha
    return best_sched, best_ms

def solve_fjsp_with_policy(jobs, num_machines, downtimes, baseline, policy, target_makespan=None):
    """Main solver: freezes baseline ops with start < freeze_until,
    then enumerates machine assignments and topological orderings
    for non-frozen ops to find minimum makespan within policy budgets.
    Frozen ops that violate downtime are still frozen (policy takes priority)."""
    import itertools
    
    freeze = policy.get('freeze', {})
    freeze_enabled = freeze.get('enabled', False)
    freeze_until = freeze.get('freeze_until', 0) if freeze_enabled else 0
    cb = policy.get('change_budget', {})
    max_mc = cb.get('max_machine_changes', float('inf'))
    max_ss = cb.get('max_total_start_shift_L1', float('inf'))
    
    # Freeze ALL ops with baseline start < freeze_until
    frozen_ops = set()
    for (j, o), info in baseline.items():
        if info['start'] < freeze_until:
            frozen_ops.add((j, o))
    
    # Non-frozen ops
    nf_ops = []
    for j in range(len(jobs)):
        for o in range(len(jobs[j])):
            if (j, o) not in frozen_ops:
                nf_ops.append((j, o, list(jobs[j][o].keys())))
    
    # Generate topological orderings
    job_nf = {}
    for j, o, _ in nf_ops:
        job_nf.setdefault(j, []).append(o)
    for j in job_nf: job_nf[j].sort()
    
    topo = []
    def bt(p, n):
        if len(p) == len(nf_ops): topo.append(list(p)); return
        if len(topo) > 5000: return
        for j in sorted(job_nf.keys()):
            ops = job_nf[j]; idx = n.get(j, 0)
            if idx >= len(ops): continue
            o = ops[idx]
            if o > 0 and (j, o-1) not in frozen_ops and (j, o-1) not in set(p): continue
            n[j] = idx+1; p.append((j,o)); bt(p,n); p.pop(); n[j] = idx
    bt([], {j:0 for j in job_nf})
    
    def build(mc_map, order):
        jc = {j:0 for j in range(len(jobs))}
        so = {m:[] for m in range(num_machines)}
        sched = []
        for (j,o) in sorted(frozen_ops):
            info = baseline[(j,o)]
            rec = {'job':j,'op':o,'machine':info['machine'],'start':info['start'],'end':info['end'],'dur':info['dur']}
            so[info['machine']].append(rec); sched.append(rec)
            jc[j] = max(jc[j], info['end'])
        for (j,o) in order:
            mid = mc_map[(j,o)]; pt = jobs[j][o][mid]; eat = jc[j]
            st = find_earliest_start(mid, eat, pt, downtimes, so)
            rec = {'job':j,'op':o,'machine':mid,'start':st,'end':st+pt,'dur':pt}
            so[mid].append(rec); sched.append(rec); jc[j] = st+pt
        return sched
    
    mo = [elig for _,_,elig in nf_ops]
    best_s, best_ms = None, float('inf')
    for combo in itertools.product(*mo):
        mc_map = {(j,o):combo[i] for i,(j,o,_) in enumerate(nf_ops)}
        mc_cnt = sum(1 for (j,o) in mc_map if baseline.get((j,o),{}).get('machine') != mc_map[(j,o)])
        if mc_cnt > max_mc: continue
        for order in topo:
            s = build(mc_map, order)
            ms = max(op['end'] for op in s)
            if ms >= best_ms: continue
            ss = sum(abs(op['start']-baseline[(op['job'],op['op'])]['start']) for op in s if (op['job'],op['op']) in baseline)
            if ss > max_ss: continue
            best_ms = ms; best_s = s
    
    return best_s, best_ms

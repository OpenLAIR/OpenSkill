def check_completeness(schedule, jobs):
    ops_found = set()
    for op in schedule:
        ops_found.add((op['job'], op['op']))
    expected = set()
    for j in range(len(jobs)):
        for o in range(len(jobs[j])):
            expected.add((j, o))
    missing = expected - ops_found
    if missing:
        return False, f"Missing ops: {missing}"
    return True, "OK"

def check_eligibility_and_duration(schedule, jobs):
    for op in schedule:
        j, o, m, d = op['job'], op['op'], op['machine'], op['dur']
        em = jobs[j][o]
        if m not in em:
            return False, f"M{m} not eligible for J{j}O{o}"
        if em[m] != d:
            return False, f"Wrong dur J{j}O{o} M{m}: {d} vs {em[m]}"
        if op['end'] - op['start'] != d:
            return False, f"end-start != dur for J{j}O{o}"
    return True, "OK"

def check_precedence(schedule, jobs):
    jt = {}
    for op in schedule:
        jt[(op['job'], op['op'])] = (op['start'], op['end'])
    for j in range(len(jobs)):
        for o in range(len(jobs[j]) - 1):
            if (j, o) not in jt or (j, o+1) not in jt: continue
            if jt[(j, o+1)][0] < jt[(j, o)][1]:
                return False, f"Prec viol J{j}: O{o+1} starts {jt[(j,o+1)][0]} < O{o} ends {jt[(j,o)][1]}"
    return True, "OK"

def check_machine_overlaps(schedule):
    mt = {}
    for op in schedule:
        m = op['machine']
        mt.setdefault(m, []).append((op['start'], op['end'], op['job'], op['op']))
    for m, tasks in mt.items():
        tasks.sort()
        for i in range(len(tasks)-1):
            if tasks[i][1] > tasks[i+1][0]:
                return False, f"Overlap M{m}: {tasks[i]} vs {tasks[i+1]}"
    return True, "OK"

def check_downtime_overlaps(schedule, downtimes):
    for op in schedule:
        m = op['machine']
        if m not in downtimes: continue
        for ds, de in downtimes[m]:
            if max(op['start'], ds) < min(op['end'], de):
                return False, f"DT overlap M{m} op J{op['job']}O{op['op']} [{op['start']},{op['end']}) vs [{ds},{de})"
    return True, "OK"

def calculate_makespan(schedule):
    return max(op['end'] for op in schedule)

def validate_schedule(schedule, jobs, num_machines, downtimes):
    checks = [
        check_completeness(schedule, jobs),
        check_eligibility_and_duration(schedule, jobs),
        check_precedence(schedule, jobs),
        check_machine_overlaps(schedule),
        check_downtime_overlaps(schedule, downtimes)
    ]
    for ok, msg in checks:
        if not ok:
            return False, msg
    return True, f"Valid. Makespan={calculate_makespan(schedule)}"

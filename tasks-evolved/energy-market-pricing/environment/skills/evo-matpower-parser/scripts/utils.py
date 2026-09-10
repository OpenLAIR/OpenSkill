import json
import numpy as np
from scipy.sparse import csr_matrix, diags
from scipy.sparse.linalg import spsolve
import copy

def load_matpower_json(filepath):
    """Load MATPOWER JSON file and return the data dict."""
    with open(filepath) as f:
        data = json.load(f)
    return data

def create_bus_mappings(bus_data):
    """Create ext2int and int2ext bus mappings."""
    ext2int = {}
    int2ext = {}
    for i, row in enumerate(bus_data):
        ext_id = int(row[0])
        ext2int[ext_id] = i
        int2ext[i] = ext_id
    return ext2int, int2ext

def find_slack_bus(bus_data):
    """Find the reference/slack bus (BUS_TYPE == 3)."""
    for row in bus_data:
        if int(row[1]) == 3:
            return int(row[0])
    # Fallback to first bus
    return int(bus_data[0][0])

def parse_generators(gen_data, ext2int):
    """Parse generator data. Returns dict with arrays."""
    ng = len(gen_data)
    gen_bus_ext = np.array([int(g[0]) for g in gen_data])
    gen_bus_int = np.array([ext2int[int(g[0])] for g in gen_data])
    pg_init = np.array([g[1] for g in gen_data])
    pmax = np.array([g[8] for g in gen_data])
    pmin = np.array([g[9] for g in gen_data])
    status = np.array([int(g[7]) for g in gen_data])
    return {
        'ng': ng,
        'gen_bus_ext': gen_bus_ext,
        'gen_bus_int': gen_bus_int,
        'pmax': pmax,
        'pmin': pmin,
        'status': status,
        'pg_init': pg_init
    }

def parse_branches(branch_data, ext2int):
    """Parse branch data. Returns dict with arrays."""
    nl = len(branch_data)
    f_bus_ext = np.array([int(b[0]) for b in branch_data])
    t_bus_ext = np.array([int(b[1]) for b in branch_data])
    f_bus_int = np.array([ext2int[int(b[0])] for b in branch_data])
    t_bus_int = np.array([ext2int[int(b[1])] for b in branch_data])
    r = np.array([b[2] for b in branch_data])
    x = np.array([b[3] for b in branch_data])
    rate_a = np.array([b[5] for b in branch_data])
    status = np.array([int(b[10]) for b in branch_data])
    return {
        'nl': nl,
        'f_bus_ext': f_bus_ext,
        't_bus_ext': t_bus_ext,
        'f_bus_int': f_bus_int,
        't_bus_int': t_bus_int,
        'r': r,
        'x': x,
        'rate_a': rate_a,
        'status': status
    }

def parse_gencost(gencost_data):
    """Parse generator cost data. Returns linear cost coefficients.
    For polynomial type 2 with NCOST=3: cost = c2*P^2 + c1*P + c0
    Returns c2, c1, c0 arrays."""
    ng = len(gencost_data)
    c2 = np.zeros(ng)
    c1 = np.zeros(ng)
    c0 = np.zeros(ng)
    for i, gc in enumerate(gencost_data):
        model = int(gc[0])
        ncost = int(gc[3])
        if model == 2:  # polynomial
            coeffs = gc[4:4+ncost]
            if ncost == 3:
                c2[i] = coeffs[0]
                c1[i] = coeffs[1]
                c0[i] = coeffs[2]
            elif ncost == 2:
                c1[i] = coeffs[0]
                c0[i] = coeffs[1]
            elif ncost == 1:
                c0[i] = coeffs[0]
    return {'c2': c2, 'c1': c1, 'c0': c0}

def compute_network_matrices(bus_data, branches, ext2int, slack_ext):
    """Compute A (incidence), Bbranch (diagonal susceptance), Bbus, and PTDF.
    Uses sparse matrices for efficiency with large networks."""
    nb = len(bus_data)
    nl = branches['nl']
    slack_idx = ext2int[slack_ext]
    
    # Build sparse incidence matrix A and diagonal Bbranch
    row_idx = []
    col_idx = []
    a_vals = []
    b_diag = np.zeros(nl)
    
    for i in range(nl):
        if branches['status'][i] == 0:
            continue
        f_idx = branches['f_bus_int'][i]
        t_idx = branches['t_bus_int'][i]
        x_val = branches['x'][i]
        if x_val == 0:
            continue
        b_val = 1.0 / x_val
        b_diag[i] = b_val
        # A[i, f_idx] = 1, A[i, t_idx] = -1
        row_idx.extend([i, i])
        col_idx.extend([f_idx, t_idx])
        a_vals.extend([1.0, -1.0])
    
    A = csr_matrix((a_vals, (row_idx, col_idx)), shape=(nl, nb))
    Bbranch_diag = diags(b_diag, 0, shape=(nl, nl), format='csr')
    
    # Bbus = A^T @ Bbranch @ A
    Bbus = A.T @ Bbranch_diag @ A
    
    # Compute PTDF using sparse solver
    # Remove slack bus row/col from Bbus
    mask = np.ones(nb, dtype=bool)
    mask[slack_idx] = False
    indices = np.where(mask)[0]
    
    Bbus_dense = Bbus.toarray()
    Bbus_reduced = Bbus_dense[np.ix_(indices, indices)]
    
    # Solve for pseudo-inverse columns
    Bbus_inv_reduced = np.linalg.inv(Bbus_reduced)
    
    # Expand back to full size
    X = np.zeros((nb, nb))
    X[np.ix_(indices, indices)] = Bbus_inv_reduced
    
    # PTDF = Bbranch @ A @ X
    BA = Bbranch_diag @ A
    PTDF = BA.toarray() @ X
    
    return {
        'A': A,
        'Bbranch_diag': b_diag,
        'Bbus': Bbus,
        'PTDF': PTDF,
        'slack_idx': slack_idx
    }

def modify_branch_rate(data, f_bus_ext, t_bus_ext, multiplier):
    """Create a deep copy of data and modify the RATE_A of the specified branch.
    Returns modified data copy."""
    data_copy = copy.deepcopy(data)
    for branch in data_copy['branch']:
        if int(branch[0]) == f_bus_ext and int(branch[1]) == t_bus_ext:
            branch[5] = branch[5] * multiplier
            break
    return data_copy

def get_load_vector(bus_data, nb):
    """Extract load vector (PD) from bus data."""
    load = np.zeros(nb)
    for i, row in enumerate(bus_data):
        load[i] = row[2]  # PD column
    return load

def get_gen_bus_matrix(gen_info, nb):
    """Create generator-to-bus mapping matrix Cg (nb x ng)."""
    ng = gen_info['ng']
    Cg = np.zeros((nb, ng))
    for i in range(ng):
        Cg[gen_info['gen_bus_int'][i], i] = 1.0
    return Cg

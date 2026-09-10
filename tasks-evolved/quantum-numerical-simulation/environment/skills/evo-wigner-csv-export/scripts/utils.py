import numpy as np
import qutip

def compute_wigner_function(rho_cavity, xvec=None, yvec=None, x_range=(-6, 6), y_range=(-6, 6), n_points=1000):
    """
    Compute the Wigner function of a bosonic density matrix on a phase-space grid.
    
    Parameters:
    - rho_cavity: Qobj density matrix for cavity mode
    - xvec: 1D array for x coordinates (if None, generated from x_range)
    - yvec: 1D array for y/p coordinates (if None, generated from y_range)
    - x_range: tuple (min, max) for x grid
    - y_range: tuple (min, max) for y/p grid
    - n_points: number of grid points in each dimension
    
    Returns: (W, xvec, yvec)
        W: 2D numpy array of shape (n_points, n_points)
        xvec: 1D array of x coordinates
        yvec: 1D array of y/p coordinates
    """
    if xvec is None:
        xvec = np.linspace(x_range[0], x_range[1], n_points)
    if yvec is None:
        yvec = np.linspace(y_range[0], y_range[1], n_points)
    
    # Use clenshaw method (best for QuTiP 4.7.0)
    W = qutip.wigner(rho_cavity, xvec, yvec, method='clenshaw', g=np.sqrt(2))
    
    return W, xvec, yvec

def save_wigner_to_csv(W, xvec, yvec, filename, float_format='%.6f'):
    """
    Save Wigner function to CSV file.
    
    The CSV format:
    - First row: header with 'p' followed by xvec values
    - Subsequent rows: yvec[i] followed by W[i,:] values
    - Rows correspond to p (yvec), columns correspond to x (xvec)
    
    Parameters:
    - W: 2D numpy array (n_points x n_points)
    - xvec: 1D array of x coordinates (columns)
    - yvec: 1D array of p coordinates (rows/index)
    - filename: output CSV file path
    - float_format: format string for floating point numbers
    """
    import pandas as pd
    
    # W shape is (len(yvec), len(xvec))
    # Index = yvec (p), Columns = xvec (x)
    df = pd.DataFrame(W, index=yvec, columns=xvec)
    df.to_csv(filename, index_label='p', float_format=float_format)
    
    return filename

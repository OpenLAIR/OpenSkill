import numpy as np
from pycbc.frame import read_frame
from pycbc.filter import highpass, resample_to_delta_t, matched_filter
from pycbc.psd import interpolate, inverse_spectrum_truncation
from pycbc.waveform import get_td_waveform


def read_and_condition_data(gwf_path, channel):
    """
    Read a GWF frame file and condition the data for matched filtering.
    
    Pipeline:
    1. Read entire frame file
    2. Highpass filter at 15 Hz (remove seismic noise)
    3. Crop 2 seconds from both ends (remove FIR filter wraparound)
    4. Resample to 2048 Hz (reduce computation)
    
    Args:
        gwf_path: Path to .gwf file
        channel: Channel name (e.g., 'H1:TEST-STRAIN')
    
    Returns:
        conditioned: Conditioned TimeSeries
    """
    # Read entire frame file
    strain = read_frame(gwf_path, channel)
    
    # Highpass at 15 Hz to remove seismic wall
    strain = highpass(strain, 15.0)
    
    # Crop FIR filter wraparound (2 seconds both ends)
    strain = strain.crop(2, 2)
    
    # Downsample to 2048 Hz
    strain = resample_to_delta_t(strain, 1.0 / 2048)
    
    return strain


def estimate_psd(conditioned_data):
    """
    Estimate PSD using Welch's method, interpolate, and apply inverse spectrum truncation.
    
    Args:
        conditioned_data: Conditioned TimeSeries from read_and_condition_data()
    
    Returns:
        psd: Processed PSD ready for matched filtering
    """
    # 4-second Welch segments (community standard)
    psd = conditioned_data.psd(4)
    
    # Interpolate to match the data's frequency resolution
    psd = interpolate(psd, conditioned_data.delta_f)
    
    # Inverse spectrum truncation: limit time-domain filter to 4 seconds
    max_filter_len = int(4 * conditioned_data.sample_rate)
    psd = inverse_spectrum_truncation(psd, max_filter_len, low_frequency_cutoff=15.0)
    
    return psd


def generate_template(approximant, mass1, mass2, delta_t, f_lower=20.0):
    """
    Generate a waveform template for matched filtering.
    
    Args:
        approximant: Waveform approximant name (e.g., 'SEOBNRv4_opt', 'IMRPhenomD', 'TaylorT4')
        mass1: Mass of first component (solar masses)
        mass2: Mass of second component (solar masses)
        delta_t: Time step (must match conditioned data)
        f_lower: Lower frequency cutoff (default 20.0 Hz)
    
    Returns:
        hp: Plus polarization TimeSeries
    """
    hp, hc = get_td_waveform(
        approximant=approximant,
        mass1=mass1,
        mass2=mass2,
        delta_t=delta_t,
        f_lower=f_lower
    )
    return hp


def compute_matched_filter_snr(conditioned_data, psd, hp, f_lower=20.0):
    """
    Perform matched filtering and extract peak SNR.
    
    Steps:
    1. Resize template to match data length
    2. Cyclic shift template to align merger peak
    3. Run matched_filter
    4. Take absolute value of complex SNR
    5. Crop edge artifacts (8s start, 4s end)
    6. Find peak SNR
    
    Args:
        conditioned_data: Conditioned strain TimeSeries
        psd: Processed PSD
        hp: Template waveform (plus polarization)
        f_lower: Lower frequency cutoff (must match template generation)
    
    Returns:
        peak_snr: Float, peak SNR value
        peak_time: Float, GPS time of peak
    """
    # Resize template to match data length
    hp.resize(len(conditioned_data))
    
    # Cyclic shift so merger peak aligns to t=0
    hp = hp.cyclic_time_shift(hp.start_time)
    
    # Matched filtering
    snr_complex = matched_filter(
        hp, conditioned_data,
        psd=psd,
        low_frequency_cutoff=f_lower
    )
    
    # Extract absolute SNR and crop boundary corruptions
    snr_real = abs(snr_complex)
    snr_real = snr_real.crop(8, 4)
    
    # Find peak
    peak_idx = np.argmax(snr_real)
    peak_snr = float(snr_real[peak_idx])
    peak_time = float(snr_real.sample_times[peak_idx])
    
    return peak_snr, peak_time


def find_peak_snr(gwf_path, channel, mass1, mass2, approximant, conditioned_data=None, psd=None):
    """
    High-level function: condition data (or reuse), generate template, and find peak SNR.
    
    Args:
        gwf_path: Path to .gwf file
        channel: Channel name
        mass1: Mass of first component (solar masses)
        mass2: Mass of second component (solar masses)
        approximant: Waveform approximant name
        conditioned_data: Pre-conditioned data (optional, avoids re-reading)
        psd: Pre-computed PSD (optional, avoids re-computing)
    
    Returns:
        peak_snr: Float, peak SNR value
        peak_time: Float, GPS time of peak
    """
    # Condition data if not provided
    if conditioned_data is None:
        conditioned_data = read_and_condition_data(gwf_path, channel)
    if psd is None:
        psd = estimate_psd(conditioned_data)
    
    # Generate template
    f_lower = 20.0
    hp = generate_template(approximant, mass1, mass2, conditioned_data.delta_t, f_lower)
    
    # Compute matched filter SNR
    peak_snr, peak_time = compute_matched_filter_snr(conditioned_data, psd, hp, f_lower)
    
    return peak_snr, peak_time

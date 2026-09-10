import pdfplumber
import re

def extract_pdf_text(filepath):
    """Extract text from PDF using pdfplumber."""
    text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def parse_preheat_params():
    """Return preheat zone parameters from handbook.
    
    From handbook: "In the preheat section, the goal is to fully preheat the SMT
    assembly to temperatures generally between 100C to 150C. The most critical
    parameter in the preheat section is to minimize the rate of rise to less than
    2C/second."
    """
    return {
        'preheat_min_c': 100.0,
        'preheat_max_c': 150.0,
        'max_ramp_rate_c_per_s': 2.0,
    }

def parse_tal_params():
    """Return TAL (wetting time) parameters from handbook.
    
    From handbook: "The wetting time is normally 30 to 60 seconds for most pastes."
    The solder must exceed its melting point (liquidus temperature).
    Liquidus is paste-specific (from MES data: solder_liquidus_c column).
    """
    return {
        'min_tal_s': 30.0,
        'max_tal_s': 60.0,
    }

def parse_peak_temp_params():
    """Return peak temperature parameters from handbook.
    
    From handbook: "This temperature must be exceeded by approximately 20C
    to ensure quality reflow." So peak >= liquidus + 20.
    """
    return {
        'peak_margin_c': 20.0,
    }

def parse_conveyor_speed_params():
    """Return conveyor speed parameters from handbook.
    
    From handbook:
    LINE SPEED (MINIMUM) = BOARDS PER MINUTE x LENGTH PER BOARD / LOAD FACTOR
    
    Operating at a conveyor speed greater than the calculated speed ensures
    that no product jams will occur.
    """
    return {
        'formula': 'min_speed = boards_per_min * board_length_cm / loading_factor',
        'description': 'Conveyor speed must be >= minimum line speed to avoid jams',
    }

def get_all_handbook_params():
    """Return all handbook parameters as a single dict."""
    return {
        'preheat': parse_preheat_params(),
        'tal': parse_tal_params(),
        'peak_temp': parse_peak_temp_params(),
        'conveyor_speed': parse_conveyor_speed_params(),
    }

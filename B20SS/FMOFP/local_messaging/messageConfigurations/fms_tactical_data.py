"""
Message Configuration for FMS Tactical Data

This configuration defines the structure for FMS tactical data messages.
Including g-force, angle of attack, sideslip, energy state, and flight mode.
"""

from datetime import datetime
from FMOFP.local_messaging.command_word_map_fms import get_fms_command_word

def create_fms_tactical_data_message(
    g_force=1.0,
    aoa=0.0,
    sideslip=0.0,
    energy_state=0.0,
    mode="NORMAL",
    timestamp=None
):
    """
    Create a message containing FMS tactical data
    
    Args:
        g_force (float): Current G-force
        aoa (float): Angle of attack in degrees
        sideslip (float): Sideslip angle in degrees
        energy_state (float): Aircraft energy state (0-100)
        mode (str): Flight mode: NORMAL, COMBAT, STEALTH, etc.
        timestamp (float, optional): Message timestamp, defaults to current time
    
    Returns:
        dict: FMS tactical data message
    """
    if timestamp is None:
        timestamp = datetime.now().timestamp()
    
    # Validate mode
    valid_modes = ["NORMAL", "COMBAT", "STEALTH", "TRAINING", "EMERGENCY"]
    if mode not in valid_modes:
        mode = "NORMAL"
    
    return {
        "message_type": "FMS_TACTICAL_STATUS",
        "command_word": get_fms_command_word("FMS_TACTICAL_STATUS"),
        "timestamp": timestamp,
        "data": {
            "g_force": g_force,
            "aoa": aoa,
            "sideslip": sideslip,
            "energy_state": energy_state,
            "mode": mode
        }
    }

def encode_fms_tactical_data(message):
    """
    Encode FMS tactical data message for 1553B transmission
    
    Args:
        message (dict): FMS tactical data message
    
    Returns:
        list: List of 16-bit integer data words
    """
    # First word is a message identifier
    data_words = [0x050D]  # FMS_TACTICAL_STATUS identifier
    
    # Scale values to fit in 16-bit integers
    data = message["data"]
    
    # G-force (0-9.99 scale by 100)
    g_force_int = min(999, max(0, int(data["g_force"] * 100))) & 0xFFFF
    
    # AoA (-40 to +40 degrees, scale by 100, add 4000 to make positive)
    aoa_adjusted = int(data["aoa"] * 100) + 4000
    aoa_int = min(8000, max(0, aoa_adjusted)) & 0xFFFF
    
    # Sideslip (-20 to +20 degrees, scale by 100, add 2000 to make positive)
    sideslip_adjusted = int(data["sideslip"] * 100) + 2000
    sideslip_int = min(4000, max(0, sideslip_adjusted)) & 0xFFFF
    
    # Energy state (0-100)
    energy_int = min(100, max(0, int(data["energy_state"]))) & 0xFFFF
    
    # Mode (encoded as integer)
    mode_map = {
        "NORMAL": 0,
        "COMBAT": 1,
        "STEALTH": 2,
        "TRAINING": 3,
        "EMERGENCY": 4
    }
    mode_int = mode_map.get(data["mode"], 0) & 0xFFFF
    
    # Add data words in a defined order
    data_words.extend([g_force_int, aoa_int, sideslip_int, energy_int, mode_int])
    
    return data_words

def decode_fms_tactical_data(data_words):
    """
    Decode 1553B data words into FMS tactical data message
    
    Args:
        data_words (list): List of 16-bit integer data words
    
    Returns:
        dict: Decoded FMS tactical data message
    """
    if len(data_words) < 6:
        raise ValueError("Insufficient data words for FMS tactical data")
    
    # Check message identifier
    if data_words[0] != 0x050D:
        raise ValueError(f"Invalid message identifier: {data_words[0]:04X}, expected 0x050D")
    
    # Extract and scale values
    g_force = (data_words[1] & 0xFFFF) / 100.0
    
    # Convert AoA back to signed range
    aoa_adjusted = data_words[2] & 0xFFFF
    aoa = (aoa_adjusted - 4000) / 100.0
    
    # Convert sideslip back to signed range
    sideslip_adjusted = data_words[3] & 0xFFFF
    sideslip = (sideslip_adjusted - 2000) / 100.0
    
    # Extract energy state
    energy_state = data_words[4] & 0xFFFF
    
    # Extract mode
    mode_int = data_words[5] & 0xFFFF
    mode_map = {
        0: "NORMAL",
        1: "COMBAT",
        2: "STEALTH",
        3: "TRAINING",
        4: "EMERGENCY"
    }
    mode = mode_map.get(mode_int, "NORMAL")
    
    # Create message
    return create_fms_tactical_data_message(
        g_force=g_force,
        aoa=aoa,
        sideslip=sideslip,
        energy_state=energy_state,
        mode=mode,
        timestamp=datetime.now().timestamp()
    )

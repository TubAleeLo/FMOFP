"""
Message Configuration for FMS Velocity Data

This configuration defines the structure for FMS velocity data messages.
Including airspeed, ground speed, vertical speed, and Mach number.
"""

from datetime import datetime
from FMOFP.local_messaging.command_word_map_fms import get_fms_command_word

def create_fms_velocity_data_message(
    airspeed=0.0,
    ground_speed=0.0,
    vertical_speed=0.0,
    mach=0.0,
    timestamp=None
):
    """
    Create a message containing FMS velocity data
    
    Args:
        airspeed (float): Aircraft airspeed in knots
        ground_speed (float): Ground speed in knots
        vertical_speed (float): Vertical speed in feet/minute
        mach (float): Mach number
        timestamp (float, optional): Message timestamp, defaults to current time
    
    Returns:
        dict: FMS velocity data message
    """
    if timestamp is None:
        timestamp = datetime.now().timestamp()
    
    return {
        "message_type": "FMS_FLIGHT_DATA",
        "command_word": get_fms_command_word("FMS_FLIGHT_DATA"),
        "timestamp": timestamp,
        "data": {
            "airspeed": airspeed,
            "ground_speed": ground_speed,
            "vertical_speed": vertical_speed,
            "mach": mach
        }
    }

def encode_fms_velocity_data(message):
    """
    Encode FMS velocity data message for 1553B transmission
    
    Args:
        message (dict): FMS velocity data message
    
    Returns:
        list: List of 16-bit integer data words
    """
    # First word is a message identifier
    data_words = [0x0505]  # FMS_FLIGHT_DATA identifier (velocity subset)
    
    # Second word is a subtype identifier for velocity data
    data_words.append(0x0001)  # Velocity data subtype
    
    # Scale values to fit in 16-bit integers
    data = message["data"]
    
    # Airspeed (0-999.9 knots, scale by 10)
    airspeed_int = min(9999, max(0, int(data["airspeed"] * 10))) & 0xFFFF
    
    # Ground speed (0-999.9 knots, scale by 10)
    ground_speed_int = min(9999, max(0, int(data["ground_speed"] * 10))) & 0xFFFF
    
    # Vertical speed (-32768 to 32767 feet/minute)
    # Convert to range 0-65535 by adding 32768
    vs_adjusted = int(data["vertical_speed"]) + 32768
    vs_int = min(65535, max(0, vs_adjusted)) & 0xFFFF
    
    # Mach number (0-5.999, scale by 1000)
    mach_int = min(5999, max(0, int(data["mach"] * 1000))) & 0xFFFF
    
    # Add data words in a defined order
    data_words.extend([airspeed_int, ground_speed_int, vs_int, mach_int])
    
    return data_words

def decode_fms_velocity_data(data_words):
    """
    Decode 1553B data words into FMS velocity data message
    
    Args:
        data_words (list): List of 16-bit integer data words
    
    Returns:
        dict: Decoded FMS velocity data message
    """
    if len(data_words) < 6:
        raise ValueError("Insufficient data words for FMS velocity data")
    
    # Check message identifier and subtype
    if data_words[0] != 0x0505 or data_words[1] != 0x0001:
        raise ValueError(f"Invalid message identifier: {data_words[0]:04X}:{data_words[1]:04X}, expected 0x0505:0x0001")
    
    # Extract and scale values
    airspeed = (data_words[2] & 0xFFFF) / 10.0
    ground_speed = (data_words[3] & 0xFFFF) / 10.0
    
    # Convert vertical speed back to signed range
    vs_adjusted = data_words[4] & 0xFFFF
    vertical_speed = vs_adjusted - 32768
    
    # Extract mach
    mach = (data_words[5] & 0xFFFF) / 1000.0
    
    # Create message
    return create_fms_velocity_data_message(
        airspeed=airspeed,
        ground_speed=ground_speed,
        vertical_speed=vertical_speed,
        mach=mach,
        timestamp=datetime.now().timestamp()
    )

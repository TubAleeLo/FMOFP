"""
Message Configuration for FMS Navigation Data

This configuration defines the structure for FMS navigation data messages.
Including position, altitude, heading, and other navigation-related parameters.
"""

from datetime import datetime
from FMOFP.local_messaging.command_word_map_fms import get_fms_command_word

def create_fms_navigation_data_message(
    latitude=0.0,
    longitude=0.0,
    altitude=0.0,
    heading=0.0,
    track=0.0,
    active_waypoint=0,
    timestamp=None
):
    """
    Create a message containing FMS navigation data
    
    Args:
        latitude (float): Current latitude in degrees
        longitude (float): Current longitude in degrees
        altitude (float): Current altitude in feet
        heading (float): Current heading in degrees
        track (float): Ground track in degrees
        active_waypoint (int): Index of active waypoint
        timestamp (float, optional): Message timestamp, defaults to current time
    
    Returns:
        dict: FMS navigation data message
    """
    if timestamp is None:
        timestamp = datetime.now().timestamp()
    
    return {
        "message_type": "FMS_UPDATE_NAVIGATION",
        "command_word": get_fms_command_word("FMS_UPDATE_NAVIGATION"),
        "timestamp": timestamp,
        "data": {
            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude,
            "heading": heading,
            "track": track,
            "active_waypoint": active_waypoint
        }
    }

def encode_fms_navigation_data(message):
    """
    Encode FMS navigation data message for 1553B transmission
    
    Args:
        message (dict): FMS navigation data message
    
    Returns:
        list: List of 16-bit integer data words
    """
    # First word is a message identifier
    data_words = [0x0502]  # FMS_UPDATE_NAVIGATION identifier
    
    # Scale values to fit in 16-bit integers
    data = message["data"]
    
    # Scale latitude/longitude: 
    # Convert to 0-359.99 degrees format (add 180 to latitude, normalize to 0-360)
    lat_adjusted = (data["latitude"] + 90.0) % 180.0
    lon_adjusted = (data["longitude"] + 180.0) % 360.0
    
    # Scale by 100 for 2 decimal places
    lat_int = int(lat_adjusted * 100) & 0xFFFF
    lon_int = int(lon_adjusted * 100) & 0xFFFF
    
    # Scale altitude (feet): allow range 0-65535 feet
    alt_int = min(65535, max(0, int(data["altitude"]))) & 0xFFFF
    
    # Scale heading and track (0-359.99 degrees, scale by 100)
    hdg_int = int((data["heading"] % 360.0) * 100) & 0xFFFF
    trk_int = int((data["track"] % 360.0) * 100) & 0xFFFF
    
    # Active waypoint (0-65535)
    wpt_int = min(65535, max(0, data["active_waypoint"])) & 0xFFFF
    
    # Add data words in a defined order
    data_words.extend([lat_int, lon_int, alt_int, hdg_int, trk_int, wpt_int])
    
    return data_words

def decode_fms_navigation_data(data_words):
    """
    Decode 1553B data words into FMS navigation data message
    
    Args:
        data_words (list): List of 16-bit integer data words
    
    Returns:
        dict: Decoded FMS navigation data message
    """
    if len(data_words) < 7:
        raise ValueError("Insufficient data words for FMS navigation data")
    
    # Check message identifier
    if data_words[0] != 0x0502:
        raise ValueError(f"Invalid message identifier: {data_words[0]:04X}, expected 0x0502")
    
    # Extract and scale values
    lat_adjusted = (data_words[1] & 0xFFFF) / 100.0
    lon_adjusted = (data_words[2] & 0xFFFF) / 100.0
    
    # Convert back to signed latitude/longitude
    latitude = lat_adjusted - 90.0
    longitude = lon_adjusted - 180.0
    
    # Extract remaining values
    altitude = data_words[3] & 0xFFFF
    heading = (data_words[4] & 0xFFFF) / 100.0
    track = (data_words[5] & 0xFFFF) / 100.0
    active_waypoint = data_words[6] & 0xFFFF
    
    # Create message
    return create_fms_navigation_data_message(
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
        heading=heading,
        track=track,
        active_waypoint=active_waypoint,
        timestamp=datetime.now().timestamp()
    )

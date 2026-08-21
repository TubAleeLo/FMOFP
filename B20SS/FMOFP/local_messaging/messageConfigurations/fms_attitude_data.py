"""
Message Configuration for FMS Attitude Data

This configuration defines the structure for FMS attitude data messages.
Including roll, pitch, yaw angles and rates.
"""

from datetime import datetime
from FMOFP.local_messaging.command_word_map_fms import get_fms_command_word

def create_fms_attitude_data_message(
    roll=0.0,
    pitch=0.0,
    yaw=0.0,
    roll_rate=0.0,
    pitch_rate=0.0,
    yaw_rate=0.0,
    timestamp=None
):
    """
    Create a message containing FMS attitude data
    
    Args:
        roll (float): Roll angle in degrees
        pitch (float): Pitch angle in degrees
        yaw (float): Yaw angle in degrees
        roll_rate (float): Roll rate in degrees/second
        pitch_rate (float): Pitch rate in degrees/second
        yaw_rate (float): Yaw rate in degrees/second
        timestamp (float, optional): Message timestamp, defaults to current time
    
    Returns:
        dict: FMS attitude data message
    """
    if timestamp is None:
        timestamp = datetime.now().timestamp()
    
    return {
        "message_type": "FMS_UPDATE_ATTITUDE",
        "command_word": get_fms_command_word("FMS_UPDATE_ATTITUDE"),
        "timestamp": timestamp,
        "data": {
            "roll": roll,
            "pitch": pitch,
            "yaw": yaw,
            "roll_rate": roll_rate,
            "pitch_rate": pitch_rate,
            "yaw_rate": yaw_rate
        }
    }

def encode_fms_attitude_data(message):
    """
    Encode FMS attitude data message for 1553B transmission
    
    Args:
        message (dict): FMS attitude data message
    
    Returns:
        list: List of 16-bit integer data words
    """
    # First word is a message identifier
    data_words = [0x0501]  # FMS_UPDATE_ATTITUDE identifier
    
    # Scale values to fit in 16-bit integers (scale by 100 for 2 decimal places)
    data = message["data"]
    roll_int = int(data["roll"] * 100) & 0xFFFF
    pitch_int = int(data["pitch"] * 100) & 0xFFFF
    yaw_int = int(data["yaw"] * 100) & 0xFFFF
    roll_rate_int = int(data["roll_rate"] * 100) & 0xFFFF
    pitch_rate_int = int(data["pitch_rate"] * 100) & 0xFFFF
    yaw_rate_int = int(data["yaw_rate"] * 100) & 0xFFFF
    
    # Add data words in a defined order
    data_words.extend([roll_int, pitch_int, yaw_int, roll_rate_int, pitch_rate_int, yaw_rate_int])
    
    return data_words

def decode_fms_attitude_data(data_words):
    """
    Decode 1553B data words into FMS attitude data message
    
    Args:
        data_words (list): List of 16-bit integer data words
    
    Returns:
        dict: Decoded FMS attitude data message
    """
    if len(data_words) < 7:
        raise ValueError("Insufficient data words for FMS attitude data")
    
    # Check message identifier
    if data_words[0] != 0x0501:
        raise ValueError(f"Invalid message identifier: {data_words[0]:04X}, expected 0x0501")
    
    # Extract and scale values
    roll = (data_words[1] & 0xFFFF) / 100.0
    pitch = (data_words[2] & 0xFFFF) / 100.0
    yaw = (data_words[3] & 0xFFFF) / 100.0
    roll_rate = (data_words[4] & 0xFFFF) / 100.0
    pitch_rate = (data_words[5] & 0xFFFF) / 100.0
    yaw_rate = (data_words[6] & 0xFFFF) / 100.0
    
    # Sign-extend values (to handle negative values)
    if roll > 327.67:  # 0x7FFF/100
        roll -= 655.36  # 0xFFFF/100
    if pitch > 327.67:
        pitch -= 655.36
    if yaw > 327.67:
        yaw -= 655.36
    if roll_rate > 327.67:
        roll_rate -= 655.36
    if pitch_rate > 327.67:
        pitch_rate -= 655.36
    if yaw_rate > 327.67:
        yaw_rate -= 655.36
    
    # Create message
    return create_fms_attitude_data_message(
        roll=roll,
        pitch=pitch,
        yaw=yaw,
        roll_rate=roll_rate,
        pitch_rate=pitch_rate,
        yaw_rate=yaw_rate,
        timestamp=datetime.now().timestamp()
    )

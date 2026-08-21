"""
Centralized message type definitions for the FMOFP system.
These constants should be used throughout the codebase instead of string literals.
This ensures consistency with MIL-STD-1553B protocol requirements.
Will be mirrored in remote systems for their use.
"""

import enum
from typing import Dict, Any, Optional, List, Union

# Base message type enum
class BaseMessageType(enum.Enum):
    """Base enum for message types across the FMOFP system."""
    # System-wide message types
    UNKNOWN = 0
    COMMAND = 1
    STATUS = 2
    DATA = 3
    EVENT = 4
    ERROR = 5

    # Radar-specific message types
    RADAR_COMMAND = 10
    RADAR_STATUS = 11
    RADAR_DATA = 12
    RADAR_MODE_CHANGE = 13
    RADAR_TRACK = 14
    RADAR_SCAN = 15

    # FMS-specific message types
    FMS_COMMAND = 20
    FMS_STATUS = 21
    FMS_DATA = 22
    FMS_MODE_CHANGE = 23
    FMS_NAVIGATION = 24
    FMS_ATTITUDE = 25

    # Display-specific message types
    DISPLAY_COMMAND = 30
    DISPLAY_STATUS = 31
    DISPLAY_DATA = 32
    DISPLAY_MODE_CHANGE = 33

    @classmethod
    def from_string(cls, name: str) -> 'BaseMessageType':
        """Convert a string name to the corresponding enum value."""
        try:
            return cls[name.upper()]
        except KeyError:
            # Default to UNKNOWN if the name is not recognized
            return cls.UNKNOWN

    @classmethod
    def to_dict(cls) -> Dict[str, int]:
        """Convert the enum to a dictionary for serialization."""
        return {name: member.value for name, member in cls.__members__.items()}

# Weather Radar Message Types
WEATHER_RADAR_MODE_CHANGE_REQUEST = 'weather_radarModeChangeRequest'
WEATHER_RADAR_MODE_CHANGE_RESPONSE = 'weather_radarModeChangeResponse'
WEATHER_RADAR_STATUS_REQUEST = 'weather_radarStatusRequest'
WEATHER_RADAR_STATUS_RESPONSE = 'weather_radarStatusResponse'
WEATHER_RADAR_VIL_REQUEST = 'weather_radarVILRequest'
WEATHER_RADAR_VIL_RESPONSE = 'weather_radarVILResponse'
WEATHER_RADAR_PRECIPITATION_REQUEST = 'weather_radarPrecipitationRequest'
WEATHER_RADAR_PRECIPITATION_RESPONSE = 'weather_radarPrecipitationResponse'
WEATHER_RADAR_ECHO_TOP_REQUEST = 'weather_radarEchoTopRequest'
WEATHER_RADAR_ECHO_TOP_RESPONSE = 'weather_radarEchoTopResponse'
WEATHER_RADAR_STORM_CELL_REQUEST = 'weather_radarStormCellRequest'
WEATHER_RADAR_STORM_CELL_RESPONSE = 'weather_radarStormCellResponse'

# TFR Radar Message Types
TFR_RADAR_MODE_CHANGE_REQUEST = 'tfr_radarModeChangeRequest'
TFR_RADAR_MODE_CHANGE_RESPONSE = 'tfr_radarModeChangeResponse'
TFR_RADAR_STATUS_REQUEST = 'tfr_radarStatusRequest'
TFR_RADAR_STATUS_RESPONSE = 'tfr_radarStatusResponse'
TFR_RADAR_ELEVATION_DATA_REQUEST = 'tfr_radarElevationDataRequest'
TFR_RADAR_ELEVATION_DATA_RESPONSE = 'tfr_radarElevationDataResponse'

# SAR Radar Message Types
SAR_RADAR_MODE_CHANGE_REQUEST = 'sar_radarModeChangeRequest'
SAR_RADAR_MODE_CHANGE_RESPONSE = 'sar_radarModeChangeResponse'
SAR_RADAR_STATUS_REQUEST = 'sar_radarStatusRequest'
SAR_RADAR_STATUS_RESPONSE = 'sar_radarStatusResponse'
SAR_RADAR_IMAGERY_REQUEST = 'sar_radarImageryRequest'
SAR_RADAR_IMAGERY_RESPONSE = 'sar_radarImageryResponse'

# Targeting Radar Message Types
TARGETING_RADAR_MODE_CHANGE_REQUEST = 'targeting_radarModeChangeRequest'
TARGETING_RADAR_MODE_CHANGE_RESPONSE = 'targeting_radarModeChangeResponse'
TARGETING_RADAR_STATUS_REQUEST = 'targeting_radarStatusRequest'
TARGETING_RADAR_STATUS_RESPONSE = 'targeting_radarStatusResponse'
TARGETING_RADAR_TRACK_REQUEST = 'targeting_radarTrackRequest'
TARGETING_RADAR_TRACK_RESPONSE = 'targeting_radarTrackResponse'
TARGETING_RADAR_LOCK_REQUEST = 'targeting_radarLockRequest'
TARGETING_RADAR_LOCK_RESPONSE = 'targeting_radarLockResponse'

# AEWC Radar Message Types
AEWC_RADAR_MODE_CHANGE_REQUEST = 'aewc_radarModeChangeRequest'
AEWC_RADAR_MODE_CHANGE_RESPONSE = 'aewc_radarModeChangeResponse'
AEWC_RADAR_STATUS_REQUEST = 'aewc_radarStatusRequest'
AEWC_RADAR_STATUS_RESPONSE = 'aewc_radarStatusResponse'
AEWC_RADAR_TRACK_REQUEST = 'aewc_radarTrackRequest'
AEWC_RADAR_TRACK_RESPONSE = 'aewc_radarTrackResponse'
AEWC_RADAR_SECTOR_SCAN_REQUEST = 'aewc_radarSectorScanRequest'
AEWC_RADAR_SECTOR_SCAN_RESPONSE = 'aewc_radarSectorScanResponse'

# FMS Message Types
FMS_MODE_CHANGE_REQUEST = 'fms_modeChangeRequest'
FMS_MODE_CHANGE_RESPONSE = 'fms_modeChangeResponse'
FMS_STATUS_REQUEST = 'fms_statusRequest'
FMS_STATUS_RESPONSE = 'fms_statusResponse'
FMS_ATTITUDE_UPDATE_REQUEST = 'fms_attitudeUpdateRequest'
FMS_ATTITUDE_UPDATE_RESPONSE = 'fms_attitudeUpdateResponse'
FMS_NAVIGATION_UPDATE_REQUEST = 'fms_navigationUpdateRequest'
FMS_NAVIGATION_UPDATE_RESPONSE = 'fms_navigationUpdateResponse'
FMS_MANEUVER_REQUEST = 'fms_maneuverRequest'
FMS_MANEUVER_RESPONSE = 'fms_maneuverResponse'

# Display Message Types
DISPLAY_MODE_REQUEST = 'display_mode_request'
DISPLAY_MODE_RESPONSE = 'display_mode_response'
DISPLAY_STATUS_REQUEST = 'display_status_request'
DISPLAY_STATUS_RESPONSE = 'display_status_response'
DISPLAY_DATA_REQUEST = 'display_data_request'
DISPLAY_DATA_RESPONSE = 'display_data_response'
DISPLAY_SHOW_REQUEST = 'display_show_request'
DISPLAY_MODE_CHANGE = 'mode_change'
DISPLAY_MODE_CHANGE_COMPLETION = 'mode_change_completion'

# Command Names/Types
COMMAND_TYPE_MODE_CHANGE = 'mode_change'
COMMAND_TYPE_MODE_CHANGE_COMPLETE = 'mode_change_complete'
COMMAND_TYPE_DATA_REQUEST = 'data_request'
COMMAND_TYPE_DATA_RESPONSE = 'data_response'
COMMAND_TYPE_VIL_DATA = 'vil_data'
COMMAND_TYPE_PRECIPITATION_DATA = 'precipitation_data'

# Communications message types
COMMS_STATUS_REQUEST          = 'comms_statusRequest'
COMMS_STATUS_RESPONSE         = 'comms_statusResponse'
COMMS_RADIO_FREQ_SET          = 'comms_radioFreqSet'
COMMS_RADIO_MODE_SET          = 'comms_radioModeSet'
COMMS_SATCOM_ACQUIRE          = 'comms_satcomAcquire'
COMMS_DATALINK_MODE_SET       = 'comms_datalinkModeSet'
COMMS_TRANSMIT_RADIO          = 'comms_transmitRadio'
COMMS_SEND_SATCOM             = 'comms_sendSatcom'
COMMS_SEND_DATALINK           = 'comms_sendDatalink'
COMMS_DATA_UPDATE             = 'comms_dataUpdate'

# Mission planning message types
MISSION_STATUS_REQUEST        = 'mission_statusRequest'
MISSION_STATUS_RESPONSE       = 'mission_statusResponse'
MISSION_PHASE_SET             = 'mission_phaseSet'
MISSION_PHASE_ADVANCE         = 'mission_phaseAdvance'
MISSION_WAYPOINT_ADD          = 'mission_waypointAdd'
MISSION_WAYPOINT_REMOVE       = 'mission_waypointRemove'
MISSION_TARGET_DESIGNATE      = 'mission_targetDesignate'
MISSION_TARGET_ENGAGE         = 'mission_targetEngage'
MISSION_TARGET_BDA            = 'mission_targetBDA'
MISSION_TARGET_UPDATE         = 'mission_targetUpdate'
MISSION_UNIT_ADD              = 'mission_unitAdd'
MISSION_UNIT_UPDATE           = 'mission_unitUpdate'
MISSION_ROUTE_OPTIMISE        = 'mission_routeOptimise'
MISSION_OBJECTIVES_SET        = 'mission_objectivesSet'
MISSION_ROE_SET               = 'mission_roeSet'
MISSION_INTEL_UPDATE          = 'mission_intelUpdate'
MISSION_DATA_UPDATE           = 'mission_dataUpdate'

# Helper functions
def get_message_type(message):
    """
    Extract message type from various message formats.

    Args:
        message: The message object, which could be a dict, object, or other format

    Returns:
        str: The message type or None if not found
    """
    if isinstance(message, dict):
        # Check direct message_type key
        if 'message_type' in message:
            return message['message_type']

        # Check in metadata
        if 'metadata' in message and isinstance(message['metadata'], dict):
            msg_type = message['metadata'].get('message_type')
            if msg_type:
                return msg_type

        # Check in additional_info (legacy format)
        if 'additional_info' in message and isinstance(message['additional_info'], dict):
            return message['additional_info'].get('message_type')

    # Handle object attributes
    elif hasattr(message, 'message_type'):
        return message.message_type
    elif hasattr(message, 'metadata') and hasattr(message.metadata, 'get'):
        return message.metadata.get('message_type')

    return None


def is_message_type(message, expected_type):
    """
    Check if message matches expected type, with case-insensitive comparison.

    Args:
        message: The message to check
        expected_type: The expected message type

    Returns:
        bool: True if the message type matches, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type or not expected_type:
        return False

    return msg_type.lower() == expected_type.lower()


def is_vil_message(message):
    """
    Check if a message is a VIL data message.

    Args:
        message: The message to check

    Returns:
        bool: True if the message is a VIL data message, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type:
        return False

    msg_type_lower = msg_type.lower()
    return (msg_type_lower == WEATHER_RADAR_VIL_REQUEST.lower() or
            msg_type_lower == WEATHER_RADAR_VIL_RESPONSE.lower() or
            'vil' in msg_type_lower)


def is_precipitation_message(message):
    """
    Check if a message is a precipitation data message.

    Args:
        message: The message to check

    Returns:
        bool: True if the message is a precipitation data message, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type:
        return False

    msg_type_lower = msg_type.lower()
    return (msg_type_lower == WEATHER_RADAR_PRECIPITATION_REQUEST.lower() or
            msg_type_lower == WEATHER_RADAR_PRECIPITATION_RESPONSE.lower() or
            'precipitation' in msg_type_lower)


def is_mode_change_message(message):
    """
    Check if a message is a mode change message.

    Args:
        message: The message to check

    Returns:
        bool: True if the message is a mode change message, False otherwise
    """
    msg_type = get_message_type(message)
    if not msg_type:
        return False

    msg_type_lower = msg_type.lower()
    return ('modechange' in msg_type_lower.replace('_', '') or
            'mode_change' in msg_type_lower)



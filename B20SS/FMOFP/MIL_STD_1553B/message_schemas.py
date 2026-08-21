"""
MIL-STD-1553B Message Schemas

This module defines schemas for all message types used in the MIL-STD-1553B communication.
These schemas are the single source of truth for the structure of messages,
ensuring consistent encoding and decoding across the system.

Each schema defines:
- data_structure: List of field definitions with position and bit information
- data_word_count: Expected number of data words (or None if variable)
- metadata_fields: List of metadata fields that should be included
"""

from typing import Dict, List, Any, Optional, Union, Tuple

# ===== CONSTANTS FOR MESSAGE TYPES =====

# Weather Radar Message Types
WEATHER_RADAR_COMMAND = "weather_radarCommand"
WEATHER_RADAR_MODE_CHANGE_REQUEST = "weather_radarModeChangeRequest"
WEATHER_RADAR_MODE_CHANGE_RESPONSE = "weather_radarModeChangeResponse"
WEATHER_RADAR_STATUS_REQUEST = "weather_radarStatusRequest"
WEATHER_RADAR_STATUS_RESPONSE = "weather_radarStatusResponse"
WEATHER_RADAR_VIL_REQUEST = "weather_radarVILRequest"
WEATHER_RADAR_VIL_RESPONSE = "weather_radarVILResponse"
WEATHER_RADAR_PRECIPITATION_REQUEST = "weather_radarPrecipitationRequest"
WEATHER_RADAR_PRECIPITATION_RESPONSE = "weather_radarPrecipitationResponse"
WEATHER_RADAR_DATA = "weather_radarData"

# FMS Command Types
FLIGHT_MANAGEMENT_SYSTEM_COMMAND = "flightManagementSystemCommand"

# Radar System Message Types
RADAR_COMMAND = "radarCommand"
RADAR_STATUS_REQUEST = "radarStatusRequest"
RADAR_STATUS_RESPONSE = "radarStatusResponse"
RADAR_DATA_REQUEST = "radarDataRequest"
RADAR_DATA_RESPONSE = "radarDataResponse"

# Targeting Radar Message Types
TARGETING_RADAR_COMMAND = "targeting_radarCommand"
TARGETING_RADAR_MODE_CHANGE_REQUEST = "targeting_radarModeChangeRequest"
TARGETING_RADAR_MODE_CHANGE_RESPONSE = "targeting_radarModeChangeResponse"
TARGETING_RADAR_STATUS_REQUEST = "targeting_radarStatusRequest"
TARGETING_RADAR_STATUS_RESPONSE = "targeting_radarStatusResponse"
TARGETING_RADAR_TRACK_REQUEST = "targeting_radarTrackRequest"
TARGETING_RADAR_TRACK_RESPONSE = "targeting_radarTrackResponse"
TARGETING_RADAR_DATA = "targeting_radarData"

# AEWC Radar Message Types
AEWC_RADAR_COMMAND = "aewc_radarCommand"
AEWC_RADAR_MODE_CHANGE_REQUEST = "aewc_radarModeChangeRequest"
AEWC_RADAR_MODE_CHANGE_RESPONSE = "aewc_radarModeChangeResponse"
AEWC_RADAR_STATUS_REQUEST = "aewc_radarStatusRequest"
AEWC_RADAR_STATUS_RESPONSE = "aewc_radarStatusResponse"
AEWC_RADAR_SECTOR_SCAN_REQUEST = "aewc_radarSectorScanRequest"
AEWC_RADAR_SECTOR_SCAN_RESPONSE = "aewc_radarSectorScanResponse"
AEWC_RADAR_DATA = "aewc_radarData"

# TFR Radar Message Types
TFR_RADAR_COMMAND = "tfr_radarCommand"
TFR_RADAR_MODE_CHANGE_REQUEST = "tfr_radarModeChangeRequest"
TFR_RADAR_MODE_CHANGE_RESPONSE = "tfr_radarModeChangeResponse"
TFR_RADAR_STATUS_REQUEST = "tfr_radarStatusRequest"
TFR_RADAR_STATUS_RESPONSE = "tfr_radarStatusResponse"
TFR_RADAR_ELEVATION_DATA_REQUEST = "tfr_radarElevationDataRequest"
TFR_RADAR_ELEVATION_DATA_RESPONSE = "tfr_radarElevationDataResponse"
TFR_RADAR_DATA = "tfr_radarData"

# SAR Radar Message Types
SAR_RADAR_COMMAND = "sar_radarCommand"
SAR_RADAR_MODE_CHANGE_REQUEST = "sar_radarModeChangeRequest"
SAR_RADAR_MODE_CHANGE_RESPONSE = "sar_radarModeChangeResponse"
SAR_RADAR_STATUS_REQUEST = "sar_radarStatusRequest"
SAR_RADAR_STATUS_RESPONSE = "sar_radarStatusResponse"
SAR_RADAR_IMAGE_REQUEST = "sar_radarImageRequest"
SAR_RADAR_IMAGE_RESPONSE = "sar_radarImageResponse"
SAR_RADAR_DATA = "sar_radarData"

# FMS Message Types
FMS_COMMAND = "fmsCommand"
FMS_DATA_REQUEST = "fmsDataRequest"
FMS_DATA_RESPONSE = "fmsDataResponse"
FMS_STATUS_REQUEST = "fmsStatusRequest"
FMS_STATUS_RESPONSE = "fmsStatusResponse"
FMS_MODE_CHANGE_REQUEST = "fms_modeChangeRequest"
FMS_MODE_CHANGE_RESPONSE = "fms_modeChangeResponse"
FMS_ATTITUDE_UPDATE_REQUEST = "fms_attitudeUpdateRequest"
FMS_ATTITUDE_UPDATE_RESPONSE = "fms_attitudeUpdateResponse"
FMS_NAVIGATION_UPDATE_REQUEST = "fms_navigationUpdateRequest"
FMS_NAVIGATION_UPDATE_RESPONSE = "fms_navigationUpdateResponse"
FMS_MANEUVER_REQUEST = "fms_maneuverRequest"
FMS_MANEUVER_RESPONSE = "fms_maneuverResponse"

# Flight Control System Message Types
FCS_COMMAND = "flight_control_systemCommand"
FCS_DATA_REQUEST = "flight_control_systemDataRequest"
FCS_DATA_RESPONSE = "flight_control_systemDataResponse"
FCS_STATUS_REQUEST = "flight_control_systemStatusRequest"
FCS_STATUS_RESPONSE = "flight_control_systemStatusResponse"
FCS_MODE_CHANGE_REQUEST = "flight_control_systemModeChangeRequest"
FCS_MODE_CHANGE_RESPONSE = "flight_control_systemModeChangeResponse"
FCS_CONTROL_INPUT_REQUEST = "flight_control_systemControlInputRequest"
FCS_CONTROL_INPUT_RESPONSE = "flight_control_systemControlInputResponse"
FCS_ORIENTATION_DATA_REQUEST = "flight_control_systemOrientationDataRequest"
FCS_ORIENTATION_DATA_RESPONSE = "flight_control_systemOrientationDataResponse"

# Display Message Types
DISPLAY_COMMAND = "displayCommand"
DISPLAY_MODE_CHANGE = "display_mode_change"
DISPLAY_MODE_REQUEST = "display_mode_request"
DISPLAY_MODE_RESPONSE = "display_mode_response"
DISPLAY_DATA_UPDATE = "displayDataUpdate"
DISPLAY_DATA = "display_data"  # Added for display_data message type
DISPLAY_VIL_DATA = "display_vil_data"  # Added for VIL data display
DISPLAY_STATUS_REQUEST = "displayStatusRequest"
DISPLAY_STATUS_RESPONSE = "displayStatusResponse"

# BIT Message Types
BIT_COMMAND = "bitCommand"
BIT_STATUS_REQUEST = "bitStatusRequest"
BIT_STATUS_RESPONSE = "bitStatusResponse"
BIT_DATA_RESPONSE = "bitDataResponse"

# System Message Types
SYSTEM_COMMAND = "systemCommand"
SYSTEM_STATUS_REQUEST = "systemStatusRequest"
SYSTEM_STATUS_RESPONSE = "systemStatusResponse"
SYSTEM_DATA_REQUEST = "systemDataRequest"
SYSTEM_DATA_RESPONSE = "systemDataResponse"

# ===== CONSTANTS FOR COMMAND TYPES =====

# Command Types
COMMAND_TYPE_MODE_CHANGE = "mode_change"
COMMAND_TYPE_MODE_CHANGE_COMPLETE = "mode_change_complete"
COMMAND_TYPE_DATA_REQUEST = "data_request"
COMMAND_TYPE_DATA_RESPONSE = "data_response"
COMMAND_TYPE_STATUS_REQUEST = "status_request"
COMMAND_TYPE_STATUS_RESPONSE = "status_response"
COMMAND_TYPE_VIL_DATA = "vil_data"
COMMAND_TYPE_PRECIPITATION_DATA = "precipitation_data"
COMMAND_TYPE_SYSTEM_COMMAND = "system_command"
COMMAND_TYPE_DISPLAY_COMMAND = "display_command"

# ===== MAPPING TABLES =====

# Maps mode names to their numeric values
MODE_VALUE_MAP = {
                    # Universal Base Modes (0-9)
                    'INITIALIZING': -1,
                    'STANDBY': 0,
                    'NORMAL': 1,
                    'DEGRADED': 2,
                    'TEST': 3,
                    'MAINTENANCE': 4,
                    'EMERGENCY': 5,
                    'FAILURE': 6,
                    'RECOVERY': 7,
                    'CALIBRATION': 8,
                    
                    # Weather Radar Modes (10-19)
                    'SURVEILLANCE': 10,
                    'MAPPING': 11,
                    'TURBULENCE': 12,
                    'WINDSHEAR': 13,
                    'PRECIPITATION': 14,
                    'WEATHER': 6,  # Legacy mapping
                    
                    # TFR Radar Modes (20-29)
                    'SEARCH': 20,
                    'TRACK': 21,
                    'ACTIVE': 22,
                    'TERRAIN_FOLLOWING': 23,
                    'OBSTACLE_AVOIDANCE': 24,
                    'GROUND_MAPPING': 25,
                    
                    # SAR Radar Modes (30-39)
                    'STRIPMAP': 30,
                    'SPOTLIGHT': 31,
                    'SCANSAR': 32,
                    'INTERFEROMETRIC': 33,
                    'DOPPLER_BEAM': 34,
                    
                    # Targeting Radar Modes (40-49)
                    'TARGET_SEARCH': 40,
                    'TARGET_TRACK': 41,
                    'LOCK': 42,
                    'TERRAIN_AVOIDANCE': 43,
                    
                    # AEWC Radar Modes (50-59)
                    'AEWC_SEARCH': 50,
                    'AEWC_SURVEILLANCE': 51,
                    'SECTOR_SCAN': 52,
                    'STEALTH_DETECTION': 53,
                    'ELECTRONIC_PROTECTION': 54
}

# Maps mode values to their names (reverse of MODE_VALUE_MAP)
MODE_NAME_MAP = {v: k for k, v in MODE_VALUE_MAP.items()}

# ===== MESSAGE SCHEMAS =====

# Constants for VIL-specific command names
DISPLAY_VIL_DATA = "DISPLAY_VIL_DATA"

# FMS Status Types
FLIGHT_MANAGEMENT_SYSTEM_STATUS = "flightManagementSystemStatus"

MESSAGE_SCHEMAS = {
    # TFR Radar Command
    TFR_RADAR_COMMAND: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode"]
    },
    
    # TFR Radar Mode Change Request
    TFR_RADAR_MODE_CHANGE_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode"]
    },
    
    # TFR Radar Mode Change Response
    TFR_RADAR_MODE_CHANGE_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"},
            {"field": "old_mode_value", "word_index": -2, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode", "old_mode", "new_mode"]
    },
    
    # TFR Radar Status Request
    TFR_RADAR_STATUS_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id"]
    },
    
    # TFR Radar Status Response
    TFR_RADAR_STATUS_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "health_status", "word_index": -2, "bits": "0"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "health_status", "mode"]
    },
    
    # TFR Radar Elevation Data Request
    TFR_RADAR_ELEVATION_DATA_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "scan_type", "word_index": 3, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "scan_type"]
    },
    
    # TFR Radar Elevation Data Response
    TFR_RADAR_ELEVATION_DATA_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "data_count", "word_index": 3, "bits": "all"},
            {"field": "scan_type", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "data_count", "scan_type"]
    },
    
    # TFR Radar Data
    TFR_RADAR_DATA: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "data_type", "word_index": 3, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "data_type"]
    },
    
    # SAR Radar Command
    SAR_RADAR_COMMAND: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode"]
    },
    
    # SAR Radar Mode Change Request
    SAR_RADAR_MODE_CHANGE_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode"]
    },
    
    # SAR Radar Mode Change Response
    SAR_RADAR_MODE_CHANGE_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"},
            {"field": "old_mode_value", "word_index": -2, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode", "old_mode", "new_mode"]
    },
    
    # SAR Radar Status Request
    SAR_RADAR_STATUS_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id"]
    },
    
    # SAR Radar Status Response
    SAR_RADAR_STATUS_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "health_status", "word_index": -2, "bits": "0"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "health_status", "mode"]
    },
    
    # SAR Radar Image Request
    SAR_RADAR_IMAGE_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "image_type", "word_index": 3, "bits": "all"},
            {"field": "resolution", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "image_type", "resolution"]
    },
    
    # SAR Radar Image Response
    SAR_RADAR_IMAGE_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "data_count", "word_index": 3, "bits": "all"},
            {"field": "image_type", "word_index": 4, "bits": "all"},
            {"field": "resolution", "word_index": 5, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "data_count", "image_type", "resolution"]
    },
    
    # SAR Radar Data
    SAR_RADAR_DATA: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "data_type", "word_index": 3, "bits": "all"},
            {"field": "resolution", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "data_type", "resolution"]
    },
    # Targeting Radar Command
    TARGETING_RADAR_COMMAND: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode"]
    },
    
    # Targeting Radar Mode Change Request
    TARGETING_RADAR_MODE_CHANGE_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode"]
    },
    
    # Targeting Radar Mode Change Response
    TARGETING_RADAR_MODE_CHANGE_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"},
            {"field": "old_mode_value", "word_index": -2, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode", "old_mode", "new_mode"]
    },
    
    # Targeting Radar Status Request
    TARGETING_RADAR_STATUS_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id"]
    },
    
    # Targeting Radar Status Response
    TARGETING_RADAR_STATUS_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "health_status", "word_index": -2, "bits": "0"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "health_status", "mode"]
    },
    
    # Targeting Radar Track Request
    TARGETING_RADAR_TRACK_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "track_type", "word_index": 3, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "track_type"]
    },
    
    # Targeting Radar Track Response
    TARGETING_RADAR_TRACK_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "track_type", "word_index": 3, "bits": "all"},
            {"field": "track_count", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "track_type", "track_count"]
    },
    
    # Targeting Radar Data
    TARGETING_RADAR_DATA: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "data_type", "word_index": 3, "bits": "all"},
            {"field": "target_count", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "data_type", "target_count"]
    },
    
    # AEWC Radar Command
    AEWC_RADAR_COMMAND: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode"]
    },
    
    # AEWC Radar Mode Change Request
    AEWC_RADAR_MODE_CHANGE_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode"]
    },
    
    # AEWC Radar Mode Change Response
    AEWC_RADAR_MODE_CHANGE_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"},
            {"field": "old_mode_value", "word_index": -2, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode", "old_mode", "new_mode"]
    },
    
    # AEWC Radar Status Request
    AEWC_RADAR_STATUS_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id"]
    },
    
    # AEWC Radar Status Response
    AEWC_RADAR_STATUS_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "health_status", "word_index": -2, "bits": "0"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "health_status", "mode"]
    },
    
    # AEWC Radar Sector Scan Request
    AEWC_RADAR_SECTOR_SCAN_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "sector_type", "word_index": 3, "bits": "all"},
            {"field": "sector_parameters", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "sector_type", "sector_parameters"]
    },
    
    # AEWC Radar Sector Scan Response
    AEWC_RADAR_SECTOR_SCAN_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "sector_type", "word_index": 3, "bits": "all"},
            {"field": "status_code", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "sector_type", "status_code"]
    },
    
    # AEWC Radar Data
    AEWC_RADAR_DATA: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "data_type", "word_index": 3, "bits": "all"},
            {"field": "sector_id", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "data_type", "sector_id"]
    },
    
    # Flight Management System Status
    FLIGHT_MANAGEMENT_SYSTEM_STATUS: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "health_status", "word_index": 3, "bits": "0"},
            {"field": "mode_value", "word_index": 4, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "health_status", "mode"]
    },
    # NOTE (production readiness re-analysis, August 2026): a duplicate
    # WEATHER_RADAR_COMMAND key used to exist here (removed by this change),
    # shadowed by a second, later definition further down in this same dict
    # literal (see the "###### WEATHER RADAR MESSAGES ######" section below).
    # Python dict literals silently keep only the last occurrence of a
    # duplicate key -- found via `ruff check --select F602`
    # (multi-value-repeated-key-variable). The two definitions genuinely
    # differed (this deleted one used 4-bit mode_value encoding and included
    # "mode" in metadata_fields; the surviving one uses 3-bit encoding and
    # omits "mode"), so this deleted definition had been completely dead and
    # unreachable the entire time -- every real lookup of
    # MESSAGE_SCHEMAS[WEATHER_RADAR_COMMAND] has always resolved to the
    # surviving definition, which is what every live boot/test this session
    # has already exercised without error. Removed the dead one rather than
    # the live one to avoid any behavior change.
# VIL Display Data
    DISPLAY_VIL_DATA: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "display_id", "word_index": 3, "bits": "all"},
            {"field": "data_type", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "display_id", "data_type", "vil_message", "vil_data_available"]
    },
    ##### FLIGHT CONTROL SYSTEM MESSAGE TYPES #####
    
    # Flight Control System Command
    FCS_COMMAND: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode"]
    },
    
    # Flight Control System Status Request
    FCS_STATUS_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id"]
    },
    
    # Flight Control System Status Response
    FCS_STATUS_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "health_status", "word_index": 3, "bits": "0"},
            {"field": "mode_value", "word_index": 4, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "health_status", "mode"]
    },
    
    # Flight Control System Mode Change Request
    FCS_MODE_CHANGE_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode"]
    },
    
    # Flight Control System Mode Change Response
    FCS_MODE_CHANGE_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "old_mode_value", "word_index": -2, "bits": "0-3"},
            {"field": "new_mode_value", "word_index": -1, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "old_mode", "new_mode"]
    },
    
    # Flight Control System Control Input Request
    FCS_CONTROL_INPUT_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "control_surface_id", "word_index": 3, "bits": "all"},
            {"field": "control_value", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "control_surface_id", "control_value"]
    },
    
    # Flight Control System Control Input Response
    FCS_CONTROL_INPUT_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "control_surface_id", "word_index": 3, "bits": "all"},
            {"field": "status_code", "word_index": 4, "bits": "all"},
            {"field": "actual_value", "word_index": 5, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "control_surface_id", "status_code", "actual_value"]
    },
    
    # Flight Control System Orientation Data Request
    FCS_ORIENTATION_DATA_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id"]
    },
    
    # Flight Control System Orientation Data Response
    FCS_ORIENTATION_DATA_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "roll", "word_index": 3, "bits": "all"},
            {"field": "pitch", "word_index": 4, "bits": "all"},
            {"field": "yaw", "word_index": 5, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "roll", "pitch", "yaw"]
    },
    
    ##### FMS SPECIFIC MESSAGE TYPES #####
    
    # FMS Mode Change Request
    FMS_MODE_CHANGE_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode"]
    },
    
    # FMS Mode Change Response
    FMS_MODE_CHANGE_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "old_mode_value", "word_index": -2, "bits": "0-3"},
            {"field": "new_mode_value", "word_index": -1, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "old_mode", "new_mode"]
    },
    
    # FMS Attitude Update Request
    FMS_ATTITUDE_UPDATE_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "roll", "word_index": 3, "bits": "all"},
            {"field": "pitch", "word_index": 4, "bits": "all"},
            {"field": "yaw", "word_index": 5, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "roll", "pitch", "yaw"]
    },
    
    # FMS Attitude Update Response
    FMS_ATTITUDE_UPDATE_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "status_code", "word_index": 3, "bits": "all"},
            {"field": "roll", "word_index": 4, "bits": "all"},
            {"field": "pitch", "word_index": 5, "bits": "all"},
            {"field": "yaw", "word_index": 6, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "status_code", "roll", "pitch", "yaw"]
    },
    
    # FMS Navigation Update Request
    FMS_NAVIGATION_UPDATE_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "update_type", "word_index": 3, "bits": "all"},
            {"field": "parameter_count", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "update_type", "parameter_count"]
    },
    
    # FMS Navigation Update Response
    FMS_NAVIGATION_UPDATE_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "status_code", "word_index": 3, "bits": "all"},
            {"field": "update_type", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "status_code", "update_type"]
    },
    
    # FMS Maneuver Request
    FMS_MANEUVER_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "maneuver_type", "word_index": 3, "bits": "all"},
            {"field": "parameter_count", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "maneuver_type", "parameter_count"]
    },
    
    # FMS Maneuver Response
    FMS_MANEUVER_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "status_code", "word_index": 3, "bits": "all"},
            {"field": "maneuver_type", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "status_code", "maneuver_type"]
    },
    ###### WEATHER RADAR MESSAGES ######
    
    # Weather Radar Command 
    WEATHER_RADAR_COMMAND: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            # Extended metadata fields in following slots
            {"field": "mode_value", "word_index": -1, "bits": "0-2"}  # Last word, lowest 3 bits
        ],
        "data_word_count": None,  # Variable based on message
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id"]
    },
    
    # Weather Radar Mode Change Request
    WEATHER_RADAR_MODE_CHANGE_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode"]
    },
    
    # Weather Radar Mode Change Response
    WEATHER_RADAR_MODE_CHANGE_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"},
            {"field": "old_mode_value", "word_index": -2, "bits": "0-2"} # Second to last word
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "mode", "old_mode", "new_mode"]
    },
    
    # Weather Radar Status Request
    WEATHER_RADAR_STATUS_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id"]
    },
    
    # Weather Radar Status Response
    WEATHER_RADAR_STATUS_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "health_status", "word_index": -2, "bits": "0"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "health_status", "mode"]
    },
    
    # Weather Radar VIL Request
    WEATHER_RADAR_VIL_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "scan_type", "word_index": -1, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "scan_parameters"]
    },
    
    # Weather Radar VIL Response
    WEATHER_RADAR_VIL_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "data_count", "word_index": 3, "bits": "all"},
            {"field": "scan_type", "word_index": 4, "bits": "0-3"},
            {"field": "mode_value", "word_index": 5, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "data_count", "scan_type", "mode"]
    },
    
    # Weather Radar Precipitation Request
    WEATHER_RADAR_PRECIPITATION_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "scan_type", "word_index": -1, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "scan_parameters"]
    },
    
    # Weather Radar Precipitation Response
    WEATHER_RADAR_PRECIPITATION_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "data_count", "word_index": 3, "bits": "all"},
            {"field": "scan_type", "word_index": 4, "bits": "0-3"},
            {"field": "mode_value", "word_index": 5, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "data_count", "scan_type", "mode"]
    },
    
    # Weather Radar Data
    WEATHER_RADAR_DATA: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "data_type", "word_index": 3, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "data_type"]
    },
    
    ###### RADAR SYSTEM MESSAGES ######
    
    # Radar Command
    RADAR_COMMAND: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "radar_type", "word_index": 3, "bits": "0-3"},
            {"field": "mode_value", "word_index": -1, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "radar_type", "mode"]
    },
    
    # Radar Status Request
    RADAR_STATUS_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "radar_type", "word_index": 3, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "radar_type"]
    },
    
    # Radar Status Response
    RADAR_STATUS_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "radar_type", "word_index": 3, "bits": "0-3"},
            {"field": "health_status", "word_index": 4, "bits": "0"},
            {"field": "mode_value", "word_index": 5, "bits": "0-2"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "radar_type", "health_status", "mode"]
    },
    
    # Radar Data Request
    RADAR_DATA_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "radar_type", "word_index": 3, "bits": "0-3"},
            {"field": "data_type", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "radar_type", "data_type"]
    },
    
    # Radar Data Response
    RADAR_DATA_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "radar_type", "word_index": 3, "bits": "0-3"},
            {"field": "data_type", "word_index": 4, "bits": "all"},
            {"field": "data_count", "word_index": 5, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "radar_type", "data_type", "data_count"]
    },
    
    # Flight Management System Command
    FLIGHT_MANAGEMENT_SYSTEM_COMMAND: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            # Extended metadata fields in following slots
            {"field": "mode_value", "word_index": -1, "bits": "0-3"}  # Last word, lowest 4 bits
        ],
        "data_word_count": None,  # Variable based on message
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id"]
    },
    
    ###### FMS MESSAGES ######
    
    # FMS Command
    FMS_COMMAND: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "command_parameter", "word_index": -1, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "command_parameter"]
    },
    
    # FMS Data Request
    FMS_DATA_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "data_type", "word_index": 3, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "data_type"]
    },
    
    # FMS Data Response
    FMS_DATA_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "data_type", "word_index": 3, "bits": "all"},
            {"field": "data_count", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "data_type", "data_count"]
    },
    
    # FMS Status Request
    FMS_STATUS_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id"]
    },
    
    # FMS Status Response
    FMS_STATUS_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "health_status", "word_index": 3, "bits": "0"},
            {"field": "mode", "word_index": 4, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "health_status", "mode"]
    },
    
    ###### DISPLAY MESSAGES ######
    
    # Display Command
    DISPLAY_COMMAND: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "display_id", "word_index": 3, "bits": "all"},
            {"field": "command_parameter", "word_index": -1, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "display_id", "command_parameter"]
    },
    
    # Display Mode Request
    DISPLAY_MODE_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "display_id", "word_index": 3, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "display_id", "mode"]
    },
    
    # Display Mode Response
    DISPLAY_MODE_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "display_id", "word_index": 3, "bits": "all"},
            {"field": "old_mode", "word_index": 4, "bits": "0-3"},
            {"field": "new_mode", "word_index": 5, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "display_id", "old_mode", "new_mode"]
    },
    
    # Display Mode Change
    DISPLAY_MODE_CHANGE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "display_id", "word_index": 3, "bits": "all"},
            {"field": "mode_value", "word_index": -1, "bits": "0-7"}  # Expanded from 0-3 to 0-7 to support larger mode values
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "display_id", "mode"]
    },
    
    # Display Data Update
    DISPLAY_DATA_UPDATE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "display_id", "word_index": 3, "bits": "all"},
            {"field": "data_type", "word_index": 4, "bits": "all"},
            {"field": "data_count", "word_index": 5, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "display_id", "data_type", "data_count"]
    },
    
    # Display Data - For backwards compatibility with older implementations
    DISPLAY_DATA: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "display_id", "word_index": 3, "bits": "all"},
            {"field": "data_type", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "display_id", "data_type"]
    },
    
    # Display Status Request
    DISPLAY_STATUS_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "display_id", "word_index": 3, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "display_id"]
    },
    
    # Display Status Response
    DISPLAY_STATUS_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "display_id", "word_index": 3, "bits": "all"},
            {"field": "health_status", "word_index": 4, "bits": "0"},
            {"field": "mode", "word_index": 5, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "display_id", "health_status", "mode"]
    },
    
    ###### BIT MESSAGES ######
    
    # BIT Command
    BIT_COMMAND: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "system_id", "word_index": 3, "bits": "all"},
            {"field": "bit_type", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "system_id", "bit_type"]
    },
    
    # BIT Status Request
    BIT_STATUS_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "system_id", "word_index": 3, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "system_id"]
    },
    
    # BIT Status Response
    BIT_STATUS_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "system_id", "word_index": 3, "bits": "all"},
            {"field": "status_code", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "system_id", "status_code"]
    },
    
    # BIT Data Response
    BIT_DATA_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "system_id", "word_index": 3, "bits": "all"},
            {"field": "bit_type", "word_index": 4, "bits": "all"},
            {"field": "data_count", "word_index": 5, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "system_id", "bit_type", "data_count"]
    },
    
    ###### SYSTEM MESSAGES ######
    
    # System Command
    SYSTEM_COMMAND: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "system_id", "word_index": 3, "bits": "all"},
            {"field": "command_parameter", "word_index": -1, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "system_id", "command_parameter"]
    },
    
    # System Status Request
    SYSTEM_STATUS_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "system_id", "word_index": 3, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "system_id"]
    },
    
    # System Status Response
    SYSTEM_STATUS_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "system_id", "word_index": 3, "bits": "all"},
            {"field": "health_status", "word_index": 4, "bits": "0"},
            {"field": "mode", "word_index": 5, "bits": "0-3"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "system_id", "health_status", "mode"]
    },
    
    # System Data Request
    SYSTEM_DATA_REQUEST: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "system_id", "word_index": 3, "bits": "all"},
            {"field": "data_type", "word_index": 4, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "system_id", "data_type"]
    },
    
    # System Data Response
    SYSTEM_DATA_RESPONSE: {
        "data_structure": [
            {"field": "message_type_code", "word_index": 1, "bits": "all"},
            {"field": "command_type_code", "word_index": 2, "bits": "all"},
            {"field": "system_id", "word_index": 3, "bits": "all"},
            {"field": "data_type", "word_index": 4, "bits": "all"},
            {"field": "data_count", "word_index": 5, "bits": "all"}
        ],
        "data_word_count": None,
        "metadata_fields": ["message_type", "command_type", "command_name", "request_id", "system_id", "data_type", "data_count"]
    }
}


def get_schema_for_message_type(message_type: str) -> Optional[Dict[str, Any]]:
    """
    Get schema for a given message type.
    
    Args:
        message_type: The message type to get schema for
        
    Returns:
        Dict containing the schema or None if not found
    """
    return MESSAGE_SCHEMAS.get(message_type)


def get_field_position(message_type: str, field_name: str) -> Optional[Dict[str, Any]]:
    """
    Get position information for a specific field in a message type.
    
    Args:
        message_type: The message type to query
        field_name: The field name to find position for
        
    Returns:
        Dict containing field position info or None if not found
    """
    schema = get_schema_for_message_type(message_type)
    if not schema:
        return None
        
    for field_def in schema.get("data_structure", []):
        if field_def["field"] == field_name:
            return field_def
    
    return None


def extract_bit_range(bits_info: str) -> Tuple[int, int]:
    """
    Extract bit range from a string like "0-2".
    
    Args:
        bits_info: String specifying bit range, e.g. "0-2"
        
    Returns:
        Tuple of (start_bit, end_bit) inclusive
    """
    if bits_info == "all":
        return (0, 15)  # For a 16-bit word
        
    parts = bits_info.split("-")
    if len(parts) != 2:
        raise ValueError(f"Invalid bit range format: {bits_info}")
        
    start = int(parts[0])
    end = int(parts[1])
    
    if start < 0 or end > 15 or start > end:
        raise ValueError(f"Invalid bit range: {start}-{end}")
        
    return (start, end)


def extract_bits(value: int, start_bit: int, end_bit: int) -> int:
    """
    Extract specific bits from an integer value.
    
    Args:
        value: The integer value to extract bits from
        start_bit: The starting bit (0-based, inclusive)
        end_bit: The ending bit (0-based, inclusive)
        
    Returns:
        Integer with only the specified bits
    """
    # Create a mask with 1s in the bit positions we want to extract
    mask = 0
    for bit in range(start_bit, end_bit + 1):
        mask |= (1 << bit)
    
    # Apply the mask and shift right to normalize the result
    result = (value & mask) >> start_bit
    
    return result


def set_bits(value: int, new_bits: int, start_bit: int, end_bit: int) -> int:
    """
    Set specific bits in an integer value.
    
    Args:
        value: The integer value to modify
        new_bits: The new value to set in the specified bit range
        start_bit: The starting bit (0-based, inclusive)
        end_bit: The ending bit (0-based, inclusive)
        
    Returns:
        Integer with the specified bits set to the new value
    """
    # Create a mask with 0s in the bit positions we want to modify
    mask = ~0
    for bit in range(start_bit, end_bit + 1):
        mask &= ~(1 << bit)
    
    # Clear the target bits in the original value
    cleared_value = value & mask
    
    # Shift the new bits into the correct position
    shifted_new_bits = new_bits << start_bit
    
    # Ensure the new bits don't exceed the specified range
    bit_range_size = end_bit - start_bit + 1
    max_new_value = (1 << bit_range_size) - 1
    if new_bits > max_new_value:
        raise ValueError(f"New bits value {new_bits} exceeds the capacity of the bit range {start_bit}-{end_bit}")
    
    # Combine the cleared value with the new bits
    result = cleared_value | shifted_new_bits
    
    return result


def apply_schema_to_data_words(message_type: str, data_words: List[str], field_values: Dict[str, Any]) -> List[str]:
    """
    Apply schema-defined field values to data words.
    
    Args:
        message_type: The message type to use schema for
        data_words: The list of data words to modify
        field_values: Dictionary of field names and their values to set
        
    Returns:
        Modified list of data words
    """
    schema = get_schema_for_message_type(message_type)
    if not schema:
        return data_words
    
    result = data_words.copy()
    
    for field_name, field_value in field_values.items():
        field_def = get_field_position(message_type, field_name)
        if not field_def:
            continue
        
        word_index = field_def["word_index"]
        # Handle negative indices (counting from end)
        actual_index = word_index if word_index >= 0 else len(result) + word_index
        
        if 0 <= actual_index < len(result):
            # Get bit range information
            bits_info = field_def["bits"]
            start_bit, end_bit = extract_bit_range(bits_info)
            
            # Convert the data word from binary string to integer
            word_value = int(result[actual_index], 2)
            
            # Set the bits for this field
            new_word_value = set_bits(word_value, field_value, start_bit, end_bit)
            
            # Convert back to binary string
            result[actual_index] = format(new_word_value, '016b')
    
    return result


def extract_fields_from_data_words(message_type: str, data_words: List[str]) -> Dict[str, Any]:
    """
    Extract fields from data words according to schema.
    
    Args:
        message_type: The message type to use schema for
        data_words: The list of data words to extract fields from
        
    Returns:
        Dictionary of extracted field values
    """
    schema = get_schema_for_message_type(message_type)
    if not schema:
        return {}
    
    result = {}
    
    for field_def in schema.get("data_structure", []):
        field_name = field_def["field"]
        word_index = field_def["word_index"]
        
        # Handle negative indices (counting from end)
        actual_index = word_index if word_index >= 0 else len(data_words) + word_index
        
        if 0 <= actual_index < len(data_words):
            # Get bit range information
            bits_info = field_def["bits"]
            start_bit, end_bit = extract_bit_range(bits_info)
            
            # Convert the data word from binary string to integer
            word_value = int(data_words[actual_index], 2)
            
            # Extract the bits for this field
            field_value = extract_bits(word_value, start_bit, end_bit)
            
            # Special handling for mode_value field to convert to mode name
            if field_name == "mode_value" and field_value in MODE_NAME_MAP:
                result["mode"] = MODE_NAME_MAP[field_value]
            
            # Store the raw field value
            result[field_name] = field_value
    
    return result

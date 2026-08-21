"""
Display-specific messaging package.

This package contains modules for handling display-specific messaging,
including message types, address utilities, and message definitions.
"""

# Import key modules for easier access
from .display_message_types import (
    # Message type constants
    DISPLAY_VIL_DATA,
    DISPLAY_PRECIPITATION_DATA,
    DISPLAY_ECHO_TOP_DATA,
    DISPLAY_STORM_CELL_DATA,
    DISPLAY_TERRAIN_DATA,
    DISPLAY_IMAGERY_DATA,
    DISPLAY_TRACK_DATA,
    DISPLAY_SECTOR_SCAN_DATA,
    
    # Command type constants
    DISPLAY_COMMAND_TYPE_SHOW,
    DISPLAY_COMMAND_TYPE_MODE,
    DISPLAY_COMMAND_TYPE_DATA,
    DISPLAY_COMMAND_TYPE_STATUS,
    DISPLAY_COMMAND_TYPE_MODE_CHANGE,
    DISPLAY_COMMAND_TYPE_MODE_CHANGE_COMPLETE,
    DISPLAY_COMMAND_TYPE_VIL_DATA,
    DISPLAY_COMMAND_TYPE_PRECIPITATION_DATA,
    
    # Helper functions
    get_message_type,
    is_message_type,
    is_vil_message,
    is_precipitation_message,
    is_echo_top_message,
    is_storm_cell_message,
    is_mode_change_message,
    translate_message_type,
    get_command_type,
    is_command_type
)

from .display_address_utils import (
    # System constants
    DISPLAY_SYSTEM_ID,
    DISPLAY_RT_ADDRESS,
    RADAR_SYSTEM_ID,
    RADAR_RT_ADDRESS,
    
    # Display subaddress constants
    PFD_SUBADDRESS,
    MFD_SUBADDRESS,
    EICAS_SUBADDRESS,
    RADAR_DISPLAY_SUBADDRESS,
    TSD_SUBADDRESS,
    SMS_SUBADDRESS,
    
    
    # Radar subaddress constants
    WEATHER_RADAR_SUBADDRESS,
    TFR_RADAR_SUBADDRESS,
    SAR_RADAR_SUBADDRESS,
    TARGETING_RADAR_SUBADDRESS,
    AEWC_RADAR_SUBADDRESS,
    
    # Helper functions
    get_display_rt_address,
    get_radar_rt_address,
    get_display_subaddress,
    get_radar_subaddress,
    get_display_id_by_subaddress,
    get_radar_type_by_subaddress,
    is_display_rt_address,
    is_radar_rt_address,
    is_display_subaddress,
    is_radar_subaddress,
    get_subaddress_info
)

# Import message classes
from .message_definitions.display_message_base import DisplayBaseMessage
from .message_definitions.display_vil_data import DisplayVILData
from .message_definitions.display_precipitation_data import DisplayPrecipitationData
from .message_definitions.display_mode_change import DisplayModeChange

# Import helper modules
from .display_1553b_helpers import (
    Display1553BHelpers,
    get_display_type,
    get_display_mode,
    parse_command_data
)

from .display_command_map import (
    DISPLAY_TYPES,
    MESSAGE_TYPES,
    MESSAGE_TYPES_EXTENDED,
    SHOW_REQUEST_MAP,
    MODE_REQUEST_MAP,
    DATA_REQUEST_MAP,
    STATUS_REQUEST_MAP,
    get_display_command_word
)

# Define package exports
__all__ = [
    # Message type constants and functions
    'DISPLAY_VIL_DATA',
    'DISPLAY_PRECIPITATION_DATA',
    'DISPLAY_ECHO_TOP_DATA',
    'DISPLAY_STORM_CELL_DATA',
    'DISPLAY_TERRAIN_DATA',
    'DISPLAY_IMAGERY_DATA',
    'DISPLAY_TRACK_DATA',
    'DISPLAY_SECTOR_SCAN_DATA',
    'DISPLAY_COMMAND_TYPE_SHOW',
    'DISPLAY_COMMAND_TYPE_MODE',
    'DISPLAY_COMMAND_TYPE_DATA',
    'DISPLAY_COMMAND_TYPE_STATUS',
    'DISPLAY_COMMAND_TYPE_MODE_CHANGE',
    'DISPLAY_COMMAND_TYPE_MODE_CHANGE_COMPLETE',
    'DISPLAY_COMMAND_TYPE_VIL_DATA',
    'DISPLAY_COMMAND_TYPE_PRECIPITATION_DATA',
    'get_message_type',
    'is_message_type',
    'is_vil_message',
    'is_precipitation_message',
    'is_echo_top_message',
    'is_storm_cell_message',
    'is_mode_change_message',
    'translate_message_type',
    'get_command_type',
    'is_command_type',
    
    # Address constants and functions
    'DISPLAY_SYSTEM_ID',
    'DISPLAY_RT_ADDRESS',
    'RADAR_SYSTEM_ID',
    'RADAR_RT_ADDRESS',
    'PFD_SUBADDRESS',
    'MFD_SUBADDRESS',
    'EICAS_SUBADDRESS',
    'RADAR_DISPLAY_SUBADDRESS',
    'TSD_SUBADDRESS',
    'SMS_SUBADDRESS',
    'WEATHER_RADAR_SUBADDRESS',
    'TFR_RADAR_SUBADDRESS',
    'SAR_RADAR_SUBADDRESS',
    'TARGETING_RADAR_SUBADDRESS',
    'AEWC_RADAR_SUBADDRESS',
    'get_display_rt_address',
    'get_radar_rt_address',
    'get_display_subaddress',
    'get_radar_subaddress',
    'get_display_id_by_subaddress',
    'get_radar_type_by_subaddress',
    'is_display_rt_address',
    'is_radar_rt_address',
    'is_display_subaddress',
    'is_radar_subaddress',
    'get_subaddress_info',
    
    # Message classes
    'DisplayBaseMessage',
    'DisplayVILData',
    'DisplayPrecipitationData',
    'DisplayModeChange',
    
    # Helper classes and functions
    'Display1553BHelpers',
    'get_display_type',
    'get_display_mode',
    'parse_command_data',
    'DISPLAY_TYPES',
    'MESSAGE_TYPES',
    'MESSAGE_TYPES_EXTENDED',
    'SHOW_REQUEST_MAP',
    'MODE_REQUEST_MAP',
    'DATA_REQUEST_MAP',
    'STATUS_REQUEST_MAP',
    'get_display_command_word'
]

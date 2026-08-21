"""
Message Definitions Module

Provides a single source of truth for all message-related definitions in the FMOFP system.
This includes system addresses, message types, command types, and command names.
All other address books, maps, and registries should reference this module for consistency.
"""

import uuid
import enum
from typing import Dict, Any, List, Optional

# System Definitions
class SystemDefinitions:
    # RT Addresses
    class RTAddresses(enum.IntEnum):
        AVIONICS = 1
        COMMUNICATIONS = 2
        ENGINE_MANAGEMENT = 3
        ENVIRONMENTAL_CONTROL = 4
        FLIGHT_CONTROL = 5
        MISSION_PLANNING = 6
        NAVIGATION = 7
        POWER_MANAGEMENT = 8
        RADAR = 9
        SENSOR_MANAGEMENT = 10
        DISPLAYS = 11
        FLIGHT_MANAGEMENT = 17
    
    # System UUIDs
    SYSTEM_UUIDS = {
        RTAddresses.AVIONICS: "11111111-1111-1111-1111-111111111111",
        RTAddresses.COMMUNICATIONS: "22222222-2222-2222-2222-222222222222",
        RTAddresses.ENGINE_MANAGEMENT: "33333333-3333-3333-3333-333333333333",
        RTAddresses.ENVIRONMENTAL_CONTROL: "44444444-4444-4444-4444-444444444444",
        RTAddresses.FLIGHT_CONTROL: "55555555-5555-5555-5555-555555555555",
        RTAddresses.MISSION_PLANNING: "66666666-6666-6666-6666-666666666666",
        RTAddresses.NAVIGATION: "77777777-7777-7777-7777-777777777777",
        RTAddresses.POWER_MANAGEMENT: "88888888-8888-8888-8888-888888888888",
        RTAddresses.RADAR: "99999999-9999-9999-9999-999999999999",
        RTAddresses.SENSOR_MANAGEMENT: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        RTAddresses.DISPLAYS: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        RTAddresses.FLIGHT_MANAGEMENT: "cccccccc-cccc-cccc-cccc-cccccccccccc"
    }
    
    # RT Address to System Name Mapping
    RT_ADDRESS_TO_NAME = {
        RTAddresses.AVIONICS: "avionics",
        RTAddresses.COMMUNICATIONS: "comms",
        RTAddresses.ENGINE_MANAGEMENT: "engine_management",
        RTAddresses.ENVIRONMENTAL_CONTROL: "environmental_control_system",
        RTAddresses.FLIGHT_CONTROL: "flight_control_system",
        RTAddresses.MISSION_PLANNING: "mission_planning",
        RTAddresses.NAVIGATION: "nav",
        RTAddresses.POWER_MANAGEMENT: "power_management",
        RTAddresses.RADAR: "radar",
        RTAddresses.SENSOR_MANAGEMENT: "sensor_management",
        RTAddresses.DISPLAYS: "displays",
        RTAddresses.FLIGHT_MANAGEMENT: "flight_management_system"
    }
    
    # Subaddress Definitions
    # Radar Subaddresses
    class RadarSubaddresses(enum.IntEnum):
        WEATHER_RADAR = 1
        TFR_RADAR = 2
        SAR_RADAR = 3
        TARGETING_RADAR = 4
        AEWC_RADAR = 5
    
    # Display Subaddresses
    class DisplaySubaddresses(enum.IntEnum):
        SHOW = 1
        MODE = 2
        DATA = 3
        STATUS = 4
        PFD = 11
        MFD = 12
        EICAS = 13
        RADAR_DISPLAY = 14
        TSD = 15
        SMS = 16
    
    # FMS Subaddresses
    class FMSSubaddresses(enum.IntEnum):
        FMS = 1
    
    # Mode Code Subaddress
    MODE_CODE_SUBADDRESS = 31

# Message Type Definitions
class MessageDefinitions:
    # Message Types
    class MessageTypes(enum.Enum):
        # Weather Radar
        WEATHER_RADAR_MODE_CHANGE_REQUEST = "weather_radarModeChangeRequest"
        WEATHER_RADAR_MODE_CHANGE_RESPONSE = "weather_radarModeChangeResponse"
        WEATHER_RADAR_PRECIPITATION_REQUEST = "weather_radarPrecipitationRequest"
        WEATHER_RADAR_PRECIPITATION_RESPONSE = "weather_radarPrecipitationResponse"
        WEATHER_RADAR_VIL_REQUEST = "weather_radarVILRequest"
        WEATHER_RADAR_VIL_RESPONSE = "weather_radarVILResponse"
        WEATHER_RADAR_ECHO_TOP_REQUEST = "weather_radarEchoTopRequest"
        WEATHER_RADAR_ECHO_TOP_RESPONSE = "weather_radarEchoTopResponse"
        
        # Display
        DISPLAY_SHOW_REQUEST = "display_show_request"
        DISPLAY_SHOW_RESPONSE = "display_show_response"
        DISPLAY_MODE_REQUEST = "display_mode_request"
        DISPLAY_MODE_RESPONSE = "display_mode_response"
        DISPLAY_DATA_REQUEST = "display_data_request"
        DISPLAY_DATA_RESPONSE = "display_data_response"
    
    # Command Types
    class CommandTypes(enum.Enum):
        MODE_CHANGE = "mode_change"
        DATA_REQUEST = "data_request"
        DATA_RESPONSE = "data_response"
        STATUS_REQUEST = "status_request"
        STATUS_RESPONSE = "status_response"
    
    # Command Names (from command_registry.xml)
    class CommandNames(enum.Enum):
        # Weather Radar
        WEATHER_RADAR_MODE_CHANGE = "WEATHER_RADAR_MODE_CHANGE"
        DISPLAY_PRECIPITATION_DATA = "DISPLAY_PRECIPITATION_DATA"
        DISPLAY_VIL_DATA = "DISPLAY_VIL_DATA"
        DISPLAY_ECHO_TOP_DATA = "DISPLAY_ECHO_TOP_DATA"
        WEATHER_RADAR_PRECIPITATION_DATA = "WEATHER_RADAR_PRECIPITATION_DATA"
        WEATHER_RADAR_VIL_DATA = "WEATHER_RADAR_VIL_DATA"
        WEATHER_RADAR_ECHO_TOP_DATA = "WEATHER_RADAR_ECHO_TOP_DATA"
    
    # Command Registry Mapping
    COMMAND_REGISTRY = {
        CommandNames.WEATHER_RADAR_MODE_CHANGE: "0x4845",
        CommandNames.DISPLAY_PRECIPITATION_DATA: "0x200F",
        CommandNames.DISPLAY_VIL_DATA: "0x200D",
        CommandNames.DISPLAY_ECHO_TOP_DATA: "0x9007",
        CommandNames.WEATHER_RADAR_PRECIPITATION_DATA: "0x2010", 
        CommandNames.WEATHER_RADAR_VIL_DATA: "0x200E",
        CommandNames.WEATHER_RADAR_ECHO_TOP_DATA: "0x9008"
    }
    
    # Message Type to Command Name Mapping
    MESSAGE_TYPE_TO_COMMAND_NAME = {
        MessageTypes.WEATHER_RADAR_MODE_CHANGE_REQUEST: CommandNames.WEATHER_RADAR_MODE_CHANGE,
        MessageTypes.WEATHER_RADAR_PRECIPITATION_REQUEST: CommandNames.DISPLAY_PRECIPITATION_DATA,
        MessageTypes.WEATHER_RADAR_VIL_REQUEST: CommandNames.DISPLAY_VIL_DATA,
        MessageTypes.WEATHER_RADAR_ECHO_TOP_REQUEST: CommandNames.DISPLAY_ECHO_TOP_DATA,
        MessageTypes.WEATHER_RADAR_PRECIPITATION_RESPONSE: CommandNames.WEATHER_RADAR_PRECIPITATION_DATA,
        MessageTypes.WEATHER_RADAR_VIL_RESPONSE: CommandNames.WEATHER_RADAR_VIL_DATA,
        MessageTypes.WEATHER_RADAR_ECHO_TOP_RESPONSE: CommandNames.WEATHER_RADAR_ECHO_TOP_DATA
    }

# Standard Message Headers
class MessageHeaders(enum.Enum):
    DATA_REQUEST = "data_request"
    DATA_RESPONSE = "data_response"
    MODE_CHANGE_REQUEST = "mode_change_request"
    MODE_CHANGE_RESPONSE = "mode_change_response"
    STATUS_REQUEST = "status_request"
    STATUS_RESPONSE = "status_response"
    EVENT = "event"
    ALERT = "alert"
    ERROR = "error"
    HEARTBEAT = "heartbeat"

# Message Priority Levels
class MessagePriority(enum.Enum):
    EMERGENCY = "emergency"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"

# Message Status Values
class MessageStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

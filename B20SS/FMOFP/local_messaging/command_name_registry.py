from FMOFP.Utils.logger.sys_logger import get_logger
logger = get_logger()

# Command name registry for unique message identification
# Values aligned with command_registry.xml which is the authoritative source for hex values
COMMAND_NAMES = {
    # Weather Radar Commands
    'WEATHER_RADAR_VIL_DATA': {
        'message_type': 'weather_radarVILResponse',
        'command_hex': '0x200E',  # Updated to match command_registry.xml (was 0x200D)
        'description': 'VIL data from weather radar'
    },
    'WEATHER_RADAR_PRECIPITATION_DATA': {  # Renamed from WEATHER_RADAR_PRECIP_DATA
        'message_type': 'weather_radarPrecipitationResponse',
        'command_hex': '0x2010',  # Updated to match command_registry.xml (was 0x200F)
        'description': 'Precipitation data from weather radar'
    },
    'WEATHER_RADAR_MODE_CHANGE': {
        'message_type': 'weather_radarModeChangeRequest',
        'command_hex': '0x4845',
        'description': 'Weather radar mode change command'
    },
    'WEATHER_RADAR_MODE_CHANGE_COMPLETE': {  # Added from command_registry.xml
        'message_type': 'weather_radarModeChangeResponse',
        'command_hex': '0x4846',
        'description': 'Weather radar mode change completion'
    },
    'WEATHER_RADAR_COMMAND': {
        'message_type': 'weather_radarCommand',
        'command_hex': '0x4847',
        'description': 'General weather radar command'
    },
    'PRECIPITATION_DATA_COMMAND': {
        'message_type': 'weather_radarPrecipitationResponse',
        'command_hex': '0x2011',
        'description': 'Precipitation data command'
    },
    'VIL_DATA_COMMAND': {
        'message_type': 'weather_radarVILResponse',
        'command_hex': '0x200F',
        'description': 'VIL data command'
    },
    'DISPLAY_ECHO_TOP_DATA': {
        'message_type': 'weather_radarEchoTopRequest',
        'command_hex': '0x9007',
        'description': 'Request for echo top data to display'
    },
    'WEATHER_RADAR_ECHO_TOP_DATA': {
        'message_type': 'weather_radarEchoTopResponse',
        'command_hex': '0x9008',
        'description': 'Echo top data from weather radar'
    },
    'WEATHER_RADAR_STORM_CELL_DATA': {
        'message_type': 'weather_radarStormCellRequest',
        'command_hex': '0x9009',
        'description': 'Storm cell data request'
    },
    'WEATHER_RADAR_STORM_CELL_DATA_RESPONSE': {
        'message_type': 'weather_radarStormCellResponse',
        'command_hex': '0x900A',
        'description': 'Storm cell data response'
    },
    
    # Display Data Commands
    'DISPLAY_VIL_DATA': {  # Added from command_registry.xml
        'message_type': 'weather_radarVILRequest',
        'command_hex': '0x200D',
        'description': 'Request for VIL data to display'
    },
    'DISPLAY_PRECIPITATION_DATA': {  # Added from command_registry.xml
        'message_type': 'weather_radarPrecipitationRequest',
        'command_hex': '0x200F',
        'description': 'Request for precipitation data to display'
    },
    'DISPLAY_DATA_REQUEST': {  # Added from command_registry.xml
        'message_type': 'display_data_request',
        'command_hex': '0x7005',
        'description': 'General display data request'
    },
    
    # TFR Radar Commands
    'TFR_RADAR_MODE_CHANGE': {
        'message_type': 'tfr_radarModeChangeRequest',
        'command_hex': '0x3003',
        'description': 'TFR radar mode change command'
    },
    'TFR_RADAR_MODE_CHANGE_COMPLETE': {
        'message_type': 'tfr_radarModeChangeResponse',
        'command_hex': '0x3004',
        'description': 'TFR radar mode change completion'
    },
    # SAR Radar Commands
    'SAR_RADAR_MODE_CHANGE': {
        'message_type': 'sar_radarModeChangeRequest',
        'command_hex': '0x4003',
        'description': 'SAR radar mode change command'
    },
    'SAR_RADAR_MODE_CHANGE_COMPLETE': {
        'message_type': 'sar_radarModeChangeResponse',
        'command_hex': '0x4004',
        'description': 'SAR radar mode change completion'
    },
    # Targeting Radar Commands
    'TARGETING_RADAR_MODE_CHANGE': {
        'message_type': 'targeting_radarModeChangeRequest',
        'command_hex': '0x5003',
        'description': 'Targeting radar mode change command'
    },
    'TARGETING_RADAR_MODE_CHANGE_COMPLETE': {
        'message_type': 'targeting_radarModeChangeResponse',
        'command_hex': '0x5004',
        'description': 'Targeting radar mode change completion'
    },
    # AEWC Radar Commands
    'AEWC_RADAR_MODE_CHANGE': {
        'message_type': 'aewc_radarModeChangeRequest',
        'command_hex': '0x6003',
        'description': 'AEWC radar mode change command'
    },
    'AEWC_RADAR_MODE_CHANGE_COMPLETE': {
        'message_type': 'aewc_radarModeChangeResponse',
        'command_hex': '0x6004',
        'description': 'AEWC radar mode change completion'
    },
    
    # Display Mode Commands
    'DISPLAY_MODE_CHANGE': {  # Renamed from DISPLAY_MODE_REQUEST to match command_registry.xml
        'message_type': 'display_mode_request',
        'command_hex': '0xB002',  # Updated to match command_registry.xml (was 0x7003)
        'description': 'Display mode change request'
    },
    'DISPLAY_MODE_RESPONSE': {
        'message_type': 'display_mode_response',
        'command_hex': '0x7004',
        'description': 'Display mode change response'
    },
    'DISPLAY_SHOW': {  # Added from command_registry.xml
        'message_type': 'display_show_request',
        'command_hex': '0x7001',
        'description': 'Request to show a display'
    },
    
    # FMS Commands
    'FMS_MODE_CHANGE': {
        'message_type': 'fms_modeChangeRequest',
        'command_hex': '0x7101',
        'description': 'FMS mode change command'
    },
    'FMS_MODE_CHANGE_COMPLETE': {
        'message_type': 'fms_modeChangeResponse',
        'command_hex': '0x7102',
        'description': 'FMS mode change completion'
    },
    'FMS_STATUS_REQUEST': {
        'message_type': 'fms_statusRequest',
        'command_hex': '0x7103',
        'description': 'FMS status request'
    },
    'FMS_STATUS_RESPONSE': {
        'message_type': 'fms_statusResponse',
        'command_hex': '0x7104',
        'description': 'FMS status response'
    },
    'FMS_ATTITUDE_UPDATE': {
        'message_type': 'fms_attitudeUpdateRequest',
        'command_hex': '0x7105',
        'description': 'FMS attitude update request'
    },
    'FMS_ATTITUDE_UPDATE_RESPONSE': {
        'message_type': 'fms_attitudeUpdateResponse',
        'command_hex': '0x7106',
        'description': 'FMS attitude update response'
    },
    'FMS_NAVIGATION_UPDATE': {
        'message_type': 'fms_navigationUpdateRequest',
        'command_hex': '0x7107',
        'description': 'FMS navigation update request'
    },
    'FMS_NAVIGATION_UPDATE_RESPONSE': {
        'message_type': 'fms_navigationUpdateResponse',
        'command_hex': '0x7108',
        'description': 'FMS navigation update response'
    },
    'FMS_MANEUVER_REQUEST': {
        'message_type': 'fms_maneuverRequest',
        'command_hex': '0x7109',
        'description': 'FMS maneuver request'
    },
    'FMS_MANEUVER_RESPONSE': {
        'message_type': 'fms_maneuverResponse',
        'command_hex': '0x710A',
        'description': 'FMS maneuver response'
    }
}

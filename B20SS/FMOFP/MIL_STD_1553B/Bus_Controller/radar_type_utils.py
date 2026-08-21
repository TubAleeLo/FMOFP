"""
Radar Type Utilities

Helper functions for radar type determination in the Bus Controller.
This module encapsulates radar-specific logic to maintain separation of concerns.
"""

import traceback
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

def determine_radar_type(frame, subaddress_int):
    """
    Determine the radar type from the frame, message_type, or subaddress.
    
    Args:
        frame: The message frame which may contain metadata with radar_type information
        subaddress_int: The default subaddress to use if radar_type isn't in frame
        
    Returns:
        Tuple of (system_type, radar_type)
    """
    try:
        logger.info(f"[BC] Determining radar type for frame: {frame.get('message_type') if isinstance(frame, dict) else 'Unknown'}")
        
        # First check if we have explicit radar_type in metadata
        radar_type_from_metadata = None
        if isinstance(frame, dict) and 'metadata' in frame and isinstance(frame['metadata'], dict):
            radar_type_from_metadata = frame['metadata'].get('radar_type')
            if radar_type_from_metadata:
                logger.info(f"[BC] Found explicit radar_type in metadata: {radar_type_from_metadata}")
                return radar_type_from_metadata, radar_type_from_metadata
        
        # Check if we can determine radar type from message_type field
        message_type = None
        if isinstance(frame, dict):
            # Try to get message_type from top level
            message_type = frame.get('message_type')
            
            # If not found at top level, check metadata
            if not message_type and 'metadata' in frame and isinstance(frame['metadata'], dict):
                message_type = frame['metadata'].get('message_type')
                
        if message_type and isinstance(message_type, str):
            logger.info(f"[BC] Examining message_type for radar type: {message_type}")
            
            # Define known radar type prefixes
            radar_prefixes = {
                'tfr_': 'tfr_radar',
                'sar_': 'sar_radar', 
                'weather_': 'weather_radar',
                'targeting_': 'targeting_radar',
                'aewc_': 'aewc_radar'
            }
            
            # Check if message_type starts with any known radar prefix
            for prefix, radar_type in radar_prefixes.items():
                if message_type.lower().startswith(prefix):
                    logger.info(f"[BC] Determined radar_type from message_type prefix: {radar_type}")
                    return radar_type, radar_type
                    
            # Alternative check: if message contains radar type anywhere
            for prefix, radar_type in radar_prefixes.items():
                prefix_without_underscore = prefix.replace('_', '')  # Handle cases without underscore
                if prefix_without_underscore in message_type.lower():
                    logger.info(f"[BC] Determined radar_type from message_type content: {radar_type}")
                    return radar_type, radar_type
                    
            logger.info(f"[BC] Could not determine radar_type from message_type: {message_type}")
            
        # Next check if frame has sub_address or metadata.subaddress field
        frame_subaddress = None
        if isinstance(frame, dict):
            if 'sub_address' in frame:
                frame_subaddress = frame['sub_address']
                logger.info(f"[BC] Using subaddress from frame: {frame_subaddress}")
            elif 'metadata' in frame and isinstance(frame['metadata'], dict) and 'subaddress' in frame['metadata']:
                frame_subaddress = frame['metadata']['subaddress']
                logger.info(f"[BC] Using subaddress from metadata: {frame_subaddress}")
        
        # Use the subaddress to determine the radar type
        radar_map = {
            1: 'weather_radar',
            2: 'tfr_radar',
            3: 'sar_radar',
            4: 'targeting_radar',
            5: 'aewc_radar'
        }
        
        # If we have a subaddress from the frame, use that rather than subaddress_int
        actual_subaddress = frame_subaddress if frame_subaddress is not None else subaddress_int
        logger.info(f"[BC] Using subaddress {actual_subaddress} to determine radar type")
        
        system_type = radar_map.get(actual_subaddress)
        if not system_type:
            logger.error(f"[BC] Unknown radar subaddress: {actual_subaddress}")
            return None, None
            
        return system_type, system_type
        
    except Exception as e:
        logger.error(f"[BC] Error determining radar type: {e}")
        logger.error(traceback.format_exc())
        return None, None

def get_radar_command_name(radar_type, command_type, is_completion=False):
    """
    Get the standardized command name for a radar command based on radar type.
    
    Args:
        radar_type: The type of radar (weather_radar, tfr_radar, etc.)
        command_type: The type of command (mode_change, precipitation_data, etc.)
        is_completion: Whether this is a completion command
        
    Returns:
        str: The standardized command name following military naming conventions
    """
    # Normalize radar_type if needed
    if radar_type is None:
        # No default, must be provided
        return None
        
    radar_type = radar_type.lower()
    command_type = command_type.lower() if command_type else "command"
    
    # Map radar types to their prefix in command names
    radar_prefix_map = {
        'weather_radar': 'WEATHER_RADAR',
        'tfr_radar': 'TFR_RADAR',
        'sar_radar': 'SAR_RADAR',
        'targeting_radar': 'TARGETING_RADAR',
        'aewc_radar': 'AEWC_RADAR'
    }
    
    # Get radar prefix, with no default
    radar_prefix = radar_prefix_map.get(radar_type)
    if not radar_prefix:
        # No match found in known radar types
        return None
    
    # Map command types to their suffix in command names
    command_suffix_map = {
        'mode_change': 'MODE_CHANGE',
        'precipitation_data': 'PRECIPITATION_DATA',
        'vil_data': 'VIL_DATA',
        'status': 'STATUS',
        'search': 'SEARCH',
        'track': 'TRACK'
    }
    
    # Get command suffix with generic fallback
    command_suffix = command_suffix_map.get(command_type, command_type.upper())
    
    # Build the command name
    command_name = f"{radar_prefix}_{command_suffix}"
    
    # Add completion suffix if needed
    if is_completion and not command_name.endswith('_COMPLETION'):
        command_name += '_COMPLETION'
        
    return command_name

# Explicitly export the functions
__all__ = ['determine_radar_type', 'get_radar_command_name']

"""
Radar Mode Converter Utility

This module provides utilities for converting between different radar mode representations,
handling multiple radar mode formats including enum instances, strings, and numeric values.
It works with all radar types (weather, TFR, SAR, targeting, AEWC) and ensures consistent 
mode handling across system and display boundaries.
"""

import logging
from enum import Enum
from typing import Optional, Tuple, Union, Dict, Any, Type

# Import the RadarDisplayMode enum
from FMOFP.local_messaging.radar_display_modes import RadarDisplayMode

# Try to import display-specific enums if available
try:
    from FMOFP.Interfaces.userInterface.displays.radar.display_radar_enums import (
        BaseDisplayRadarMode,
        DisplayWeatherRadarMode,
        DisplayTFRRadarMode,
        DisplaySARRadarMode,
        DisplayTargetingRadarMode,
        DisplayAEWCRadarMode,
        get_display_mode_class
    )
    HAS_DISPLAY_ENUMS = True
except ImportError:
    HAS_DISPLAY_ENUMS = False

# Configure logging
logger = logging.getLogger(__name__)

def get_radar_display_mode(
    mode: Union[str, RadarDisplayMode, int, dict, Any, None], 
    radar_type: Optional[str] = None
) -> Tuple[Optional[RadarDisplayMode], Optional[str]]:
    """
    Convert various mode representations to a RadarDisplayMode enum instance and its string name.
    
    This function handles multiple input types:
    - RadarDisplayMode enum instances
    - Display radar enum instances (from display subsystem)
    - String mode names (e.g., "NORMAL", "STANDBY")
    - Integer mode values
    - Dictionary with 'mode' key
    - Objects with mode attribute
    - None values
    
    Args:
        mode: The mode to convert, which can be a string name, RadarDisplayMode enum,
              display enum, integer value, dictionary, object, or None
        radar_type: Optional string identifying the specific radar type
              (weather_radar, tfr_radar, sar_radar, targeting_radar, aewc_radar)
              
    Returns:
        Tuple containing:
        - RadarDisplayMode enum instance (or None if conversion failed)
        - String mode name (or None if conversion failed)
    """
    # Initialize return values
    display_mode = None
    mode_name = None
    
    # Return early for None values
    if mode is None:
        logger.warning("Received None mode value, cannot convert")
        return None, None
    
    try:
        # Try to determine radar_type if not provided
        if radar_type is None:
            # Look for radar type in metadata or attributes
            if isinstance(mode, dict):
                for key in ['radar_type', 'system_type', 'source_system', 'system_name']:
                    if key in mode and mode[key]:
                        radar_type = mode[key]
                        break
            # Check object attributes                
            elif hasattr(mode, 'radar_type'):
                radar_type = getattr(mode, 'radar_type')
            elif hasattr(mode, 'system_type'):
                radar_type = getattr(mode, 'system_type')
            elif hasattr(mode, 'system_name'):
                radar_type = getattr(mode, 'system_name')
        
        # Select the appropriate mode map based on radar type
        try:
            # Default to the global mode map
            mode_map = RadarDisplayMode.mode_map
            
            if radar_type:
                # Instead of dynamic attribute access, use explicit checks for each radar type
                if 'weather_radar' in radar_type:
                    # Check if the attribute exists and is a dictionary
                    if hasattr(RadarDisplayMode, 'weather_radar_modes'):
                        if isinstance(RadarDisplayMode.weather_radar_modes, dict):
                            mode_map = RadarDisplayMode.weather_radar_modes
                            logger.debug(f"Using weather_radar_modes map")
                        else:
                            logger.warning(f"weather_radar_modes is not a dictionary, using global mode_map")
                
                elif 'tfr_radar' in radar_type:
                    if hasattr(RadarDisplayMode, 'tfr_radar_modes'):
                        if isinstance(RadarDisplayMode.tfr_radar_modes, dict):
                            mode_map = RadarDisplayMode.tfr_radar_modes
                            logger.debug(f"Using tfr_radar_modes map")
                        else:
                            logger.warning(f"tfr_radar_modes is not a dictionary, using global mode_map")
                
                elif 'sar_radar' in radar_type:
                    if hasattr(RadarDisplayMode, 'sar_radar_modes'):
                        if isinstance(RadarDisplayMode.sar_radar_modes, dict):
                            mode_map = RadarDisplayMode.sar_radar_modes
                            logger.debug(f"Using sar_radar_modes map")
                        else:
                            logger.warning(f"sar_radar_modes is not a dictionary, using global mode_map")
                
                elif 'targeting_radar' in radar_type:
                    if hasattr(RadarDisplayMode, 'targeting_radar_modes'):
                        if isinstance(RadarDisplayMode.targeting_radar_modes, dict):
                            mode_map = RadarDisplayMode.targeting_radar_modes
                            logger.debug(f"Using targeting_radar_modes map")
                        else:
                            logger.warning(f"targeting_radar_modes is not a dictionary, using global mode_map")
                
                elif 'aewc_radar' in radar_type:
                    if hasattr(RadarDisplayMode, 'aewc_radar_modes'):
                        if isinstance(RadarDisplayMode.aewc_radar_modes, dict):
                            mode_map = RadarDisplayMode.aewc_radar_modes
                            logger.debug(f"Using aewc_radar_modes map")
                        else:
                            logger.warning(f"aewc_radar_modes is not a dictionary, using global mode_map")
                
                else:
                    # For any other radar type, use the global map
                    logger.debug(f"No specific map for radar type {radar_type}, using global mode_map")
            else:
                logger.debug("No radar type provided, using global mode_map")
        except Exception as e:
            logger.error(f"Error selecting mode map: {str(e)}, using global mode_map")
            mode_map = RadarDisplayMode.mode_map
        
        # Verify we have a valid mode_map
        if not isinstance(mode_map, dict):
            logger.error(f"Mode map is not a dictionary. Type: {type(mode_map)}. Using fallback global mode_map.")
            try:
                mode_map = RadarDisplayMode.mode_map
                if not isinstance(mode_map, dict):
                    # Create a comprehensive fallback dictionary with ALL radar modes
                    logger.warning("Global mode_map is also not a dictionary, creating comprehensive fallback dictionary")
                    # Build a dictionary with all RadarDisplayMode enum values
                    mode_map = {}
                    for radar_mode in RadarDisplayMode:
                        mode_map[radar_mode.name] = radar_mode
                    
                    # Log the complete fallback map for debugging
                    logger.debug(f"Created comprehensive fallback mode_map with {len(mode_map)} entries")
            except Exception as e:
                logger.error(f"Error accessing global mode_map: {str(e)}, creating minimal fallback")

        
        # Handle dictionary input - extract mode from dictionary
        if isinstance(mode, dict):
            # Try different possible keys
            for key in ['mode', 'current_mode', 'radar_mode', 'display_mode']:
                if key in mode and mode[key] is not None:
                    # Recursive call with extracted value, preserving radar_type
                    return get_radar_display_mode(mode[key], radar_type)
            
            # If we got here, we couldn't find a valid mode in the dictionary
            logger.error(f"Could not find valid mode key in dictionary: {list(mode.keys())}")
            return None, None
            
        # Handle object with mode attribute
        if hasattr(mode, 'mode') and not isinstance(mode, (str, int, Enum)):
            # Recursive call with the mode attribute
            return get_radar_display_mode(getattr(mode, 'mode'), radar_type)
            
        # Handle object with current_mode attribute
        if hasattr(mode, 'current_mode') and not isinstance(mode, (str, int, Enum)):
            # Recursive call with the current_mode attribute
            return get_radar_display_mode(getattr(mode, 'current_mode'), radar_type)
        
        # Case 1: Mode is already a RadarDisplayMode enum instance
        if isinstance(mode, RadarDisplayMode):
            display_mode = mode
            mode_name = mode.name
            logger.info(f"Using RadarDisplayMode directly: {mode_name}")
            
        # Case 2: Mode is a display enum instance (from display subsystem)
        elif HAS_DISPLAY_ENUMS and isinstance(mode, Enum):
            # Check if this is one of our display enum types
            enum_class_name = mode.__class__.__name__
            if enum_class_name in ['BaseDisplayRadarMode', 'DisplayWeatherRadarMode', 
                                  'DisplayTFRRadarMode', 'DisplaySARRadarMode', 
                                  'DisplayTargetingRadarMode', 'DisplayAEWCRadarMode']:
                # Map from display enum to system enum
                try:
                    # Use the name to map between enum types
                    mode_str = mode.name
                    if mode_str in mode_map:
                        display_mode = mode_map[mode_str]
                        mode_name = display_mode.name
                        logger.info(f"Mapped {enum_class_name} {mode_str} to RadarDisplayMode: {mode_name}")
                    else:
                        # Try mapping by value if name doesn't match
                        try:
                            # First try to find a matching enum value
                            for radar_mode in RadarDisplayMode:
                                if radar_mode.value == mode.value:
                                    display_mode = radar_mode
                                    mode_name = display_mode.name
                                    logger.info(f"Mapped {enum_class_name} value {mode.value} to RadarDisplayMode: {mode_name}")
                                    break
                                    
                            # If not matched above, try direct constructor
                            if display_mode is None:
                                display_mode = RadarDisplayMode(mode.value)
                                mode_name = display_mode.name
                                logger.info(f"Direct mapped {enum_class_name} value {mode.value} to RadarDisplayMode: {mode_name}")
                        except ValueError:
                            # Use radar-specific helper if available
                            if hasattr(mode.__class__, 'to_radar_display_mode'):
                                # This will use the BaseDisplayRadarMode's shared helper method
                                display_mode = mode.__class__.to_radar_display_mode(mode)
                                if display_mode:
                                    mode_name = display_mode.name
                                    logger.info(f"Used to_radar_display_mode for {enum_class_name}: {mode_name}")
                                else:
                                    logger.error(f"to_radar_display_mode returned None for {enum_class_name} {mode}")
                            else:
                                logger.error(f"Could not map {enum_class_name} {mode} to RadarDisplayMode - no helper method")
                except Exception as e:
                    logger.error(f"Error mapping display mode enum: {str(e)}")
                    logger.error(f"Failed to convert {enum_class_name} {mode}")
                
        # Case 3: Mode is any other Enum type - try to use name or value
        elif isinstance(mode, Enum):
            # Try name first
            if hasattr(mode, 'name') and isinstance(mode_map, dict) and mode.name in mode_map:
                display_mode = mode_map[mode.name]
                mode_name = display_mode.name
                logger.info(f"Mapped Enum name {mode.name} to RadarDisplayMode: {mode_name}")
            # Try value if name doesn't work
            elif hasattr(mode, 'value'):
                try:
                    # First try to find a mode with matching value
                    for radar_mode in RadarDisplayMode:
                        if radar_mode.value == mode.value:
                            display_mode = radar_mode
                            mode_name = display_mode.name
                            logger.info(f"Mapped Enum value {mode.value} to RadarDisplayMode: {mode_name}")
                            break
                    
                    # If not found above, try direct constructor
                    if display_mode is None:
                        display_mode = RadarDisplayMode(mode.value)
                        mode_name = display_mode.name
                        logger.info(f"Mapped Enum value {mode.value} to RadarDisplayMode: {mode_name}")
                except ValueError:
                    # Try radar-specific mapping for legacy values
                    if radar_type and radar_type == 'weather_radar' and HAS_DISPLAY_ENUMS:
                        # Legacy DisplayWeatherRadarMode values may need special handling
                        if mode.value in [1, 2, 3, 4, 5]:  # Old enum values
                            legacy_map = {
                                1: RadarDisplayMode.STANDBY.value,      # Old STANDBY(1) -> New STANDBY(0)
                                2: RadarDisplayMode.MAPPING.value,      # Old MAPPING(2) -> New MAPPING(11)  
                                3: RadarDisplayMode.SURVEILLANCE.value, # Old SURVEILLANCE(3) -> New SURVEILLANCE(10)
                                4: RadarDisplayMode.TURBULENCE.value,   # Old WEATHER(4) -> New TURBULENCE(12) 
                                5: RadarDisplayMode.TEST.value,         # Old TEST(5) -> New TEST(3)
                            }
                            new_value = legacy_map.get(mode.value)
                            if new_value is not None:
                                try:
                                    display_mode = RadarDisplayMode(new_value)
                                    mode_name = display_mode.name
                                    logger.info(f"Mapped legacy weather radar enum value {mode.value} to RadarDisplayMode: {mode_name}")
                                except ValueError:
                                    logger.error(f"Invalid mapped mode value: {new_value}, cannot map to RadarDisplayMode")
                            else:
                                logger.error(f"Invalid enum value: {mode.value}, no legacy mapping available")
                        else:
                            logger.error(f"Invalid enum value: {mode.value}, cannot map to RadarDisplayMode")
                    else:
                        logger.error(f"Invalid enum value: {mode.value}, cannot map to RadarDisplayMode")
            else:
                logger.error(f"Cannot map enum {mode} to RadarDisplayMode: no usable name or value")
            
        # Case 4: Mode is a string key in the mode_map
        elif isinstance(mode, str) and isinstance(mode_map, dict) and mode in mode_map:
            display_mode = mode_map[mode]
            mode_name = display_mode.name
            logger.info(f"Mapped mode string '{mode}' to RadarDisplayMode: {mode_name}")
            
        # Case 5: Mode is a string but not in mode_map - try upper case version
        elif isinstance(mode, str) and isinstance(mode_map, dict) and mode.upper() in mode_map:
            upper_mode = mode.upper()
            display_mode = mode_map[upper_mode]
            mode_name = display_mode.name
            logger.info(f"Mapped mode string '{mode}' to RadarDisplayMode: {mode_name} (case-insensitive)")
            
        # Case 6: Mode is a string that matches a RadarDisplayMode enum name directly
        elif isinstance(mode, str):
            # Try direct attribute access on RadarDisplayMode
            try:
                upper_mode = mode.upper()
                # Check if the string matches any RadarDisplayMode enum name directly
                if hasattr(RadarDisplayMode, upper_mode):
                    display_mode = getattr(RadarDisplayMode, upper_mode)
                    mode_name = display_mode.name
                    logger.info(f"Mapped string representation '{mode}' to RadarDisplayMode enum directly")
                else:
                    # Special handling for "NORMAL", "STANDBY" and other common modes
                    if upper_mode == "NORMAL":
                        display_mode = RadarDisplayMode.NORMAL
                        mode_name = "NORMAL"
                        logger.info("Special handling: Mapped 'NORMAL' to RadarDisplayMode.NORMAL")
                    elif upper_mode == "STANDBY":
                        display_mode = RadarDisplayMode.STANDBY
                        mode_name = "STANDBY"
                        logger.info("Special handling: Mapped 'STANDBY' to RadarDisplayMode.STANDBY")
                    elif upper_mode == "SURVEILLANCE":
                        display_mode = RadarDisplayMode.SURVEILLANCE
                        mode_name = "SURVEILLANCE"
                        logger.info("Special handling: Mapped 'SURVEILLANCE' to RadarDisplayMode.SURVEILLANCE")
                    elif upper_mode == "WINDSHEAR":
                        display_mode = RadarDisplayMode.WINDSHEAR
                        mode_name = "WINDSHEAR"
                        logger.info("Special handling: Mapped 'WINDSHEAR' to RadarDisplayMode.WINDSHEAR")
                    else:
                        logger.error(f"Unknown mode string: {mode}, cannot map to RadarDisplayMode directly")
            except Exception as e:
                logger.error(f"Error in direct string-to-enum mapping: {str(e)}")
        
        # Case 7: Mode is an integer - try to map to enum value directly
        elif isinstance(mode, int):
            try:
                # First try direct match
                for radar_mode in RadarDisplayMode:
                    if radar_mode.value == mode:
                        display_mode = radar_mode
                        mode_name = display_mode.name
                        logger.info(f"Mapped mode value {mode} to RadarDisplayMode: {mode_name}")
                        break
                
                # If not found above, try direct constructor
                if display_mode is None:
                    display_mode = RadarDisplayMode(mode)
                    mode_name = display_mode.name
                    logger.info(f"Mapped mode value {mode} to RadarDisplayMode: {mode_name}")
            except ValueError:
                # Try radar-specific mapping for legacy values
                if radar_type and radar_type == 'weather_radar' and HAS_DISPLAY_ENUMS:
                    # Legacy DisplayWeatherRadarMode values may need special handling
                    if mode in [1, 2, 3, 4, 5]:  # Old enum values
                        legacy_map = {
                            1: RadarDisplayMode.STANDBY.value,      # Old STANDBY(1) -> New STANDBY(0)
                            2: RadarDisplayMode.MAPPING.value,      # Old MAPPING(2) -> New MAPPING(11)  
                            3: RadarDisplayMode.SURVEILLANCE.value, # Old SURVEILLANCE(3) -> New SURVEILLANCE(10)
                            4: RadarDisplayMode.TURBULENCE.value,   # Old WEATHER(4) -> New TURBULENCE(12) 
                            5: RadarDisplayMode.TEST.value,         # Old TEST(5) -> New TEST(3)
                        }
                        new_value = legacy_map.get(mode)
                        if new_value is not None:
                            try:
                                display_mode = RadarDisplayMode(new_value)
                                mode_name = display_mode.name
                                logger.info(f"Mapped legacy weather radar value {mode} to RadarDisplayMode: {mode_name}")
                            except ValueError:
                                logger.error(f"Invalid mapped mode value: {new_value}, cannot map to RadarDisplayMode")
                        else:
                            logger.error(f"Invalid mode value: {mode}, no legacy mapping available")
                    else:
                        logger.error(f"Invalid mode value: {mode}, cannot map to RadarDisplayMode")
                else:
                    logger.error(f"Invalid mode value: {mode}, cannot map to RadarDisplayMode")
        
        # Case 8: Any other type - try string representation as last resort
        else:
            try:
                # Try string representation
                mode_str = str(mode).upper()
                if isinstance(mode_map, dict) and mode_str in mode_map:
                    display_mode = mode_map[mode_str]
                    mode_name = display_mode.name
                    logger.info(f"Mapped string representation '{mode_str}' to RadarDisplayMode: {mode_name}")
                else:
                    logger.error(f"Unknown mode type {type(mode)}: {mode}, cannot map to RadarDisplayMode")
            except Exception as str_err:
                logger.error(f"Failed to convert {mode} to string: {str_err}")
            
    except Exception as e:
        logger.error(f"Error converting radar mode: {str(e)}")
        display_mode = None
        mode_name = None
        
    return display_mode, mode_name

def mode_to_string(
    mode: Union[str, RadarDisplayMode, int, dict, Any, None], 
    radar_type: Optional[str] = None
) -> Optional[str]:
    """
    Convert any mode representation to a string mode name.
    
    Args:
        mode: The mode to convert to a string
        radar_type: Optional string identifying the specific radar type
        
    Returns:
        str: The string mode name, or None if conversion failed
    """
    _, mode_name = get_radar_display_mode(mode, radar_type)
    return mode_name

def mode_to_enum(
    mode: Union[str, RadarDisplayMode, int, dict, Any, None], 
    radar_type: Optional[str] = None
) -> Optional[RadarDisplayMode]:
    """
    Convert any mode representation to a RadarDisplayMode enum instance.
    
    Args:
        mode: The mode to convert to an enum
        radar_type: Optional string identifying the specific radar type
        
    Returns:
        RadarDisplayMode: The enum instance, or None if conversion failed
    """
    display_mode, _ = get_radar_display_mode(mode, radar_type)
    return display_mode

def mode_to_value(
    mode: Union[str, RadarDisplayMode, int, dict, Any, None], 
    radar_type: Optional[str] = None
) -> Optional[int]:
    """
    Convert any mode representation to an integer mode value.
    
    Args:
        mode: The mode to convert to an integer value
        radar_type: Optional string identifying the specific radar type
        
    Returns:
        int: The integer mode value, or None if conversion failed
    """
    display_mode, _ = get_radar_display_mode(mode, radar_type)
    return display_mode.value if display_mode else None

def is_valid_radar_mode(
    mode: Union[str, RadarDisplayMode, int, dict, Any, None], 
    radar_type: Optional[str] = None
) -> bool:
    """
    Check if the given mode represents a valid radar mode.
    
    Args:
        mode: The mode to check, which can be a string name, RadarDisplayMode enum,
              integer value, dictionary, object, or None
        radar_type: Optional string identifying the specific radar type
              
    Returns:
        bool: True if the mode is valid, False otherwise
    """
    display_mode, _ = get_radar_display_mode(mode, radar_type)
    return display_mode is not None

def get_mode_properties(
    mode: Union[str, RadarDisplayMode, int, dict, Any, None], 
    radar_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get a dictionary of properties for the given mode.
    
    This function is useful for constructing message data and metadata.
    
    Args:
        mode: The mode to get properties for
        radar_type: Optional string identifying the specific radar type
        
    Returns:
        Dict: Dictionary with mode properties including:
            - 'mode': String mode name
            - 'mode_value': Integer mode value
            - 'mode_enum': RadarDisplayMode enum instance
            - 'is_valid': Boolean indicating if mode is valid
            - 'radar_type': The radar type if provided or determined
    """
    display_mode, mode_name = get_radar_display_mode(mode, radar_type)
    
    return {
        'mode': mode_name,
        'mode_value': display_mode.value if display_mode else None,
        'mode_enum': display_mode,
        'is_valid': display_mode is not None,
        'radar_type': radar_type
    }

def get_display_mode_enum(
    mode: Union[str, RadarDisplayMode, int, dict, Any, None], 
    radar_type: str
) -> Optional[Enum]:
    """
    Convert a mode to the appropriate display-side enum instance.
    
    This function is useful for converting system-side RadarDisplayMode
    to display-side enums for proper display handling.
    
    Args:
        mode: The mode to convert
        radar_type: String identifying the specific radar type 
            (weather_radar, tfr_radar, sar_radar, targeting_radar, aewc_radar)
            
    Returns:
        Enum: The appropriate display mode enum instance, or None if conversion failed
    """
    if not HAS_DISPLAY_ENUMS:
        logger.error("Display enums not available, cannot convert to display mode")
        return None
        
    try:
        # First convert to RadarDisplayMode
        radar_mode, _ = get_radar_display_mode(mode, radar_type)
        if not radar_mode:
            logger.error(f"Could not convert {mode} to RadarDisplayMode")
            return None
            
        # Get the appropriate display enum class for this radar type
        display_mode_class = get_display_mode_class(radar_type)
        if not display_mode_class:
            logger.error(f"No display mode class found for radar type: {radar_type}")
            return None
        
        logger.info(f"Using display mode class {display_mode_class.__name__} for {radar_type}")
            
        # Try to map by matching value
        for display_mode in display_mode_class:
            if display_mode.value == radar_mode.value:
                logger.info(f"Mapped RadarDisplayMode {radar_mode.name} to {display_mode_class.__name__}: {display_mode.name}")
                return display_mode
                
        # Try by name if value not found
        mode_name = radar_mode.name
        try:
            # Note: we use getattr to get the enum value rather than direct key access 
            # to avoid KeyError if the name doesn't exist
            display_mode = getattr(display_mode_class, mode_name, None)
            if display_mode:
                logger.info(f"Mapped RadarDisplayMode {mode_name} to {display_mode_class.__name__} by name")
                return display_mode
            else:
                logger.error(f"No enum member named {mode_name} in {display_mode_class.__name__}")
        except (AttributeError, ValueError) as e:
            logger.error(f"Error mapping by name {mode_name} in {display_mode_class.__name__}: {str(e)}")
            
        # Default to STANDBY if mapping failed
        logger.warning(f"Could not map {radar_mode.name} to {display_mode_class.__name__}, defaulting to STANDBY")
        return display_mode_class.STANDBY
        
    except Exception as e:
        logger.error(f"Error converting to display mode enum: {str(e)}")
        return None

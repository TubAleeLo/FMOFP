"""
Radar Display Modes
--Aligns with addressbook.xml
Defines the display modes specific to radar displays.
This file serves as a central reference for radar display modes used across the system.

This is the primary source of truth for all radar mode values in the system.
All display and system components must use these values for consistency.
"""

from enum import Enum

class RadarDisplayMode(Enum):
    """
    Radar-specific display modes.
    
    These modes are used for radar displays and are separate from the general
    display modes (DAY, NIGHT, NVG) defined in base_display.py.
    
    This comprehensive enum includes modes from all radar types:
    - Weather Radar
    - Terrain Following Radar (TFR)
    - Synthetic Aperture Radar (SAR)
    - Targeting Radar
    - Airborne Early Warning and Control (AEWC) Radar
    
    The mode values follow a standardized structure:
    - Universal Base Modes: -1 to 9
    - Weather Radar Modes: 10-19
    - TFR Radar Modes: 20-29
    - SAR Radar Modes: 30-39
    - Targeting Radar Modes: 40-49
    - AEWC Radar Modes: 50-59
    """
    # Universal Base Modes (0-9)
    INITIALIZING = -1   # Special pre-operational state
    STANDBY = 0         # Power-saving/inactive state
    NORMAL = 1          # Standard operational mode
    DEGRADED = 2        # Reduced capability mode
    TEST = 3            # Built-in test mode 
    MAINTENANCE = 4     # Maintenance/calibration mode
    EMERGENCY = 5       # Emergency operations mode
    FAILURE = 6         # System failure mode
    RECOVERY = 7        # Recovery from failure mode
    CALIBRATION = 8     # Active calibration mode
    
    # Weather Radar Modes (10-19)
    SURVEILLANCE = 10   # Primary weather surveillance mode
    MAPPING = 11        # Ground mapping (Weather radar)
    TURBULENCE = 12     # Turbulence detection (Weather radar)
    WINDSHEAR = 13      # Wind shear detection (Weather radar)
    PRECIPITATION = 14  # Precipitation measurement mode
    
    # TFR Radar Modes (20-29)
    TFR_SEARCH = 20     # Search mode (TFR)
    TFR_TRACK = 21      # Track mode (TFR)
    TFR_ACTIVE = 22     # Active mode (TFR)
    TERRAIN_FOLLOWING = 23  # Terrain following (TFR)
    OBSTACLE_AVOIDANCE = 24 # Obstacle avoidance (TFR)
    TFR_GROUND_MAPPING = 25 # Ground mapping (TFR)
    
    # SAR Radar Modes (30-39)
    STRIPMAP = 30       # Stripmap mode (SAR)
    SPOTLIGHT = 31      # Spotlight mode (SAR)
    SCANSAR = 32        # ScanSAR mode (SAR)
    INTERFEROMETRIC = 33 # Interferometric mode (SAR)
    DOPPLER_BEAM = 34   # Doppler beam mode (SAR)
    
    # Targeting Radar Modes (40-49)
    TARGET_SEARCH = 40  # Target search mode
    TARGET_TRACK = 41   # Target tracking mode
    LOCK = 42           # Lock mode (Targeting)
    TERRAIN_AVOIDANCE = 43 # Terrain avoidance (Targeting)
    
    # AEWC Radar Modes (50-59)
    AEWC_SEARCH = 50    # Search mode (AEWC)
    AEWC_SURVEILLANCE = 51 # Surveillance mode (AEWC)
    SECTOR_SCAN = 52    # Sector scan (AEWC)
    STEALTH_DETECTION = 53 # Stealth detection (AEWC)
    ELECTRONIC_PROTECTION = 54 # Electronic protection (AEWC)
    AEWC_TRACK = 55     # Track mode (AEWC)

    
    # Comprehensive mode map for all radar types
    mode_map = {
        # Universal Base Modes
        'INITIALIZING': INITIALIZING,
        'STANDBY': STANDBY,
        'NORMAL': NORMAL,
        'DEGRADED': DEGRADED,
        'TEST': TEST,
        'MAINTENANCE': MAINTENANCE,
        'EMERGENCY': EMERGENCY,
        'FAILURE': FAILURE,
        'RECOVERY': RECOVERY,
        'CALIBRATION': CALIBRATION,
        
        # Weather Radar Modes
        'SURVEILLANCE': SURVEILLANCE,
        'MAPPING': MAPPING,
        'TURBULENCE': TURBULENCE,
        'WINDSHEAR': WINDSHEAR,
        'PRECIPITATION': PRECIPITATION,
        
        # TFR Radar Modes
        'TFR_SEARCH': TFR_SEARCH,
        'SEARCH': TFR_SEARCH,  # Alias for backward compatibility
        'TFR_TRACK': TFR_TRACK,
        'TRACK': TFR_TRACK,    # Alias for backward compatibility
        'TFR_ACTIVE': TFR_ACTIVE,
        'ACTIVE': TFR_ACTIVE,  # Alias for backward compatibility
        'TERRAIN_FOLLOWING': TERRAIN_FOLLOWING,
        'OBSTACLE_AVOIDANCE': OBSTACLE_AVOIDANCE,
        'TFR_GROUND_MAPPING': TFR_GROUND_MAPPING,
        'GROUND_MAPPING': TFR_GROUND_MAPPING,  # Alias for backward compatibility
        
        # SAR Radar Modes
        'STRIPMAP': STRIPMAP,
        'SPOTLIGHT': SPOTLIGHT,
        'SCANSAR': SCANSAR,
        'INTERFEROMETRIC': INTERFEROMETRIC,
        'DOPPLER_BEAM': DOPPLER_BEAM,
        
        # Targeting Radar Modes
        'TARGET_SEARCH': TARGET_SEARCH,
        'TARGET_TRACK': TARGET_TRACK,
        'LOCK': LOCK,
        'TERRAIN_AVOIDANCE': TERRAIN_AVOIDANCE,
        
        # AEWC Radar Modes
        'AEWC_SEARCH': AEWC_SEARCH,
        'AEWC_SURVEILLANCE': AEWC_SURVEILLANCE,
        'SECTOR_SCAN': SECTOR_SCAN,
        'STEALTH_DETECTION': STEALTH_DETECTION, 
        'ELECTRONIC_PROTECTION': ELECTRONIC_PROTECTION,
        'AEWC_TRACK': AEWC_TRACK,

        # NOTE (production readiness re-analysis, August 2026): a duplicate
        # 'SEARCH'/'TRACK'/'ACTIVE' block used to be here, repeating the same
        # three keys (with identical values: TFR_SEARCH/TFR_TRACK/TFR_ACTIVE)
        # already defined above under "TFR Radar Modes" as backward-
        # compatibility aliases. Found via `ruff check --select F601`
        # (multi-value-repeated-key-literal). Since the values were
        # byte-for-byte identical both times, this was purely redundant --
        # not a behavior bug, just dead duplicate code -- removed rather than
        # the earlier occurrence to keep the aliases defined in one place.
    }
    
    # Radar-specific mode maps to help with converting between system and display modes
    weather_radar_modes = {
        'STANDBY': STANDBY,
        'NORMAL': NORMAL,
        'SURVEILLANCE': SURVEILLANCE,
        'MAPPING': MAPPING,
        'TURBULENCE': TURBULENCE,
        'WINDSHEAR': WINDSHEAR,
        'PRECIPITATION': PRECIPITATION
    }
    
    tfr_radar_modes = {
        'STANDBY': STANDBY,
        'NORMAL': NORMAL,
        'SEARCH': TFR_SEARCH,
        'TRACK': TFR_TRACK,
        'ACTIVE': TFR_ACTIVE,
        'TERRAIN_FOLLOWING': TERRAIN_FOLLOWING,
        'OBSTACLE_AVOIDANCE': OBSTACLE_AVOIDANCE,
        'GROUND_MAPPING': TFR_GROUND_MAPPING
    }
    
    sar_radar_modes = {
        'STANDBY': STANDBY,
        'NORMAL': NORMAL,
        'STRIPMAP': STRIPMAP,
        'SPOTLIGHT': SPOTLIGHT,
        'SCANSAR': SCANSAR,
        'INTERFEROMETRIC': INTERFEROMETRIC,
        'DOPPLER_BEAM': DOPPLER_BEAM
    }
    
    targeting_radar_modes = {
        'STANDBY': STANDBY,
        'NORMAL': NORMAL,
        'SEARCH': TARGET_SEARCH,
        'TRACK': TARGET_TRACK,
        'LOCK': LOCK,
        'TERRAIN_AVOIDANCE': TERRAIN_AVOIDANCE
    }
    
    aewc_radar_modes = {
        'STANDBY': STANDBY,
        'NORMAL': NORMAL,
        'SEARCH': AEWC_SEARCH,
        'TRACK': AEWC_TRACK,
        'SURVEILLANCE': AEWC_SURVEILLANCE,
        'SECTOR_SCAN': SECTOR_SCAN,
        'STEALTH_DETECTION': STEALTH_DETECTION,
        'ELECTRONIC_PROTECTION': ELECTRONIC_PROTECTION
    }

    @classmethod
    def from_string(cls, mode_str):
        """
        Convert a string mode name to the corresponding enum value.
        
        Args:
            mode_str: String representation of the mode name
            
        Returns:
            RadarDisplayMode: The corresponding enum value, or STANDBY if not found
        """
        if not mode_str:
            return cls.STANDBY
            
        mode_str = mode_str.upper()
        
        # First check the comprehensive mode map
        if mode_str in cls.mode_map:
            return cls.mode_map[mode_str]
            
        # Then try a direct match with enum names
        for mode in cls:
            if mode.name == mode_str:
                return mode
                
        # Default to STANDBY if not found
        return cls.STANDBY
    
    @classmethod
    def to_string(cls, mode_value):
        """
        Convert a mode value to its string representation.
        
        Args:
            mode_value: Integer value of the mode
            
        Returns:
            str: The string representation of the mode, or "STANDBY" if not found
        """
        if mode_value is None:
            return "STANDBY"
            
        # Try to convert directly from value
        for mode in cls:
            if mode.value == mode_value:
                return mode.name
                
        # Default to STANDBY if not found
        return "STANDBY"
        
    @classmethod
    def get_radar_specific_mode(cls, mode_name_or_value, radar_type):
        """
        Get the appropriate mode for a specific radar type.
        
        This handles the case where the same name might map to different
        mode values for different radar types.
        
        Args:
            mode_name_or_value: String name or integer value of the mode
            radar_type: String identifying the radar type
                (weather_radar, tfr_radar, sar_radar, targeting_radar, aewc_radar)
                
        Returns:
            RadarDisplayMode: The appropriate mode for the specified radar type
        """
        # Convert mode to string if it's an integer or enum
        if isinstance(mode_name_or_value, int):
            mode_name = cls.to_string(mode_name_or_value)
        elif isinstance(mode_name_or_value, cls):
            mode_name = mode_name_or_value.name
        else:
            mode_name = str(mode_name_or_value).upper()
            
        # Select the appropriate mode map based on radar type
        if radar_type == 'weather_radar':
            mode_map = cls.weather_radar_modes
        elif radar_type == 'tfr_radar':
            mode_map = cls.tfr_radar_modes
        elif radar_type == 'sar_radar':
            mode_map = cls.sar_radar_modes
        elif radar_type == 'targeting_radar':
            mode_map = cls.targeting_radar_modes
        elif radar_type == 'aewc_radar':
            mode_map = cls.aewc_radar_modes
        else:
            # If radar type is unknown, use the comprehensive mode map
            mode_map = cls.mode_map
            
        # Look up the mode in the selected mode map
        if mode_name in mode_map:
            return mode_map[mode_name]
            
        # Default to the common mode map if not found in radar-specific map
        if mode_name in cls.mode_map:
            return cls.mode_map[mode_name]
            
        # Default to STANDBY if not found anywhere
        return cls.STANDBY

"""
Display-local radar enums

This module contains enums used by the radar display components.
These are display-local versions of the radar system enums that directly match
the values defined in radar_display_modes.py to ensure consistent mode handling
across system and display boundaries.
"""

from enum import Enum, auto
from FMOFP.local_messaging.radar_display_modes import RadarDisplayMode

class BaseDisplayRadarMode(Enum):
    """
    Base radar mode enum for display use.
    
    Contains universal base modes common to all radar types.
    Values directly match those in RadarDisplayMode.
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
    
    @classmethod
    def from_string(cls, mode_str):
        """Convert a string mode name to enum value."""
        try:
            return cls[mode_str.upper()]
        except KeyError:
            # Try to map from radar display mode
            try:
                radar_mode = RadarDisplayMode.from_string(mode_str)
                for mode in cls:
                    if mode.value == radar_mode.value:
                        return mode
                # If not found, return STANDBY as default
                return cls.STANDBY
            except Exception:
                return cls.STANDBY
            
    @classmethod
    def from_value(cls, value):
        """Convert a numeric value to enum value."""
        try:
            return cls(value)
        except ValueError:
            # Try to find a matching value or return STANDBY
            for mode in cls:
                if mode.value == value:
                    return mode
            return cls.STANDBY
            
    @classmethod
    def to_radar_display_mode(cls, mode):
        """Convert display-side mode to system-side RadarDisplayMode."""
        if mode is None:
            return RadarDisplayMode.STANDBY
            
        # If already a RadarDisplayMode, return it
        if isinstance(mode, RadarDisplayMode):
            return mode
            
        # If it's a string, convert to enum first
        if isinstance(mode, str):
            mode = cls.from_string(mode)
            
        # If it's an integer, convert by value
        if isinstance(mode, int):
            mode_value = mode
        else:
            # It's our enum type
            mode_value = mode.value
            
        # Map to RadarDisplayMode by value
        for radar_mode in RadarDisplayMode:
            if radar_mode.value == mode_value:
                return radar_mode
                
        # Default to STANDBY if not found
        return RadarDisplayMode.STANDBY

class DisplayWeatherRadarMode(Enum):
    """
    Weather radar mode enum for display use.
    Values exactly match those in RadarDisplayMode for consistency.
    """
    # Universal Base Modes (0-9)
    INITIALIZING = -1
    STANDBY = 0
    NORMAL = 1
    DEGRADED = 2
    TEST = 3
    MAINTENANCE = 4
    EMERGENCY = 5
    FAILURE = 6
    RECOVERY = 7
    CALIBRATION = 8
    
    # Weather Radar Modes (10-19)
    SURVEILLANCE = 10   # Primary weather surveillance mode
    MAPPING = 11        # Ground mapping (Weather radar)
    TURBULENCE = 12     # Turbulence detection (Weather radar)
    WINDSHEAR = 13      # Wind shear detection (Weather radar)
    PRECIPITATION = 14  # Precipitation measurement mode
    
    # Legacy compatibility - map the old values to the new ones
    @classmethod
    def _convert_legacy_value(cls, value):
        """Convert from old value schema to new standardized values."""
        legacy_map = {
            1: cls.STANDBY.value,      # Old STANDBY(1) -> New STANDBY(0)
            2: cls.MAPPING.value,      # Old MAPPING(2) -> New MAPPING(11)
            3: cls.SURVEILLANCE.value, # Old SURVEILLANCE(3) -> New SURVEILLANCE(10)
            4: cls.TURBULENCE.value,   # Old WEATHER(4) -> New TURBULENCE(12)
            5: cls.TEST.value,         # Old TEST(5) -> New TEST(3)
        }
        return legacy_map.get(value, cls.STANDBY.value)
    
    @classmethod
    def from_value(cls, value):
        """
        Convert a numeric value to enum value, handling legacy values.
        
        This method ensures backward compatibility by mapping old enum
        values to the new standardized values.
        """
        try:
            return cls(value)
        except ValueError:
            # Check if it's a legacy value that needs conversion
            if value in [1, 2, 3, 4, 5]:  # Old enum values
                new_value = cls._convert_legacy_value(value)
                return cls(new_value)
            
            # Try to find a direct match
            for mode in cls:
                if mode.value == value:
                    return mode
                    
            # Default to STANDBY
            return cls.STANDBY
            
    @classmethod
    def from_string(cls, mode_str):
        """Convert a string mode name to enum value."""
        try:
            return cls[mode_str.upper()]
        except KeyError:
            # Try to map from radar display mode
            try:
                radar_mode = RadarDisplayMode.from_string(mode_str)
                for mode in cls:
                    if mode.value == radar_mode.value:
                        return mode
                # If not found, return STANDBY as default
                return cls.STANDBY
            except Exception:
                return cls.STANDBY
                
    @classmethod
    def to_radar_display_mode(cls, mode):
        """Convert display-side mode to system-side RadarDisplayMode."""
        return BaseDisplayRadarMode.to_radar_display_mode(mode)

class DisplayTFRRadarMode(Enum):
    """
    Terrain Following Radar (TFR) mode enum for display use.
    Values exactly match those in RadarDisplayMode for consistency.
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
    
    
    @classmethod
    def from_string(cls, mode_str):
        """Convert a string mode name to enum value."""
        try:
            return cls[mode_str.upper()]
        except KeyError:
            # Try to map from radar display mode
            try:
                radar_mode = RadarDisplayMode.from_string(mode_str)
                for mode in cls:
                    if mode.value == radar_mode.value:
                        return mode
                # If not found, return STANDBY as default
                return cls.STANDBY
            except Exception:
                return cls.STANDBY
                
    @classmethod
    def from_value(cls, value):
        """Convert a numeric value to enum value."""
        try:
            return cls(value)
        except ValueError:
            # Try to find a matching value or return STANDBY
            for mode in cls:
                if mode.value == value:
                    return mode
            return cls.STANDBY
            
    @classmethod
    def to_radar_display_mode(cls, mode):
        """Convert display-side mode to system-side RadarDisplayMode."""
        return BaseDisplayRadarMode.to_radar_display_mode(mode)

class DisplaySARRadarMode(Enum):
    """
    Synthetic Aperture Radar (SAR) mode enum for display use.
    Values exactly match those in RadarDisplayMode for consistency.
    """
    # Universal Base Modes (0-9)
    INITIALIZING = -1
    STANDBY = 0
    NORMAL = 1
    DEGRADED = 2
    TEST = 3
    MAINTENANCE = 4
    EMERGENCY = 5
    FAILURE = 6
    RECOVERY = 7
    CALIBRATION = 8
    
    # SAR Radar Modes (30-39)
    STRIPMAP = 30       # Stripmap mode (SAR)
    SPOTLIGHT = 31      # Spotlight mode (SAR)
    SCANSAR = 32        # ScanSAR mode (SAR)
    INTERFEROMETRIC = 33 # Interferometric mode (SAR)
    DOPPLER_BEAM = 34   # Doppler beam mode (SAR)
    
    @classmethod
    def from_string(cls, mode_str):
        """Convert a string mode name to enum value."""
        try:
            return cls[mode_str.upper()]
        except KeyError:
            # Try to map from radar display mode
            try:
                radar_mode = RadarDisplayMode.from_string(mode_str)
                for mode in cls:
                    if mode.value == radar_mode.value:
                        return mode
                # If not found, return STANDBY as default
                return cls.STANDBY
            except Exception:
                return cls.STANDBY
                
    @classmethod
    def from_value(cls, value):
        """Convert a numeric value to enum value."""
        try:
            return cls(value)
        except ValueError:
            # Try to find a matching value or return STANDBY
            for mode in cls:
                if mode.value == value:
                    return mode
            return cls.STANDBY
            
    @classmethod
    def to_radar_display_mode(cls, mode):
        """Convert display-side mode to system-side RadarDisplayMode."""
        return BaseDisplayRadarMode.to_radar_display_mode(mode)

class DisplayTargetingRadarMode(Enum):
    """
    Targeting Radar mode enum for display use.
    Values exactly match those in RadarDisplayMode for consistency.
    """
    # Universal Base Modes (0-9)
    INITIALIZING = -1
    STANDBY = 0
    NORMAL = 1
    DEGRADED = 2
    TEST = 3
    MAINTENANCE = 4
    EMERGENCY = 5
    FAILURE = 6
    RECOVERY = 7
    CALIBRATION = 8
    
    # Targeting Radar Modes (40-49)
    SEARCH = 40         # Target search mode
    TRACK = 41          # Target tracking mode
    LOCK = 42           # Lock mode (Targeting)
    TERRAIN_AVOIDANCE = 43 # Terrain avoidance (Targeting)
    
    @classmethod
    def from_string(cls, mode_str):
        """Convert a string mode name to enum value."""
        try:
            return cls[mode_str.upper()]
        except KeyError:
            # Try to map from radar display mode
            try:
                radar_mode = RadarDisplayMode.from_string(mode_str)
                for mode in cls:
                    if mode.value == radar_mode.value:
                        return mode
                # If not found, return STANDBY as default
                return cls.STANDBY
            except Exception:
                return cls.STANDBY
                
    @classmethod
    def from_value(cls, value):
        """Convert a numeric value to enum value."""
        try:
            return cls(value)
        except ValueError:
            # Try to find a matching value or return STANDBY
            for mode in cls:
                if mode.value == value:
                    return mode
            return cls.STANDBY
            
    @classmethod
    def to_radar_display_mode(cls, mode):
        """Convert display-side mode to system-side RadarDisplayMode."""
        return BaseDisplayRadarMode.to_radar_display_mode(mode)

class DisplayAEWCRadarMode(Enum):
    """
    Airborne Early Warning and Control (AEWC) Radar mode enum for display use.
    Values exactly match those in RadarDisplayMode for consistency.
    """
    # Universal Base Modes (0-9)
    INITIALIZING = -1
    STANDBY = 0
    NORMAL = 1
    DEGRADED = 2
    TEST = 3
    MAINTENANCE = 4
    EMERGENCY = 5
    FAILURE = 6
    RECOVERY = 7
    CALIBRATION = 8
    
    # AEWC Radar Modes (50-59)
    SEARCH = 50         # Search mode (AEWC)
    SURVEILLANCE = 51   # Surveillance mode (AEWC)
    SECTOR_SCAN = 52    # Sector scan (AEWC)
    STEALTH_DETECTION = 53 # Stealth detection (AEWC)
    ELECTRONIC_PROTECTION = 54 # Electronic protection (AEWC)
    
    @classmethod
    def from_string(cls, mode_str):
        """Convert a string mode name to enum value."""
        try:
            return cls[mode_str.upper()]
        except KeyError:
            # Try to map from radar display mode
            try:
                radar_mode = RadarDisplayMode.from_string(mode_str)
                for mode in cls:
                    if mode.value == radar_mode.value:
                        return mode
                # If not found, return STANDBY as default
                return cls.STANDBY
            except Exception:
                return cls.STANDBY
                
    @classmethod
    def from_value(cls, value):
        """Convert a numeric value to enum value."""
        try:
            return cls(value)
        except ValueError:
            # Try to find a matching value or return STANDBY
            for mode in cls:
                if mode.value == value:
                    return mode
            return cls.STANDBY
            
    @classmethod
    def to_radar_display_mode(cls, mode):
        """Convert display-side mode to system-side RadarDisplayMode."""
        return BaseDisplayRadarMode.to_radar_display_mode(mode)

# Map radar type strings to their corresponding display enum classes
radar_display_mode_map = {
    'weather_radar': DisplayWeatherRadarMode,
    'tfr_radar': DisplayTFRRadarMode,
    'sar_radar': DisplaySARRadarMode,
    'targeting_radar': DisplayTargetingRadarMode,
    'aewc_radar': DisplayAEWCRadarMode
}

def get_display_mode_class(radar_type):
    """
    Get the appropriate display mode enum class for a given radar type.
    
    Args:
        radar_type: String identifying the radar type
            (weather_radar, tfr_radar, sar_radar, targeting_radar, aewc_radar)
            
    Returns:
        Enum class: The appropriate display mode enum class for the radar type
    """
    return radar_display_mode_map.get(radar_type, BaseDisplayRadarMode)

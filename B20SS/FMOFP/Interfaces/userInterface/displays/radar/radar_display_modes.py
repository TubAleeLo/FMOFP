"""
Radar Display Modes for Display System
--Local version for the display system
Defines the display modes specific to radar displays.
This file serves as a central reference for radar display modes used across the display system.
"""

from enum import Enum

class RadarDisplayMode(Enum):
    """
    Radar-specific display modes for the display system.
    
    These modes are used for radar displays and are separate from the general
    display modes (DAY, NIGHT, NVG) defined in base_display.py.
    
    The values are aligned with the mode values used in the radar systems:
    - STANDBY (0): Radar is powered but not actively scanning
    - NORMAL/SURVEILLANCE (1): Standard surveillance mode
    - MAPPING (2): Ground mapping mode
    - TURBULENCE (3): Turbulence detection mode
    - WINDSHEAR (4): Wind shear detection mode
    - NORMAL (5): Standard mode
    """
    STANDBY = 0
    SURVEILLANCE = 1 # Primary name for mode 1
    MAPPING = 2
    TURBULENCE = 3
    WINDSHEAR = 4
    NORMAL = 5

    @classmethod
    def from_string(cls, mode_str):
        """Convert a string mode name to the corresponding enum value."""
        if not isinstance(mode_str, str):
            return cls.SURVEILLANCE  # Default to SURVEILLANCE for non-string inputs
        
        mode_str = mode_str.upper()
        for mode in cls:
            if mode.name == mode_str:
                return mode
        
        # Special case handling
        if mode_str == "NORMAL":
            return cls.SURVEILLANCE  # Map "NORMAL" to "SURVEILLANCE" as fallback
            
        return cls.SURVEILLANCE  # Default to SURVEILLANCE if not found
    
    @classmethod
    def to_string(cls, mode_value):
        """Convert a mode value to its string representation."""
        if isinstance(mode_value, int):
            for mode in cls:
                if mode.value == mode_value:
                    return mode.name
        return "SURVEILLANCE"  # Default to SURVEILLANCE if not found
        
    @classmethod
    def get_mode_map(cls):
        """Get a dictionary mapping mode names to enum values."""
        return {
            'STANDBY': cls.STANDBY,
            'SURVEILLANCE': cls.SURVEILLANCE,
            'MAPPING': cls.MAPPING,
            'TURBULENCE': cls.TURBULENCE,
            'WINDSHEAR': cls.WINDSHEAR,
            'NORMAL': cls.SURVEILLANCE  # Map "NORMAL" to "SURVEILLANCE"
        }

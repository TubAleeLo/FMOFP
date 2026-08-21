"""
Radar Enums

Contains all radar-related enumerations to avoid circular imports.
"""

from enum import Enum, auto

class MissionPhase(Enum):
    PRE_FLIGHT = 0
    TAKEOFF = 1
    CLIMB = 2
    CRUISE = 3
    DESCENT = 4
    APPROACH = 5
    LANDING = 6
    POST_FLIGHT = 7

class RadarMode(Enum):
    STANDBY = 0
    NORMAL = 1
    ACTIVE = 2
    SEARCH = 3
    TRACK = 4

class weather_radarMode(Enum):
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
    
    # Weather Radar Specific Modes (10-19)
    SURVEILLANCE = 10   # Primary weather surveillance mode
    MAPPING = 11        # Ground mapping (Weather radar)
    TURBULENCE = 12     # Turbulence detection (Weather radar)
    WINDSHEAR = 13      # Wind shear detection (Weather radar)
    PRECIPITATION = 14  # Precipitation measurement mode

class targeting_radarMode(Enum):
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
    
    # Targeting Radar Specific Modes (40-49)
    TARGET_SEARCH = 40  # Target search mode
    SEARCH = 40         # Alias for TARGET_SEARCH
    TARGET_TRACK = 41   # Target tracking mode
    TRACK = 41          # Alias for TARGET_TRACK
    TRACKING = 41        # Alias for TARGET_TRACK (matches the name used by
                         # Interfaces/predefinedMessages' targeting radar
                         # message helpers)
    LOCK = 42           # Lock mode (Targeting)
    TERRAIN_AVOIDANCE = 43 # Terrain avoidance (Targeting)
    GROUND_MAPPING = 25 # Using TFR ground mapping value for compatibility

class sar_radarMode(Enum):
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
    
    # SAR Radar Specific Modes (30-39)
    STRIPMAP = 30       # Stripmap mode (SAR)
    SPOTLIGHT = 31      # Spotlight mode (SAR)
    SCANSAR = 32        # ScanSAR mode (SAR)
    INTERFEROMETRIC = 33 # Interferometric mode (SAR)
    DOPPLER_BEAM = 34   # Doppler beam mode (SAR)

class aewc_radarMode(Enum):
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
    
    # AEWC Radar Specific Modes (50-59)
    AEWC_SEARCH = 50    # Search mode (AEWC)
    SEARCH = 50         # Alias for AEWC_SEARCH
    AEWC_SURVEILLANCE = 51 # Surveillance mode (AEWC)
    SURVEILLANCE = 51   # Alias for AEWC_SURVEILLANCE
    SECTOR_SCAN = 52    # Sector scan (AEWC)
    STEALTH_DETECTION = 53 # Stealth detection (AEWC)
    ELECTRONIC_PROTECTION = 54 # Electronic protection (AEWC)
    AEWC_TRACK = 55     # Track mode (AEWC)
    TRACK = 55          # Alias for AEWC_TRACK
    TRACKING = 55        # Alias for AEWC_TRACK (matches the name used by
                         # Interfaces/predefinedMessages' AEWC message
                         # helpers)
    GROUND_MAPPING = 25 # Using TFR ground mapping value for compatibility

class tfr_radarMode(Enum):
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
    
    # TFR Radar Specific Modes (20-29)
    TFR_SEARCH = 20     # Search mode (TFR)
    SEARCH = 20         # Alias for TFR_SEARCH
    TFR_TRACK = 21      # Track mode (TFR)
    TRACK = 21          # Alias for TFR_TRACK
    TFR_ACTIVE = 22     # Active mode (TFR)
    ACTIVE = 22         # Alias for TFR_ACTIVE
    TERRAIN_FOLLOWING = 23 # Terrain following (TFR)
    OBSTACLE_AVOIDANCE = 24 # Obstacle avoidance (TFR)
    TFR_GROUND_MAPPING = 25 # Ground mapping (TFR)
    GROUND_MAPPING = 25 # Alias for TFR_GROUND_MAPPING

class RadarTrackClass(Enum):
    UNKNOWN = auto()
    FIGHTER = auto()
    BOMBER = auto()
    TRANSPORT = auto()
    HELICOPTER = auto()
    UAV = auto()
    STEALTH = auto()
    GROUND_VEHICLE = auto()
    SHIP = auto()

class RadarTrackQuality(Enum):
    LOST = 0
    POOR = 1
    FAIR = 2
    GOOD = 3
    EXCELLENT = 4

class RadarPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class RadarAlertLevel(Enum):
    INFO = 1
    WARNING = 2
    CAUTION = 3
    CRITICAL = 4

class RadarMaintenanceStatus(Enum):
    OPERATIONAL = auto()
    DEGRADED = auto()
    MAINTENANCE_REQUIRED = auto()
    FAULT = auto()
    FAILED = auto()

class RadarInterferenceType(Enum):
    NONE = auto()
    NOISE = auto()
    JAMMING = auto()
    SPOOFING = auto()
    MULTIPATH = auto()
    CLUTTER = auto()

class RadarEnvironmentalCondition(Enum):
    NORMAL = auto()
    RAIN = auto()
    SNOW = auto()
    FOG = auto()
    DUST = auto()
    DUCTING = auto()

class RadarProcessingMode(Enum):
    NORMAL = auto()
    HIGH_SENSITIVITY = auto()
    CLUTTER_REJECTION = auto()
    JAMMING_RESISTANCE = auto()
    STEALTH_OPTIMIZED = auto()

class RadarCalibrationStatus(Enum):
    NOT_CALIBRATED = auto()
    IN_PROGRESS = auto()
    PARTIAL = auto()
    COMPLETE = auto()
    FAILED = auto()

class RadarDataQuality(Enum):
    UNUSABLE = 0
    DEGRADED = 1
    ACCEPTABLE = 2
    NOMINAL = 3
    OPTIMAL = 4

class RadarOperationalState(Enum):
    OFF = auto()
    INITIALIZING = auto()
    STANDBY = auto()
    OPERATING = auto()
    DEGRADED = auto()
    FAULT = auto()
    MAINTENANCE = auto()
    SHUTDOWN = auto()

class RadarTestStatus(Enum):
    NOT_TESTED = auto()
    TEST_IN_PROGRESS = auto()
    TEST_PASSED = auto()
    TEST_FAILED = auto()
    TEST_ABORTED = auto()

class RadarSectorPriority(Enum):
    BACKGROUND = 1
    NORMAL = 2
    PRIORITY = 3
    URGENT = 4
    CRITICAL = 5

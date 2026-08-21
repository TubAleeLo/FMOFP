"""
Radar Topic Registry

Defines the topic structure for all radar types.
Provides validation and lookup for radar topics.
"""

from typing import Dict, List
from ..radar_enums import (
    weather_radarMode,
    tfr_radarMode,
    sar_radarMode,
    targeting_radarMode,
    aewc_radarMode
)

# Topic registry for all radar types
RADAR_TOPIC_REGISTRY: Dict[str, Dict[str, List[str]]] = {
    'weather_radar': {
        'data_types': ['vil', 'precipitation', 'turbulence', 'echo_top', 'shear'],
        'commands': ['mode_change', 'status_update', 'calibration'],
        'events': ['alert', 'maintenance', 'data_ready', 'error']
    },
    'targeting_radar': {
        'data_types': ['track', 'search', 'lock', 'range', 'doppler'],
        'commands': ['mode_change', 'status_update', 'target_designation'],
        'events': ['target_acquired', 'track_lost', 'lock_achieved', 'error']
    },
    'sar_radar': {
        'data_types': ['stripmap', 'spotlight', 'scansar', 'terrain_map'],
        'commands': ['mode_change', 'status_update', 'resolution_change'],
        'events': ['image_ready', 'scan_complete', 'processing_status', 'error']
    },
    'aewc_radar': {
        'data_types': ['search', 'track', 'sector', 'elevation', 'classification'],
        'commands': ['mode_change', 'status_update', 'sector_select'],
        'events': ['target_detected', 'sector_scan_complete', 'track_update', 'error']
    },
    'tfr_radar': {
        'data_types': ['terrain', 'obstacle', 'profile', 'clearance'],
        'commands': ['mode_change', 'status_update', 'altitude_setting'],
        'events': ['terrain_warning', 'obstacle_detected', 'profile_update', 'error']
    }
}

# Radar modes mapping
RADAR_MODES = {
    'weather_radar': weather_radarMode,
    'targeting_radar': targeting_radarMode,
    'sar_radar': sar_radarMode,
    'aewc_radar': aewc_radarMode,
    'tfr_radar': tfr_radarMode
}

# Topic descriptions for documentation
TOPIC_DESCRIPTIONS = {
    'weather_radar': {
        'vil': 'Vertically Integrated Liquid data',
        'precipitation': 'Precipitation type and intensity',
        'turbulence': 'Atmospheric turbulence measurements',
        'echo_top': 'Cloud top height measurements',
        'shear': 'Wind shear detection data'
    },
    'targeting_radar': {
        'track': 'Target tracking data',
        'search': 'Search pattern data',
        'lock': 'Target lock status',
        'range': 'Target range information',
        'doppler': 'Doppler velocity data'
    },
    'sar_radar': {
        'stripmap': 'Strip mapping mode data',
        'spotlight': 'Spotlight mode imagery',
        'scansar': 'ScanSAR mode data',
        'terrain_map': 'Terrain mapping data'
    },
    'aewc_radar': {
        'search': 'Wide area search data',
        'track': 'Multiple target tracking',
        'sector': 'Sector scan data',
        'elevation': 'Target elevation data',
        'classification': 'Target classification data'
    },
    'tfr_radar': {
        'terrain': 'Terrain following data',
        'obstacle': 'Obstacle detection data',
        'profile': 'Terrain profile data',
        'clearance': 'Ground clearance data'
    }
}

def validate_topic(radar_type: str, topic: str) -> bool:
    """Validate if topic is valid for radar type.
    
    Args:
        radar_type (str): Type of radar
        topic (str): Topic to validate
        
    Returns:
        bool: True if topic is valid
    """
    if radar_type not in RADAR_TOPIC_REGISTRY:
        return False
        
    radar_topics = RADAR_TOPIC_REGISTRY[radar_type]
    return (topic in radar_topics['data_types'] or
            topic in radar_topics['commands'] or
            topic in radar_topics['events'])

def get_topic_description(radar_type: str, topic: str) -> str:
    """Get description for radar topic.
    
    Args:
        radar_type (str): Type of radar
        topic (str): Topic to get description for
        
    Returns:
        str: Topic description or empty string if not found
    """
    if radar_type not in TOPIC_DESCRIPTIONS:
        return ''
        
    return TOPIC_DESCRIPTIONS[radar_type].get(topic, '')

def get_radar_mode_enum(radar_type: str):
    """Get mode enum for radar type.
    
    Args:
        radar_type (str): Type of radar
        
    Returns:
        Enum: Radar mode enum class
        
    Raises:
        ValueError: If radar type not found
    """
    if radar_type not in RADAR_MODES:
        raise ValueError(f"Unknown radar type: {radar_type}")
        
    return RADAR_MODES[radar_type]

def get_all_topics(radar_type: str) -> List[str]:
    """Get all topics for radar type.
    
    Args:
        radar_type (str): Type of radar
        
    Returns:
        List[str]: List of all topics
        
    Raises:
        ValueError: If radar type not found
    """
    if radar_type not in RADAR_TOPIC_REGISTRY:
        raise ValueError(f"Unknown radar type: {radar_type}")
        
    radar_topics = RADAR_TOPIC_REGISTRY[radar_type]
    return (
        radar_topics['data_types'] +
        radar_topics['commands'] +
        radar_topics['events']
    )

"""
Radar Message Extractor

Extends the Universal Message Extractor with radar-specific field extraction logic.
Specialized handling for message formats in the radar system context, including
precipitation, VIL data, and mode changes.
"""

import sys
import os
import time
from typing import Dict, Any, List, Union, Optional

# Import the base class
from FMOFP.Utils.common.universal_message_extractor import UniversalMessageExtractor

# Import system logger
try:
    from FMOFP.Utils.logger.sys_logger import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logger = logging.getLogger('radar_message_extractor')

class RadarMessageExtractor(UniversalMessageExtractor):
    """
    Radar-specific message extractor with specialized handling for radar messages.
    Enhances the base extractor with radar-specific field processing and validation.
    """
    
    def __init__(self, radar_type='weather_radar', **kwargs):
        """
        Initialize radar-specific message extractor.
        
        Args:
            radar_type: Type of radar ('weather_radar', 'tfr_radar', etc.)
            **kwargs: Additional arguments for base class
        """
        super().__init__(**kwargs)
        self.radar_type = radar_type
        self.logger.info(f"RadarMessageExtractor initialized for {radar_type}")
    
    def _process_critical_fields(self, result):
        """
        Radar-specific processing for critical fields.
        
        Includes:
        - Radar-specific command_name normalization
        - Radar-specific message_type translation
        - Mode handling for radar messages
        - UUID preservation for reliable message tracking
        
        Args:
            result: Current result dictionary from base extractor
            
        Returns:
            dict: Result with radar-specific processing applied
        """
        # First apply base processing
        result = super()._process_critical_fields(result)
        
        # Ensure UUID fields are preserved in metadata for resilient tracking
        self._ensure_uuid_fields_in_metadata(result)
        
        # Set radar type if not already set
        if not result.get('radar_type'):
            result['radar_type'] = self.radar_type
            
        # Set source_system if not already set
        if not result.get('source_system'):
            result['source_system'] = 'radar_management'
        
        # Special handling for precipitation data
        if ('precipitation' in str(result.get('message_type', '')).lower() or 
            'precip' in str(result.get('command_type', '')).lower() or
            (result.get('command_name') and 'PRECIPITATION' in result['command_name'])):
            
            # Standardize fields for radar precipitation
            result['message_type'] = 'precipitation_data'
            result['command_type'] = 'precipitation_data'
            radar_type_upper = self.radar_type.upper()
            result['command_name'] = f"{radar_type_upper}_PRECIPITATION_DATA"
            
            # Flag for message routing
            result['is_precipitation_data'] = True
            result['data_type'] = 'precipitation'
            
            # Add to metadata for consistent access
            if 'metadata' in result and isinstance(result['metadata'], dict):
                result['metadata']['precipitation_data'] = True
                result['metadata']['data_type'] = 'precipitation'
                result['metadata']['command_name'] = result['command_name']
                
        # Special handling for VIL data
        elif ('vil' in str(result.get('message_type', '')).lower() or 
              'vil' in str(result.get('command_type', '')).lower() or
              (result.get('command_name') and 'VIL' in result['command_name'])):
            
            # Standardize fields for radar VIL
            result['message_type'] = 'vil_data'
            result['command_type'] = 'vil_data'
            radar_type_upper = self.radar_type.upper()
            result['command_name'] = f"{radar_type_upper}_VIL_DATA"
            
            # Flag for message routing
            result['is_vil_data'] = True
            result['data_type'] = 'vil'
            
            # Add to metadata for consistent access
            if 'metadata' in result and isinstance(result['metadata'], dict):
                result['metadata']['vil_data'] = True
                result['metadata']['data_type'] = 'vil'
                result['metadata']['command_name'] = result['command_name']
                
        # Special handling for mode change
        elif ('mode' in str(result.get('message_type', '')).lower() or 
              'mode' in str(result.get('command_type', '')).lower() or
              (result.get('command_name') and 'MODE' in result['command_name'])):
            
            # Standardize fields for mode change
            result['message_type'] = 'mode_change'
            result['command_type'] = 'mode_change'
            radar_type_upper = self.radar_type.upper()
            result['command_name'] = f"{radar_type_upper}_MODE_CHANGE"
            
            # Flag for message routing
            result['is_mode_change'] = True
            
            # Add to metadata for consistent access
            if 'metadata' in result and isinstance(result['metadata'], dict):
                result['metadata']['mode_change'] = True
                result['metadata']['data_type'] = 'mode'
                
                # Extract mode information if available
                if result.get('mode'):
                    result['metadata']['mode'] = result['mode']
                if result.get('mode_value'):
                    result['metadata']['mode_value'] = result['mode_value']
                    
        # Ensure radar destination is set
        if not result.get('destination') and not result.get('source_system'):
            result['destination'] = 'radar'
            
        # If this is a request message, ensure destination is set
        if 'request' in str(result.get('message_type', '')).lower():
            result['destination'] = 'radar'
            
        # If this is a response message, set source system
        if 'response' in str(result.get('message_type', '')).lower():
            result['source_system'] = 'radar_management'
            
        return result
    
    def _extract_radar_mode_data(self, message):
        """
        Extract radar mode data from messages.
        
        Specialized extraction for mode-related fields.
        
        Args:
            message: Message to extract mode data from
            
        Returns:
            dict: Mode data fields
        """
        mode_data = {}
        
        # Try to extract mode-specific fields
        if isinstance(message, dict):
            # Look for common mode field patterns
            if 'mode' in message:
                mode_data['mode'] = message['mode']
            elif 'radar_mode' in message:
                mode_data['mode'] = message['radar_mode']
            
            # Extract mode value if available
            if 'mode_value' in message:
                mode_data['mode_value'] = message['mode_value']
            elif 'value' in message:
                mode_data['mode_value'] = message['value']
                
            # Check for mode parameters
            if 'scan_parameters' in message:
                mode_data['scan_parameters'] = message['scan_parameters']
                
        elif hasattr(message, '__dict__'):
            # Extract from object attributes
            if hasattr(message, 'mode'):
                mode_data['mode'] = message.mode
            elif hasattr(message, 'radar_mode'):
                mode_data['mode'] = message.radar_mode
                
            # Extract mode value if available
            if hasattr(message, 'mode_value'):
                mode_data['mode_value'] = message.mode_value
            elif hasattr(message, 'value'):
                mode_data['mode_value'] = message.value
                
            # Check for scan parameters
            if hasattr(message, 'scan_parameters'):
                mode_data['scan_parameters'] = message.scan_parameters
        
        return mode_data
    
    def _ensure_uuid_fields_in_metadata(self, result):
        """
        Ensure all UUID fields are properly preserved in metadata.
        
        This is critical for tracking message flows across the system.
        
        Args:
            result: Result dictionary with fields to process
            
        Returns:
            dict: Result with UUID fields ensured in metadata
        """
        # Initialize metadata if not present
        if 'metadata' not in result or not result['metadata']:
            result['metadata'] = {}
            
        # List of UUID fields to check
        uuid_fields = ['message_uuid', 'request_uuid', 'query_uuid', 'status_uuid', 'command_uuid']
        
        # Copy all UUID fields to metadata
        for field in uuid_fields:
            if field in result and result[field]:
                result['metadata'][field] = result[field]
                self.logger.debug(f"[RADAR_EXTRACTOR] Preserved {field} in metadata: {result[field]}")
        
        # Ensure command_name is also preserved in metadata
        if result.get('command_name'):
            result['metadata']['command_name'] = result['command_name']
            self.logger.debug(f"[RADAR_EXTRACTOR] Preserved command_name in metadata: {result['command_name']}")
            
        # Ensure message_type is preserved in metadata
        if result.get('message_type'):
            result['metadata']['message_type'] = result['message_type']
            
        return result
    
    def extract_all_fields(self, message, current_level=0):
        """
        Enhanced field extraction for radar messages.
        
        Adds specialized handling for radar-specific message types.
        
        Args:
            message: Any message format
            current_level: Current nesting level
            
        Returns:
            dict: Complete extracted fields with radar-specific enhancements
        """
        # Safe handling for string frames (normalize to dict before specialized extraction)
        if isinstance(message, str):
            # Use base class to normalize string to dictionary - strictly preserving data
            message = super().extract_all_fields(message, current_level)

        # Special handling for mode change messages
        if isinstance(message, dict) and 'mode' in message:
            # First get base extraction
            result = super().extract_all_fields(message, current_level)
            
            # Extract specialized mode data
            mode_data = self._extract_radar_mode_data(message)
            if mode_data:
                result.update(mode_data)
                
                # Set mode-specific fields
                result['message_type'] = 'mode_change'
                result['command_type'] = 'mode_change'
                radar_type_upper = self.radar_type.upper()
                result['command_name'] = f"{radar_type_upper}_MODE_CHANGE"
                result['is_mode_change'] = True
                
            return result
            
        # Default to base implementation for other cases
        return super().extract_all_fields(message, current_level)

def get_radar_message_extractor(radar_type='weather_radar'):
    """Get a new instance of RadarMessageExtractor for the specified radar type."""
    return RadarMessageExtractor(radar_type=radar_type)

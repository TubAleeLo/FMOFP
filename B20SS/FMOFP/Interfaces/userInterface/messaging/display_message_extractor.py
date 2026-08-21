"""
Display Message Extractor

Extends the Universal Message Extractor with display-specific field extraction logic.
Specialized handling for message formats in the display system context.
Uses display-local message types and utilities for consistent message handling.
"""

import sys
import os
import time
import traceback
from typing import Dict, Any, List, Union, Optional

# Import the base class
from FMOFP.Utils.common.universal_message_extractor import UniversalMessageExtractor

# Import display-local modules
from .display_metadata_decoder import DisplayMetadataDecoder
from .display_message_types import (
    DISPLAY_VIL_DATA, DISPLAY_PRECIPITATION_DATA, DISPLAY_ECHO_TOP_DATA, DISPLAY_STORM_CELL_DATA,
    DISPLAY_COMMAND_TYPE_MODE, DISPLAY_COMMAND_TYPE_MODE_CHANGE, DISPLAY_COMMAND_TYPE_MODE_CHANGE_COMPLETE,
    get_message_type, is_vil_message, is_precipitation_message, is_mode_change_message,
    translate_message_type
)

# Import system logger
try:
    from Utils.logger.sys_logger import get_logger
    logger = get_logger()
except ImportError:
    import logging
    logger = logging.getLogger('display_message_extractor')

class DisplayMessageExtractor(UniversalMessageExtractor):
    """
    Display-specific message extractor with specialized handling for display messages.
    Enhances the base extractor with display-specific field processing and translation.
    Uses display-local message types and utilities for consistent message handling.
    """
    
    def __init__(self, **kwargs):
        """Initialize display-specific message extractor."""
        super().__init__(**kwargs)
        self.logger.info("DisplayMessageExtractor initialized")
    
    def _process_critical_fields(self, result):
        """
        Display-specific processing for critical fields.
        
        Enhances the base processing with special handling for:
        - Display-specific message type translation
        - Precipitation and VIL data processing
        - Display mode handling
        - UUID fields preservation
        - Command name standardization
        
        Args:
            result: Current result dictionary
            
        Returns:
            dict: Result with display-specific processing applied
        """
        try:
            # First apply base processing
            result = super()._process_critical_fields(result)
            
            # Display-specific message type translation using display_message_types utilities
            if result.get('message_type'):
                # Use centralized translate_message_type function
                original_type = result['message_type']
                result['message_type'] = translate_message_type(original_type)
                
                # Store original message type if different
                if original_type != result['message_type']:
                    result['original_message_type'] = original_type
                    self.logger.info(f"[DISPLAY_EXTRACTOR] Translated message_type: {original_type} -> {result['message_type']}")
                    
            # Ensure UUID fields are preserved in metadata for resilient tracking
            self._ensure_uuid_fields_in_metadata(result)
            
            # Use helper functions from display_message_types for message type detection
            # Special handling for precipitation data
            if is_precipitation_message(result):
                # Standardize fields for display precipitation using constants
                result['message_type'] = DISPLAY_PRECIPITATION_DATA
                result['command_type'] = 'precipitation_data'
                result['command_name'] = 'DISPLAY_PRECIPITATION_DATA'
                
                # Flag for display processing
                result['is_precipitation_data'] = True
                result['display_data_type'] = 'precipitation'
                
                # Add necessary metadata for display rendering
                if 'metadata' in result:
                    result['metadata']['display_data_type'] = 'precipitation'
                    result['metadata']['precipitation_data'] = True
                    
                self.logger.info(f"[DISPLAY_EXTRACTOR] Processed precipitation data message")
            
            # Special handling for VIL data
            elif is_vil_message(result):
                # Standardize fields for display VIL using constants
                result['message_type'] = DISPLAY_VIL_DATA
                result['command_type'] = 'vil_data'
                result['command_name'] = 'DISPLAY_VIL_DATA'
                
                # Flag for display processing
                result['is_vil_data'] = True
                result['display_data_type'] = 'vil'
                
                # Add necessary metadata for display rendering
                if 'metadata' in result:
                    result['metadata']['display_data_type'] = 'vil'
                    result['metadata']['vil_data'] = True
                    
                self.logger.info(f"[DISPLAY_EXTRACTOR] Processed VIL data message")
            
            # Special handling for mode changes
            elif is_mode_change_message(result):
                # Check if this is a mode completion message
                if 'completion' in str(result.get('message_type', '')).lower():
                    result['message_type'] = DISPLAY_COMMAND_TYPE_MODE_CHANGE_COMPLETE
                    result['command_type'] = DISPLAY_COMMAND_TYPE_MODE_CHANGE_COMPLETE
                    result['is_completion'] = True
                else:
                    result['message_type'] = DISPLAY_COMMAND_TYPE_MODE_CHANGE
                    result['command_type'] = DISPLAY_COMMAND_TYPE_MODE_CHANGE
                
                # Set appropriate command name based on radar type
                radar_type = result.get('radar_type', 'weather_radar').upper()
                result['command_name'] = f"{radar_type}_MODE_CHANGE"
                
                # Flag for display processing
                result['is_mode_change'] = True
                
                # Add necessary metadata for display mode change handling
                if 'metadata' in result:
                    result['metadata']['is_mode_change'] = True
                    if result.get('mode'):
                        result['metadata']['mode'] = result['mode']
                    if result.get('mode_value'):
                        result['metadata']['mode_value'] = result['mode_value']
                        
                self.logger.info(f"[DISPLAY_EXTRACTOR] Processed mode change message")
            
            # Ensure display destination is set
            if not result.get('destination'):
                result['destination'] = 'display'
                
            return result
            
        except Exception as e:
            self.logger.error(f"[DISPLAY_EXTRACTOR] Error processing critical fields: {str(e)}")
            self.logger.error(traceback.format_exc())
            # Return original result on error to avoid data loss
            return result
    
    def _extract_precipitation_data(self, message):
        """
        Extract precipitation data from display messages.
        
        Specialized extraction for precipitation data fields.
        
        Args:
            message: Message to extract precipitation data from
            
        Returns:
            dict: Precipitation data fields
        """
        try:
            precip_data = {}
            
            # Try to extract precipitation-specific fields
            if isinstance(message, dict):
                # Look for common precipitation field patterns
                if 'precipitation_data' in message:
                    precip_data['data'] = message['precipitation_data']
                elif 'precipitation' in message:
                    precip_data['data'] = message['precipitation']
                elif 'precip_points' in message:
                    precip_data['data'] = message['precip_points']
                
                # Extract metadata fields
                if 'scan_parameters' in message:
                    precip_data['scan_parameters'] = message['scan_parameters']
                    
                # Check for range/angle data
                for field in ['range_start', 'range_end', 'azimuth', 'elevation']:
                    if field in message:
                        precip_data[field] = message[field]
                    
            elif hasattr(message, '__dict__'):
                # Extract from object attributes
                if hasattr(message, 'precipitation_data'):
                    precip_data['data'] = message.precipitation_data
                elif hasattr(message, 'precipitation'):
                    precip_data['data'] = message.precipitation
                elif hasattr(message, 'precip_points'):
                    precip_data['data'] = message.precip_points
                    
                # Extract scan parameters if available
                if hasattr(message, 'scan_parameters'):
                    precip_data['scan_parameters'] = message.scan_parameters
                    
                # Check for range/angle data
                for attr in ['range_start', 'range_end', 'azimuth', 'elevation']:
                    if hasattr(message, attr):
                        precip_data[attr] = getattr(message, attr)
            
            # Log extraction results
            if 'data' in precip_data:
                data_len = len(precip_data['data']) if isinstance(precip_data['data'], list) else 1
                self.logger.info(f"[DISPLAY_EXTRACTOR] Extracted {data_len} precipitation data points")
            
            return precip_data
            
        except Exception as e:
            self.logger.error(f"[DISPLAY_EXTRACTOR] Error extracting precipitation data: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {}
    
    def _extract_vil_data(self, message):
        """
        Extract VIL data from display messages.
        
        Specialized extraction for VIL data fields.
        
        Args:
            message: Message to extract VIL data from
            
        Returns:
            dict: VIL data fields
        """
        try:
            vil_data = {}
            
            # Try to extract VIL-specific fields
            if isinstance(message, dict):
                # Look for common VIL field patterns
                if 'vil_data' in message:
                    vil_data['data'] = message['vil_data']
                elif 'vil' in message:
                    vil_data['data'] = message['vil']
                elif 'vil_points' in message:
                    vil_data['data'] = message['vil_points']
                
                # Extract metadata fields
                if 'scan_parameters' in message:
                    vil_data['scan_parameters'] = message['scan_parameters']
                    
                # Check for range/angle data
                for field in ['range_start', 'range_end', 'azimuth', 'elevation']:
                    if field in message:
                        vil_data[field] = message[field]
                    
            elif hasattr(message, '__dict__'):
                # Extract from object attributes
                if hasattr(message, 'vil_data'):
                    vil_data['data'] = message.vil_data
                elif hasattr(message, 'vil'):
                    vil_data['data'] = message.vil
                elif hasattr(message, 'vil_points'):
                    vil_data['data'] = message.vil_points
                    
                # Extract scan parameters if available
                if hasattr(message, 'scan_parameters'):
                    vil_data['scan_parameters'] = message.scan_parameters
                    
                # Check for range/angle data
                for attr in ['range_start', 'range_end', 'azimuth', 'elevation']:
                    if hasattr(message, attr):
                        vil_data[attr] = getattr(message, attr)
            
            # Log extraction results
            if 'data' in vil_data:
                data_len = len(vil_data['data']) if isinstance(vil_data['data'], list) else 1
                self.logger.info(f"[DISPLAY_EXTRACTOR] Extracted {data_len} VIL data points")
            
            return vil_data
            
        except Exception as e:
            self.logger.error(f"[DISPLAY_EXTRACTOR] Error extracting VIL data: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {}
        
    def _ensure_uuid_fields_in_metadata(self, result):
        """
        Ensure all UUID fields are properly preserved in metadata.
        
        This is critical for tracking message flows across the system.
        
        Args:
            result: Result dictionary with fields to process
            
        Returns:
            dict: Result with UUID fields ensured in metadata
        """
        try:
            # Initialize metadata if not present
            if 'metadata' not in result or not result['metadata']:
                result['metadata'] = {}
                
            # List of UUID fields to check
            uuid_fields = ['message_uuid', 'request_uuid', 'query_uuid', 'status_uuid', 'command_uuid', 'request_id']
            
            # Copy all UUID fields to metadata
            for field in uuid_fields:
                if field in result and result[field]:
                    result['metadata'][field] = result[field]
                    self.logger.debug(f"[DISPLAY_EXTRACTOR] Preserved {field} in metadata: {result[field]}")
            
            # Ensure command_name is also preserved in metadata
            if result.get('command_name'):
                result['metadata']['command_name'] = result['command_name']
                self.logger.debug(f"[DISPLAY_EXTRACTOR] Preserved command_name in metadata: {result['command_name']}")
                
            # Ensure message_type is preserved in metadata
            if result.get('message_type'):
                result['metadata']['message_type'] = result['message_type']
                
            # Ensure command_type is preserved in metadata
            if result.get('command_type'):
                result['metadata']['command_type'] = result['command_type']
                
            return result
            
        except Exception as e:
            self.logger.error(f"[DISPLAY_EXTRACTOR] Error ensuring UUID fields in metadata: {str(e)}")
            self.logger.error(traceback.format_exc())
            return result
        
    def extract_all_fields(self, message, current_level=0):
        """
        Enhanced field extraction for display messages.
        
        Adds specialized handling for precipitation and VIL data in display context.
        Uses display-local message types and constants for consistent handling.
        
        Args:
            message: Any message format
            current_level: Current nesting level
            
        Returns:
            dict: Complete extracted fields with display-specific enhancements
        """
        try:
            # Safe handling for string frames (normalize to dict before specialized extraction)
            if isinstance(message, str):
                # Use base class to normalize string to dictionary
                message = super().extract_all_fields(message, current_level)
            
            # Use helper functions from display_message_types for message type detection
            # Special handling for precipitation data
            if isinstance(message, dict) and any(
                precip_key in message for precip_key in 
                ['precipitation_data', 'precipitation', 'precip_points']):
                
                result = super().extract_all_fields(message, current_level)
                
                # Extract specialized precipitation data
                precip_data = self._extract_precipitation_data(message)
                if precip_data:
                    result.update(precip_data)
                    
                    # Set precipitation-specific fields using constants
                    result['message_type'] = DISPLAY_PRECIPITATION_DATA
                    result['command_type'] = 'precipitation_data'
                    result['command_name'] = 'DISPLAY_PRECIPITATION_DATA'
                    result['is_precipitation_data'] = True
                    
                return result
                
            # Special handling for VIL data
            elif isinstance(message, dict) and any(
                vil_key in message for vil_key in 
                ['vil_data', 'vil', 'vil_points']):
                
                result = super().extract_all_fields(message, current_level)
                
                # Extract specialized VIL data
                vil_data = self._extract_vil_data(message)
                if vil_data:
                    result.update(vil_data)
                    
                    # Set VIL-specific fields using constants
                    result['message_type'] = DISPLAY_VIL_DATA
                    result['command_type'] = 'vil_data'
                    result['command_name'] = 'DISPLAY_VIL_DATA'
                    result['is_vil_data'] = True
                    
                return result
                
            # Default to base implementation for other cases
            return super().extract_all_fields(message, current_level)
            
        except Exception as e:
            self.logger.error(f"[DISPLAY_EXTRACTOR] Error in extract_all_fields: {str(e)}")
            self.logger.error(traceback.format_exc())
            # Return a basic dictionary with error information to avoid complete failure
            if isinstance(message, dict):
                # Return original message with error flag
                message['extraction_error'] = str(e)
                return message
            else:
                # Create a new dictionary with error information
                return {
                    'extraction_error': str(e),
                    'message_type': 'error',
                    'original_message': str(message)[:100] + '...' if isinstance(message, str) and len(str(message)) > 100 else str(message)
                }

def get_display_message_extractor():
    """Get a new instance of DisplayMessageExtractor."""
    return DisplayMessageExtractor()

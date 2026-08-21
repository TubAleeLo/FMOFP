"""
Flight Management System Message Processor

Responsible for processing messages received by the FMS
and dispatching them to the appropriate handling logic.
"""

import logging
import traceback
from typing import Dict, Any, Optional, Union

from FMOFP.Utils.logger.sys_logger import get_logger
# Import the FMSCompletionMessageHandler for sending completion notifications
from FMOFP.Systems.flightManagementSys.fms_messaging.completion_message_handler import get_fms_completion_message_handler
# Import the FCS message types
from FMOFP.Systems.flightManagementSys.fms_messaging.message_types import (
    is_control_input_message,
    is_orientation_data_message,
    COMMAND_TYPE_CONTROL_INPUT,
    COMMAND_TYPE_ORIENTATION_DATA
)

logger = get_logger()

class FMSMessageProcessor:
    """
    Processes messages for the Flight Management System
    
    This class handles the actual processing of messages that have
    been received by the FlightManagementSystem class. It dispatches
    messages to appropriate handling methods based on message type.
    """
    
    def __init__(self, fms_instance):
        """
        Initialize with a reference to the FMS instance
        
        Args:
            fms_instance: The FlightManagementSystem instance to operate on
        """
        self.fms = fms_instance
    
    def process_message(self, message: Dict[str, Any]) -> bool:
        """
        Process a message received by the FMS
        
        Args:
            message: The message to process
            
        Returns:
            bool: True if processing was successful, False otherwise
        """
        try:
            # Log the received message
            logger.debug(f"[FMS_PROC] Processing message: {message}")
            
            # Check for MIL-STD-1553B message format
            if isinstance(message, dict) and message.get('message_type') == 'flightManagementSystemCommand':
                return self._process_1553b_message(message)
            
            # Otherwise try traditional message format
            return self._process_traditional_message(message)
            
        except Exception as e:
            logger.error(f"[FMS_PROC] Error processing message: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _process_1553b_message(self, message: Dict[str, Any]) -> bool:
        """
        Process a MIL-STD-1553B formatted message
        
        Args:
            message: The message to process
            
        Returns:
            bool: True if processing was successful, False otherwise
        """
        try:
            # Extract command information
            command_type = message.get('command_type', '')
            command_name = message.get('command_name', '')
            data = message.get('data', '')
            
            logger.info(f"[FMS_PROC] Processing 1553B message - command_type: {command_type}, command_name: {command_name}")
            
            # Handle different command types
            if command_type == 'mode_change':
                return self._handle_mode_change(message)
            elif command_type == 'status_request':
                return self._handle_status_request(message)
            elif command_type == 'data_request':
                return self._handle_data_request(message)
            elif command_type == COMMAND_TYPE_CONTROL_INPUT:
                return self._handle_control_input(message)
            elif command_type == COMMAND_TYPE_ORIENTATION_DATA:
                return self._handle_orientation_data_request(message)
            else:
                logger.warning(f"[FMS_PROC] Unknown command type: {command_type}")
                return False
                
        except Exception as e:
            logger.error(f"[FMS_PROC] Error processing 1553B message: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _process_traditional_message(self, message: Dict[str, Any]) -> bool:
        """
        Process a traditional message format
        
        Args:
            message: The message to process
            
        Returns:
            bool: True if processing was successful, False otherwise
        """
        try:
            # Extract message type and payload
            message_type = message.get('message_type', '')
            payload = message.get('data', {})
            
            logger.info(f"[FMS_PROC] Processing traditional message - type: {message_type}")
            
            # Handle different message types
            if message_type == 'FMS_SET_MODE':
                return self._handle_set_mode(payload)
            elif message_type == 'FMS_SET_FLIGHT_PARAMETERS':
                return self._handle_set_flight_parameters(payload)
            elif message_type == 'FMS_ADD_WAYPOINT':
                return self._handle_add_waypoint(payload)
            elif message_type == 'FMS_ACTIVATE_WAYPOINT':
                return self._handle_activate_waypoint(payload)
            # Handle FCS message types
            elif message_type == 'flight_control_systemCommand':
                logger.info(f"[FMS_PROC] Processing flight_control_systemCommand message")
                command_type = message.get('command_type', '')
                
                if command_type == 'mode_change':
                    return self._handle_fcs_mode_change(message)
                elif is_control_input_message(message):
                    return self._handle_control_input(message)
                else:
                    # Forward to FCS through FMS
                    if self.fms.flight_control_system:
                        logger.info(f"[FMS_PROC] Forwarding flight_control_systemCommand to FCS")
                        return self.fms.flight_control_system.receive_message(message)
                    else:
                        logger.warning(f"[FMS_PROC] Flight Control System not initialized")
                        return False
            elif is_control_input_message(message):
                return self._handle_control_input(message)
            elif is_orientation_data_message(message):
                return self._handle_orientation_data_request(message)
            else:
                logger.warning(f"[FMS_PROC] Unknown message type: {message_type}")
                return False
                
        except Exception as e:
            logger.error(f"[FMS_PROC] Error processing traditional message: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _send_mode_change_completion(self, old_mode: str, new_mode: str, mode_value: int = None, request_id: str = None) -> bool:
        """
        Send mode change completion notification to display system.
        
        This is critical for proper synchronization between FMS and display systems.
        According to MIL-STD-1553B protocol, this separate completion message ensures
        that the display system knows when the FMS has actually completed the mode change,
        rather than just acknowledging receipt of the command.
        
        Args:
            old_mode: The previous FMS mode
            new_mode: The new FMS mode
            mode_value: The mode value (optional)
            request_id: The original request ID to include in the completion message
            
        Returns:
            bool: True if the notification was sent successfully, False otherwise
        """
        try:
            # Get the FMSCompletionMessageHandler instance
            completion_handler = get_fms_completion_message_handler()
            
            # Log the mode change completion notification
            logger.info(f"[FMS_PROC] Sending mode change completion notification: {old_mode} -> {new_mode}")
            
            # Determine mode value if not provided
            if mode_value is None and new_mode:
                # Map mode name to value
                mode_map = {"NORMAL": 0, "COMBAT": 1, "STEALTH": 2, "TRAINING": 3, "EMERGENCY": 4}
                mode_value = mode_map.get(new_mode, 0)
            
            # Send the mode change completion message
            success = completion_handler.send_mode_change_completion(
                system_name='flightmanagementsystem',
                old_mode=old_mode,
                new_mode=new_mode,
                mode_value=mode_value,
                request_id=request_id
            )
            
            if success:
                logger.info(f"[FMS_PROC] Mode change completion notification sent successfully")
            else:
                logger.error(f"[FMS_PROC] Failed to send mode change completion notification")
                
            return success
                
        except Exception as e:
            logger.error(f"[FMS_PROC] Error sending mode change completion: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _handle_mode_change(self, message: Dict[str, Any]) -> bool:
        """
        Handle a mode change command
        
        Args:
            message: The mode change message
            
        Returns:
            bool: True if mode change was successful, False otherwise
        """
        try:
            logger.info(f"[FMS_PROC] Detected mode change message")
            
            # Get current mode before change (for completion message)
            old_mode = self.fms.tactical['mode'] if hasattr(self.fms, 'tactical') else "NORMAL"
            logger.info(f"[FMS_PROC] Current mode before change: {old_mode}")
            
            # Extract request ID from message for completion notification
            request_id = message.get('request_id')
            logger.debug(f"[FMS_PROC] Extracted request ID: {request_id}")
            
            # Extract mode data
            data = message.get('data', '')
            mode_value = None
            mode = None
            
            # Extract mode value from binary data
            if isinstance(data, str) and all(c in '01' for c in data):
                # Convert binary string to integer
                try:
                    # Handle binary string format (common in 1553B messages)
                    mode_bytes = bytes([int(data[i:i+8], 2) for i in range(0, len(data), 8)])
                    mode_value = int.from_bytes(mode_bytes, byteorder='big')
                    
                    # Map mode value to mode name
                    mode_map = {0: "NORMAL", 1: "COMBAT", 2: "STEALTH", 3: "TRAINING", 4: "EMERGENCY"}
                    mode = mode_map.get(mode_value, "NORMAL")
                    
                    logger.info(f"[FMS_PROC] Setting mode from binary data to: {mode}")
                    result = self.fms.set_mode(mode)
                    
                    if result:
                        # Log mode change completion
                        logger.info(f"[FMS_PROC] FMS mode changed from {old_mode} to {mode}")
                        
                        # Send mode change completion notification
                        self._send_mode_change_completion(old_mode, mode, mode_value, request_id)
                    
                    return result
                except Exception as e:
                    logger.error(f"[FMS_PROC] Error processing binary mode data: {e}")
                    return False
            
            # Try to get mode from other message formats
            if isinstance(message, dict):
                # Try to extract mode from various possible locations
                if 'mode' in message:
                    mode = message['mode']
                elif 'mode_name' in message:
                    mode = message['mode_name']
                elif isinstance(message.get('parameters'), dict):
                    params = message['parameters']
                    if 'mode' in params:
                        mode = params['mode']
                    elif 'mode_name' in params:
                        mode = params['mode_name']
                
                if mode:
                    logger.info(f"[FMS_PROC] Setting mode from message fields: {mode}")
                    result = self.fms.set_mode(mode)
                    
                    if result:
                        # Log mode change completion
                        logger.info(f"[FMS_PROC] FMS mode changed from {old_mode} to {mode}")
                        
                        # Send mode change completion notification
                        self._send_mode_change_completion(old_mode, mode, None, request_id)
                    
                    return result
            
            logger.warning(f"[FMS_PROC] Could not determine mode from message: {message}")
            return False
            
        except Exception as e:
            logger.error(f"[FMS_PROC] Error handling mode change: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _handle_status_request(self, message: Dict[str, Any]) -> bool:
        """
        Handle a status request command
        
        Args:
            message: The status request message
            
        Returns:
            bool: True if status request was handled, False otherwise
        """
        # Status requests don't need to change state, just log and return success
        logger.info(f"[FMS_PROC] Processing status request")
        return True
    
    def _handle_data_request(self, message: Dict[str, Any]) -> bool:
        """
        Handle a data request command
        
        Args:
            message: The data request message
            
        Returns:
            bool: True if data request was handled, False otherwise
        """
        # Data requests don't need to change state, just log and return success
        logger.info(f"[FMS_PROC] Processing data request")
        return True
    
    def _handle_set_mode(self, payload: Dict[str, Any]) -> bool:
        """
        Handle a set mode message
        
        Args:
            payload: The message payload
            
        Returns:
            bool: True if mode was set successfully, False otherwise
        """
        try:
            # Get current mode before change (for completion message)
            old_mode = self.fms.tactical['mode'] if hasattr(self.fms, 'tactical') else "NORMAL"
            
            # Extract mode from payload
            mode = payload.get('mode', '')
            
            if not mode:
                logger.warning(f"[FMS_PROC] No mode specified in payload: {payload}")
                return False
            
            logger.info(f"[FMS_PROC] Setting mode to: {mode}")
            result = self.fms.set_mode(mode)
            
            if result:
                # Log mode change completion
                logger.info(f"[FMS_PROC] FMS mode changed from {old_mode} to {mode}")
                
                # Send mode change completion notification
                self._send_mode_change_completion(old_mode, mode)
            
            return result
            
        except Exception as e:
            logger.error(f"[FMS_PROC] Error handling activate waypoint: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _handle_control_input(self, message: Dict[str, Any]) -> bool:
        """
        Handle a flight control input message.
        
        Args:
            message: The control input message
            
        Returns:
            bool: True if control input was handled, False otherwise
        """
        try:
            logger.info(f"[FMS_PROC] Processing flight control input message")
            
            # Extract request ID for completion notification
            request_id = message.get('request_id')
            
            # Ensure FCS is initialized in the FMS
            if not hasattr(self.fms, 'flight_control_system') or self.fms.flight_control_system is None:
                logger.error(f"[FMS_PROC] Flight Control System not initialized")
                return False
            
            # Extract control type and value
            control_type = None
            value = None
            
            # Try to get from data field
            if isinstance(message.get('data'), list) and len(message.get('data', [])) >= 2:
                data = message.get('data')
                # First word might be control type encoded as integer
                control_word = data[0]
                value_word = data[1]
                
                # Map integer control word to control type if needed
                if isinstance(control_word, int):
                    if control_word == 1:
                        control_type = 'aileron'
                    elif control_word == 2:
                        control_type = 'elevator'
                    elif control_word == 3:
                        control_type = 'rudder'
                    elif control_word == 4:
                        control_type = 'throttle'
                elif isinstance(control_word, str):
                    control_type = control_word
                
                # Convert value word to float if needed
                if isinstance(value_word, (int, float)):
                    value = float(value_word)
                    # Scale integer values from 16-bit signed range to -1.0 to 1.0
                    if isinstance(value_word, int) and abs(value_word) > 1:
                        if value_word > 32767:  # Handle unsigned to signed conversion
                            value_word = value_word - 65536
                        value = value_word / 32767.0
                elif isinstance(value_word, str):
                    try:
                        value = float(value_word)
                    except ValueError:
                        logger.warning(f"[FMS_PROC] Invalid value in control input: {value_word}")
            
            # Try to get from message fields
            if control_type is None and 'control_type' in message:
                control_type = message['control_type']
            if value is None and 'value' in message:
                value = message['value']
            
            # Check if we have the required data
            if control_type is None or value is None:
                logger.warning(f"[FMS_PROC] Missing control_type or value in control input message: {message}")
                return False
            
            logger.info(f"[FMS_PROC] Setting flight control input: {control_type} = {value}")
            
            # Forward control input to FCS
            return self.fms.flight_control_system.set_control_input(
                control_type, value, send_completion=True, request_id=request_id
            )
            
        except Exception as e:
            logger.error(f"[FMS_PROC] Error handling control input: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _handle_orientation_data_request(self, message: Dict[str, Any]) -> bool:
        """
        Handle an orientation data request message.
        
        Args:
            message: The orientation data request message
            
        Returns:
            bool: True if orientation data request was handled, False otherwise
        """
        try:
            logger.info(f"[FMS_PROC] Processing orientation data request message")
            
            # Ensure FCS is initialized in the FMS
            if not hasattr(self.fms, 'flight_control_system') or self.fms.flight_control_system is None:
                logger.error(f"[FMS_PROC] Flight Control System not initialized")
                return False
            
            # Forward request to FCS to send orientation data
            return self.fms.flight_control_system.send_orientation_data()
            
        except Exception as e:
            logger.error(f"[FMS_PROC] Error handling orientation data request: {str(e)}")
            logger.error(traceback.format_exc())
            return False
            
    def _handle_fcs_mode_change(self, message: Dict[str, Any]) -> bool:
        """
        Handle a Flight Control System mode change command.
        
        Args:
            message: The FCS mode change message
            
        Returns:
            bool: True if FCS mode change was successful, False otherwise
        """
        try:
            logger.info(f"[FMS_PROC] Processing FCS mode change message")
            
            # Ensure FCS is initialized in the FMS
            if not hasattr(self.fms, 'flight_control_system') or self.fms.flight_control_system is None:
                logger.error(f"[FMS_PROC] Flight Control System not initialized")
                return False
            
            # Extract request ID from message for completion notification
            request_id = message.get('request_id')
            
            # Extract mode data
            mode = None
            
            # Try to get mode from message
            if isinstance(message, dict):
                # Dump the full message for debugging
                logger.info(f"[FMS_PROC] Full message content: {message}")
                
                if 'mode' in message:
                    mode = message['mode']
                    logger.info(f"[FMS_PROC] Found mode directly in message: {mode}")
                elif 'data' in message:
                    data = message['data']
                    logger.info(f"[FMS_PROC] Examining data field: {data} (type: {type(data)})")
                    
                    if isinstance(data, str):
                        # Check if it's a binary string (common in 1553B messages)
                        if all(c in '01' for c in data):
                            try:
                                # Convert binary string to integer
                                # For single binary string with 16 bits
                                mode_value = int(data, 2)
                                logger.info(f"[FMS_PROC] Converted binary data {data} to value: {mode_value}")
                                
                                # Debug the conversion to help troubleshoot
                                logger.info(f"[FMS_PROC] Binary data: {data}, length: {len(data)}")
                                logger.info(f"[FMS_PROC] Binary value as int: {mode_value}")
                                
                                # Map mode value to name - correctly align with FCS definitions
                                mode_map = {
                                    0: "NORMAL",
                                    1: "COMBAT",
                                    2: "PRECISION",
                                    3: "AUTOPILOT",
                                    4: "TERRAIN",
                                    5: "EMERGENCY"
                                }
                                mode = mode_map.get(mode_value, "NORMAL")
                                logger.info(f"[FMS_PROC] Mapped value {mode_value} to mode: {mode}")
                            except ValueError as e:
                                logger.warning(f"[FMS_PROC] Could not convert binary data: {e}")
                        else:
                            logger.info(f"[FMS_PROC] Data not in binary format: {data}")
                            mode = data
                    elif isinstance(data, list) and len(data) > 0:
                        logger.info(f"[FMS_PROC] Data is a list with {len(data)} items")
                        mode_data = data[0]
                        logger.info(f"[FMS_PROC] First item in data list: {mode_data} (type: {type(mode_data)})")
                        
                        if isinstance(mode_data, str):
                            # Check if it's a binary string
                            if all(c in '01' for c in mode_data):
                                try:
                                    mode_value = int(mode_data, 2)
                                    logger.info(f"[FMS_PROC] Converted binary item {mode_data} to value: {mode_value}")
                                    
                                    # Use correctly aligned mode map
                                    mode_map = {
                                        0: "NORMAL", 
                                        1: "COMBAT",
                                        2: "PRECISION",
                                        3: "AUTOPILOT",
                                        4: "TERRAIN",
                                        5: "EMERGENCY"
                                    }
                                    mode = mode_map.get(mode_value, "NORMAL")
                                except ValueError:
                                    mode = mode_data
                            else:
                                mode = mode_data
                        elif isinstance(mode_data, int):
                            # Map integer to mode
                            logger.info(f"[FMS_PROC] Mode data is an integer: {mode_data}")
                            mode_map = {
                                0: "NORMAL", 
                                1: "COMBAT",
                                2: "PRECISION",
                                3: "AUTOPILOT",
                                4: "TERRAIN",
                                5: "EMERGENCY"
                            }
                            mode = mode_map.get(mode_data, "NORMAL")
                            logger.info(f"[FMS_PROC] Mapped integer {mode_data} to mode: {mode}")
            
            # Check if we can directly extract mode from the data field if mode is still None
            if not mode and 'data' in message and isinstance(message['data'], str):
                data = message['data']
                logger.info(f"[FMS_PROC] Attempting direct binary data extraction from data field: {data}")
                try:
                    # Direct binary string conversion - used when receiving from message handler
                    if all(c in '01' for c in data):
                        mode_value = int(data, 2)
                        logger.info(f"[FMS_PROC] Directly converted binary data {data} to value: {mode_value}")
                        
                        # Map mode value to mode name - use FCS definitions
                        mode_map = {
                            0: "NORMAL", 
                            1: "COMBAT",
                            2: "PRECISION",
                            3: "AUTOPILOT",
                            4: "TERRAIN",
                            5: "EMERGENCY"
                        }
                        mode = mode_map.get(mode_value, "NORMAL")
                        logger.info(f"[FMS_PROC] Directly mapped value {mode_value} to mode: {mode}")
                except ValueError as e:
                    logger.warning(f"[FMS_PROC] Could not convert binary data directly: {e}")
                
            if not mode:
                logger.warning(f"[FMS_PROC] Could not determine FCS mode from message: {message}")
                return False
            
            # Set the FCS mode
            logger.info(f"[FMS_PROC] Setting FCS mode to: {mode}")
            return self.fms.flight_control_system.set_mode(mode, send_completion=True, request_id=request_id)
            
        except Exception as e:
            logger.error(f"[FMS_PROC] Error handling FCS mode change: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _handle_set_flight_parameters(self, payload: Dict[str, Any]) -> bool:
        """
        Handle a set flight parameters message
        
        Args:
            payload: The message payload
            
        Returns:
            bool: True if parameters were set successfully, False otherwise
        """
        try:
            # Extract parameters from payload
            parameters = payload.get('parameters', {})
            
            logger.info(f"[FMS_PROC] Setting flight parameters")
            self.fms.set_flight_parameters(parameters)
            return True
            
        except Exception as e:
            logger.error(f"[FMS_PROC] Error handling set flight parameters: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _handle_add_waypoint(self, payload: Dict[str, Any]) -> bool:
        """
        Handle an add waypoint message
        
        Args:
            payload: The message payload
            
        Returns:
            bool: True if waypoint was added successfully, False otherwise
        """
        try:
            # Extract waypoint parameters from payload
            name = payload.get('name', f'WP{len(self.fms.navigation["waypoints"])}')
            latitude = payload.get('latitude', 0)
            longitude = payload.get('longitude', 0)
            altitude = payload.get('altitude', self.fms.navigation['altitude'])
            waypoint_type = payload.get('type', 'NORMAL')
            
            logger.info(f"[FMS_PROC] Adding waypoint: {name}")
            return self.fms.add_waypoint(name, latitude, longitude, altitude, waypoint_type)
            
        except Exception as e:
            logger.error(f"[FMS_PROC] Error handling add waypoint: {str(e)}")
            logger.error(traceback.format_exc())
            return False
    
    def _handle_activate_waypoint(self, payload: Dict[str, Any]) -> bool:
        """
        Handle an activate waypoint message
        
        Args:
            payload: The message payload
            
        Returns:
            bool: True if waypoint was activated successfully, False otherwise
        """
        try:
            # Extract waypoint ID from payload
            waypoint_id = payload.get('waypoint_id', 0)
            
            logger.info(f"[FMS_PROC] Activating waypoint: {waypoint_id}")
            return self.fms.activate_waypoint(waypoint_id)
            
        except Exception as e:
            logger.error(f"[FMS_PROC] Error handling activate waypoint: {str(e)}")
            logger.error(traceback.format_exc())
            return False

# Singleton instance
_fms_message_processor = None

def get_fms_message_processor(fms_instance=None):
    """
    Get singleton instance of FMS Message Processor
    
    Args:
        fms_instance: Optional FMS instance to use
        
    Returns:
        FMSMessageProcessor: The singleton instance
    """
    global _fms_message_processor
    if _fms_message_processor is None and fms_instance is not None:
        _fms_message_processor = FMSMessageProcessor(fms_instance)
    return _fms_message_processor

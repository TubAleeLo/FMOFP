"""
Display Outgoing Router

Handles messages that are ready for final delivery to the display system.
Prevents routing loops by bypassing special case handlers for processed messages.
Uses MIL-STD-1553B messaging protocol to send messages directly to the display system.
"""

import traceback
import asyncio
import time
import uuid
from typing import Dict, Any, Union

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.MIL_STD_1553B.Messaging import send1553Msg
from FMOFP.local_messaging.routing.handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
from FMOFP.local_messaging.radar_display_modes import RadarDisplayMode
from FMOFP.local_messaging.routing.message_transformations import (
    transform_message, get_message_type
)

logger = get_logger()

class DisplayOutgoingRouter:
    # Constants for message types - matching DisplayMessageHandler    # We are in the local system and should be importing from the expect
    SHOW_COMMAND = 0x01
    MODE_COMMAND = 0x02
    DATA_COMMAND = 0x03
    
    def __init__(self):
        self.logger = get_logger()
        self.sendMsg = send1553Msg()  # Initialize the send1553Msg instance
        self.display_handler = None   # Will be initialized on first use
        
        # Get DisplayResponseService
        from FMOFP.local_messaging.routing.response_services.system_response_services.DisplayResponseService import get_display_response_service
        self.response_service = get_display_response_service()
        
        logger.info("DisplayOutgoingRouter initialized with MIL-STD-1553B messaging capability")
        
    def route_message(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Route a message directly to the display system based on command type.
        
        Args:
            message: The message to route
            
        Returns:
            bool: True if the message was routed successfully, False otherwise
        """
        try:
            # Log the message being routed
            self.logger.info(f"[LOCAL_DISP_OUTGOING] Routing message to display system")
            
            # Convert message to dictionary if needed
            message_dict = message
            if not isinstance(message, dict):
                message_dict = {}
                for attr in dir(message):
                    if not attr.startswith('_') and not callable(getattr(message, attr)):
                        message_dict[attr] = getattr(message, attr)
            
            # Get message type and command type for routing
            message_type = message_dict.get('message_type')
            command_type = message_dict.get('command_type')
            
            self.logger.info(f"[LOCAL_DISP_OUTGOING] Message type: {message_type}, Command type: {command_type}")
            
            # Route based on command type - this is the primary routing mechanism
            if command_type == 'precipitation_data':
                self.logger.warning(f"[LOCAL_DISP_OUTGOING] Routing precipitation data message")
                # Create a task for the async method and add a callback to handle the result
                loop = asyncio.get_event_loop()
                task = loop.create_task(self._route_precipitation_data(message))
                
                # Add a callback to handle the result
                def handle_result(future):
                    try:
                        result = future.result()
                        if result:
                            self.logger.warning(f"[LOCAL_DISP_OUTGOING] Successfully routed precipitation data")
                        else:
                            self.logger.error(f"[LOCAL_DISP_OUTGOING] Failed to route precipitation data")
                    except Exception as e:
                        self.logger.error(f"[LOCAL_DISP_OUTGOING] Error in precipitation data routing: {e}")
                        self.logger.error(traceback.format_exc())
                
                # Add the callback
                task.add_done_callback(handle_result)
                return True
            elif message_type == 'weather_radarPrecipitationResponse':
                self.logger.warning(f"[LOCAL_DISP_OUTGOING] Routing precipitation response message")
                # Create a task for the async method and add a callback to handle the result
                loop = asyncio.get_event_loop()
                task = loop.create_task(self._route_precipitation_data(message))
                
                # Add a callback to handle the result
                def handle_result(future):
                    try:
                        result = future.result()
                        if result:
                            self.logger.warning(f"[LOCAL_DISP_OUTGOING] Successfully routed precipitation response")
                        else:
                            self.logger.error(f"[LOCAL_DISP_OUTGOING] Failed to route precipitation response")
                    except Exception as e:
                        self.logger.error(f"[LOCAL_DISP_OUTGOING] Error in precipitation response routing: {e}")
                        self.logger.error(traceback.format_exc())
                
                # Add the callback
                task.add_done_callback(handle_result)
                return True
                
            elif command_type == 'vil_data' or (message_type and 'vil' in message_type.lower() and 'precipitation' not in message_type.lower()):
                self.logger.info(f"[LOCAL_DISP_OUTGOING] Routing VIL data message")
                return self._route_vil_data(message)
                
            elif command_type == 'mode_change' or command_type == 'mode_change_completion':
                self.logger.info(f"[LOCAL_DISP_OUTGOING] Routing mode change message")
                # Check if this is a completion message
                is_completion = (command_type == 'mode_change_completion' or 
                                message_type == 'weather_radarModeChangeCompletion')
                return self._route_mode_change(message, is_completion)
                
            elif command_type == 'show_display':
                self.logger.info(f"[LOCAL_DISP_OUTGOING] Routing show display message")
                return self._route_show_display(message)
                
            else:
                # For all other message types, use the DisplayResponseService
                self.logger.info(f"[LOCAL_DISP_OUTGOING] Routing generic message to DisplayResponseService")
                
                # Extract metadata from message
                request_id = message_dict.get('request_id')
                source_system = None
                mode = None
                mode_value = None
                
                if 'metadata' in message_dict and isinstance(message_dict['metadata'], dict):
                    metadata = message_dict['metadata']
                    source_system = metadata.get('source_system') or metadata.get('sending_system')
                    mode = metadata.get('mode')
                    mode_value = metadata.get('mode_value')
                    if 'request_id' in metadata and not request_id:
                        request_id = metadata['request_id']
                
                # Create command data for DisplayResponseService
                command_data = {
                    'command_type': command_type if command_type else 'data',
                    'display_type': 'radar_display',  # Use proper display type
                    'status': 'acknowledged',
                    'request_id': request_id,
                    'additional_info': {
                        'source_system': source_system if source_system else 'weather_radar',
                        'mode': mode,
                        'mode_value': mode_value,
                        'force_update': True,
                        'update_visual': True,
                        'original_message': message_dict  # Include original message for reference
                    }
                }
                
                # Send to DisplayResponseService using create_task
                try:
                    # Create a task to handle the display command
                    asyncio.create_task(self._send_to_display_response_service(command_data))
                    self.logger.info(f"[LOCAL_DISP_OUTGOING] Successfully created task to route message to DisplayResponseService")
                    return True
                except Exception as e:
                    self.logger.error(f"[LOCAL_DISP_OUTGOING] Error creating task to route to DisplayResponseService: {e}")
                    self.logger.error(traceback.format_exc())
                    # Fall back to generic message routing
                    return self._route_generic_message(message)
            
        except Exception as e:
            self.logger.error(f"[LOCAL_DISP_OUTGOING] Error routing message: {e}")
            self.logger.error(traceback.format_exc())
            return False
    
    async def _send_to_display_response_service(self, command_data: Dict[str, Any]) -> bool:
        """
        Send command data to the DisplayResponseService.
        
        Args:
            command_data: The command data to send
            
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        try:
            # Send the command to the DisplayResponseService
            await self.response_service.handle_display_command(command_data, from_display_handler=True)
            self.logger.info(f"[LOCAL_DISP_OUTGOING] Successfully sent command to DisplayResponseService")
            return True
        except Exception as e:
            self.logger.error(f"[LOCAL_DISP_OUTGOING] Error sending to DisplayResponseService: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    def _get_display_handler(self):
        """Get the DisplayMessageHandler instance, initializing if needed."""
        if not self.display_handler:
            self.display_handler = get_display_message_handler()
            if not self.display_handler:
                self.logger.error("[LOCAL_DISP_OUTGOING] Failed to get DisplayMessageHandler")
        return self.display_handler

    async def _send_via_display_handler(self, display_type: str, command_type: str, command_data: Any) -> bool:
        """
        Send a message via the DisplayMessageHandler.
        
        Args:
            display_type: Type of display (e.g., 'radar_display')
            command_type: Type of command (e.g., 'mode_change')
            command_data: Command data
            
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        try:
            # Get display handler
            display_handler = self._get_display_handler()
            if not display_handler:
                return False
                
            # Send request through display handler
            request_id = await display_handler.send_request(
                display_type=display_type,
                command_type=command_type,
                command_data=command_data
            )
            
            if request_id:
                self.logger.info(f"[LOCAL_DISP_OUTGOING] Message sent via DisplayMessageHandler with request_id: {request_id}")
                return True
            else:
                self.logger.error("[LOCAL_DISP_OUTGOING] Failed to send message via DisplayMessageHandler")
                return False
                
        except Exception as e:
            self.logger.error(f"[LOCAL_DISP_OUTGOING] Error sending via DisplayMessageHandler: {e}")
            self.logger.error(traceback.format_exc())
            return False

    def _route_mode_change(self, message: Union[Dict[str, Any], Any], is_completion: bool) -> bool:
        """
        Route a mode change message to the display system using MIL-STD-1553B messaging protocol.
        
        Args:
            message: The message to route
            is_completion: Whether this is a mode change completion message
            
        Returns:
            bool: True if the message was routed successfully, False otherwise
        """
        try:
            # Convert message to dictionary if needed
            message_dict = message
            if not isinstance(message, dict):
                message_dict = {}
                for attr in dir(message):
                    if not attr.startswith('_') and not callable(getattr(message, attr)):
                        message_dict[attr] = getattr(message, attr)
            
            # Extract mode information with enhanced logging
            mode = None
            mode_value = None
            
            # Try to get mode from metadata
            if 'metadata' in message_dict and isinstance(message_dict['metadata'], dict):
                metadata = message_dict['metadata']
                if 'mode' in metadata:
                    mode = metadata['mode']
                    self.logger.info(f"[LOCAL_DISP_OUTGOING] Found mode in metadata: {mode}")
                elif 'new_mode' in metadata:
                    mode = metadata['new_mode']
                    self.logger.info(f"[LOCAL_DISP_OUTGOING] Found new_mode in metadata: {mode}")
                    
                # Try to get mode_value from metadata
                if 'mode_value' in metadata:
                    mode_value = metadata['mode_value']
                    self.logger.info(f"[LOCAL_DISP_OUTGOING] Found mode_value in metadata: {mode_value}")
            
            # If we couldn't get mode from metadata, try to get it from data
            if mode is None and 'data' in message_dict:
                data = message_dict['data']
                if isinstance(data, list) and len(data) > 0:
                    # First item in data list might be the mode value
                    mode_value = data[0]
                    self.logger.info(f"[LOCAL_DISP_OUTGOING] Found mode_value in data list: {mode_value}")
                    
                    # Try to map mode value to mode name
                    mode = self._get_mode_name_from_value(mode_value)
                    if mode:
                        self.logger.info(f"[LOCAL_DISP_OUTGOING] Derived mode name from value: {mode}")
                elif isinstance(data, (int, str)):
                    # Data might be the mode value directly
                    try:
                        mode_value = int(data)
                        self.logger.info(f"[LOCAL_DISP_OUTGOING] Found mode_value in data: {mode_value}")
                        
                        # Try to map mode value to mode name
                        mode = self._get_mode_name_from_value(mode_value)
                        if mode:
                            self.logger.info(f"[LOCAL_DISP_OUTGOING] Derived mode name from value: {mode}")
                    except (ValueError, TypeError):
                        pass
            
            # Log the mode information
            self.logger.info(f"[LOCAL_DISP_OUTGOING] Final mode information: mode={mode}, mode_value={mode_value}")
            
            
            # Get the display handler
            display_handler = self._get_display_handler()
            if not display_handler:
                self.logger.error("[LOCAL_DISP_OUTGOING] Failed to get DisplayMessageHandler")
                return False
                
            # For mode change completion messages, use DisplayResponseService
            if is_completion:
                # Extract request_id from message
                request_id = None
                if 'request_id' in message_dict:
                    request_id = message_dict['request_id']
                elif 'metadata' in message_dict and isinstance(message_dict['metadata'], dict):
                    metadata = message_dict['metadata']
                    if 'request_id' in metadata:
                        request_id = metadata['request_id']
                
                # Check if this message has already been processed
                if 'metadata' in message_dict and isinstance(message_dict['metadata'], dict):
                    if message_dict['metadata'].get('_processed_by_display_response'):
                        logger.warning(f"[LOCAL_DISP_OUTGOING] Skipping already processed mode change completion message")
                        return True
                
                # Create command data for DisplayResponseService
                command_data = {
                    'command_type': 'mode_change_completion',
                    'display_type': 'radar_display',  # Use proper display type
                    'status': 'acknowledged',
                    'request_id': request_id,
                    'timestamp': time.time(),
                    'additional_info': {
                        'source_system': 'weather_radar',
                        'mode': mode,
                        'mode_value': mode_value,
                        'force_update': True,
                        'update_visual': True,
                        'is_completion_message': True,
                        '_processed_by_display_response': True,  # Mark as processed
                        '_prevent_rerouting': True  # Add explicit flag to prevent re-routing
                    }
                }
                
                # Generate a unique transaction ID for this command
                import uuid
                transaction_id = str(uuid.uuid4())
                command_data['additional_info']['transaction_id'] = transaction_id
                
                # Send to DisplayResponseService using create_task
                try:
                    # Create a task to handle the display command
                    asyncio.create_task(self._send_to_display_response_service(command_data))
                    logger.info(f"[LOCAL_DISP_OUTGOING] Created task to route mode change completion to DisplayResponseService with transaction_id {transaction_id}")
                    return True
                except Exception as e:
                    logger.error(f"[LOCAL_DISP_OUTGOING] Error creating task to route to DisplayResponseService: {e}")
                    logger.error(traceback.format_exc())
                    # Continue with normal processing as fallback
            
            # Extract display_type from message (only used if DisplayResponseService routing failed or for non-completion messages)
            display_type = 'radar_display'  # Default to radar_display
            if 'display_type' in message_dict:
                display_type = message_dict['display_type']
            elif 'metadata' in message_dict and isinstance(message_dict['metadata'], dict):
                metadata = message_dict['metadata']
                if 'display_type' in metadata:
                    display_type = metadata['display_type']
                
            # Extract command_type from message (for non-completion messages)
            command_type = 'mode_change'  # Default to mode_change
            if 'command_type' in message_dict:
                command_type = message_dict['command_type']
            elif 'metadata' in message_dict and isinstance(message_dict['metadata'], dict):
                metadata = message_dict['metadata']
                if 'command_type' in metadata:
                    command_type = metadata['command_type']
                    
            # If this is a completion message, ensure command_type is set to mode_change
            if is_completion and (command_type == 'mode_change_completion'):
                command_type = 'mode_change'
                self.logger.info(f"[LOCAL_DISP_OUTGOING] Setting command_type to 'mode_change' for completion message")
            
            # Get message type for transformation
            message_type = get_message_type(message_dict)
                    
            # Log the message type for debugging
            self.logger.info(f"[LOCAL_DISP_OUTGOING] Message type for transformation: {message_type}")
            
            # Transform the message for display
            transformed_message = transform_message(message_dict, message_type, 'display')
            
            # Extract command_data from transformed message
            command_data = {}
            for field in ['mode', 'mode_value', 'force_update', 'update_visual', 'is_completion_message']:
                if field in transformed_message:
                    command_data[field] = transformed_message[field]
            
            # For mode change completion messages, extract the mode from the message
            if is_completion:
                # Try to get the mode from the message
                if mode is not None:
                    self.logger.info(f"[LOCAL_DISP_OUTGOING] Mode change completion message, using mode from message: {mode}")
                    try:
                        radar_mode = RadarDisplayMode.from_string(mode)
                    except Exception as e:
                        self.logger.error(f"[LOCAL_DISP_OUTGOING] Error converting mode {mode} to RadarDisplayMode: {e}")
                        # Fall back to mode_value if available
                        if mode_value is not None:
                            try:
                                mode_name = RadarDisplayMode.to_string(int(mode_value))
                                radar_mode = RadarDisplayMode.from_string(mode_name)
                                self.logger.info(f"[LOCAL_DISP_OUTGOING] Using mode_value {mode_value} to get mode {mode_name}")
                            except Exception as e2:
                                raise Exception(f"Error converting mode_value {mode_value} to RadarDisplayMode: {e2}")
                        else:
                            raise Exception(f"Error converting mode_value {mode_value} to RadarDisplayMode: {e}")
                elif mode_value is not None:
                    # Try to convert the mode value to a string and then to an enum
                    try:
                        mode_name = RadarDisplayMode.to_string(int(mode_value))
                        radar_mode = RadarDisplayMode.from_string(mode_name)
                        self.logger.info(f"[LOCAL_DISP_OUTGOING] Using mode_value {mode_value} to get mode {mode_name}")
                    except Exception as e:
                        raise Exception(f"Error converting mode_value {mode_value} to RadarDisplayMode: {e}")

                else:
                    # NOTE (production readiness re-analysis, August 2026): this branch
                    # is reached when both `mode` and `mode_value` are None (it's the
                    # final `else` of the `if mode is not None: / elif mode_value is not
                    # None: / else:` chain above) -- there is no exception object in
                    # scope here, so the original `{e}` interpolation referenced an
                    # undefined name. Found via `ruff check --select F821`. Reworded to
                    # describe the actual condition instead of a nonexistent exception.
                    raise Exception("Cannot convert to RadarDisplayMode: both mode "
                                     "and mode_value are missing/None")
            else:
                # For mode change completion messages, prioritize the mode from metadata
                if is_completion and mode is not None:
                    self.logger.info(f"[LOCAL_DISP_OUTGOING] Mode change completion message, using mode from metadata: {mode}")
                    try:
                        radar_mode = RadarDisplayMode.from_string(mode)
                        self.logger.info(f"[LOCAL_DISP_OUTGOING] Successfully converted mode {mode} to RadarDisplayMode: {radar_mode}")
                    except Exception as e:
                        self.logger.error(f"[LOCAL_DISP_OUTGOING] Error converting mode {mode} to RadarDisplayMode: {e}")
                        # Fall back to mode_value if available
                        if mode_value is not None:
                            try:
                                mode_name = RadarDisplayMode.to_string(int(mode_value))
                                radar_mode = RadarDisplayMode.from_string(mode_name)
                                self.logger.info(f"[LOCAL_DISP_OUTGOING] Using mode_value {mode_value} to get mode {mode_name}")
                            except Exception as e2:
                                raise Exception(f"Error converting mode_value {mode_value} to RadarDisplayMode: {e2}")

                        else:
                            raise Exception(f"Error converting mode_value {mode_value} to RadarDisplayMode: {e}")

                # For regular mode change messages, try to map mode value to RadarDisplayMode
                radar_mode = None
                try:
                    if mode_value is not None:
                        # Try to convert the mode value to a string and then to an enum
                        mode_name = RadarDisplayMode.to_string(int(mode_value))
                        radar_mode = RadarDisplayMode.from_string(mode_name)
                        self.logger.info(f"[LOCAL_DISP_OUTGOING] Converted mode_value {mode_value} to RadarDisplayMode: {radar_mode}")
                    elif mode is not None:
                        # Try to convert the mode name to an enum
                        radar_mode = RadarDisplayMode.from_string(mode)
                        self.logger.info(f"[LOCAL_DISP_OUTGOING] Converted mode {mode} to RadarDisplayMode: {radar_mode}")
                    else:
                        # NOTE (production readiness re-analysis, August 2026): same class
                        # of bug as the other `{e}` fix above in this file -- this `else`
                        # (both mode_value and mode are None) is a sibling branch inside
                        # the `try:` block, reached before any `except` binds `e`, so the
                        # original interpolation referenced an undefined name. Found via
                        # `ruff check --select F821`.
                        raise Exception(f"Cannot convert to RadarDisplayMode: both mode "
                                         f"and mode_value are missing/None")
                except Exception as e:
                    raise Exception(f"Error converting mode_value {mode_value} to RadarDisplayMode: {e}")

            
            self.logger.info(f"[LOCAL_DISP_OUTGOING] Using radar mode: {radar_mode}")
        
            try:
                # Use command_type from transformed message if available
                if 'command_type' in transformed_message:
                    command_type = transformed_message['command_type']
                
                # Use display_type from transformed message if available
                if 'display_type' in transformed_message:
                    display_type = transformed_message['display_type']
                
                self.logger.info(f"[LOCAL_DISP_OUTGOING] Sending {command_type} request to {display_type} with mode {radar_mode}")
                
                # Create a task to send the request
                loop = asyncio.get_event_loop()
                task = asyncio.create_task(
                    display_handler.send_request(
                        display_type=display_type,
                        command_type=command_type,
                        command_data=radar_mode if is_completion else command_data
                    )
                )
                
                # Add a callback to handle the result
                def handle_result(future):
                    try:
                        mode_change_request = future.result()
                        if mode_change_request:
                            self.logger.info(f"[LOCAL_DISP_OUTGOING] Message sent successfully to display system")
                        else:
                            self.logger.error(f"[LOCAL_DISP_OUTGOING] Failed to send message to display system")
                    except Exception as e:
                        self.logger.error(f"[LOCAL_DISP_OUTGOING] Error in send_request callback: {e}")
                        self.logger.error(traceback.format_exc())
                
                # Add the callback
                task.add_done_callback(handle_result)
                
                # Return success since we've created the task
                return True
                
            except Exception as e:
                self.logger.error(f"[LOCAL_DISP_OUTGOING] Error in _send_mode_change_request: {e}")
                self.logger.error(traceback.format_exc())
                return False
            
        except Exception as e:
            self.logger.error(f"[LOCAL_DISP_OUTGOING] Error routing mode change: {e}")
            self.logger.error(traceback.format_exc())
            # Return True to prevent further processing
            return True

    def _route_vil_data(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Route VIL data to the display system.
        
        Args:
            message: The message to route
            
        Returns:
            bool: True if the message was routed successfully, False otherwise
        """
        try:
            # Convert message to dictionary if needed
            message_dict = message
            if not isinstance(message, dict):
                message_dict = {}
                for attr in dir(message):
                    if not attr.startswith('_') and not callable(getattr(message, attr)):
                        message_dict[attr] = getattr(message, attr)
            
            # Extract VIL data
            vil_data = None
            
            # Try to get VIL data from various locations in the message
            if 'vil_data' in message_dict:
                vil_data = message_dict['vil_data']
            elif 'data' in message_dict and isinstance(message_dict['data'], dict) and 'vil_data' in message_dict['data']:
                vil_data = message_dict['data']['vil_data']
            elif 'metadata' in message_dict and isinstance(message_dict['metadata'], dict) and 'weather_data' in message_dict['metadata']:
                weather_data = message_dict['metadata']['weather_data']
                if isinstance(weather_data, dict) and 'vil_data' in weather_data:
                    vil_data = weather_data['vil_data']
            
            if not vil_data:
                self.logger.error("[LOCAL_DISP_OUTGOING] No VIL data found in message")
                return False
            
            # Create command data for display handler
            command_data = {
                'type': 'vil_data',
                'vil_data': vil_data,
                'force_update': True,
                'update_visual': True
            }
            
            # Add command_name from message if available
            if 'command_name' in message_dict:
                command_data['command_name'] = message_dict['command_name']
            elif 'metadata' in message_dict and isinstance(message_dict['metadata'], dict) and 'command_name' in message_dict['metadata']:
                command_data['command_name'] = message_dict['metadata']['command_name']
            
            # Add request_id if available
            if 'request_id' in message_dict:
                command_data['request_id'] = message_dict['request_id']
            
            # Create a task to send the request
            display_handler = self._get_display_handler()
            if not display_handler:
                self.logger.error("[LOCAL_DISP_OUTGOING] Failed to get DisplayMessageHandler")
                return False
                
            # Create a task to send the request
            task = asyncio.create_task(
                display_handler.send_request(
                    display_type='radar_display',
                    command_type='data',
                    command_data=command_data
                )
            )
            
            # Add a callback to handle the result
            def handle_result(future):
                try:
                    result = future.result()
                    if result:
                        self.logger.info(f"[LOCAL_DISP_OUTGOING] VIL data sent successfully to display system")
                    else:
                        self.logger.error(f"[LOCAL_DISP_OUTGOING] Failed to send VIL data to display system")
                except Exception as e:
                    self.logger.error(f"[LOCAL_DISP_OUTGOING] Error in send_request callback: {e}")
                    self.logger.error(traceback.format_exc())
            
            # Add the callback
            task.add_done_callback(handle_result)
            
            # Return success since we've created the task
            return True
            
        except Exception as e:
            self.logger.error(f"[LOCAL_DISP_OUTGOING] Error routing VIL data: {e}")
            self.logger.error(traceback.format_exc())
            return False

    async def _route_precipitation_data(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Route precipitation data to the display system using the DisplayMessageHandler.
        
        Args:
            message: The message to route
            
        Returns:
            bool: True if the message was routed successfully, False otherwise
        """
        try:
            self.logger.warning("[LOCAL_DISP_OUTGOING] Starting _route_precipitation_data with AWAIT implementation")
            
            # Convert message to dictionary if needed
            message_dict = message
            if not isinstance(message, dict):
                message_dict = {}
                for attr in dir(message):
                    if not attr.startswith('_') and not callable(getattr(message, attr)):
                        message_dict[attr] = getattr(message, attr)
                        
            # Check if this message has already been processed by DisplayResponseService
            metadata = message_dict.get('metadata', {})
            if metadata.get('_processed_by_display_response'):
                self.logger.warning("[LOCAL_DISP_OUTGOING] Skipping precipitation data already processed by DisplayResponseService")
                return True
            
            # Log message structure
            self.logger.info(f"[LOCAL_DISP_OUTGOING] Message keys: {list(message_dict.keys())}")
            if 'metadata' in message_dict:
                self.logger.info(f"[LOCAL_DISP_OUTGOING] Metadata keys: {list(message_dict['metadata'].keys())}")
            
            # Extract precipitation data with enhanced logging
            precipitation_data = None
            extraction_source = None
            
            # Try to get precipitation data from various locations in the message
            if 'precipitation_data' in message_dict:
                precipitation_data = message_dict['precipitation_data']
                extraction_source = 'precipitation_data key'
            elif 'precipitation' in message_dict:
                precipitation_data = message_dict['precipitation']
                extraction_source = 'precipitation key'
            elif 'data' in message_dict:
                if isinstance(message_dict['data'], dict):
                    if 'precipitation_data' in message_dict['data']:
                        precipitation_data = message_dict['data']['precipitation_data']
                        extraction_source = 'data.precipitation_data'
                    elif 'precipitation' in message_dict['data']:
                        precipitation_data = message_dict['data']['precipitation']
                        extraction_source = 'data.precipitation'
                else:
                    # If data is not a dict, use it directly as precipitation data
                    precipitation_data = message_dict['data']
                    extraction_source = 'data (direct)'
            elif 'metadata' in message_dict and isinstance(message_dict['metadata'], dict):
                metadata = message_dict['metadata']
                if 'precipitation_data' in metadata:
                    precipitation_data = metadata['precipitation_data']
                    extraction_source = 'metadata.precipitation_data'
                elif 'precipitation' in metadata:
                    precipitation_data = metadata['precipitation']
                    extraction_source = 'metadata.precipitation'
                elif 'weather_data' in metadata:
                    weather_data = metadata['weather_data']
                    if isinstance(weather_data, dict):
                        if 'precipitation_data' in weather_data:
                            precipitation_data = weather_data['precipitation_data']
                            extraction_source = 'metadata.weather_data.precipitation_data'
                        elif 'precipitation' in weather_data:
                            precipitation_data = weather_data['precipitation']
                            extraction_source = 'metadata.weather_data.precipitation'
            
            # Log extraction results
            if precipitation_data:
                if isinstance(precipitation_data, list):
                    self.logger.info(f"[LOCAL_DISP_OUTGOING] Extracted {len(precipitation_data)} precipitation data points from {extraction_source}")
                else:
                    self.logger.info(f"[LOCAL_DISP_OUTGOING] Extracted precipitation data of type {type(precipitation_data)} from {extraction_source}")
            else:
                self.logger.error("[LOCAL_DISP_OUTGOING] No precipitation data found in message")
                return False
            
            # Get display handler
            display_handler = self._get_display_handler()
            if not display_handler:
                self.logger.error("[LOCAL_DISP_OUTGOING] Failed to get DisplayMessageHandler")
                return False
            
            # Create command data for display handler
            command_data = {
                'type': 'precipitation_data',
                'data_type': 'precipitation',  # Add explicit data_type for proper identification
                'precipitation': precipitation_data,
                'force_update': True,
                'update_visual': True,
                'show_precipitation': True,  # Add explicit flag to show precipitation
                'precipitation_message': True,  # Add flag to identify this as precipitation data
                'weather_data': {  # Add weather_data structure for consistency with other data types
                    'precipitation': precipitation_data,
                    'show_precipitation': True  # Also set flag in weather_data
                }
            }
            
            # Add command_name from message if available
            if 'command_name' in message_dict:
                command_data['command_name'] = message_dict['command_name']
            elif 'metadata' in message_dict and isinstance(message_dict['metadata'], dict) and 'command_name' in message_dict['metadata']:
                command_data['command_name'] = message_dict['metadata']['command_name']
            
            # Add request_id if available
            if 'request_id' in message_dict:
                command_data['request_id'] = message_dict['request_id']
                self.logger.info(f"[LOCAL_DISP_OUTGOING] Using request_id from message: {message_dict['request_id']}")
            
            # Log command data structure
            self.logger.info(f"[LOCAL_DISP_OUTGOING] Command data keys: {list(command_data.keys())}")
            if 'weather_data' in command_data:
                self.logger.info(f"[LOCAL_DISP_OUTGOING] Weather data keys: {list(command_data['weather_data'].keys())}")
            
            # IMPORTANT: Directly await the send_request call instead of creating a task
            self.logger.warning("[LOCAL_DISP_OUTGOING] Directly awaiting send_request call to ensure message is sent through BC")
            request_id = await display_handler.send_request(
                display_type='radar_display',
                command_type='data',
                command_data=command_data
            )
            
            # Log the result immediately
            if request_id:
                self.logger.warning(f"[LOCAL_DISP_OUTGOING] Precipitation data sent successfully through DisplayMessageHandler with request ID: {request_id}")
                
                # Also store in DisplayResponseService for tracking
                try:
                    # Create command data for DisplayResponseService
                    response_command_data = {
                        'command_type': 'precipitation_data',
                        'display_type': 'radar_display',
                        'status': 'acknowledged',
                        'request_id': command_data.get('request_id', None),
                        'timestamp': time.time(),
                        'additional_info': {
                            'source_system': 'weather_radar',
                            'data_type': 'precipitation',
                            'weather_data': {
                                'precipitation': precipitation_data
                            },
                            'force_update': True,
                            'update_visual': True,
                            'show_precipitation': True
                        }
                    }
                    
                    # Add transaction ID to prevent re-routing
                    # Note: uuid module is already imported at the top of the file
                    if 'additional_info' not in response_command_data:
                        response_command_data['additional_info'] = {}
                    if 'transaction_id' not in response_command_data['additional_info']:
                        response_command_data['additional_info']['transaction_id'] = str(uuid.uuid4())
                    
                    # Add flag to prevent re-routing
                    response_command_data['additional_info']['_prevent_rerouting'] = True
                    
                    # Send to DisplayResponseService
                    await self._send_to_display_response_service(response_command_data)
                    self.logger.info(f"[LOCAL_DISP_OUTGOING] Also sent precipitation data to DisplayResponseService for tracking with transaction_id {response_command_data['additional_info']['transaction_id']}")
                except Exception as e:
                    self.logger.error(f"[LOCAL_DISP_OUTGOING] Error sending to DisplayResponseService: {e}")
                    # Continue with normal processing as we already sent via the primary method
                
                # Return success since we've successfully sent the message
                return True
            else:
                self.logger.error(f"[LOCAL_DISP_OUTGOING] Failed to send precipitation data through DisplayMessageHandler")
                return False
            
        except Exception as e:
            self.logger.error(f"[LOCAL_DISP_OUTGOING] Error routing precipitation data: {e}")
            self.logger.error(traceback.format_exc())
            return False

    def _route_show_display(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Route show display command to the display system.
        
        Args:
            message: The message to route
            
        Returns:
            bool: True if the message was routed successfully, False otherwise
        """
        try:
            # Convert message to dictionary if needed
            message_dict = message
            if not isinstance(message, dict):
                message_dict = {}
                for attr in dir(message):
                    if not attr.startswith('_') and not callable(getattr(message, attr)):
                        message_dict[attr] = getattr(message, attr)
            
            # Extract display type
            display_type = message_dict.get('display_type', 'radar_display')
            
            # Get display handler
            display_handler = self._get_display_handler()
            if not display_handler:
                self.logger.error("[LOCAL_DISP_OUTGOING] Failed to get DisplayMessageHandler")
                return False
            
            # Create a task to send the request
            task = asyncio.create_task(
                display_handler.send_request(
                    display_type=display_type,
                    command_type='show',
                    command_data=None
                )
            )
            
            # Add a callback to handle the result
            def handle_result(future):
                try:
                    result = future.result()
                    if result:
                        self.logger.info(f"[LOCAL_DISP_OUTGOING] Show display command sent successfully")
                    else:
                        self.logger.error(f"[LOCAL_DISP_OUTGOING] Failed to send show display command")
                except Exception as e:
                    self.logger.error(f"[LOCAL_DISP_OUTGOING] Error in send_request callback: {e}")
                    self.logger.error(traceback.format_exc())
            
            # Add the callback
            task.add_done_callback(handle_result)
            
            # Return success since we've created the task
            return True
            
        except Exception as e:
            self.logger.error(f"[LOCAL_DISP_OUTGOING] Error routing show display: {e}")
            self.logger.error(traceback.format_exc())
            return False

    def _route_generic_message(self, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Route a generic message to the display system.
        
        Args:
            message: The message to route
            
        Returns:
            bool: True if the message was routed successfully, False otherwise
        """
        try:
            # Convert message to dictionary if needed
            message_dict = message
            if not isinstance(message, dict):
                message_dict = {}
                for attr in dir(message):
                    if not attr.startswith('_') and not callable(getattr(message, attr)):
                        message_dict[attr] = getattr(message, attr)
            
            # Extract command type and display type
            command_type = message_dict.get('command_type', 'data')
            display_type = message_dict.get('display_type', 'radar_display')
            
            # Create command data from message
            command_data = {}
            
            # Copy relevant fields from message
            for field in ['data', 'mode', 'type', 'request_id', 'force_update', 'update_visual']:
                if field in message_dict:
                    command_data[field] = message_dict[field]
            
            # Copy metadata fields if available
            if 'metadata' in message_dict and isinstance(message_dict['metadata'], dict):
                for field in ['mode', 'mode_value', 'source_system', 'request_id']:
                    if field in message_dict['metadata']:
                        command_data[field] = message_dict['metadata'][field]
            
            # Get display handler
            display_handler = self._get_display_handler()
            if not display_handler:
                self.logger.error("[LOCAL_DISP_OUTGOING] Failed to get DisplayMessageHandler")
                return False
            
            # Create a task to send the request
            task = asyncio.create_task(
                display_handler.send_request(
                    display_type=display_type,
                    command_type=command_type,
                    command_data=command_data
                )
            )
            
            # Add a callback to handle the result
            def handle_result(future):
                try:
                    result = future.result()
                    if result:
                        self.logger.info(f"[LOCAL_DISP_OUTGOING] Generic message sent successfully to display system")
                    else:
                        self.logger.error(f"[LOCAL_DISP_OUTGOING] Failed to send generic message to display system")
                except Exception as e:
                    self.logger.error(f"[LOCAL_DISP_OUTGOING] Error in send_request callback: {e}")
                    self.logger.error(traceback.format_exc())
            
            # Add the callback
            task.add_done_callback(handle_result)
            
            # Return success since we've created the task
            return True
            
        except Exception as e:
            self.logger.error(f"[LOCAL_DISP_OUTGOING] Error routing generic message: {e}")
            self.logger.error(traceback.format_exc())
            return False
            
    def _get_mode_name_from_value(self, mode_value: Union[int, str]) -> str:
        """
        Get mode name from mode value.
        
        Args:
            mode_value: The mode value
            
        Returns:
            str: The mode name
        """
        # Convert to int if string
        if isinstance(mode_value, str):
            try:
                mode_value = int(mode_value)
            except ValueError:
                return None
                
        # Weather radar modes
        weather_radar_modes = {
            0: 'STANDBY',
            1: 'SURVEILLANCE',
            2: 'MAPPING',
            3: 'TURBULENCE',
            4: 'WINDSHEAR',
            5: 'NORMAL'
        }
        
        return weather_radar_modes.get(mode_value, None)

def get_display_outgoing_router():
    """Get a new instance of DisplayOutgoingRouter."""
    return DisplayOutgoingRouter()

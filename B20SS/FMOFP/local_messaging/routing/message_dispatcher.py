"""
Message Dispatcher

Dispatches messages to system queues.
Handles message priorities and delivery confirmation.
"""

import time
import traceback
from typing import Dict, Any, Union

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class MessageDispatcher:
    def __init__(self):
        self.logger = get_logger()
        self.message_queue_manager = None
        logger.info("MessageDispatcher initialized")
        
    def initialize(self):
        """Initialize the dispatcher."""
        # Get the message queue manager through the system manager
        # This respects system boundaries by using the central system manager
        from FMOFP.core.system_manager import get_system_manager
        system_manager = get_system_manager()
        self.message_queue_manager = system_manager.get_component('message_queue_manager')
        
        if not self.message_queue_manager:
            self.logger.warning("Message queue manager not found in system manager, will try to get it when needed")
        else:
            self.logger.info("MessageDispatcher initialized with message queue manager")
        
    def dispatch_message(self, destination: str, message: Union[Dict[str, Any], Any]) -> bool:
        """
        Dispatch a message to a system queue.
        
        Args:
            destination: The destination system ID
            message: The message to dispatch
            
        Returns:
            bool: True if the message was dispatched successfully, False otherwise
        """
        try:
            # Get message queue manager if not already available
            if not self.message_queue_manager:
                from FMOFP.MIL_STD_1553B.Remote_Terminal.RT_messaging.message_queue_manager import get_message_queue_manager
                self.message_queue_manager = get_message_queue_manager()
                
            if not self.message_queue_manager:
                self.logger.error(f"Message queue manager not available for destination: {destination}")
                return False
            
            # Extract and log critical fields for tracking
            request_id = None
            command_name = None
            
            if isinstance(message, dict):
                request_id = message.get('request_id')
                command_name = message.get('command_name')
            elif hasattr(message, 'request_id') and hasattr(message, 'command_name'):
                request_id = message.request_id
                command_name = message.command_name
                
            self.logger.info(f"[DISPATCHER] Dispatching message to {destination} - request_id: {request_id}, command_name: {command_name}")
                
            # Ensure critical fields are preserved before dispatching
            if isinstance(message, dict):
                # Make sure we have metadata
                if 'metadata' not in message:
                    message['metadata'] = {}
                    
                # Preserve command_name in metadata
                if command_name and 'command_name' not in message['metadata']:
                    message['metadata']['command_name'] = command_name
                    self.logger.info(f"[DISPATCHER] Preserved command_name in metadata: {command_name}")
                    
                # Preserve request_id in metadata
                if request_id and 'request_id' not in message['metadata']:
                    message['metadata']['request_id'] = request_id
                    self.logger.info(f"[DISPATCHER] Preserved request_id in metadata: {request_id}")
                
            # Get message priority
            priority = self._get_message_priority(message)
            
            # Add message to appropriate queue
            if destination in self.message_queue_manager.system_queues:
                # Use the queue manager's queue locks for thread safety
                with self.message_queue_manager.queue_locks[destination]:
                    self.message_queue_manager.system_queues[destination].append(message)
                    self.logger.info(f"[DISPATCHER] Message dispatched to {destination} queue with priority {priority}")
                return True
            else:
                self.logger.error(f"[DISPATCHER] Unknown destination queue: {destination}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error dispatching message to {destination}: {e}")
            self.logger.error(traceback.format_exc())
            return False



    def _get_message_priority(self, message: Union[Dict[str, Any], Any]) -> int:
        """
        Get message priority.
        
        Args:
            message: The message to get priority for
            
        Returns:
            int: Message priority (0 = high, 1 = normal, 2 = low)
        """
        # Check metadata for priority
        if isinstance(message, dict) and 'metadata' in message:
            metadata = message['metadata']
            if isinstance(metadata, dict) and 'priority' in metadata:
                return metadata['priority']
        elif hasattr(message, 'metadata') and message.metadata:
            metadata = message.metadata
            if isinstance(metadata, dict) and 'priority' in metadata:
                return metadata['priority']
                
        # Check message type for priority
        message_type = None
        if isinstance(message, dict):
            message_type = message.get('message_type')
        elif hasattr(message, 'message_type'):
            message_type = message.message_type
            
        if message_type:
            # High priority message types
            high_priority_types = [
                'weather_radarModeChangeRequest', 
                'weather_radarModeChangeResponse',
                'tfr_radarModeChangeRequest',
                'tfr_radarModeChangeResponse',
                'sar_radarModeChangeRequest',
                'sar_radarModeChangeResponse',
                'targeting_radarModeChangeRequest',
                'targeting_radarModeChangeResponse',
                'aewc_radarModeChangeRequest',
                'aewc_radarModeChangeResponse',
                'mode_change',
                'mode_change_completion',
                'display_mode_request',
                'weather_radarStatusRequest',
                'weather_radarStatusResponse',
                'tfr_radarStatusRequest',
                'tfr_radarStatusResponse',
                'sar_radarStatusRequest',
                'sar_radarStatusResponse',
                'targeting_radarStatusRequest',
                'targeting_radarStatusResponse',
                'aewc_radarStatusRequest',
                'aewc_radarStatusResponse'
            ]
            
            if message_type in high_priority_types:
                return 0  # High priority
                
        # Check command name for priority
        command_name = None
        if isinstance(message, dict):
            command_name = message.get('command_name')
        elif hasattr(message, 'command_name'):
            command_name = message.command_name
            
        if command_name:
            # High priority command names
            high_priority_commands = [
                'radar_modeChange',
                'displays_modeChange',
                'weather_radar_modeChange',
                'tfr_radar_modeChange',
                'sar_radar_modeChange',
                'targeting_radar_modeChange',
                'aewc_radar_modeChange',
                'radar_status',
                'displays_status',
                'weather_radar_status',
                'tfr_radar_status',
                'sar_radar_status',
                'targeting_radar_status',
                'aewc_radar_status'
            ]
            
            if command_name in high_priority_commands:
                return 0  # High priority
                
        # Check command type for priority
        command_type = None
        if isinstance(message, dict):
            command_type = message.get('command_type')
        elif hasattr(message, 'command_type'):
            command_type = message.command_type
            
        if command_type:
            # High priority command types
            high_priority_types = ['modeChange', 'status']
            
            if command_type in high_priority_types:
                return 0  # High priority
                
        # Default to normal priority
        return 1  # Normal priority

def get_message_dispatcher():
    """Get a new instance of MessageDispatcher."""
    return MessageDispatcher()

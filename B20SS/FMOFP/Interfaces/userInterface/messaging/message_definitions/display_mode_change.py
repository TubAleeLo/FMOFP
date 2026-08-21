"""
Display-specific mode change message definitions.
"""

import time
from typing import Dict, Any, Optional, List, Union
from .display_message_base import DisplayBaseMessage
from ..display_message_types import DISPLAY_MODE_CHANGE
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class DisplayModeChange(DisplayBaseMessage):
    """Display-specific mode change message."""
    
    # Mode change status values
    STATUS_PENDING = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    
    def __init__(self, display_id: Optional[str] = None, 
                 current_mode: Optional[str] = None, 
                 target_mode: Optional[str] = None, 
                 status: Optional[str] = None,
                 completion_percentage: Optional[float] = None,
                 error_message: Optional[str] = None,
                 mode_parameters: Optional[Dict[str, Any]] = None,
                 request_id: Optional[str] = None, 
                 timestamp: Optional[float] = None, 
                 metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a mode change message.
        
        Args:
            display_id: Display identifier (e.g., 'pfd', 'mfd', 'radar_display')
            current_mode: Current display mode
            target_mode: Target display mode
            status: Mode change status (pending, in_progress, completed, failed)
            completion_percentage: Percentage of mode change completion (0.0 to 100.0)
            error_message: Error message if status is 'failed'
            mode_parameters: Additional parameters for the mode change
            request_id: Unique identifier for the message request
            timestamp: Message creation timestamp
            metadata: Additional metadata for the message
        """
        super().__init__(request_id, timestamp, metadata, DISPLAY_MODE_CHANGE)
        self.display_id = display_id or 'unknown'
        self.current_mode = current_mode or 'STANDBY'
        self.target_mode = target_mode or 'STANDBY'
        self.status = status or self.STATUS_PENDING
        self.completion_percentage = completion_percentage or 0.0
        self.error_message = error_message
        self.mode_parameters = mode_parameters or {}
        
        # Add mode change-specific metadata
        self.add_metadata('command_type', 'mode_change')
        self.add_metadata('display_id', self.display_id)
        self.add_metadata('current_mode', self.current_mode)
        self.add_metadata('target_mode', self.target_mode)
        
        # Log creation with mode change-specific details
        logger.debug(f"Created mode change message for display={self.display_id}, current={self.current_mode}, target={self.target_mode}, status={self.status}")
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert message to dictionary.
        
        Returns:
            Dict: Dictionary representation of the message
        """
        data = super().to_dict()
        data.update({
            'display_id': self.display_id,
            'current_mode': self.current_mode,
            'target_mode': self.target_mode,
            'status': self.status,
            'completion_percentage': self.completion_percentage,
            'mode_parameters': self.mode_parameters
        })
        
        # Only include error_message if it exists
        if self.error_message:
            data['error_message'] = self.error_message
            
        return data
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DisplayModeChange':
        """
        Create message from dictionary.
        
        Args:
            data: Dictionary containing message data
            
        Returns:
            DisplayModeChange: New message instance
            
        Raises:
            ValueError: If data is not a dictionary
        """
        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")
            
        return cls(
            display_id=data.get('display_id'),
            current_mode=data.get('current_mode'),
            target_mode=data.get('target_mode'),
            status=data.get('status'),
            completion_percentage=data.get('completion_percentage'),
            error_message=data.get('error_message'),
            mode_parameters=data.get('mode_parameters'),
            request_id=data.get('request_id'),
            timestamp=data.get('timestamp'),
            metadata=data.get('metadata')
        )
        
    @classmethod
    def from_radar_mode_change_response(cls, response: Dict[str, Any]) -> 'DisplayModeChange':
        """
        Create mode change message from radar mode change response.
        
        Args:
            response: Radar mode change response data
            
        Returns:
            DisplayModeChange: New message instance
            
        Raises:
            ValueError: If response is not a dictionary or is missing required fields
        """
        if not isinstance(response, dict):
            raise ValueError("Response must be a dictionary")
            
        # Extract mode change data from response
        mode_data = response.get('data', {})
        if not mode_data:
            raise ValueError("Response missing mode data")
            
        # Extract metadata
        metadata = response.get('metadata', {})
        if 'transaction_id' not in metadata:
            metadata['transaction_id'] = response.get('request_id', '')
            
        # Determine display_id from radar type
        radar_type = metadata.get('radar_type', 'weather_radar')
        display_id = 'radar_display'
        
        # Create mode change message
        return cls(
            display_id=display_id,
            current_mode=mode_data.get('current_mode'),
            target_mode=mode_data.get('target_mode'),
            status=mode_data.get('status', cls.STATUS_COMPLETED),
            completion_percentage=mode_data.get('completion_percentage', 100.0),
            error_message=mode_data.get('error_message'),
            mode_parameters=mode_data.get('mode_parameters'),
            request_id=response.get('request_id'),
            timestamp=response.get('timestamp'),
            metadata=metadata
        )
        
    def update_status(self, status: str, completion_percentage: Optional[float] = None, error_message: Optional[str] = None) -> None:
        """
        Update mode change status.
        
        Args:
            status: New status
            completion_percentage: New completion percentage
            error_message: Error message if status is 'failed'
        """
        self.status = status
        
        if completion_percentage is not None:
            self.completion_percentage = completion_percentage
            
        if error_message is not None:
            self.error_message = error_message
            
        # Update metadata
        self.add_metadata('status', self.status)
        self.add_metadata('completion_percentage', self.completion_percentage)
        
        # Log status update
        logger.debug(f"Updated mode change status: display={self.display_id}, status={self.status}, completion={self.completion_percentage}%")
        
    def is_completed(self) -> bool:
        """
        Check if mode change is completed.
        
        Returns:
            bool: True if status is 'completed', False otherwise
        """
        return self.status == self.STATUS_COMPLETED
        
    def is_failed(self) -> bool:
        """
        Check if mode change failed.
        
        Returns:
            bool: True if status is 'failed', False otherwise
        """
        return self.status == self.STATUS_FAILED
        
    def __str__(self) -> str:
        """
        Get string representation of the message.
        
        Returns:
            str: String representation
        """
        return f"DisplayModeChange(request_id={self.request_id}, display={self.display_id}, current={self.current_mode}, target={self.target_mode}, status={self.status})"

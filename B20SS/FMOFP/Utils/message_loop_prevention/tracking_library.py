"""
Message Tracking Library Module

This library provides specialized tracking of messages by both request ID
and message type to effectively prevent message loops.
"""

import threading
import time
from typing import Dict, Any, Optional, Set

class MessageTrackingLibrary:
    """
    Specialized library for tracking message IDs and their associated message types.
    Provides efficient lookup to detect duplicate messages while allowing different
    message types with the same ID (e.g., commands, acknowledgements, completions).
    """
    
    def __init__(self, expiration_time=3600):
        # Primary tracking structure: {request_id -> {message_type -> count}}
        self._request_type_map = {}
        
        # Time-based tracking for expiration: {request_id -> timestamp}
        self._request_timestamps = {}
        
        # Lock for thread safety
        self._lock = threading.RLock()
        
        # Expiration settings
        self._expiration_time = expiration_time
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes
    
    def has_seen_message(self, request_id, message_type):
        """
        Check if we've seen this exact request_id + message_type combination before.
        
        Args:
            request_id: The ID of the message from the request_id field
            message_type: The type of message (e.g., 'command', 'acknowledgement', 'completion')
            
        Returns:
            bool: True if this combination has been seen before, False otherwise
        """
        with self._lock:
            self._cleanup_if_needed()
            
            if not request_id:
                return False  # Can't track without a request_id
                
            if request_id not in self._request_type_map:
                return False  # First time seeing this request_id
                
            # We've seen this request_id, but have we seen this specific message type?
            return message_type in self._request_type_map[request_id]
    
    def record_message(self, request_id, message_type):
        """
        Record that we've seen this request_id + message_type combination.
        
        Args:
            request_id: The ID of the message from the request_id field
            message_type: The type of message (e.g., 'command', 'acknowledgement', 'completion')
            
        Returns:
            int: The new count for this combination (1 for first time seen)
        """
        with self._lock:
            if not request_id:
                return 0  # Can't track without a request_id
                
            # Update timestamp for this request_id
            now = time.time()
            self._request_timestamps[request_id] = now
            
            # Initialize tracking structures if needed
            if request_id not in self._request_type_map:
                self._request_type_map[request_id] = {}
                
            # Record the message type
            if message_type in self._request_type_map[request_id]:
                self._request_type_map[request_id][message_type] += 1
            else:
                self._request_type_map[request_id][message_type] = 1
                
            return self._request_type_map[request_id][message_type]
    
    def get_message_types(self, request_id):
        """
        Get all message types seen for a given request_id.
        
        Args:
            request_id: The ID to check
            
        Returns:
            Dict[str, int]: Map of message_type -> count, empty if request_id not found
        """
        with self._lock:
            if request_id not in self._request_type_map:
                return {}
            
            return self._request_type_map[request_id].copy()
    
    def get_count(self, request_id, message_type):
        """
        Get the count of how many times this specific combination has been seen.
        
        Args:
            request_id: The message ID
            message_type: The message type
            
        Returns:
            int: Count of this combination, 0 if never seen
        """
        with self._lock:
            if request_id not in self._request_type_map:
                return 0
            
            if message_type not in self._request_type_map[request_id]:
                return 0
                
            return self._request_type_map[request_id][message_type]
    
    def clear(self):
        """Clear all tracking data."""
        with self._lock:
            self._request_type_map.clear()
            self._request_timestamps.clear()
    
    def _cleanup_if_needed(self):
        """Cleanup expired entries if needed."""
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_expired()
            self._last_cleanup = now
    
    def _cleanup_expired(self):
        """Remove expired request IDs."""
        now = time.time()
        expiration_threshold = now - self._expiration_time
        
        # Find expired request IDs
        expired_requests = []
        for request_id, timestamp in self._request_timestamps.items():
            if timestamp < expiration_threshold:
                expired_requests.append(request_id)
        
        # Remove expired entries
        for request_id in expired_requests:
            if request_id in self._request_type_map:
                del self._request_type_map[request_id]
            if request_id in self._request_timestamps:
                del self._request_timestamps[request_id]

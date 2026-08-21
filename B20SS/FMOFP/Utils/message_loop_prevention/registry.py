"""
Message Registry Module

This module provides a registry for tracking processed messages and detecting loops.
"""

import time
import threading
from typing import Dict, Set, List, Any, Optional, Tuple, Union

class MessageRegistry:
    """Registry for tracking processed messages and detecting loops."""
    
    def __init__(self, max_cache_size: int = 10000, expiration_time: int = 3600):
        """Initialize the message registry.
        
        Args:
            max_cache_size: Maximum number of messages to track before pruning
            expiration_time: Time in seconds after which messages are considered expired
        """
        self._processed_messages: Dict[str, float] = {}  # message_id -> timestamp
        self._message_categories: Dict[str, Dict[str, float]] = {}  # category -> {message_id -> timestamp}
        self._max_cache_size = max_cache_size
        self._expiration_time = expiration_time
        self._lock = threading.RLock()  # Thread-safe operations
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes
        
    def is_processed(self, message_id: str, category: Optional[str] = None) -> bool:
        """Check if a message has been processed.
        
        Args:
            message_id: The message ID to check
            category: Optional category to check in
            
        Returns:
            True if the message has been processed, False otherwise
        """
        with self._lock:
            self._cleanup_if_needed()
            
            # Check in category-specific registry if provided
            if category and category in self._message_categories:
                return message_id in self._message_categories[category]
                
            # Check in general registry
            return message_id in self._processed_messages
            
    def mark_processed(self, message_id: str, category: Optional[str] = None) -> None:
        """Mark a message as processed.
        
        Args:
            message_id: The message ID to mark as processed
            category: Optional category to mark in
        """
        with self._lock:
            timestamp = time.time()
            
            # Add to general registry
            self._processed_messages[message_id] = timestamp
            
            # Add to category-specific registry if provided
            if category:
                if category not in self._message_categories:
                    self._message_categories[category] = {}
                self._message_categories[category][message_id] = timestamp
                
            # Prune if necessary
            self._prune_if_needed()
            
    def get_processed_count(self, category: Optional[str] = None) -> int:
        """Get the number of processed messages.
        
        Args:
            category: Optional category to get count for
            
        Returns:
            The number of processed messages
        """
        with self._lock:
            if category and category in self._message_categories:
                return len(self._message_categories[category])
            return len(self._processed_messages)
            
    def get_stats(self) -> Dict[str, Any]:
        """Get detailed statistics about the registry.
        
        Returns:
            Dictionary of statistics
        """
        with self._lock:
            return {
                'total_messages': len(self._processed_messages),
                'categories': {
                    category: len(messages)
                    for category, messages in self._message_categories.items()
                }
            }
            
    def reset_stats(self) -> None:
        """Reset statistics."""
        with self._lock:
            # We don't clear the registries, just reset any counters
            pass
            
    def clear(self, category: Optional[str] = None) -> None:
        """Clear the registry.
        
        Args:
            category: Optional category to clear
        """
        with self._lock:
            if category and category in self._message_categories:
                self._message_categories[category].clear()
            else:
                self._processed_messages.clear()
                self._message_categories.clear()
                
    def _cleanup_if_needed(self) -> None:
        """Clean up expired entries if needed."""
        current_time = time.time()
        if current_time - self._last_cleanup > self._cleanup_interval:
            self._cleanup_expired()
            self._last_cleanup = current_time
            
    def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        current_time = time.time()
        expiration_threshold = current_time - self._expiration_time
        
        # Clean general registry
        self._processed_messages = {
            msg_id: timestamp 
            for msg_id, timestamp in self._processed_messages.items() 
            if timestamp > expiration_threshold
        }
        
        # Clean category-specific registries
        for category in list(self._message_categories.keys()):
            self._message_categories[category] = {
                msg_id: timestamp 
                for msg_id, timestamp in self._message_categories[category].items() 
                if timestamp > expiration_threshold
            }
            
            # Remove empty categories
            if not self._message_categories[category]:
                del self._message_categories[category]
            
    def _prune_if_needed(self) -> None:
        """Prune registries if they exceed max size."""
        # Prune general registry
        if len(self._processed_messages) > self._max_cache_size:
            self._prune_registry(self._processed_messages)
            
        # Prune category-specific registries
        for category in self._message_categories:
            if len(self._message_categories[category]) > self._max_cache_size:
                self._prune_registry(self._message_categories[category])
                
    def _prune_registry(self, registry: Dict[str, float]) -> None:
        """Prune a registry to max_cache_size.
        
        Args:
            registry: The registry to prune
        """
        # Sort by timestamp (oldest first)
        sorted_items = sorted(registry.items(), key=lambda x: x[1])
        
        # Keep only the newest max_cache_size * 0.8 items
        keep_count = int(self._max_cache_size * 0.8)
        items_to_keep = sorted_items[-keep_count:]
        
        # Update registry
        registry.clear()
        registry.update(dict(items_to_keep))

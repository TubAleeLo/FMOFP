"""
Base Display Node

Provides core node functionality for display state management.
Handles thread-safe updates and subscriber notifications.
"""

import threading
import time
import traceback
from typing import Any, Set, Dict, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from Utils.logger.sys_logger import get_logger

logger = get_logger()

@dataclass
class NodeMetadata:
    """Metadata for node state tracking"""
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    update_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None

class DisplayNode:
    """Base node class for display state tree"""
    
    def __init__(self, name: str, parent: Optional['DisplayNode'] = None):
        """Initialize display node.
        
        Args:
            name: Node identifier
            parent: Optional parent node
        """
        self.name = name
        self.parent = parent
        self.children: Dict[str, DisplayNode] = {}
        self.value: Any = None
        self.subscribers: Set[Callable[[str, Any], Awaitable[None]]] = set()
        self._lock = threading.Lock()
        self.metadata = NodeMetadata()
        
        logger.info(f"[DISPLAY_NODE] Created node: {name}")
        if parent:
            logger.info(f"[DISPLAY_NODE] Parent: {parent.name}")

    async def update(self, value: Any, notify: bool = True) -> None:
        """Update node value and notify subscribers.
        
        Args:
            value: New node value
            notify: Whether to notify subscribers
        """
        try:
            with self._lock:
                # Store previous value for transition logging
                previous_value = self.value
                
                # Update value and metadata
                self.value = value
                data = value if isinstance(value, dict) else {'data': value}
                self.metadata.last_updated = time.time()
                self.metadata.update_count += 1
                
                # Log based on node type
                if self.__class__.__name__ == 'ModeNode':
                    # Mode node logging
                    if isinstance(value, dict):
                        mode_name = value.get('current_mode', str(value))
                    else:
                        mode_name = str(value)
                    logger.info(f"[DISPLAY_NODE] Mode state update: {mode_name}")
                    prev_mode = previous_value.get('current_mode', str(previous_value)) if isinstance(previous_value, dict) else str(previous_value)
                    logger.info(f"[DISPLAY_NODE] {self.name} transitioned: {prev_mode} -> {mode_name}")
                else:
                    # Visual node logging
                    if isinstance(value, dict):
                        overlay = value.get('overlay', None)
                        logger.info(f"[DISPLAY_NODE] Updating visual: {value}")
                        logger.info(f"[DISPLAY_NODE] Updated visual: {overlay}")
                    else:
                        logger.info(f"[DISPLAY_NODE] Updating visual: {value}")
                        logger.info(f"[DISPLAY_NODE] Updated visual: {value}")
                
                # If this is a VIL data node, store the data directly in the coordinator
                if self.name == 'vil' or (isinstance(data, dict) and data.get('data_type') == 'vil'):
                    try:
                        # Import the data coordinator
                        from ..radar.radar_display_data_coordinator import get_radar_display_data_coordinator
                        coordinator = get_radar_display_data_coordinator()
                        
                        # Extract the VIL data and request_id
                        vil_data = None
                        request_id = None
                        
                        if isinstance(data, dict):
                            # Extract from dictionary format
                            vil_data = data.get('data', [])
                            request_id = data.get('request_id')
                            
                            # Log the data extraction
                            logger.warning(f"[DISPLAY_NODE] Extracted VIL data from dict: {len(vil_data)} items, request_id: {request_id}")
                        else:
                            # Direct data format
                            vil_data = data
                            # Try to extract request_id if available
                            if hasattr(data, 'request_id'):
                                request_id = data.request_id
                            
                            # Log the direct data
                            logger.warning(f"[DISPLAY_NODE] Using direct VIL data: {type(data)}")
                        
                        # Store the data in the coordinator
                        if vil_data:
                            stored_count = coordinator.store_data('vil', vil_data, request_id)
                            logger.warning(f"[DISPLAY_NODE] Directly stored {stored_count} VIL data points in coordinator")
                    except Exception as e:
                        logger.error(f"[DISPLAY_NODE] Error directly storing VIL data: {str(e)}")
                        logger.error(traceback.format_exc())
                        
                # If this is a precipitation data node, store the data directly in the coordinator
                elif self.name == 'precipitation' or (isinstance(data, dict) and data.get('data_type') == 'precipitation'):
                    try:
                        # Import the data coordinator
                        from ..radar.radar_display_data_coordinator import get_radar_display_data_coordinator
                        coordinator = get_radar_display_data_coordinator()
                        
                        # Extract the precipitation data and request_id
                        precipitation_data = None
                        request_id = None
                        
                        if isinstance(data, dict):
                            # Extract from dictionary format
                            precipitation_data = data.get('data', [])
                            # Also check 'precipitation' key which is commonly used
                            if not precipitation_data and 'precipitation' in data:
                                precipitation_data = data.get('precipitation', [])
                            request_id = data.get('request_id')
                            
                            # Log the data extraction
                            logger.warning(f"[DISPLAY_NODE] Extracted precipitation data from dict: {len(precipitation_data) if precipitation_data else 0} items, request_id: {request_id}")
                        else:
                            # Direct data format
                            precipitation_data = data
                            # Try to extract request_id if available
                            if hasattr(data, 'request_id'):
                                request_id = data.request_id
                            
                            # Log the direct data
                            logger.warning(f"[DISPLAY_NODE] Using direct precipitation data: {type(data)}")
                        
                        # Store the data in the coordinator
                        if precipitation_data:
                            stored_count = coordinator.store_data('precipitation', precipitation_data, request_id)
                            logger.warning(f"[DISPLAY_NODE] Directly stored {stored_count} precipitation data points in coordinator")
                    except Exception as e:
                        logger.error(f"[DISPLAY_NODE] Error directly storing precipitation data: {str(e)}")
                        logger.error(traceback.format_exc())

            # Notify subscribers *outside* the `with self._lock` block above.
            # Added (August 2026 re-analysis round, Round 12, display-tree
            # subscriber race/deadlock sweep): self._lock is a plain
            # threading.Lock, not an asyncio.Lock. Holding it across `await
            # self._notify_subscribers()` meant any concurrent
            # add_subscriber()/remove_subscriber() call on this same node
            # (both of which also acquire self._lock) would block on
            # Lock.acquire() -- a synchronous, uninterruptible call -- for a
            # lock that can only be released once this same coroutine
            # resumes and exits its `with` block. Since asyncio is single
            # threaded, that resumption itself depends on the event loop
            # scheduling other tasks, which can't happen while the loop
            # thread is stuck blocking on the same lock: a full,
            # unrecoverable event-loop deadlock. Live-reproduced (a
            # notifier() task and a concurrent remove_subscriber() call
            # deadlocked every run, confirmed via asyncio.wait_for timeout).
            # The value/metadata mutation above is still fully
            # lock-protected; only the subscriber notification (which now
            # does its own defensive snapshotting -- see
            # _notify_subscribers()) moved outside the lock.
            if notify:
                await self._notify_subscribers()

        except Exception as e:
            self.metadata.error_count += 1
            self.metadata.last_error = str(e)
            logger.error(f"[DISPLAY_NODE] Error updating {self.name}: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def _notify_subscribers(self) -> None:
        """Notify all subscribers of value update."""
        # Snapshot the subscriber set under the lock before iterating.
        # Added (August 2026 re-analysis round, Round 12, display-tree
        # subscriber race/deadlock sweep): this method used to iterate
        # self.subscribers (a live, mutable set) directly with no locking at
        # all. Any concurrent mutation of that same set from another
        # coroutine -- e.g. weather_radar_widget.py's reset path, which
        # calls `visual_node.subscribers.clear()` directly -- raised
        # "RuntimeError: Set changed size during iteration" mid-notify,
        # live-reproduced with a 10/10 failure rate across repeated runs.
        # Copying to a plain list while briefly holding self._lock gives
        # this method its own stable, private view to iterate; concurrent
        # add_subscriber()/remove_subscriber()/direct-set-mutation calls can
        # now safely proceed against the live self.subscribers set without
        # affecting an in-progress notification pass (a subscriber added or
        # removed during a notify simply takes effect starting with the
        # *next* notify call, not the one already underway -- standard,
        # expected snapshot-iteration semantics).
        with self._lock:
            subscribers_snapshot = list(self.subscribers)

        subscriber_count = len(subscribers_snapshot)
        path = self.get_path()
        logger.warning(f"[DISPLAY_NODE] Notifying {subscriber_count} subscribers for {path}")
        
        # Log subscriber details for debugging
        if subscriber_count > 0:
            for i, subscriber in enumerate(subscribers_snapshot):
                subscriber_name = subscriber.__qualname__ if hasattr(subscriber, '__qualname__') else str(subscriber)
                logger.warning(f"[DISPLAY_NODE] Subscriber {i+1}: {subscriber_name}")
        
        # Process each subscriber
        for i, subscriber in enumerate(subscribers_snapshot):
            try:
                subscriber_name = subscriber.__qualname__ if hasattr(subscriber, '__qualname__') else str(subscriber)
                logger.warning(f"[DISPLAY_NODE] Calling subscriber {i+1}: {subscriber_name}")
                
                # Call the subscriber
                await subscriber(self.name, self.value)
                
                logger.warning(f"[DISPLAY_NODE] Successfully called subscriber {i+1}: {subscriber_name}")
            except Exception as e:
                self.metadata.error_count += 1
                self.metadata.last_error = str(e)
                logger.error(f"[DISPLAY_NODE] Subscriber error for {self.name}: {str(e)}")
                logger.error(traceback.format_exc())

    def add_child(self, child: 'DisplayNode') -> None:
        """Add child node.
        
        Args:
            child: Child node to add
        """
        with self._lock:
            self.children[child.name] = child
            child.parent = self
            # Log with proper format for tree initialization
            if child.name == 'weather_radar':
                logger.info(f"[DISPLAY_NODE] Added child {child.name} to {self.name}")

    def get_child(self, name: str) -> Optional['DisplayNode']:
        """Get child node by name.
        
        Args:
            name: Child node name
            
        Returns:
            Child node if found, None otherwise
        """
        return self.children.get(name)

    def remove_child(self, name: str) -> None:
        """Remove child node.
        
        Args:
            name: Name of child to remove
        """
        with self._lock:
            if name in self.children:
                del self.children[name]
                logger.info(f"[DISPLAY_NODE] Removed child {name} from {self.name}")

    def add_subscriber(self, subscriber: Callable[[str, Any], Awaitable[None]]) -> None:
        """Add subscriber callback.
        
        Args:
            subscriber: Async callback function
        """
        with self._lock:
            self.subscribers.add(subscriber)
            logger.info(f"[DISPLAY_NODE] Added subscriber to {self.name}")

    def remove_subscriber(self, subscriber: Optional[Callable[[str, Any], Awaitable[None]]] = None) -> None:
        """Remove subscriber callback or clear all subscribers if none specified.
        
        Args:
            subscriber: Subscriber to remove, or None to clear all
        """
        with self._lock:
            if subscriber is None:
                # Clear all subscribers
                subscriber_count = len(self.subscribers)
                self.subscribers.clear()
                logger.info(f"[DISPLAY_NODE] Cleared all {subscriber_count} subscribers from {self.name}")
            else:
                # Remove specific subscriber
                self.subscribers.discard(subscriber)
                logger.info(f"[DISPLAY_NODE] Removed subscriber from {self.name}")

    def get_path(self) -> str:
        """Get full path from root to this node.
        
        Returns:
            Dot-separated path string
        """
        if self.parent is None:
            return self.name
        return f"{self.parent.get_path()}.{self.name}"

    async def notify_subscribers(self) -> None:
        """Public method to notify all subscribers of value update."""
        logger.info(f"[DISPLAY_NODE] notify_subscribers called for {self.name}")
        await self._notify_subscribers()
    
    def get_state(self) -> Dict[str, Any]:
        """Get complete state including children.
        
        Returns:
            Dict containing node state
        """
        try:
            # Use acquire with timeout to prevent deadlocks
            lock_acquired = self._lock.acquire(timeout=1.0)
            if not lock_acquired:
                logger.error(f"[DISPLAY_NODE] Could not acquire lock for {self.name} in get_state() - timeout exceeded")
                # Return basic state without children to avoid deadlock
                return {
                    'name': self.name,
                    'value': self.value,
                    'path': self.get_path(),
                    'error': 'Lock acquisition timeout',
                    'metadata': {
                        'created_at': self.metadata.created_at,
                        'last_updated': self.metadata.last_updated,
                        'update_count': self.metadata.update_count,
                        'error_count': self.metadata.error_count + 1,
                        'last_error': 'Lock acquisition timeout'
                    }
                }
                
            # Lock acquired successfully, proceed with state building
            try:
                state = {
                    'name': self.name,
                    'value': self.value,
                    'path': self.get_path(),
                    'metadata': {
                        'created_at': self.metadata.created_at,
                        'last_updated': self.metadata.last_updated,
                        'update_count': self.metadata.update_count,
                        'error_count': self.metadata.error_count,
                        'last_error': self.metadata.last_error
                    },
                    'children': {}
                }
                
                # Only process children with a try-except block to avoid cascading failures
                try:
                    for name, child in self.children.items():
                        try:
                            # Set a timeout for nested get_state calls
                            # to prevent cascading lock issues
                            child_state = child.get_state()
                            state['children'][name] = child_state
                        except Exception as child_e:
                            logger.error(f"[DISPLAY_NODE] Error getting state of child {name}: {str(child_e)}")
                            # Provide a placeholder for the child state
                            state['children'][name] = {'name': name, 'error': str(child_e)}
                except Exception as e:
                    logger.error(f"[DISPLAY_NODE] Error processing children in get_state: {str(e)}")
                    state['children_error'] = str(e)
                    
                return state
            finally:
                # Always release the lock
                self._lock.release()
                
        except Exception as e:
            logger.error(f"[DISPLAY_NODE] Error in get_state for {self.name}: {str(e)}")
            logger.error(traceback.format_exc())
            # Return minimal state in case of error
            return {
                'name': self.name,
                'error': str(e)
            }

    async def update_data(self, data: Any) -> None:
        """Update node data.
        
        Args:
            data: New data to update
        """
        try:
            logger.info(f"[DISPLAY_NODE] Updating data for {self.name}")
            await self.update(data)
        except Exception as e:
            logger.error(f"[DISPLAY_NODE] Error updating data for {self.name}: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def __repr__(self) -> str:
        """String representation of node.
        
        Returns:
            Node description string
        """
        return f"DisplayNode(name={self.name}, path={self.get_path()}, children={len(self.children)})"

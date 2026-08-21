"""
Log throttling utility for display systems.
Provides a centralized mechanism to reduce log spam while maintaining
important information and statistics.
"""
import time
from typing import Dict, Any, Tuple, Optional
import threading

class LogThrottler:
    """
    Utility class to manage throttled logging across the display system.
    Tracks message counts and timestamps to reduce log spam while ensuring
    critical information is still captured at appropriate intervals.
    """
    
    def __init__(self):
        """Initialize a new log throttler instance."""
        self._last_log_times = {}
        self._log_counters = {}
        self._last_reset_time = time.time()
        self._reset_interval = 60.0  # Reset counters every minute
        self._lock = threading.RLock()  # Thread safety
        self._stats = {}  # Store statistics by category
        
    def should_log(self, key: str, interval: float = 5.0) -> Tuple[bool, int]:
        """
        Check if we should log for this key based on the interval.
        
        Args:
            key: Unique identifier for this log type
            interval: Minimum seconds between logs for this key
            
        Returns:
            Tuple of (should_log, count_since_last_log)
        """
        with self._lock:
            current_time = time.time()
            
            # Reset counters periodically to prevent memory growth
            if current_time - self._last_reset_time > self._reset_interval:
                # Only reset counters that haven't been used recently
                for k in list(self._log_counters.keys()):
                    if current_time - self._last_log_times.get(k, 0) > self._reset_interval:
                        del self._log_counters[k]
                        if k in self._last_log_times:
                            del self._last_log_times[k]
                self._last_reset_time = current_time
                
            # Initialize counter for this key if not exists
            if key not in self._log_counters:
                self._log_counters[key] = 0
                
            # Count this call
            self._log_counters[key] += 1
            
            # Get stats category from key (before first underscore)
            category = key.split('_')[0] if '_' in key else key
            if category not in self._stats:
                self._stats[category] = 0
            self._stats[category] += 1
                
            # Check if enough time has passed since last log
            last_time = self._last_log_times.get(key, 0)
            if current_time - last_time >= interval:
                self._last_log_times[key] = current_time
                count = self._log_counters[key]
                self._log_counters[key] = 0  # Reset counter
                return True, count
            
            return False, 0
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about throttled logging by category."""
        with self._lock:
            return dict(self._stats)
    
    def reset_counter(self, key: str) -> None:
        """Reset the counter for a specific key."""
        with self._lock:
            self._log_counters[key] = 0
            
    def reset_all_stats(self) -> None:
        """Reset all statistics and counters."""
        with self._lock:
            self._log_counters = {}
            self._last_log_times = {}
            self._stats = {}
            self._last_reset_time = time.time()

# Global throttler instance
_log_throttler = None

def get_log_throttler():
    """Get the global log throttler instance."""
    global _log_throttler
    if _log_throttler is None:
        _log_throttler = LogThrottler()
    return _log_throttler

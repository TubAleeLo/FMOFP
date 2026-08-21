"""
Manual animation timer for holographic display elements
"""
from PyQt6.QtCore import QTimer
import math
import time
import logging

logger = logging.getLogger(__name__)

class ManualAnimationTimer:
    """Provides a fallback animation mechanism for holographic displays"""
    
    def __init__(self, update_interval=50):
        """Initialize manual animation timer
        
        Args:
            update_interval: Update interval in milliseconds (default: 50ms for 20fps)
        """
        self.timer = QTimer()
        self.timer.setInterval(update_interval)
        self.last_update_time = time.time()
        self.running = False
        self.callbacks = {}
        
        # Connect timer to update method
        self.timer.timeout.connect(self._update)
        
    def start(self):
        """Start the animation timer"""
        if not self.running:
            self.last_update_time = time.time()
            self.timer.start()
            self.running = True
            logger.info("Manual animation timer started")
            
    def stop(self):
        """Stop the animation timer"""
        if self.running:
            self.timer.stop()
            self.running = False
            logger.info("Manual animation timer stopped")
            
    def is_running(self):
        """Check if timer is running"""
        return self.running
        
    def add_animation(self, name, update_func, speed=1.0):
        """Add an animation to be updated by the timer
        
        Args:
            name: Unique name for the animation
            update_func: Function to call with updated value (0.0 to 1.0)
            speed: Animation speed multiplier
        """
        self.callbacks[name] = {
            'func': update_func,
            'speed': speed,
            'value': 0.0
        }
        logger.info(f"Added manual animation: {name}")
        
        # Start timer if not already running
        if not self.running:
            self.start()
            
    def remove_animation(self, name):
        """Remove an animation from the timer
        
        Args:
            name: Name of the animation to remove
        """
        if name in self.callbacks:
            del self.callbacks[name]
            logger.info(f"Removed manual animation: {name}")
            
            # Stop timer if no animations left
            if not self.callbacks and self.running:
                self.stop()
                
    def _update(self):
        """Update all animations"""
        # Calculate delta time
        current_time = time.time()
        delta_time = current_time - self.last_update_time
        self.last_update_time = current_time
        
        # Update each animation
        for name, animation in self.callbacks.items():
            # Update animation value (cycle from 0.0 to 1.0)
            animation['value'] = (animation['value'] + delta_time * animation['speed']) % 1.0
            
            # Call update function
            try:
                animation['func'](animation['value'])
            except Exception as e:
                logger.error(f"Error in manual animation callback for {name}: {str(e)}")

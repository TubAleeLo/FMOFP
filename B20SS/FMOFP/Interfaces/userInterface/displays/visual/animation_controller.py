"""
Animation controller for smooth transitions and effects in displays
"""
from PyQt6.QtCore import QTimer, QObject, QEasingCurve
from typing import Dict, Any, Optional, Callable, List, Tuple
import time
import math
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class AnimationProperty:
    """Represents a property being animated"""
    
    def __init__(self, 
                start_value: float, 
                end_value: float, 
                duration: float,
                easing_curve: QEasingCurve.Type = QEasingCurve.Type.OutCubic):
        """Initialize animation property
        
        Args:
            start_value: Starting value
            end_value: Target value
            duration: Duration in seconds
            easing_curve: Easing curve type for animation
        """
        self.start_value = start_value
        self.end_value = end_value
        self.current_value = start_value
        self.duration = max(0.001, duration)  # Ensure non-zero duration
        self.elapsed_time = 0.0
        self.easing_curve = QEasingCurve(easing_curve)
        self.is_complete = False
        
    def update(self, delta_time: float) -> float:
        """Update animation and return current value
        
        Args:
            delta_time: Time elapsed since last update in seconds
            
        Returns:
            Current interpolated value
        """
        if self.is_complete:
            return self.end_value
            
        # Update elapsed time
        self.elapsed_time += delta_time
        
        # Calculate progress (0.0 to 1.0)
        progress = min(self.elapsed_time / self.duration, 1.0)
        
        # Apply easing curve
        eased_progress = self.easing_curve.valueForProgress(progress)
        
        # Calculate current value
        self.current_value = self.start_value + (self.end_value - self.start_value) * eased_progress
        
        # Check if animation is complete
        if progress >= 1.0:
            self.is_complete = True
            self.current_value = self.end_value
            
        return self.current_value

class AnimationController(QObject):
    """Controls animations and transitions for display elements"""
    
    def __init__(self, update_interval: int = 16):
        """Initialize animation controller
        
        Args:
            update_interval: Update interval in milliseconds (default: 16ms for ~60fps)
        """
        super().__init__()
        
        # Animation properties
        self._animations: Dict[str, AnimationProperty] = {}
        self._callbacks: Dict[str, Callable[[float], None]] = {}
        self._completion_callbacks: Dict[str, Callable[[], None]] = {}
        
        # Timer for animation updates
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(update_interval)
        self._update_timer.timeout.connect(self._update_animations)
        
        # Time tracking
        self._last_update_time = time.time()
        self._is_running = False
        
    def start(self):
        """Start animation controller"""
        if not self._is_running:
            self._last_update_time = time.time()
            self._update_timer.start()
            self._is_running = True
            logger.debug("Animation controller started")
            
    def stop(self):
        """Stop animation controller"""
        if self._is_running:
            self._update_timer.stop()
            self._is_running = False
            logger.debug("Animation controller stopped")
            
    def is_running(self) -> bool:
        """Check if animation controller is running"""
        return self._is_running
        
    def has_active_animations(self) -> bool:
        """Check if there are any active animations"""
        return len(self._animations) > 0
        
    def create_animation(self, 
                       property_id: str, 
                       start_value: float, 
                       end_value: float, 
                       duration: float,
                       callback: Callable[[float], None],
                       completion_callback: Optional[Callable[[], None]] = None,
                       easing_curve: QEasingCurve.Type = QEasingCurve.Type.OutCubic) -> bool:
        """Create a new animation
        
        Args:
            property_id: Unique identifier for the animated property
            start_value: Starting value
            end_value: Target value
            duration: Duration in seconds
            callback: Function to call with updated value
            completion_callback: Function to call when animation completes
            easing_curve: Easing curve type for animation
            
        Returns:
            True if animation was created, False if it already exists
        """
        # Check if animation already exists
        if property_id in self._animations:
            logger.warning(f"Animation already exists for property: {property_id}")
            return False
            
        # Create animation property
        self._animations[property_id] = AnimationProperty(
            start_value, 
            end_value, 
            duration,
            easing_curve
        )
        
        # Store callback
        self._callbacks[property_id] = callback
        
        # Store completion callback if provided
        if completion_callback:
            self._completion_callbacks[property_id] = completion_callback
            
        # Ensure controller is running
        if not self._is_running and len(self._animations) > 0:
            self.start()
            
        logger.debug(f"Created animation for property: {property_id}")
        return True
        
    def update_animation(self,
                       property_id: str,
                       end_value: float,
                       duration: float,
                       easing_curve: QEasingCurve.Type = QEasingCurve.Type.OutCubic) -> bool:
        """Update an existing animation with new target value
        
        Args:
            property_id: Unique identifier for the animated property
            end_value: New target value
            duration: New duration in seconds
            easing_curve: New easing curve type
            
        Returns:
            True if animation was updated, False if it doesn't exist
        """
        # Check if animation exists
        if property_id not in self._animations:
            logger.warning(f"Animation doesn't exist for property: {property_id}")
            return False
            
        # Get current value as new start value
        current_value = self._animations[property_id].current_value
        
        # Create new animation property
        self._animations[property_id] = AnimationProperty(
            current_value, 
            end_value, 
            duration,
            easing_curve
        )
        
        # Ensure controller is running
        if not self._is_running:
            self.start()
            
        logger.debug(f"Updated animation for property: {property_id}")
        return True
        
    def cancel_animation(self, property_id: str) -> bool:
        """Cancel an animation
        
        Args:
            property_id: Unique identifier for the animated property
            
        Returns:
            True if animation was cancelled, False if it doesn't exist
        """
        # Check if animation exists
        if property_id not in self._animations:
            logger.warning(f"Animation doesn't exist for property: {property_id}")
            return False
            
        # Remove animation and callbacks
        del self._animations[property_id]
        del self._callbacks[property_id]
        
        if property_id in self._completion_callbacks:
            del self._completion_callbacks[property_id]
            
        # Stop controller if no animations left
        if len(self._animations) == 0:
            self.stop()
            
        logger.debug(f"Cancelled animation for property: {property_id}")
        return True
        
    def cancel_all_animations(self):
        """Cancel all animations"""
        self._animations.clear()
        self._callbacks.clear()
        self._completion_callbacks.clear()
        self.stop()
        logger.debug("Cancelled all animations")
        
    def get_value(self, property_id: str) -> Optional[float]:
        """Get current value of an animated property
        
        Args:
            property_id: Unique identifier for the animated property
            
        Returns:
            Current value or None if property doesn't exist
        """
        if property_id in self._animations:
            return self._animations[property_id].current_value
        return None
        
    def _update_animations(self):
        """Update all active animations"""
        # Calculate delta time
        current_time = time.time()
        delta_time = current_time - self._last_update_time
        self._last_update_time = current_time
        
        # Ensure delta_time is a float (handle case where it might be a dict)
        if not isinstance(delta_time, (int, float)):
            logger.warning(f"delta_time is a {type(delta_time)}, using default value")
            delta_time = 0.016  # ~60 FPS as a safe default
        
        # List of completed animations to remove
        completed = []
        
        # Update each animation
        for property_id, animation in self._animations.items():
            # Update animation
            value = animation.update(delta_time)
            
            # Call callback with updated value
            if property_id in self._callbacks:
                try:
                    self._callbacks[property_id](value)
                except Exception as e:
                    logger.error(f"Error in animation callback for {property_id}: {str(e)}")
            
            # Check if animation is complete
            if animation.is_complete:
                completed.append(property_id)
                
                # Call completion callback if exists
                if property_id in self._completion_callbacks:
                    try:
                        self._completion_callbacks[property_id]()
                    except Exception as e:
                        logger.error(f"Error in animation completion callback for {property_id}: {str(e)}")
        
        # Remove completed animations
        for property_id in completed:
            del self._animations[property_id]
            del self._callbacks[property_id]
            
            if property_id in self._completion_callbacks:
                del self._completion_callbacks[property_id]
        
        # Stop controller if no animations left
        if len(self._animations) == 0:
            self.stop()

class TransitionGroup:
    """Group of related animations that can be controlled together"""
    
    def __init__(self, controller: AnimationController, group_id: str):
        """Initialize transition group
        
        Args:
            controller: Animation controller to use
            group_id: Unique identifier for the group
        """
        self.controller = controller
        self.group_id = group_id
        self.property_ids: List[str] = []
        self.is_complete = True
        self._completion_callback: Optional[Callable[[], None]] = None
        self._properties_completed = 0
        
    def add_transition(self, 
                     property_name: str, 
                     start_value: float, 
                     end_value: float, 
                     duration: float,
                     callback: Callable[[float], None],
                     easing_curve: QEasingCurve.Type = QEasingCurve.Type.OutCubic) -> str:
        """Add a transition to the group
        
        Args:
            property_name: Name of the property (will be prefixed with group_id)
            start_value: Starting value
            end_value: Target value
            duration: Duration in seconds
            callback: Function to call with updated value
            easing_curve: Easing curve type for animation
            
        Returns:
            Full property ID
        """
        # Create unique property ID
        property_id = f"{self.group_id}.{property_name}"
        
        # Add to property list
        self.property_ids.append(property_id)
        
        # Create animation with completion tracking
        self.controller.create_animation(
            property_id,
            start_value,
            end_value,
            duration,
            callback,
            lambda: self._on_property_complete(),
            easing_curve
        )
        
        # Group is now active
        self.is_complete = False
        
        return property_id
        
    def set_completion_callback(self, callback: Callable[[], None]):
        """Set callback to be called when all transitions complete
        
        Args:
            callback: Function to call when all transitions complete
        """
        self._completion_callback = callback
        
    def cancel(self):
        """Cancel all transitions in the group"""
        for property_id in self.property_ids:
            self.controller.cancel_animation(property_id)
            
        self.property_ids.clear()
        self.is_complete = True
        self._properties_completed = 0
        
    def _on_property_complete(self):
        """Called when a property animation completes"""
        self._properties_completed += 1
        
        # Check if all properties are complete
        if self._properties_completed >= len(self.property_ids):
            self.is_complete = True
            
            # Call completion callback if set
            if self._completion_callback:
                try:
                    self._completion_callback()
                except Exception as e:
                    logger.error(f"Error in transition group completion callback: {str(e)}")

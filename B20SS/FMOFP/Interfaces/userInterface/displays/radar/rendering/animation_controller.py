"""
Advanced animation controller for weather radar visualization.

This module provides a more sophisticated animation system for weather radar
visualization, including temporal buffering, animation phases, and configurable
animation parameters.
"""
from PyQt6.QtCore import QTimer, QObject, pyqtSignal, QRectF
from typing import Dict, Any, List, Tuple, Optional, Callable
import time
import math
import random
import copy
import uuid
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class AnimationPhase:
    """Represents a specific phase in a weather animation sequence."""
    
    def __init__(self, name: str, duration: float, transition_duration: float = 0.5):
        """
        Initialize an animation phase.
        
        Args:
            name: Unique name for this phase
            duration: Duration of this phase in seconds
            transition_duration: Duration of transition to next phase in seconds
        """
        self.name = name
        self.duration = duration
        self.transition_duration = transition_duration
        self.start_time: Optional[float] = None
        self.is_active = False
        self.is_transitioning = False
        self.transition_start_time: Optional[float] = None
        self.transition_progress = 0.0  # 0.0 to 1.0
        self.next_phase: Optional[AnimationPhase] = None
        
    def start(self, current_time: float):
        """Start this animation phase."""
        self.start_time = current_time
        self.is_active = True
        self.is_transitioning = False
        
    def update(self, current_time: float) -> Tuple[bool, float]:
        """
        Update this animation phase based on current time.
        
        Args:
            current_time: Current system time
            
        Returns:
            Tuple of (is_complete, progress)
            - is_complete: True if phase is complete
            - progress: Progress through this phase (0.0 to 1.0)
        """
        if not self.is_active or self.start_time is None:
            return False, 0.0
            
        elapsed = current_time - self.start_time
        
        # Check if we should start transitioning
        if not self.is_transitioning and elapsed >= (self.duration - self.transition_duration):
            self.is_transitioning = True
            self.transition_start_time = current_time
            
        # Update transition progress if transitioning
        if self.is_transitioning and self.transition_start_time is not None:
            transition_elapsed = current_time - self.transition_start_time
            self.transition_progress = min(1.0, transition_elapsed / self.transition_duration)
            
        # Check if phase is complete
        is_complete = elapsed >= self.duration
        
        # Calculate overall progress through this phase
        progress = min(1.0, elapsed / self.duration)
        
        return is_complete, progress
        
    def get_transition_progress(self) -> float:
        """Get the current transition progress (0.0 to 1.0)."""
        return self.transition_progress


class AnimationSequence:
    """Manages a sequence of animation phases."""
    
    def __init__(self, name: str, loop: bool = True):
        """
        Initialize an animation sequence.
        
        Args:
            name: Unique name for this sequence
            loop: Whether to loop the sequence when complete
        """
        self.name = name
        self.phases: List[AnimationPhase] = []
        self.current_phase_index = 0
        self.loop = loop
        self.is_active = False
        self.is_complete = False
        
    def add_phase(self, phase: AnimationPhase):
        """Add a phase to this sequence."""
        self.phases.append(phase)
        
        # Link phases for transitions
        if len(self.phases) > 1:
            self.phases[-2].next_phase = phase
            
        # If looping, link last phase to first
        if self.loop and len(self.phases) > 1:
            self.phases[-1].next_phase = self.phases[0]
            
    def start(self, current_time: float):
        """Start this animation sequence."""
        if not self.phases:
            logger.warning("[ANIMATION] Cannot start empty animation sequence")
            return
            
        self.is_active = True
        self.is_complete = False
        self.current_phase_index = 0
        self.phases[0].start(current_time)
        
    def update(self, current_time: float) -> Tuple[str, float, float]:
        """
        Update this animation sequence based on current time.
        
        Args:
            current_time: Current system time
            
        Returns:
            Tuple of (current_phase_name, phase_progress, transition_progress)
        """
        if not self.is_active or not self.phases:
            return "", 0.0, 0.0
            
        current_phase = self.phases[self.current_phase_index]
        is_complete, progress = current_phase.update(current_time)
        
        if is_complete:
            # Move to next phase
            self.current_phase_index += 1
            
            # Check if sequence is complete
            if self.current_phase_index >= len(self.phases):
                if self.loop:
                    # Loop back to beginning
                    self.current_phase_index = 0
                    self.phases[0].start(current_time)
                else:
                    # Mark sequence as complete
                    self.is_active = False
                    self.is_complete = True
                    return current_phase.name, progress, current_phase.transition_progress
            else:
                # Start next phase
                self.phases[self.current_phase_index].start(current_time)
                
        return current_phase.name, progress, current_phase.transition_progress


class TemporalBuffer:
    """
    Manages temporal data for weather visualization.
    
    This buffer stores multiple frames of weather data to enable
    smooth transitions, interpolation, and temporal effects.
    """
    
    def __init__(self, max_frames: int = 10, frame_duration: float = 0.1):
        """
        Initialize the temporal buffer.
        
        Args:
            max_frames: Maximum number of frames to store
            frame_duration: Target duration between frames in seconds
        """
        self.max_frames = max_frames
        self.frame_duration = frame_duration
        self.frames: List[Dict[str, Any]] = []
        self.last_frame_time = 0.0
        
    def add_frame(self, frame_data: Dict[str, Any], current_time: float) -> bool:
        """
        Add a new frame to the buffer if enough time has passed.
        
        Args:
            frame_data: Data for this frame
            current_time: Current system time
            
        Returns:
            True if frame was added, False otherwise
        """
        # Check if enough time has passed since last frame
        if current_time - self.last_frame_time < self.frame_duration:
            return False
            
        # Add timestamp to frame data
        frame_with_time = copy.deepcopy(frame_data)
        frame_with_time['timestamp'] = current_time
        
        # Add frame to buffer
        self.frames.append(frame_with_time)
        
        # Remove oldest frames if buffer is full
        while len(self.frames) > self.max_frames:
            self.frames.pop(0)
            
        self.last_frame_time = current_time
        return True
        
    def get_frame(self, index: int = -1) -> Optional[Dict[str, Any]]:
        """
        Get a specific frame from the buffer.
        
        Args:
            index: Frame index (-1 for most recent)
            
        Returns:
            Frame data or None if index is invalid
        """
        if not self.frames or index >= len(self.frames) or abs(index) > len(self.frames):
            return None
            
        return self.frames[index]
        
    def get_interpolated_frame(self, time_offset: float) -> Optional[Dict[str, Any]]:
        """
        Get an interpolated frame at a specific time offset from the most recent frame.
        
        Args:
            time_offset: Time offset in seconds (negative for past frames)
            
        Returns:
            Interpolated frame data or None if interpolation is not possible
        """
        if not self.frames:
            return None
            
        # Get current time from most recent frame
        current_time = self.frames[-1]['timestamp']
        target_time = current_time + time_offset
        
        # Find frames that bracket the target time
        frame1 = None
        frame2 = None
        
        for i in range(len(self.frames) - 1):
            if (self.frames[i]['timestamp'] <= target_time and 
                self.frames[i+1]['timestamp'] >= target_time):
                frame1 = self.frames[i]
                frame2 = self.frames[i+1]
                break
                
        if not frame1 or not frame2:
            # No bracketing frames found, return closest frame
            if target_time <= self.frames[0]['timestamp']:
                return self.frames[0]
            elif target_time >= self.frames[-1]['timestamp']:
                return self.frames[-1]
            else:
                # This shouldn't happen if we checked all pairs
                return self.frames[-1]
                
        # Calculate interpolation factor
        time_range = frame2['timestamp'] - frame1['timestamp']
        if time_range <= 0:
            return frame1  # Avoid division by zero
            
        factor = (target_time - frame1['timestamp']) / time_range
        
        # Interpolate between frames
        return self._interpolate_frames(frame1, frame2, factor)
        
    def _interpolate_frames(self, frame1: Dict[str, Any], frame2: Dict[str, Any], 
                           factor: float) -> Dict[str, Any]:
        """
        Interpolate between two frames.
        
        Args:
            frame1: First frame
            frame2: Second frame
            factor: Interpolation factor (0.0 to 1.0)
            
        Returns:
            Interpolated frame
        """
        result = {}
        
        # Copy non-interpolatable fields from frame2
        for key in frame2:
            if key not in ['precipitation', 'vil', 'cells', 'timestamp']:
                result[key] = frame2[key]
                
        # Set timestamp
        result['timestamp'] = frame1['timestamp'] + factor * (frame2['timestamp'] - frame1['timestamp'])
        
        # Interpolate precipitation data
        result['precipitation'] = self._interpolate_weather_data(
            frame1.get('precipitation', []),
            frame2.get('precipitation', []),
            factor
        )
        
        # Interpolate VIL data
        result['vil'] = self._interpolate_weather_data(
            frame1.get('vil', []),
            frame2.get('vil', []),
            factor
        )
        
        # Interpolate cell data
        result['cells'] = self._interpolate_weather_data(
            frame1.get('cells', []),
            frame2.get('cells', []),
            factor
        )
        
        return result
        
    def _interpolate_weather_data(self, data1: List[Dict[str, Any]], 
                                 data2: List[Dict[str, Any]], 
                                 factor: float) -> List[Dict[str, Any]]:
        """
        Interpolate between two sets of weather data.
        
        Args:
            data1: First data set
            data2: Second data set
            factor: Interpolation factor (0.0 to 1.0)
            
        Returns:
            Interpolated data
        """
        # Create dictionaries keyed by ID for easier matching
        data1_dict = {item.get('id', str(i)): item for i, item in enumerate(data1)}
        data2_dict = {item.get('id', str(i)): item for i, item in enumerate(data2)}
        
        result = []
        
        # Process items in both data sets
        all_ids = set(data1_dict.keys()) | set(data2_dict.keys())
        
        for item_id in all_ids:
            if item_id in data1_dict and item_id in data2_dict:
                # Item exists in both data sets, interpolate
                item1 = data1_dict[item_id]
                item2 = data2_dict[item_id]
                
                # Create interpolated item
                interpolated_item = {}
                
                # Copy non-interpolatable fields from item2
                for key in item2:
                    if key not in ['position', 'value', 'intensity', 'rate', 'x', 'y']:
                        interpolated_item[key] = item2[key]
                
                # Interpolate position
                if 'position' in item1 and 'position' in item2:
                    pos1 = item1['position']
                    pos2 = item2['position']
                    
                    if isinstance(pos1, (list, tuple)) and isinstance(pos2, (list, tuple)):
                        interpolated_item['position'] = (
                            pos1[0] + factor * (pos2[0] - pos1[0]),
                            pos1[1] + factor * (pos2[1] - pos1[1])
                        )
                
                # Interpolate x, y coordinates
                if 'x' in item1 and 'x' in item2:
                    interpolated_item['x'] = item1['x'] + factor * (item2['x'] - item1['x'])
                if 'y' in item1 and 'y' in item2:
                    interpolated_item['y'] = item1['y'] + factor * (item2['y'] - item1['y'])
                
                # Interpolate numeric values
                for key in ['value', 'intensity', 'rate']:
                    if key in item1 and key in item2:
                        interpolated_item[key] = item1[key] + factor * (item2[key] - item1[key])
                
                result.append(interpolated_item)
                
            elif item_id in data2_dict:
                # Item only exists in data2, use it directly with reduced opacity
                item = copy.deepcopy(data2_dict[item_id])
                
                # Fade in based on factor
                if 'opacity' in item:
                    item['opacity'] = item['opacity'] * factor
                if 'intensity' in item:
                    item['intensity'] = item['intensity'] * factor
                    
                result.append(item)
                
            elif item_id in data1_dict:
                # Item only exists in data1, use it directly with reduced opacity
                item = copy.deepcopy(data1_dict[item_id])
                
                # Fade out based on factor
                if 'opacity' in item:
                    item['opacity'] = item['opacity'] * (1.0 - factor)
                if 'intensity' in item:
                    item['intensity'] = item['intensity'] * (1.0 - factor)
                    
                result.append(item)
        
        return result


class AnimationController(QObject):
    """
    Advanced animation controller for weather radar visualization.
    
    This controller manages animation sequences, temporal buffering,
    and provides configurable animation parameters.
    """
    
    # Signal emitted when animation state changes
    animation_updated = pyqtSignal(dict)
    
    def __init__(self):
        """Initialize the animation controller."""
        super().__init__()
        
        # Animation parameters
        self.params = {
            'wind_speed': 20.0,  # pixels per second
            'wind_direction': 45.0,  # degrees (0 = east, 90 = north)
            'turbulence': 0.2,  # random movement factor
            'fade_duration': 2.0,  # seconds for fade in/out
            'particle_lifetime': 4.0,  # seconds
            'particle_count_factor': 1.0,  # multiplier for particle counts
            'animation_speed': 1.0,  # overall speed multiplier
            'enable_temporal_effects': True,  # enable temporal buffer
            'enable_advanced_animation': True,  # enable animation sequences
        }
        
        # Animation sequences
        self.sequences: Dict[str, AnimationSequence] = {}
        self.active_sequence: Optional[AnimationSequence] = None
        
        # Temporal buffer
        self.temporal_buffer = TemporalBuffer(max_frames=20, frame_duration=0.1)
        
        # Animation timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_animation)
        self.timer.start(16)  # ~60 FPS
        
        # Wind vector
        self._update_wind_vector()
        
        # Last update time
        self.last_update_time = time.time()
        
        # Create default animation sequences
        self._create_default_sequences()
        
        logger.info("[ANIMATION] Advanced animation controller initialized")
        
    def _create_default_sequences(self):
        """Create default animation sequences."""
        # Standard weather sequence
        standard_seq = AnimationSequence("standard", loop=True)
        
        # Add phases
        standard_seq.add_phase(AnimationPhase("normal", 10.0, 1.0))
        standard_seq.add_phase(AnimationPhase("intensify", 5.0, 1.0))
        standard_seq.add_phase(AnimationPhase("peak", 3.0, 1.0))
        standard_seq.add_phase(AnimationPhase("dissipate", 7.0, 1.0))
        
        self.sequences["standard"] = standard_seq
        
        # Storm cell sequence
        storm_seq = AnimationSequence("storm", loop=True)
        
        # Add phases
        storm_seq.add_phase(AnimationPhase("formation", 8.0, 1.0))
        storm_seq.add_phase(AnimationPhase("intensification", 6.0, 1.0))
        storm_seq.add_phase(AnimationPhase("mature", 10.0, 1.0))
        storm_seq.add_phase(AnimationPhase("dissipation", 12.0, 1.0))
        
        self.sequences["storm"] = storm_seq
        
        # Set default active sequence
        self.active_sequence = self.sequences["standard"]
        self.active_sequence.start(time.time())
        
    def set_parameter(self, name: str, value: Any):
        """
        Set an animation parameter.
        
        Args:
            name: Parameter name
            value: Parameter value
        """
        if name in self.params:
            self.params[name] = value
            
            # Update wind vector if related parameters changed
            if name in ['wind_speed', 'wind_direction']:
                self._update_wind_vector()
                
            logger.info(f"[ANIMATION] Set parameter {name} = {value}")
        else:
            logger.warning(f"[ANIMATION] Unknown parameter: {name}")
            
    def get_parameter(self, name: str) -> Any:
        """
        Get an animation parameter.
        
        Args:
            name: Parameter name
            
        Returns:
            Parameter value or None if not found
        """
        return self.params.get(name)
        
    def get_all_parameters(self) -> Dict[str, Any]:
        """
        Get all animation parameters.
        
        Returns:
            Dictionary of all parameters
        """
        return self.params.copy()
        
    def set_active_sequence(self, name: str):
        """
        Set the active animation sequence.
        
        Args:
            name: Sequence name
        """
        if name in self.sequences:
            self.active_sequence = self.sequences[name]
            self.active_sequence.start(time.time())
            logger.info(f"[ANIMATION] Set active sequence: {name}")
        else:
            logger.warning(f"[ANIMATION] Unknown sequence: {name}")
            
    def add_frame(self, frame_data: Dict[str, Any]):
        """
        Add a frame to the temporal buffer.
        
        Args:
            frame_data: Data for this frame
        """
        if self.params['enable_temporal_effects']:
            self.temporal_buffer.add_frame(frame_data, time.time())
            
    def get_current_frame(self) -> Optional[Dict[str, Any]]:
        """
        Get the current frame from the temporal buffer.
        
        Returns:
            Current frame data or None if not available
        """
        if self.params['enable_temporal_effects']:
            return self.temporal_buffer.get_frame()
        return None
        
    def get_interpolated_frame(self, time_offset: float) -> Optional[Dict[str, Any]]:
        """
        Get an interpolated frame at a specific time offset.
        
        Args:
            time_offset: Time offset in seconds
            
        Returns:
            Interpolated frame data or None if not available
        """
        if self.params['enable_temporal_effects']:
            return self.temporal_buffer.get_interpolated_frame(time_offset)
        return None
        
    def _update_animation(self):
        """Update animation state."""
        current_time = time.time()
        dt = current_time - self.last_update_time
        self.last_update_time = current_time
        
        # Update active sequence
        if self.active_sequence and self.params['enable_advanced_animation']:
            phase_name, phase_progress, transition_progress = self.active_sequence.update(current_time)
            
            # Emit animation update signal
            self.animation_updated.emit({
                'phase_name': phase_name,
                'phase_progress': phase_progress,
                'transition_progress': transition_progress,
                'wind_vector': self.get_wind_vector(),
                'turbulence': self.params['turbulence'] * self.params['animation_speed'],
                'dt': dt * self.params['animation_speed']
            })
            
    def _update_wind_vector(self):
        """Update the wind vector based on speed and direction."""
        # Convert direction from degrees to radians
        # 0 degrees = east, 90 degrees = north
        direction_rad = math.radians(self.params['wind_direction'])
        
        # Calculate normalized vector components
        self._wind_vector = (
            math.cos(direction_rad),  # x component
            -math.sin(direction_rad)  # y component (negative because y increases downward in screen coordinates)
        )
        
    def get_wind_vector(self) -> Tuple[float, float]:
        """
        Get the current wind vector.
        
        Returns:
            Tuple of (x, y) normalized direction
        """
        # Apply speed and animation speed
        speed = self.params['wind_speed'] * self.params['animation_speed']
        return (
            self._wind_vector[0] * speed,
            self._wind_vector[1] * speed
        )
        
    def get_turbulence_offset(self) -> Tuple[float, float]:
        """
        Get a random turbulence offset.
        
        Returns:
            Tuple of (x, y) offset
        """
        turbulence = self.params['turbulence'] * self.params['animation_speed']
        return (
            random.uniform(-turbulence, turbulence),
            random.uniform(-turbulence, turbulence)
        )
        
    def get_animation_state(self) -> Dict[str, Any]:
        """
        Get the current animation state.
        
        Returns:
            Dictionary with animation state
        """
        if not self.active_sequence:
            return {
                'phase_name': '',
                'phase_progress': 0.0,
                'transition_progress': 0.0,
                'wind_vector': self.get_wind_vector(),
                'turbulence': self.params['turbulence'],
                'dt': 0.0
            }
            
        phase_name, phase_progress, transition_progress = self.active_sequence.update(time.time())
        
        return {
            'phase_name': phase_name,
            'phase_progress': phase_progress,
            'transition_progress': transition_progress,
            'wind_vector': self.get_wind_vector(),
            'turbulence': self.params['turbulence'],
            'dt': 0.0
        }


# Singleton instance
_animation_controller = None

def get_animation_controller() -> AnimationController:
    """
    Get the singleton animation controller instance.
    
    Returns:
        AnimationController instance
    """
    global _animation_controller
    if _animation_controller is None:
        _animation_controller = AnimationController()
    return _animation_controller

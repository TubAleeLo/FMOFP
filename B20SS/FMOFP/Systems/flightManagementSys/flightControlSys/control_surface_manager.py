"""
Control Surface Manager

Manages aircraft control surfaces for the Flight Control System.
"""

import math
import time
from typing import Dict, Any, List, Optional

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class ControlSurfaceManager:
    """
    Control Surface Manager for the Flight Control System.
    
    This component manages the control surfaces of the aircraft, including:
    - Converting control inputs to surface positions
    - Applying control limits and protections
    - Modeling control surface dynamics and actuator characteristics
    - Handling control surface degradation and failures
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Control Surface Manager.
        
        Args:
            config: Configuration dictionary with control surface parameters
        """
        self.config = config or self._get_default_config()
        
        # Control surface positions
        self.surface_positions = {
            # Primary surfaces
            'left_aileron': 0.0,    # -1.0 (down) to 1.0 (up)
            'right_aileron': 0.0,   # -1.0 (down) to 1.0 (up)
            'elevator': 0.0,        # -1.0 (down) to 1.0 (up) 
            'rudder': 0.0,          # -1.0 (left) to 1.0 (right)
            
            # Secondary surfaces
            'left_flap': 0.0,       # 0.0 (retracted) to 1.0 (extended)
            'right_flap': 0.0,      # 0.0 (retracted) to 1.0 (extended)
            'left_slat': 0.0,       # 0.0 (retracted) to 1.0 (extended)
            'right_slat': 0.0,      # 0.0 (retracted) to 1.0 (extended)
            'left_spoiler': 0.0,    # 0.0 (retracted) to 1.0 (extended)
            'right_spoiler': 0.0,   # 0.0 (retracted) to 1.0 (extended)
            'airbrake': 0.0,        # 0.0 (retracted) to 1.0 (extended)
        }
        
        # Trim tab positions
        self.trim_positions = {
            'aileron_trim': 0.0,    # -1.0 to 1.0
            'elevator_trim': 0.0,   # -1.0 to 1.0
            'rudder_trim': 0.0,     # -1.0 to 1.0
        }
        
        # Surface health status (1.0 = fully operational, 0.0 = failed)
        self.surface_health = {
            'left_aileron': 1.0,
            'right_aileron': 1.0,
            'elevator': 1.0,
            'rudder': 1.0,
            'left_flap': 1.0,
            'right_flap': 1.0,
            'left_slat': 1.0,
            'right_slat': 1.0,
            'left_spoiler': 1.0,
            'right_spoiler': 1.0,
            'airbrake': 1.0,
        }
        
        # Control surface actuator characteristics
        self.actuator_params = {
            'rate_limits': {
                'aileron': 80.0,    # degrees per second
                'elevator': 60.0,   # degrees per second
                'rudder': 40.0,     # degrees per second
                'flap': 5.0,        # degrees per second
                'slat': 3.0,        # degrees per second
                'spoiler': 20.0,    # degrees per second
                'airbrake': 10.0,   # degrees per second
            },
            'time_constants': {
                'aileron': 0.05,    # seconds
                'elevator': 0.05,   # seconds
                'rudder': 0.05,     # seconds
                'flap': 0.5,        # seconds
                'slat': 0.5,        # seconds
                'spoiler': 0.1,     # seconds
                'airbrake': 0.2,    # seconds
            },
            'max_deflections': {
                'aileron': 30.0,    # degrees
                'elevator': 25.0,   # degrees
                'rudder': 20.0,     # degrees
                'flap': 45.0,       # degrees
                'slat': 20.0,       # degrees
                'spoiler': 60.0,    # degrees
                'airbrake': 60.0,   # degrees
            }
        }
        
        # Actuator state (command, position, rate)
        self.actuator_state = {}
        for surface in self.surface_positions:
            self.actuator_state[surface] = {
                'command': 0.0,     # Commanded position (normalized)
                'position': 0.0,    # Current position (normalized)
                'rate': 0.0,        # Current rate (normalized/second)
                'last_update': time.time()
            }
        
        logger.info("[FCS_CONTROL] Control Surface Manager initialized")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'use_simplified_model': True,      # Use simplified actuator model
            'enforce_limits': True,            # Enforce control limits
            'apply_envelope_protection': True, # Apply flight envelope protection
            'differential_aileron': True,      # Use differential aileron (more up than down)
            'enable_failures': False,          # Enable simulated failures
            'failure_probability': 0.0001,     # Probability of failure per hour
        }
    
    def set_control_positions(self, control_inputs: Dict[str, float], 
                             aircraft_state: Dict[str, Any]) -> Dict[str, float]:
        """
        Set control surface positions based on control inputs and aircraft state.
        
        Args:
            control_inputs: Control inputs (-1.0 to 1.0)
            aircraft_state: Current aircraft state
            
        Returns:
            Dictionary of surface positions (-1.0 to 1.0)
        """
        try:
            # Extract control inputs
            aileron_input = control_inputs.get('aileron', 0.0)
            elevator_input = control_inputs.get('elevator', 0.0)
            rudder_input = control_inputs.get('rudder', 0.0)
            throttle_input = control_inputs.get('throttle', 0.5)
            
            # Extract trim positions
            aileron_trim = self.trim_positions.get('aileron_trim', 0.0)
            elevator_trim = self.trim_positions.get('elevator_trim', 0.0)
            rudder_trim = self.trim_positions.get('rudder_trim', 0.0)
            
            # Apply trim to control inputs
            aileron_command = aileron_input + aileron_trim
            elevator_command = elevator_input + elevator_trim
            rudder_command = rudder_input + rudder_trim
            
            # Apply flight envelope protection if enabled
            if self.config.get('apply_envelope_protection', True):
                aileron_command, elevator_command, rudder_command = self._apply_envelope_protection(
                    aileron_command, elevator_command, rudder_command, aircraft_state
                )
            
            # Apply control limits
            if self.config.get('enforce_limits', True):
                aileron_command = max(-1.0, min(1.0, aileron_command))
                elevator_command = max(-1.0, min(1.0, elevator_command))
                rudder_command = max(-1.0, min(1.0, rudder_command))
            
            # Set aileron positions (differential aileron if enabled)
            if self.config.get('differential_aileron', True):
                # Differential aileron logic: more deflection upward than downward
                if aileron_command > 0:
                    # Right roll: left aileron up, right aileron down
                    left_aileron = aileron_command
                    right_aileron = -aileron_command * 0.7  # 70% down deflection
                else:
                    # Left roll: left aileron down, right aileron up
                    left_aileron = aileron_command * 0.7    # 70% down deflection
                    right_aileron = -aileron_command
            else:
                # Standard aileron
                left_aileron = aileron_command
                right_aileron = -aileron_command
            
            # Update commanded positions
            self.actuator_state['left_aileron']['command'] = left_aileron
            self.actuator_state['right_aileron']['command'] = right_aileron
            self.actuator_state['elevator']['command'] = elevator_command
            self.actuator_state['rudder']['command'] = rudder_command
            
            # Handle flaps, slats, spoilers, and airbrake based on aircraft configuration
            # For now, we'll keep them at their current positions
            # In a full implementation, these would be set based on aircraft speed,
            # altitude, and configuration (takeoff, landing, etc.)
            
            # Return current surface positions
            return self.surface_positions.copy()
            
        except Exception as e:
            logger.error(f"[FCS_CONTROL] Error setting control positions: {e}")
            # Return current positions on error to avoid crashes
            return self.surface_positions.copy()
    
    def update_actuators(self, dt: float) -> Dict[str, float]:
        """
        Update actuator positions based on commanded positions and dynamics.
        
        Args:
            dt: Time step in seconds
            
        Returns:
            Updated surface positions
        """
        try:
            # Update each actuator based on its dynamics
            current_time = time.time()
            
            for surface, state in self.actuator_state.items():
                # Calculate elapsed time since last update
                elapsed = current_time - state['last_update']
                if elapsed <= 0:
                    continue
                    
                # Get actuator parameters based on surface type
                surface_type = self._get_surface_type(surface)
                rate_limit = self.actuator_params['rate_limits'].get(surface_type, 60.0)
                time_constant = self.actuator_params['time_constants'].get(surface_type, 0.05)
                
                # Convert to normalized rate (per second)
                normalized_rate_limit = rate_limit / self.actuator_params['max_deflections'].get(surface_type, 30.0)
                
                # Calculate target position and error
                target = state['command']
                current = state['position']
                error = target - current
                
                if abs(error) < 0.001:
                    # Already at target
                    state['rate'] = 0.0
                else:
                    # Calculate desired rate with first-order response
                    desired_rate = error / time_constant
                    
                    # Apply rate limiting
                    state['rate'] = max(-normalized_rate_limit, 
                                       min(normalized_rate_limit, desired_rate))
                
                # Apply health factor to rate
                if surface in self.surface_health:
                    state['rate'] *= self.surface_health[surface]
                
                # Update position
                state['position'] += state['rate'] * elapsed
                
                # Apply position limits
                state['position'] = max(-1.0, min(1.0, state['position']))
                
                # Update surface position
                self.surface_positions[surface] = state['position']
                
                # Update last update time
                state['last_update'] = current_time
            
            # Check for random failures if enabled
            if self.config.get('enable_failures', False):
                self._check_for_failures(dt)
            
            # Return current surface positions
            return self.surface_positions.copy()
            
        except Exception as e:
            logger.error(f"[FCS_CONTROL] Error updating actuators: {e}")
            # Return current positions on error to avoid crashes
            return self.surface_positions.copy()
    
    def set_trim(self, trim_type: str, value: float) -> bool:
        """
        Set a trim value.
        
        Args:
            trim_type: Type of trim ('aileron_trim', 'elevator_trim', 'rudder_trim')
            value: Trim value (-1.0 to 1.0)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if trim_type not in self.trim_positions:
                logger.warning(f"[FCS_CONTROL] Invalid trim type: {trim_type}")
                return False
            
            # Apply limits
            value = max(-1.0, min(1.0, value))
            
            # Set trim value
            self.trim_positions[trim_type] = value
            logger.info(f"[FCS_CONTROL] {trim_type} set to {value}")
            
            return True
        except Exception as e:
            logger.error(f"[FCS_CONTROL] Error setting trim: {e}")
            return False
    
    def set_surface_health(self, surface: str, health: float) -> bool:
        """
        Set health status for a control surface.
        
        Args:
            surface: Surface name
            health: Health factor (0.0 to 1.0)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if surface not in self.surface_health:
                logger.warning(f"[FCS_CONTROL] Invalid surface: {surface}")
                return False
            
            # Apply limits
            health = max(0.0, min(1.0, health))
            
            # Set health value
            self.surface_health[surface] = health
            logger.info(f"[FCS_CONTROL] {surface} health set to {health}")
            
            return True
        except Exception as e:
            logger.error(f"[FCS_CONTROL] Error setting surface health: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get control surface status.
        
        Returns:
            Dictionary with surface positions, trim positions, and health status
        """
        return {
            'surface_positions': self.surface_positions.copy(),
            'trim_positions': self.trim_positions.copy(),
            'surface_health': self.surface_health.copy()
        }
    
    def _apply_envelope_protection(self, aileron: float, elevator: float, rudder: float, 
                                  aircraft_state: Dict[str, Any]) -> tuple:
        """
        Apply flight envelope protection to control inputs.
        
        Args:
            aileron: Aileron command (-1.0 to 1.0)
            elevator: Elevator command (-1.0 to 1.0)
            rudder: Rudder command (-1.0 to 1.0)
            aircraft_state: Current aircraft state
            
        Returns:
            Tuple of (aileron, elevator, rudder) commands with protection applied
        """
        # Extract aircraft state
        roll = aircraft_state.get('roll', 0.0)
        pitch = aircraft_state.get('pitch', 0.0)
        alpha = aircraft_state.get('alpha', 0.0)
        beta = aircraft_state.get('beta', 0.0)
        g_force = aircraft_state.get('g_force', 1.0)
        
        # Protection parameters
        max_roll_angle = 60.0  # degrees
        max_pitch_angle = 30.0  # degrees
        min_pitch_angle = -15.0  # degrees
        max_alpha = 15.0  # degrees
        min_alpha = -5.0  # degrees
        max_beta = 10.0  # degrees
        max_g = 9.0  # g
        min_g = -3.0  # g
        
        # Roll protection
        if abs(roll) > max_roll_angle:
            # If roll exceeds limit, reduce aileron input in the direction of roll
            if (roll > 0 and aileron > 0) or (roll < 0 and aileron < 0):
                # Scale down aileron based on how far over the limit we are
                factor = 1.0 - min(1.0, (abs(roll) - max_roll_angle) / 10.0)
                aileron *= factor
        
        # Pitch/alpha protection
        if pitch > max_pitch_angle or alpha > max_alpha or g_force > max_g:
            # If pitch or alpha exceeds upper limit, reduce pull-up elevator input
            if elevator < 0:  # Remember: negative elevator is pull up
                factor = 1.0 - min(1.0, max(
                    (pitch - max_pitch_angle) / 10.0 if pitch > max_pitch_angle else 0,
                    (alpha - max_alpha) / 5.0 if alpha > max_alpha else 0,
                    (g_force - max_g) / 2.0 if g_force > max_g else 0
                ))
                elevator *= factor
        
        if pitch < min_pitch_angle or alpha < min_alpha or g_force < min_g:
            # If pitch or alpha exceeds lower limit, reduce push-down elevator input
            if elevator > 0:  # Positive elevator is push down
                factor = 1.0 - min(1.0, max(
                    (min_pitch_angle - pitch) / 10.0 if pitch < min_pitch_angle else 0,
                    (min_alpha - alpha) / 5.0 if alpha < min_alpha else 0,
                    (min_g - g_force) / 2.0 if g_force < min_g else 0
                ))
                elevator *= factor
        
        # Beta/sideslip protection
        if abs(beta) > max_beta:
            # If sideslip exceeds limit, reduce rudder input in the same direction
            if (beta > 0 and rudder > 0) or (beta < 0 and rudder < 0):
                factor = 1.0 - min(1.0, (abs(beta) - max_beta) / 5.0)
                rudder *= factor
        
        return aileron, elevator, rudder
    
    def _check_for_failures(self, dt: float):
        """
        Check for random control surface failures.
        
        Args:
            dt: Time step in seconds
        """
        # Calculate failure probability for this time step
        failure_prob = self.config.get('failure_probability', 0.0001) * dt / 3600.0
        
        # Check each surface
        for surface in self.surface_health:
            # Only check healthy or partially degraded surfaces
            if self.surface_health[surface] > 0:
                # Random failure check
                if random.random() < failure_prob:
                    # Determine severity (complete failure or partial degradation)
                    if random.random() < 0.3:  # 30% chance of complete failure
                        self.surface_health[surface] = 0.0
                        logger.warning(f"[FCS_CONTROL] {surface} complete failure!")
                    else:
                        # Partial degradation (random: 0.3 to 0.9 of current health)
                        degradation = 0.3 + random.random() * 0.6
                        self.surface_health[surface] *= degradation
                        logger.warning(f"[FCS_CONTROL] {surface} degraded to {self.surface_health[surface]:.2f}!")
    
    def _get_surface_type(self, surface: str) -> str:
        """
        Get the type of a control surface for parameter lookup.
        
        Args:
            surface: The surface name
            
        Returns:
            The surface type for parameter lookup
        """
        if 'aileron' in surface:
            return 'aileron'
        elif 'elevator' in surface:
            return 'elevator'
        elif 'rudder' in surface:
            return 'rudder'
        elif 'flap' in surface:
            return 'flap'
        elif 'slat' in surface:
            return 'slat'
        elif 'spoiler' in surface:
            return 'spoiler'
        elif 'airbrake' in surface:
            return 'airbrake'
        else:
            return 'aileron'  # Default

# Add missing import at the top
import random

# Singleton instance
_control_surface_manager = None

def get_control_surface_manager(config=None):
    """Get the singleton instance of the Control Surface Manager."""
    global _control_surface_manager
    if _control_surface_manager is None:
        _control_surface_manager = ControlSurfaceManager(config)
    return _control_surface_manager

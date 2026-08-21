"""
Flight Dynamics Processor

Handles aircraft flight dynamics calculations for the Flight Control System.
"""

import math
import time
from typing import Dict, Any, Tuple

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class FlightDynamicsProcessor:
    """
    Flight Dynamics Processor for the Flight Control System.
    
    This component handles the calculation of aircraft dynamics, including:
    - Control surface effects on aircraft motion
    - Aircraft response to control inputs
    - Simulation of basic flight physics
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Flight Dynamics Processor.
        
        Args:
            config: Configuration dictionary with flight model parameters
        """
        self.config = config or self._get_default_config()
        
        # Aircraft characteristics
        self.aircraft_params = {
            'mass': 15000.0,             # kg
            'wing_area': 50.0,           # m^2
            'wing_span': 14.0,           # m
            'mean_chord': 3.0,           # m
            'roll_inertia': 25000.0,     # kg.m^2
            'pitch_inertia': 75000.0,    # kg.m^2
            'yaw_inertia': 100000.0,     # kg.m^2
            'roll_damping': 0.4,         # Roll damping coefficient
            'pitch_damping': 0.6,        # Pitch damping coefficient
            'yaw_damping': 0.3,          # Yaw damping coefficient
            'roll_effectiveness': 1.0,   # Roll control effectiveness
            'pitch_effectiveness': 1.0,  # Pitch control effectiveness
            'yaw_effectiveness': 1.0,    # Yaw control effectiveness
        }
        
        # Simplified aerodynamic coefficients
        self.aero_coefficients = {
            'CL_0': 0.2,                 # Base lift coefficient
            'CL_alpha': 0.1,             # Lift curve slope (per degree)
            'CD_0': 0.02,                # Zero-lift drag coefficient
            'CD_alpha': 0.001,           # Drag due to alpha
            'CD_alpha_squared': 0.05,    # Drag due to alpha squared
            'CY_beta': 0.1,              # Side force due to sideslip
            'Cl_beta': -0.05,            # Roll moment due to sideslip (dihedral effect)
            'Cl_aileron': 0.1,           # Roll moment due to aileron
            'Cm_0': 0.0,                 # Baseline pitch moment
            'Cm_alpha': -0.05,           # Pitch stability
            'Cm_elevator': -0.1,         # Pitch moment due to elevator
            'Cn_beta': 0.1,              # Yaw moment due to sideslip (weathercock stability)
            'Cn_rudder': 0.05,           # Yaw moment due to rudder
        }
        
        logger.info("[FCS_DYNAMICS] Flight Dynamics Processor initialized")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'simulation_fidelity': 'medium',   # Low, medium, high
            'max_roll_rate': 120.0,            # deg/sec
            'max_pitch_rate': 60.0,            # deg/sec
            'max_yaw_rate': 30.0,              # deg/sec
            'max_g_force': 9.0,                # g
            'min_g_force': -3.0,               # g
            'max_alpha': 25.0,                 # deg
            'min_alpha': -15.0,                # deg
            'max_beta': 15.0,                  # deg
            'use_simplified_model': True,      # Use simplified flight model
        }
    
    def calculate_control_response(self, control_inputs: Dict[str, float], 
                                   current_state: Dict[str, Any], 
                                   dt: float) -> Dict[str, Any]:
        """
        Calculate aircraft response to control inputs.
        
        Args:
            control_inputs: Control input values (-1.0 to 1.0)
            current_state: Current aircraft state
            dt: Time step in seconds
            
        Returns:
            Updated aircraft state
        """
        try:
            # Extract control inputs
            aileron = control_inputs.get('aileron', 0.0)
            elevator = control_inputs.get('elevator', 0.0)
            rudder = control_inputs.get('rudder', 0.0)
            throttle = control_inputs.get('throttle', 0.5)
            
            # Extract current state
            roll = current_state.get('roll', 0.0)         # deg
            pitch = current_state.get('pitch', 0.0)       # deg
            yaw = current_state.get('yaw', 0.0)           # deg
            roll_rate = current_state.get('roll_rate', 0.0)    # deg/s
            pitch_rate = current_state.get('pitch_rate', 0.0)  # deg/s
            yaw_rate = current_state.get('yaw_rate', 0.0)      # deg/s
            airspeed = current_state.get('airspeed', 200.0)    # knots
            altitude = current_state.get('altitude', 10000.0)  # feet
            
            # Convert airspeed to m/s for calculations
            airspeed_ms = airspeed * 0.51444  # knots to m/s
            
            # Get air density based on altitude
            rho = self._get_air_density(altitude)
            
            # Calculate dynamic pressure
            q = 0.5 * rho * airspeed_ms**2
            
            # Use simplified model if configured
            if self.config.get('use_simplified_model', True):
                return self._calculate_simplified_response(
                    control_inputs, current_state, dt
                )
            else:
                # Full aerodynamic model (more complex calculation)
                # This would be a much more detailed calculation
                # using full aerodynamic coefficients
                # For now, we'll just use the simplified model
                return self._calculate_simplified_response(
                    control_inputs, current_state, dt
                )
                
        except Exception as e:
            logger.error(f"[FCS_DYNAMICS] Error calculating control response: {e}")
            # Return original state on error to avoid crashes
            return current_state.copy()
    
    def _get_air_density(self, altitude_feet: float) -> float:
        """
        Get air density based on altitude using standard atmosphere model.
        
        Args:
            altitude_feet: Altitude in feet
            
        Returns:
            Air density in kg/m^3
        """
        # Convert feet to meters
        altitude = altitude_feet * 0.3048
        
        # Standard atmosphere model
        if altitude < 11000:  # Troposphere
            # Temperature lapse rate 6.5 K/km
            temperature = 288.15 - 0.0065 * altitude
            # Pressure formula
            pressure = 101325 * (temperature / 288.15) ** 5.2561
        else:  # Simplified stratosphere model
            temperature = 216.65
            pressure = 22632 * math.exp(-0.00015769 * (altitude - 11000))
        
        # Ideal gas law: ρ = p/(RT)
        gas_constant = 287.05  # J/(kg·K)
        density = pressure / (gas_constant * temperature)
        
        return density
    
    def _calculate_simplified_response(self, control_inputs: Dict[str, float], 
                                       current_state: Dict[str, Any], 
                                       dt: float) -> Dict[str, Any]:
        """
        Calculate aircraft response using a simplified flight model.
        
        Args:
            control_inputs: Control input values (-1.0 to 1.0)
            current_state: Current aircraft state
            dt: Time step in seconds
            
        Returns:
            Updated aircraft state
        """
        # Create a copy of the current state to modify
        new_state = current_state.copy()
        
        # Extract control inputs
        aileron = control_inputs.get('aileron', 0.0)
        elevator = control_inputs.get('elevator', 0.0)
        rudder = control_inputs.get('rudder', 0.0)
        throttle = control_inputs.get('throttle', 0.5)
        
        # Extract current state
        roll = current_state.get('roll', 0.0)
        pitch = current_state.get('pitch', 0.0)
        yaw = current_state.get('yaw', 0.0)
        roll_rate = current_state.get('roll_rate', 0.0)
        pitch_rate = current_state.get('pitch_rate', 0.0)
        yaw_rate = current_state.get('yaw_rate', 0.0)
        
        # Calculate target angular rates based on control inputs
        # These values are aircraft-specific and would be calibrated for each airframe
        target_roll_rate = aileron * self.config.get('max_roll_rate', 120.0)    # deg/s
        target_pitch_rate = -elevator * self.config.get('max_pitch_rate', 60.0) # deg/s, inverted because elevator is positive when pulled back
        target_yaw_rate = rudder * self.config.get('max_yaw_rate', 30.0)        # deg/s
        
        # Apply damping to simulate aerodynamic resistance
        roll_damping = self.aircraft_params['roll_damping']
        pitch_damping = self.aircraft_params['pitch_damping']
        yaw_damping = self.aircraft_params['yaw_damping']
        
        # Calculate new rates with damping (first-order response)
        # This simulates how the aircraft responds to control inputs over time
        new_roll_rate = roll_rate + (target_roll_rate - roll_rate) * (1.0 - math.exp(-dt / roll_damping))
        new_pitch_rate = pitch_rate + (target_pitch_rate - pitch_rate) * (1.0 - math.exp(-dt / pitch_damping))
        new_yaw_rate = yaw_rate + (target_yaw_rate - yaw_rate) * (1.0 - math.exp(-dt / yaw_damping))
        
        # Integrate rates to get attitudes
        new_roll = roll + new_roll_rate * dt
        new_pitch = pitch + new_pitch_rate * dt
        new_yaw = yaw + new_yaw_rate * dt
        
        # Normalize angles
        new_roll = (new_roll + 180) % 360 - 180  # -180 to 180
        new_pitch = max(self.config.get('min_alpha', -15.0), 
                        min(self.config.get('max_alpha', 25.0), new_pitch))  # Limit pitch
        new_yaw = new_yaw % 360  # 0 to 360
        
        # Update state with new values
        new_state['roll'] = new_roll
        new_state['pitch'] = new_pitch
        new_state['yaw'] = new_yaw
        new_state['roll_rate'] = new_roll_rate
        new_state['pitch_rate'] = new_pitch_rate
        new_state['yaw_rate'] = new_yaw_rate
        
        # Calculate angle of attack and sideslip (simplified)
        new_state['alpha'] = new_pitch * 0.1 + new_pitch_rate * 0.01
        new_state['beta'] = -new_yaw_rate * 0.1
        
        # Calculate g-force based on pitch rate and roll rate (simplified)
        g_force_pitch = 1.0 + abs(new_pitch_rate) / self.config.get('max_pitch_rate', 60.0) * 4.0
        g_force_roll = 1.0 + (new_roll_rate / self.config.get('max_roll_rate', 120.0))**2 * 4.0
        new_state['g_force'] = max(self.config.get('min_g_force', -3.0),
                                min(self.config.get('max_g_force', 9.0),
                                    max(g_force_pitch, g_force_roll)))
        
        return new_state
    
    def calculate_forces_and_moments(self, control_surface_positions: Dict[str, float], 
                                     current_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate aerodynamic forces and moments based on control surface positions and aircraft state.
        
        Args:
            control_surface_positions: Control surface positions (-1.0 to 1.0)
            current_state: Current aircraft state
            
        Returns:
            Dictionary containing forces and moments
        """
        try:
            # Extract control surface positions
            aileron_pos = control_surface_positions.get('left_aileron', 0.0)  # Using just left for simplicity
            elevator_pos = control_surface_positions.get('elevator', 0.0)
            rudder_pos = control_surface_positions.get('rudder', 0.0)
            
            # Extract current state
            airspeed = current_state.get('airspeed', 200.0)    # knots
            altitude = current_state.get('altitude', 10000.0)  # feet
            alpha = current_state.get('alpha', 0.0)            # deg (angle of attack)
            beta = current_state.get('beta', 0.0)              # deg (sideslip angle)
            
            # Convert airspeed to m/s for calculations
            airspeed_ms = airspeed * 0.51444  # knots to m/s
            
            # Get air density based on altitude
            rho = self._get_air_density(altitude)
            
            # Calculate dynamic pressure
            q = 0.5 * rho * airspeed_ms**2
            
            # Calculate lift coefficient
            CL = (self.aero_coefficients['CL_0'] + 
                  self.aero_coefficients['CL_alpha'] * alpha)
            
            # Calculate drag coefficient (quadratic with alpha)
            CD = (self.aero_coefficients['CD_0'] + 
                  self.aero_coefficients['CD_alpha'] * abs(alpha) +
                  self.aero_coefficients['CD_alpha_squared'] * alpha**2)
            
            # Calculate side force coefficient
            CY = self.aero_coefficients['CY_beta'] * beta
            
            # Calculate roll moment coefficient
            Cl = (self.aero_coefficients['Cl_beta'] * beta +
                  self.aero_coefficients['Cl_aileron'] * aileron_pos)
            
            # Calculate pitch moment coefficient
            Cm = (self.aero_coefficients['Cm_0'] +
                  self.aero_coefficients['Cm_alpha'] * alpha +
                  self.aero_coefficients['Cm_elevator'] * elevator_pos)
            
            # Calculate yaw moment coefficient
            Cn = (self.aero_coefficients['Cn_beta'] * beta +
                  self.aero_coefficients['Cn_rudder'] * rudder_pos)
            
            # Calculate forces
            lift = q * self.aircraft_params['wing_area'] * CL
            drag = q * self.aircraft_params['wing_area'] * CD
            side_force = q * self.aircraft_params['wing_area'] * CY
            
            # Calculate moments
            roll_moment = q * self.aircraft_params['wing_area'] * self.aircraft_params['wing_span'] * Cl
            pitch_moment = q * self.aircraft_params['wing_area'] * self.aircraft_params['mean_chord'] * Cm
            yaw_moment = q * self.aircraft_params['wing_area'] * self.aircraft_params['wing_span'] * Cn
            
            return {
                'forces': {
                    'lift': lift,
                    'drag': drag,
                    'side_force': side_force
                },
                'moments': {
                    'roll': roll_moment,
                    'pitch': pitch_moment,
                    'yaw': yaw_moment
                },
                'coefficients': {
                    'CL': CL,
                    'CD': CD,
                    'CY': CY,
                    'Cl': Cl,
                    'Cm': Cm,
                    'Cn': Cn
                }
            }
            
        except Exception as e:
            logger.error(f"[FCS_DYNAMICS] Error calculating forces and moments: {e}")
            # Return default values on error
            return {
                'forces': {'lift': 0.0, 'drag': 0.0, 'side_force': 0.0},
                'moments': {'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0},
                'coefficients': {'CL': 0.0, 'CD': 0.0, 'CY': 0.0, 'Cl': 0.0, 'Cm': 0.0, 'Cn': 0.0}
            }

# Singleton instance
_flight_dynamics_processor = None

def get_flight_dynamics_processor(config=None):
    """Get the singleton instance of the Flight Dynamics Processor."""
    global _flight_dynamics_processor
    if _flight_dynamics_processor is None:
        _flight_dynamics_processor = FlightDynamicsProcessor(config)
    return _flight_dynamics_processor

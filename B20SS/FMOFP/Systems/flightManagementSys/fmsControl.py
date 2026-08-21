import threading
import time
import math
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.flightManagementSys.flightManagementSystem import get_flightManagementSystem

logger = get_logger()

class FMSControl:
    """
    FMS Control module for aircraft.
    
    This class handles the control aspects of the Flight Management System,
    managing modes, flight profiles, and tactical operations.
    """
    def __init__(self):
        self.fms = get_flightManagementSystem()
        self.lock = threading.Lock()
        self.mode = "NORMAL"
        self.available_modes = ["NORMAL", "COMBAT", "STEALTH", "TRAINING", "EMERGENCY"]
        self.flight_profiles = {
            "NORMAL": {
                "max_bank_angle": 30,      # degrees
                "max_pitch_angle": 20,     # degrees
                "max_g_force": 2.5,        # g's
                "max_aoa": 15,             # degrees
                "engine_power": 0.7,       # 0-1 scale
                "turn_rate_limit": 3,      # degrees/second
            },
            "COMBAT": {
                "max_bank_angle": 80,      # degrees
                "max_pitch_angle": 60,     # degrees
                "max_g_force": 9.0,        # g's
                "max_aoa": 25,             # degrees
                "engine_power": 1.0,       # 0-1 scale (afterburner)
                "turn_rate_limit": 20,     # degrees/second
            },
            "STEALTH": {
                "max_bank_angle": 45,      # degrees
                "max_pitch_angle": 30,     # degrees
                "max_g_force": 5.0,        # g's
                "max_aoa": 20,             # degrees
                "engine_power": 0.6,       # 0-1 scale (reduced for signature)
                "turn_rate_limit": 5,      # degrees/second
            },
            "TRAINING": {
                "max_bank_angle": 60,      # degrees
                "max_pitch_angle": 45,     # degrees
                "max_g_force": 7.0,        # g's
                "max_aoa": 22,             # degrees
                "engine_power": 0.9,       # 0-1 scale
                "turn_rate_limit": 15,     # degrees/second
            },
            "EMERGENCY": {
                "max_bank_angle": 90,      # degrees
                "max_pitch_angle": 85,     # degrees
                "max_g_force": 9.5,        # g's (absolute max)
                "max_aoa": 30,             # degrees
                "engine_power": 1.0,       # 0-1 scale (max available)
                "turn_rate_limit": 25,     # degrees/second
            }
        }
        
        # Current flight profile limits (initialized to NORMAL)
        self.current_profile = self.flight_profiles["NORMAL"].copy()
        
        # Flight control parameters
        self.thrust = 0.5  # Normalized thrust level (0.0 to 1.0)
        self.throttle_position = 50  # Percentage (0-100)
        self.afterburner = False  # Afterburner state
        self.flaps_position = 0  # Degrees (0-30 typically)
        self.landing_gear = "UP"  # UP or DOWN
        self.spoilers = 0  # Percentage deployed (0-100)
        self.rudder = 0  # Position (-100 to 100)
        self.elevator = 0  # Position (-100 to 100)
        self.ailerons = 0  # Position (-100 to 100)
        
        # Target values for autopilot/FMS control
        self.target_altitude = 30000  # feet
        self.target_airspeed = 450    # knots
        self.target_heading = 0       # degrees
        self.target_vertical_speed = 0  # feet per minute
        
        # Performance envelope monitoring
        self.envelope_warnings = []
        
        # Tactical systems status
        self.tactical_systems = {
            "countermeasures": "STANDBY",
            "targeting": "STANDBY",
            "weapons": "SAFE",
            "stealth_mode": "OFF"
        }

    def set_mode(self, mode):
        """
        Set the flight mode and update flight parameters accordingly
        
        Args:
            mode (str): The desired mode (NORMAL, COMBAT, STEALTH, etc.)
            
        Returns:
            bool: True if mode was changed successfully, False otherwise
        """
        with self.lock:
            if mode in self.available_modes:
                old_mode = self.mode
                self.mode = mode
                self.current_profile = self.flight_profiles[mode].copy()
                
                # Update FMS mode
                self.fms.set_mode(mode)
                
                # Update tactical systems based on mode
                self._update_tactical_systems(mode)
                
                logger.info(f"FMS mode changed from {old_mode} to {mode}")
                logger.info(f"Flight profile updated to {mode} profile")
                return True
            else:
                logger.warning(f"Invalid FMS mode: {mode}")
                return False

    def _update_tactical_systems(self, mode):
        """
        Update tactical systems based on flight mode
        
        Args:
            mode (str): The current flight mode
        """
        if mode == "COMBAT":
            self.tactical_systems["countermeasures"] = "READY"
            self.tactical_systems["targeting"] = "ACTIVE"
            self.tactical_systems["weapons"] = "ARMED"
            self.tactical_systems["stealth_mode"] = "OFF"
        elif mode == "STEALTH":
            self.tactical_systems["countermeasures"] = "PASSIVE"
            self.tactical_systems["targeting"] = "PASSIVE"
            self.tactical_systems["weapons"] = "SAFE"
            self.tactical_systems["stealth_mode"] = "ON"
        elif mode == "EMERGENCY":
            self.tactical_systems["countermeasures"] = "ACTIVE"
            self.tactical_systems["targeting"] = "READY"
            self.tactical_systems["weapons"] = "READY"
            self.tactical_systems["stealth_mode"] = "OFF"
        else:  # NORMAL or TRAINING
            self.tactical_systems["countermeasures"] = "STANDBY"
            self.tactical_systems["targeting"] = "STANDBY"
            self.tactical_systems["weapons"] = "SAFE"
            self.tactical_systems["stealth_mode"] = "OFF"

    def update_attitude(self, roll=None, pitch=None, yaw=None, 
                      roll_rate=None, pitch_rate=None, yaw_rate=None):
        """
        Update aircraft attitude parameters with envelope protection
        
        Args:
            roll (float): Roll angle in degrees
            pitch (float): Pitch angle in degrees
            yaw (float): Yaw angle in degrees
            roll_rate (float): Roll rate in degrees/second
            pitch_rate (float): Pitch rate in degrees/second
            yaw_rate (float): Yaw rate in degrees/second
            
        Returns:
            dict: Applied attitude parameters (may differ from requested values due to envelope protection)
        """
        with self.lock:
            # Get current flight data
            flight_data = self.fms.get_flight_data()
            current_attitude = flight_data['attitude']
            
            # Initialize with current values if not provided
            applied_attitude = {
                'roll': roll if roll is not None else current_attitude['roll'],
                'pitch': pitch if pitch is not None else current_attitude['pitch'],
                'yaw': yaw if yaw is not None else current_attitude['yaw'],
                'roll_rate': roll_rate if roll_rate is not None else current_attitude['roll_rate'],
                'pitch_rate': pitch_rate if pitch_rate is not None else current_attitude['pitch_rate'],
                'yaw_rate': yaw_rate if yaw_rate is not None else current_attitude['yaw_rate']
            }
            
            # Apply envelope protection based on current mode
            # Limit roll angle
            if abs(applied_attitude['roll']) > self.current_profile['max_bank_angle']:
                applied_attitude['roll'] = math.copysign(
                    self.current_profile['max_bank_angle'], 
                    applied_attitude['roll']
                )
                logger.warning(f"Roll angle limited to {applied_attitude['roll']} degrees (mode: {self.mode})")
                self.envelope_warnings.append("BANK_ANGLE")
            else:
                if "BANK_ANGLE" in self.envelope_warnings:
                    self.envelope_warnings.remove("BANK_ANGLE")
            
            # Limit pitch angle
            if abs(applied_attitude['pitch']) > self.current_profile['max_pitch_angle']:
                applied_attitude['pitch'] = math.copysign(
                    self.current_profile['max_pitch_angle'], 
                    applied_attitude['pitch']
                )
                logger.warning(f"Pitch angle limited to {applied_attitude['pitch']} degrees (mode: {self.mode})")
                self.envelope_warnings.append("PITCH_ANGLE")
            else:
                if "PITCH_ANGLE" in self.envelope_warnings:
                    self.envelope_warnings.remove("PITCH_ANGLE")
            
            # Limit rate values
            if abs(applied_attitude['roll_rate']) > self.current_profile['turn_rate_limit'] * 3:
                applied_attitude['roll_rate'] = math.copysign(
                    self.current_profile['turn_rate_limit'] * 3, 
                    applied_attitude['roll_rate']
                )
                logger.warning(f"Roll rate limited to {applied_attitude['roll_rate']} deg/s (mode: {self.mode})")
                self.envelope_warnings.append("ROLL_RATE")
            else:
                if "ROLL_RATE" in self.envelope_warnings:
                    self.envelope_warnings.remove("ROLL_RATE")
                    
            if abs(applied_attitude['pitch_rate']) > self.current_profile['turn_rate_limit'] * 2:
                applied_attitude['pitch_rate'] = math.copysign(
                    self.current_profile['turn_rate_limit'] * 2, 
                    applied_attitude['pitch_rate']
                )
                logger.warning(f"Pitch rate limited to {applied_attitude['pitch_rate']} deg/s (mode: {self.mode})")
                self.envelope_warnings.append("PITCH_RATE")
            else:
                if "PITCH_RATE" in self.envelope_warnings:
                    self.envelope_warnings.remove("PITCH_RATE")
            
            if abs(applied_attitude['yaw_rate']) > self.current_profile['turn_rate_limit']:
                applied_attitude['yaw_rate'] = math.copysign(
                    self.current_profile['turn_rate_limit'], 
                    applied_attitude['yaw_rate']
                )
                logger.warning(f"Yaw rate limited to {applied_attitude['yaw_rate']} deg/s (mode: {self.mode})")
                self.envelope_warnings.append("YAW_RATE")
            else:
                if "YAW_RATE" in self.envelope_warnings:
                    self.envelope_warnings.remove("YAW_RATE")
            
            # Update FMS with applied values
            self.fms.set_flight_parameters({'attitude': applied_attitude})
            
            return applied_attitude

    def set_thrust(self, thrust_level):
        """
        Set the engine thrust level
        
        Args:
            thrust_level (float): Normalized thrust level (0.0 to 1.0)
            
        Returns:
            float: Applied thrust level (may differ from requested value due to envelope protection)
        """
        with self.lock:
            # Apply limits based on current mode
            min_thrust = 0.1  # Minimum thrust for engine operation
            max_thrust = 1.0 if self.afterburner else 0.9  # Max thrust with/without afterburner
            
            # Ensure thrust is within limits
            applied_thrust = max(min_thrust, min(max_thrust, thrust_level))
            
            # Update throttle position (0-100%)
            self.throttle_position = int(applied_thrust * 100)
            
            # Set afterburner state if thrust is high enough
            if applied_thrust > 0.9:
                self.afterburner = True
                logger.info("Afterburner engaged")
            elif applied_thrust < 0.85 and self.afterburner:
                self.afterburner = False
                logger.info("Afterburner disengaged")
            
            # Update internal state
            self.thrust = applied_thrust
            
            # Log if limited
            if applied_thrust != thrust_level:
                logger.warning(f"Thrust limited to {applied_thrust:.2f} (requested: {thrust_level:.2f})")
            else:
                logger.info(f"Thrust set to {applied_thrust:.2f}")
                
            return applied_thrust
            
    def set_control_surfaces(self, ailerons=None, elevator=None, rudder=None, flaps=None, spoilers=None):
        """
        Set control surface positions
        
        Args:
            ailerons (float): Aileron position (-100 to 100)
            elevator (float): Elevator position (-100 to 100)
            rudder (float): Rudder position (-100 to 100)
            flaps (float): Flaps position (0 to 30 degrees)
            spoilers (float): Spoiler deployment (0 to 100 percent)
            
        Returns:
            dict: Applied control surface positions
        """
        with self.lock:
            # Initialize with current values if not provided
            if ailerons is not None:
                self.ailerons = max(-100, min(100, ailerons))
            if elevator is not None:
                self.elevator = max(-100, min(100, elevator))
            if rudder is not None:
                self.rudder = max(-100, min(100, rudder))
            if flaps is not None:
                self.flaps_position = max(0, min(30, flaps))
            if spoilers is not None:
                self.spoilers = max(0, min(100, spoilers))
                
            # Return applied values
            applied_values = {
                'ailerons': self.ailerons,
                'elevator': self.elevator,
                'rudder': self.rudder,
                'flaps': self.flaps_position,
                'spoilers': self.spoilers
            }
            
            # Update attitude based on control surfaces
            # This is a simple simulation - in a real system, the FCS would handle this
            roll_effect = self.ailerons * 0.01  # Convert to approximate roll rate
            pitch_effect = self.elevator * 0.005  # Convert to approximate pitch rate
            yaw_effect = self.rudder * 0.003  # Convert to approximate yaw rate
            
            # Apply control surface effects to attitude rates
            self.update_attitude(
                roll_rate=roll_effect,
                pitch_rate=pitch_effect,
                yaw_rate=yaw_effect
            )
            
            logger.info(f"Control surfaces updated: {applied_values}")
            return applied_values
    
    def set_landing_gear(self, position):
        """
        Set landing gear position
        
        Args:
            position (str): Landing gear position ('UP' or 'DOWN')
            
        Returns:
            str: Applied landing gear position
        """
        with self.lock:
            if position.upper() in ['UP', 'DOWN']:
                self.landing_gear = position.upper()
                logger.info(f"Landing gear set to {self.landing_gear}")
                return self.landing_gear
            else:
                logger.warning(f"Invalid landing gear position: {position}")
                return self.landing_gear

    def set_autopilot_targets(self, altitude=None, airspeed=None, heading=None, vertical_speed=None):
        """
        Set target parameters for the FMS/autopilot
        
        Args:
            altitude (float): Target altitude in feet
            airspeed (float): Target airspeed in knots
            heading (float): Target heading in degrees
            vertical_speed (float): Target vertical speed in feet per minute
            
        Returns:
            dict: Applied target values
        """
        with self.lock:
            # Update target values if provided
            if altitude is not None:
                self.target_altitude = max(0, min(60000, altitude))  # Limit to realistic range
            if airspeed is not None:
                self.target_airspeed = max(100, min(1000, airspeed))  # Limit to realistic range
            if heading is not None:
                self.target_heading = heading % 360  # Normalize to 0-359 range
            if vertical_speed is not None:
                self.target_vertical_speed = max(-8000, min(6000, vertical_speed))  # Limit to realistic range
                
            # Return applied values
            applied_targets = {
                'altitude': self.target_altitude,
                'airspeed': self.target_airspeed,
                'heading': self.target_heading,
                'vertical_speed': self.target_vertical_speed
            }
            
            logger.info(f"Autopilot targets set: {applied_targets}")
            return applied_targets
    
    def calculate_energy_maneuverability(self):
        """
        Calculate energy maneuverability metrics for tactical display and decision-making
        
        Returns:
            dict: Energy maneuverability metrics
        """
        flight_data = self.fms.get_flight_data()
        
        # Extract relevant parameters
        mass = 15000  # kg, typical for fighter aircraft
        g = 9.81  # m/s^2
        altitude_m = flight_data['navigation']['altitude'] * 0.3048  # feet to meters
        speed_ms = flight_data['velocity']['airspeed'] * 0.51444  # knots to m/s
        
        # Calculate specific excess power (Ps)
        # Simplified model: Ps = V * (T-D)/W where:
        # V = velocity, T = thrust, D = drag, W = weight
        
        # For this simulation, we'll approximate it using current mode's engine power
        engine_efficiency = self.current_profile['engine_power']
        # Get AOA from tactical data if available, otherwise use a default value
        aoa = flight_data['tactical'].get('aoa', 0)
        drag_coefficient = 0.02 + (abs(aoa) / 100)  # simplified drag model
        
        # Calculate thrust available (very simplified)
        thrust_available = engine_efficiency * 150000  # N, max thrust
        
        # Calculate drag (simplified)
        air_density = 1.225 * math.exp(-altitude_m / 10000)  # simplified atmospheric model
        drag = 0.5 * air_density * speed_ms * speed_ms * drag_coefficient * 30  # m^2 reference area
        
        # Calculate specific excess power
        weight = mass * g
        specific_excess_power = speed_ms * (thrust_available - drag) / weight
        
        # Calculate turn performance - guard against invalid math domains
        thrust_weight_ratio = thrust_available/weight
        try:
            # Only calculate if thrust/weight ratio > 1 to avoid math domain error
            if thrust_weight_ratio > 1.0:
                max_sustained_turn_rate = math.degrees(g * math.sqrt(thrust_weight_ratio**2 - 1) / max(1.0, speed_ms))
            else:
                max_sustained_turn_rate = 0.0  # Not enough thrust for sustained turn
            
            # Guard against invalid g-force values
            g_force = max(1.01, self.current_profile['max_g_force'])
            max_instantaneous_turn_rate = math.degrees(g * math.sqrt(g_force**2 - 1) / max(1.0, speed_ms))
        except (ValueError, ZeroDivisionError):
            # Fallback values if calculations fail
            max_sustained_turn_rate = 0.0
            max_instantaneous_turn_rate = 0.0
            logger.warning("Turn rate calculation failed, using default values")
        
        # Calculate climb performance
        max_climb_rate = specific_excess_power  # m/s
        max_climb_rate_fpm = max_climb_rate * 196.85  # convert to feet per minute
        
        # Return metrics as a dictionary
        return {
            'specific_excess_power': specific_excess_power,  # m/s
            'max_sustained_turn_rate': max_sustained_turn_rate,  # deg/s
            'max_instantaneous_turn_rate': max_instantaneous_turn_rate,  # deg/s
            'max_climb_rate': max_climb_rate_fpm,  # feet per minute
            'energy_advantage': specific_excess_power * 10  # simplified metric for tactical advantage
        }

    def get_tactical_status(self):
        """
        Get the current tactical status of the aircraft
        
        Returns:
            dict: Current tactical status including warnings and system states
        """
        with self.lock:
            # Get current flight data
            flight_data = self.fms.get_flight_data()
            
            # Calculate energy maneuverability metrics
            energy_metrics = self.calculate_energy_maneuverability()
            
            # Prepare tactical status report
            tactical_status = {
                'mode': self.mode,
                'envelope_warnings': self.envelope_warnings.copy(),
                'tactical_systems': self.tactical_systems.copy(),
                'energy_metrics': energy_metrics,
                'profile_limits': self.current_profile.copy(),
                'g_force': flight_data['tactical']['g_force'],
                'aoa': flight_data['tactical']['aoa'],
                'energy_state': flight_data['tactical']['energy_state']
            }
            
            return tactical_status

    def execute_maneuver(self, maneuver_type, parameters=None):
        """
        Execute a predefined tactical maneuver
        
        Args:
            maneuver_type (str): Type of maneuver to execute (BREAK, BARREL_ROLL, etc.)
            parameters (dict): Additional parameters for the maneuver
            
        Returns:
            bool: True if maneuver initiated successfully, False otherwise
        """
        if parameters is None:
            parameters = {}
            
        logger.info(f"Executing maneuver: {maneuver_type}")
        
        # Pre-programmed flight maneuvers for  aircraft
        if maneuver_type == "BREAK_RIGHT":
            # Hard right turn with max performance
            self.update_attitude(roll=60, roll_rate=40, yaw_rate=10)
            return True
            
        elif maneuver_type == "BREAK_LEFT":
            # Hard left turn with max performance
            self.update_attitude(roll=-60, roll_rate=-40, yaw_rate=-10)
            return True
            
        elif maneuver_type == "BARREL_ROLL":
            # Not implemented yet - would require multi-step execution
            logger.info("Barrel roll maneuver not implemented in this version")
            return False
            
        elif maneuver_type == "DEFENSIVE_SPLIT_S":
            # Split S maneuver (roll inverted, pull down into opposite direction)
            self.update_attitude(roll=180, pitch=-80)
            return True
            
        elif maneuver_type == "MAXIMUM_CLIMB":
            # Maximum performance climb
            self.update_attitude(pitch=self.current_profile['max_pitch_angle'])
            return True
            
        elif maneuver_type == "DIVE":
            # Rapid descent
            dive_angle = parameters.get('angle', -30)  # Default to -30 degrees
            self.update_attitude(pitch=dive_angle)
            return True
            
        else:
            logger.warning(f"Unknown maneuver type: {maneuver_type}")
            return False

    def process_command(self, command_type, parameters=None):
        """
        Process a command from external systems
        
        Args:
            command_type (str): Type of command to process
            parameters (dict): Parameters for the command
            
        Returns:
            dict: Command result with status and data
        """
        if parameters is None:
            parameters = {}
            
        result = {
            'status': 'ERROR',
            'message': 'Unknown command',
            'data': {}
        }
        
        try:
            if command_type == "SET_MODE":
                mode = parameters.get('mode', 'NORMAL')
                success = self.set_mode(mode)
                if success:
                    result['status'] = 'SUCCESS'
                    result['message'] = f"Mode set to {mode}"
                else:
                    result['message'] = f"Failed to set mode to {mode}"
                    
            elif command_type == "GET_STATUS":
                tactical_status = self.get_tactical_status()
                result['status'] = 'SUCCESS'
                result['message'] = "Tactical status retrieved"
                result['data'] = tactical_status
                
            elif command_type == "UPDATE_ATTITUDE":
                attitude = self.update_attitude(
                    roll=parameters.get('roll'),
                    pitch=parameters.get('pitch'),
                    yaw=parameters.get('yaw'),
                    roll_rate=parameters.get('roll_rate'),
                    pitch_rate=parameters.get('pitch_rate'),
                    yaw_rate=parameters.get('yaw_rate')
                )
                result['status'] = 'SUCCESS'
                result['message'] = "Attitude updated"
                result['data'] = {'applied_attitude': attitude}
                
            elif command_type == "SET_THRUST":
                thrust_level = parameters.get('thrust_level')
                if thrust_level is not None:
                    applied_thrust = self.set_thrust(thrust_level)
                    result['status'] = 'SUCCESS'
                    result['message'] = f"Thrust set to {applied_thrust:.2f}"
                    result['data'] = {'applied_thrust': applied_thrust}
                else:
                    result['message'] = "Missing thrust_level parameter"
                    
            elif command_type == "SET_CONTROL_SURFACES":
                applied_values = self.set_control_surfaces(
                    ailerons=parameters.get('ailerons'),
                    elevator=parameters.get('elevator'),
                    rudder=parameters.get('rudder'),
                    flaps=parameters.get('flaps'),
                    spoilers=parameters.get('spoilers')
                )
                result['status'] = 'SUCCESS'
                result['message'] = "Control surfaces updated"
                result['data'] = {'applied_values': applied_values}
                    
            elif command_type == "SET_LANDING_GEAR":
                position = parameters.get('position')
                if position:
                    applied_position = self.set_landing_gear(position)
                    result['status'] = 'SUCCESS'
                    result['message'] = f"Landing gear set to {applied_position}"
                    result['data'] = {'applied_position': applied_position}
                else:
                    result['message'] = "Missing position parameter"
                    
            elif command_type == "SET_AUTOPILOT":
                applied_targets = self.set_autopilot_targets(
                    altitude=parameters.get('altitude'),
                    airspeed=parameters.get('airspeed'),
                    heading=parameters.get('heading'),
                    vertical_speed=parameters.get('vertical_speed')
                )
                result['status'] = 'SUCCESS'
                result['message'] = "Autopilot targets updated"
                result['data'] = {'applied_targets': applied_targets}
                
            elif command_type == "EXECUTE_MANEUVER":
                maneuver_type = parameters.get('maneuver_type')
                if maneuver_type:
                    success = self.execute_maneuver(maneuver_type, parameters)
                    if success:
                        result['status'] = 'SUCCESS'
                        result['message'] = f"Maneuver {maneuver_type} executed"
                    else:
                        result['message'] = f"Failed to execute maneuver {maneuver_type}"
                else:
                    result['message'] = "Missing maneuver_type parameter"
                    
            else:
                result['message'] = f"Unknown command type: {command_type}"
                
        except Exception as e:
            logger.error(f"Error processing command {command_type}: {e}")
            result['status'] = 'ERROR'
            result['message'] = f"Exception: {str(e)}"
            
        return result

# Singleton instance
_fms_control = None

def get_fms_control():
    """Get the singleton instance of the FMS Control"""
    global _fms_control
    if _fms_control is None:
        _fms_control = FMSControl()
    return _fms_control

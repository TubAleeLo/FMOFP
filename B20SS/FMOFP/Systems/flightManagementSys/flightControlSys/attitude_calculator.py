"""
Attitude Calculator

Calculates and manages aircraft attitude data for the Flight Control System.
"""

import math
import time
import numpy as np
from typing import Dict, Any, List, Tuple, Optional

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class AttitudeCalculator:
    """
    Attitude Calculator for the Flight Control System.
    
    This component calculates and maintains the aircraft's attitude information:
    - Orientation (roll, pitch, yaw)
    - Angular rates (roll rate, pitch rate, yaw rate)
    - Angular accelerations
    - Flight parameters (alpha, beta, g-force)
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the Attitude Calculator.
        
        Args:
            config: Configuration dictionary with calculation parameters
        """
        self.config = config or self._get_default_config()
        
        # Initialize attitude state
        self.attitude = {
            # Orientation (Euler angles in degrees)
            'roll': 0.0,           # Roll angle (degrees)
            'pitch': 0.0,          # Pitch angle (degrees)
            'yaw': 0.0,            # Yaw angle/heading (degrees)
            
            # Angular rates (degrees per second)
            'roll_rate': 0.0,      # Roll rate (deg/s)
            'pitch_rate': 0.0,     # Pitch rate (deg/s)
            'yaw_rate': 0.0,       # Yaw rate (deg/s)
            
            # Angular accelerations (degrees per second squared)
            'roll_accel': 0.0,     # Roll acceleration (deg/s²)
            'pitch_accel': 0.0,    # Pitch acceleration (deg/s²)
            'yaw_accel': 0.0,      # Yaw acceleration (deg/s²)
            
            # Flight parameters
            'alpha': 0.0,          # Angle of attack (degrees)
            'beta': 0.0,           # Sideslip angle (degrees)
            'g_force': 1.0,        # G-force (g)
            
            # Rotation quaternion (for 3D calculations, w,x,y,z format)
            'quaternion': [1.0, 0.0, 0.0, 0.0],
            
            # Timestamp of last update
            'timestamp': time.time()
        }
        
        # Previous state for derivative calculations
        self.prev_attitude = self.attitude.copy()
        
        # Sensor fusion weights
        self.sensor_weights = {
            'gyro': 0.7,           # Gyroscope weight
            'accel': 0.2,          # Accelerometer weight
            'mag': 0.1,            # Magnetometer weight
        }
        
        # Complementary filter time constant (seconds)
        self.filter_tau = 0.5
        
        logger.info("[FCS_ATTITUDE] Attitude Calculator initialized")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'use_quaternions': True,        # Use quaternions for attitude representation
            'gyro_bias_correction': True,   # Apply gyroscope bias correction
            'magnetic_declination': 0.0,    # Local magnetic declination (degrees)
            'max_roll': 180.0,              # Maximum roll angle (degrees)
            'max_pitch': 90.0,              # Maximum pitch angle (degrees)
            'filter_type': 'complementary', # Filter type: 'complementary', 'kalman'
        }
    
    def update(self, sensor_data: Dict[str, Any] = None, 
              control_inputs: Dict[str, float] = None,
              surface_positions: Dict[str, float] = None,
              dt: float = 0.02) -> Dict[str, Any]:
        """
        Update attitude based on sensor data and control inputs.
        
        Args:
            sensor_data: Sensor measurements (gyro, accel, mag)
            control_inputs: Control stick/pedal inputs
            surface_positions: Control surface positions
            dt: Time step in seconds
            
        Returns:
            Updated attitude state
        """
        try:
            # Store previous state for derivative calculations
            self.prev_attitude = self.attitude.copy()
            current_time = time.time()
            
            # Use provided dt or calculate from timestamps
            if dt <= 0:
                dt = current_time - self.prev_attitude['timestamp']
                if dt <= 0:
                    dt = 0.02  # Use default time step if invalid
            
            # Handle the case where no sensor data is provided
            if sensor_data is None:
                # If no sensor data, use simulation mode based on control inputs
                return self._simulate_attitude(control_inputs, surface_positions, dt)
            
            # Extract sensor data
            gyro = sensor_data.get('gyro', {'x': 0.0, 'y': 0.0, 'z': 0.0})
            accel = sensor_data.get('accel', {'x': 0.0, 'y': 0.0, 'z': 9.81})
            mag = sensor_data.get('mag', {'x': 0.0, 'y': 0.0, 'z': 0.0})
            
            # Choose appropriate filter based on configuration
            if self.config.get('filter_type') == 'kalman':
                # Kalman filter for sensor fusion
                self._update_attitude_kalman(gyro, accel, mag, dt)
            else:
                # Default to complementary filter
                self._update_attitude_complementary(gyro, accel, mag, dt)
            
            # Update timestamp
            self.attitude['timestamp'] = current_time
            
            # Return updated attitude
            return self.attitude.copy()
            
        except Exception as e:
            logger.error(f"[FCS_ATTITUDE] Error updating attitude: {e}")
            # Return current attitude on error to avoid crashes
            return self.attitude.copy()
    
    def _simulate_attitude(self, control_inputs: Dict[str, float], 
                          surface_positions: Dict[str, float],
                          dt: float) -> Dict[str, Any]:
        """
        Simulate attitude changes based on control inputs.
        Used when no sensor data is available.
        
        Args:
            control_inputs: Control inputs (-1.0 to 1.0)
            surface_positions: Control surface positions (-1.0 to 1.0)
            dt: Time step in seconds
            
        Returns:
            Updated attitude state
        """
        # Use either control inputs or surface positions, preferring surface positions
        if surface_positions:
            # Calculate angular rates from surface positions
            left_aileron = surface_positions.get('left_aileron', 0.0)
            right_aileron = surface_positions.get('right_aileron', 0.0)
            elevator = surface_positions.get('elevator', 0.0)
            rudder = surface_positions.get('rudder', 0.0)
            
            # Calculate effective aileron deflection
            aileron_effect = (left_aileron - right_aileron) / 2.0
            
            # Map surface positions to target rates
            # These values are calibrated for the specific aircraft
            target_roll_rate = aileron_effect * 120.0  # Max 120 deg/sec for full deflection
            target_pitch_rate = -elevator * 60.0       # Max 60 deg/sec, negative because pushing elevator down causes pitch up
            target_yaw_rate = rudder * 30.0            # Max 30 deg/sec
        elif control_inputs:
            # Calculate angular rates directly from control inputs
            aileron = control_inputs.get('aileron', 0.0)
            elevator = control_inputs.get('elevator', 0.0)
            rudder = control_inputs.get('rudder', 0.0)
            
            # Map control inputs to target rates
            target_roll_rate = aileron * 120.0
            target_pitch_rate = -elevator * 60.0
            target_yaw_rate = rudder * 30.0
        else:
            # No inputs provided, maintain current rates
            target_roll_rate = self.attitude['roll_rate']
            target_pitch_rate = self.attitude['pitch_rate']
            target_yaw_rate = self.attitude['yaw_rate']
        
        # Apply damping to simulate aerodynamic effects
        roll_damping = 0.1  # Seconds
        pitch_damping = 0.2
        yaw_damping = 0.3
        
        # Calculate new rates with damping (first-order response)
        roll_rate = self.attitude['roll_rate'] + (target_roll_rate - self.attitude['roll_rate']) * (1.0 - math.exp(-dt / roll_damping))
        pitch_rate = self.attitude['pitch_rate'] + (target_pitch_rate - self.attitude['pitch_rate']) * (1.0 - math.exp(-dt / pitch_damping))
        yaw_rate = self.attitude['yaw_rate'] + (target_yaw_rate - self.attitude['yaw_rate']) * (1.0 - math.exp(-dt / yaw_damping))
        
        # Calculate accelerations
        roll_accel = (roll_rate - self.attitude['roll_rate']) / dt
        pitch_accel = (pitch_rate - self.attitude['pitch_rate']) / dt
        yaw_accel = (yaw_rate - self.attitude['yaw_rate']) / dt
        
        # Integrate rates to get angles
        roll = self.attitude['roll'] + roll_rate * dt
        pitch = self.attitude['pitch'] + pitch_rate * dt
        yaw = self.attitude['yaw'] + yaw_rate * dt
        
        # Normalize angles
        roll = ((roll + 180) % 360) - 180  # -180 to 180
        pitch = max(-90, min(90, pitch))   # -90 to 90
        yaw = yaw % 360                    # 0 to 360
        
        # Calculate angle of attack and sideslip (simplified)
        alpha = pitch * 0.1 + pitch_rate * 0.01
        beta = -yaw_rate * 0.1
        
        # Calculate g-force (simplified)
        g_force_pitch = 1.0 + abs(pitch_rate) / 60.0 * 4.0
        g_force_roll = 1.0 + (roll_rate / 120.0)**2 * 4.0
        g_force = max(-3.0, min(9.0, max(g_force_pitch, g_force_roll)))
        
        # Update quaternion if using quaternions
        if self.config.get('use_quaternions', True):
            self.attitude['quaternion'] = self._euler_to_quaternion(
                math.radians(roll), math.radians(pitch), math.radians(yaw)
            )
        
        # Update attitude state
        self.attitude['roll'] = roll
        self.attitude['pitch'] = pitch
        self.attitude['yaw'] = yaw
        self.attitude['roll_rate'] = roll_rate
        self.attitude['pitch_rate'] = pitch_rate
        self.attitude['yaw_rate'] = yaw_rate
        self.attitude['roll_accel'] = roll_accel
        self.attitude['pitch_accel'] = pitch_accel
        self.attitude['yaw_accel'] = yaw_accel
        self.attitude['alpha'] = alpha
        self.attitude['beta'] = beta
        self.attitude['g_force'] = g_force
        
        return self.attitude.copy()
    
    def _update_attitude_complementary(self, gyro: Dict[str, float], 
                                      accel: Dict[str, float],
                                      mag: Dict[str, float],
                                      dt: float):
        """
        Update attitude using complementary filter.
        
        Args:
            gyro: Gyroscope readings (x,y,z in deg/s)
            accel: Accelerometer readings (x,y,z in m/s²)
            mag: Magnetometer readings (x,y,z in arbitrary units)
            dt: Time step in seconds
        """
        # Extract gyro rates (converted to radians/sec for calculations)
        gyro_x = math.radians(gyro.get('x', 0.0))
        gyro_y = math.radians(gyro.get('y', 0.0))
        gyro_z = math.radians(gyro.get('z', 0.0))
        
        # Extract current attitude in radians
        roll_rad = math.radians(self.attitude['roll'])
        pitch_rad = math.radians(self.attitude['pitch'])
        yaw_rad = math.radians(self.attitude['yaw'])
        
        # Gyro integration (prediction)
        # For small rotations we can use Euler angles directly
        roll_gyro = roll_rad + gyro_x * dt
        pitch_gyro = pitch_rad + gyro_y * dt
        yaw_gyro = yaw_rad + gyro_z * dt
        
        # Accelerometer-based attitude (for roll and pitch only)
        accel_x = accel.get('x', 0.0)
        accel_y = accel.get('y', 0.0)
        accel_z = accel.get('z', 0.0) if accel.get('z', 0.0) != 0 else 0.0001  # Avoid division by zero
        
        # Calculate roll and pitch from accelerometer
        roll_acc = math.atan2(accel_y, accel_z)
        pitch_acc = math.atan2(-accel_x, math.sqrt(accel_y**2 + accel_z**2))
        
        # Magnetometer-based yaw
        mag_x = mag.get('x', 0.0)
        mag_y = mag.get('y', 0.0)
        
        # Tilt-compensated magnetometer calculations
        mag_x_comp = mag_x * math.cos(pitch_rad) + mag_y * math.sin(roll_rad) * math.sin(pitch_rad)
        mag_y_comp = mag_y * math.cos(roll_rad)
        
        # Calculate yaw from magnetometer
        yaw_mag = math.atan2(-mag_y_comp, mag_x_comp)
        
        # Apply magnetic declination
        yaw_mag += math.radians(self.config.get('magnetic_declination', 0.0))
        
        # Normalize to 0-2π
        yaw_mag = (yaw_mag + 2 * math.pi) % (2 * math.pi)
        
        # Complementary filter parameter
        alpha = dt / (self.filter_tau + dt)
        
        # Apply complementary filter
        roll_rad = (1 - alpha) * roll_gyro + alpha * roll_acc
        pitch_rad = (1 - alpha) * pitch_gyro + alpha * pitch_acc
        
        # For yaw, check if magnetometer data is valid before using it
        if mag_x != 0 or mag_y != 0:
            yaw_rad = (1 - alpha) * yaw_gyro + alpha * yaw_mag
        else:
            yaw_rad = yaw_gyro  # Use gyro only if no magnetometer data
        
        # Convert back to degrees
        roll = math.degrees(roll_rad)
        pitch = math.degrees(pitch_rad)
        yaw = math.degrees(yaw_rad)
        
        # Normalize angles
        roll = ((roll + 180) % 360) - 180  # -180 to 180
        pitch = max(-90, min(90, pitch))   # -90 to 90
        yaw = yaw % 360                    # 0 to 360
        
        # Calculate rates and accelerations
        roll_rate = math.degrees(gyro_x)
        pitch_rate = math.degrees(gyro_y)
        yaw_rate = math.degrees(gyro_z)
        
        roll_accel = (roll_rate - self.attitude['roll_rate']) / dt
        pitch_accel = (pitch_rate - self.attitude['pitch_rate']) / dt
        yaw_accel = (yaw_rate - self.attitude['yaw_rate']) / dt
        
        # Calculate angle of attack and sideslip (these would normally come from air data sensors)
        # Here we're approximating based on attitude
        alpha = pitch * 0.1 + pitch_rate * 0.01
        beta = -yaw_rate * 0.1
        
        # Calculate g-force based on accelerometer readings
        accel_magnitude = math.sqrt(accel_x**2 + accel_y**2 + accel_z**2)
        g_force = accel_magnitude / 9.81  # Convert to g units
        
        # Update quaternion if using quaternions
        if self.config.get('use_quaternions', True):
            self.attitude['quaternion'] = self._euler_to_quaternion(roll_rad, pitch_rad, yaw_rad)
        
        # Update attitude state
        self.attitude['roll'] = roll
        self.attitude['pitch'] = pitch
        self.attitude['yaw'] = yaw
        self.attitude['roll_rate'] = roll_rate
        self.attitude['pitch_rate'] = pitch_rate
        self.attitude['yaw_rate'] = yaw_rate
        self.attitude['roll_accel'] = roll_accel
        self.attitude['pitch_accel'] = pitch_accel
        self.attitude['yaw_accel'] = yaw_accel
        self.attitude['alpha'] = alpha
        self.attitude['beta'] = beta
        self.attitude['g_force'] = g_force
    
    def _update_attitude_kalman(self, gyro: Dict[str, float], 
                              accel: Dict[str, float],
                              mag: Dict[str, float],
                              dt: float):
        """
        Update attitude using Kalman filter.
        
        Args:
            gyro: Gyroscope readings (x,y,z in deg/s)
            accel: Accelerometer readings (x,y,z in m/s²)
            mag: Magnetometer readings (x,y,z in arbitrary units)
            dt: Time step in seconds
        """
        # This would be a full Kalman filter implementation for attitude estimation
        # For now, we'll use a simplified complementary filter
        self._update_attitude_complementary(gyro, accel, mag, dt)
    
    def _euler_to_quaternion(self, roll: float, pitch: float, yaw: float) -> List[float]:
        """
        Convert Euler angles to quaternion.
        
        Args:
            roll: Roll angle in radians
            pitch: Pitch angle in radians
            yaw: Yaw angle in radians
            
        Returns:
            Quaternion [w, x, y, z]
        """
        # Calculate half angles
        cr = math.cos(roll / 2)
        sr = math.sin(roll / 2)
        cp = math.cos(pitch / 2)
        sp = math.sin(pitch / 2)
        cy = math.cos(yaw / 2)
        sy = math.sin(yaw / 2)
        
        # Calculate quaternion components
        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy
        
        return [w, x, y, z]
    
    def _quaternion_to_euler(self, quaternion: List[float]) -> Tuple[float, float, float]:
        """
        Convert quaternion to Euler angles.
        
        Args:
            quaternion: Quaternion [w, x, y, z]
            
        Returns:
            Tuple of (roll, pitch, yaw) in radians
        """
        # Extract quaternion components
        w, x, y, z = quaternion
        
        # Roll (x-axis rotation)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        
        # Pitch (y-axis rotation)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)  # Use 90 degrees if out of range
        else:
            pitch = math.asin(sinp)
        
        # Yaw (z-axis rotation)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        
        return (roll, pitch, yaw)
    
    def get_euler_angles(self) -> Tuple[float, float, float]:
        """
        Get current Euler angles.
        
        Returns:
            Tuple of (roll, pitch, yaw) in degrees
        """
        return (
            self.attitude['roll'],
            self.attitude['pitch'],
            self.attitude['yaw']
        )
    
    def get_angular_rates(self) -> Tuple[float, float, float]:
        """
        Get current angular rates.
        
        Returns:
            Tuple of (roll_rate, pitch_rate, yaw_rate) in degrees/sec
        """
        return (
            self.attitude['roll_rate'],
            self.attitude['pitch_rate'],
            self.attitude['yaw_rate']
        )
    
    def get_quaternion(self) -> List[float]:
        """
        Get current attitude quaternion.
        
        Returns:
            Quaternion [w, x, y, z]
        """
        if self.config.get('use_quaternions', True):
            return self.attitude['quaternion']
        else:
            # Calculate quaternion from Euler angles if not using quaternions internally
            return self._euler_to_quaternion(
                math.radians(self.attitude['roll']),
                math.radians(self.attitude['pitch']),
                math.radians(self.attitude['yaw'])
            )
    
    def get_attitude(self) -> Dict[str, Any]:
        """
        Get complete attitude state.
        
        Returns:
            Dictionary with all attitude parameters
        """
        return self.attitude.copy()

# Singleton instance
_attitude_calculator = None

def get_attitude_calculator(config=None):
    """Get the singleton instance of the Attitude Calculator."""
    global _attitude_calculator
    if _attitude_calculator is None:
        _attitude_calculator = AttitudeCalculator(config)
    return _attitude_calculator

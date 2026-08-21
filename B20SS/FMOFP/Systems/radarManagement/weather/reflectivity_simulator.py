"""
Reflectivity Simulator Module

Generates realistic 3D reflectivity patterns for weather radar simulation with time-based evolution.
"""

import numpy as np
import random
import math
import time
from typing import Dict, Tuple, Any, Optional, List
from FMOFP.Utils.logger.sys_logger import get_logger
logger = get_logger()

# Import the weather state manager
from FMOFP.Systems.radarManagement.weather.weather_state_manager import WeatherStateManager, StormCell, StratiformArea

class ReflectivitySimulator:
    """Simulates realistic 3D reflectivity patterns for weather radar with time-based evolution."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the reflectivity simulator with configuration.
        
        Args:
            config: Dictionary containing radar configuration parameters
        """
        self.config = config
        # Get the singleton WeatherStateManager instance
        self.weather_state = WeatherStateManager.get_instance()
        
    def generate_reflectivity(self, mode_name: str, elevation_angles: Tuple[float, ...]) -> np.ndarray:
        """
        Generate a 3D volume of simulated reflectivity data with realistic weather patterns that evolve over time.
        
        Args:
            mode_name: Name of the radar mode (e.g., 'surveillance', 'mapping')
            elevation_angles: Tuple of elevation angles in degrees
            
        Returns:
            3D numpy array of reflectivity values (azimuth, elevation, range)
        """
        # Define dimensions
        azimuth_steps = 360  # 1-degree resolution
        elevation_steps = len(elevation_angles)
        range_steps = 200    # 200 km range
        
        # Create a 3D array to store reflectivity values
        reflectivity = np.zeros((azimuth_steps, elevation_steps, range_steps))
        
        # Get current time for updates
        current_time = time.time()
        
        # Initialize weather state if needed
        with self.weather_state._lock:
            if not self.weather_state.initialized or (not self.weather_state.storm_cells and not self.weather_state.stratiform_areas):
                logger.warning("WARNING: No active weather systems found. Initializing weather state.")
                self._initialize_weather_state()
                
            # Calculate time delta since last update
            delta_time = current_time - self.weather_state.last_update_time
            
            # Update all weather systems
            self._update_weather_systems(delta_time)
            
            # Update last update time
            self.weather_state.last_update_time = current_time
            
            # Render all weather systems to the reflectivity array
            self._render_storm_cells(reflectivity, elevation_steps)
            self._render_stratiform_areas(reflectivity, elevation_steps)
        
        # Add ground clutter (this doesn't need to be persistent)
        self._add_ground_clutter(reflectivity, azimuth_steps, elevation_steps)
        
        # Ensure reflectivity values are within a realistic range
        reflectivity = np.clip(reflectivity, -20, 65)
        
        return reflectivity
    
    def _initialize_weather_state(self) -> None:
        """Initialize the weather state with randomized weather systems."""
        # Create storm cells
        num_cells = random.randint(3, 8)
        for _ in range(num_cells):
            cell_az = random.uniform(0, 360)
            cell_range = random.uniform(20, 180)
            cell_size = random.uniform(5, 20)
            cell_intensity = random.uniform(35, 65)
            
            # Create vertical development profile
            vertical_dev = {}
            for i in range(10):  # Reasonable max elevations
                if i < 4:  # Lower levels have more reflectivity
                    vertical_dev[i] = 1.0 - (i * 0.1)
                else:  # Higher levels have less
                    vertical_dev[i] = max(0.2, 1.0 - (i * 0.2))
            
            # Create and add storm cell
            cell = StormCell((cell_az, cell_range), cell_size, cell_intensity, vertical_dev)
            self.weather_state.storm_cells.append(cell)
            
            # Debug logging to verify cell creation
            logger.info(f"Created storm cell at az={cell_az:.1f}, range={cell_range:.1f}, size={cell_size:.1f}, intensity={cell_intensity:.1f}")
        
        # Create stratiform areas
        if random.random() < 0.7:  # 70% chance of stratiform precipitation
            area_az = random.uniform(0, 360)
            area_width = random.uniform(60, 180)
            area_range = random.uniform(10, 100)
            area_depth = random.uniform(30, 100)
            area_intensity = random.uniform(15, 30)
            
            # Create and add stratiform area
            area = StratiformArea((area_az, area_range), area_width, area_depth, area_intensity)
            self.weather_state.stratiform_areas.append(area)
            logger.info(f"Created stratiform area at az={area_az:.1f}, range={area_range:.1f}, width={area_width:.1f}, depth={area_depth:.1f}, intensity={area_intensity:.1f}")
        else:
            # Ensure we have at least one stratiform area if randomness didn't create one
            area_az = random.uniform(0, 360)
            area_width = random.uniform(60, 180)
            area_range = random.uniform(10, 100)
            area_depth = random.uniform(30, 100)
            area_intensity = random.uniform(15, 30)
            
            area = StratiformArea((area_az, area_range), area_width, area_depth, area_intensity)
            self.weather_state.stratiform_areas.append(area)
            logger.info(f"Created backup stratiform area at az={area_az:.1f}, range={area_range:.1f}, width={area_width:.1f}, depth={area_depth:.1f}, intensity={area_intensity:.1f}")
        
        # Mark as initialized
        self.weather_state.initialized = True
        
        # Debug logging to confirm initialization
        logger.info(f"Weather state initialized with {len(self.weather_state.storm_cells)} storm cells and {len(self.weather_state.stratiform_areas)} stratiform areas")
    
    def _update_weather_systems(self, delta_time: float) -> None:
        """
        Update all weather systems based on time delta.
        
        Args:
            delta_time: Time in seconds since last update
        """
        # Update storm cells
        active_cells = []
        for cell in self.weather_state.storm_cells:
            if cell.update(delta_time, self.weather_state.wind['altitude']):
                active_cells.append(cell)
        
        # Replace expired cells with new ones (to maintain roughly same number)
        expired_count = len(self.weather_state.storm_cells) - len(active_cells)
        for _ in range(expired_count):
            if random.random() < 0.7:  # 70% chance to replace
                # Create new cell at edge of radar range, opposite to wind direction
                entry_azimuth = (self.weather_state.wind['altitude']['direction'] + 180) % 360
                entry_azimuth += random.uniform(-30, 30)  # +/- 30 degrees variation
                
                cell_az = entry_azimuth
                cell_range = 180  # Start at far range
                cell_size = random.uniform(5, 20)
                cell_intensity = random.uniform(35, 45)  # Start less intense
                
                # Create vertical development profile
                vertical_dev = {}
                for i in range(10):
                    vertical_dev[i] = max(0.2, 1.0 - (i * 0.15))
                
                # Create and add storm cell
                cell = StormCell((cell_az, cell_range), cell_size, cell_intensity, vertical_dev)
                active_cells.append(cell)
        
        self.weather_state.storm_cells = active_cells
        
        # Update stratiform areas
        active_areas = []
        for area in self.weather_state.stratiform_areas:
            if area.update(delta_time, self.weather_state.wind['surface']):
                active_areas.append(area)
        
        # Replace expired areas
        if not active_areas and random.random() < 0.3:  # 30% chance to add new if none exist
            area_az = (self.weather_state.wind['surface']['direction'] + 180) % 360
            area_az += random.uniform(-45, 45)
            area_width = random.uniform(60, 180)
            area_range = 180  # Start at far range
            area_depth = random.uniform(30, 100)
            area_intensity = random.uniform(15, 30)
            
            area = StratiformArea((area_az, area_range), area_width, area_depth, area_intensity)
            active_areas.append(area)
        
        self.weather_state.stratiform_areas = active_areas
    
    def _render_storm_cells(self, reflectivity: np.ndarray, elevation_steps: int) -> None:
        """
        Render all storm cells to the reflectivity array.
        
        Args:
            reflectivity: 3D array to modify
            elevation_steps: Number of elevation steps
        """
        azimuth_steps, _, range_steps = reflectivity.shape
        
        # Check if we have storm cells to render
        if not self.weather_state.storm_cells:
            logger.warning("No storm cells to render in _render_storm_cells")
            # Add at least one cell to ensure we have data
            cell_az = random.uniform(0, 360)
            cell_range = random.uniform(20, 180)
            cell_size = random.uniform(5, 20)
            cell_intensity = random.uniform(35, 65)
            
            # Create vertical development profile
            vertical_dev = {}
            for i in range(10):  # Reasonable max elevations
                if i < 4:  # Lower levels have more reflectivity
                    vertical_dev[i] = 1.0 - (i * 0.1)
                else:  # Higher levels have less
                    vertical_dev[i] = max(0.2, 1.0 - (i * 0.2))
            
            # Create and add storm cell
            cell = StormCell((cell_az, cell_range), cell_size, cell_intensity, vertical_dev)
            self.weather_state.storm_cells.append(cell)
            logger.info(f"Created emergency storm cell at az={cell_az:.1f}, range={cell_range:.1f}, size={cell_size:.1f}, intensity={cell_intensity:.1f}")
        
        cells_added = 0
        for cell in self.weather_state.storm_cells:
            # Extract cell properties
            cell_az, cell_range = cell.position
            cell_size = cell.size
            cell_intensity = cell.intensity
            
            # Convert to array indices
            cell_az_idx = int(cell_az) % azimuth_steps
            cell_range_idx = min(range_steps - 1, int(cell_range))
            
            points_added = 0
            # Render cell at each azimuth and range
            for az in range(azimuth_steps):
                az_diff = min(abs(az - cell_az_idx), 
                             abs(az - cell_az_idx + azimuth_steps), 
                             abs(az - cell_az_idx - azimuth_steps))
                az_factor = max(0, 1 - (az_diff / (cell_size * 0.5)))
                
                for r in range(range_steps):
                    r_diff = abs(r - cell_range_idx)
                    r_factor = max(0, 1 - (r_diff / cell_size))
                    
                    combined_factor = az_factor * r_factor
                    if combined_factor > 0:
                        for el in range(elevation_steps):
                            # Apply vertical development profile
                            el_factor = cell.vertical_development.get(el, 0.1)
                            
                            # Calculate new reflectivity value
                            new_value = cell_intensity * combined_factor * el_factor
                            
                            # Only count as a point if it's significant
                            if new_value > 5:
                                points_added += 1
                            
                            # Add reflectivity to the array
                            reflectivity[az, el, r] = max(
                                reflectivity[az, el, r],
                                new_value
                            )
            cells_added += 1
            logger.info(f"Rendered storm cell {cells_added} with {points_added} significant reflectivity points")
    
    def _render_stratiform_areas(self, reflectivity: np.ndarray, elevation_steps: int) -> None:
        """
        Render all stratiform areas to the reflectivity array.
        
        Args:
            reflectivity: 3D array to modify
            elevation_steps: Number of elevation steps
        """
        azimuth_steps, _, range_steps = reflectivity.shape
        
        # Check if we have stratiform areas to render
        if not self.weather_state.stratiform_areas:
            logger.warning("No stratiform areas to render in _render_stratiform_areas")
            # Add at least one area to ensure we have data
            area_az = random.uniform(0, 360)
            area_width = random.uniform(60, 180)
            area_range = random.uniform(10, 100)
            area_depth = random.uniform(30, 100)
            area_intensity = random.uniform(15, 30)
            
            area = StratiformArea((area_az, area_range), area_width, area_depth, area_intensity)
            self.weather_state.stratiform_areas.append(area)
            logger.info(f"Created emergency stratiform area at az={area_az:.1f}, range={area_range:.1f}, width={area_width:.1f}, depth={area_depth:.1f}, intensity={area_intensity:.1f}")
        
        areas_added = 0
        for area in self.weather_state.stratiform_areas:
            # Extract area properties
            area_az, area_range = area.position
            area_width = area.az_width
            area_depth = area.range_depth
            area_intensity = area.intensity
            
            # Convert to array indices
            area_az_idx = int(area_az) % azimuth_steps
            area_range_idx = min(range_steps - 1, int(area_range))
            
            # Calculate boundaries
            az_half_width = int(area_width / 2)
            range_half_depth = int(area_depth / 2)
            
            # Calculate start and end indices with wrapping for azimuth
            az_start = (area_az_idx - az_half_width) % azimuth_steps
            az_end = (area_az_idx + az_half_width) % azimuth_steps
            range_start = max(0, area_range_idx - range_half_depth)
            range_end = min(range_steps - 1, area_range_idx + range_half_depth)
            
            # Handle wrap-around case for azimuth
            if az_start > az_end:
                az_ranges = [(az_start, azimuth_steps), (0, az_end)]
            else:
                az_ranges = [(az_start, az_end)]
            
            points_added = 0
            # Render stratiform area
            for az_range in az_ranges:
                for az in range(az_range[0], az_range[1]):
                    for r in range(range_start, range_end + 1):
                        # Calculate distance from center as fraction of area size
                        az_dist = min(abs(az - area_az_idx),
                                     abs(az - area_az_idx + azimuth_steps),
                                     abs(az - area_az_idx - azimuth_steps)) / max(1, az_half_width)  # Prevent division by zero
                        r_dist = abs(r - area_range_idx) / max(1, range_half_depth)  # Prevent division by zero
                        
                        # Intensity decreases from center
                        factor = max(0, 1 - math.sqrt(az_dist**2 + r_dist**2))
                        
                        if factor > 0:
                            for el in range(min(3, elevation_steps)):  # Lower elevations only
                                # Add some variability
                                noise = random.uniform(-2, 2)
                                intensity = area_intensity * factor + noise
                                
                                # Count significant point
                                if intensity > 5:
                                    points_added += 1
                                
                                # Only replace if new intensity is higher
                                if intensity > reflectivity[az, el, r]:
                                    reflectivity[az, el, r] = intensity
            
            areas_added += 1
            logger.info(f"Rendered stratiform area {areas_added} with {points_added} significant reflectivity points")
    
    def _add_ground_clutter(self, reflectivity: np.ndarray, azimuth_steps: int, 
                           elevation_steps: int) -> None:
        """
        Add ground clutter near the radar.
        
        Args:
            reflectivity: 3D array to modify
            azimuth_steps: Number of azimuth steps
            elevation_steps: Number of elevation steps
        """
        # Add ground clutter near the radar
        for az in range(azimuth_steps):
            for r in range(10):  # First 10 km
                for el in range(min(2, elevation_steps)):  # Lowest elevations
                    if reflectivity[az, el, r] < 10:
                        reflectivity[az, el, r] = 10 + 5 * random.random()

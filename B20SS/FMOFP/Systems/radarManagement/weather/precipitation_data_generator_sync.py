"""
Synchronous Precipitation Data Generator Module

Optimized version of the precipitation data generator with no asyncio dependencies,
hard limits on data points, and aggressive downsampling for performance.
"""

import numpy as np
import uuid
import time
import math
from typing import Dict, Tuple, List, Any, Optional
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

def round_to_sigfigs(x, n_sigfigs=3):
    """
    Round values to specified number of significant figures.
    
    Works with both scalar values and numpy arrays.
    Handles zero, NaN, and infinity values appropriately.
    
    Args:
        x: Value or numpy array to round
        n_sigfigs: Number of significant figures (default: 3)
        
    Returns:
        Rounded value(s) with specified number of significant figures
    """
    if isinstance(x, np.ndarray):
        # Handle arrays
        # Create a mask for non-zero, finite values
        mask = (x != 0) & np.isfinite(x)
        
        # Initialize result array as a copy of the input
        result = x.copy()
        
        if np.any(mask):
            # Only process non-zero, finite values
            masked_x = x[mask]
            
            # Calculate the order of magnitude
            magnitude = np.floor(np.log10(np.abs(masked_x)))
            
            # Calculate the scale factor for each element
            scale = 10 ** (n_sigfigs - magnitude - 1)
            
            # Round and scale back
            result[mask] = np.round(masked_x * scale) / scale
            
        return result
    else:
        # Handle scalar values
        if x == 0 or not np.isfinite(x):
            return x
            
        # Calculate the order of magnitude
        magnitude = math.floor(math.log10(abs(x)))
        
        # Calculate the scale factor
        scale = 10 ** (n_sigfigs - magnitude - 1)
        
        # Round and scale back
        return round(x * scale) / scale

# Constants for limits and thresholds
MAX_PRECIPITATION_POINTS = 500   # Hard limit on precipitation points processed
DOWNSAMPLE_THRESHOLD = 1000      # When to start downsampling
RATE_THRESHOLD = 0.1             # Minimum precipitation rate to be considered

class PrecipitationDataGenerator:
    """Generates precipitation data from reflectivity data."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the precipitation data generator with configuration.
        
        Args:
            config: Dictionary containing radar configuration parameters
        """
        self.config = config
    
    def calculate_precipitation(self, reflectivity: np.ndarray, elevation_angles: Tuple[float, ...]) -> np.ndarray:
        """
        Calculate precipitation rates from reflectivity volume scan.
        
        Uses the standard Z-R relationship: Z = a * R^b
        where Z is the reflectivity factor and R is the rainfall rate.
        
        Args:
            reflectivity: 3D array of reflectivity values (azimuth, elevation, range)
            elevation_angles: Tuple of elevation angles in degrees
            
        Returns:
            2D numpy array of precipitation values (azimuth, range)
        """
        if reflectivity is None:
            return None
        
        # Get dimensions
        azimuth_steps, elevation_steps, range_steps = reflectivity.shape
        
        # Initialize precipitation array (2D - azimuth x range)
        precipitation = np.zeros((azimuth_steps, range_steps))
        
        # Ensure we have enough elevation angles
        if len(elevation_angles) < elevation_steps:
            # Fill in missing elevations with reasonable values
            elevation_angles = list(elevation_angles)
            for i in range(len(elevation_angles), elevation_steps):
                elevation_angles.append(elevation_angles[-1] + 1.5)
        
        # Z-R relationship parameters (Marshall-Palmer)
        a = 200  # Default coefficient
        b = 1.6  # Default exponent
        
        # Use config values if available
        if 'precip_params' in self.config:
            a = self.config['precip_params'].get('a', a)
            b = self.config['precip_params'].get('b', b)
        
        # Calculate precipitation for each column
        for az in range(azimuth_steps):
            for r in range(range_steps):
                # Find maximum reflectivity in the column
                max_dbz = -np.inf
                for el in range(elevation_steps):
                    dbz = reflectivity[az, el, r]
                    if dbz > max_dbz:
                        max_dbz = dbz
                
                # Convert dBZ to Z (mm^6/m^3)
                if max_dbz > 0:  # Only process positive reflectivity
                    z = 10 ** (max_dbz / 10)
                    z = round_to_sigfigs(z)  # Round Z value
                    
                    # Apply Z-R relationship: Z = a * R^b, solve for R
                    # R = (Z/a)^(1/b)
                    rain_rate = (z / a) ** (1 / b)
                    rain_rate = round_to_sigfigs(rain_rate)  # Round rain rate
                    
                    # Store precipitation rate
                    precipitation[az, r] = rain_rate
        
        # Round the entire precipitation array before returning
        precipitation = round_to_sigfigs(precipitation)
        return precipitation
    
    def generate_precipitation_data_objects(self, precip_array: np.ndarray, request_id: Optional[str] = None) -> List[Any]:
        """
        Generate precipitation data objects from a 2D precipitation array with trajectory-based sampling for continuity.
        Fully synchronous implementation with aggressive downsampling and hard limits.
        
        Args:
            precip_array: 2D array of precipitation values (azimuth, range)
            request_id: Optional request ID to include in the data objects
            
        Returns:
            List of PrecipitationData objects
        """
        # Import radar-local message classes to respect system boundaries
        from FMOFP.Systems.radarManagement.radar_messaging.message_definitions import PrecipitationData
        from FMOFP.Systems.radarManagement.weather.weather_state_manager import WeatherStateManager
        import random
        
        # Performance tracking
        start_time = round_to_sigfigs(time.time())
        
        # Get the singleton weather state manager
        weather_state = WeatherStateManager.get_instance()
        
        # Create precipitation data objects from the calculated values
        precip_objects = []
        
        if not request_id:
            raise ValueError("[PRECIP_DATA_GEN_SYNC] No request ID provided for precipitation data generation.")
        
        # Current time - round to 3 significant digits
        current_time = round_to_sigfigs(time.time())
        
        # FAST PATH: Handle empty/None data with quick check - return empty list
        if precip_array is None or precip_array.size == 0:
            logger.warning("[WEATHER][PRECIP] Precipitation array is empty or None. Returning empty list.")
            return []

        # Quick check for significant values using sampling
        sample_max = np.max(precip_array[::10, ::10]) if precip_array.size > 100 else np.max(precip_array)
        sample_max = round_to_sigfigs(sample_max)  # Round max value
        if sample_max <= RATE_THRESHOLD:
            logger.warning(f"[WEATHER][PRECIP] No significant precipitation found (max = {sample_max:.2f}). Returning empty list.")
            return []
        
        # AGGRESSIVE DOWNSAMPLING: Reduce array size if too large
        original_shape = precip_array.shape
        if precip_array.size > DOWNSAMPLE_THRESHOLD:
            # Calculate downsample factor based on array size
            factor = max(2, int(np.sqrt(precip_array.size / DOWNSAMPLE_THRESHOLD)))
            
            # Apply downsampling
            precip_array = precip_array[::factor, ::factor]
            
            # Round the downsampled array
            precip_array = round_to_sigfigs(precip_array)
            
            logger.info(f"[WEATHER] Downsampled precipitation array from {original_shape} to {precip_array.shape} (factor {factor})")
            
        # Get dimensions after potential downsampling
        azimuth_steps, range_steps = precip_array.shape
            
        # OPTIMIZATION: Get only significant precipitation points
        # Only get points above the threshold to reduce processing
        threshold_mask = precip_array > RATE_THRESHOLD
        nonzero_count = np.count_nonzero(threshold_mask)
        
        # Log with actual count
        logger.info(f"[WEATHER] Found {nonzero_count} significant precipitation points above threshold {RATE_THRESHOLD}")
        
        # Get the indices of significant points
        az_indices, r_indices = np.nonzero(threshold_mask)
        
        # HARD LIMIT: Apply a hard limit to the number of points processed
        if len(az_indices) > MAX_PRECIPITATION_POINTS:
            # Random selection ensures a good distribution across the field
            keep_indices = np.random.choice(len(az_indices), MAX_PRECIPITATION_POINTS, replace=False)
            az_indices = az_indices[keep_indices]
            r_indices = r_indices[keep_indices]
            
            logger.info(f"[WEATHER] Limited to {MAX_PRECIPITATION_POINTS} precipitation points (from {nonzero_count})")
            
        # If no significant points, return empty list
        if len(az_indices) == 0:
            logger.warning("[WEATHER][PRECIP] No precipitation points found after filtering. Returning empty list.")
            return []
        
        # Use time as a seed for deterministic type assignment
        sampling_seed = int(current_time / 30)  # Changes every 30 seconds
        sampling_rng = random.Random(sampling_seed)
        
        # VECTORIZED CALCULATION: Convert to coordinates all at once
        # Convert to normalized coordinates
        normalized_az = az_indices / azimuth_steps  # 0-1 range
        normalized_range = r_indices / range_steps  # 0-1 range
        
        # Round normalized coordinates
        normalized_az = round_to_sigfigs(normalized_az)
        normalized_range = round_to_sigfigs(normalized_range)
        
        # Convert to radar-centric coordinates
        azimuth_rads = np.radians(normalized_az * 360.0)
        range_nms = round_to_sigfigs(normalized_range * 40.0)  # 40 nm max range
            
        # Vectorized coordinate conversion
        x_coords = round_to_sigfigs(range_nms * np.sin(azimuth_rads))
        y_coords = round_to_sigfigs(range_nms * np.cos(azimuth_rads))
        
        # ENHANCED VALIDATION: Filter out invalid coordinates and zero positions
        valid_indices = ~(np.isnan(x_coords) | np.isnan(y_coords) | 
                         np.isinf(x_coords) | np.isinf(y_coords) |
                         ((np.abs(x_coords) < 0.5) & (np.abs(y_coords) < 0.5)))  # Filter out positions near (0,0)
        
        # Log how many points were filtered out
        filtered_count = len(az_indices) - np.sum(valid_indices)
        if filtered_count > 0:
            logger.warning(f"[WEATHER] Filtered out {filtered_count} precipitation points with invalid or zero coordinates")
        
        # Filter the coordinate and rate arrays
        x_coords = x_coords[valid_indices]
        y_coords = y_coords[valid_indices]
        rates = round_to_sigfigs(precip_array[az_indices, r_indices][valid_indices])
            
        # RETRY MECHANISM: If too many points were filtered out, try to regenerate
        retry_count = 0
        max_retries = 3
        
        while len(x_coords) < 5 and retry_count < max_retries:  # Ensure we have at least 5 points
            retry_count += 1
            logger.warning(f"[WEATHER] Insufficient valid precipitation points ({len(x_coords)}). Retry {retry_count}/{max_retries}...")
            
            # Adjust the selection criteria - use different azimuth/range
            # This creates a different set of points with different coordinates
            azimuth_offset = retry_count * 7  # Shift the azimuth by 7 degrees on each retry
            range_offset = retry_count * 3    # Shift the range by 3 units on each retry
            
            # Create new indices by offsetting the originals
            new_az_indices = (az_indices + azimuth_offset) % azimuth_steps
            new_r_indices = np.clip(r_indices + range_offset, 0, range_steps - 1)
            
            # Recalculate coordinates with rounding
            new_azimuth_rads = np.radians(new_az_indices)
            new_range_nms = round_to_sigfigs(new_r_indices * 0.539957)  # Convert km to nm with rounding
            
            # Calculate new coordinates with rounding
            new_x_coords = round_to_sigfigs(new_range_nms * np.sin(new_azimuth_rads))
            new_y_coords = round_to_sigfigs(new_range_nms * np.cos(new_azimuth_rads))
            
            # Filter out invalid or zero coordinates
            new_valid_indices = ~(np.isnan(new_x_coords) | np.isnan(new_y_coords) | 
                                np.isinf(new_x_coords) | np.isinf(new_y_coords) |
                                ((new_x_coords == 0.0) & (new_y_coords == 0.0)))
            
            # If we found new valid points, add them to our existing arrays
            if np.any(new_valid_indices):
                # Append the new valid coordinates and values
                x_coords = np.append(x_coords, new_x_coords[new_valid_indices])
                y_coords = np.append(y_coords, new_y_coords[new_valid_indices])
                
                # Get the corresponding precipitation rates with rounding
                new_rates = precip_array[new_az_indices[new_valid_indices], new_r_indices[new_valid_indices]]
                new_rates = round_to_sigfigs(new_rates)  # Round the new rates
                rates = np.append(rates, new_rates)
                
                logger.warning(f"[WEATHER] Added {np.sum(new_valid_indices)} new precipitation points on retry {retry_count}")
                
                # If we have enough points, break out of the retry loop
                if len(x_coords) >= 5:
                    break
        
        # If we still don't have any valid points after all retries, log and return empty
        if len(x_coords) == 0:
            logger.error("[WEATHER] Failed to generate any valid precipitation points after multiple retries.")
            return []
            
        # If we have fewer than expected but not zero, continue with what we have
        if len(x_coords) < 5:
            logger.warning(f"[WEATHER] Proceeding with limited precipitation points ({len(x_coords)}) after {retry_count} retries")
            
        # Create precipitation objects using filtered array lengths
        # All arrays should have the same length after filtering, but we'll use the length of rates to be safe
        logger.warning(f"[WEATHER] Creating {len(rates)} precipitation objects from filtered data")
        logger.warning(f"[WEATHER] Arrays lengths after filtering - rates: {len(rates)}, x_coords: {len(x_coords)}, y_coords: {len(y_coords)}")
        
        for i in range(len(rates)):  # Use the filtered array length
            rate = rates[i]
            
            # Extra safety check to ensure we don't go out of bounds
            if i >= len(x_coords) or i >= len(y_coords):
                logger.error(f"[WEATHER] Index {i} out of bounds for coordinate arrays (x_coords: {len(x_coords)}, y_coords: {len(y_coords)})")
                continue
                
            # Determine precipitation type based on rate and time-seeded randomness
            if rate > 50:
                precip_type = 'hail'
            elif rate > 25:
                precip_type = 'mixed'
            elif rate > 10:
                precip_type = 'rain'
            else:
                precip_type = 'snow' if sampling_rng.random() < 0.3 else 'rain'
                
            # Normalize intensity to 0-1 range and round
            intensity = round_to_sigfigs(min(1.0, rate / 50.0))
                
            # STRONGER VALIDATION: Final check before creating the object
            # No need for individual coordinate validation as we're using the filtered arrays
            # But we'll add it anyway for extra safety
            if (np.isnan(x_coords[i]) or np.isnan(y_coords[i]) or 
                np.isinf(x_coords[i]) or np.isinf(y_coords[i]) or
                (x_coords[i] == 0.0 and y_coords[i] == 0.0)):
                logger.warning(f"[WEATHER] Skipping precipitation point with invalid coordinates: ({x_coords[i]}, {y_coords[i]})")
                continue
            
            # Create precipitation data object with explicit float casting for coordinates
            precip_obj = PrecipitationData(
                position=(round_to_sigfigs(float(x_coords[i])), round_to_sigfigs(float(y_coords[i]))),
                type=precip_type,
                rate=round_to_sigfigs(rate),
                intensity=intensity,
                show_values=(intensity > 0.3)
            )
                
            # Set request ID and timestamp
            precip_obj.request_id = request_id
            precip_obj.timestamp = current_time
                
            # Add metadata
            precip_obj.additional_info = {
                'original_request_id': request_id,
                'precipitation_message': True
            }
            
            # Verify that all numeric values are properly rounded
            # This ensures no full-precision values slip through
            if hasattr(precip_obj, 'rate'):
                precip_obj.rate = round_to_sigfigs(precip_obj.rate)
            if hasattr(precip_obj, 'intensity'):
                precip_obj.intensity = round_to_sigfigs(precip_obj.intensity)
            if hasattr(precip_obj, 'position') and isinstance(precip_obj.position, tuple) and len(precip_obj.position) == 2:
                precip_obj.position = (round_to_sigfigs(precip_obj.position[0]), round_to_sigfigs(precip_obj.position[1]))
                
            precip_objects.append(precip_obj)
        
        # MIL-STD-1553B COMPLIANCE: Limit to 15 data points for 32-word limit
        # Each precipitation object uses 2 data words, so 15 objects = 30 words
        if len(precip_objects) > 15:
            # Get wind vector for surface level (where precipitation typically forms)
            wind_vector = weather_state.get_wind('surface')
            
            # Calculate time since last update with rounding
            time_delta = round_to_sigfigs(current_time - weather_state.last_sampling_time)
            
            # Use trajectory-aware sampling to select points
            selected_indices = weather_state.sample_points_with_trajectory(
                'precip',           # Data type
                precip_objects,     # All candidate points
                15,                 # Maximum points to display
                wind_vector,        # Current wind vector
                time_delta,         # Time since last sampling
                current_time        # Current time
            )
            
            # Update tracking for the selected points
            weather_state.update_tracked_points(
                'precip',           # Data type
                [precip_objects[i] for i in selected_indices],
                wind_vector,
                current_time
            )
            
            # Use the trajectory-aware selection - ensure we're returning data
            selected_objects = [precip_objects[i] for i in selected_indices]
            
            # Performance tracking with rounding
            elapsed_time = round_to_sigfigs(time.time() - start_time)
            logger.info(f"[WEATHER] Precipitation data generation completed in {elapsed_time:.3f} seconds")
            
            # Return the selected objects
            return selected_objects
        
        # Performance tracking with rounding
        elapsed_time = round_to_sigfigs(time.time() - start_time)
        logger.info(f"[WEATHER] Precipitation data generation completed in {elapsed_time:.3f} seconds with {len(precip_objects)} objects")
        
        # Return all objects if <= 15
        return precip_objects
    
    def create_precipitation_response(self, precip_objects: List[Any], request_id: str, current_mode: str = None) -> Any:
        """
        Create a precipitation response message with the generated precipitation data objects.
        
        Args:
            precip_objects: List of PrecipitationData objects
            request_id: Request ID to include in the response
            current_mode: Current radar mode (optional)
            
        Returns:
            WeatherRadarPrecipitationResponse object
        """
        # Import radar-local message classes to respect system boundaries
        from FMOFP.Systems.radarManagement.radar_messaging.message_definitions import WeatherRadarPrecipitationResponse
        
        # Import message type constants
        from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
            WEATHER_RADAR_PRECIPITATION_RESPONSE,
            COMMAND_TYPE_PRECIPITATION_DATA
        )
        
        # Create response message with the original request ID
        # Use "radar" as the system ID (not "weather_radar" which is a subaddress ID)
        response = WeatherRadarPrecipitationResponse(
            message_header="precipitation_data",
            sending_system="radar", # Changed from "weather_radar" to "radar" to match valid system ID in address book
            destination="displays",
            request_id=request_id,
            response_uuid=request_id,  # Use the same UUID for request and response
            precipitation_data=precip_objects
        )
        
        # Ensure all data objects have 3 significant digits
        for obj in precip_objects:
            if hasattr(obj, 'rate'):
                obj.rate = round_to_sigfigs(obj.rate)
            if hasattr(obj, 'intensity'):
                obj.intensity = round_to_sigfigs(obj.intensity)
            if hasattr(obj, 'position') and isinstance(obj.position, tuple) and len(obj.position) == 2:
                obj.position = (round_to_sigfigs(obj.position[0]), round_to_sigfigs(obj.position[1]))
        
        # Add metadata to track the message flow
        if hasattr(response, 'additional_info'):
            response.additional_info['original_request_id'] = request_id
            response.additional_info['precipitation_message'] = True
            response.additional_info['command_type'] = "data_response"  
            if current_mode:
                response.additional_info['mode'] = current_mode
        else:
            additional_info = {
                'original_request_id': request_id,
                'precipitation_message': True,
                'command_type': "data_response"  
            }
            if current_mode:
                additional_info['mode'] = current_mode
            response.additional_info = additional_info
        
        return response

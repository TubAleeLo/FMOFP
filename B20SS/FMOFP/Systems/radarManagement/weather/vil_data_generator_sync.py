"""
Synchronous VIL Data Generator Module

Optimized version that calculates and generates Vertically Integrated Liquid (VIL) 
data from reflectivity data with no asyncio dependencies and aggressive downsampling.
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
MAX_VIL_POINTS = 500         # Hard limit on VIL points processed
DOWNSAMPLE_THRESHOLD = 1000  # When to start downsampling
VIL_THRESHOLD = 0.1          # Minimum VIL value to be considered significant

class VILDataGenerator:
    """Generates VIL data from reflectivity data with synchronous implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the VIL data generator with configuration.
        
        Args:
            config: Dictionary containing radar configuration parameters
        """
        self.config = config
    
    def calculate_vil(self, reflectivity: np.ndarray, elevation_angles: Tuple[float, ...]) -> np.ndarray:
        """
        Calculate Vertically Integrated Liquid (VIL) from reflectivity volume scan.
        
        Uses the standard meteorological formula: VIL = Σ(3.44 × 10^-6 × Z^4/7 × Δh)
        where Z is the linear reflectivity factor and Δh is the layer thickness in meters.
        
        Args:
            reflectivity: 3D array of reflectivity values (azimuth, elevation, range)
            elevation_angles: Tuple of elevation angles in degrees
            
        Returns:
            2D numpy array of VIL values (azimuth, range)
        """
        if reflectivity is None:
            return None
        
        # Get dimensions
        azimuth_steps, elevation_steps, range_steps = reflectivity.shape
        
        # Initialize VIL array (2D - azimuth x range)
        vil = np.zeros((azimuth_steps, range_steps))
        
        # Ensure we have enough elevation angles
        if len(elevation_angles) < elevation_steps:
            # Fill in missing elevations with reasonable values
            elevation_angles = list(elevation_angles)
            for i in range(len(elevation_angles), elevation_steps):
                elevation_angles.append(elevation_angles[-1] + 1.5)
        
        # Calculate layer thickness (in meters)
        layer_thickness = []
        for i in range(elevation_steps - 1):
            # Calculate thickness based on elevation angle difference
            # This is a simplification - in reality it depends on beam width and range
            thickness = 1000 * (np.sin(np.radians(elevation_angles[i+1])) - 
                               np.sin(np.radians(elevation_angles[i])))
            layer_thickness.append(max(100, thickness))  # Minimum 100m thickness
                
        # Add a final layer and ensure all layer thicknesses are rounded
        layer_thickness.append(layer_thickness[-1] if layer_thickness else 1000)
        layer_thickness = [round_to_sigfigs(thickness) for thickness in layer_thickness]
        
        # Calculate VIL for each column
        for az in range(azimuth_steps):
            for r in range(range_steps):
                for el in range(elevation_steps):
                    # Get reflectivity in dBZ
                    dbz = reflectivity[az, el, r]
                
                    # Convert dBZ to Z (mm^6/m^3)
                    if dbz > 0:  # Only process positive reflectivity
                        z = 10 ** (dbz / 10)
                        z = round_to_sigfigs(z)  # Round Z value
                        
                        # Apply VIL formula: 3.44 × 10^-3 × Z^4/7 × Δh
                        # The 4/7 power approximates the Z-M relationship
                        vil_contribution = (3.44 * 10**-3) * (z ** (4/7)) * layer_thickness[el]
                        vil_contribution = round_to_sigfigs(vil_contribution)  # Round contribution
                        
                        # Add to total VIL
                        vil[az, r] += vil_contribution # Convert to kg/m²
        
        # Round the entire VIL array before returning
        vil = round_to_sigfigs(vil)
        return vil
    
    def generate_vil_data_objects(self, vil_array: np.ndarray, request_id: Optional[str] = None) -> List[Any]:
        """
        Generate VIL data objects from a 2D VIL array with optimized performance.
        
        Args:
            vil_array: 2D array of VIL values (azimuth, range)
            request_id: Optional request ID to include in the data objects
            
        Returns:
            List of WeatherRadarVILData objects, or empty list if no significant data
        """
# Import radar-local message classes to respect system boundaries
        from FMOFP.Systems.radarManagement.radar_messaging.message_definitions import WeatherRadarVILData
        from FMOFP.Systems.radarManagement.weather.weather_state_manager import WeatherStateManager
        
        # Performance tracking
        start_time = round_to_sigfigs(time.time())
        
        # Get the singleton weather state manager
        weather_state = WeatherStateManager.get_instance()
        
        # Create VIL data objects from the calculated values
        vil_objects = []
        
        if not request_id:
            
            raise ValueError("[VIL_DATA_GENERATOR_SYNC] Request ID is required for VIL data generation.")

        # Log the request ID being used
        logger.debug(f"[WEATHER][VIL] Generating VIL data objects with request ID: {request_id}")
        
        # Get current time and round to 3 significant digits
        current_time = round_to_sigfigs(time.time())
        
        # FAST PATH: Handle empty/None data with quick check - return empty list
        if vil_array is None or vil_array.size == 0:
            logger.warning("[WEATHER][VIL] VIL array is empty or None. Returning empty list.")
            return []

        # Quick check for significant values using sampling
        sample_max = np.max(vil_array[::10, ::10]) if vil_array.size > 100 else np.max(vil_array)
        sample_max = round_to_sigfigs(sample_max)
        if sample_max <= VIL_THRESHOLD:
            logger.warning(f"[WEATHER][VIL] No significant VIL values found (max = {sample_max:.2f}). Returning empty list.")
            return []
        
        # AGGRESSIVE DOWNSAMPLING: Reduce array size if too large
        original_shape = vil_array.shape
        if vil_array.size > DOWNSAMPLE_THRESHOLD:
            # Calculate downsample factor based on array size
            factor = max(2, int(np.sqrt(vil_array.size / DOWNSAMPLE_THRESHOLD)))
            
            # Apply downsampling
            vil_array = vil_array[::factor, ::factor]
            
            # Round the downsampled array
            vil_array = round_to_sigfigs(vil_array)
            
            logger.info(f"[WEATHER][VIL] Downsampled VIL array from {original_shape} to {vil_array.shape} (factor {factor})")
            
        # Get dimensions after potential downsampling
        azimuth_steps, range_steps = vil_array.shape
        
        # OPTIMIZATION: Get only significant VIL points
        # Only get points above the threshold to reduce processing
        threshold_mask = vil_array > VIL_THRESHOLD
        nonzero_count = np.count_nonzero(threshold_mask)
        
        # Log the actual count
        logger.info(f"[WEATHER][VIL] Found {nonzero_count} significant VIL points above threshold {VIL_THRESHOLD}")
        
        # If no significant points, return empty list
        if nonzero_count == 0:
            logger.warning("[WEATHER][VIL] No VIL points found after filtering. Returning empty list.")
            return []
        
        # Get the indices of significant points
        az_indices, r_indices = np.nonzero(threshold_mask)
        
        # HARD LIMIT: Apply a hard limit to the number of points processed
        if len(az_indices) > MAX_VIL_POINTS:
            # Random selection ensures a good distribution across the field
            keep_indices = np.random.choice(len(az_indices), MAX_VIL_POINTS, replace=False)
            az_indices = az_indices[keep_indices]
            r_indices = r_indices[keep_indices]
            
            logger.info(f"[WEATHER][VIL] Limited to {MAX_VIL_POINTS} VIL points (from {nonzero_count})")
        
        # Ensure we generate valid, distributed coordinates
        # First convert to normalized coordinates
        normalized_az = az_indices / azimuth_steps  # 0-1 range
        normalized_range = r_indices / range_steps  # 0-1 range
        
        # Round normalized coordinates
        normalized_az = round_to_sigfigs(normalized_az)
        normalized_range = round_to_sigfigs(normalized_range)
        
        # Now convert to radar-centric coordinates (range 0-360°, range in nm)
        azimuth_degrees = round_to_sigfigs(normalized_az * 360.0)
        azimuth_rads = np.radians(azimuth_degrees)
        range_nms = round_to_sigfigs(normalized_range * 40.0)  # Scale to radar range (typically 40nm)
        
        # Apply strong random perturbation to avoid points clustering
        # This helps ensure data points are well-distributed
        range_perturbation = round_to_sigfigs(np.random.uniform(0.8, 1.2, size=range_nms.shape))
        azimuth_perturbation = round_to_sigfigs(np.random.uniform(-10, 10, size=azimuth_rads.shape))
        azimuth_rads = np.radians(round_to_sigfigs(azimuth_degrees + azimuth_perturbation))
        range_nms = round_to_sigfigs(range_nms * range_perturbation)
            
        # Now convert to Cartesian coordinates with improved calculation
        x_coords = round_to_sigfigs(range_nms * np.sin(azimuth_rads))
        y_coords = round_to_sigfigs(range_nms * np.cos(azimuth_rads))
        
        # Log the coordinate distribution statistics
        logger.warning(f"[WEATHER][VIL] Coordinate statistics - x range: {np.min(x_coords):.1f} to {np.max(x_coords):.1f}, y range: {np.min(y_coords):.1f} to {np.max(y_coords):.1f}")
        
        # Add explicit position verification for debugging
        zero_positions = np.sum((np.abs(x_coords) < 0.01) & (np.abs(y_coords) < 0.01))
        if zero_positions > 0:
            logger.error(f"[WEATHER][VIL] Found {zero_positions} points near (0,0) - will be filtered out")
        
        # ENHANCED VALIDATION: Filter out invalid coordinates (NaN, inf, zeros, etc.)
        # Also filter out positions that are exactly or very near (0.0, 0.0)
        valid_indices = ~(np.isnan(x_coords) | np.isnan(y_coords) | 
                         np.isinf(x_coords) | np.isinf(y_coords) |
                         ((np.abs(x_coords) < 0.5) & (np.abs(y_coords) < 0.5)))  # Filter out positions near (0,0)
        
        # Log how many points were filtered out
        filtered_count = len(az_indices) - np.sum(valid_indices)
        if filtered_count > 0:
            logger.warning(f"[WEATHER][VIL] Filtered out {filtered_count} VIL points with invalid or zero coordinates")
        
        # Filter the coordinate and VIL value arrays
        x_coords = x_coords[valid_indices]
        y_coords = y_coords[valid_indices]
        vil_values = round_to_sigfigs(vil_array[az_indices, r_indices][valid_indices])
            
        # RETRY MECHANISM: If too many points were filtered out, try to regenerate
        retry_count = 0
        max_retries = 3
        
        while len(x_coords) < 5 and retry_count < max_retries:  # Ensure we have at least 5 points
            retry_count += 1
            logger.warning(f"[WEATHER][VIL] Insufficient valid points ({len(x_coords)}). Retry {retry_count}/{max_retries}...")
            
            # Adjust the selection criteria - use different azimuth/range
            # This creates a different set of points with different coordinates
            azimuth_offset = retry_count * 5  # Shift the azimuth by 5 degrees on each retry
            range_offset = retry_count * 2    # Shift the range by 2 units on each retry
            
            # Create new indices by offsetting the originals
            new_az_indices = (az_indices + azimuth_offset) % azimuth_steps
            new_r_indices = np.clip(r_indices + range_offset, 0, range_steps - 1)
            
            # Recalculate coordinates
            new_azimuth_rads = np.radians(new_az_indices)
            new_range_nms = round_to_sigfigs(new_r_indices * 0.539957)  # Convert km to nm
            
            # Calculate new coordinates
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
                
                # Get the corresponding VIL values
                new_vil_values = vil_array[new_az_indices[new_valid_indices], new_r_indices[new_valid_indices]]
                # Round the new VIL values
                new_vil_values = round_to_sigfigs(new_vil_values)
                vil_values = np.append(vil_values, new_vil_values)
                
                logger.warning(f"[WEATHER][VIL] Added {np.sum(new_valid_indices)} new points on retry {retry_count}")
                
                # If we have enough points, break out of the retry loop
                if len(x_coords) >= 5:
                    break
        
        # If we still don't have any valid points after all retries, log and return empty
        if len(x_coords) == 0:
            logger.error("[WEATHER][VIL] Failed to generate any valid VIL points after multiple retries.")
            return []
            
        # If we have fewer than expected but not zero, continue with what we have
        if len(x_coords) < 5:
            logger.warning(f"[WEATHER][VIL] Proceeding with limited VIL points ({len(x_coords)}) after {retry_count} retries")
            
        # Create VIL objects using filtered array lengths
        # All arrays should have the same length after filtering, but we'll use the length of vil_values to be safe
        logger.warning(f"[WEATHER][VIL] Creating {len(vil_values)} VIL objects from filtered data")
        logger.warning(f"[WEATHER][VIL] Arrays lengths after filtering - vil_values: {len(vil_values)}, x_coords: {len(x_coords)}, y_coords: {len(y_coords)}")
        
        for i in range(len(vil_values)):  # Use filtered array length
            value = vil_values[i]
            
            # Extra safety check to ensure we don't go out of bounds
            if i >= len(x_coords) or i >= len(y_coords):
                logger.error(f"[WEATHER][VIL] Index {i} out of bounds for coordinate arrays (x_coords: {len(x_coords)}, y_coords: {len(y_coords)})")
                continue
                
            # STRONGER VALIDATION: Extra validation check before creating the object
            if (np.isnan(x_coords[i]) or np.isnan(y_coords[i]) or 
                np.isinf(x_coords[i]) or np.isinf(y_coords[i]) or
                (x_coords[i] == 0.0 and y_coords[i] == 0.0)):
                logger.warning(f"[WEATHER][VIL] Skipping VIL point with invalid coordinates: ({x_coords[i]}, {y_coords[i]})")
                continue  # Skip any points that somehow passed the earlier filter
                
            # Create VIL data object with realistic parameters
            intensity = min(1.0, value / 65.0)  # Normalize to 0-1
            layer_count = min(15, int(intensity * 15) + 1)  # More layers for higher intensity
            
            # Round intensity calculation
            intensity = round_to_sigfigs(intensity)
            
            # Create the VIL data object with explicit float casting for coordinates
            vil_obj = WeatherRadarVILData(
                position=(round_to_sigfigs(float(x_coords[i])), round_to_sigfigs(float(y_coords[i]))),
                value=round_to_sigfigs(value),
                layer_count=layer_count,
                intensity=intensity,
                show_values=(intensity > 0.3)  # Only show values for significant VIL
            )
            
            # Set request ID and timestamp
            vil_obj.request_id = request_id
            vil_obj.timestamp = current_time
            
            # Add metadata to track the message flow
            vil_obj.additional_info = {'original_request_id': request_id}
            
            # Verify that all numeric values are properly rounded
            # This ensures no full-precision values slip through
            if hasattr(vil_obj, 'value'):
                vil_obj.value = round_to_sigfigs(vil_obj.value)
            if hasattr(vil_obj, 'intensity'):
                vil_obj.intensity = round_to_sigfigs(vil_obj.intensity)
            if hasattr(vil_obj, 'position') and isinstance(vil_obj.position, tuple) and len(vil_obj.position) == 2:
                vil_obj.position = (round_to_sigfigs(vil_obj.position[0]), round_to_sigfigs(vil_obj.position[1]))
            
            vil_objects.append(vil_obj)
        
        # MIL-STD-1553B COMPLIANCE: Limit to 20 data points to respect bandwidth constraints
        if len(vil_objects) > 20:
            # Get wind vector for high altitude (where VIL data is typically gathered)
            wind_vector = weather_state.get_wind('altitude')
            
            # Calculate time since last update
            time_delta = round_to_sigfigs(current_time - weather_state.last_sampling_time)
            
            # Use trajectory-aware sampling to select points                     SopaDeMurloc
            selected_indices = weather_state.sample_points_with_trajectory(
                'vil',            # Data type
                vil_objects,      # All candidate points
                20,               # Maximum points to display
                wind_vector,      # Current wind vector
                time_delta,       # Time since last sampling
                current_time      # Current time
            )
            
            # Update tracking for the selected points
            weather_state.update_tracked_points(
                'vil',            # Data type
                [vil_objects[i] for i in selected_indices],
                wind_vector,
                current_time
            )
            
            # Use the trajectory-aware selection
            selected_objects = [vil_objects[i] for i in selected_indices]
            
            # Performance tracking
            elapsed_time = round_to_sigfigs(time.time() - start_time)
            logger.info(f"[WEATHER][VIL] VIL data generation completed in {elapsed_time:.3f} seconds")
            
            # Return the selected objects
            return selected_objects
        
        # Performance tracking
        elapsed_time = round_to_sigfigs(time.time() - start_time)
        logger.info(f"[WEATHER][VIL] VIL data generation completed in {elapsed_time:.3f} seconds with {len(vil_objects)} objects")
        
        # Return all objects
        return vil_objects
    
    def create_vil_response(self, vil_objects: List[Any], request_id: str, current_mode: str = None) -> Any:
        """
        Create a VIL response message with the generated VIL data objects.
        
        Args:
            vil_objects: List of WeatherRadarVILData objects
            request_id: Request ID to include in the response
            current_mode: Current radar mode (optional)
            
        Returns:
            weather_radarVILResponse object
        """
# Import radar-local message classes to respect system boundaries
        from FMOFP.Systems.radarManagement.radar_messaging.message_definitions import WeatherRadarVILResponse

# Import message type constants
        from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
            WEATHER_RADAR_VIL_RESPONSE,
            COMMAND_TYPE_VIL_DATA
        )
        
# Create response message with the original request ID
        # Remove command_name and command_type as they're already set in WeatherRadarVILResponse constructor
        response = WeatherRadarVILResponse(
            message_header="vil_data",
            sending_system="radar",
            destination="displays",
            request_id=request_id,
            response_uuid=request_id,  # Use the same UUID for request and response
            vil_data=vil_objects
        )
        
        # Ensure all VIL data has 3 significant digits
        for obj in vil_objects:
            if hasattr(obj, 'value'):
                obj.value = round_to_sigfigs(obj.value)
            if hasattr(obj, 'intensity'):
                obj.intensity = round_to_sigfigs(obj.intensity)
            if hasattr(obj, 'position') and isinstance(obj.position, tuple) and len(obj.position) == 2:
                obj.position = (round_to_sigfigs(obj.position[0]), round_to_sigfigs(obj.position[1]))
        
        # Add command name, as we need to ensure it's consistent
        response.command_name = "DISPLAY_VIL_DATA"
        
        # Add metadata to track the message flow
        if hasattr(response, 'additional_info'):
            response.additional_info['original_request_id'] = request_id
            response.additional_info['vil_message'] = True
            response.additional_info['vil_data_available'] = True
            response.additional_info['command_type'] = "vil_data"  # Add command_type to metadata
            response.additional_info['message_type'] = WEATHER_RADAR_VIL_RESPONSE
            response.additional_info['command_name'] = "DISPLAY_VIL_DATA"  # Ensure command_name is set in metadata
            if current_mode:
                response.additional_info['mode'] = current_mode
        else:
            additional_info = {
                'original_request_id': request_id,
                'vil_message': True,
                'vil_data_available': True,
                'command_type': "vil_data",  # Add command_type to metadata
                'message_type': WEATHER_RADAR_VIL_RESPONSE,
                'command_name': "DISPLAY_VIL_DATA"  # Ensure command_name is set in metadata
            }
            if current_mode:
                additional_info['mode'] = current_mode
            response.additional_info = additional_info
        
        return response

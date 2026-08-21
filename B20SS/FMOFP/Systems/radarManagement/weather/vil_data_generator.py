# """
# VIL Data Generator Module

# Calculates and generates Vertically Integrated Liquid (VIL) data from reflectivity data.
# """

# import numpy as np
# import uuid
# import time
# from typing import Dict, Tuple, List, Any, Optional

# class VILDataGenerator:
#     """Generates VIL data from reflectivity data."""
    
#     def __init__(self, config: Dict[str, Any]):
#         """
#         Initialize the VIL data generator with configuration.
        
#         Args:
#             config: Dictionary containing radar configuration parameters
#         """
#         self.config = config
    
#     def calculate_vil(self, reflectivity: np.ndarray, elevation_angles: Tuple[float, ...]) -> np.ndarray:
#         """
#         Calculate Vertically Integrated Liquid (VIL) from reflectivity volume scan.
        
#         Uses the standard meteorological formula: VIL = Σ(3.44 × 10^-6 × Z^4/7 × Δh)
#         where Z is the linear reflectivity factor and Δh is the layer thickness in meters.
        
#         Args:
#             reflectivity: 3D array of reflectivity values (azimuth, elevation, range)
#             elevation_angles: Tuple of elevation angles in degrees
            
#         Returns:
#             2D numpy array of VIL values (azimuth, range)
#         """
#         if reflectivity is None:
#             return None
        
#         # Get dimensions
#         azimuth_steps, elevation_steps, range_steps = reflectivity.shape
        
#         # Initialize VIL array (2D - azimuth x range)
#         vil = np.zeros((azimuth_steps, range_steps))
        
#         # Ensure we have enough elevation angles
#         if len(elevation_angles) < elevation_steps:
#             # Fill in missing elevations with reasonable values
#             elevation_angles = list(elevation_angles)
#             for i in range(len(elevation_angles), elevation_steps):
#                 elevation_angles.append(elevation_angles[-1] + 1.5)
        
#         # Calculate layer thickness (in meters)
#         layer_thickness = []
#         for i in range(elevation_steps - 1):
#             # Calculate thickness based on elevation angle difference
#             # This is a simplification - in reality it depends on beam width and range
#             thickness = 1000 * (np.sin(np.radians(elevation_angles[i+1])) - 
#                                np.sin(np.radians(elevation_angles[i])))
#             layer_thickness.append(max(100, thickness))  # Minimum 100m thickness
        
#         # Add a final layer
#         layer_thickness.append(layer_thickness[-1] if layer_thickness else 1000)
        
#         # Calculate VIL for each column
#         for az in range(azimuth_steps):
#             for r in range(range_steps):
#                 for el in range(elevation_steps):
#                     # Get reflectivity in dBZ
#                     dbz = reflectivity[az, el, r]
                    
#                     # Convert dBZ to Z (mm^6/m^3)
#                     if dbz > 0:  # Only process positive reflectivity
#                         z = 10 ** (dbz / 10)
                        
#                         # Apply VIL formula: 3.44 × 10^-3 × Z^4/7 × Δh
#                         # Code-------------: (3.44 * 10**-3) * (z ** (4/7)) * layer_thickness[el]
#                         # The 4/7 power approximates the Z-M relationship
#                         # Scale up by 1,000 to make values visible on display
#                         vil_contribution = (3.44 * 10**-3) * (z ** (4/7)) * layer_thickness[el]
                        
#                         # Add to total VIL
#                         vil[az, r] += vil_contribution # Convert to kg/m²
        
#         return vil
    
#     def generate_vil_data_objects(self, vil_array: np.ndarray, request_id: Optional[str] = None) -> List[Any]:
#         """
#         Generate VIL data objects from a 2D VIL array with trajectory-based sampling for continuity.
        
#         Args:
#             vil_array: 2D array of VIL values (azimuth, range)
#             request_id: Optional request ID to include in the data objects
            
#         Returns:
#             List of WeatherRadarVILData objects
#         """
#         # Import radar-local message classes to respect system boundaries
#         from FMOFP.Systems.radarManagement.radar_messaging.message_definitions import WeatherRadarVILData
#         from FMOFP.Systems.radarManagement.weather.weather_state_manager import WeatherStateManager
        
#         # Get the singleton weather state manager
#         weather_state = WeatherStateManager.get_instance()
        
#         # Create VIL data objects from the calculated values
#         vil_objects = []
        
#         # Get dimensions
#         azimuth_steps, range_steps = vil_array.shape
        
#         if not request_id:
            
#             raise ValueError("[VIL_DATA_GEN] Request ID is required for VIL data generation.")
            
#         # Log the request ID being used
#         print(f"[VIL_SEN] Generating VIL data objects with request ID: {request_id}")
        
#         # Get current time
#         current_time = time.time()
        
#         # Validation check for vil_array
#         if vil_array is None or not np.any(vil_array):
#             raise ValueError("[VIL_SEN] VIL array is empty or None.")
        
#         # Generate all potential VIL objects
#         for az in range(azimuth_steps):
#             for r in range(range_steps):
#                 if vil_array[az, r] > 0:  # Only include non-zero values
#                     # Convert array indices to position in nm
#                     # Assuming 1 degree azimuth resolution and 1km range resolution
#                     azimuth_rad = np.radians(az)
#                     range_nm = r * 0.539957  # Convert km to nm
                    
#                     # Convert to x,y coordinates
#                     x = range_nm * np.sin(azimuth_rad)
#                     y = range_nm * np.cos(azimuth_rad)
                    
#                     # Create VIL data object with realistic parameters
#                     intensity = min(1.0, vil_array[az, r] / 65.0)  # Normalize to 0-1
#                     layer_count = min(15, int(intensity * 15) + 1)  # More layers for higher intensity
                    
#                     # Create the VIL data object with the original request ID
#                     vil_obj = WeatherRadarVILData(
#                         position=(x, y),
#                         value=vil_array[az, r],
#                         layer_count=layer_count,
#                         intensity=intensity,
#                         show_values=(intensity > 0.3)  # Only show values for significant VIL
#                     )
                    
#                     # Set request ID and timestamp
#                     vil_obj.request_id = request_id
#                     vil_obj.timestamp = current_time
                    
#                     # Add metadata to track the message flow
#                     if hasattr(vil_obj, 'additional_info'):
#                         vil_obj.additional_info['original_request_id'] = request_id
#                     else:
#                         vil_obj.additional_info = {'original_request_id': request_id}
                    
#                     vil_objects.append(vil_obj)
        
#         # Ensure we have at least one data point to maintain data flow
#         if not vil_objects:
#             print(f"Warning: No VIL objects generated. Creating backup data point.")
#             vil_obj = WeatherRadarVILData(
#                 position=(50.0, 50.0),
#                 value=30.0,  # Moderate VIL
#                 layer_count=5,
#                 intensity=0.5,
#                 show_values=True
#             )
#             vil_obj.request_id = request_id
#             vil_obj.timestamp = current_time
#             vil_obj.additional_info = {'original_request_id': request_id}
#             vil_objects = [vil_obj]
        
#         # Limit to a reasonable number of data points using trajectory-aware sampling
#         if len(vil_objects) > 20:
#             # Get wind vector for high altitude (where VIL data is typically gathered)
#             wind_vector = weather_state.get_wind('altitude')
            
#             # Calculate time since last update
#             time_delta = current_time - weather_state.last_sampling_time
            
#             # Use trajectory-aware sampling to select points
#             selected_indices = weather_state.sample_points_with_trajectory(
#                 'vil',            # Data type
#                 vil_objects,      # All candidate points
#                 20,               # Maximum points to display
#                 wind_vector,      # Current wind vector
#                 time_delta,       # Time since last sampling
#                 current_time      # Current time
#             )
            
#             # Update tracking for the selected points
#             weather_state.update_tracked_points(
#                 'vil',            # Data type
#                 [vil_objects[i] for i in selected_indices],
#                 wind_vector,
#                 current_time
#             )
            
#             # Use the trajectory-aware selection
#             selected_objects = [vil_objects[i] for i in selected_indices]
            
#             # Return the selected objects explicitly
#             return selected_objects
        
#         # Return all objects
#         return vil_objects
    
#     def create_vil_response(self, vil_objects: List[Any], request_id: str, current_mode: str = None) -> Any:
#         """
#         Create a VIL response message with the generated VIL data objects.
        
#         Args:
#             vil_objects: List of WeatherRadarVILData objects
#             request_id: Request ID to include in the response
#             current_mode: Current radar mode (optional)
            
#         Returns:
#             WeatherRadarVILResponse object
#         """
#         # Import radar-local message classes to respect system boundaries
#         from FMOFP.Systems.radarManagement.radar_messaging.message_definitions import WeatherRadarVILResponse
        
#         # Import message types and constants
#         from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
#             WEATHER_RADAR_VIL_RESPONSE,
#             COMMAND_TYPE_VIL_DATA
#         )
        
#         # Create response message with the original request ID
#         response = WeatherRadarVILResponse(
#             message_header="vil_data",
#             sending_system="weather_radar",
#             destination="radar_handler",
#             request_id=request_id,
#             response_uuid=request_id,  # Use the same UUID for request and response
#             vil_data=vil_objects,
#             command_name="WEATHER_RADAR_VIL_DATA",
#             command_type=COMMAND_TYPE_VIL_DATA
#         )
        
#         # Add metadata to track the message flow
#         if hasattr(response, 'additional_info'):
#             response.additional_info['original_request_id'] = request_id
#             response.additional_info['command_name'] = 'WEATHER_RADAR_VIL_DATA'
#             response.additional_info['command_type'] = 'data'
#             if current_mode:
#                 response.additional_info['mode'] = current_mode
#         else:
#             additional_info = {
#                 'original_request_id': request_id,
#                 'command_name': 'WEATHER_RADAR_VIL_DATA',
#                 'command_type': 'data'
#             }
#             if current_mode:
#                 additional_info['mode'] = current_mode
#             response.additional_info = additional_info
        
#         return response

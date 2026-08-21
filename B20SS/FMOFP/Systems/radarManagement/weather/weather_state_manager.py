"""
Weather State Manager Module

Manages persistent state for weather simulation, including storm cells, stratiform areas,
and tracked data points for continuity across radar sweeps.
Enables realistic weather movement over time with trajectory tracking.
"""

import threading
import time
import random
import math
import uuid
from typing import Dict, List, Tuple, Any, Optional, Set
import numpy as np

class StormCell:
    """Represents a storm cell with position, size, intensity, and lifecycle."""
    
    def __init__(self, position: Tuple[float, float], size: float, intensity: float, vertical_development: Dict[int, float]):
        """
        Initialize a storm cell.
        
        Args:
            position: Tuple of (azimuth, range) - azimuth in degrees, range in km
            size: Radius in km
            intensity: Maximum reflectivity in dBZ
            vertical_development: Dictionary mapping elevation index to intensity multiplier
        """
        self.position = position  # (az, range) - azimuth in degrees, range in km
        self.size = size  # radius in km
        self.intensity = intensity  # max reflectivity in dBZ
        self.vertical_development = vertical_development  # dictionary mapping elevation to multiplier
        self.age = 0  # time since creation in seconds
        self.lifetime = random.uniform(1800, 7200)  # 30-120 minutes lifetime
        self.growth_phase = random.uniform(0.15, 0.3)  # portion of lifetime spent growing
        self.mature_phase = random.uniform(0.4, 0.6)  # portion spent in mature state
        # Remaining portion is decay phase
    
    def update(self, delta_time: float, wind: Dict[str, float]) -> bool:
        """
        Update storm cell based on time delta and wind.
        
        Args:
            delta_time: Time delta in seconds
            wind: Dictionary with 'direction' (degrees) and 'speed' (knots)
            
        Returns:
            bool: True if cell is still active, False if it has decayed
        """
        # Age the cell
        self.age += delta_time
        
        # Calculate lifecycle phase factor (0-1)
        life_fraction = self.age / self.lifetime
        
        # Update intensity based on lifecycle
        if life_fraction < self.growth_phase:
            # Growth phase - increasing intensity
            phase_progress = life_fraction / self.growth_phase
            self.intensity = 35 + 30 * phase_progress  # 35-65 dBZ
        elif life_fraction < (self.growth_phase + self.mature_phase):
            # Mature phase - stable intensity with fluctuations
            self.intensity = 65 + random.uniform(-5, 5)  # 60-70 dBZ with fluctuations
        else:
            # Decay phase - decreasing intensity
            decay_progress = (life_fraction - (self.growth_phase + self.mature_phase)) / (1 - (self.growth_phase + self.mature_phase))
            self.intensity = max(0, 65 - 65 * decay_progress)  # 65-0 dBZ
        
        # Update position based on wind (convert knots to km/h, then to km/second)
        wind_speed_km_s = wind['speed'] * 1.852 / 3600  # convert knots to km/s
        wind_direction_rad = math.radians(wind['direction'])
        
        # Calculate position change in polar coordinates
        delta_range = wind_speed_km_s * delta_time * math.cos(wind_direction_rad)
        # Avoid division by zero for azimuthal movement calculation
        delta_az = math.degrees(wind_speed_km_s * delta_time * math.sin(wind_direction_rad) / (self.position[1] + 0.001))
        
        # Update position
        self.position = (
            (self.position[0] + delta_az) % 360,  # Wrap azimuth to 0-360
            self.position[1] + delta_range  # Update range
        )
        
        # Return True if cell is still active, False if it has decayed
        return self.age < self.lifetime and self.intensity > 5


class StratiformArea:
    """Represents a stratiform precipitation area with position, size, and intensity."""
    
    def __init__(self, position: Tuple[float, float], az_width: float, range_depth: float, intensity: float):
        """
        Initialize a stratiform precipitation area.
        
        Args:
            position: Tuple of (azimuth, range) - azimuth in degrees, range in km
            az_width: Width in azimuth degrees
            range_depth: Depth in range (km)
            intensity: Reflectivity in dBZ
        """
        self.position = position  # (az, range) - azimuth in degrees, range in km
        self.az_width = az_width  # width in azimuth degrees
        self.range_depth = range_depth  # depth in range km
        self.intensity = intensity  # reflectivity in dBZ
        self.age = 0  # time since creation in seconds
        self.lifetime = random.uniform(3600, 10800)  # 1-3 hours lifetime
        self.intensity_variation = 0.0  # current intensity variation
    
    def update(self, delta_time: float, wind: Dict[str, float]) -> bool:
        """
        Update stratiform area based on time delta and wind.
        
        Args:
            delta_time: Time delta in seconds
            wind: Dictionary with 'direction' (degrees) and 'speed' (knots)
            
        Returns:
            bool: True if area is still active, False if it has decayed
        """
        # Age the stratiform area
        self.age += delta_time
        
        # Calculate lifecycle phase
        life_fraction = self.age / self.lifetime
        
        # Add some intensity variation over time
        self.intensity_variation = 3.0 * math.sin(self.age / 600) # Vary by +/- 3 dBZ every 10 minutes
        
        # Update intensity based on lifecycle (stratiform areas decay slower)
        if life_fraction > 0.8:
            # Only decay in the last 20% of lifetime
            decay_progress = (life_fraction - 0.8) / 0.2
            base_intensity = self.intensity * (1 - decay_progress * 0.8)  # Decay to 20% of original
        else:
            base_intensity = self.intensity
            
        # Apply variation
        self.intensity = base_intensity + self.intensity_variation
        
        # Update position based on wind (convert knots to km/h, then to km/second)
        wind_speed_km_s = wind['speed'] * 1.852 / 3600  # convert knots to km/s
        wind_direction_rad = math.radians(wind['direction'])
        
        # Calculate position change in polar coordinates
        delta_range = wind_speed_km_s * delta_time * math.cos(wind_direction_rad)
        # Avoid division by zero for azimuthal movement calculation
        delta_az = math.degrees(wind_speed_km_s * delta_time * math.sin(wind_direction_rad) / (self.position[1] + 0.001))
        
        # Update position
        self.position = (
            (self.position[0] + delta_az) % 360,  # Wrap azimuth to 0-360
            self.position[1] + delta_range  # Update range
        )
        
        # Return True if area is still active, False if it has decayed
        return self.age < self.lifetime and self.intensity > 5


class TrackedPoint:
    """Class to track points across multiple frames for coherent movement."""
    
    def __init__(self, position: Tuple[float, float], intensity: float, 
                attributes: Dict[str, Any], point_id: Optional[str] = None):
        """
        Initialize a tracked point.
        
        Args:
            position: (x, y) coordinates
            intensity: Current intensity value
            attributes: Other point-specific attributes (type, additional data)
            point_id: Unique identifier (or auto-generated if None)
        """
        self.position = position  # (x, y) coordinates
        self.intensity = intensity  # Current intensity value
        self.attributes = attributes  # Other point-specific attributes
        self.point_id = point_id or str(uuid.uuid4())  # Unique identifier
        self.trajectory = [position]  # History of positions
        self.last_update_time = time.time()
        self.predicted_next_position = None  # For trajectory prediction
        self.age = 0.0  # Age of tracked point in seconds


class WeatherStateManager:
    """Singleton class that manages weather system state between simulation cycles."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance of WeatherStateManager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
        
    def __init__(self):
        """Initialize the weather state manager."""
        # Initialize only if no instance exists
        if WeatherStateManager._instance is not None:
            raise Exception("Use get_instance() to get the singleton instance")
            
        # Weather state
        self.storm_cells: List[StormCell] = []  # List of StormCell objects
        self.stratiform_areas: List[StratiformArea] = []  # List of StratiformArea objects
        self.last_update_time = time.time()
        self.initialized = False
        
        # Wind vector (direction and speed) - can vary with altitude
        self.wind = {
            'surface': {'direction': 270, 'speed': 15},  # 270° at 15 knots (west to east)
            'altitude': {'direction': 290, 'speed': 25}  # 290° at 25 knots (WNW to ESE)
        }
        
        # Point tracking for continuity between frames
        self.tracked_vil_points: Dict[str, TrackedPoint] = {}  # Dict mapping point_id to TrackedPoint
        self.tracked_precip_points: Dict[str, TrackedPoint] = {}  # Same for precipitation data
        self.last_sampling_time = time.time()
        self.tracking_history_length = 5  # Number of frames to track history
        self.max_tracked_point_age = 120.0  # Maximum age in seconds to keep tracked points
        
        # Lock for thread safety
        self._lock = threading.Lock()
    
    def get_wind(self, altitude: str = 'surface') -> Dict[str, float]:
        """
        Get wind vector at specified altitude.
        
        Args:
            altitude: 'surface' or 'altitude'
            
        Returns:
            Dict with 'direction' and 'speed'
        """
        return self.wind.get(altitude, self.wind['surface'])
    
    def set_wind(self, altitude: str, direction: float, speed: float) -> None:
        """
        Set wind vector at specified altitude.
        
        Args:
            altitude: 'surface' or 'altitude'
            direction: Wind direction in degrees (0-360, 0=North, 90=East)
            speed: Wind speed in knots
        """
        with self._lock:
            if altitude in self.wind:
                self.wind[altitude] = {'direction': direction, 'speed': speed}
    
    def calculate_expected_movement(self, wind: Dict[str, float], time_delta: float) -> Tuple[float, float]:
        """
        Calculate expected movement vector based on wind and time delta.
        
        Args:
            wind: Dictionary with 'direction' (degrees) and 'speed' (knots)
            time_delta: Time in seconds
            
        Returns:
            Tuple (delta_x, delta_y) in nm
        """
        # Convert knots to nm/second
        wind_speed_nm_s = wind['speed'] / 3600.0  # nm per second
        wind_direction_rad = math.radians(wind['direction'])
        
        # Calculate deltas in x and y
        delta_x = wind_speed_nm_s * time_delta * math.sin(wind_direction_rad)
        delta_y = wind_speed_nm_s * time_delta * math.cos(wind_direction_rad)
        
        return (delta_x, delta_y)
    
    def predict_next_position(self, point: TrackedPoint, 
                             expected_movement: Tuple[float, float]) -> Tuple[float, float]:
        """
        Predict next position for a tracked point.
        
        Args:
            point: Tracked point
            expected_movement: Movement vector from calculate_expected_movement
            
        Returns:
            Tuple (x, y) of predicted position
        """
        delta_x, delta_y = expected_movement
        current_x, current_y = point.position
        
        predicted_x = current_x + delta_x
        predicted_y = current_y + delta_y
        
        return (predicted_x, predicted_y)
    
    def calculate_distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """
        Calculate Euclidean distance between two positions.
        
        Args:
            pos1: First position (x, y)
            pos2: Second position (x, y)
            
        Returns:
            Distance in same units as positions
        """
        x1, y1 = pos1
        x2, y2 = pos2
        
        return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    
    def cluster_points(self, points: List[Any], radius: float = 5.0) -> List[List[int]]:
        """
        Group points into spatial clusters using a simplified DBSCAN algorithm.
        
        Args:
            points: List of point objects with position attributes
            radius: Maximum distance between points in same cluster
            
        Returns:
            List of clusters (each a list of point indices)
        """
        # Extract positions for distance calculations
        positions = [point.position for point in points]
        
        # Initialize clusters and visited flags
        clusters = []
        visited = set()
        
        # For each unvisited point
        for i in range(len(points)):
            if i in visited:
                continue
                
            # Start a new cluster
            cluster = [i]
            visited.add(i)
            
            # Process all points in this cluster
            j = 0
            while j < len(cluster):
                current_idx = cluster[j]
                current_pos = positions[current_idx]
                
                # Find neighbors within radius
                for k in range(len(points)):
                    if k not in visited:
                        if self.calculate_distance(current_pos, positions[k]) <= radius:
                            cluster.append(k)
                            visited.add(k)
                
                j += 1
            
            # Add cluster to result
            clusters.append(cluster)
        
        return clusters
    
    def calculate_cluster_intensity(self, points: List[Any], cluster: List[int]) -> float:
        """
        Calculate average intensity of a cluster.
        
        Args:
            points: List of all points
            cluster: List of indices into points representing a cluster
            
        Returns:
            Average intensity of the cluster
        """
        if not cluster:
            return 0.0
            
        intensity_sum = sum(points[i].intensity for i in cluster)
        return intensity_sum / len(cluster)
    
    def match_points_to_previous(self, current_points: List[Any], 
                                previous_tracked: Dict[str, TrackedPoint],
                                wind_vector: Dict[str, float], 
                                time_delta: float,
                                max_distance: float = 10.0) -> Dict[int, str]:
        """
        Match current points to previously tracked points.
        
        Args:
            current_points: List of current point objects
            previous_tracked: Dict of previously tracked points
            wind_vector: Wind vector dict with 'direction' and 'speed'
            time_delta: Time delta since last update
            max_distance: Maximum distance for a point to be considered a match
            
        Returns:
            Dict mapping current point indices to matched tracked point IDs
        """
        if not previous_tracked or not current_points:
            return {}
            
        # Calculate expected movement
        expected_movement = self.calculate_expected_movement(wind_vector, time_delta)
        
        # For each previous point, predict its new position
        predicted_positions = {}
        for point_id, tracked_point in previous_tracked.items():
            predicted_pos = self.predict_next_position(tracked_point, expected_movement)
            predicted_positions[point_id] = predicted_pos
        
        # Match current points to previous based on proximity to predicted positions
        matches = {}
        matched_tracked_ids = set()
        
        # First pass: Find best matches for each current point
        for i, point in enumerate(current_points):
            best_match = None
            best_distance = float('inf')
            
            for point_id, predicted_pos in predicted_positions.items():
                if point_id in matched_tracked_ids:
                    continue
                    
                distance = self.calculate_distance(point.position, predicted_pos)
                
                if distance < best_distance:
                    best_distance = distance
                    best_match = point_id
            
            # If we found a good match within threshold
            if best_match is not None and best_distance < max_distance:
                matches[i] = best_match
                matched_tracked_ids.add(best_match)
        
        return matches
    
    def update_tracked_points(self, data_type: str, current_points: List[Any], 
                             wind_vector: Dict[str, float], current_time: float) -> None:
        """
        Update tracked points with new data.
        
        Args:
            data_type: 'vil' or 'precip'
            current_points: List of current data points
            wind_vector: Wind vector for this update
            current_time: Current timestamp
        """
        # Determine which tracking dict to use
        tracked_dict = self.tracked_vil_points if data_type == 'vil' else self.tracked_precip_points
        
        # Create new tracking dict
        new_tracked = {}
        
        # Calculate time delta since last update
        time_delta = current_time - self.last_sampling_time
        
        # Get point matches
        matches = self.match_points_to_previous(current_points, tracked_dict, wind_vector, time_delta)
        
        # Update matched points and create new ones
        for i, point in enumerate(current_points):
            if i in matches:
                # Update existing tracked point
                point_id = matches[i]
                tracked = tracked_dict[point_id]
                
                # Update position and other attributes
                tracked.position = point.position
                tracked.intensity = point.intensity
                tracked.trajectory.append(point.position)
                tracked.last_update_time = current_time
                tracked.age += time_delta
                
                # Limit trajectory history
                if len(tracked.trajectory) > self.tracking_history_length:
                    tracked.trajectory = tracked.trajectory[-self.tracking_history_length:]
                
                # Calculate predicted next position
                expected_movement = self.calculate_expected_movement(wind_vector, 30.0)  # Predict 30s ahead
                tracked.predicted_next_position = self.predict_next_position(tracked, expected_movement)
                
                # Store in new dict and link point to tracked ID
                new_tracked[tracked.point_id] = tracked
                setattr(point, 'tracked_id', tracked.point_id)
            else:
                # Create new tracked point
                point_id = str(uuid.uuid4())
                
                # Extract attributes from point
                attributes = {
                    'type': data_type,
                    'point_type': point.__class__.__name__
                }
                
                # Add any important fields from the point
                for attr in ['request_id', 'type', 'layer_count', 'value']:
                    if hasattr(point, attr):
                        attributes[attr] = getattr(point, attr)
                
                # Create tracked point
                tracked = TrackedPoint(
                    point.position,
                    point.intensity,
                    attributes,
                    point_id=point_id
                )
                tracked.last_update_time = current_time
                
                # Add predicted next position
                expected_movement = self.calculate_expected_movement(wind_vector, 30.0)  # Predict 30s ahead
                tracked.predicted_next_position = self.predict_next_position(tracked, expected_movement)
                
                # Store in new dict and link point to tracked ID
                new_tracked[point_id] = tracked
                setattr(point, 'tracked_id', point_id)
        
        # Update the tracking dict
        if data_type == 'vil':
            self.tracked_vil_points = new_tracked
        else:
            self.tracked_precip_points = new_tracked
        
        # Update last sampling time
        self.last_sampling_time = current_time
    
    def sample_points_with_trajectory(self, data_type: str, all_points: List[Any], 
                                    max_points: int, 
                                    wind_vector: Dict[str, float],
                                    time_delta: float = 30.0,
                                    current_time: float = None) -> List[int]:
        """
        Sample points ensuring trajectory continuity.
        
        Args:
            data_type: 'vil' or 'precip'
            all_points: All candidate points
            max_points: Maximum number of points to select
            wind_vector: Current wind vector
            time_delta: Time since last sampling
            current_time: Current timestamp (or use time.time() if None)
            
        Returns:
            List of indices of selected points
        """
        if not all_points:
            return []
            
        if current_time is None:
            current_time = time.time()
            
        # Get tracked points
        tracked_dict = self.tracked_vil_points if data_type == 'vil' else self.tracked_precip_points
        
        # Match current points to previous selections
        matches = self.match_points_to_previous(all_points, tracked_dict, wind_vector, time_delta)
        
        # Get indices of matched points (these are our priority selections)
        continuing_indices = list(matches.keys())
        
        # If we need more points, select from clusters
        remaining_slots = max_points - len(continuing_indices)
        
        if remaining_slots > 0 and len(all_points) > len(continuing_indices):
            # Get unmatched points
            unmatched_indices = [i for i in range(len(all_points)) if i not in matches]
            
            if unmatched_indices:
                # Create subset of unmatched points for clustering
                unmatched_points = [all_points[i] for i in unmatched_indices]
                
                # Cluster remaining points
                clusters = self.cluster_points(unmatched_points)
                
                # Sort clusters by average intensity (prioritize more intense clusters)
                sorted_clusters = []
                for cluster in clusters:
                    avg_intensity = self.calculate_cluster_intensity(unmatched_points, cluster)
                    sorted_clusters.append((cluster, avg_intensity))
                
                # Sort by intensity descending
                sorted_clusters.sort(key=lambda x: -x[1])
                
                # Sample points from each cluster based on intensity
                additional_indices = []
                
                # Calculate points per cluster proportionally to intensity
                total_intensity = sum(c[1] for c in sorted_clusters)
                if total_intensity > 0:
                    for cluster, intensity in sorted_clusters:
                        # Points to take from this cluster proportional to intensity
                        cluster_points = min(
                            max(1, round(intensity / total_intensity * remaining_slots)),
                            len(cluster),
                            remaining_slots - len(additional_indices)
                        )
                        
                        if cluster_points <= 0 or len(additional_indices) >= remaining_slots:
                            continue
                            
                        # Sort points in cluster by intensity
                        cluster_with_intensity = [(i, unmatched_points[i].intensity) for i in cluster]
                        cluster_with_intensity.sort(key=lambda x: -x[1])  # Sort by intensity descending
                        
                        # Take the most intense points from this cluster
                        for j in range(cluster_points):
                            if j < len(cluster_with_intensity):
                                # Convert back to original index
                                orig_idx = unmatched_indices[cluster_with_intensity[j][0]]
                                additional_indices.append(orig_idx)
                                
                        # Stop if we've filled all slots
                        if len(additional_indices) >= remaining_slots:
                            break
                else:
                    # No intensity, just take random points
                    sample_count = min(remaining_slots, len(unmatched_indices))
                    additional_indices = random.sample(unmatched_indices, sample_count)
                
                # Add the additional indices to our continuing indices
                continuing_indices.extend(additional_indices)
        
        # Ensure we're returning valid indices and not exceeding max_points
        result = sorted(continuing_indices[:max_points])
        return result

"""
Particle System for Weather Radar Visualization

Provides a realistic, particle-based visualization system for weather radar data.
Implements dynamic, fluid-like behavior for precipitation, VIL, and storm cell data.
"""
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QImage, QPen, QBrush, QPainterPath, QRadialGradient
from typing import Dict, List, Any, Optional, Tuple, Set
import math
import time
import uuid
import numpy as np
import random

from Utils.logger.sys_logger import get_logger

# Import animation controller for wind simulation
from .animation_controller import get_animation_controller

logger = get_logger()

class Particle:
    """
    Represents a single particle in the weather visualization system.
    
    Each particle has position, size, color, opacity, and lifetime properties.
    Particles move based on wind vectors and can belong to clusters for more
    realistic cloud-like formations.
    """
    
    def __init__(self, 
                 position: QPointF, 
                 size: float, 
                 color: QColor, 
                 lifetime: float,
                 original_position: QPointF,
                 cluster_id: int = 0,
                 cluster_strength: float = 1.0):
        """
        Initialize a particle.
        
        Args:
            position: Initial position
            size: Particle size in pixels
            color: Particle color
            lifetime: Lifetime in seconds
            original_position: Reference to the center point of the weather phenomenon
            cluster_id: ID of the cluster this particle belongs to
            cluster_strength: Strength of the cluster (affects opacity and behavior)
        """
        self.position = position
        self.size = size
        self.color = color
        self.max_lifetime = lifetime
        self.lifetime = lifetime
        self.original_position = original_position
        self.cluster_id = cluster_id
        self.cluster_strength = cluster_strength
        
        # Calculate distance from original position for reference
        self.distance_from_origin = math.sqrt(
            (position.x() - original_position.x()) ** 2 +
            (position.y() - original_position.y()) ** 2
        )
        
        # Generate a unique ID for this particle
        self.id = str(uuid.uuid4())
        
        # Initialize velocity components
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        
    def update(self, dt: float, wind_vector: Tuple[float, float], turbulence: float) -> bool:
        """
        Update particle position and lifetime.
        
        Args:
            dt: Time delta in seconds
            wind_vector: (x, y) wind vector
            turbulence: Turbulence factor (0.0-1.0)
            
        Returns:
            True if particle is still alive, False if expired
        """
        # Update lifetime
        self.lifetime -= dt
        if self.lifetime <= 0:
            return False
            
        # Calculate lifetime ratio (1.0 at start, 0.0 at end)
        lifetime_ratio = self.lifetime / self.max_lifetime
        
        # Apply wind vector (scaled by cluster strength)
        wind_x, wind_y = wind_vector
        
        # Apply wind force to velocity (with damping)
        damping = 0.95  # Velocity damping factor
        self.velocity_x = self.velocity_x * damping + wind_x * dt * self.cluster_strength
        self.velocity_y = self.velocity_y * damping + wind_y * dt * self.cluster_strength
        
        # Apply turbulence (random movement)
        if turbulence > 0:
            # Scale turbulence by cluster strength and lifetime
            # Particles in stronger clusters and newer particles have less turbulence
            effective_turbulence = turbulence * (1.0 - self.cluster_strength * 0.7) * (1.0 - lifetime_ratio * 0.5)
            
            # Add random turbulence to velocity
            self.velocity_x += random.uniform(-effective_turbulence, effective_turbulence) * 10.0 * dt
            self.velocity_y += random.uniform(-effective_turbulence, effective_turbulence) * 10.0 * dt
        
        # Update position based on velocity
        self.position = QPointF(
            self.position.x() + self.velocity_x,
            self.position.y() + self.velocity_y
        )
        
        # Update distance from origin
        self.distance_from_origin = math.sqrt(
            (self.position.x() - self.original_position.x()) ** 2 +
            (self.position.y() - self.original_position.y()) ** 2
        )
        
        return True
        
    def get_opacity(self) -> float:
        """
        Get the current opacity of the particle.
        
        Opacity is affected by:
        - Lifetime (fades out as lifetime decreases)
        - Distance from origin (fades out at edges)
        - Cluster strength (stronger clusters have higher opacity)
        
        Returns:
            Opacity value (0.0-1.0)
        """
        # Base opacity from color
        base_opacity = self.color.alphaF()
        
        # Lifetime factor (fade out as lifetime decreases)
        lifetime_factor = self.lifetime / self.max_lifetime
        
        # Distance factor (fade out at edges)
        # This creates a natural falloff at the edges of weather systems
        distance_factor = 1.0
        if self.distance_from_origin > 0:
            # Calculate maximum distance based on original size
            max_distance = self.size * 10.0  # Arbitrary scaling factor
            distance_factor = max(0.0, 1.0 - (self.distance_from_origin / max_distance))
            
        # Cluster strength factor
        cluster_factor = self.cluster_strength
        
        # Combine factors
        opacity = base_opacity * lifetime_factor * distance_factor * cluster_factor
        
        # Ensure opacity is in valid range
        return max(0.0, min(1.0, opacity))


class Cluster:
    """
    Represents a cluster of particles in the weather visualization system.
    
    Clusters are used to create more realistic cloud-like formations by
    grouping particles around multiple density centers rather than
    distributing them uniformly.
    """
    
    def __init__(self, 
                 center: QPointF, 
                 radius: float, 
                 strength: float = 1.0,
                 is_main_cluster: bool = False):
        """
        Initialize a cluster.
        
        Args:
            center: Center position of the cluster
            radius: Radius of the cluster
            strength: Strength of the cluster (0.0-1.0)
            is_main_cluster: Whether this is the main cluster for a weather phenomenon
        """
        self.center = center
        self.radius = radius
        self.strength = strength
        self.is_main_cluster = is_main_cluster
        
        # Generate a unique ID for this cluster
        self.id = str(uuid.uuid4())
        
    def get_random_position(self) -> QPointF:
        """
        Get a random position within this cluster.
        
        Uses a normal distribution centered at the cluster center,
        with standard deviation based on the radius. This creates
        a natural-looking density pattern with more particles near
        the center of the cluster.
        
        Returns:
            Random position as QPointF
        """
        # Use normal distribution for more realistic clustering
        # Standard deviation is 1/3 of radius so ~99.7% of particles
        # fall within the cluster radius
        std_dev = self.radius / 3.0
        
        # Generate random offsets using normal distribution
        x_offset = np.random.normal(0, std_dev)
        y_offset = np.random.normal(0, std_dev)
        
        # Apply offsets to center position
        return QPointF(
            self.center.x() + x_offset,
            self.center.y() + y_offset
        )
        
    def get_strength_at_position(self, position: QPointF) -> float:
        """
        Get the strength of the cluster at a specific position.
        
        Strength decreases with distance from the center, creating
        a natural falloff at the edges of the cluster.
        
        Args:
            position: Position to check
            
        Returns:
            Strength at position (0.0-1.0)
        """
        # Calculate distance from center
        distance = math.sqrt(
            (position.x() - self.center.x()) ** 2 +
            (position.y() - self.center.y()) ** 2
        )
        
        # Calculate strength based on distance
        # Use a smooth falloff function (1 - (d/r)^2)^2
        if distance >= self.radius:
            return 0.0
        else:
            normalized_distance = distance / self.radius
            return self.strength * ((1.0 - normalized_distance ** 2) ** 2)


class ParticleSystem:
    """
    Manages particles for realistic weather visualization.
    
    The particle system creates, updates, and renders particles to represent
    weather phenomena like precipitation, VIL, and storm cells. It uses
    clustering algorithms to create realistic cloud-like formations and
    simulates wind effects for dynamic movement.
    """
    
    def __init__(self):
        """Initialize the particle system."""
        # Particle storage
        # Data type -> Data point ID -> List of particles
        self.particles: Dict[str, Dict[str, List[Particle]]] = {
            'precipitation': {},
            'vil': {},
            'cells': {}
        }
        
        # Cluster storage
        # Data type -> Data point ID -> List of clusters
        self.clusters: Dict[str, Dict[str, List[Cluster]]] = {
            'precipitation': {},
            'vil': {},
            'cells': {}
        }
        
        # Settings
        self.settings = {
            'max_particles_per_point': {
                'precipitation': 300,
                'vil': 250,
                'cells': 400
            },
            'base_particle_size': {
                'precipitation': 4.0,
                'vil': 5.0,
                'cells': 6.0
            },
            'particle_size_variation': 0.5,  # +/- 50% size variation
            'min_lifetime': 2.0,  # seconds
            'max_lifetime': 6.0,  # seconds
            'clusters_per_point': {
                'precipitation': 3,
                'vil': 4,
                'cells': 5
            },
            'satellite_cluster_count': {
                'precipitation': 2,
                'vil': 3,
                'cells': 4
            },
            'main_cluster_strength': 1.0,
            'satellite_cluster_min_strength': 0.3,
            'satellite_cluster_max_strength': 0.7,
            'enable_wind': True,
            'enable_turbulence': True,
            'quality_level': 3  # 1-5
        }
        
        # Get animation controller for wind simulation
        self.animation_controller = get_animation_controller()
        
        # Setup update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_particles)
        self.update_timer.start(16)  # ~60 FPS
        
        # Track last update time
        self.last_update_time = time.time()
        
        # Statistics
        self.stats = {
            'total_particles': 0,
            'active_data_points': 0,
            'update_time': 0.0,
            'render_time': 0.0
        }
        
        logger.info("[PARTICLE_SYSTEM] Initialized")
        
    def _update_particles(self):
        """Update all particles based on elapsed time and wind."""
        try:
            # Calculate time delta
            current_time = time.time()
            dt = current_time - self.last_update_time
            self.last_update_time = current_time
            
            # Limit dt to prevent large jumps
            dt = min(dt, 0.1)
            
            # Skip update if dt is too small
            if dt < 0.001:
                return
                
            # Get animation state from animation controller
            animation_state = self.animation_controller.get_animation_state()
            
            # Extract wind vector and turbulence
            wind_vector = animation_state.get('wind_vector', (0.0, 0.0))
            turbulence = animation_state.get('turbulence', 0.0)
            
            # Apply animation speed
            animation_speed = self.animation_controller.get_parameter('animation_speed')
            if animation_speed:
                dt *= animation_speed
                
            # Update particles for each data type
            for data_type in self.particles:
                for data_point_id in list(self.particles[data_type].keys()):
                    # Get particles for this data point
                    data_point_particles = self.particles[data_type][data_point_id]
                    
                    # Update each particle
                    updated_particles = []
                    for particle in data_point_particles:
                        # Update particle and check if still alive
                        if particle.update(dt, wind_vector, turbulence):
                            updated_particles.append(particle)
                    
                    # Replace particle list with updated list
                    self.particles[data_type][data_point_id] = updated_particles
                    
                    # Remove data point if no particles left
                    if not updated_particles:
                        del self.particles[data_type][data_point_id]
                        if data_point_id in self.clusters[data_type]:
                            del self.clusters[data_type][data_point_id]
            
            # Update statistics
            total_particles = sum(
                len(particles)
                for data_type in self.particles
                for particles in self.particles[data_type].values()
            )
            active_data_points = sum(
                len(self.particles[data_type])
                for data_type in self.particles
            )
            self.stats['total_particles'] = total_particles
            self.stats['active_data_points'] = active_data_points
            
        except Exception as e:
            logger.error(f"[PARTICLE_SYSTEM] Error updating particles: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def _create_clusters(self, data_type: str, data_point_id: str, 
                        center: QPointF, radius: float, intensity: float):
        """
        Create clusters for a data point.
        
        Args:
            data_type: Type of data ('precipitation', 'vil', 'cells')
            data_point_id: ID of the data point
            center: Center position of the data point
            radius: Radius of the data point
            intensity: Intensity of the data point (0.0-1.0)
        """
        try:
            # Initialize cluster list for this data point
            if data_point_id not in self.clusters[data_type]:
                self.clusters[data_type][data_point_id] = []
                
            # Clear existing clusters
            self.clusters[data_type][data_point_id] = []
            
            # Get cluster settings
            clusters_per_point = self.settings['clusters_per_point'][data_type]
            satellite_cluster_count = self.settings['satellite_cluster_count'][data_type]
            main_cluster_strength = self.settings['main_cluster_strength']
            satellite_cluster_min_strength = self.settings['satellite_cluster_min_strength']
            satellite_cluster_max_strength = self.settings['satellite_cluster_max_strength']
            
            # Scale cluster count based on intensity and quality level
            quality_factor = self.settings['quality_level'] / 3.0
            cluster_count = max(1, int(clusters_per_point * intensity * quality_factor))
            
            # Create main cluster at center
            main_cluster = Cluster(
                center=center,
                radius=radius,
                strength=main_cluster_strength * intensity,
                is_main_cluster=True
            )
            self.clusters[data_type][data_point_id].append(main_cluster)
            
            # Create satellite clusters
            satellite_count = min(satellite_cluster_count, cluster_count - 1)
            for i in range(satellite_count):
                # Calculate random position within main cluster radius
                angle = random.uniform(0, 2 * math.pi)
                distance = random.uniform(0, radius * 0.8)  # Keep within 80% of radius
                satellite_center = QPointF(
                    center.x() + distance * math.cos(angle),
                    center.y() + distance * math.sin(angle)
                )
                
                # Calculate satellite radius (smaller than main cluster)
                satellite_radius = radius * random.uniform(0.3, 0.6)
                
                # Calculate satellite strength (weaker than main cluster)
                satellite_strength = random.uniform(
                    satellite_cluster_min_strength,
                    satellite_cluster_max_strength
                ) * intensity
                
                # Create satellite cluster
                satellite_cluster = Cluster(
                    center=satellite_center,
                    radius=satellite_radius,
                    strength=satellite_strength,
                    is_main_cluster=False
                )
                self.clusters[data_type][data_point_id].append(satellite_cluster)
                
            logger.debug(f"[PARTICLE_SYSTEM] Created {len(self.clusters[data_type][data_point_id])} clusters for {data_type} data point {data_point_id}")
            
        except Exception as e:
            logger.error(f"[PARTICLE_SYSTEM] Error creating clusters: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def _generate_particles(self, data_type: str, data_point_id: str, 
                           data_point: Dict[str, Any]):
        """
        Generate particles for a data point.
        
        Args:
            data_type: Type of data ('precipitation', 'vil', 'cells')
            data_point_id: ID of the data point
            data_point: Data point dictionary
        """
        try:
            # Extract position
            position = data_point.get('position')
            if not isinstance(position, QPointF):
                # Convert tuple/list to QPointF
                if isinstance(position, (tuple, list)) and len(position) >= 2:
                    position = QPointF(position[0], position[1])
                else:
                    logger.error(f"[PARTICLE_SYSTEM] Invalid position format: {position}")
                    return
                    
            # Extract intensity
            intensity = data_point.get('intensity', 0.5)
            
            # Calculate radius based on data type and intensity
            base_radius = 20.0  # Base radius in pixels
            if data_type == 'precipitation':
                # Scale radius based on intensity and rate
                rate = data_point.get('rate', 20.0)
                radius = base_radius + intensity * 15.0 + min(rate / 10.0, 5.0) * 2.0
            elif data_type == 'vil':
                # Scale radius based on intensity and value
                value = data_point.get('value', 20.0)
                radius = base_radius + intensity * 20.0 + min(value / 10.0, 5.0) * 3.0
            elif data_type == 'cells':
                # Scale radius based on intensity
                radius = base_radius + intensity * 25.0
            else:
                radius = base_radius + intensity * 15.0
                
            # Create clusters for this data point
            self._create_clusters(data_type, data_point_id, position, radius, intensity)
            
            # Get clusters
            clusters = self.clusters[data_type].get(data_point_id, [])
            if not clusters:
                logger.error(f"[PARTICLE_SYSTEM] No clusters found for {data_type} data point {data_point_id}")
                return
                
            # Calculate particle count based on intensity and quality level
            max_particles = self.settings['max_particles_per_point'][data_type]
            quality_factor = self.settings['quality_level'] / 3.0
            particle_count = int(max_particles * intensity * quality_factor)
            
            # Ensure at least some particles
            particle_count = max(10, particle_count)
            
            # Get base particle size
            base_size = self.settings['base_particle_size'][data_type]
            
            # Get color based on data type
            if data_type == 'precipitation':
                # Get precipitation type
                precip_type = data_point.get('type', 'rain')
                
                # Get color based on type and intensity
                if precip_type == 'rain':
                    if intensity > 0.8:
                        color = QColor(255, 0, 0, 200)  # Red
                    elif intensity > 0.6:
                        color = QColor(255, 165, 0, 180)  # Orange
                    elif intensity > 0.3:
                        color = QColor(255, 255, 0, 160)  # Yellow
                    else:
                        color = QColor(0, 255, 0, 140)  # Green
                elif precip_type == 'snow':
                    if intensity > 0.8:
                        color = QColor(255, 255, 255, 200)  # White
                    elif intensity > 0.6:
                        color = QColor(200, 200, 255, 180)  # Light blue
                    elif intensity > 0.3:
                        color = QColor(180, 180, 255, 160)  # Lighter blue
                    else:
                        color = QColor(220, 220, 255, 140)  # Very light blue
                elif precip_type == 'hail':
                    if intensity > 0.8:
                        color = QColor(255, 0, 255, 200)  # Magenta
                    elif intensity > 0.6:
                        color = QColor(200, 0, 200, 180)  # Purple
                    elif intensity > 0.3:
                        color = QColor(180, 0, 180, 160)  # Light purple
                    else:
                        color = QColor(160, 0, 160, 140)  # Very light purple
                else:
                    if intensity > 0.8:
                        color = QColor(128, 0, 255, 200)  # Purple
                    elif intensity > 0.6:
                        color = QColor(100, 0, 200, 180)  # Dark purple
                    elif intensity > 0.3:
                        color = QColor(80, 0, 180, 160)  # Medium purple
                    else:
                        color = QColor(60, 0, 160, 140)  # Light purple
            elif data_type == 'vil':
                # Get color based on VIL level
                value = data_point.get('value', 20.0)
                if value > 30:
                    color = QColor(255, 0, 0, 200)  # Red
                elif value > 20:
                    color = QColor(255, 165, 0, 180)  # Orange
                elif value > 10:
                    color = QColor(255, 255, 0, 160)  # Yellow
                else:
                    color = QColor(0, 255, 0, 140)  # Green
            elif data_type == 'cells':
                # Get color based on intensity
                if intensity > 0.8:
                    color = QColor(255, 0, 0, 220)  # Red
                elif intensity > 0.6:
                    color = QColor(255, 100, 0, 200)  # Red-orange
                elif intensity > 0.4:
                    color = QColor(255, 200, 0, 180)  # Orange
                elif intensity > 0.2:
                    color = QColor(255, 255, 0, 160)  # Yellow
                else:
                    color = QColor(200, 200, 0, 140)  # Dark yellow
            else:
                # Default color
                color = QColor(128, 128, 128, 160)  # Gray
                
            # Initialize particle list for this data point
            if data_point_id not in self.particles[data_type]:
                self.particles[data_type][data_point_id] = []
                
            # Generate particles
            new_particles = []
            for i in range(particle_count):
                # Select a cluster based on strength
                # Stronger clusters have a higher chance of being selected
                cluster_weights = [cluster.strength for cluster in clusters]
                total_weight = sum(cluster_weights)
                if total_weight <= 0:
                    # Fallback if no valid clusters
                    selected_cluster = clusters[0]
                else:
                    # Normalize weights
                    normalized_weights = [weight / total_weight for weight in cluster_weights]
                    
                    # Select cluster based on weights
                    random_value = random.random()
                    cumulative_weight = 0.0
                    selected_cluster = clusters[-1]  # Default to last cluster
                    
                    for j, weight in enumerate(normalized_weights):
                        cumulative_weight += weight
                        if random_value <= cumulative_weight:
                            selected_cluster = clusters[j]
                            break
                
                # Get random position within selected cluster
                particle_position = selected_cluster.get_random_position()
                
                # Calculate particle size (base size with variation)
                size_variation = self.settings['particle_size_variation']
                particle_size = base_size * (1.0 + random.uniform(-size_variation, size_variation))
                
                # Scale size based on cluster strength
                particle_size *= 0.7 + selected_cluster.strength * 0.3
                
                # Calculate lifetime
                min_lifetime = self.settings['min_lifetime']
                max_lifetime = self.settings['max_lifetime']
                lifetime = random.uniform(min_lifetime, max_lifetime)
                
                # Create particle
                particle = Particle(
                    position=particle_position,
                    size=particle_size,
                    color=color,
                    lifetime=lifetime,
                    original_position=position,
                    cluster_id=clusters.index(selected_cluster),
                    cluster_strength=selected_cluster.strength
                )
                
                new_particles.append(particle)
                
            # Add new particles to existing particles
            self.particles[data_type][data_point_id].extend(new_particles)
            
            logger.debug(f"[PARTICLE_SYSTEM] Generated {len(new_particles)} particles for {data_type} data point {data_point_id}")
            
        except Exception as e:
            logger.error(f"[PARTICLE_SYSTEM] Error generating particles: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def update_data_point(self, data_type: str, data_point: Dict[str, Any]):
        """
        Update a single data point.
        
        Args:
            data_type: Type of data ('precipitation', 'vil', 'cells')
            data_point: Data point dictionary
        """
        try:
            # Validate data type
            if data_type not in self.particles:
                logger.error(f"[PARTICLE_SYSTEM] Invalid data type: {data_type}")
                return
                
            # Generate a unique ID for this data point if not provided
            data_point_id = data_point.get('id')
            if not data_point_id:
                # Generate ID based on position
                position = data_point.get('position')
                if isinstance(position, QPointF):
                    data_point_id = f"{data_type}_{position.x():.1f}_{position.y():.1f}"
                elif isinstance(position, (tuple, list)) and len(position) >= 2:
                    data_point_id = f"{data_type}_{position[0]:.1f}_{position[1]:.1f}"
                else:
                    data_point_id = f"{data_type}_{str(uuid.uuid4())}"
                    
            # Generate particles for this data point
            self._generate_particles(data_type, data_point_id, data_point)
            
        except Exception as e:
            logger.error(f"[PARTICLE_SYSTEM] Error updating data point: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def update_data(self, data_type: str, data_points: List[Dict[str, Any]]):
        """
        Update all data points of a specific type.
        
        Args:
            data_type: Type of data ('precipitation', 'vil', 'cells')
            data_points: List of data point dictionaries
        """
        try:
            # Validate data type
            if data_type not in self.particles:
                logger.error(f"[PARTICLE_SYSTEM] Invalid data type: {data_type}")
                return
                
            # Track existing data point IDs
            existing_ids = set()
            
            # Update each data point
            for data_point in data_points:
                # Generate a unique ID for this data point if not provided
                data_point_id = data_point.get('id')
                if not data_point_id:
                    # Generate ID based on position
                    position = data_point.get('position')
                    if isinstance(position, QPointF):
                        data_point_id = f"{data_type}_{position.x():.1f}_{position.y():.1f}"
                    elif isinstance(position, (tuple, list)) and len(position) >= 2:
                        data_point_id = f"{data_type}_{position[0]:.1f}_{position[1]:.1f}"
                    else:
                        data_point_id = f"{data_type}_{str(uuid.uuid4())}"
                        
                # Add to existing IDs
                existing_ids.add(data_point_id)
                
                # Generate particles for this data point
                self._generate_particles(data_type, data_point_id, data_point)
                
            # Remove data points that no longer exist
            for data_point_id in list(self.particles[data_type].keys()):
                if data_point_id not in existing_ids:
                    del self.particles[data_type][data_point_id]
                    if data_point_id in self.clusters[data_type]:
                        del self.clusters[data_type][data_point_id]
            
            # Update statistics
            self.stats['total_particles'] = sum(
                len(particles)
                for data_type in self.particles
                for particles in self.particles[data_type].values()
            )
            self.stats['active_data_points'] = sum(
                len(self.particles[data_type])
                for data_type in self.particles
            )
            
        except Exception as e:
            logger.error(f"[PARTICLE_SYSTEM] Error updating data: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def clear_data(self, data_type: Optional[str] = None):
        """
        Clear all data of a specific type or all data.
        
        Args:
            data_type: Type of data to clear, or None to clear all
        """
        try:
            if data_type is not None:
                # Clear specific data type
                if data_type in self.particles:
                    self.particles[data_type] = {}
                if data_type in self.clusters:
                    self.clusters[data_type] = {}
            else:
                # Clear all data
                for dt in self.particles:
                    self.particles[dt] = {}
                for dt in self.clusters:
                    self.clusters[dt] = {}
                    
            # Update statistics
            self.stats['total_particles'] = 0
            self.stats['active_data_points'] = 0
            
            logger.info(f"[PARTICLE_SYSTEM] Cleared {'all' if data_type is None else data_type} data")
            
        except Exception as e:
            logger.error(f"[PARTICLE_SYSTEM] Error clearing data: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def render(self, painter: QPainter, data_type: Optional[str] = None):
        """
        Render particles for a specific data type or all data types.
        
        Args:
            painter: QPainter to render with
            data_type: Type of data to render, or None to render all
        """
        try:
            start_time = time.time()
            
            # Enable antialiasing for smoother particles
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            
            # Determine which data types to render
            data_types = [data_type] if data_type is not None else list(self.particles.keys())
            
            # Render each data type
            for dt in data_types:
                if dt not in self.particles:
                    continue
                    
                # Get all particles for this data type
                all_particles = []
                for data_point_id, particles in self.particles[dt].items():
                    all_particles.extend(particles)
                    
                # Sort particles by size (largest first) for proper layering
                all_particles.sort(key=lambda p: p.size, reverse=True)
                
                # Render each particle
                for particle in all_particles:
                    # Get current opacity
                    opacity = particle.get_opacity()
                    
                    # Skip if fully transparent
                    if opacity <= 0.001:
                        continue
                        
                    # Create color with current opacity
                    color = QColor(particle.color)
                    color.setAlphaF(opacity)
                    
                    # Create radial gradient for smooth particle
                    gradient = QRadialGradient(
                        particle.position.x(),
                        particle.position.y(),
                        particle.size
                    )
                    gradient.setColorAt(0.0, color)
                    
                    # Create transparent version of color for edge
                    edge_color = QColor(color)
                    edge_color.setAlphaF(0.0)
                    gradient.setColorAt(1.0, edge_color)
                    
                    # Draw particle
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QBrush(gradient))
                    painter.drawEllipse(
                        particle.position.x() - particle.size,
                        particle.position.y() - particle.size,
                        particle.size * 2,
                        particle.size * 2
                    )
            
            # Update render time statistic
            self.stats['render_time'] = time.time() - start_time
            
        except Exception as e:
            logger.error(f"[PARTICLE_SYSTEM] Error rendering particles: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def set_quality_level(self, quality_level: int):
        """
        Set the quality level for particle rendering.
        
        Args:
            quality_level: Quality level (1-5)
        """
        # Ensure quality level is within valid range
        quality_level = max(1, min(5, quality_level))
        
        # Update quality level
        self.settings['quality_level'] = quality_level
        
        logger.info(f"[PARTICLE_SYSTEM] Set quality level to {quality_level}")
        
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the particle system.
        
        Returns:
            Dictionary of statistics
        """
        return self.stats.copy()


# Singleton instance
_particle_system = None

def get_particle_system() -> ParticleSystem:
    """
    Get the singleton particle system instance.
    
    Returns:
        ParticleSystem instance
    """
    global _particle_system
    if _particle_system is None:
        _particle_system = ParticleSystem()
    return _particle_system

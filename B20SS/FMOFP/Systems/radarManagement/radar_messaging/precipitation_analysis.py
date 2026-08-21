"""
Precipitation Analysis Capability for Weather Radar

Handles analysis of precipitation based on radar reflectivity data.
Provides precipitation rate and type classification.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import time
from dataclasses import dataclass
from Utils.logger.sys_logger import get_logger

logger = get_logger()

@dataclass
class PrecipitationData:
    """Precipitation data structure"""
    position: Tuple[float, float]  # (x, y) in nm
    reflectivity: float  # dBZ
    rate: float  # mm/hr
    type: str  # rain, snow, hail, etc.
    intensity: float  # 0-1 scale
    last_update: float  # timestamp

class PrecipitationAnalyzer:
    """
    Analyzes precipitation from radar reflectivity data.
    
    Capabilities:
    - DBZ processing and thresholding
    - Precipitation rate calculation
    - Type classification based on returns
    - Intensity analysis
    """
    
    def __init__(self):
        self._precipitation_data: Dict[Tuple[float, float], PrecipitationData] = {}
        self._min_reflectivity = 30  # dBZ threshold
        self._max_tracking_age = 300  # seconds
        self._enabled = True
        self._last_update = 0.0
        
    def process_radar_data(self, reflectivity_data: np.ndarray,
                          temperature_data: Optional[np.ndarray] = None,
                          scan_elevation: float = 0.0,
                          timestamp: Optional[float] = None) -> bool:
        """
        Process radar scan data to analyze precipitation.
        
        Args:
            reflectivity_data: 2D array of reflectivity values (dBZ)
            temperature_data: Optional 2D array of temperature data (°C)
            scan_elevation: Elevation angle of the scan (degrees)
            timestamp: Data timestamp (if None, uses current time)
        """
        try:
            if not self._enabled:
                return False
                
            current_time = timestamp or time.time()
            
            # Remove old data
            self._remove_expired_data(current_time)
            
            # Process precipitation data
            precip_data = self._analyze_precipitation(reflectivity_data, temperature_data)
            
            # Update precipitation tracking
            self._update_precipitation_data(precip_data, current_time)
            
            self._last_update = current_time
            return True
            
        except Exception as e:
            logger.error(f"Error processing radar data: {str(e)}")
            return False
            
    def _analyze_precipitation(self, reflectivity_data: np.ndarray,
                             temperature_data: Optional[np.ndarray]) -> List[Dict]:
        """
        Analyze precipitation from reflectivity data.
        
        Uses reflectivity thresholding and optional temperature data
        for precipitation type classification.
        """
        try:
            precipitation = []
            # Create binary mask of significant reflectivity
            significant = reflectivity_data > self._min_reflectivity
            
            # Find connected components
            from scipy import ndimage
            labeled, num_features = ndimage.label(significant)
            
            # Analyze each precipitation area
            for i in range(1, num_features + 1):
                precip_mask = labeled == i
                
                # Get precipitation properties
                precip_reflectivity = np.mean(reflectivity_data[precip_mask])
                
                # Calculate centroid
                coords = np.argwhere(precip_mask)
                center_y, center_x = coords.mean(axis=0)
                
                # Calculate rate using Z-R relationship
                # R = aZ^b where Z = 10^(dBZ/10)
                # Default coefficients: a=200, b=1.6 (Marshall-Palmer)
                Z = 10 ** (precip_reflectivity / 10)
                rate = (Z / 200) ** (1/1.6)
                
                # Determine type based on temperature if available
                if temperature_data is not None:
                    temp = temperature_data[int(center_y), int(center_x)]
                    precip_type = self._classify_precipitation_type(precip_reflectivity, temp)
                else:
                    precip_type = self._classify_precipitation_type(precip_reflectivity)
                
                precipitation.append({
                    'position': (float(center_x), float(center_y)),
                    'reflectivity': float(precip_reflectivity),
                    'rate': float(rate),
                    'type': precip_type,
                    'intensity': self._calculate_intensity(precip_reflectivity)
                })
                
            return precipitation
            
        except Exception as e:
            logger.error(f"Error analyzing precipitation: {str(e)}")
            return []
            
    def _classify_precipitation_type(self, reflectivity: float,
                                   temperature: Optional[float] = None) -> str:
        """
        Classify precipitation type based on reflectivity and temperature.
        
        Uses temperature when available for more accurate classification.
        """
        try:
            if temperature is not None:
                if temperature > 2:  # Above 2°C
                    if reflectivity > 55:
                        return "hail"
                    else:
                        return "rain"
                elif temperature < -5:  # Below -5°C
                    return "snow"
                else:  # Between -5°C and 2°C
                    return "mixed"
            else:
                # Classification based on reflectivity only
                if reflectivity > 55:
                    return "hail"
                elif reflectivity > 45:
                    return "heavy_rain"
                else:
                    return "rain"
                    
        except Exception as e:
            logger.error(f"Error classifying precipitation: {str(e)}")
            return "unknown"
            
    def _calculate_intensity(self, reflectivity: float) -> float:
        """Calculate normalized intensity from reflectivity."""
        try:
            # Convert dBZ to normalized intensity (0-1)
            # Assuming max significant reflectivity is 65 dBZ
            min_dbz = self._min_reflectivity
            max_dbz = 65
            
            intensity = (reflectivity - min_dbz) / (max_dbz - min_dbz)
            return float(np.clip(intensity, 0.0, 1.0))
            
        except Exception as e:
            logger.error(f"Error calculating intensity: {str(e)}")
            return 0.0
            
    def _update_precipitation_data(self, precip_data: List[Dict],
                                 timestamp: float) -> None:
        """Update precipitation tracking data."""
        try:
            # Clear old data
            self._precipitation_data.clear()
            
            # Add new precipitation data
            for precip in precip_data:
                self._precipitation_data[precip['position']] = PrecipitationData(
                    position=precip['position'],
                    reflectivity=precip['reflectivity'],
                    rate=precip['rate'],
                    type=precip['type'],
                    intensity=precip['intensity'],
                    last_update=timestamp
                )
                
        except Exception as e:
            logger.error(f"Error updating precipitation data: {str(e)}")
            
    def _remove_expired_data(self, current_time: float) -> None:
        """Remove precipitation data that hasn't been updated recently."""
        try:
            for pos in list(self._precipitation_data.keys()):
                data = self._precipitation_data[pos]
                if current_time - data.last_update > self._max_tracking_age:
                    del self._precipitation_data[pos]
        except Exception as e:
            logger.error(f"Error removing expired data: {str(e)}")
            
    def get_precipitation_data(self) -> List[PrecipitationData]:
        """Get list of current precipitation data."""
        return list(self._precipitation_data.values())
        
    def get_data_at_position(self, position: Tuple[float, float]) -> Optional[PrecipitationData]:
        """Get precipitation data at specific position."""
        return self._precipitation_data.get(position)
        
    def enable(self) -> None:
        """Enable precipitation analysis."""
        self._enabled = True
        
    def disable(self) -> None:
        """Disable precipitation analysis."""
        self._enabled = False
        
    def is_enabled(self) -> bool:
        """Check if analysis is enabled."""
        return self._enabled

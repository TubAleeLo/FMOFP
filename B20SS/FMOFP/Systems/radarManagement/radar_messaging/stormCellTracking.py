"""
Storm Cell Tracking Capability for Weather Radar

Handles detection, analysis, and tracking of storm cells based on radar returns.
Provides data that can be used by display systems.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import time
from dataclasses import dataclass
from Utils.logger.sys_logger import get_logger

logger = get_logger()

@dataclass
class StormCell:
    """Storm cell data structure"""
    cell_id: int
    position: Tuple[float, float]  # (x, y) in nm
    altitude: float  # feet
    reflectivity: float  # dBZ
    velocity: Tuple[float, float]  # (dx, dy) in knots
    size: float  # nm
    intensity: float  # 0-1 scale
    vertical_development: float  # feet/minute
    last_update: float  # timestamp

class StormCellTracker:
    """
    Tracks and analyzes storm cells from radar returns.

    Capabilities:
    - Storm cell detection from reflectivity data
    - Cell tracking and movement prediction
    - Intensity analysis
    - Vertical development monitoring
    - Cell lifecycle tracking
    """

    def __init__(self):
        self._cells: Dict[int, StormCell] = {}
        self._next_cell_id = 1
        self._min_reflectivity = 30  # dBZ
        self._max_tracking_age = 300  # seconds
        self._min_cell_size = 0.5  # nm
        self._enabled = True
        self._last_update = 0.0

    def process_radar_data(self, reflectivity_data: np.ndarray,
                          velocity_data: Optional[np.ndarray] = None,
                          scan_elevation: float = 0.0,
                          timestamp: Optional[float] = None) -> bool:
        """
        Process radar scan data to detect and track storm cells.

        Args:
            reflectivity_data: 2D array of reflectivity values (dBZ)
            velocity_data: Optional 2D array of velocity data (knots)
            scan_elevation: Elevation angle of the scan (degrees)
            timestamp: Data timestamp (if None, uses current time)
        """
        try:
            if not self._enabled:
                return False

            current_time = timestamp or time.time()

            # Remove old cells
            self._remove_expired_cells(current_time)

            # Detect cells in current scan
            new_cells = self._detect_cells(reflectivity_data)

            # Update existing cells and track movement
            self._update_cell_tracking(new_cells, velocity_data, current_time)

            # Analyze vertical development if we have elevation data
            if scan_elevation > 0:
                self._analyze_vertical_development(scan_elevation)

            self._last_update = current_time
            return True

        except Exception as e:
            logger.error(f"Error processing radar data: {str(e)}")
            return False

    def _detect_cells(self, reflectivity_data: np.ndarray) -> List[Dict]:
        """
        Detect storm cells in reflectivity data.

        Uses connected component analysis to identify regions of high reflectivity.
        """
        try:
            cells = []
            # Create binary mask of significant reflectivity
            significant = reflectivity_data > self._min_reflectivity

            # Find connected components (simplified for example)
            from scipy import ndimage
            labeled, num_features = ndimage.label(significant)

            # Analyze each potential cell
            for i in range(1, num_features + 1):
                cell_mask = labeled == i

                # Get cell properties
                cell_reflectivity = np.mean(reflectivity_data[cell_mask])
                cell_size = np.sum(cell_mask) * 0.5  # Assuming 0.5nm per pixel

                if cell_size >= self._min_cell_size:
                    # Calculate centroid
                    coords = np.argwhere(cell_mask)
                    center_y, center_x = coords.mean(axis=0)

                    cells.append({
                        'position': (float(center_x), float(center_y)),
                        'reflectivity': float(cell_reflectivity),
                        'size': float(cell_size)
                    })

            return cells

        except Exception as e:
            logger.error(f"Error detecting cells: {str(e)}")
            return []

    def _update_cell_tracking(self, new_cells: List[Dict],
                            velocity_data: Optional[np.ndarray],
                            timestamp: float) -> None:
        """Update tracking of existing cells and add new ones."""
        try:
            # Match new detections with existing tracks
            matched_cells = {}
            unmatched_new = []

            for new_cell in new_cells:
                matched = False
                new_pos = new_cell['position']

                # Try to match with existing cells
                for cell_id, existing in self._cells.items():
                    if self._is_same_cell(new_pos, existing.position):
                        self._update_existing_cell(cell_id, new_cell,
                                                velocity_data, timestamp)
                        matched_cells[cell_id] = True
                        matched = True
                        break

                if not matched:
                    unmatched_new.append(new_cell)

            # Add new cells
            for new_cell in unmatched_new:
                self._add_new_cell(new_cell, timestamp)

            # Remove unmatched existing cells
            for cell_id in list(self._cells.keys()):
                if cell_id not in matched_cells:
                    del self._cells[cell_id]

        except Exception as e:
            logger.error(f"Error updating cell tracking: {str(e)}")

    def _is_same_cell(self, pos1: Tuple[float, float],
                     pos2: Tuple[float, float],
                     max_dist: float = 5.0) -> bool:
        """Check if two positions likely represent the same cell."""
        try:
            dx = pos1[0] - pos2[0]
            dy = pos1[1] - pos2[1]
            distance = np.sqrt(dx*dx + dy*dy)
            return distance <= max_dist
        except Exception as e:
            logger.error(f"Error checking cell similarity: {str(e)}")
            return False

    def _update_existing_cell(self, cell_id: int, new_data: Dict,
                            velocity_data: Optional[np.ndarray],
                            timestamp: float) -> None:
        """Update an existing cell with new data."""
        try:
            cell = self._cells[cell_id]

            # Calculate velocity if we have previous position
            if velocity_data is not None:
                x, y = new_data['position']
                cell_velocity = velocity_data[int(y), int(x)]
            else:
                dt = timestamp - cell.last_update
                if dt > 0:
                    dx = new_data['position'][0] - cell.position[0]
                    dy = new_data['position'][1] - cell.position[1]
                    cell_velocity = (dx/dt, dy/dt)
                else:
                    cell_velocity = cell.velocity

            # Update cell data
            self._cells[cell_id] = StormCell(
                cell_id=cell_id,
                position=new_data['position'],
                altitude=cell.altitude,  # Maintained from previous
                reflectivity=new_data['reflectivity'],
                velocity=cell_velocity,
                size=new_data['size'],
                intensity=self._calculate_intensity(new_data['reflectivity']),
                vertical_development=cell.vertical_development,  # Maintained
                last_update=timestamp
            )

        except Exception as e:
            logger.error(f"Error updating existing cell: {str(e)}")

    def _add_new_cell(self, cell_data: Dict, timestamp: float) -> None:
        """Add a new cell to tracking."""
        try:
            self._cells[self._next_cell_id] = StormCell(
                cell_id=self._next_cell_id,
                position=cell_data['position'],
                altitude=0.0,  # Initial altitude
                reflectivity=cell_data['reflectivity'],
                velocity=(0.0, 0.0),  # Initial velocity
                size=cell_data['size'],
                intensity=self._calculate_intensity(cell_data['reflectivity']),
                vertical_development=0.0,  # Initial vertical development
                last_update=timestamp
            )
            self._next_cell_id += 1

        except Exception as e:
            logger.error(f"Error adding new cell: {str(e)}")

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

    def _remove_expired_cells(self, current_time: float) -> None:
        """Remove cells that haven't been updated recently."""
        try:
            for cell_id in list(self._cells.keys()):
                cell = self._cells[cell_id]
                if current_time - cell.last_update > self._max_tracking_age:
                    del self._cells[cell_id]
        except Exception as e:
            logger.error(f"Error removing expired cells: {str(e)}")


    def _analyze_vertical_development(self, scan_elevation: float) -> None:
        """
        Estimate vertical development for tracked cells using the current
        elevation angle.  A higher elevation scan that still shows high
        reflectivity indicates a taller cell.
        """
        try:
            for cell_id, cell in self._cells.items():
                # Simple model: vertical development proportional to elevation
                # at which the cell was last detected with strong reflectivity.
                if cell.reflectivity >= self._min_reflectivity:
                    # Estimate cell top altitude from elevation angle (degrees)
                    # and typical range (use size as proxy for range in nm).
                    range_m = cell.size * 1852  # nm → m
                    top_altitude = range_m * np.tan(np.radians(scan_elevation))
                    dt = time.time() - cell.last_update
                    if dt > 0:
                        old_top = cell.altitude
                        rate = (top_altitude - old_top) / dt  # feet/min (approx)
                        self._cells[cell_id] = StormCell(
                            cell_id=cell.cell_id,
                            position=cell.position,
                            altitude=top_altitude,
                            reflectivity=cell.reflectivity,
                            velocity=cell.velocity,
                            size=cell.size,
                            intensity=cell.intensity,
                            vertical_development=float(rate),
                            last_update=cell.last_update
                        )
        except Exception as e:
            logger.error(f"Error analyzing vertical development: {str(e)}")

    def get_active_cells(self) -> List[StormCell]:
        """Get list of currently active storm cells."""
        return list(self._cells.values())

    def get_cell_by_id(self, cell_id: int) -> Optional[StormCell]:
        """Get specific storm cell by ID."""
        return self._cells.get(cell_id)

    def enable(self) -> None:
        """Enable storm cell tracking."""
        self._enabled = True

    def disable(self) -> None:
        """Disable storm cell tracking."""
        self._enabled = False

    def is_enabled(self) -> bool:
        """Check if tracking is enabled."""
        return self._enabled

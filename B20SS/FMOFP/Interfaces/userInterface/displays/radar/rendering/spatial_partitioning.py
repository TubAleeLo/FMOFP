"""
Spatial partitioning system for optimized weather radar visualization.

This module provides spatial partitioning techniques to optimize rendering
of dense weather data by dividing the screen space into cells and only
processing/rendering particles that are visible or relevant.
"""
from PyQt6.QtCore import QRectF, QPointF
from typing import Dict, Any, List, Tuple, Optional, Set, Callable
import math
import time
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class SpatialGrid:
    """
    Grid-based spatial partitioning system.
    
    Divides the screen space into a grid of cells and tracks which
    objects are in which cells for efficient spatial queries.
    """
    
    def __init__(self, width: float, height: float, cell_size: float = 50.0):
        """
        Initialize the spatial grid.
        
        Args:
            width: Width of the total area
            height: Height of the total area
            cell_size: Size of each grid cell
        """
        self.width = width
        self.height = height
        self.cell_size = cell_size
        
        # Calculate grid dimensions
        self.cols = math.ceil(width / cell_size)
        self.rows = math.ceil(height / cell_size)
        
        # Initialize grid cells
        self.grid: Dict[Tuple[int, int], Set[str]] = {}
        
        # Object storage
        self.objects: Dict[str, Dict[str, Any]] = {}
        
        # Statistics
        self.stats = {
            'object_count': 0,
            'cell_count': 0,
            'query_count': 0,
            'last_update_time': 0.0,
            'update_duration': 0.0
        }
        
        logger.info(f"[SPATIAL] Initialized grid with {self.cols}x{self.rows} cells")
        
    def resize(self, width: float, height: float):
        """
        Resize the grid.
        
        Args:
            width: New width
            height: New height
        """
        old_cols = self.cols
        old_rows = self.rows
        
        self.width = width
        self.height = height
        
        # Recalculate grid dimensions
        self.cols = math.ceil(width / self.cell_size)
        self.rows = math.ceil(height / self.cell_size)
        
        # Only rebuild grid if dimensions changed
        if old_cols != self.cols or old_rows != self.rows:
            self._rebuild_grid()
            logger.info(f"[SPATIAL] Resized grid to {self.cols}x{self.rows} cells")
            
    def _rebuild_grid(self):
        """Rebuild the entire grid."""
        # Clear existing grid
        self.grid = {}
        
        # Re-insert all objects
        for obj_id, obj in self.objects.items():
            self._insert_object(obj_id, obj)
            
    def _get_cell_coords(self, x: float, y: float) -> Tuple[int, int]:
        """
        Get the grid cell coordinates for a point.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            Tuple of (col, row)
        """
        col = max(0, min(self.cols - 1, int(x / self.cell_size)))
        row = max(0, min(self.rows - 1, int(y / self.cell_size)))
        return (col, row)
        
    def _get_cells_for_rect(self, rect: QRectF) -> List[Tuple[int, int]]:
        """
        Get all grid cells that intersect with a rectangle.
        
        Args:
            rect: Rectangle to check
            
        Returns:
            List of (col, row) tuples
        """
        min_col, min_row = self._get_cell_coords(rect.left(), rect.top())
        max_col, max_row = self._get_cell_coords(rect.right(), rect.bottom())
        
        cells = []
        for row in range(min_row, max_col + 1):
            for col in range(min_col, max_col + 1):
                cells.append((col, row))
                
        return cells
        
    def _insert_object(self, obj_id: str, obj: Dict[str, Any]):
        """
        Insert an object into the appropriate grid cells.
        
        Args:
            obj_id: Object ID
            obj: Object data
        """
        # Get object position
        x = obj.get('x', 0.0)
        y = obj.get('y', 0.0)
        
        # Get object size/radius
        size = obj.get('size', 1.0)
        
        # Create rectangle for object
        rect = QRectF(x - size/2, y - size/2, size, size)
        
        # Get cells that intersect with this rectangle
        cells = self._get_cells_for_rect(rect)
        
        # Add object to each cell
        for cell in cells:
            if cell not in self.grid:
                self.grid[cell] = set()
            self.grid[cell].add(obj_id)
            
    def insert(self, obj_id: str, obj: Dict[str, Any]):
        """
        Insert an object into the grid.
        
        Args:
            obj_id: Object ID
            obj: Object data
        """
        # Store object
        self.objects[obj_id] = obj
        
        # Insert into grid
        self._insert_object(obj_id, obj)
        
        # Update stats
        self.stats['object_count'] = len(self.objects)
        self.stats['cell_count'] = len(self.grid)
        
    def update(self, obj_id: str, obj: Dict[str, Any]):
        """
        Update an object's position in the grid.
        
        Args:
            obj_id: Object ID
            obj: Updated object data
        """
        # Remove from current cells
        self.remove(obj_id)
        
        # Insert at new position
        self.insert(obj_id, obj)
        
    def remove(self, obj_id: str):
        """
        Remove an object from the grid.
        
        Args:
            obj_id: Object ID
        """
        # Remove from all cells
        for cell_objects in self.grid.values():
            if obj_id in cell_objects:
                cell_objects.remove(obj_id)
                
        # Remove from objects dictionary
        if obj_id in self.objects:
            del self.objects[obj_id]
            
        # Update stats
        self.stats['object_count'] = len(self.objects)
        
        # Remove empty cells
        empty_cells = [cell for cell, objects in self.grid.items() if not objects]
        for cell in empty_cells:
            del self.grid[cell]
            
        self.stats['cell_count'] = len(self.grid)
        
    def clear(self):
        """Clear all objects from the grid."""
        self.grid = {}
        self.objects = {}
        
        # Update stats
        self.stats['object_count'] = 0
        self.stats['cell_count'] = 0
        
    def query_rect(self, rect: QRectF) -> List[str]:
        """
        Query all objects that intersect with a rectangle.
        
        Args:
            rect: Rectangle to query
            
        Returns:
            List of object IDs
        """
        # Get cells that intersect with this rectangle
        cells = self._get_cells_for_rect(rect)
        
        # Collect all objects in these cells
        result = set()
        for cell in cells:
            if cell in self.grid:
                result.update(self.grid[cell])
                
        # Update stats
        self.stats['query_count'] += 1
        
        return list(result)
        
    def query_point(self, point: QPointF, radius: float = 0.0) -> List[str]:
        """
        Query all objects that contain a point or are within a radius.
        
        Args:
            point: Point to query
            radius: Optional radius around point
            
        Returns:
            List of object IDs
        """
        if radius > 0:
            # Use rectangle query for radius
            rect = QRectF(point.x() - radius, point.y() - radius, radius * 2, radius * 2)
            return self.query_rect(rect)
            
        # Get cell for this point
        cell = self._get_cell_coords(point.x(), point.y())
        
        # Get objects in this cell
        if cell in self.grid:
            # Update stats
            self.stats['query_count'] += 1
            
            return list(self.grid[cell])
        
        # Update stats
        self.stats['query_count'] += 1
        
        return []
        
    def query_visible(self, viewport: QRectF) -> List[str]:
        """
        Query all objects visible within a viewport.
        
        Args:
            viewport: Visible rectangle
            
        Returns:
            List of object IDs
        """
        return self.query_rect(viewport)
        
    def update_all(self, objects: Dict[str, Dict[str, Any]]):
        """
        Update all objects in the grid.
        
        Args:
            objects: Dictionary of object ID -> object data
        """
        start_time = time.time()
        
        # Clear grid but keep objects
        old_objects = self.objects
        self.grid = {}
        self.objects = {}
        
        # Insert all objects
        for obj_id, obj in objects.items():
            self.insert(obj_id, obj)
            
        # Remove objects that no longer exist
        for obj_id in list(old_objects.keys()):
            if obj_id not in objects:
                self.remove(obj_id)
                
        # Update stats
        self.stats['update_duration'] = time.time() - start_time
        self.stats['last_update_time'] = time.time()
        
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the grid.
        
        Returns:
            Dictionary of statistics
        """
        return self.stats.copy()


class DirtyRegionTracker:
    """
    Tracks regions of the screen that need to be redrawn.
    
    This allows for partial updates of the display, which can
    significantly improve performance for large displays.
    """
    
    def __init__(self, width: float, height: float, cell_size: float = 50.0):
        """
        Initialize the dirty region tracker.
        
        Args:
            width: Width of the total area
            height: Height of the total area
            cell_size: Size of each grid cell
        """
        self.width = width
        self.height = height
        self.cell_size = cell_size
        
        # Calculate grid dimensions
        self.cols = math.ceil(width / cell_size)
        self.rows = math.ceil(height / cell_size)
        
        # Initialize dirty cells
        self.dirty_cells: Set[Tuple[int, int]] = set()
        
        # Full redraw flag
        self.full_redraw_needed = True
        
        # Statistics
        self.stats = {
            'dirty_cell_count': 0,
            'mark_count': 0,
            'clear_count': 0,
            'full_redraw_count': 0
        }
        
        logger.info(f"[DIRTY] Initialized tracker with {self.cols}x{self.rows} cells")
        
    def resize(self, width: float, height: float):
        """
        Resize the tracker.
        
        Args:
            width: New width
            height: New height
        """
        old_cols = self.cols
        old_rows = self.rows
        
        self.width = width
        self.height = height
        
        # Recalculate grid dimensions
        self.cols = math.ceil(width / self.cell_size)
        self.rows = math.ceil(height / self.cell_size)
        
        # Force full redraw if dimensions changed
        if old_cols != self.cols or old_rows != self.rows:
            self.mark_full_redraw()
            logger.info(f"[DIRTY] Resized tracker to {self.cols}x{self.rows} cells")
            
    def _get_cell_coords(self, x: float, y: float) -> Tuple[int, int]:
        """
        Get the grid cell coordinates for a point.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            Tuple of (col, row)
        """
        col = max(0, min(self.cols - 1, int(x / self.cell_size)))
        row = max(0, min(self.rows - 1, int(y / self.cell_size)))
        return (col, row)
        
    def _get_cells_for_rect(self, rect: QRectF) -> List[Tuple[int, int]]:
        """
        Get all grid cells that intersect with a rectangle.
        
        Args:
            rect: Rectangle to check
            
        Returns:
            List of (col, row) tuples
        """
        min_col, min_row = self._get_cell_coords(rect.left(), rect.top())
        max_col, max_row = self._get_cell_coords(rect.right(), rect.bottom())
        
        cells = []
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                cells.append((col, row))
                
        return cells
        
    def mark_dirty(self, rect: QRectF):
        """
        Mark a rectangle as dirty.
        
        Args:
            rect: Rectangle to mark
        """
        # If full redraw is already needed, no need to mark individual cells
        if self.full_redraw_needed:
            return
            
        # Get cells that intersect with this rectangle
        cells = self._get_cells_for_rect(rect)
        
        # Mark cells as dirty
        self.dirty_cells.update(cells)
        
        # Update stats
        self.stats['dirty_cell_count'] = len(self.dirty_cells)
        self.stats['mark_count'] += 1
        
    def mark_point_dirty(self, x: float, y: float, radius: float = 0.0):
        """
        Mark a point (or circle) as dirty.
        
        Args:
            x: X coordinate
            y: Y coordinate
            radius: Optional radius around point
        """
        if radius > 0:
            # Use rectangle for radius
            rect = QRectF(x - radius, y - radius, radius * 2, radius * 2)
            self.mark_dirty(rect)
        else:
            # Mark single cell
            cell = self._get_cell_coords(x, y)
            
            # If full redraw is already needed, no need to mark individual cells
            if self.full_redraw_needed:
                return
                
            self.dirty_cells.add(cell)
            
            # Update stats
            self.stats['dirty_cell_count'] = len(self.dirty_cells)
            self.stats['mark_count'] += 1
            
    def mark_full_redraw(self):
        """Mark the entire screen as dirty."""
        self.full_redraw_needed = True
        self.dirty_cells.clear()
        
        # Update stats
        self.stats['dirty_cell_count'] = self.cols * self.rows
        self.stats['full_redraw_count'] += 1
        
    def clear(self):
        """Clear all dirty regions."""
        self.dirty_cells.clear()
        self.full_redraw_needed = False
        
        # Update stats
        self.stats['dirty_cell_count'] = 0
        self.stats['clear_count'] += 1
        
    def is_dirty(self, rect: QRectF) -> bool:
        """
        Check if a rectangle intersects with any dirty regions.
        
        Args:
            rect: Rectangle to check
            
        Returns:
            True if dirty, False otherwise
        """
        # If full redraw is needed, everything is dirty
        if self.full_redraw_needed:
            return True
            
        # Get cells that intersect with this rectangle
        cells = self._get_cells_for_rect(rect)
        
        # Check if any cell is dirty
        return any(cell in self.dirty_cells for cell in cells)
        
    def is_point_dirty(self, x: float, y: float) -> bool:
        """
        Check if a point is in a dirty region.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            True if dirty, False otherwise
        """
        # If full redraw is needed, everything is dirty
        if self.full_redraw_needed:
            return True
            
        # Get cell for this point
        cell = self._get_cell_coords(x, y)
        
        # Check if cell is dirty
        return cell in self.dirty_cells
        
    def get_dirty_rects(self) -> List[QRectF]:
        """
        Get a list of dirty rectangles.
        
        Returns:
            List of dirty rectangles
        """
        # If full redraw is needed, return the entire screen
        if self.full_redraw_needed:
            return [QRectF(0, 0, self.width, self.height)]
            
        # Convert dirty cells to rectangles
        rects = []
        for col, row in self.dirty_cells:
            x = col * self.cell_size
            y = row * self.cell_size
            rects.append(QRectF(x, y, self.cell_size, self.cell_size))
            
        # Merge adjacent rectangles to reduce the number of rects
        # This is a simple implementation that may not be optimal
        merged_rects = self._merge_rects(rects)
        
        return merged_rects
        
    def _merge_rects(self, rects: List[QRectF]) -> List[QRectF]:
        """
        Merge adjacent rectangles.
        
        Args:
            rects: List of rectangles to merge
            
        Returns:
            List of merged rectangles
        """
        if not rects:
            return []
            
        # Sort rectangles by top-left corner
        sorted_rects = sorted(rects, key=lambda r: (r.top(), r.left()))
        
        # Initialize result with first rectangle
        result = [sorted_rects[0]]
        
        # Try to merge each rectangle with the last one in result
        for rect in sorted_rects[1:]:
            last = result[-1]
            
            # Check if rectangles can be merged horizontally
            if (abs(last.top() - rect.top()) < 0.001 and
                abs(last.height() - rect.height()) < 0.001 and
                abs(last.right() - rect.left()) < 0.001):
                # Merge horizontally
                result[-1] = QRectF(
                    last.left(),
                    last.top(),
                    last.width() + rect.width(),
                    last.height()
                )
            # Check if rectangles can be merged vertically
            elif (abs(last.left() - rect.left()) < 0.001 and
                  abs(last.width() - rect.width()) < 0.001 and
                  abs(last.bottom() - rect.top()) < 0.001):
                # Merge vertically
                result[-1] = QRectF(
                    last.left(),
                    last.top(),
                    last.width(),
                    last.height() + rect.height()
                )
            else:
                # Cannot merge, add as new rectangle
                result.append(rect)
                
        return result
        
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the tracker.
        
        Returns:
            Dictionary of statistics
        """
        return self.stats.copy()


# Singleton instances
_spatial_grid = None
_dirty_region_tracker = None

def get_spatial_grid(width: float = 800.0, height: float = 600.0) -> SpatialGrid:
    """
    Get the singleton spatial grid instance.
    
    Args:
        width: Width of the total area
        height: Height of the total area
        
    Returns:
        SpatialGrid instance
    """
    global _spatial_grid
    if _spatial_grid is None:
        _spatial_grid = SpatialGrid(width, height)
    return _spatial_grid

def get_dirty_region_tracker(width: float = 800.0, height: float = 600.0) -> DirtyRegionTracker:
    """
    Get the singleton dirty region tracker instance.
    
    Args:
        width: Width of the total area
        height: Height of the total area
        
    Returns:
        DirtyRegionTracker instance
    """
    global _dirty_region_tracker
    if _dirty_region_tracker is None:
        _dirty_region_tracker = DirtyRegionTracker(width, height)
    return _dirty_region_tracker

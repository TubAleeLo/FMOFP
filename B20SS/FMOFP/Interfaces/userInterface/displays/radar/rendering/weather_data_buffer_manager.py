"""
Weather Data Buffer Manager

Manages multiple buffer layers for different weather data types.
Handles compositing and blending between layers.
"""
from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QPainter, QImage, QColor
from typing import Dict, List, Optional, Set, Tuple
import time

from Utils.logger.sys_logger import get_logger

logger = get_logger()

class WeatherDataBufferManager:
    """
    Manages multiple buffer layers for different weather data types.
    Handles compositing and blending between layers.
    """
    
    def __init__(self):
        """Initialize buffer manager with empty buffers."""
        # Data type -> QImage mapping
        self.buffers: Dict[str, QImage] = {}
        
        # Composite buffer for final output
        self.composite_buffer: Optional[QImage] = None
        
        # Data type -> list of dirty rects
        self.dirty_regions: Dict[str, List[QRectF]] = {}
        
        # Track buffer size
        self.buffer_size = QSize(0, 0)
        
        # Track last update time for each buffer
        self.last_update_time: Dict[str, float] = {}
        
        # Track buffer usage statistics
        self.buffer_stats = {
            'composite_count': 0,
            'clear_count': 0,
            'last_stats_time': time.time()
        }
        
        # Known data types
        self.known_data_types = ['precipitation', 'vil', 'cells']
        
        logger.info("[BUFFER_MANAGER] Initialized WeatherDataBufferManager")
        
    def initialize_buffers(self, size: QSize):
        """
        Initialize all buffers to the specified size.
        
        Args:
            size: QSize for the buffers
        """
        try:
            # Check if size has changed
            if size == self.buffer_size and self.composite_buffer is not None:
                return
                
            # Update buffer size
            self.buffer_size = size
            
            # Create buffers for each data type
            for data_type in self.known_data_types:
                self.buffers[data_type] = QImage(
                    size, 
                    QImage.Format.Format_ARGB32_Premultiplied
                )
                self.buffers[data_type].fill(Qt.GlobalColor.transparent)
                self.dirty_regions[data_type] = []
                
            # Create composite buffer
            self.composite_buffer = QImage(
                size, 
                QImage.Format.Format_ARGB32_Premultiplied
            )
            self.composite_buffer.fill(Qt.GlobalColor.transparent)
            
            logger.info(f"[BUFFER_MANAGER] Initialized buffers with size {size.width()}x{size.height()}")
            
        except Exception as e:
            logger.error(f"[BUFFER_MANAGER] Error initializing buffers: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
    def get_buffer(self, data_type: str) -> Optional[QImage]:
        """
        Get the buffer for a specific data type.
        
        Args:
            data_type: Type of data ('precipitation', 'vil', etc.)
            
        Returns:
            QImage buffer for the specified data type or None if not found
        """
        # Create buffer if it doesn't exist
        if data_type not in self.buffers:
            if self.buffer_size.width() > 0 and self.buffer_size.height() > 0:
                self.buffers[data_type] = QImage(
                    self.buffer_size, 
                    QImage.Format.Format_ARGB32_Premultiplied
                )
                self.buffers[data_type].fill(Qt.GlobalColor.transparent)
                self.dirty_regions[data_type] = []
                logger.info(f"[BUFFER_MANAGER] Created new buffer for {data_type}")
            else:
                logger.error(f"[BUFFER_MANAGER] Cannot create buffer for {data_type}: Invalid size")
                return None
                
        return self.buffers.get(data_type)
        
    def mark_dirty_region(self, data_type: str, rect: QRectF):
        """
        Mark a region as dirty for a specific data type.
        
        Args:
            data_type: Type of data
            rect: QRectF of dirty region
        """
        if data_type not in self.dirty_regions:
            self.dirty_regions[data_type] = []
            
        # Add dirty region
        self.dirty_regions[data_type].append(rect)
        
        # Update last update time
        self.last_update_time[data_type] = time.time()
        
        logger.debug(f"[BUFFER_MANAGER] Marked dirty region for {data_type}: {rect}")
        
    def get_dirty_regions(self, data_type: Optional[str] = None) -> Dict[str, List[QRectF]]:
        """
        Get dirty regions for a specific data type or all data types.
        
        Args:
            data_type: Type of data, or None for all
            
        Returns:
            Dictionary of data type -> list of dirty rects
        """
        if data_type is not None:
            return {data_type: self.dirty_regions.get(data_type, [])}
        else:
            return self.dirty_regions
            
    def clear_dirty_regions(self, data_type: Optional[str] = None):
        """
        Clear dirty regions for a specific data type or all data types.
        
        Args:
            data_type: Type of data, or None for all
        """
        if data_type is not None:
            if data_type in self.dirty_regions:
                self.dirty_regions[data_type] = []
        else:
            for dt in self.dirty_regions:
                self.dirty_regions[dt] = []
                
        logger.debug(f"[BUFFER_MANAGER] Cleared dirty regions for {data_type if data_type else 'all data types'}")
        
    def composite_layers(self) -> QImage:
        """
        Composite all layers into the final buffer.
        
        Returns:
            QImage with the composited result
        """
        try:
            # Ensure composite buffer exists
            if self.composite_buffer is None or self.buffer_size.width() <= 0 or self.buffer_size.height() <= 0:
                logger.error("[BUFFER_MANAGER] Cannot composite: Invalid buffer")
                # Return an empty image
                return QImage(1, 1, QImage.Format.Format_ARGB32_Premultiplied)
                
            # Clear composite buffer
            self.composite_buffer.fill(Qt.GlobalColor.transparent)
            
            # Create painter for composite buffer
            painter = QPainter(self.composite_buffer)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            
            # Composite order (bottom to top)
            composite_order = ['cells', 'precipitation', 'vil']
            
            # Draw each layer
            for data_type in composite_order:
                if data_type in self.buffers:
                    # Draw buffer with alpha blending
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                    painter.drawImage(0, 0, self.buffers[data_type])
                    
            # End painting
            painter.end()
            
            # Update stats
            self.buffer_stats['composite_count'] += 1
            
            # Log stats periodically
            current_time = time.time()
            if current_time - self.buffer_stats['last_stats_time'] >= 60.0:  # Log every minute
                logger.info(f"[BUFFER_MANAGER] Buffer stats: composite_count={self.buffer_stats['composite_count']}, clear_count={self.buffer_stats['clear_count']}")
                self.buffer_stats['composite_count'] = 0
                self.buffer_stats['clear_count'] = 0
                self.buffer_stats['last_stats_time'] = current_time
                
            return self.composite_buffer
            
        except Exception as e:
            logger.error(f"[BUFFER_MANAGER] Error compositing layers: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Return an empty image
            return QImage(1, 1, QImage.Format.Format_ARGB32_Premultiplied)
            
    def clear_buffer(self, data_type: Optional[str] = None):
        """
        Clear a specific buffer or all buffers.
        
        Args:
            data_type: Type of data, or None to clear all
        """
        try:
            if data_type is not None:
                # Clear specific buffer
                if data_type in self.buffers:
                    self.buffers[data_type].fill(Qt.GlobalColor.transparent)
                    self.dirty_regions[data_type] = []
                    logger.debug(f"[BUFFER_MANAGER] Cleared buffer for {data_type}")
            else:
                # Clear all buffers
                for dt in self.buffers:
                    self.buffers[dt].fill(Qt.GlobalColor.transparent)
                    self.dirty_regions[dt] = []
                
                # Clear composite buffer
                if self.composite_buffer is not None:
                    self.composite_buffer.fill(Qt.GlobalColor.transparent)
                    
                logger.debug("[BUFFER_MANAGER] Cleared all buffers")
                
            # Update stats
            self.buffer_stats['clear_count'] += 1
            
        except Exception as e:
            logger.error(f"[BUFFER_MANAGER] Error clearing buffer: {str(e)}")
            
    def get_buffer_painter(self, data_type: str) -> Optional[QPainter]:
        """
        Get a painter for a specific buffer.
        
        Args:
            data_type: Type of data
            
        Returns:
            QPainter for the buffer or None if buffer doesn't exist
        """
        buffer = self.get_buffer(data_type)
        if buffer is None:
            return None
            
        # Create painter
        painter = QPainter(buffer)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        
        return painter
        
    def merge_dirty_regions(self, data_type: str, max_regions: int = 10):
        """
        Merge dirty regions to reduce the number of regions.
        
        Args:
            data_type: Type of data
            max_regions: Maximum number of regions to keep
        """
        if data_type not in self.dirty_regions or len(self.dirty_regions[data_type]) <= max_regions:
            return
            
        # Sort regions by area (largest first)
        regions = sorted(
            self.dirty_regions[data_type],
            key=lambda r: r.width() * r.height(),
            reverse=True
        )
        
        # Keep largest regions up to max_regions
        if len(regions) > max_regions:
            regions = regions[:max_regions]
            
        # Update dirty regions
        self.dirty_regions[data_type] = regions
        
        logger.debug(f"[BUFFER_MANAGER] Merged dirty regions for {data_type}: {len(regions)} regions")

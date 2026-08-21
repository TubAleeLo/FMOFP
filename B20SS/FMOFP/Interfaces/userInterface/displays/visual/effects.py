"""
Visual effects utilities for enhanced display rendering
"""
from PyQt6.QtCore import QPointF, QRectF, Qt, QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient, QRadialGradient
from typing import Optional, Tuple, List, Dict, Any
from .theme_manager import get_theme_manager
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class VisualEffects:
    """Utility class for enhanced visual effects that can be applied to displays"""
    
    def __init__(self):
        """Initialize visual effects with animation state"""
        self._pulse_time = 0.0  # Time counter for pulse effects
        self._last_update_time = 0.0  # Last update time for animations
    
    @staticmethod
    def draw_enhanced_text(painter: QPainter, rect: QRectF, flags: int, text: str, 
                          glow: bool = False, glow_color: Optional[QColor] = None,
                          shadow: bool = False) -> None:
        """Draw text with optional glow and shadow effects"""
        theme_mgr = get_theme_manager()
        
        # Save painter state
        painter.save()
        
        try:
            # Apply shadow if enabled
            if shadow and theme_mgr.get_style_param("use_shadows", False):
                shadow_offset_x = theme_mgr.get_style_param("shadow_offset_x", 1.0)
                shadow_offset_y = theme_mgr.get_style_param("shadow_offset_y", 1.0)
                shadow_color = QColor(0, 0, 0, 100)  # Semi-transparent black
                
                # Draw shadow text
                painter.setPen(shadow_color)
                shadow_rect = QRectF(
                    rect.x() + shadow_offset_x,
                    rect.y() + shadow_offset_y,
                    rect.width(),
                    rect.height()
                )
                painter.drawText(shadow_rect, flags, text)
            
            # Apply glow if enabled
            if glow and theme_mgr.get_style_param("use_gradients", False):
                if glow_color is None:
                    glow_color = theme_mgr.get_color("hud")
                
                # Create semi-transparent glow color
                glow_alpha = min(glow_color.alpha(), 120)  # Cap alpha for glow
                glow_effect_color = QColor(glow_color)
                glow_effect_color.setAlpha(glow_alpha)
                
                # Draw glow with slight offset in multiple passes
                for offset in [0.8, 0.6, 0.4, 0.2]:
                    painter.setPen(glow_effect_color)
                    painter.drawText(rect, flags, text)
            
            # Draw main text
            painter.setPen(glow_color if glow_color else theme_mgr.get_color("hud"))
            painter.drawText(rect, flags, text)
            
        finally:
            # Restore painter state
            painter.restore()
    
    @staticmethod
    def draw_enhanced_line(painter: QPainter, start: QPointF, end: QPointF, 
                          color: Optional[QColor] = None, width: float = 1.0,
                          glow: bool = False) -> None:
        """Draw line with enhanced visual effects"""
        theme_mgr = get_theme_manager()
        
        # Save painter state
        painter.save()
        
        try:
            if color is None:
                color = theme_mgr.get_color("hud")
            
            # Apply glow if enabled
            if glow and theme_mgr.get_style_param("use_gradients", False):
                # Create glow effect with multiple passes
                glow_color = QColor(color)
                glow_color.setAlpha(min(color.alpha() // 2, 100))
                
                # Draw wider line for glow
                glow_pen = QPen(glow_color)
                glow_pen.setWidthF(width * 2.5)
                painter.setPen(glow_pen)
                painter.drawLine(start, end)
                
                # Draw medium line
                glow_color.setAlpha(min(color.alpha() * 2 // 3, 160))
                glow_pen.setColor(glow_color)
                glow_pen.setWidthF(width * 1.8)
                painter.setPen(glow_pen)
                painter.drawLine(start, end)
            
            # Draw main line
            pen = QPen(color)
            pen.setWidthF(width)
            painter.setPen(pen)
            painter.drawLine(start, end)
            
        finally:
            # Restore painter state
            painter.restore()
    
    @staticmethod
    def draw_enhanced_rect(painter: QPainter, rect: QRectF, 
                          color: Optional[QColor] = None,
                          fill: bool = False, fill_color: Optional[QColor] = None,
                          corner_radius: Optional[float] = None) -> None:
        """Draw rectangle with enhanced visual effects"""
        theme_mgr = get_theme_manager()
        
        # Save painter state
        painter.save()
        
        try:
            if color is None:
                color = theme_mgr.get_color("hud")
                
            if corner_radius is None:
                corner_radius = theme_mgr.get_style_param("corner_radius", 0.0)
            
            # Set up pen for outline
            pen = QPen(color)
            pen.setWidthF(theme_mgr.get_style_param("line_width", 1.0))
            painter.setPen(pen)
            
            # Handle fill if requested
            if fill:
                if fill_color is None:
                    # Create semi-transparent fill color
                    fill_color = QColor(color)
                    fill_color.setAlpha(min(color.alpha() // 3, 80))
                
                painter.setBrush(QBrush(fill_color))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            
            # Draw rectangle with optional rounded corners
            if corner_radius > 0:
                painter.drawRoundedRect(rect, corner_radius, corner_radius)
            else:
                painter.drawRect(rect)
            
        finally:
            # Restore painter state
            painter.restore()
    
    @staticmethod
    def draw_enhanced_ellipse(painter: QPainter, rect: QRectF,
                             color: Optional[QColor] = None,
                             fill: bool = False, fill_color: Optional[QColor] = None,
                             glow: bool = False) -> None:
        """Draw ellipse with enhanced visual effects"""
        theme_mgr = get_theme_manager()
        
        # Save painter state
        painter.save()
        
        try:
            if color is None:
                color = theme_mgr.get_color("hud")
            
            # Apply glow if enabled
            if glow and theme_mgr.get_style_param("use_gradients", False):
                # Create glow effect with multiple passes
                glow_color = QColor(color)
                glow_color.setAlpha(min(color.alpha() // 2, 100))
                
                # Draw wider ellipse for glow
                glow_pen = QPen(glow_color)
                glow_pen.setWidthF(theme_mgr.get_style_param("line_width", 1.0) * 2.5)
                painter.setPen(glow_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(rect)
                
                # Draw medium ellipse
                glow_color.setAlpha(min(color.alpha() * 2 // 3, 160))
                glow_pen.setColor(glow_color)
                glow_pen.setWidthF(theme_mgr.get_style_param("line_width", 1.0) * 1.8)
                painter.setPen(glow_pen)
                painter.drawEllipse(rect)
            
            # Set up pen for outline
            pen = QPen(color)
            pen.setWidthF(theme_mgr.get_style_param("line_width", 1.0))
            painter.setPen(pen)
            
            # Handle fill if requested
            if fill:
                if fill_color is None:
                    # Create semi-transparent fill color
                    fill_color = QColor(color)
                    fill_color.setAlpha(min(color.alpha() // 3, 80))
                
                painter.setBrush(QBrush(fill_color))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            
            # Draw main ellipse
            painter.drawEllipse(rect)
            
        finally:
            # Restore painter state
            painter.restore()
    
    @staticmethod
    def draw_enhanced_path(painter: QPainter, path: QPainterPath,
                          color: Optional[QColor] = None,
                          fill: bool = False, fill_color: Optional[QColor] = None,
                          glow: bool = False) -> None:
        """Draw path with enhanced visual effects"""
        theme_mgr = get_theme_manager()
        
        # Save painter state
        painter.save()
        
        try:
            if color is None:
                color = theme_mgr.get_color("hud")
            
            # Apply glow if enabled
            if glow and theme_mgr.get_style_param("use_gradients", False):
                # Create glow effect with multiple passes
                glow_color = QColor(color)
                glow_color.setAlpha(min(color.alpha() // 2, 100))
                
                # Draw wider path for glow
                glow_pen = QPen(glow_color)
                glow_pen.setWidthF(theme_mgr.get_style_param("line_width", 1.0) * 2.5)
                painter.setPen(glow_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
                
                # Draw medium path
                glow_color.setAlpha(min(color.alpha() * 2 // 3, 160))
                glow_pen.setColor(glow_color)
                glow_pen.setWidthF(theme_mgr.get_style_param("line_width", 1.0) * 1.8)
                painter.setPen(glow_pen)
                painter.drawPath(path)
            
            # Set up pen for outline
            pen = QPen(color)
            pen.setWidthF(theme_mgr.get_style_param("line_width", 1.0))
            painter.setPen(pen)
            
            # Handle fill if requested
            if fill:
                if fill_color is None:
                    # Create semi-transparent fill color
                    fill_color = QColor(color)
                    fill_color.setAlpha(min(color.alpha() // 3, 80))
                
                painter.setBrush(QBrush(fill_color))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            
            # Draw main path
            painter.drawPath(path)
            
        finally:
            # Restore painter state
            painter.restore()
    
    @staticmethod
    def create_gradient_brush(start_color: QColor, end_color: QColor, 
                             vertical: bool = True) -> QBrush:
        """Create a linear gradient brush"""
        gradient = QLinearGradient(0, 0, 0 if vertical else 1, 1 if vertical else 0)
        gradient.setColorAt(0, start_color)
        gradient.setColorAt(1, end_color)
        return QBrush(gradient)
    
    @staticmethod
    def create_radial_gradient_brush(center_color: QColor, edge_color: QColor) -> QBrush:
        """Create a radial gradient brush"""
        gradient = QRadialGradient(0.5, 0.5, 0.5)
        gradient.setColorAt(0, center_color)
        gradient.setColorAt(1, edge_color)
        return QBrush(gradient)
    
    def update_animation_time(self, delta_time: float) -> None:
        """Update animation timers for effects like pulsing"""
        self._pulse_time += delta_time
        self._last_update_time = self._pulse_time
        
        # Keep pulse time within reasonable bounds to avoid float precision issues
        if self._pulse_time > 1000.0:
            self._pulse_time = 0.0
    
    def get_pulse_factor(self, rate: float = 1.0, min_value: float = 0.7, max_value: float = 1.0) -> float:
        """Get current pulse factor for animations based on time"""
        # Calculate pulse factor using sine wave
        import math
        pulse = (math.sin(self._pulse_time * rate) + 1.0) / 2.0  # 0.0 to 1.0
        return min_value + pulse * (max_value - min_value)
    
    def draw_angular_frame(self, painter: QPainter, rect: QRectF, 
                          color: Optional[QColor] = None,
                          line_width: Optional[float] = None,
                          corner_style: str = "angular",
                          glow: bool = False) -> None:
        """Draw modern angular frame with different corner styles"""
        theme_mgr = get_theme_manager()
        
        # Save painter state
        painter.save()
        
        try:
            if color is None:
                color = theme_mgr.get_color("hud")
                
            if line_width is None:
                line_width = theme_mgr.get_style_param("line_width", 1.5)
            
            # Set up pen
            pen = QPen(color)
            pen.setWidthF(line_width)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
            
            # Create path for the frame
            path = QPainterPath()
            
            # Get rect dimensions
            x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
            
            # Corner size (adjust based on rect size)
            corner_size = min(w, h) * 0.1
            
            if corner_style == "angular":
                # Top-left corner
                path.moveTo(x, y + corner_size)
                path.lineTo(x, y)
                path.lineTo(x + corner_size, y)
                
                # Top-right corner
                path.moveTo(x + w - corner_size, y)
                path.lineTo(x + w, y)
                path.lineTo(x + w, y + corner_size)
                
                # Bottom-right corner
                path.moveTo(x + w, y + h - corner_size)
                path.lineTo(x + w, y + h)
                path.lineTo(x + w - corner_size, y + h)
                
                # Bottom-left corner
                path.moveTo(x + corner_size, y + h)
                path.lineTo(x, y + h)
                path.lineTo(x, y + h - corner_size)
                
            elif corner_style == "hexagonal":
                # Calculate hex corner offset
                hex_offset = min(w, h) * 0.15
                
                # Start at top-left
                path.moveTo(x + hex_offset, y)
                path.lineTo(x + w - hex_offset, y)  # Top edge
                path.lineTo(x + w, y + hex_offset)  # Top-right corner
                path.lineTo(x + w, y + h - hex_offset)  # Right edge
                path.lineTo(x + w - hex_offset, y + h)  # Bottom-right corner
                path.lineTo(x + hex_offset, y + h)  # Bottom edge
                path.lineTo(x, y + h - hex_offset)  # Bottom-left corner
                path.lineTo(x, y + hex_offset)  # Left edge
                path.lineTo(x + hex_offset, y)  # Back to start
                
            elif corner_style == "beveled":
                # Calculate bevel size
                bevel = min(w, h) * 0.08
                
                # Start at top-left after bevel
                path.moveTo(x + bevel, y)
                path.lineTo(x + w - bevel, y)  # Top edge
                path.lineTo(x + w, y + bevel)  # Top-right bevel
                path.lineTo(x + w, y + h - bevel)  # Right edge
                path.lineTo(x + w - bevel, y + h)  # Bottom-right bevel
                path.lineTo(x + bevel, y + h)  # Bottom edge
                path.lineTo(x, y + h - bevel)  # Bottom-left bevel
                path.lineTo(x, y + bevel)  # Left edge
                path.lineTo(x + bevel, y)  # Top-left bevel
                
            else:  # Default to rectangular
                path.addRect(rect)
            
            # Draw with glow if requested
            if glow and theme_mgr.get_style_param("use_gradients", False):
                self.draw_enhanced_path(painter, path, color, fill=False, glow=True)
            else:
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
                
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_hexagonal_grid(self, painter: QPainter, center: QPointF, radius: float,
                           color: Optional[QColor] = None, rings: int = 4,
                           rotation: float = 0.0, glow: bool = False) -> None:
        """Draw hexagonal grid pattern for radar displays"""
        theme_mgr = get_theme_manager()
        
        # Save painter state
        painter.save()
        
        try:
            if color is None:
                color = theme_mgr.get_color("grid")
            
            # Set up pen
            pen = QPen(color)
            pen.setWidthF(theme_mgr.get_style_param("line_width", 1.0))
            painter.setPen(pen)
            
            # Calculate hexagon points
            import math
            
            # Rotate the grid if requested
            painter.translate(center)
            painter.rotate(rotation)
            painter.translate(-center.x(), -center.y())
            
            # Draw rings of hexagons
            for ring in range(1, rings + 1):
                ring_radius = (radius / rings) * ring
                
                # Create path for this ring
                path = QPainterPath()
                
                # Calculate points for hexagon
                points = []
                for i in range(6):
                    angle = math.pi / 3.0 * i
                    x = center.x() + ring_radius * math.cos(angle)
                    y = center.y() + ring_radius * math.sin(angle)
                    points.append(QPointF(x, y))
                
                # Create hexagon path
                path.moveTo(points[0])
                for i in range(1, 6):
                    path.lineTo(points[i])
                path.lineTo(points[0])  # Close the path
                
                # Draw with glow if requested
                if glow and theme_mgr.get_style_param("use_gradients", False):
                    # Adjust glow based on ring
                    ring_glow = glow and (ring == rings)  # Only outer ring glows
                    self.draw_enhanced_path(painter, path, color, fill=False, glow=ring_glow)
                else:
                    painter.drawPath(path)
                
                # Draw radial lines for the outermost ring
                if ring == rings:
                    for i in range(6):
                        self.draw_enhanced_line(
                            painter, 
                            center, 
                            points[i], 
                            color=color, 
                            glow=glow
                        )
                
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_data_visualization(self, painter: QPainter, rect: QRectF, 
                              data_points: List[float], 
                              color: Optional[QColor] = None,
                              style: str = "modern",
                              fill: bool = True,
                              glow: bool = False) -> None:
        """Draw data visualization with modern styling"""
        theme_mgr = get_theme_manager()
        
        # Save painter state
        painter.save()
        
        try:
            if color is None:
                color = theme_mgr.get_color("data_primary")
            
            # Ensure we have data
            if not data_points or len(data_points) < 2:
                return
                
            # Create fill color if needed
            fill_color = None
            if fill:
                fill_color = QColor(color)
                fill_color.setAlpha(min(color.alpha() // 3, 80))
            
            # Calculate scaling
            x_step = rect.width() / (len(data_points) - 1)
            y_scale = rect.height() / max(max(data_points), 1.0)
            
            # Create path for the visualization
            path = QPainterPath()
            
            # Start at the first point
            start_x = rect.x()
            start_y = rect.y() + rect.height() - (data_points[0] * y_scale)
            path.moveTo(start_x, start_y)
            
            if style == "modern":
                # Draw smooth curve through points
                for i in range(1, len(data_points)):
                    x = rect.x() + i * x_step
                    y = rect.y() + rect.height() - (data_points[i] * y_scale)
                    
                    # Use quadratic curves for smoother appearance
                    if i < len(data_points) - 1:
                        # Control point is midway between points
                        ctrl_x = x + x_step / 2
                        ctrl_y = rect.y() + rect.height() - (data_points[i+1] * y_scale)
                        path.quadTo(x, y, ctrl_x, ctrl_y)
                    else:
                        # Last point
                        path.lineTo(x, y)
                        
            elif style == "angular":
                # Draw angular lines between points
                for i in range(1, len(data_points)):
                    x = rect.x() + i * x_step
                    y = rect.y() + rect.height() - (data_points[i] * y_scale)
                    path.lineTo(x, y)
                    
            elif style == "stepped":
                # Draw stepped lines (horizontal then vertical)
                for i in range(1, len(data_points)):
                    x = rect.x() + i * x_step
                    prev_y = rect.y() + rect.height() - (data_points[i-1] * y_scale)
                    y = rect.y() + rect.height() - (data_points[i] * y_scale)
                    
                    # Horizontal line to new x, then vertical to new y
                    path.lineTo(x, prev_y)
                    path.lineTo(x, y)
            
            # If filling, complete the path back to the bottom
            if fill:
                # Line to bottom-right corner
                path.lineTo(rect.x() + rect.width(), rect.y() + rect.height())
                # Line to bottom-left corner
                path.lineTo(rect.x(), rect.y() + rect.height())
                # Close the path
                path.closeSubpath()
            
            # Draw with enhanced effects
            self.draw_enhanced_path(
                painter, 
                path, 
                color=color, 
                fill=fill, 
                fill_color=fill_color,
                glow=glow
            )
            
            # Draw data points as small circles for emphasis
            if style == "modern" or style == "angular":
                point_radius = 2.0
                for i in range(len(data_points)):
                    x = rect.x() + i * x_step
                    y = rect.y() + rect.height() - (data_points[i] * y_scale)
                    point_rect = QRectF(
                        x - point_radius, 
                        y - point_radius,
                        point_radius * 2,
                        point_radius * 2
                    )
                    self.draw_enhanced_ellipse(
                        painter, 
                        point_rect, 
                        color=color, 
                        fill=True,
                        glow=False
                    )
                
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_layered_background(self, painter: QPainter, rect: QRectF,
                              base_color: Optional[QColor] = None,
                              grid_color: Optional[QColor] = None,
                              grid_type: str = "hex") -> None:
        """Draw sophisticated background with hexagonal or triangular grid"""
        theme_mgr = get_theme_manager()
        
        # Save painter state
        painter.save()
        
        try:
            if base_color is None:
                base_color = theme_mgr.get_color("background")
                
            if grid_color is None:
                grid_color = theme_mgr.get_color("grid")
            
            # Fill background
            painter.fillRect(rect, base_color)
            
            # Draw grid based on type
            if grid_type == "hex":
                # Calculate center and radius for hexagonal grid
                center = QPointF(rect.center())
                radius = max(rect.width(), rect.height()) * 0.5
                
                # Draw hexagonal grid
                self.draw_hexagonal_grid(
                    painter, 
                    center, 
                    radius, 
                    color=grid_color,
                    rings=5,
                    glow=False
                )
                
            elif grid_type == "triangular":
                # Draw triangular grid
                import math
                
                # Calculate grid spacing
                spacing = min(rect.width(), rect.height()) / 15
                
                # Set up pen
                pen = QPen(grid_color)
                pen.setWidthF(theme_mgr.get_style_param("line_width", 0.5))
                painter.setPen(pen)
                
                # Draw horizontal lines
                for y in range(0, int(rect.height()), int(spacing)):
                    painter.drawLine(
                        QPointF(rect.left(), rect.top() + y),
                        QPointF(rect.right(), rect.top() + y)
                    )
                
                # Draw diagonal lines (positive slope)
                for x in range(0, int(rect.width() + rect.height()), int(spacing)):
                    painter.drawLine(
                        QPointF(rect.left() + x, rect.top()),
                        QPointF(rect.left(), rect.top() + x)
                    )
                
                # Draw diagonal lines (negative slope)
                for x in range(0, int(rect.width() + rect.height()), int(spacing)):
                    painter.drawLine(
                        QPointF(rect.left() + x, rect.top()),
                        QPointF(rect.left() + rect.width(), rect.top() + rect.height() - x)
                    )
                
            elif grid_type == "radial":
                # Draw radial grid
                center = QPointF(rect.center())
                max_radius = max(rect.width(), rect.height()) * 0.5
                
                # Set up pen
                pen = QPen(grid_color)
                pen.setWidthF(theme_mgr.get_style_param("line_width", 0.5))
                painter.setPen(pen)
                
                # Draw concentric circles
                rings = 5
                for i in range(1, rings + 1):
                    radius = (max_radius / rings) * i
                    painter.drawEllipse(center, radius, radius)
                
                # Draw radial lines
                import math
                num_lines = 12
                for i in range(num_lines):
                    angle = 2 * math.pi * i / num_lines
                    end_x = center.x() + max_radius * math.cos(angle)
                    end_y = center.y() + max_radius * math.sin(angle)
                    painter.drawLine(center, QPointF(end_x, end_y))
                
        finally:
            # Restore painter state
            painter.restore()

"""
Enhanced visual effects utilities for advanced display rendering
"""
from PyQt6.QtCore import QPointF, QRectF, Qt, QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QLinearGradient, QRadialGradient, QFont
from typing import Optional, Tuple, List, Dict, Any
from .effects import VisualEffects
from .enhanced_theme_manager import get_enhanced_theme_manager
from Utils.logger.sys_logger import get_logger
import math
import time

logger = get_logger()

class EnhancedVisualEffects(VisualEffects):
    """Enhanced visual effects for modern displays with 3D and holographic capabilities"""
    
    def __init__(self):
        """Initialize enhanced visual effects"""
        super().__init__()
        self._theme_manager = get_enhanced_theme_manager()
        self._pulse_time = 0.0
        self._last_update_time = time.time()
        
    def update_animation_time(self, delta_time: float) -> None:
        """Update animation timers"""
        # Apply animation speed
        effective_delta = delta_time * self._theme_manager.get_animation_speed()
        
        # Update pulse time
        self._pulse_time += effective_delta
        self._last_update_time = time.time()
        
        # Keep pulse time within reasonable bounds
        if self._pulse_time > 1000.0:
            self._pulse_time = 0.0
            
    def get_pulse_factor(self, rate: float = 1.0, min_value: float = 0.7, max_value: float = 1.0) -> float:
        """Get current pulse factor for animations"""
        # Check if pulse effects are enabled
        if not self._theme_manager.get_style_param("use_pulse_effects", False):
            return 1.0
            
        # Apply theme pulse rate
        theme_rate = self._theme_manager.get_style_param("pulse_rate", 1.0)
        effective_rate = rate * theme_rate
        
        # Calculate pulse using sine wave
        pulse = (math.sin(self._pulse_time * effective_rate) + 1.0) / 2.0
        return min_value + pulse * (max_value - min_value)
    
    def draw_enhanced_text(self, painter: QPainter, rect: QRectF, flags: int, text: str, 
                          glow: bool = False, glow_color: Optional[QColor] = None,
                          shadow: bool = False, depth: float = 0.0) -> None:
        """Draw text with enhanced visual effects including depth"""
        # Save painter state
        painter.save()
        
        try:
            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            use_shadows = self._theme_manager.get_style_param("use_shadows", False)
            use_glow = self._theme_manager.get_style_param("use_glow", False)
            glow_intensity = self._theme_manager.get_style_param("glow_intensity", 0.5)
            
            # Apply shadow if enabled
            if shadow and use_shadows:
                shadow_offset_x = self._theme_manager.get_style_param("shadow_offset_x", 1.0)
                shadow_offset_y = self._theme_manager.get_style_param("shadow_offset_y", 1.0)
                shadow_blur = self._theme_manager.get_style_param("shadow_blur", 3.0)
                
                # Apply depth effect to shadow
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    shadow_offset_x *= (1.0 + depth * 0.5)
                    shadow_offset_y *= (1.0 + depth * 0.5)
                
                # Create shadow color
                shadow_color = QColor(0, 0, 0, 100)
                
                # Draw shadow with multiple passes for blur effect
                for i in range(int(shadow_blur)):
                    blur_factor = i / max(1, shadow_blur - 1)
                    offset_x = shadow_offset_x * (1.0 - blur_factor * 0.5)
                    offset_y = shadow_offset_y * (1.0 - blur_factor * 0.5)
                    
                    shadow_rect = QRectF(
                        rect.x() + offset_x,
                        rect.y() + offset_y,
                        rect.width(),
                        rect.height()
                    )
                    
                    # Adjust alpha for each pass
                    pass_color = QColor(shadow_color)
                    pass_color.setAlpha(int(shadow_color.alpha() * (1.0 - blur_factor * 0.7)))
                    
                    painter.setPen(pass_color)
                    painter.drawText(shadow_rect, flags, text)
            
            # Apply glow if enabled
            if glow and use_glow and use_gradients:
                if glow_color is None:
                    glow_color = self._theme_manager.get_color("hud")
                
                # Apply depth effect to glow
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    glow_color = self._theme_manager.create_color_with_depth("hud", depth)
                
                # Apply pulse effect to glow
                if self._theme_manager.get_style_param("use_pulse_effects", False):
                    pulse_factor = self.get_pulse_factor(
                        rate=self._theme_manager.get_style_param("pulse_rate", 1.0),
                        min_value=0.7,
                        max_value=1.0
                    )
                    
                    # Adjust glow intensity with pulse
                    effective_intensity = glow_intensity * pulse_factor
                else:
                    effective_intensity = glow_intensity
                
                # Create glow color with adjusted intensity
                glow_alpha = min(glow_color.alpha(), int(120 * effective_intensity))
                glow_effect_color = QColor(glow_color)
                glow_effect_color.setAlpha(glow_alpha)
                
                # Draw glow with multiple passes
                for offset in [0.8, 0.6, 0.4, 0.2]:
                    pass_color = QColor(glow_effect_color)
                    pass_color.setAlpha(int(glow_effect_color.alpha() * offset))
                    painter.setPen(pass_color)
                    painter.drawText(rect, flags, text)
            
            # Draw main text
            if glow_color is not None:
                painter.setPen(glow_color)
            else:
                # Apply depth effect to text color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    painter.setPen(self._theme_manager.create_color_with_depth("hud", depth))
                else:
                    painter.setPen(self._theme_manager.get_color("hud"))
            
            painter.drawText(rect, flags, text)
            
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_enhanced_line(self, painter: QPainter, start: QPointF, end: QPointF, 
                          color: Optional[QColor] = None, width: float = 1.0,
                          glow: bool = False, depth: float = 0.0) -> None:
        """Draw line with enhanced visual effects including depth"""
        # Save painter state
        painter.save()
        
        try:
            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            use_glow = self._theme_manager.get_style_param("use_glow", False)
            glow_intensity = self._theme_manager.get_style_param("glow_intensity", 0.5)
            
            if color is None:
                # Apply depth effect to line color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth("hud", depth)
                else:
                    color = self._theme_manager.get_color("hud")
            
            # Apply glow if enabled
            if glow and use_glow and use_gradients:
                # Apply pulse effect to glow
                if self._theme_manager.get_style_param("use_pulse_effects", False):
                    pulse_factor = self.get_pulse_factor(
                        rate=self._theme_manager.get_style_param("pulse_rate", 1.0),
                        min_value=0.7,
                        max_value=1.0
                    )
                    
                    # Adjust glow intensity with pulse
                    effective_intensity = glow_intensity * pulse_factor
                else:
                    effective_intensity = glow_intensity
                
                # Create glow color
                glow_color = QColor(color)
                glow_color.setAlpha(min(color.alpha() // 2, int(100 * effective_intensity)))
                
                # Draw wider line for glow
                glow_pen = QPen(glow_color)
                glow_pen.setWidthF(width * 2.5)
                painter.setPen(glow_pen)
                painter.drawLine(start, end)
                
                # Draw medium line
                glow_color.setAlpha(min(color.alpha() * 2 // 3, int(160 * effective_intensity)))
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
    
    def draw_enhanced_rect(self, painter: QPainter, rect: QRectF, 
                          color: Optional[QColor] = None,
                          fill: bool = False, fill_color: Optional[QColor] = None,
                          corner_radius: Optional[float] = None,
                          glow: bool = False, depth: float = 0.0) -> None:
        """Draw rectangle with enhanced visual effects including depth"""
        # Save painter state
        painter.save()
        
        try:
            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            use_glow = self._theme_manager.get_style_param("use_glow", False)
            glow_intensity = self._theme_manager.get_style_param("glow_intensity", 0.5)
            
            if color is None:
                # Apply depth effect to rect color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth("hud", depth)
                else:
                    color = self._theme_manager.get_color("hud")
                
            if corner_radius is None:
                corner_radius = self._theme_manager.get_style_param("corner_radius", 0.0)
            
            # Apply glow if enabled
            if glow and use_glow and use_gradients:
                # Apply pulse effect to glow
                if self._theme_manager.get_style_param("use_pulse_effects", False):
                    pulse_factor = self.get_pulse_factor(
                        rate=self._theme_manager.get_style_param("pulse_rate", 1.0),
                        min_value=0.7,
                        max_value=1.0
                    )
                    
                    # Adjust glow intensity with pulse
                    effective_intensity = glow_intensity * pulse_factor
                else:
                    effective_intensity = glow_intensity
                
                # Create glow color
                glow_color = QColor(color)
                glow_color.setAlpha(min(color.alpha() // 2, int(100 * effective_intensity)))
                
                # Draw glow with multiple passes
                for i in range(3):
                    glow_factor = (3 - i) / 3.0
                    glow_width = self._theme_manager.get_style_param("line_width", 1.0) * (1.0 + glow_factor * 2.0)
                    
                    # Adjust alpha for each pass
                    pass_color = QColor(glow_color)
                    pass_color.setAlpha(int(glow_color.alpha() * glow_factor))
                    
                    # Draw glow rect
                    glow_pen = QPen(pass_color)
                    glow_pen.setWidthF(glow_width)
                    painter.setPen(glow_pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    
                    if corner_radius > 0:
                        painter.drawRoundedRect(rect, corner_radius, corner_radius)
                    else:
                        painter.drawRect(rect)
            
            # Set up pen for outline
            pen = QPen(color)
            pen.setWidthF(self._theme_manager.get_style_param("line_width", 1.0))
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
    
    def draw_enhanced_ellipse(self, painter: QPainter, rect: QRectF,
                             color: Optional[QColor] = None,
                             fill: bool = False, fill_color: Optional[QColor] = None,
                             glow: bool = False, depth: float = 0.0) -> None:
        """Draw ellipse with enhanced visual effects including depth"""
        # Save painter state
        painter.save()
        
        try:
            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            use_glow = self._theme_manager.get_style_param("use_glow", False)
            glow_intensity = self._theme_manager.get_style_param("glow_intensity", 0.5)
            
            if color is None:
                # Apply depth effect to ellipse color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth("hud", depth)
                else:
                    color = self._theme_manager.get_color("hud")
            
            # Apply glow if enabled
            if glow and use_glow and use_gradients:
                # Apply pulse effect to glow
                if self._theme_manager.get_style_param("use_pulse_effects", False):
                    pulse_factor = self.get_pulse_factor(
                        rate=self._theme_manager.get_style_param("pulse_rate", 1.0),
                        min_value=0.7,
                        max_value=1.0
                    )
                    
                    # Adjust glow intensity with pulse
                    effective_intensity = glow_intensity * pulse_factor
                else:
                    effective_intensity = glow_intensity
                
                # Create glow color
                glow_color = QColor(color)
                glow_color.setAlpha(min(color.alpha() // 2, int(100 * effective_intensity)))
                
                # Draw glow with multiple passes
                for i in range(3):
                    glow_factor = (3 - i) / 3.0
                    glow_width = self._theme_manager.get_style_param("line_width", 1.0) * (1.0 + glow_factor * 2.0)
                    
                    # Adjust alpha for each pass
                    pass_color = QColor(glow_color)
                    pass_color.setAlpha(int(glow_color.alpha() * glow_factor))
                    
                    # Draw glow ellipse
                    glow_pen = QPen(pass_color)
                    glow_pen.setWidthF(glow_width)
                    painter.setPen(glow_pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawEllipse(rect)
            
            # Set up pen for outline
            pen = QPen(color)
            pen.setWidthF(self._theme_manager.get_style_param("line_width", 1.0))
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
    
    def draw_enhanced_path(self, painter: QPainter, path: QPainterPath,
                          color: Optional[QColor] = None,
                          fill: bool = False, fill_color: Optional[QColor] = None,
                          glow: bool = False, depth: float = 0.0) -> None:
        """Draw path with enhanced visual effects including depth"""
        # Save painter state
        painter.save()
        
        try:
            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            use_glow = self._theme_manager.get_style_param("use_glow", False)
            glow_intensity = self._theme_manager.get_style_param("glow_intensity", 0.5)
            
            if color is None:
                # Apply depth effect to path color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth("hud", depth)
                else:
                    color = self._theme_manager.get_color("hud")
            
            # Apply glow if enabled
            if glow and use_glow and use_gradients:
                # Apply pulse effect to glow
                if self._theme_manager.get_style_param("use_pulse_effects", False):
                    pulse_factor = self.get_pulse_factor(
                        rate=self._theme_manager.get_style_param("pulse_rate", 1.0),
                        min_value=0.7,
                        max_value=1.0
                    )
                    
                    # Adjust glow intensity with pulse
                    effective_intensity = glow_intensity * pulse_factor
                else:
                    effective_intensity = glow_intensity
                
                # Create glow color
                glow_color = QColor(color)
                glow_color.setAlpha(min(color.alpha() // 2, int(100 * effective_intensity)))
                
                # Draw glow with multiple passes
                for i in range(3):
                    glow_factor = (3 - i) / 3.0
                    glow_width = self._theme_manager.get_style_param("line_width", 1.0) * (1.0 + glow_factor * 2.0)
                    
                    # Adjust alpha for each pass
                    pass_color = QColor(glow_color)
                    pass_color.setAlpha(int(glow_color.alpha() * glow_factor))
                    
                    # Draw glow path
                    glow_pen = QPen(pass_color)
                    glow_pen.setWidthF(glow_width)
                    painter.setPen(glow_pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(path)
            
            # Set up pen for outline
            pen = QPen(color)
            pen.setWidthF(self._theme_manager.get_style_param("line_width", 1.0))
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
    
    def draw_angular_frame(self, painter: QPainter, rect: QRectF, 
                          color: Optional[QColor] = None,
                          line_width: Optional[float] = None,
                          corner_style: str = "angular",
                          glow: bool = False, depth: float = 0.0) -> None:
        """Draw modern angular frame with different corner styles and depth effects"""
        # Save painter state
        painter.save()
        
        try:
            # Get theme parameters
            use_angular_design = self._theme_manager.get_style_param("use_angular_design", False)
            
            # Override corner style if angular design is disabled
            if not use_angular_design:
                corner_style = "rectangular"
            
            if color is None:
                # Apply depth effect to frame color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth("hud", depth)
                else:
                    color = self._theme_manager.get_color("hud")
                
            if line_width is None:
                line_width = self._theme_manager.get_style_param("line_width", 1.5)
            
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
            if glow:
                self.draw_enhanced_path(painter, path, color, fill=False, glow=True, depth=depth)
            else:
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
                
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_hexagonal_grid(self, painter: QPainter, center: QPointF, radius: float,
                           color: Optional[QColor] = None, rings: int = 4,
                           rotation: float = 0.0, glow: bool = False, depth: float = 0.0) -> None:
        """Draw hexagonal grid pattern for radar displays with depth effects"""
        # Save painter state
        painter.save()
        
        try:
            # Get grid type from theme
            grid_type = self._theme_manager.get_style_param("grid_type", "hexagonal")
            
            # Override grid type if not hexagonal
            if grid_type != "hexagonal":
                if grid_type == "radial":
                    self.draw_radial_grid(painter, center, radius, color, rings, glow, depth)
                else:
                    self.draw_standard_grid(painter, center, radius, color, glow, depth)
                return
            
            if color is None:
                # Apply depth effect to grid color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth("grid", depth)
                else:
                    color = self._theme_manager.get_color("grid")
            
            # Rotate the grid if requested
            painter.translate(center.x(), center.y())
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
                ring_glow = glow and (ring == rings)  # Only outer ring glows
                self.draw_enhanced_path(painter, path, color, fill=False, glow=ring_glow, depth=depth)
                
                # Draw radial lines for the outermost ring
                if ring == rings:
                    for i in range(6):
                        self.draw_enhanced_line(
                            painter, 
                            center, 
                            points[i], 
                            color=color, 
                            glow=glow,
                            depth=depth
                        )
                
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_radial_grid(self, painter: QPainter, center: QPointF, radius: float,
                        color: Optional[QColor] = None, rings: int = 4,
                        glow: bool = False, depth: float = 0.0) -> None:
        """Draw radial grid pattern for radar displays with depth effects"""
        # Save painter state
        painter.save()
        
        try:
            if color is None:
                # Apply depth effect to grid color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth("grid", depth)
                else:
                    color = self._theme_manager.get_color("grid")
            
            # Draw concentric circles
            for ring in range(1, rings + 1):
                ring_radius = (radius / rings) * ring
                
                # Create ellipse rect
                ellipse_rect = QRectF(
                    center.x() - ring_radius,
                    center.y() - ring_radius,
                    ring_radius * 2,
                    ring_radius * 2
                )
                
                # Draw with glow if requested
                ring_glow = glow and (ring == rings)  # Only outer ring glows
                self.draw_enhanced_ellipse(
                    painter, 
                    ellipse_rect, 
                    color, 
                    fill=False, 
                    glow=ring_glow,
                    depth=depth
                )
            
            # Draw radial lines
            num_lines = 12
            for i in range(num_lines):
                angle = 2 * math.pi * i / num_lines
                end_x = center.x() + radius * math.cos(angle)
                end_y = center.y() + radius * math.sin(angle)
                
                self.draw_enhanced_line(
                    painter,
                    center,
                    QPointF(end_x, end_y),
                    color=color,
                    glow=glow,
                    depth=depth
                )
                
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_standard_grid(self, painter: QPainter, center: QPointF, radius: float,
                          color: Optional[QColor] = None, glow: bool = False, depth: float = 0.0) -> None:
        """Draw standard grid pattern for radar displays with depth effects"""
        # Save painter state
        painter.save()
        
        try:
            if color is None:
                # Apply depth effect to grid color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth("grid", depth)
                else:
                    color = self._theme_manager.get_color("grid")
            
            # Draw horizontal and vertical lines
            line_spacing = radius / 5
            
            # Draw horizontal lines
            for i in range(-5, 6):
                y = center.y() + i * line_spacing
                
                self.draw_enhanced_line(
                    painter,
                    QPointF(center.x() - radius, y),
                    QPointF(center.x() + radius, y),
                    color=color,
                    glow=glow and i == 0,  # Only center line glows
                    depth=depth
                )
            
            # Draw vertical lines
            for i in range(-5, 6):
                x = center.x() + i * line_spacing
                
                self.draw_enhanced_line(
                    painter,
                    QPointF(x, center.y() - radius),
                    QPointF(x, center.y() + radius),
                    color=color,
                    glow=glow and i == 0,  # Only center line glows
                    depth=depth
                )
                
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_layered_background(self, painter: QPainter, rect: QRectF,
                              base_color: Optional[QColor] = None,
                              grid_color: Optional[QColor] = None,
                              grid_type: str = "hexagonal",
                              depth: float = 0.0) -> None:
        """Draw sophisticated background with grid and depth effects"""
        # Save painter state
        painter.save()
        
        try:
            if base_color is None:
                # Apply depth effect to background color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    base_color = self._theme_manager.create_color_with_depth("background", depth)
                else:
                    base_color = self._theme_manager.get_color("background")
                
            if grid_color is None:
                # Apply depth effect to grid color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    grid_color = self._theme_manager.create_color_with_depth("grid", depth)
                else:
                    grid_color = self._theme_manager.get_color("grid")
            
            # Fill background
            painter.fillRect(rect, base_color)
            
            # Draw grid based on type
            if grid_type == "hexagonal":
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
                    glow=False,
                    depth=depth
                )
                
            elif grid_type == "radial":
                # Calculate center and radius for radial grid
                center = QPointF(rect.center())
                radius = max(rect.width(), rect.height()) * 0.5
                
                # Draw radial grid
                self.draw_radial_grid(
                    painter, 
                    center, 
                    radius, 
                    color=grid_color,
                    rings=5,
                    glow=False,
                    depth=depth
                )
                
            else:  # Default to standard grid
                # Calculate center and radius for standard grid
                center = QPointF(rect.center())
                radius = max(rect.width(), rect.height()) * 0.5
                
                # Draw standard grid
                self.draw_standard_grid(
                    painter, 
                    center, 
                    radius, 
                    color=grid_color,
                    glow=False,
                    depth=depth
                )
                
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_scan_line(self, painter: QPainter, center: QPointF, radius: float,
                      angle: float, color: Optional[QColor] = None,
                      width: float = 2.0, depth: float = 0.0) -> None:
        """Draw radar scan line with enhanced visuals and depth effects"""
        # Save painter state
        painter.save()
        
        try:
            if color is None:
                # Apply depth effect to scan line color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth("data_primary", depth)
                else:
                    color = self._theme_manager.get_color("data_primary")
            
            # Draw scan arc (trailing effect) only - removed the thin line
            # Calculate arc angles
            start_angle = (angle - 30) % 360
            span_angle = 30
            
            # Create arc path
            path = QPainterPath()
            path.moveTo(center)
            
            # Add arc
            arc_rect = QRectF(
                center.x() - radius,
                center.y() - radius,
                radius * 2,
                radius * 2
            )
            
            # Convert to Qt angles (16th of a degree, clockwise from 3 o'clock)
            qt_start_angle = (90 - start_angle) * 16
            qt_span_angle = -span_angle * 16  # Negative for clockwise
            
            path.arcTo(arc_rect, qt_start_angle / 16, qt_span_angle / 16)
            path.lineTo(center)
            
            # Create gradient fill
            gradient = QRadialGradient(center, radius)
            
            # Create transparent version of color
            transparent_color = QColor(color)
            transparent_color.setAlpha(0)
            
            # Set gradient stops
            gradient.setColorAt(0, color)
            gradient.setColorAt(1, transparent_color)
            
            # Draw arc with gradient fill
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawPath(path)
            
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_tactical_overlay(self, painter: QPainter, rect: QRectF,
                            threat_level: int, threat_direction: float,
                            color: Optional[QColor] = None, depth: float = 0.0) -> None:
        """Draw tactical overlay with threat indicators and depth effects"""
        # Save painter state
        painter.save()
        
        try:
            # Determine color based on threat level
            if color is None:
                if threat_level >= 8:
                    color_name = "critical"
                elif threat_level >= 5:
                    color_name = "warning"
                elif threat_level >= 3:
                    color_name = "data_tertiary"
                else:
                    color_name = "data_primary"
                
                # Apply depth effect to color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth(color_name, depth)
                else:
                    color = self._theme_manager.get_color(color_name)
            
            # Draw tactical frame
            self.draw_angular_frame(
                painter,
                rect,
                color=color,
                corner_style="angular",
                glow=True,
                depth=depth
            )
            
            # Draw threat direction indicator
            center_x = rect.center().x()
            top_y = rect.top() + 20
            
            # Create direction indicator
            indicator_radius = min(rect.width(), rect.height()) * 0.2
            indicator_center = QPointF(center_x, top_y + indicator_radius)
            
            # Draw direction circle
            indicator_rect = QRectF(
                indicator_center.x() - indicator_radius,
                indicator_center.y() - indicator_radius,
                indicator_radius * 2,
                indicator_radius * 2
            )
            
            self.draw_enhanced_ellipse(
                painter,
                indicator_rect,
                color=color,
                fill=False,
                glow=True,
                depth=depth
            )
            
            # Draw direction line
            rad_angle = math.radians(threat_direction)
            line_end_x = indicator_center.x() + indicator_radius * 0.8 * math.cos(rad_angle)
            line_end_y = indicator_center.y() + indicator_radius * 0.8 * math.sin(rad_angle)
            
            self.draw_enhanced_line(
                painter,
                indicator_center,
                QPointF(line_end_x, line_end_y),
                color=color,
                width=2.0,
                glow=True,
                depth=depth
            )
            
            # Draw threat level text
            text_rect = QRectF(
                rect.left() + 20,
                rect.top() + 20,
                rect.width() - 40,
                30
            )
            
            self.draw_enhanced_text(
                painter,
                text_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"THREAT LEVEL: {threat_level}",
                glow=True,
                glow_color=color,
                shadow=True,
                depth=depth
            )
            
            # Draw tactical data
            data_rect = QRectF(
                rect.left() + 20,
                rect.bottom() - 50,
                rect.width() - 40,
                30
            )
            
            self.draw_enhanced_text(
                painter,
                data_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"DIR: {int(threat_direction)}°",
                glow=True,
                glow_color=color,
                shadow=True,
                depth=depth
            )
            
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_startup_animation(self, painter: QPainter, rect: QRectF,
                             progress: float, color: Optional[QColor] = None,
                             glow: bool = True, depth: float = 0.0) -> None:
        """Draw startup animation with holographic effects"""
        # Save painter state
        painter.save()
        
        try:
            if color is None:
                # Apply depth effect to color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth("hud", depth)
                else:
                    color = self._theme_manager.get_color("hud")
            
            # Draw background overlay
            overlay_color = QColor(0, 0, 0, int(255 * (1.0 - progress)))
            painter.fillRect(rect, overlay_color)
            
            # Draw scan line effect
            scan_y = rect.y() + rect.height() * progress
            
            scan_color = QColor(color)
            scan_color.setAlpha(150)
            
            scan_rect = QRectF(rect.x(), scan_y - 2, rect.width(), 4)
            painter.fillRect(scan_rect, scan_color)
            
            # Draw glow effect around scan line
            if glow:
                glow_color = QColor(color)
                glow_color.setAlpha(80)
                
                glow_rect = QRectF(rect.x(), scan_y - 10, rect.width(), 20)
                
                gradient = QLinearGradient(0, glow_rect.top(), 0, glow_rect.bottom())
                gradient.setColorAt(0, QColor(0, 0, 0, 0))
                gradient.setColorAt(0.5, glow_color)
                gradient.setColorAt(1, QColor(0, 0, 0, 0))
                
                painter.fillRect(glow_rect, gradient)
            
            # Draw grid pattern that appears with progress
            grid_spacing = 40
            grid_color = QColor(color)
            grid_color.setAlpha(int(80 * progress))
            
            pen = QPen(grid_color)
            pen.setWidthF(1.0)
            painter.setPen(pen)
            
            # Draw horizontal grid lines
            for y in range(0, int(rect.height()), grid_spacing):
                if y < scan_y:  # Only draw grid below scan line
                    painter.drawLine(
                        QPointF(rect.x(), rect.y() + y),
                        QPointF(rect.x() + rect.width(), rect.y() + y)
                    )
            
            # Draw vertical grid lines
            for x in range(0, int(rect.width()), grid_spacing):
                if x < rect.width() * progress:  # Gradually reveal vertical lines
                    painter.drawLine(
                        QPointF(rect.x() + x, rect.y()),
                        QPointF(rect.x() + x, rect.y() + rect.height())
                    )
            
            # Draw angular corners that appear with progress
            if progress > 0.3:
                corner_progress = min(1.0, (progress - 0.3) / 0.7)
                corner_size = 40 * corner_progress
                
                corner_color = QColor(color)
                corner_color.setAlpha(int(200 * corner_progress))
                
                pen = QPen(corner_color)
                pen.setWidthF(2.0)
                painter.setPen(pen)
                
                # Top-left corner
                painter.drawLine(
                    QPointF(rect.x(), rect.y() + corner_size),
                    QPointF(rect.x(), rect.y())
                )
                painter.drawLine(
                    QPointF(rect.x(), rect.y()),
                    QPointF(rect.x() + corner_size, rect.y())
                )
                
                # Top-right corner
                painter.drawLine(
                    QPointF(rect.x() + rect.width() - corner_size, rect.y()),
                    QPointF(rect.x() + rect.width(), rect.y())
                )
                painter.drawLine(
                    QPointF(rect.x() + rect.width(), rect.y()),
                    QPointF(rect.x() + rect.width(), rect.y() + corner_size)
                )
                
                # Bottom-right corner
                painter.drawLine(
                    QPointF(rect.x() + rect.width(), rect.y() + rect.height() - corner_size),
                    QPointF(rect.x() + rect.width(), rect.y() + rect.height())
                )
                painter.drawLine(
                    QPointF(rect.x() + rect.width(), rect.y() + rect.height()),
                    QPointF(rect.x() + rect.width() - corner_size, rect.y() + rect.height())
                )
                
                # Bottom-left corner
                painter.drawLine(
                    QPointF(rect.x() + corner_size, rect.y() + rect.height()),
                    QPointF(rect.x(), rect.y() + rect.height())
                )
                painter.drawLine(
                    QPointF(rect.x(), rect.y() + rect.height()),
                    QPointF(rect.x(), rect.y() + rect.height() - corner_size)
                )
        
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_rect(self, painter: QPainter, rect: QRectF, 
                 color: Optional[QColor] = None,
                 fill: bool = False, fill_color: Optional[QColor] = None,
                 corner_radius: float = 0.0, glow: bool = False, depth: float = 0.0) -> None:
        """Draw rectangle with enhanced visual effects including depth"""
        # Save painter state
        painter.save()
        
        try:
            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            use_glow = self._theme_manager.get_style_param("use_glow", False)
            glow_intensity = self._theme_manager.get_style_param("glow_intensity", 0.5)
            
            if color is None:
                # Apply depth effect to rect color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth("hud", depth)
                else:
                    color = self._theme_manager.get_color("hud")
            
            # Apply glow if enabled
            if glow and use_glow and use_gradients:
                # Apply pulse effect to glow
                if self._theme_manager.get_style_param("use_pulse_effects", False):
                    pulse_factor = self.get_pulse_factor(
                        rate=self._theme_manager.get_style_param("pulse_rate", 1.0),
                        min_value=0.7,
                        max_value=1.0
                    )
                    
                    # Adjust glow intensity with pulse
                    effective_intensity = glow_intensity * pulse_factor
                else:
                    effective_intensity = glow_intensity
                
                # Create glow color
                glow_color = QColor(color)
                glow_color.setAlpha(min(color.alpha() // 2, int(100 * effective_intensity)))
                
                # Draw glow with multiple passes
                for i in range(3):
                    glow_factor = (3 - i) / 3.0
                    glow_width = self._theme_manager.get_style_param("line_width", 1.0) * (1.0 + glow_factor * 2.0)
                    
                    # Adjust alpha for each pass
                    pass_color = QColor(glow_color)
                    pass_color.setAlpha(int(glow_color.alpha() * glow_factor))
                    
                    # Draw glow rect
                    glow_pen = QPen(pass_color)
                    glow_pen.setWidthF(glow_width)
                    painter.setPen(glow_pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    
                    if corner_radius > 0:
                        painter.drawRoundedRect(rect, corner_radius, corner_radius)
                    else:
                        painter.drawRect(rect)
            
            # Set up pen for outline
            pen = QPen(color)
            pen.setWidthF(self._theme_manager.get_style_param("line_width", 1.0))
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
    
    def draw_targeting_grid(self, painter: QPainter, center: QPointF, radius: float,
                          color: Optional[QColor] = None, glow: bool = False,
                          depth: float = 0.0) -> None:
        """Draw targeting grid with holographic effects"""
        # Save painter state
        painter.save()
        
        try:
            if color is None:
                # Apply depth effect to grid color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth("grid", depth)
                else:
                    color = self._theme_manager.get_color("grid")
            
            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            use_glow = self._theme_manager.get_style_param("use_glow", False)
            
            # Draw concentric circles
            for i in range(1, 4):
                ring_radius = radius * i / 3
                
                # Create ellipse rect
                ring_rect = QRectF(
                    center.x() - ring_radius,
                    center.y() - ring_radius,
                    ring_radius * 2,
                    ring_radius * 2
                )
                
                # Draw ring with glow
                self.draw_enhanced_ellipse(
                    painter,
                    ring_rect,
                    color=color,
                    fill=False,
                    glow=glow and use_glow and i == 3,  # Only outer ring glows
                    depth=depth
                )
            
            # Draw crosshairs
            # Horizontal line
            self.draw_enhanced_line(
                painter,
                QPointF(center.x() - radius, center.y()),
                QPointF(center.x() + radius, center.y()),
                color=color,
                width=1.0,
                glow=glow and use_glow,
                depth=depth
            )
            
            # Vertical line
            self.draw_enhanced_line(
                painter,
                QPointF(center.x(), center.y() - radius),
                QPointF(center.x(), center.y() + radius),
                color=color,
                width=1.0,
                glow=glow and use_glow,
                depth=depth
            )
            
            # Draw diagonal lines
            # Top-left to bottom-right
            self.draw_enhanced_line(
                painter,
                QPointF(center.x() - radius * 0.7, center.y() - radius * 0.7),
                QPointF(center.x() + radius * 0.7, center.y() + radius * 0.7),
                color=color,
                width=1.0,
                glow=False,
                depth=depth
            )
            
            # Top-right to bottom-left
            self.draw_enhanced_line(
                painter,
                QPointF(center.x() + radius * 0.7, center.y() - radius * 0.7),
                QPointF(center.x() - radius * 0.7, center.y() + radius * 0.7),
                color=color,
                width=1.0,
                glow=False,
                depth=depth
            )
            
            # Draw angle markers
            for angle in range(0, 360, 30):
                # Calculate marker position
                rad_angle = math.radians(angle)
                marker_x = center.x() + radius * 0.9 * math.cos(rad_angle)
                marker_y = center.y() + radius * 0.9 * math.sin(rad_angle)
                
                # Draw marker
                marker_size = 3.0
                marker_rect = QRectF(
                    marker_x - marker_size,
                    marker_y - marker_size,
                    marker_size * 2,
                    marker_size * 2
                )
                
                self.draw_enhanced_ellipse(
                    painter,
                    marker_rect,
                    color=color,
                    fill=True,
                    glow=False,
                    depth=depth
                )
                
                # Draw angle label for major angles
                if angle % 90 == 0:
                    # Calculate label position
                    label_x = center.x() + radius * 0.75 * math.cos(rad_angle)
                    label_y = center.y() + radius * 0.75 * math.sin(rad_angle)
                    
                    # Create label rect
                    label_rect = QRectF(
                        label_x - 15,
                        label_y - 10,
                        30,
                        20
                    )
                    
                    # Draw label
                    self.draw_enhanced_text(
                        painter,
                        label_rect,
                        Qt.AlignmentFlag.AlignCenter,
                        f"{angle}°",
                        glow=False,
                        depth=depth
                    )
            
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_targeting_reticle(self, painter: QPainter, center: QPointF, radius: float,
                             color: Optional[QColor] = None, glow: bool = False,
                             depth: float = 0.0) -> None:
        """Draw targeting reticle with holographic effects"""
        # Save painter state
        painter.save()
        
        try:
            if color is None:
                # Apply depth effect to reticle color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth("critical", depth)
                else:
                    color = self._theme_manager.get_color("critical")
            
            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            use_glow = self._theme_manager.get_style_param("use_glow", False)
            
            # Apply pulse effect to glow
            if self._theme_manager.get_style_param("use_pulse_effects", False):
                pulse_factor = self.get_pulse_factor(
                    rate=self._theme_manager.get_style_param("pulse_rate", 1.0),
                    min_value=0.7,
                    max_value=1.0
                )
                
                # Adjust glow intensity with pulse
                glow_intensity = self._theme_manager.get_style_param("glow_intensity", 0.5) * pulse_factor
            else:
                glow_intensity = self._theme_manager.get_style_param("glow_intensity", 0.5)
            
            # Create glow color
            glow_color = QColor(color)
            glow_color.setAlpha(min(color.alpha() // 2, int(100 * glow_intensity)))
            
            # Draw outer circle
            outer_rect = QRectF(
                center.x() - radius,
                center.y() - radius,
                radius * 2,
                radius * 2
            )
            
            self.draw_enhanced_ellipse(
                painter,
                outer_rect,
                color=color,
                fill=False,
                glow=glow and use_glow,
                depth=depth
            )
            
            # Draw inner circle
            inner_radius = radius * 0.2
            inner_rect = QRectF(
                center.x() - inner_radius,
                center.y() - inner_radius,
                inner_radius * 2,
                inner_radius * 2
            )
            
            self.draw_enhanced_ellipse(
                painter,
                inner_rect,
                color=color,
                fill=False,
                glow=glow and use_glow,
                depth=depth
            )
            
            # Draw crosshairs
            # Horizontal line
            self.draw_enhanced_line(
                painter,
                QPointF(center.x() - radius * 0.5, center.y()),
                QPointF(center.x() - inner_radius, center.y()),
                color=color,
                width=1.5,
                glow=glow and use_glow,
                depth=depth
            )
            
            self.draw_enhanced_line(
                painter,
                QPointF(center.x() + inner_radius, center.y()),
                QPointF(center.x() + radius * 0.5, center.y()),
                color=color,
                width=1.5,
                glow=glow and use_glow,
                depth=depth
            )
            
            # Vertical line
            self.draw_enhanced_line(
                painter,
                QPointF(center.x(), center.y() - radius * 0.5),
                QPointF(center.x(), center.y() - inner_radius),
                color=color,
                width=1.5,
                glow=glow and use_glow,
                depth=depth
            )
            
            self.draw_enhanced_line(
                painter,
                QPointF(center.x(), center.y() + inner_radius),
                QPointF(center.x(), center.y() + radius * 0.5),
                color=color,
                width=1.5,
                glow=glow and use_glow,
                depth=depth
            )
            
            # Draw tick marks
            for angle in range(0, 360, 45):
                # Calculate tick position
                rad_angle = math.radians(angle)
                inner_x = center.x() + inner_radius * 1.5 * math.cos(rad_angle)
                inner_y = center.y() + inner_radius * 1.5 * math.sin(rad_angle)
                outer_x = center.x() + inner_radius * 2.0 * math.cos(rad_angle)
                outer_y = center.y() + inner_radius * 2.0 * math.sin(rad_angle)
                
                # Draw tick
                self.draw_enhanced_line(
                    painter,
                    QPointF(inner_x, inner_y),
                    QPointF(outer_x, outer_y),
                    color=color,
                    width=1.5,
                    glow=False,
                    depth=depth
                )
            
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_targeting_box(self, painter: QPainter, rect: QRectF,
                         color: Optional[QColor] = None, lock_status: str = "TRACKING",
                         glow: bool = False, depth: float = 0.0) -> None:
        """Draw targeting box with holographic effects"""
        # Save painter state
        painter.save()
        
        try:
            if color is None:
                # Apply depth effect to box color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth("critical", depth)
                else:
                    color = self._theme_manager.get_color("critical")
            
            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            use_glow = self._theme_manager.get_style_param("use_glow", False)
            
            # Apply pulse effect to glow
            if self._theme_manager.get_style_param("use_pulse_effects", False):
                pulse_factor = self.get_pulse_factor(
                    rate=self._theme_manager.get_style_param("pulse_rate", 1.0),
                    min_value=0.7,
                    max_value=1.0
                )
                
                # Adjust glow intensity with pulse
                glow_intensity = self._theme_manager.get_style_param("glow_intensity", 0.5) * pulse_factor
            else:
                glow_intensity = self._theme_manager.get_style_param("glow_intensity", 0.5)
            
            # Create glow color
            glow_color = QColor(color)
            glow_color.setAlpha(min(color.alpha() // 2, int(100 * glow_intensity)))
            
            # Draw corner brackets instead of full box
            bracket_length = min(rect.width(), rect.height()) * 0.3
            
            # Top-left corner
            self.draw_enhanced_line(
                painter,
                QPointF(rect.left(), rect.top() + bracket_length),
                QPointF(rect.left(), rect.top()),
                color=color,
                width=2.0,
                glow=glow and use_glow,
                depth=depth
            )
            
            self.draw_enhanced_line(
                painter,
                QPointF(rect.left(), rect.top()),
                QPointF(rect.left() + bracket_length, rect.top()),
                color=color,
                width=2.0,
                glow=glow and use_glow,
                depth=depth
            )
            
            # Top-right corner
            self.draw_enhanced_line(
                painter,
                QPointF(rect.right() - bracket_length, rect.top()),
                QPointF(rect.right(), rect.top()),
                color=color,
                width=2.0,
                glow=glow and use_glow,
                depth=depth
            )
            
            self.draw_enhanced_line(
                painter,
                QPointF(rect.right(), rect.top()),
                QPointF(rect.right(), rect.top() + bracket_length),
                color=color,
                width=2.0,
                glow=glow and use_glow,
                depth=depth
            )
            
            # Bottom-right corner
            self.draw_enhanced_line(
                painter,
                QPointF(rect.right(), rect.bottom() - bracket_length),
                QPointF(rect.right(), rect.bottom()),
                color=color,
                width=2.0,
                glow=glow and use_glow,
                depth=depth
            )
            
            self.draw_enhanced_line(
                painter,
                QPointF(rect.right(), rect.bottom()),
                QPointF(rect.right() - bracket_length, rect.bottom()),
                color=color,
                width=2.0,
                glow=glow and use_glow,
                depth=depth
            )
            
            # Bottom-left corner
            self.draw_enhanced_line(
                painter,
                QPointF(rect.left() + bracket_length, rect.bottom()),
                QPointF(rect.left(), rect.bottom()),
                color=color,
                width=2.0,
                glow=glow and use_glow,
                depth=depth
            )
            
            self.draw_enhanced_line(
                painter,
                QPointF(rect.left(), rect.bottom()),
                QPointF(rect.left(), rect.bottom() - bracket_length),
                color=color,
                width=2.0,
                glow=glow and use_glow,
                depth=depth
            )
            
            # Draw lock status
            status_rect = QRectF(
                rect.left(),
                rect.bottom() + 5,
                rect.width(),
                20
            )
            
            self.draw_enhanced_text(
                painter,
                status_rect,
                Qt.AlignmentFlag.AlignCenter,
                lock_status,
                glow=glow and use_glow,
                glow_color=color,
                depth=depth
            )
            
        finally:
            # Restore painter state
            painter.restore()
    
    def draw_3d_terrain(self, painter: QPainter, rect: QRectF,
                       terrain_data: List[float],
                       color: Optional[QColor] = None,
                       style: str = "modern",
                       depth: float = 0.0) -> None:
        """Draw 3D terrain visualization with depth effects"""
        # Save painter state
        painter.save()
        
        try:
            if color is None:
                # Apply depth effect to terrain color
                if depth != 0.0 and self._theme_manager.is_depth_enabled():
                    color = self._theme_manager.create_color_with_depth("data_secondary", depth)
                else:
                    color = self._theme_manager.get_color("data_secondary")
            
            # Ensure we have data
            if not terrain_data or len(terrain_data) < 2:
                return
            
            # Calculate scaling
            x_step = rect.width() / (len(terrain_data) - 1)
            y_scale = rect.height() * 0.8  # Leave some margin
            
            # Create path for the terrain
            path = QPainterPath()
            
            # Start at the first point
            start_x = rect.x()
            start_y = rect.y() + rect.height() - (terrain_data[0] * y_scale)
            path.moveTo(start_x, start_y)
            
            if style == "angular":
                # Draw angular lines between points
                for i in range(1, len(terrain_data)):
                    x = rect.x() + i * x_step
                    y = rect.y() + rect.height() - (terrain_data[i] * y_scale)
                    path.lineTo(x, y)
            else:  # Default to modern
                # Draw smooth curve through points
                for i in range(1, len(terrain_data)):
                    x = rect.x() + i * x_step
                    y = rect.y() + rect.height() - (terrain_data[i] * y_scale)
                    
                    # Use quadratic curves for smoother appearance
                    if i < len(terrain_data) - 1:
                        # Control point is midway between points
                        ctrl_x = x + x_step / 2
                        ctrl_y = rect.y() + rect.height() - (terrain_data[i+1] * y_scale)
                        path.quadTo(x, y, ctrl_x, ctrl_y)
                    else:
                        # Last point
                        path.lineTo(x, y)
            
            # Complete the path to create a filled shape
            path.lineTo(rect.x() + rect.width(), rect.y() + rect.height())
            path.lineTo(rect.x(), rect.y() + rect.height())
            path.closeSubpath()
            
            # Create gradient fill
            gradient = QLinearGradient(
                rect.x(), rect.y(),
                rect.x(), rect.y() + rect.height()
            )
            
            # Create transparent version of color for gradient
            fill_color = QColor(color)
            fill_color.setAlpha(180)
            
            transparent_color = QColor(color)
            transparent_color.setAlpha(50)
            
            gradient.setColorAt(0, fill_color)
            gradient.setColorAt(1, transparent_color)
            
            # Draw terrain with gradient fill and glow outline
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawPath(path)
            
            # Draw outline with glow
            outline_path = QPainterPath()
            outline_path.moveTo(start_x, start_y)
            
            if style == "angular":
                # Draw angular lines between points
                for i in range(1, len(terrain_data)):
                    x = rect.x() + i * x_step
                    y = rect.y() + rect.height() - (terrain_data[i] * y_scale)
                    outline_path.lineTo(x, y)
            else:  # Default to modern
                # Draw smooth curve through points
                for i in range(1, len(terrain_data)):
                    x = rect.x() + i * x_step
                    y = rect.y() + rect.height() - (terrain_data[i] * y_scale)
                    
                    # Use quadratic curves for smoother appearance
                    if i < len(terrain_data) - 1:
                        # Control point is midway between points
                        ctrl_x = x + x_step / 2
                        ctrl_y = rect.y() + rect.height() - (terrain_data[i+1] * y_scale)
                        outline_path.quadTo(x, y, ctrl_x, ctrl_y)
                    else:
                        # Last point
                        outline_path.lineTo(x, y)
            
            # Draw outline with glow
            self.draw_enhanced_path(
                painter,
                outline_path,
                color=color,
                fill=False,
                glow=True,
                depth=depth
            )
            
            # Draw grid lines for depth effect
            if self._theme_manager.is_depth_enabled():
                grid_color = QColor(color)
                grid_color.setAlpha(40)
                painter.setPen(grid_color)
                
                # Draw horizontal grid lines
                for i in range(1, 5):
                    y = rect.y() + (rect.height() * i / 5)
                    painter.drawLine(QPointF(rect.x(), y), QPointF(rect.x() + rect.width(), y))
                
                # Draw vertical grid lines
                for i in range(1, len(terrain_data), 2):
                    x = rect.x() + i * x_step
                    painter.drawLine(QPointF(x, rect.y()), QPointF(x, rect.y() + rect.height()))
            
        finally:
            # Restore painter state
            painter.restore()

# Singleton instance
_enhanced_visual_effects = None

def get_enhanced_visual_effects() -> EnhancedVisualEffects:
    """Get the singleton enhanced visual effects instance"""
    global _enhanced_visual_effects
    if _enhanced_visual_effects is None:
        _enhanced_visual_effects = EnhancedVisualEffects()
    return _enhanced_visual_effects

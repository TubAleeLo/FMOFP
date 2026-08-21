"""
Holographic display base class for advanced displays
"""
from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPainterPath
from .base_display import BaseDisplay, DisplayType
from .visual.enhanced_theme_manager import get_enhanced_theme_manager
from .visual.enhanced_effects import get_enhanced_visual_effects
import math
import time
import traceback
from typing import Dict, List, Optional, Any, Tuple
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class HolographicDisplay(BaseDisplay):
    """Base class for holographic displays with advanced 3D and depth effects"""
    
    def __init__(self, display_type: DisplayType, parent=None):
        """Initialize holographic display"""
        super().__init__(display_type, parent=parent)
        
        # Use enhanced theme manager and visual effects
        self._theme_manager = get_enhanced_theme_manager()
        self._visual_effects = get_enhanced_visual_effects()
        
        # Animation parameters
        self._animation_timer = QTimer()
        self._animation_timer.timeout.connect(self._update_animations)
        self._animation_timer.start(16)  # ~60 FPS
        
        # Animation state
        self._last_update_time = time.time()
        self._pulse_time = 0.0
        
        # Depth effect parameters
        self._parallax_offset_x = 0.0
        self._parallax_offset_y = 0.0
        self._parallax_scale = 1.0
        
        # Holographic parameters
        self._holographic_intensity = 1.0
        self._holographic_noise = 0.0
        
        # Startup animation
        self._startup_progress = 0.0
        self._startup_time = time.time()
        self._startup_duration = 1.5  # seconds
        
        logger.info(f"Initialized holographic {display_type.name} display")
    
    def _update_animations(self):
        """Update animation state"""
        current_time = time.time()
        delta_time = current_time - self._last_update_time
        self._last_update_time = current_time
        
        # Update visual effects animation time
        self._visual_effects.update_animation_time(delta_time)
        
        # Update startup animation
        if self._startup_progress < 1.0:
            elapsed = current_time - self._startup_time
            self._startup_progress = min(1.0, elapsed / self._startup_duration)
            
        # Update pulse time
        pulse_rate = self._theme_manager.get_style_param("pulse_rate", 1.0)
        self._pulse_time += delta_time * pulse_rate
        if self._pulse_time > 1000.0:
            self._pulse_time = 0.0
            
        # Update holographic noise
        noise_rate = 2.0
        self._holographic_noise = (math.sin(self._pulse_time * noise_rate) + 1.0) / 2.0 * 0.05
        
        # Update parallax effect based on time
        if self._theme_manager.get_style_param("use_parallax_effects", False):
            parallax_rate = 0.2
            self._parallax_offset_x = math.sin(self._pulse_time * parallax_rate) * 2.0
            self._parallax_offset_y = math.cos(self._pulse_time * parallax_rate) * 2.0
            self._parallax_scale = 1.0 + math.sin(self._pulse_time * parallax_rate * 0.5) * 0.01
        
        # Request repaint
        self.update()
    
    def get_pulse_factor(self, rate: float = 1.0, min_value: float = 0.7, max_value: float = 1.0) -> float:
        """Get current pulse factor for animations"""
        return self._visual_effects.get_pulse_factor(rate, min_value, max_value)
    
    def draw_holographic_background(self, painter: QPainter, rect: QRectF, depth: float = 0.0):
        """Draw holographic background with grid and depth effects"""
        # Draw layered background with grid
        self._visual_effects.draw_layered_background(
            painter,
            rect,
            grid_type=self._theme_manager.get_style_param("grid_type", "radial"),
            depth=depth
        )
        
        # Draw holographic noise effect if enabled
        if self._theme_manager.get_style_param("use_holographic_elements", False):
            # Create noise pattern
            noise_color = self._theme_manager.get_color("grid")
            noise_color.setAlpha(int(20 * self._holographic_noise))
            
            # Draw random dots
            painter.setPen(noise_color)
            
            # Generate random dots based on time
            import random
            random.seed(int(self._pulse_time * 10))
            
            for _ in range(100):
                x = random.uniform(rect.left(), rect.right())
                y = random.uniform(rect.top(), rect.bottom())
                size = random.uniform(1, 3)
                
                painter.drawEllipse(QPointF(x, y), size, size)
    
    def draw_holographic_frame(self, painter: QPainter, rect: QRectF, depth: float = 0.0):
        """Draw holographic frame with depth effects"""
        # Draw angular frame with glow
        self._visual_effects.draw_angular_frame(
            painter,
            rect,
            corner_style="hexagonal" if self._theme_manager.get_style_param("use_angular_design", False) else "beveled",
            glow=True,
            depth=depth
        )
        
        # Draw holographic elements if enabled
        if self._theme_manager.get_style_param("use_holographic_elements", False):
            # Draw corner accents
            corner_size = min(rect.width(), rect.height()) * 0.05
            
            # Top-left corner
            self._visual_effects.draw_enhanced_line(
                painter,
                QPointF(rect.left(), rect.top() + corner_size),
                QPointF(rect.left() + corner_size, rect.top()),
                glow=True,
                depth=depth + 0.2
            )
            
            # Top-right corner
            self._visual_effects.draw_enhanced_line(
                painter,
                QPointF(rect.right() - corner_size, rect.top()),
                QPointF(rect.right(), rect.top() + corner_size),
                glow=True,
                depth=depth + 0.2
            )
            
            # Bottom-right corner
            self._visual_effects.draw_enhanced_line(
                painter,
                QPointF(rect.right(), rect.bottom() - corner_size),
                QPointF(rect.right() - corner_size, rect.bottom()),
                glow=True,
                depth=depth + 0.2
            )
            
            # Bottom-left corner
            self._visual_effects.draw_enhanced_line(
                painter,
                QPointF(rect.left() + corner_size, rect.bottom()),
                QPointF(rect.left(), rect.bottom() - corner_size),
                glow=True,
                depth=depth + 0.2
            )
    
    def draw_holographic_text(self, painter: QPainter, rect: QRectF, flags: int, text: str, 
                            depth: float = 0.0, color_name: str = "hud"):
        """Draw holographic text with depth effects"""
        # Apply parallax effect if enabled
        if self._theme_manager.get_style_param("use_parallax_effects", False):
            # Adjust rect based on depth and parallax
            parallax_factor = depth * 5.0
            adjusted_rect = QRectF(
                rect.x() + self._parallax_offset_x * parallax_factor,
                rect.y() + self._parallax_offset_y * parallax_factor,
                rect.width() * self._parallax_scale,
                rect.height() * self._parallax_scale
            )
            
            # Draw text with enhanced effects
            self._visual_effects.draw_enhanced_text(
                painter,
                adjusted_rect,
                flags,
                text,
                glow=True,
                glow_color=self._theme_manager.create_color_with_depth(color_name, depth),
                shadow=True,
                depth=depth
            )
        else:
            # Draw text with enhanced effects (no parallax)
            self._visual_effects.draw_enhanced_text(
                painter,
                rect,
                flags,
                text,
                glow=True,
                glow_color=self._theme_manager.create_color_with_depth(color_name, depth),
                shadow=True,
                depth=depth
            )
    
    def draw_holographic_data_box(self, painter: QPainter, rect: QRectF, title: str, 
                                value: str, unit: str = "", depth: float = 0.0,
                                color_name: str = "data_primary"):
        """Draw holographic data box with title, value and unit"""
        # Draw box frame
        self._visual_effects.draw_angular_frame(
            painter,
            rect,
            color=self._theme_manager.create_color_with_depth(color_name, depth),
            corner_style="angular" if self._theme_manager.get_style_param("use_angular_design", False) else "beveled",
            glow=True,
            depth=depth
        )
        
        # Draw title
        title_rect = QRectF(
            rect.x() + 5,
            rect.y() + 5,
            rect.width() - 10,
            rect.height() * 0.3
        )
        
        self.draw_holographic_text(
            painter,
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            title,
            depth=depth,
            color_name=color_name
        )
        
        # Draw value
        value_rect = QRectF(
            rect.x() + 5,
            rect.y() + rect.height() * 0.3,
            rect.width() - 10,
            rect.height() * 0.5
        )
        
        self.draw_holographic_text(
            painter,
            value_rect,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            value,
            depth=depth + 0.1,  # Slightly more depth for emphasis
            color_name=color_name
        )
        
        # Draw unit
        if unit:
            unit_rect = QRectF(
                rect.x() + 5,
                rect.y() + rect.height() * 0.8,
                rect.width() - 10,
                rect.height() * 0.2
            )
            
            self.draw_holographic_text(
                painter,
                unit_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                unit,
                depth=depth,
                color_name=color_name
            )
    
    def draw_holographic_indicator(self, painter: QPainter, center: QPointF, radius: float,
                                 value: float, min_value: float, max_value: float,
                                 color_name: str = "data_primary", depth: float = 0.0):
        """Draw holographic circular indicator with value"""
        # Calculate normalized value (0.0 to 1.0)
        normalized = (value - min_value) / (max_value - min_value)
        normalized = max(0.0, min(1.0, normalized))
        
        # Calculate start and end angles (0 degrees is at 3 o'clock, going clockwise)
        start_angle = 135
        end_angle = -135
        span_angle = end_angle - start_angle
        
        # Calculate value angle
        value_angle = start_angle + span_angle * normalized
        
        # Get color based on depth
        color = self._theme_manager.create_color_with_depth(color_name, depth)
        
        # Draw background arc
        bg_path = QPainterPath()
        bg_path.moveTo(center)
        
        # Add background arc
        bg_rect = QRectF(
            center.x() - radius,
            center.y() - radius,
            radius * 2,
            radius * 2
        )
        
        # Convert to Qt angles (16th of a degree, clockwise from 3 o'clock)
        qt_start_angle = start_angle * 16
        qt_span_angle = span_angle * 16
        
        bg_path.arcTo(bg_rect, start_angle, span_angle)
        
        # Draw background arc with glow
        bg_color = QColor(color)
        bg_color.setAlpha(80)
        
        self._visual_effects.draw_enhanced_path(
            painter,
            bg_path,
            color=bg_color,
            fill=False,
            glow=False,
            depth=depth
        )
        
        # Draw value arc
        value_path = QPainterPath()
        value_path.moveTo(center)
        
        # Add value arc
        value_path.arcTo(bg_rect, start_angle, value_angle - start_angle)
        
        # Draw value arc with glow
        self._visual_effects.draw_enhanced_path(
            painter,
            value_path,
            color=color,
            fill=False,
            glow=True,
            depth=depth + 0.1  # Slightly more depth for emphasis
        )
        
        # Draw center dot
        center_rect = QRectF(
            center.x() - 3,
            center.y() - 3,
            6,
            6
        )
        
        self._visual_effects.draw_enhanced_ellipse(
            painter,
            center_rect,
            color=color,
            fill=True,
            glow=True,
            depth=depth + 0.2  # More depth for emphasis
        )
        
        # Draw tick marks
        for i in range(11):  # 0%, 10%, 20%, ..., 100%
            tick_normalized = i / 10.0
            tick_angle = start_angle + span_angle * tick_normalized
            
            # Convert to radians
            rad_angle = math.radians(tick_angle)
            
            # Calculate tick start and end points
            inner_radius = radius * 0.9
            outer_radius = radius
            
            if i % 5 == 0:  # Major ticks at 0%, 50%, 100%
                inner_radius = radius * 0.85
                
            start_x = center.x() + inner_radius * math.cos(rad_angle)
            start_y = center.y() + inner_radius * math.sin(rad_angle)
            
            end_x = center.x() + outer_radius * math.cos(rad_angle)
            end_y = center.y() + outer_radius * math.sin(rad_angle)
            
            # Draw tick with glow for major ticks
            self._visual_effects.draw_enhanced_line(
                painter,
                QPointF(start_x, start_y),
                QPointF(end_x, end_y),
                color=color,
                glow=i % 5 == 0,
                depth=depth
            )
            
            # Draw value label for major ticks
            if i % 5 == 0:
                label_radius = radius * 1.1
                label_x = center.x() + label_radius * math.cos(rad_angle)
                label_y = center.y() + label_radius * math.sin(rad_angle)
                
                label_rect = QRectF(
                    label_x - 15,
                    label_y - 10,
                    30,
                    20
                )
                
                # Calculate value at this tick
                tick_value = min_value + (max_value - min_value) * tick_normalized
                
                self.draw_holographic_text(
                    painter,
                    label_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    f"{int(tick_value)}",
                    depth=depth,
                    color_name=color_name
                )
    
    def draw_holographic_bar(self, painter: QPainter, rect: QRectF, value: float, 
                           min_value: float, max_value: float, vertical: bool = True,
                           color_name: str = "data_primary", depth: float = 0.0):
        """Draw holographic bar indicator with value"""
        # Calculate normalized value (0.0 to 1.0)
        normalized = (value - min_value) / (max_value - min_value)
        normalized = max(0.0, min(1.0, normalized))
        
        # Get color based on depth
        color = self._theme_manager.create_color_with_depth(color_name, depth)
        
        # Draw background bar
        self._visual_effects.draw_enhanced_rect(
            painter,
            rect,
            color=color,
            fill=True,
            fill_color=QColor(color.red(), color.green(), color.blue(), 40),
            corner_radius=2.0,
            glow=False,
            depth=depth
        )
        
        # Calculate value rect
        if vertical:
            # Vertical bar (bottom to top)
            value_height = rect.height() * normalized
            value_rect = QRectF(
                rect.x(),
                rect.y() + rect.height() - value_height,
                rect.width(),
                value_height
            )
        else:
            # Horizontal bar (left to right)
            value_width = rect.width() * normalized
            value_rect = QRectF(
                rect.x(),
                rect.y(),
                value_width,
                rect.height()
            )
        
        # Draw value bar with glow
        self._visual_effects.draw_enhanced_rect(
            painter,
            value_rect,
            color=color,
            fill=True,
            corner_radius=2.0,
            glow=True,
            depth=depth + 0.1  # Slightly more depth for emphasis
        )
        
        # Draw tick marks
        if vertical:
            # Vertical ticks
            for i in range(11):  # 0%, 10%, 20%, ..., 100%
                y = rect.y() + rect.height() - (rect.height() * i / 10.0)
                
                # Draw tick
                tick_width = 5.0 if i % 5 == 0 else 3.0  # Longer ticks for major marks
                
                self._visual_effects.draw_enhanced_line(
                    painter,
                    QPointF(rect.x(), y),
                    QPointF(rect.x() + tick_width, y),
                    color=color,
                    glow=i % 5 == 0,
                    depth=depth
                )
                
                # Draw value label for major ticks
                if i % 5 == 0:
                    tick_value = min_value + (max_value - min_value) * (i / 10.0)
                    
                    label_rect = QRectF(
                        rect.x() + tick_width + 2,
                        y - 10,
                        30,
                        20
                    )
                    
                    self.draw_holographic_text(
                        painter,
                        label_rect,
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        f"{int(tick_value)}",
                        depth=depth,
                        color_name=color_name
                    )
        else:
            # Horizontal ticks
            for i in range(11):  # 0%, 10%, 20%, ..., 100%
                x = rect.x() + (rect.width() * i / 10.0)
                
                # Draw tick
                tick_height = 5.0 if i % 5 == 0 else 3.0  # Longer ticks for major marks
                
                self._visual_effects.draw_enhanced_line(
                    painter,
                    QPointF(x, rect.y() + rect.height()),
                    QPointF(x, rect.y() + rect.height() - tick_height),
                    color=color,
                    glow=i % 5 == 0,
                    depth=depth
                )
                
                # Draw value label for major ticks
                if i % 5 == 0:
                    tick_value = min_value + (max_value - min_value) * (i / 10.0)
                    
                    label_rect = QRectF(
                        x - 15,
                        rect.y() + rect.height() - tick_height - 20,
                        30,
                        20
                    )
                    
                    self.draw_holographic_text(
                        painter,
                        label_rect,
                        Qt.AlignmentFlag.AlignCenter,
                        f"{int(tick_value)}",
                        depth=depth,
                        color_name=color_name
                    )
    
    def cleanup(self):
        """Clean up resources"""
        # Stop animation timer
        if hasattr(self, '_animation_timer') and self._animation_timer:
            self._animation_timer.stop()
            self._animation_timer = None
        
        # Call base class cleanup if it exists
        if hasattr(super(), 'cleanup'):
            super().cleanup()
    
    def draw_startup_animation(self, painter: QPainter):
        """Draw startup animation for holographic display"""
        if self._startup_progress >= 1.0:
            return
            
        # Save state
        painter.save()
        
        try:
            # Get display dimensions
            width = self.width()
            height = self.height()
            
            # Draw background overlay
            overlay_color = self._theme_manager.get_color("background")
            overlay_color.setAlpha(int(255 * (1.0 - self._startup_progress)))
            painter.fillRect(0, 0, width, height, overlay_color)
            
            # Draw startup text
            if self._startup_progress < 0.3:
                # Phase 1: Initializing
                progress_text = "INITIALIZING HOLOGRAPHIC SYSTEMS"
            elif self._startup_progress < 0.6:
                # Phase 2: Calibrating
                progress_text = "CALIBRATING DISPLAY PARAMETERS"
            elif self._startup_progress < 0.9:
                # Phase 3: Loading
                progress_text = "LOADING TACTICAL DATA"
            else:
                # Phase 4: Ready
                progress_text = "HOLOGRAPHIC DISPLAY READY"
            
            # Draw progress text
            text_rect = QRectF(0, height / 2 - 20, width, 40)
            
            self._visual_effects.draw_enhanced_text(
                painter,
                text_rect,
                Qt.AlignmentFlag.AlignCenter,
                progress_text,
                glow=True,
                shadow=True
            )
            
            # Draw progress bar
            bar_width = width * 0.5
            bar_height = 10
            bar_rect = QRectF(
                (width - bar_width) / 2,
                height / 2 + 30,
                bar_width,
                bar_height
            )
            
            # Draw background bar
            painter.fillRect(bar_rect, QColor(40, 40, 40))
            
            # Draw progress bar
            progress_rect = QRectF(
                bar_rect.x(),
                bar_rect.y(),
                bar_rect.width() * self._startup_progress,
                bar_rect.height()
            )
            
            progress_color = self._theme_manager.get_color("data_primary")
            painter.fillRect(progress_rect, progress_color)
            
            # Draw scanning lines
            scan_color = self._theme_manager.get_color("data_primary")
            scan_color.setAlpha(100)
            painter.setPen(scan_color)
            
            # Horizontal scan line
            scan_y = height * (0.1 + self._startup_progress * 0.8)
            painter.drawLine(0, scan_y, width, scan_y)
            
            # Vertical scan line
            scan_x = width * (0.1 + self._startup_progress * 0.8)
            painter.drawLine(scan_x, 0, scan_x, height)
            
        finally:
            # Restore state
            painter.restore()

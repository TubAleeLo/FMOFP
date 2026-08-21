"""Legend Manager

Centralized management of radar display legends with support for multiple data types.
Provides distinct visual representations with tactical-style animations and
intelligent selection based on mode.
"""

from typing import Dict, List, Optional, Any, Set, Tuple, Callable
from enum import Enum, auto
import time
import traceback
from PyQt6.QtCore import QRectF, QPointF, QTimer, QObject
from PyQt6.QtGui import QPainter, QColor, QBrush, QLinearGradient, QPainterPath, QPen, QFont
from PyQt6.QtCore import Qt

from ..utils.visual_settings_manager import get_visual_settings_manager
from Utils.logger.sys_logger import get_logger

logger = get_logger()


BORDER_WIDTH = 2
GRID_OPACITY = 0.15
PANEL_OPACITY = 0.60  # 60% opacity
ANIMATION_DURATION = 350  # ms

class LegendState(Enum):
    """States for the collapsible legend panel"""
    COLLAPSED = auto()  # Fully collapsed (just the tab)
    EXPANDING = auto()  # In the process of expanding
    EXPANDED = auto()   # Fully expanded
    COLLAPSING = auto() # In the process of collapsing

class LegendShape(Enum):
    """Shapes used for legend items"""
    SQUARE = auto()
    CIRCLE = auto()
    DIAMOND = auto()
    TRIANGLE = auto()
    HEXAGON = auto()
    GRADIENT = auto()
    DASHED = auto()
    LIGHTNING = auto()
    CRYSTAL = auto()

class LegendRenderStrategy(Enum):
    """Strategies for rendering legends"""
    STANDARD = auto()    # Single legend with full details
    COMPACT = auto()     # Condensed version with minimal details
    COMBINED = auto()    # Multiple legends in a single display
    CONTEXTUAL = auto()  # Dynamic based on visible data

class LegendConfig:
    """Enhanced configuration for a specific legend type"""
    
    def __init__(self, name: str, allowed_modes: List[str], enabled: bool = False):
        """Initialize legend configuration.
        
        Args:
            name: Legend identifier
            allowed_modes: List of modes where this legend can be shown
            enabled: Initial enabled state
        """
        self.name = name
        self.allowed_modes = set(allowed_modes)
        self.enabled = enabled
        self.colors: Dict[str, QColor] = {}
        self.labels: List[str] = []
        self.position: Optional[Tuple[float, float]] = None
        self.show_values = False
        self.priority = 0  # Higher priority legends are drawn first
        
        # Enhanced properties
        self.shape = LegendShape.SQUARE  # Default shape
        self.units = ""  # Units for values (e.g., "kg/m²")
        self.title = name.capitalize()  # Human-readable title
        self.render_strategy = LegendRenderStrategy.STANDARD
        self.data_type = name  # Type of data this legend represents
        
    def is_allowed_in_mode(self, mode: str) -> bool:
        """Check if legend is allowed in given mode."""
        return mode.upper() in {m.upper() for m in self.allowed_modes}
        
    def __repr__(self) -> str:
        return f"LegendConfig(name={self.name}, enabled={self.enabled}, modes={self.allowed_modes})"

class CollapsibleLegendPanel(QObject):
    """style collapsible legend panel with tactical animations"""
    
    def __init__(self, parent=None):
        """Initialize the collapsible legend panel.
        
        Args:
            parent: Parent QObject
        """
        super().__init__(parent)
        self._state = LegendState.COLLAPSED
        self._animation_progress = 0.0  # 0.0 = collapsed, 1.0 = expanded
        self._animation_start_time = 0
        self._scan_line_position = 0.0
        self._scan_line_visible = False
        self._panel_rect = QRectF()
        self._tab_rect = QRectF()
        self._content_rect = QRectF()
        self._legend_config = None
        self._last_click_time = 0
        self._accent_color = QColor(0, 170, 255)  # Default blue accent
        self._pulse_opacity = 0.7
        self._pulse_direction = 1
        self._grid_offset = 0.0
        
        # Animation timer
        self._animation_timer = QTimer()
        self._animation_timer.setInterval(16)  # ~60fps
        self._animation_timer.timeout.connect(self._update_animation)
        
        # Pulse timer for collapsed state
        self._pulse_timer = QTimer()
        self._pulse_timer.setInterval(50)
        self._pulse_timer.timeout.connect(self._update_pulse)
        self._pulse_timer.start()
        
        logger.info("[LEGEND_PANEL] Initialized collapsible legend panel")
        
    def set_legend_config(self, config: LegendConfig) -> None:
        """Set the legend configuration to display.
        
        Args:
            config: Legend configuration
        """
        self._legend_config = config
        
        # SETS THE ACCENT COLOR BASED ON LEGEND TYPE #
        # Set fixed accent color based on legend type
        # Use fixed colors to prevent influence from VIL data points
        if config:
            if config.name == "vil":
                # Use a fixed blue color for VIL that won't be affected by the data
                self._accent_color = QColor(0, 170, 255)  # Blue
            elif config.name == "precipitation":
                self._accent_color = QColor(0, 0, 204)    # Dark Blue
            elif config.name == "intensity":
                self._accent_color = QColor(255, 136, 0)  # Orange
            elif config.name == "turbulence":
                self._accent_color = QColor(255, 255, 0)  # Yellow
            elif config.name == "windshear":
                self._accent_color = QColor(255, 0, 0)    # Red
            elif config.name == "terrain":
                self._accent_color = QColor(0, 100, 0)    # Dark Green
            
            # Add time-based throttling for accent color logging
            current_time = time.time()
            if not hasattr(self, '_last_accent_color_log_time'):
                self._last_accent_color_log_time = 0
                
            # Only log once every 5 seconds, regardless of whether the color changed
            if current_time - self._last_accent_color_log_time > 5.0:
                logger.debug(f"[LEGEND_PANEL] Set accent color for {config.name} legend: {self._accent_color.name()}")
                self._last_accent_color_log_time = current_time
                
            self._last_accent_color = self._accent_color
        
    def update_layout(self, rect: QRectF) -> None:
        """Update the panel layout based on the available space.
        
        Args:
            rect: Available rectangle for drawing
        """
        # Tab dimensions
        tab_width = 40
        tab_height = 25
        
        # Panel dimensions / SIZE
        panel_width = 153
        
        # Get content based height if we have a legend config
        if self._legend_config and hasattr(self._legend_config, 'colors'):
            # Calculate height based on number of items to display
            item_count = len(self._legend_config.colors)
            # Header (25px) + item_height (20px) * items + padding (15px)
            dynamic_height = 25 + (item_count * 20) + 15
            # Ensure min/max bounds
            panel_height = max(100, min(250, dynamic_height))
        else:
            # Default height if no config
            panel_height = min(250, rect.height() * 0.4)
        
        
        self._tab_rect = QRectF(
            740.0,  # Fixed X position based on working clicks
            555.0,  # Fixed Y position based on working clicks
            tab_width,
            tab_height
        )
        
        # Position panel above tab
        self._panel_rect = QRectF(
            self._tab_rect.left() - panel_width + tab_width,
            self._tab_rect.top() - panel_height,
            panel_width,
            panel_height
        )
        
        # Content rect is inside panel with margins
        margin = 5
        self._content_rect = QRectF(
            self._panel_rect.left() + margin,
            self._panel_rect.top() + margin,
            self._panel_rect.width() - 2 * margin,
            self._panel_rect.height() - 2 * margin
        )
        
    def handle_click(self, pos: QPointF) -> bool:
        """Handle mouse click at the specified position.
        
        Args:
            pos: Click position
            
        Returns:
            True if click was handled, False otherwise
        """
        
        # Create an expanded clickable rect
        expanded_tab_rect = QRectF(
            self._tab_rect.left() - 1,       # 1 pixel to the left
            self._tab_rect.top() - 1,        # 1 pixel to the top
            self._tab_rect.width() + 20,     # 9 pixels to the right
            self._tab_rect.height() + 20     # 9 pixels to the bottom
        )
        
        # Check if click is within expanded tab area
        if expanded_tab_rect.contains(pos):
            current_time = time.time()
            
            # Prevent rapid clicking
            if current_time - self._last_click_time < 0.5:
                return True
                
            self._last_click_time = current_time
            
            # Toggle state
            if self._state == LegendState.COLLAPSED:
                self._expand()
            elif self._state == LegendState.EXPANDED:
                self._collapse()
                
            return True
            
        # Check if click is within panel when expanded
        if self._state == LegendState.EXPANDED and self._panel_rect.contains(pos):
            return True
            
        return False
        
    def _expand(self) -> None:
        """Start expansion animation."""
        if self._state == LegendState.COLLAPSED:
            self._state = LegendState.EXPANDING
            self._animation_progress = 0.0
            self._animation_start_time = time.time()
            self._scan_line_visible = True
            self._scan_line_position = 0.0
            self._animation_timer.start()
            logger.info("[LEGEND_PANEL] Starting expansion animation")
            
    def _collapse(self) -> None:
        """Start collapse animation."""
        if self._state == LegendState.EXPANDED:
            self._state = LegendState.COLLAPSING
            self._animation_progress = 1.0
            self._animation_start_time = time.time()
            self._scan_line_visible = True
            self._scan_line_position = 1.0
            self._animation_timer.start()
            logger.info("[LEGEND_PANEL] Starting collapse animation")
            
    def _update_animation(self) -> None:
        """Update animation state."""
        current_time = time.time()
        elapsed = (current_time - self._animation_start_time) * 1000  # ms
        
        if self._state == LegendState.EXPANDING:
            # Update progress
            self._animation_progress = min(1.0, elapsed / ANIMATION_DURATION)
            
            # Update scan line
            self._scan_line_position = min(1.0, elapsed / (ANIMATION_DURATION * 0.8))
            
            # Check if animation is complete
            if self._animation_progress >= 1.0:
                self._state = LegendState.EXPANDED
                self._animation_timer.stop()
                self._scan_line_visible = False
                logger.info("[LEGEND_PANEL] Expansion animation complete")
                
        elif self._state == LegendState.COLLAPSING:
            # Update progress
            self._animation_progress = max(0.0, 1.0 - (elapsed / ANIMATION_DURATION))
            
            # Update scan line
            self._scan_line_position = max(0.0, 1.0 - (elapsed / (ANIMATION_DURATION * 0.8)))
            
            # Check if animation is complete
            if self._animation_progress <= 0.0:
                self._state = LegendState.COLLAPSED
                self._animation_timer.stop()
                self._scan_line_visible = False
                logger.info("[LEGEND_PANEL] Collapse animation complete")
                
    def _update_pulse(self) -> None:
        """Update pulse effect for collapsed state."""
        if self._state == LegendState.COLLAPSED:
            # Update pulse opacity
            self._pulse_opacity += 0.02 * self._pulse_direction
            
            # Reverse direction at limits
            if self._pulse_opacity >= 0.9:
                self._pulse_direction = -1
            elif self._pulse_opacity <= 0.5:
                self._pulse_direction = 1
                
        # Update grid offset for tactical grid effect
        self._grid_offset = (self._grid_offset + 0.2) % 20.0
        
    def draw(self, painter: QPainter, legend_manager) -> None:
        """Draw the collapsible legend panel.
        
        Args:
            painter: QPainter instance
            legend_manager: LegendManager instance for rendering legends
        """
        # Save painter state
        painter.save()
        
        # Draw tab
        self._draw_tab(painter)
        
        # Draw panel if expanding, expanded, or collapsing
        if self._state != LegendState.COLLAPSED:
            self._draw_panel(painter, legend_manager)
            
        # Restore painter state
        painter.restore()
        
    def _draw_tab(self, painter: QPainter) -> None:
        """Draw the tab button."""
        # Save painter state
        painter.save()
        
        # Set up colors
        border_color = self._accent_color
        if self._state == LegendState.COLLAPSED:
            # Pulsing effect in collapsed state
            border_color.setAlphaF(self._pulse_opacity)
        
        # Draw tab background with style angular corners
        tab_path = QPainterPath()
        tab_path.moveTo(self._tab_rect.left() + 5, self._tab_rect.top())
        tab_path.lineTo(self._tab_rect.right() - 5, self._tab_rect.top())
        tab_path.lineTo(self._tab_rect.right(), self._tab_rect.top() + 5)
        tab_path.lineTo(self._tab_rect.right(), self._tab_rect.bottom())
        tab_path.lineTo(self._tab_rect.left(), self._tab_rect.bottom())
        tab_path.lineTo(self._tab_rect.left(), self._tab_rect.top() + 5)
        tab_path.closeSubpath()
        
        # Fill with semi-transparent black
        background_color = QColor(0, 0, 0, 180)
        painter.fillPath(tab_path, background_color)
        
        # Draw border
        pen = QPen(border_color)
        pen.setWidth(BORDER_WIDTH)
        painter.setPen(pen)
        painter.drawPath(tab_path)
        
        # Draw icon (≡≡)
        painter.setPen(Qt.GlobalColor.white)
        font = QFont("Arial", 10)
        painter.setFont(font)
        painter.drawText(
            self._tab_rect,
            Qt.AlignmentFlag.AlignCenter,
            "≡≡"
        )
        
        # Draw scan line during animation
        if self._scan_line_visible and (self._state == LegendState.EXPANDING or self._state == LegendState.COLLAPSING):
            scan_line_y = self._tab_rect.top() + self._scan_line_position * self._tab_rect.height()
            scan_line_pen = QPen(self._accent_color)
            scan_line_pen.setWidth(1)
            painter.setPen(scan_line_pen)
            painter.drawLine(
                QPointF(self._tab_rect.left(), scan_line_y),
                QPointF(self._tab_rect.right(), scan_line_y)
            )
        
        # Restore painter state
        painter.restore()
        
    def _draw_panel(self, painter: QPainter, legend_manager) -> None:
        """Draw the panel with legend content."""
        # Save painter state
        painter.save()
        
        # Calculate animated panel rect
        if self._state == LegendState.EXPANDING or self._state == LegendState.COLLAPSING:
            # During animation, adjust height based on progress
            animated_height = self._panel_rect.height() * self._animation_progress
            animated_panel_rect = QRectF(
                self._panel_rect.left(),
                self._panel_rect.bottom() - animated_height,
                self._panel_rect.width(),
                animated_height
            )
            
            # Adjust content rect
            margin = 5
            animated_content_rect = QRectF(
                animated_panel_rect.left() + margin,
                animated_panel_rect.top() + margin,
                animated_panel_rect.width() - 2 * margin,
                animated_panel_rect.height() - 2 * margin
            )
        else:
            # Fully expanded
            animated_panel_rect = self._panel_rect
            animated_content_rect = self._content_rect
        
        # Draw panel background with style angular corners
        panel_path = QPainterPath()
        panel_path.moveTo(animated_panel_rect.left() + 10, animated_panel_rect.top())
        panel_path.lineTo(animated_panel_rect.right() - 10, animated_panel_rect.top())
        panel_path.lineTo(animated_panel_rect.right(), animated_panel_rect.top() + 10)
        panel_path.lineTo(animated_panel_rect.right(), animated_panel_rect.bottom())
        panel_path.lineTo(animated_panel_rect.left(), animated_panel_rect.bottom())
        panel_path.lineTo(animated_panel_rect.left(), animated_panel_rect.top() + 10)
        panel_path.closeSubpath()
        
        # Fill with semi-transparent black
        background_color = QColor(0, 0, 0)
        background_color.setAlphaF(PANEL_OPACITY * self._animation_progress)
        painter.fillPath(panel_path, background_color)
        
        # Draw tactical grid overlay
        self._draw_tactical_grid(painter, animated_panel_rect)
        
        # Draw border
        pen = QPen(self._accent_color)
        pen.setWidth(BORDER_WIDTH)
        painter.setPen(pen)
        painter.drawPath(panel_path)
        
        # Draw scan line during animation
        if self._scan_line_visible:
            if self._state == LegendState.EXPANDING:
                scan_line_y = animated_panel_rect.top() + self._scan_line_position * animated_panel_rect.height()
            else:  # COLLAPSING
                scan_line_y = animated_panel_rect.bottom() - self._scan_line_position * animated_panel_rect.height()
                
            scan_line_pen = QPen(self._accent_color)
            scan_line_pen.setWidth(1)
            painter.setPen(scan_line_pen)
            painter.drawLine(
                QPointF(animated_panel_rect.left(), scan_line_y),
                QPointF(animated_panel_rect.right(), scan_line_y)
            )
        
        # Draw legend content if we have a config
        if self._legend_config and self._animation_progress > 0.5:
            # Set clip rect to content area
            painter.setClipRect(animated_content_rect)
            
            # Draw legend
            legend_manager._render_legend(painter, animated_content_rect, self._legend_config)
            
            # Clear clip rect
            painter.setClipRect(QRectF())
        
        # Draw collapse indicator at top of panel
        if self._animation_progress > 0.9:
            indicator_rect = QRectF(
                animated_panel_rect.center().x() - 10,
                animated_panel_rect.top() + 5,
                20,
                10
            )
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(
                indicator_rect,
                Qt.AlignmentFlag.AlignCenter,
                "▲"
            )
        
        # Restore painter state
        painter.restore()
        
    def _draw_tactical_grid(self, painter: QPainter, rect: QRectF) -> None:
        """Draw tactical grid overlay."""
        # Save painter state
        painter.save()
        
        # Set up grid pen
        grid_pen = QPen(self._accent_color)
        grid_pen.setWidth(1)
        grid_opacity = GRID_OPACITY * self._animation_progress
        grid_color = QColor(self._accent_color)
        grid_color.setAlphaF(grid_opacity)
        grid_pen.setColor(grid_color)
        painter.setPen(grid_pen)
        
        # Draw horizontal grid lines
        grid_spacing = 20
        offset_y = self._grid_offset
        y = rect.top() + offset_y
        while y < rect.bottom():
            painter.drawLine(
                QPointF(rect.left(), y),
                QPointF(rect.right(), y)
            )
            y += grid_spacing
            
        # Draw vertical grid lines
        offset_x = self._grid_offset
        x = rect.left() + offset_x
        while x < rect.right():
            painter.drawLine(
                QPointF(x, rect.top()),
                QPointF(x, rect.bottom())
            )
            x += grid_spacing
        
        # Restore painter state
        painter.restore()

class LegendRenderStrategy(Enum):
    """Strategies for rendering legends"""
    STANDARD = auto()    # Single legend with full details
    COMPACT = auto()     # Condensed version with minimal details
    COMBINED = auto()    # Multiple legends in a single display
    CONTEXTUAL = auto()  # Dynamic based on visible data

class LegendConfig:
    """Enhanced configuration for a specific legend type"""
    
    def __init__(self, name: str, allowed_modes: List[str], enabled: bool = False):
        """Initialize legend configuration.
        
        Args:
            name: Legend identifier
            allowed_modes: List of modes where this legend can be shown
            enabled: Initial enabled state
        """
        self.name = name
        self.allowed_modes = set(allowed_modes)
        self.enabled = enabled
        self.colors: Dict[str, QColor] = {}
        self.labels: List[str] = []
        self.position: Optional[Tuple[float, float]] = None
        self.show_values = False
        self.priority = 0  # Higher priority legends are drawn first
        
        # Enhanced properties
        self.shape = LegendShape.SQUARE  # Default shape
        self.units = ""  # Units for values (e.g., "kg/m²")
        self.title = name.capitalize()  # Human-readable title
        self.render_strategy = LegendRenderStrategy.STANDARD
        self.data_type = name  # Type of data this legend represents
        
    def is_allowed_in_mode(self, mode: str) -> bool:
        """Check if legend is allowed in given mode."""
        return mode.upper() in {m.upper() for m in self.allowed_modes}
        
    def __repr__(self) -> str:
        return f"LegendConfig(name={self.name}, enabled={self.enabled}, modes={self.allowed_modes})"

class LegendManager:
    """Enhanced manager for radar display legends"""
    
    def __init__(self, radar_type: str):
        """Initialize legend manager.
        
        Args:
            radar_type: Type of radar (e.g. 'weather_radar')
        """
        self.radar_type = radar_type
        self._current_mode = None
        self._legend_configs: Dict[str, LegendConfig] = {}
        self._settings_manager = get_visual_settings_manager(radar_type)
        self._active_legend = None  # Currently active legend type
        self._render_strategies: Dict[LegendRenderStrategy, Callable] = {
            LegendRenderStrategy.STANDARD: self._render_standard_legend,
            LegendRenderStrategy.COMPACT: self._render_compact_legend,
            LegendRenderStrategy.COMBINED: self._render_combined_legend,
            LegendRenderStrategy.CONTEXTUAL: self._render_contextual_legend
        }
        
        # Create collapsible panel
        self._collapsible_panel = CollapsibleLegendPanel()
        self._last_click_pos = None
        self._last_click_time = 0
        
        # Enhanced color schemes for different data types
        
        # VIL data: Blue-Purple-Red gradient
        self._vil_colors = {
            'HIGH': QColor(204, 0, 0, 180),       # Deep Red
            'MEDIUM': QColor(136, 0, 204, 180),   # Purple
            'LOW': QColor(0, 68, 204, 180),       # Blue
            'MINIMAL': QColor(0, 170, 255, 180)   # Light Blue
        }
        
        # Precipitation: Blues, White, Purple, Magenta
        self._precipitation_colors = {
            'HEAVY_RAIN': QColor(0, 0, 204, 180),     # Dark Blue
            'RAIN': QColor(0, 102, 255, 180),         # Medium Blue
            'SNOW': QColor(255, 255, 255, 180),       # White
            'MIXED': QColor(136, 0, 170, 180),        # Purple
            'HAIL': QColor(255, 0, 255, 180)          # Magenta
        }
        
        # Storm cells: Yellow-Orange-Red gradient
        self._intensity_colors = {
            'SEVERE': QColor(255, 0, 0, 180),         # Bright Red
            'MODERATE': QColor(255, 136, 0, 180),     # Orange
            'LIGHT': QColor(255, 255, 0, 180),        # Yellow
            'VERY_LIGHT': QColor(0, 255, 0, 180)      # Green
        }
        
        # Turbulence: Green-Yellow-Red gradient
        self._turbulence_colors = {
            'SEVERE': QColor(255, 0, 0, 180),         # Bright Red
            'MODERATE': QColor(255, 255, 0, 180),     # Yellow
            'LIGHT': QColor(0, 255, 0, 180)           # Green
        }
        
        # Windshear: Amber-Red gradient
        self._windshear_colors = {
            'CRITICAL': QColor(255, 0, 0, 180),       # Bright Red
            'WARNING': QColor(255, 170, 0, 180),      # Amber
            'CAUTION': QColor(255, 255, 0, 180)       # Yellow
        }
        
        # Terrain elevation: Earth tones
        self._terrain_colors = {
            'MOUNTAIN': QColor(139, 69, 19, 180),     # Brown
            'HILL': QColor(0, 100, 0, 180),           # Dark Green
            'PLAIN': QColor(144, 238, 144, 180),      # Light Green
            'SEA_LEVEL': QColor(30, 144, 255, 180)    # Blue
        }
        
        # Initialize built-in legends with enhanced properties
        self._init_legends()
        logger.info(f"[LEGEND_MANAGER] Initialized enhanced manager for {radar_type}")
        
    def _init_legends(self) -> None:
        """Initialize built-in legend configurations with enhanced properties."""
        # VIL Legend - highest priority for SURVEILLANCE mode
        vil_legend = LegendConfig("vil", ["SURVEILLANCE", "MAPPING"], False)
        vil_legend.colors = self._vil_colors
        vil_legend.labels = ["High VIL", "Medium VIL", "Low VIL", "Minimal VIL"]
        vil_legend.priority = 100  # Highest priority
        vil_legend.shape = LegendShape.DIAMOND
        vil_legend.units = "kg/m²"
        vil_legend.title = "Vertically Integrated Liquid"
        vil_legend.data_type = "vil"
        self._legend_configs["vil"] = vil_legend
        
        # Precipitation Legend - high priority for SURVEILLANCE mode
        precip_legend = LegendConfig("precipitation", ["SURVEILLANCE", "MAPPING"], False)
        precip_legend.colors = self._precipitation_colors
        precip_legend.labels = ["Heavy Rain", "Rain", "Snow", "Mixed", "Hail"]
        precip_legend.priority = 90  # High priority
        precip_legend.shape = LegendShape.SQUARE
        precip_legend.units = "mm/hr"
        precip_legend.title = "Precipitation Type"
        precip_legend.data_type = "precipitation"
        self._legend_configs["precipitation"] = precip_legend
        
        # Intensity Scale Legend - medium priority
        intensity_legend = LegendConfig("intensity", ["SURVEILLANCE", "TURBULENCE", "WINDSHEAR"], False)
        intensity_legend.colors = self._intensity_colors
        intensity_legend.labels = ["Severe", "Moderate", "Light", "Very Light"]
        intensity_legend.priority = 50  # Medium priority
        intensity_legend.shape = LegendShape.CIRCLE
        intensity_legend.title = "Storm Cell Intensity"
        intensity_legend.data_type = "storm_cell"
        self._legend_configs["intensity"] = intensity_legend
        
        # Turbulence Legend - highest priority for TURBULENCE mode
        turbulence_legend = LegendConfig("turbulence", ["TURBULENCE", "SURVEILLANCE"], False)
        turbulence_legend.colors = self._turbulence_colors
        turbulence_legend.labels = ["Severe", "Moderate", "Light"]
        turbulence_legend.priority = 95  # Very high priority in TURBULENCE mode
        turbulence_legend.shape = LegendShape.TRIANGLE
        turbulence_legend.title = "Turbulence Severity"
        turbulence_legend.data_type = "turbulence"
        self._legend_configs["turbulence"] = turbulence_legend
        
        # Windshear Legend - highest priority for WINDSHEAR mode
        windshear_legend = LegendConfig("windshear", ["WINDSHEAR", "SURVEILLANCE"], False)
        windshear_legend.colors = self._windshear_colors
        windshear_legend.labels = ["Critical", "Warning", "Caution"]
        windshear_legend.priority = 95  # Very high priority in WINDSHEAR mode
        windshear_legend.shape = LegendShape.HEXAGON
        windshear_legend.title = "Windshear Risk"
        windshear_legend.data_type = "windshear"
        self._legend_configs["windshear"] = windshear_legend
        
        # Terrain Scale Legend - highest priority for MAPPING mode
        terrain_legend = LegendConfig("terrain", ["MAPPING"], False)
        terrain_legend.colors = self._terrain_colors
        terrain_legend.labels = ["Mountains", "Hills", "Plains", "Sea Level"]
        terrain_legend.priority = 75  # High priority
        terrain_legend.shape = LegendShape.GRADIENT
        terrain_legend.units = "ft"
        terrain_legend.title = "Terrain Elevation"
        terrain_legend.data_type = "terrain"
        self._legend_configs["terrain"] = terrain_legend
        
        logger.info("[LEGEND_MANAGER] Initialized enhanced legend configurations")
        
    def register_legend(self, config: LegendConfig) -> None:
        """Register a new legend configuration.
        
        Args:
            config: Legend configuration to register
        """
        self._legend_configs[config.name] = config
        logger.info(f"[LEGEND_MANAGER] Registered legend: {config.name}")
        
    def get_legend_config(self, name: str) -> Optional[LegendConfig]:
        """Get legend configuration by name."""
        return self._legend_configs.get(name)
        
    def get_active_legends(self, context: Optional[Dict[str, Any]] = None) -> List[LegendConfig]:
        """Get list of currently active legend configurations.
        
        Args:
            context: Optional context information to influence selection
            
        Returns:
            List of active legend configurations sorted by priority
        """
        """Get list of currently active legend configurations."""
        if not self._current_mode:
            return []
            
        # Get all legends that are enabled and allowed in current mode
        active_legends = [
            config for config in self._legend_configs.values()
            if config.enabled and config.is_allowed_in_mode(self._current_mode)
        ]
        
        # Sort by priority (highest first)
        active_legends.sort(key=lambda x: x.priority, reverse=True)
        
        return active_legends
    
    def _create_combined_legend_config(self, legend_configs: List[LegendConfig]) -> LegendConfig:
        """Create a combined legend configuration for multiple data types.
        
        Args:
            legend_configs: List of legend configurations to combine
            
        Returns:
            Combined legend configuration
        """
        # Create a new config with combined properties
        combined_config = LegendConfig("combined", [], True)
        combined_config.title = "Combined Data"
        
        # Track which data types are included
        included_types = []
        
        # Collect all colors and labels
        combined_config.colors = {}
        combined_config.labels = []
        
        # Keep track of which legend types are included
        for config in legend_configs:
            included_types.append(config.name.upper())
            
            # Add colors prefixed with data type
            for level, color in config.colors.items():
                key = f"{config.name.upper()}_{level}"
                combined_config.colors[key] = color
                
                # Add label with data type prefix
                if config.name == "vil":
                    label = f"VIL {level}"
                elif config.name == "precipitation":
                    label = f"PRECIP {level}"
                else:
                    label = f"{config.name.upper()} {level}"
                combined_config.labels.append(label)
        
        # Set title based on included types
        if len(included_types) == 2:
            combined_config.title = f"{included_types[0]} & {included_types[1]} DATA"
        elif len(included_types) > 2:
            combined_config.title = f"MULTI-DATA DISPLAY"
        
        # Set to use the combined rendering strategy
        combined_config.render_strategy = LegendRenderStrategy.COMBINED
        
        return combined_config

    def get_primary_legend(self, context: Optional[Dict[str, Any]] = None) -> Optional[LegendConfig]:
        """Get the primary legend for the current mode.
        
        Args:
            context: Optional context information to influence selection
            
        Returns:
            Primary legend configuration or None if no legends are active
        """
        """Get the primary legend for the current mode."""
        active_legends = self.get_active_legends()
        if not active_legends:
            return None
            
        # If we have an explicitly set active legend, use that
        if self._active_legend and self._active_legend in self._legend_configs:
            config = self._legend_configs[self._active_legend]
            if config.enabled and config.is_allowed_in_mode(self._current_mode):
                return config
                
        # Otherwise return the highest priority legend
        return active_legends[0] if active_legends else None
        
    def set_active_legend(self, legend_type: str) -> bool:
        """Set the active legend type.
        
        Args:
            legend_type: Type of legend to set as active
            
        Returns:
            True if successful, False if legend not found or not allowed
        """
        if legend_type not in self._legend_configs:
            logger.warning(f"[LEGEND_MANAGER] Legend type not found: {legend_type}")
            return False
            
        config = self._legend_configs[legend_type]
        if not self._current_mode or not config.is_allowed_in_mode(self._current_mode):
            logger.warning(f"[LEGEND_MANAGER] Legend {legend_type} not allowed in mode {self._current_mode}")
            return False
            
        self._active_legend = legend_type
        logger.info(f"[LEGEND_MANAGER] Set active legend to {legend_type}")
        return True
        
    def update_legend_state(self, mode: str) -> None:
        """Update legend states based on mode.
        
        Args:
            mode: Current radar mode
        """
        self._current_mode = mode.upper()
        settings = self._settings_manager.get_settings()
        
        # Update each legend's enabled state based on mode and settings
        for name, config in self._legend_configs.items():
            if config.is_allowed_in_mode(self._current_mode):
                # Check settings for specific legend enabled state
                setting_key = f"show_{name}_legend"
                config.enabled = settings.get(setting_key, False)
                
                # Special handling for values
                value_key = f"show_{name}_values"
                config.show_values = settings.get(value_key, False)
            else:
                config.enabled = False
                
        # Set appropriate active legend based on mode with enhanced logic
        if self._current_mode == "SURVEILLANCE":
            # In SURVEILLANCE mode, prioritize VIL, then precipitation, then intensity
            if "vil" in self._legend_configs and self._legend_configs["vil"].enabled:
                self._active_legend = "vil"
            elif "precipitation" in self._legend_configs and self._legend_configs["precipitation"].enabled:
                self._active_legend = "precipitation"
            elif "intensity" in self._legend_configs and self._legend_configs["intensity"].enabled:
                self._active_legend = "intensity"
        elif self._current_mode == "MAPPING":
            # In MAPPING mode, prioritize terrain, then VIL
            if "terrain" in self._legend_configs and self._legend_configs["terrain"].enabled:
                self._active_legend = "terrain"
            elif "vil" in self._legend_configs and self._legend_configs["vil"].enabled:
                self._active_legend = "vil"
        elif self._current_mode == "TURBULENCE":
            # In TURBULENCE mode, prioritize turbulence data
            if "turbulence" in self._legend_configs and self._legend_configs["turbulence"].enabled:
                self._active_legend = "turbulence"
            elif "intensity" in self._legend_configs and self._legend_configs["intensity"].enabled:
                self._active_legend = "intensity"
        elif self._current_mode == "WINDSHEAR":
            # In WINDSHEAR mode, prioritize windshear data
            if "windshear" in self._legend_configs and self._legend_configs["windshear"].enabled:
                self._active_legend = "windshear"
            elif "intensity" in self._legend_configs and self._legend_configs["intensity"].enabled:
                self._active_legend = "intensity"
                
        logger.info(f"[LEGEND_MANAGER] Updated legend states for mode: {mode}, active legend: {self._active_legend}")
        
    def draw_legend(self, painter: QPainter, rect: QRectF, legend_type: Optional[str] = None) -> None:
        """Draw a specific legend type or the primary legend if none specified.
        
        Args:
            painter: QPainter instance
            rect: Drawing rectangle
            legend_type: Type of legend to draw, or None to draw primary legend
        """
        # If no specific legend requested, use primary legend
        if legend_type is None:
            config = self.get_primary_legend()
            if not config:
                return
            legend_type = config.name
        else:
            config = self._legend_configs.get(legend_type)
            if not config or not config.enabled:
                return
            
        # Use the appropriate rendering strategy
        strategy = config.render_strategy
        render_func = self._render_strategies.get(strategy, self._render_standard_legend)
        render_func(painter, rect, config)
            
    def handle_click(self, pos: QPointF) -> bool:
        """Handle mouse click at the specified position.
        
        Args:
            pos: Click position
            
        Returns:
            True if click was handled, False otherwise
        """
        # Store click position and time
        self._last_click_pos = pos
        self._last_click_time = time.time()
        
        # Log the click position for debugging
        logger.warning(f"[LEGEND_MANAGER] Handling click at position: ({pos.x():.1f}, {pos.y():.1f})")
        
        # Update panel layout with a more accurate display size
        # The standard size is 800x600 based on the widget settings
        self._collapsible_panel.update_layout(QRectF(0, 0, 800, 600))
        
        # Log the tab rectangle for debugging
        tab_rect = self._collapsible_panel._tab_rect
        logger.warning(f"[LEGEND_MANAGER] Tab rectangle: ({tab_rect.left():.1f}, {tab_rect.top():.1f}, {tab_rect.width():.1f}, {tab_rect.height():.1f})")
        
        # Check if click is within tab rectangle
        if tab_rect.contains(pos):
            logger.warning(f"[LEGEND_MANAGER] Click is within tab rectangle")
        else:
            logger.warning(f"[LEGEND_MANAGER] Click is outside tab rectangle")
        
        # Handle click with panel
        result = self._collapsible_panel.handle_click(pos)
        logger.warning(f"[LEGEND_MANAGER] Click handled: {result}")
        return result
    
    def draw_all_legends(self, painter: QPainter, rect: QRectF, strategy: str = "standard") -> None:
        """Draw all active legends using the specified strategy with style animations.
        
        Args:
            painter: QPainter instance
            rect: Drawing rectangle
            strategy: Rendering strategy ("standard", "compact", "combined", "contextual")
        """
        # Get active legends sorted by priority
        active_legends = self.get_active_legends()
        
        if not active_legends:
            return
        
        # Update panel layout
        self._collapsible_panel.update_layout(rect)
        
        # Check if we should show multiple legends based on active data types
        multiple_active_types = len(active_legends) > 1
        
        # If we have multiple active data types, set a special combined config
        if multiple_active_types:
            # Create a combined config for all active legends
            combined_config = self._create_combined_legend_config(active_legends)
            self._collapsible_panel.set_legend_config(combined_config)
            
            # Logging for combined legends
            current_time = time.time()
            if not hasattr(self, '_last_multiple_legend_log_time'):
                self._last_multiple_legend_log_time = 0
                
            if current_time - self._last_multiple_legend_log_time >= 5.0:
                legend_names = [config.name for config in active_legends]
                logger.warning(f"[LEGEND_MANAGER] Drawing combined legend with {len(legend_names)} types: {legend_names}")
                self._last_multiple_legend_log_time = current_time
        else:
            # Set the highest priority legend as the active one
            highest_priority_legend = active_legends[0]
            self._collapsible_panel.set_legend_config(highest_priority_legend)
            
            # Throttle logging - only log once every 5 seconds
            if not hasattr(self, '_last_legend_log_time'):
                self._last_legend_log_time = 0
                
            current_time = time.time()
            if current_time - self._last_legend_log_time >= 5.0:
                logger.debug(f"[LEGEND_MANAGER] Drawing collapsible panel with {highest_priority_legend.name} legend")
                self._last_legend_log_time = current_time
        
        # Draw the collapsible panel
        self._collapsible_panel.draw(painter, self)
            
    def _render_standard_legend(self, painter: QPainter, rect: QRectF, config: LegendConfig) -> None:
        """Render a legend using the standard strategy.
        
        Args:
            painter: QPainter instance
            rect: Drawing rectangle
            config: Legend configuration
        """
        try:
            # Draw legend title
            title_rect = QRectF(
                rect.right() - 100,
                rect.center().y() - rect.height() * 0.25,
                90,
                20
            )
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(
                title_rect,
                Qt.AlignmentFlag.AlignCenter,
                config.title
            )
            
            # Draw legend items
            start_y = title_rect.bottom() + 5
            legend_item_height = 20
            
            for i, (level, color) in enumerate(config.colors.items()):
                # Draw color box with appropriate shape
                box_rect = QRectF(
                    rect.right() - 20 - 10,
                    start_y + i * legend_item_height,
                    20,
                    legend_item_height - 2
                )
                
                # Draw shape based on legend type
                self._draw_shape(painter, box_rect, color, config.shape)
                
                # Draw label with units if applicable
                label_text = config.labels[i] if i < len(config.labels) else level
                if config.units and config.show_values:
                    # Add example value with units
                    if config.name == "vil":
                        example_values = {"HIGH": "35", "MEDIUM": "25", "LOW": "15", "MINIMAL": "5"}
                        value = example_values.get(level, "")
                        if value:
                            label_text += f" ({value} {config.units})"
                    elif config.name == "precipitation":
                        example_values = {"HEAVY_RAIN": "50", "RAIN": "25", "SNOW": "15", "MIXED": "20", "HAIL": "30"}
                        value = example_values.get(level, "")
                        if value:
                            label_text += f" ({value} {config.units})"
                
                label_rect = QRectF(
                    box_rect.left() - 90,
                    box_rect.top(),
                    85,
                    legend_item_height
                )
                painter.drawText(
                    label_rect,
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    label_text
                )
                
        except Exception as e:
            logger.error(f"[LEGEND_MANAGER] Error rendering standard legend: {str(e)}")
            
    def _render_compact_legend(self, painter: QPainter, rect: QRectF, config: LegendConfig) -> None:
        """Render a legend using the compact strategy.
        
        Args:
            painter: QPainter instance
            rect: Drawing rectangle
            config: Legend configuration
        """
        try:
            # Draw compact legend with just colors and minimal labels
            title_rect = QRectF(
                rect.right() - 80,
                rect.center().y() - rect.height() * 0.15,
                70,
                20
            )
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(
                title_rect,
                Qt.AlignmentFlag.AlignCenter,
                config.title
            )
            
            # Draw compact color boxes in a row
            box_size = 15
            start_x = rect.right() - (len(config.colors) * box_size) - 10
            start_y = title_rect.bottom() + 5
            
            for i, (level, color) in enumerate(config.colors.items()):
                box_rect = QRectF(
                    start_x + (i * box_size),
                    start_y,
                    box_size - 2,
                    box_size - 2
                )
                painter.fillRect(box_rect, color)
                painter.setPen(Qt.GlobalColor.white)
                painter.drawRect(box_rect)
        except Exception as e:
            logger.error(f"[LEGEND_MANAGER] Error rendering compact legend: {str(e)}")
            
    def _render_combined_legend(self, painter: QPainter, rect: QRectF, config: LegendConfig) -> None:
        """Render a legend using the combined strategy with multiple data types.
        
        Args:
            painter: QPainter instance
            rect: Drawing rectangle
            config: Legend configuration
        """
        try:
            # Save painter state
            painter.save()
            
            # Set up style font
            font = QFont("Arial", 9)
            font.setBold(True)
            painter.setFont(font)
            
            # Draw legend title with style header
            title_rect = QRectF(
                rect.left(),
                rect.top(),
                rect.width(),
                25
            )
            
            # Draw title background
            title_path = QPainterPath()
            title_path.moveTo(title_rect.left(), title_rect.top())
            title_path.lineTo(title_rect.right() - 10, title_rect.top())
            title_path.lineTo(title_rect.right(), title_rect.top() + 10)
            title_path.lineTo(title_rect.right(), title_rect.bottom())
            title_path.lineTo(title_rect.left(), title_rect.bottom())
            title_path.closeSubpath()
            
            # Fill with accent color - purple for combined data
            accent_color = QColor(128, 0, 255, 180)  # Purple
            painter.fillPath(title_path, QColor(0, 0, 0, 180))
            
            # Draw title border
            pen = QPen(accent_color)
            pen.setWidth(BORDER_WIDTH)
            painter.setPen(pen)
            painter.drawPath(title_path)
            
            # Draw title text
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(
                title_rect,
                Qt.AlignmentFlag.AlignCenter,
                config.title
            )
            
            # Draw legend items with style formatting
            content_rect = QRectF(
                rect.left(),
                title_rect.bottom() + 5,
                rect.width(),
                rect.height() - title_rect.height() - 5
            )
            
            # Calculate item height based on available space and number of items
            item_count = len(config.labels)
            item_height = min(20, (content_rect.height() - 10) / max(1, item_count))
            
            # Group items by data type
            data_types = {}
            for level, color in config.colors.items():
                if '_' in level:
                    data_type, value = level.split('_', 1)
                    if data_type not in data_types:
                        data_types[data_type] = []
                    data_types[data_type].append((value, color))
            
            # Draw section headers and items for each data type
            y_offset = content_rect.top()
            
            for data_type, items in data_types.items():
                # Skip if no items
                if not items:
                    continue
                
                # Draw data type header
                header_rect = QRectF(
                    content_rect.left(),
                    y_offset,
                    content_rect.width(),
                    18
                )
                
                # Fill header background
                header_bg = QLinearGradient(
                    header_rect.topLeft(),
                    header_rect.bottomLeft()
                )
                bg_color = QColor(40, 40, 40, 180)
                header_bg.setColorAt(0.0, bg_color)
                header_bg.setColorAt(1.0, QColor(bg_color.red(), bg_color.green(), bg_color.blue(), 120))
                painter.fillRect(header_rect, header_bg)
                
                # Draw header text
                painter.setPen(Qt.GlobalColor.white)
                header_text = "VIL" if data_type == "VIL" else data_type
                painter.drawText(
                    header_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    f"{header_text} DATA"
                )
                
                y_offset += header_rect.height() + 2
                
                # Draw items for this data type
                for i, (level, color) in enumerate(items):
                    # Item rectangle
                    item_rect = QRectF(
                        content_rect.left() + 5,
                        y_offset,
                        content_rect.width() - 10,
                        item_height - 2
                    )
                    
                    # Draw item background
                    item_bg = QLinearGradient(
                        item_rect.topLeft(),
                        item_rect.bottomLeft()
                    )
                    bg_color = QColor(0, 0, 0, 80)
                    item_bg.setColorAt(0.0, bg_color)
                    item_bg.setColorAt(1.0, QColor(bg_color.red(), bg_color.green(), bg_color.blue(), 40))
                    painter.fillRect(item_rect, item_bg)
                    
                    # Draw color sample with appropriate shape
                    shape_rect = QRectF(
                        item_rect.left() + 5,
                        item_rect.top() + (item_rect.height() - 15) / 2,
                        15,
                        15
                    )
                    
                    # Choose shape based on data type
                    if "VIL" in data_type:
                        shape = LegendShape.DIAMOND
                    elif "PRECIP" in data_type:
                        shape = LegendShape.SQUARE
                    else:
                        shape = LegendShape.CIRCLE
                        
                    self._draw_shape(painter, shape_rect, color, shape)
                    
                    # Draw label
                    label_rect = QRectF(
                        shape_rect.right() + 10,
                        item_rect.top(),
                        item_rect.width() - shape_rect.width() - 20,
                        item_rect.height()
                    )
                    
                    painter.setPen(Qt.GlobalColor.white)
                    painter.drawText(
                        label_rect,
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        level
                    )
                    
                    y_offset += item_height
                
                # Add spacing between data type sections
                y_offset += 5
            
            # Restore painter state
            painter.restore()
            
        except Exception as e:
            logger.error(f"[LEGEND_MANAGER] Error rendering combined legend: {str(e)}")
            logger.error(traceback.format_exc())
            
    def _render_contextual_legend(self, painter: QPainter, rect: QRectF, config: LegendConfig) -> None:
        """Render a legend using the contextual strategy.
        
        Args:
            painter: QPainter instance
            rect: Drawing rectangle
            config: Legend configuration
        """
        try:
            # Simplified implementation - just use standard rendering for now
            self._render_standard_legend(painter, rect, config)
        except Exception as e:
            logger.error(f"[LEGEND_MANAGER] Error rendering contextual legend: {str(e)}")
            
    def _render_combined_legends(self, painter: QPainter, rect: QRectF, configs: List[LegendConfig]) -> None:
        """Render multiple legends in a combined format.
        
        Args:
            painter: QPainter instance
            rect: Drawing rectangle
            configs: List of legend configurations to render
        """
        try:
            # For now, just render the first legend
            if configs:
                self._render_standard_legend(painter, rect, configs[0])
        except Exception as e:
            logger.error(f"[LEGEND_MANAGER] Error rendering combined legends: {str(e)}")
            
    def _render_contextual_legends(self, painter: QPainter, rect: QRectF, configs: List[LegendConfig]) -> None:
        """Render legends based on context.
        
        Args:
            painter: QPainter instance
            rect: Drawing rectangle
            configs: List of legend configurations to render
        """
        try:
            # For now, just render the first legend
            if configs:
                self._render_standard_legend(painter, rect, configs[0])
        except Exception as e:
            logger.error(f"[LEGEND_MANAGER] Error rendering contextual legends: {str(e)}")
            
    def _draw_shape(self, painter: QPainter, rect: QRectF, color: QColor, shape: LegendShape) -> None:
        """Draw a shape with the specified color.
        
        Args:
            painter: QPainter instance
            rect: Drawing rectangle
            color: Shape color
            shape: Shape type
        """
        try:
            center = rect.center()
            width = rect.width()
            height = rect.height()
            
            # Save painter state
            painter.save()
            
            # Set up painter
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.GlobalColor.white)
            
            # Draw shape based on type
            if shape == LegendShape.SQUARE:
                painter.drawRect(rect)
            elif shape == LegendShape.CIRCLE:
                painter.drawEllipse(rect)
            elif shape == LegendShape.DIAMOND:
                path = QPainterPath()
                path.moveTo(center.x(), rect.top())
                path.lineTo(rect.right(), center.y())
                path.lineTo(center.x(), rect.bottom())
                path.lineTo(rect.left(), center.y())
                path.closeSubpath()
                painter.drawPath(path)
            elif shape == LegendShape.TRIANGLE:
                path = QPainterPath()
                path.moveTo(center.x(), rect.top())
                path.lineTo(rect.right(), rect.bottom())
                path.lineTo(rect.left(), rect.bottom())
                path.closeSubpath()
                painter.drawPath(path)
            elif shape == LegendShape.HEXAGON:
                path = QPainterPath()
                path.moveTo(rect.left() + width * 0.25, rect.top())
                path.lineTo(rect.right() - width * 0.25, rect.top())
                path.lineTo(rect.right(), center.y())
                path.lineTo(rect.right() - width * 0.25, rect.bottom())
                path.lineTo(rect.left() + width * 0.25, rect.bottom())
                path.lineTo(rect.left(), center.y())
                path.closeSubpath()
                painter.drawPath(path)
            elif shape == LegendShape.GRADIENT:
                # Draw a gradient rectangle
                gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
                gradient.setColorAt(0.0, color)
                gradient.setColorAt(1.0, QColor(color.red() // 2, color.green() // 2, color.blue() // 2))
                painter.fillRect(rect, gradient)
                painter.drawRect(rect)
            elif shape == LegendShape.DASHED:
                # Draw a dashed outline
                pen = QPen(Qt.GlobalColor.white)
                pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawRect(rect)
            elif shape == LegendShape.LIGHTNING:
                # Draw a lightning bolt
                path = QPainterPath()
                path.moveTo(center.x(), rect.top())
                path.lineTo(rect.left() + width * 0.4, center.y())
                path.lineTo(center.x() - width * 0.1, center.y())
                path.lineTo(center.x(), rect.bottom())
                path.lineTo(rect.right() - width * 0.4, center.y())
                path.lineTo(center.x() + width * 0.1, center.y())
                path.closeSubpath()
                painter.drawPath(path)
            elif shape == LegendShape.CRYSTAL:
                # Draw a crystal shape
                path = QPainterPath()
                path.moveTo(center.x(), rect.top())
                path.lineTo(rect.right() - width * 0.2, center.y() - height * 0.2)
                path.lineTo(rect.right(), center.y() + height * 0.2)
                path.lineTo(center.x(), rect.bottom())
                path.lineTo(rect.left(), center.y() + height * 0.2)
                path.lineTo(rect.left() + width * 0.2, center.y() - height * 0.2)
                path.closeSubpath()
                painter.drawPath(path)
            else:
                # Default to rectangle
                painter.drawRect(rect)
                
            # Restore painter state
            painter.restore()
        except Exception as e:
            logger.error(f"[LEGEND_MANAGER] Error drawing shape: {str(e)}")
            
    def _render_legend(self, painter: QPainter, rect: QRectF, config: LegendConfig) -> None:
        """Render a legend using the style tactical design.
        
        Args:
            painter: QPainter instance
            rect: Drawing rectangle
            config: Legend configuration
        """
        try:
            # Save painter state
            painter.save()
            
            # Set up style font
            font = QFont("Arial", 9)
            font.setBold(True)
            painter.setFont(font)
            
            # Draw legend title with style header
            title_rect = QRectF(
                rect.left(),
                rect.top(),
                rect.width(),
                25
            )
            
            # Draw title background
            title_path = QPainterPath()
            title_path.moveTo(title_rect.left(), title_rect.top())
            title_path.lineTo(title_rect.right() - 10, title_rect.top())
            title_path.lineTo(title_rect.right(), title_rect.top() + 10)
            title_path.lineTo(title_rect.right(), title_rect.bottom())
            title_path.lineTo(title_rect.left(), title_rect.bottom())
            title_path.closeSubpath()
            
            # Fill with accent color
            accent_color = QColor(0, 0, 0, 180)
            painter.fillPath(title_path, accent_color)
            
            # Draw title border
            pen = QPen(Qt.GlobalColor.white)
            pen.setWidth(BORDER_WIDTH)
            painter.setPen(pen)
            painter.drawPath(title_path)
            
            # Draw title text
            painter.setPen(Qt.GlobalColor.white)
            
            # Format title in style
            style_title = f"{config.title.upper()} DATA"
            if config.name == "vil":
                style_title = "VIL DATA"
            elif config.name == "precipitation":
                style_title = "PRECIP DATA"
            elif config.name == "intensity":
                style_title = "STORM INTENSITY"
            elif config.name == "turbulence":
                style_title = "TURBULENCE LEVELS"
            elif config.name == "windshear":
                style_title = "WINDSHEAR ALERT"
            elif config.name == "terrain":
                style_title = "TERRAIN PROFILE"
                
            painter.drawText(
                title_rect,
                Qt.AlignmentFlag.AlignCenter,
                style_title
            )
            
            # Draw legend items with style formatting
            content_rect = QRectF(
                rect.left(),
                title_rect.bottom() + 5,
                rect.width(),
                rect.height() - title_rect.height() - 5
            )
            
            # Calculate item height based on available space and number of items
            item_count = len(config.colors)
            item_height = min(25, (content_rect.height() - 10) / item_count)
            
            # Draw each legend item
            for i, (level, color) in enumerate(config.colors.items()):
                # Item rectangle
                item_rect = QRectF(
                    content_rect.left() + 5,
                    content_rect.top() + i * item_height,
                    content_rect.width() - 10,
                    item_height - 2
                )
                
                # Draw item background with subtle gradient
                item_bg = QLinearGradient(
                    item_rect.topLeft(),
                    item_rect.bottomLeft()
                )
                bg_color = QColor(0, 0, 0, 100)
                item_bg.setColorAt(0.0, bg_color)
                item_bg.setColorAt(1.0, QColor(bg_color.red(), bg_color.green(), bg_color.blue(), 50))
                painter.fillRect(item_rect, item_bg)
                
                # Draw shape based on legend type
                shape_rect = QRectF(
                    item_rect.left() + 5,
                    item_rect.top() + (item_rect.height() - 15) / 2,
                    15,
                    15
                )
                self._draw_shape(painter, shape_rect, color, config.shape)
                
                # Draw label with style formatting
                label_text = config.labels[i] if i < len(config.labels) else level
                
                # Format label in style
                if config.name == "vil":
                    # Example: "HIGH [35+]" with "THREAT LEVEL: SEVERE" below
                    threat_levels = {
                        "HIGH": "SEVERE",
                        "MEDIUM": "MODERATE",
                        "LOW": "CAUTION",
                        "MINIMAL": "MINIMAL"
                    }
                    
                    # Value ranges
                    value_ranges = {
                        "HIGH": "35+",
                        "MEDIUM": "20-35",
                        "LOW": "10-20",
                        "MINIMAL": "<10"
                    }
                    
                    # Primary label with value range
                    primary_label = f"{level} [{value_ranges.get(level, '')}]"
                    
                    # Secondary label with threat level
                    secondary_label = f"THREAT LEVEL: {threat_levels.get(level, level)}"
                    
                    # Draw primary label
                    primary_rect = QRectF(
                        shape_rect.right() + 10,
                        item_rect.top(),
                        item_rect.width() - shape_rect.width() - 20,
                        item_rect.height() / 2
                    )
                    painter.drawText(
                        primary_rect,
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                        primary_label
                    )
                    
                    # Draw secondary label
                    secondary_rect = QRectF(
                        shape_rect.right() + 10,
                        item_rect.top() + item_rect.height() / 2,
                        item_rect.width() - shape_rect.width() - 20,
                        item_rect.height() / 2
                    )
                    
                    # Use smaller font for secondary label
                    small_font = QFont(font)
                    small_font.setPointSize(7)
                    painter.setFont(small_font)
                    painter.drawText(
                        secondary_rect,
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                        secondary_label
                    )
                    
                    # Restore font
                    painter.setFont(font)
                else:
                    # For other legend types, just draw the label
                    label_rect = QRectF(
                        shape_rect.right() + 10,
                        item_rect.top(),
                        item_rect.width() - shape_rect.width() - 20,
                        item_rect.height()
                    )
                    painter.drawText(
                        label_rect,
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        label_text
                    )
            
            # Restore painter state
            painter.restore()
            
        except Exception as e:
            logger.error(f"[LEGEND_MANAGER] Error rendering legend: {str(e)}")
            logger.error(traceback.format_exc())
            
    def _draw_vil_legend(self, painter: QPainter, rect: QRectF, config: LegendConfig) -> None:
        """Draw VIL legend."""
        try:
            vil_start_y = rect.center().y() + rect.height() * 0.1
            legend_item_height = 20
            
            for i, (level, color) in enumerate(config.colors.items()):
                # Draw color box
                box_rect = QRectF(
                    rect.right() - 20 - 10,
                    vil_start_y + i * legend_item_height,
                    20,
                    legend_item_height - 2
                )
                painter.fillRect(box_rect, color)
                painter.setPen(Qt.GlobalColor.white)
                painter.drawRect(box_rect)
                
                # Draw label
                label_rect = QRectF(
                    box_rect.left() - 70,
                    box_rect.top(),
                    65,
                    legend_item_height
                )
                painter.drawText(
                    label_rect,
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    f"VIL {level}"
                )
                
        except Exception as e:
            logger.error(f"[LEGEND_MANAGER] Error drawing VIL legend: {str(e)}")
            
    def _draw_intensity_legend(self, painter: QPainter, rect: QRectF, config: LegendConfig) -> None:
        """Draw intensity scale legend."""
        try:
            scale_width = 20
            scale_height = rect.height() * 0.3
            scale_rect = QRectF(
                rect.right() - scale_width - 10,
                rect.center().y() - scale_height/2,
                scale_width,
                scale_height
            )
            
            # Draw gradient
            gradient = QLinearGradient(
                scale_rect.topLeft(),
                scale_rect.bottomLeft()
            )
            gradient.setColorAt(0.0, config.colors['SEVERE'])
            gradient.setColorAt(0.3, config.colors['MODERATE'])
            gradient.setColorAt(0.6, config.colors['LIGHT'])
            gradient.setColorAt(1.0, config.colors['VERY_LIGHT'])
            
            painter.fillRect(scale_rect, gradient)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawRect(scale_rect)
            
            # Draw labels
            label_width = 60
            painter.drawText(
                QRectF(scale_rect.left() - label_width, scale_rect.top() - 20, label_width, 20),
                Qt.AlignmentFlag.AlignRight,
                "Severe"
            )
            painter.drawText(
                QRectF(scale_rect.left() - label_width, scale_rect.bottom(), label_width, 20),
                Qt.AlignmentFlag.AlignRight,
                "Light"
            )
            
        except Exception as e:
            logger.error(f"[LEGEND_MANAGER] Error drawing intensity legend: {str(e)}")
            
    def _draw_terrain_legend(self, painter: QPainter, rect: QRectF, config: LegendConfig) -> None:
        """Draw terrain elevation legend."""
        try:
            scale_width = 20
            scale_height = rect.height() * 0.6
            scale_rect = QRectF(
                rect.right() - scale_width - 10,
                rect.top() + (rect.height() - scale_height)/2,
                scale_width,
                scale_height
            )
            
            # Draw gradient
            gradient = QLinearGradient(
                scale_rect.topLeft(),
                scale_rect.bottomLeft()
            )
            gradient.setColorAt(0.0, config.colors['MOUNTAIN'])
            gradient.setColorAt(0.3, config.colors['HILL'])
            gradient.setColorAt(0.6, config.colors['PLAIN'])
            gradient.setColorAt(1.0, config.colors['SEA_LEVEL'])
            
            painter.fillRect(scale_rect, gradient)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawRect(scale_rect)
            
            # Draw labels
            label_width = 80
            for i, label in enumerate(config.labels):
                y_pos = scale_rect.top() + (i * scale_height / (len(config.labels) - 1))
                painter.drawText(
                    QRectF(scale_rect.left() - label_width, y_pos - 10, label_width, 20),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    label
                )
                
        except Exception as e:
            logger.error(f"[LEGEND_MANAGER] Error drawing terrain legend: {str(e)}")

# Global instance
_legend_manager = None

def get_legend_manager(radar_type: str = 'weather_radar'):
    """Get global LegendManager instance."""
    global _legend_manager
    if _legend_manager is None:
        _legend_manager = LegendManager(radar_type)
    return _legend_manager

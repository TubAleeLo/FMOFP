from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPaintEvent, QPen, QBrush
from PyQt6.QtCore import Qt, QTimer, QEvent, QMetaObject
from enum import Enum, IntEnum
import traceback
from Utils.logger.sys_logger import get_logger
from .visual.theme_manager import get_theme_manager, DisplayTheme
from .visual.effects import VisualEffects

logger = get_logger()

class DisplayType(Enum):
    PFD = "Primary Flight Display"
    MFD = "Multi-Function Display"
    EICAS = "Engine Indicating and Crew Alerting System"
    RADAR = "Radar Display"
    TSD = "Tactical Situation Display"
    SMS = "Stores Management System"
    HUD = "Head-Up Display"

class DisplayMode(IntEnum):
    DAY = 1
    NIGHT = 2
    NVG = 3

    @property
    def display_name(self):
        return {
            self.DAY: "Day Mode",
            self.NIGHT: "Night Mode",
            self.NVG: "Night Vision Mode"
        }[self]

class DisplayPage(Enum):
    NAV = "Navigation"
    RADAR = "Radar"
    WEAPONS = "Weapons"
    SYSTEMS = "Systems"
    COMMS = "Communications"
    SETTINGS = "Settings"
    ENGINE = "Engine"
    MISSION = "Mission"

class BaseDisplay(QWidget):
    def __init__(self, display_type, parent=None):
        logger.debug(f"Initializing {display_type.value} display")
        super().__init__(parent)  # Allow parent to be specified

        # Basic properties
        self.display_type = display_type
        self.display_mode = DisplayMode.DAY
        self._running = False
        self._paint_error = False
        self._error_message = ""
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(16)  # ~60 FPS
        self._update_timer.timeout.connect(self._safe_update)

        # Window dragging support (only used for top-level windows)
        self._dragging = False
        self._drag_position = None

        # Theme manager and visual effects
        self._theme_manager = get_theme_manager()
        self._visual_effects = VisualEffects()

        # Colors - will be updated from theme
        self.hud_color = QColor(0, 255, 200, 200)
        self.warning_color = QColor(255, 0, 0, 200)
        self.caution_color = QColor(255, 255, 0, 200)
        self.background_color = QColor(0, 0, 0)  # Black background

        # Update colors from theme
        self.update_colors_from_theme()

        # Set up the display
        self.setup_display()

        # Install event filter
        self.installEventFilter(self)

    def update_colors_from_theme(self):
        """Update display colors from current theme"""
        self.hud_color = self._theme_manager.get_color("hud")
        self.warning_color = self._theme_manager.get_color("warning")
        self.caution_color = self._theme_manager.get_color("caution")
        self.background_color = self._theme_manager.get_color("background")

    def set_theme(self, theme: DisplayTheme):
        """Set display theme and update"""
        if self._theme_manager.set_theme(theme):
            self.update_colors_from_theme()
            self._safe_update()
            return True
        return False

    def setup_display(self):
        """Set up the display window with proper flags and attributes"""
        logger.debug(f"{self.display_type.value}: Setting up display")

        # Only set window flags if this is a top-level window (no parent)
        if self.parent() is None:
            # Set window flags for standalone display
            self.setWindowFlags(
                Qt.WindowType.Window |              # Regular window
                Qt.WindowType.WindowStaysOnTopHint  # Stay on top
            )

            # Configure window title and geometry for standalone window
            self.setWindowTitle(str(self.display_type.value))
            self.setGeometry(100, 100, 800, 600)

        # Set window attributes for optimal rendering
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        # Only set this attribute for top-level windows
        if self.parent() is None:
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        # Set minimum size
        self.setMinimumSize(800, 600)

        # Set up palette for background
        palette = self.palette()
        palette.setColor(self.backgroundRole(), self.background_color)
        self.setPalette(palette)

        # Set focus policy
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Enable mouse tracking
        self.setMouseTracking(True)

    def _safe_update(self):
        """Safely request a display update"""
        if self._running and self.isVisible():
            # Use QMetaObject to ensure update happens in main thread
            QMetaObject.invokeMethod(self, "update", Qt.ConnectionType.QueuedConnection)

    def start(self):
        """Start the display"""
        logger.debug(f"{self.display_type.value}: Starting display")
        self._running = True
        self._update_timer.start()

        # Only show and raise if this is a top-level window
        if self.parent() is None:
            self.show()
            self.raise_()

    def stop(self):
        """Stop the display"""
        logger.debug(f"{self.display_type.value}: Stopping display")
        self._running = False
        self._update_timer.stop()
        self.hide()

    def is_running(self):
        """Check if display is running"""
        return self._running

    def update_display(self):
        """Request display update"""
        self._safe_update()

    def set_mode(self, mode: DisplayMode):
        """Set display mode and update"""
        self.display_mode = mode
        self._safe_update()

    def paint_display(self, painter: QPainter):
        """Override in derived classes to paint specific display content"""
        pass

    def paintEvent(self, event: QPaintEvent):
        """Handle paint event with proper error handling"""
        if not self._running:
            return

        painter = QPainter()
        try:
            # Begin painting
            success = painter.begin(self)
            if not success:
                logger.error("Failed to begin painting")
                return

            # Set rendering hints
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

            # Save state
            painter.save()

            try:
                # Fill background
                painter.fillRect(event.rect(), self.background_color)

                if self._paint_error:
                    # Paint error message with enhanced visuals
                    use_gradients = self._theme_manager.get_style_param("use_gradients", False)
                    if use_gradients:
                        self._visual_effects.draw_enhanced_text(
                            painter, event.rect(),
                            Qt.AlignmentFlag.AlignCenter,
                            self._error_message,
                            glow=True,
                            glow_color=self.warning_color
                        )
                    else:
                        painter.setPen(self.warning_color)
                        painter.drawText(event.rect(), Qt.AlignmentFlag.AlignCenter, self._error_message)
                else:
                    # Paint display content
                    self.paint_display(painter)

            except Exception as e:
                logger.error(f"Error in paint_display: {str(e)}")
                logger.error(traceback.format_exc())
                self._paint_error = True
                self._error_message = f"Display Error: {str(e)}"
                painter.setPen(self.warning_color)
                painter.drawText(event.rect(), Qt.AlignmentFlag.AlignCenter, self._error_message)

            finally:
                # Restore state
                painter.restore()

        except Exception as e:
            logger.error(f"Critical paint error: {str(e)}")
            logger.error(traceback.format_exc())
            if painter.isActive():
                painter.setPen(self.warning_color)
                painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"Critical Error: {str(e)}")

        finally:
            # End painting if active
            if painter.isActive():
                painter.end()

    def draw_text(self, painter: QPainter, rect, flags: int, text: str,
                 color=None, glow: bool = False):
        """Draw text with theme-aware enhancements"""
        if color is None:
            color = self.hud_color

        use_effects = self._theme_manager.get_style_param("use_gradients", False)
        if use_effects:
            self._visual_effects.draw_enhanced_text(
                painter, rect, flags, text,
                glow=glow,
                glow_color=color,
                shadow=self._theme_manager.get_style_param("use_shadows", False)
            )
        else:
            # Fall back to basic drawing if effects disabled
            painter.setPen(color)
            painter.drawText(rect, flags, text)

    def draw_line(self, painter: QPainter, start, end,
                 color=None, width: float = 1.0, glow: bool = False):
        """Draw line with theme-aware enhancements"""
        if color is None:
            color = self.hud_color

        use_effects = self._theme_manager.get_style_param("use_gradients", False)
        if use_effects:
            self._visual_effects.draw_enhanced_line(
                painter, start, end,
                color=color,
                width=width,
                glow=glow
            )
        else:
            # Fall back to basic drawing if effects disabled
            pen = QPen(color)
            pen.setWidthF(width)
            painter.setPen(pen)
            painter.drawLine(start, end)

    def draw_rect(self, painter: QPainter, rect,
                 color=None, fill: bool = False, fill_color=None,
                 corner_radius=None):
        """Draw rectangle with theme-aware enhancements"""
        if color is None:
            color = self.hud_color

        use_effects = self._theme_manager.get_style_param("use_gradients", False)
        if use_effects:
            self._visual_effects.draw_enhanced_rect(
                painter, rect,
                color=color,
                fill=fill,
                fill_color=fill_color,
                corner_radius=corner_radius
            )
        else:
            # Fall back to basic drawing if effects disabled
            painter.setPen(color)

            if fill:
                if fill_color is None:
                    fill_color = QColor(color)
                    fill_color.setAlpha(min(color.alpha() // 3, 80))
                painter.setBrush(QBrush(fill_color))
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)

            if corner_radius and corner_radius > 0:
                painter.drawRoundedRect(rect, corner_radius, corner_radius)
            else:
                painter.drawRect(rect)

    def eventFilter(self, obj, event: QEvent) -> bool:
        """Filter events to prevent unwanted interactions"""
        if event.type() == QEvent.Type.MouseButtonPress:
            # Handle mouse press
            self.mousePressEvent(event)
            return True
        elif event.type() == QEvent.Type.MouseButtonRelease:
            # Handle mouse release
            self.mouseReleaseEvent(event)
            return True
        elif event.type() == QEvent.Type.MouseMove:
            # Handle mouse move
            self.mouseMoveEvent(event)
            return True

        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        """Handle mouse press events"""
        # Disable dragging by default - only allow in specific cases
        # where a display needs to be movable
        event.accept()

    def mouseReleaseEvent(self, event):
        """Handle mouse release events"""
        # Disable dragging by default
        event.accept()

    def mouseMoveEvent(self, event):
        """Handle mouse move events"""
        # Disable dragging by default
        event.accept()

    def showEvent(self, event):
        """Handle window show event"""
        super().showEvent(event)

        # Only raise and activate if this is a top-level window
        if self.parent() is None:
            self.raise_()
            self.activateWindow()

    def closeEvent(self, event):
        """Handle window close event"""
        self.stop()
        super().closeEvent(event)

    def moveEvent(self, event):
        """Handle window move event"""
        super().moveEvent(event)
        if self._running:
            self._safe_update()

    def resizeEvent(self, event):
        """Handle window resize event"""
        super().resizeEvent(event)
        if self._running:
            self._safe_update()

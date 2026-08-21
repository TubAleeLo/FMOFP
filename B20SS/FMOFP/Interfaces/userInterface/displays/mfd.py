"""
Multi-Function Display implementation
"""
from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QPainterPath, QFont, QPen
# NOTE (production readiness re-analysis, August 2026): QFont and QPen were
# missing from the import above despite being used extensively throughout
# this file (draw_systems_page/draw_comms_page/draw_engine_page/
# draw_mission_page, ~43 usages total) -- found via `ruff check --select F821`
# (undefined-name), which had never been run locally or in CI against this
# file before (CI's lint job excludes FMOFP/Tests but does run against the
# rest of the tree; this gap simply hadn't been checked). Every one of those
# draw_*_page() methods wraps its body in a broad `except Exception as e:
# logger.error(...)`, so the resulting NameError was never an uncaught crash
# -- it silently produced a blank/broken page render plus one ERROR log line
# every time a user navigated the MFD to Systems, Comms, Engine, or Mission.
# Confirmed live after this fix: all four pages now render without error.
from .base_display import BaseDisplay, DisplayType, DisplayPage
from .visual.theme_manager import get_theme_manager, DisplayTheme
from .pfd_display_factory import PFDDisplayFactory

import math
import traceback
from enum import Enum
from typing import Dict, List, Optional, Union
from FMOFP.local_messaging.routing.handlers.system_message_handlers.RadarMessageHandler import get_radar_message_handler
from Systems.radarManagement.radar_enums import (
    RadarMode, weather_radarMode, targeting_radarMode,
    tfr_radarMode, sar_radarMode, aewc_radarMode
)
from .radar.radar_display_factory import RadarDisplayFactory
from .radar.weather_radar_display import WeatherRadarDisplay
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class RadarData:
    def __init__(self):
        self.mode: Union[RadarMode, weather_radarMode, targeting_radarMode,
                        tfr_radarMode, sar_radarMode, aewc_radarMode] = RadarMode.STANDBY
        self.weather_data: Dict = {}
        self.targets: List[Dict] = []
        self.tfr_data: List[Dict] = []
        self.sar_data: Optional[Dict] = None
        self.aewc_tracks: List[Dict] = []
        self.status: str = "STANDBY"
        self.range_scale = 40  # nautical miles

class RadarType(Enum):
    BACK = "Return to Main Menu"  # Add Back option at the top
    WEATHER = "Weather Radar"
    TARGETING = "Targeting Radar"
    TFR = "Terrain Following"
    SAR = "Synthetic Aperture"
    AEWC = "AEWC Radar"

class MultiFunctionDisplay(BaseDisplay):
    def __init__(self, parent=None):
        super().__init__(DisplayType.MFD, parent=parent)
        self.current_page = DisplayPage.NAV
        self.pages = [DisplayPage.NAV, DisplayPage.RADAR, DisplayPage.SYSTEMS,
                     DisplayPage.WEAPONS, DisplayPage.COMMS, DisplayPage.MISSION,
                     DisplayPage.SETTINGS]
        # Mission page sub-tab: 'ROUTE' | 'TARGETS' | 'OOB'
        self._mission_tab: str = 'ROUTE'

        # Menu configuration
        self.menu_width = 150.0
        self.menu_item_height = 40.0
        self.menu_start_y = 100.0

        # Content area configuration
        self.content_margin = 20.0
        self.content_start_x = self.menu_width + self.content_margin

        # Radar data and handler
        self.radar_data = RadarData()
        self.radar_handler = get_radar_message_handler()
        self._setup_radar_handlers()

        # Current radar display instance
        self._current_radar_display = None

        # Current radar type (weather, targeting, etc.)
        self._current_radar_type = weather_radarMode  # Default to weather radar

        # Radar sub-menu configuration
        self.radar_types = [
            RadarType.BACK,  # Add Back option at the top
            RadarType.WEATHER,
            RadarType.TARGETING,
            RadarType.TFR,
            RadarType.SAR,
            RadarType.AEWC
        ]
        self.current_radar_type = RadarType.WEATHER

    def _map_radar_mode(self, mode: RadarMode) -> Optional[Enum]:
        """Map general radar mode to specific radar mode"""
        try:
            # Map based on current radar type
            if mode == RadarMode.STANDBY:
                return self._current_radar_type.STANDBY
            elif mode == RadarMode.ACTIVE:
                # Map to appropriate active mode based on radar type
                if self._current_radar_type == weather_radarMode:
                    return weather_radarMode.SURVEILLANCE
                elif self._current_radar_type == targeting_radarMode:
                    return targeting_radarMode.SEARCH
                elif self._current_radar_type == tfr_radarMode:
                    return tfr_radarMode.SEARCH
                elif self._current_radar_type == sar_radarMode:
                    return sar_radarMode.STRIPMAP
                elif self._current_radar_type == aewc_radarMode:
                    return aewc_radarMode.SEARCH
            elif mode == RadarMode.SEARCH:
                # Map to appropriate search mode
                if self._current_radar_type == targeting_radarMode:
                    return targeting_radarMode.SEARCH
                elif self._current_radar_type == tfr_radarMode:
                    return tfr_radarMode.SEARCH
                elif self._current_radar_type == aewc_radarMode:
                    return aewc_radarMode.SEARCH
            elif mode == RadarMode.TRACK:
                # Map to appropriate track mode
                if self._current_radar_type == targeting_radarMode:
                    return targeting_radarMode.TRACK
                elif self._current_radar_type == tfr_radarMode:
                    return tfr_radarMode.TRACK
                elif self._current_radar_type == aewc_radarMode:
                    return aewc_radarMode.TRACK

            return None

        except Exception as e:
            logger.error(f"Error mapping radar mode: {str(e)}")
            return None

    def paint_display(self, painter: QPainter):
        """Paint the Multi-Function Display"""
        try:
            # Save state
            painter.save()

            # Enable antialiasing
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

            # Draw main elements in order
            self.draw_title(painter)
            self.draw_menu(painter)
            self.draw_page_content(painter)

            # Restore state
            painter.restore()

        except Exception as e:
            logger.error(f"MFD paint error: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _setup_radar_handlers(self):
        """Set up handlers for radar messages"""
        try:
            if self.radar_handler and self.radar_handler.async_handler:
                # Register handlers for different radar message types
                self.radar_handler.async_handler.register_handler(
                    "radar_mode_update",  # Changed from RadarStatusMessage to match RadarMessageHandler
                    self._handle_radar_mode_update  # New handler name
                )
                self.radar_handler.async_handler.register_handler(
                    "weather_radarData",
                    self._handle_weather_data
                )
                self.radar_handler.async_handler.register_handler(
                    "targeting_radarTrack",
                    self._handle_target_data
                )
                self.radar_handler.async_handler.register_handler(
                    "tfr_radarElevation",
                    self._handle_tfr_data
                )
                self.radar_handler.async_handler.register_handler(
                    "sar_radarImagery",
                    self._handle_sar_data
                )
                self.radar_handler.async_handler.register_handler(
                    "aewc_radarTrack",
                    self._handle_aewc_data
                )
                self.radar_handler.async_handler.register_handler(
                    "radar_status_update",
                    self._handle_radar_status
                )
                logger.info("Radar message handlers registered")
        except Exception as e:
            logger.error(f"Error setting up radar handlers: {str(e)}")
            logger.error(traceback.format_exc())

    def _handle_radar_mode_update(self, data: Dict):
        """Handle radar mode updates"""
        try:
            radar_type = data.get('radar_type')
            mode = data.get('mode')

            if not radar_type or mode is None:
                logger.error("Invalid radar mode update format")
                return

            # Update radar data mode
            self.radar_data.mode = mode
            self.radar_data.status = mode.name

            # Update display
            self._current_radar_display = RadarDisplayFactory.create_display(mode)

            logger.info(f"Updated radar mode to {mode.name}")
            self.update()  # Trigger display update

        except Exception as e:
            logger.error(f"Error handling radar mode update: {str(e)}")

    def _handle_weather_data(self, data: Dict):
        """Handle incoming weather radar data"""
        try:
            # Get existing weather data
            weather_data = self.radar_data.weather_data

            # Update with new data while preserving existing data
            if isinstance(data, dict):
                # Handle VIL data
                if 'vil_data' in data:
                    weather_data['vil_data'] = data['vil_data']
                # Handle precipitation data
                if 'precipitation' in data:
                    weather_data['precipitation'] = data['precipitation']
                # Handle other weather data
                if 'weather_data' in data:
                    weather_data.update(data['weather_data'])
                # Handle mode updates
                if 'mode' in data:
                    weather_data['mode'] = data['mode']

            # Update radar data
            self.radar_data.weather_data = weather_data
            self.update()
        except Exception as e:
            logger.error(f"Error handling weather data: {str(e)}")

    def _handle_target_data(self, data: Dict):
        """Handle incoming target data"""
        try:
            target = {
                'id': data.get('track_id'),
                'position': data.get('position'),
                'velocity': data.get('velocity'),
                'identity': data.get('identity'),
                'classification': data.get('classification')
            }
            # Update or add target
            updated = False
            for i, existing in enumerate(self.radar_data.targets):
                if existing['id'] == target['id']:
                    self.radar_data.targets[i] = target
                    updated = True
                    break
            if not updated:
                self.radar_data.targets.append(target)
            self.update()
        except Exception as e:
            logger.error(f"Error handling target data: {str(e)}")

    def _handle_tfr_data(self, data: Dict):
        """Handle incoming TFR data"""
        try:
            point = {
                'distance': data.get('distance', 0),
                'elevation': data.get('elevation', 0)
            }
            self.radar_data.tfr_data.append(point)
            # Keep only last N points
            max_points = 100
            if len(self.radar_data.tfr_data) > max_points:
                self.radar_data.tfr_data = self.radar_data.tfr_data[-max_points:]
            self.update()
        except Exception as e:
            logger.error(f"Error handling TFR data: {str(e)}")

    def _handle_sar_data(self, data: Dict):
        """Handle incoming SAR data"""
        try:
            self.radar_data.sar_data = {
                'image_data': data.get('image_data', b""),
                'corner_points': data.get('corner_points', []),
                'resolution': data.get('resolution', 0)
            }
            self.update()
        except Exception as e:
            logger.error(f"Error handling SAR data: {str(e)}")

    def _handle_aewc_data(self, data: Dict):
        """Handle incoming AEWC data"""
        try:
            track = {
                'id': data.get('track_id'),
                'position': data.get('position'),
                'velocity': data.get('velocity'),
                'identity': data.get('identity'),
                'classification': data.get('classification'),
                'is_stealth': data.get('is_stealth', False)
            }
            # Update or add track
            updated = False
            for i, existing in enumerate(self.radar_data.aewc_tracks):
                if existing['id'] == track['id']:
                    self.radar_data.aewc_tracks[i] = track
                    updated = True
                    break
            if not updated:
                self.radar_data.aewc_tracks.append(track)
            self.update()
        except Exception as e:
            logger.error(f"Error handling AEWC data: {str(e)}")

    def _handle_radar_status(self, data: Dict):
        """Handle radar status updates"""
        try:
            self.radar_data.status = data.get('status', None)
            new_mode = data.get('mode', RadarMode.STANDBY)

            # Map general mode to specific mode
            specific_mode = self._map_radar_mode(new_mode)
            if specific_mode is not None:
                self.radar_data.mode = specific_mode

                # Only update display if mode changed
                if specific_mode != self.radar_data.mode:
                    self.radar_data.mode = specific_mode
                    # Get new radar display for mode
                    self._current_radar_display = RadarDisplayFactory.create_display(specific_mode)

            self.update()
        except Exception as e:
            logger.error(f"Error handling radar status: {str(e)}")

    def draw_radar_page(self, painter: QPainter, rect: QRectF):
        """Draw radar page content"""
        try:
            # Removed static text elements that were not connected to the display tree
            # Use full content area for radar display
            content_rect = rect.adjusted(10, 10, -10, -10)
            if self._current_radar_display:
                # Check if it's a WeatherRadarDisplay
                if isinstance(self._current_radar_display, WeatherRadarDisplay):
                    # Use draw_radar_elements directly for WeatherRadarDisplay
                    self._current_radar_display.draw_radar_elements(
                        painter,
                        content_rect,
                        self._get_radar_data()
                    )
                else:
                    # Use standard draw_display method for other types
                    self._current_radar_display.draw_display(
                        painter,
                        content_rect,
                        self._get_radar_data()
                    )
            else:
                self._draw_standby_display(painter, content_rect)

        except Exception as e:
            logger.error(f"Error drawing radar page: {str(e)}")
            raise

    def _draw_standby_display(self, painter: QPainter, rect: QRectF):
        """Draw standby radar display"""
        try:
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignCenter,
                "RADAR STANDBY"
            )
        except Exception as e:
            logger.error(f"Error drawing standby display: {str(e)}")
            raise

    def _get_radar_data(self) -> Dict:
        """Get appropriate radar data based on current mode"""
        try:
            # Always include mode in the data to ensure proper mode handling
            base_data = {'mode': self.radar_data.mode}

            if isinstance(self.radar_data.mode, weather_radarMode):
                # Include weather data and ensure mode is passed
                base_data.update({'weather_data': self.radar_data.weather_data})
                return base_data
            elif isinstance(self.radar_data.mode, targeting_radarMode):
                # Include targets data and ensure mode is passed
                base_data.update({'targets': self.radar_data.targets})
                return base_data
            elif isinstance(self.radar_data.mode, tfr_radarMode):
                # Include TFR data and ensure mode is passed
                base_data.update({
                    'tfr_data': self.radar_data.tfr_data,
                    'terrain_clearance': 500,  # Example value, should be from actual data
                    'system_health': 'NORMAL'  # Example value, should be from actual data
                })
                return base_data
            elif isinstance(self.radar_data.mode, sar_radarMode):
                # Include SAR data and ensure mode is passed
                if self.radar_data.sar_data:
                    base_data.update(self.radar_data.sar_data)
                return base_data
            elif isinstance(self.radar_data.mode, aewc_radarMode):
                # Include AEWC data and ensure mode is passed
                base_data.update({'targets': self.radar_data.aewc_tracks})
                return base_data
            return base_data
        except Exception as e:
            logger.error(f"Error getting radar data: {str(e)}")
            return {}

    def draw_title(self, painter: QPainter):
        """Draw the MFD title bar with enhanced visuals"""
        try:
            # Calculate title bar dimensions
            title_height = float(self.height()) / 12
            title_rect = QRectF(0, 0, float(self.width()), title_height)

            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)

            if use_gradients:
                # Create gradient background for title
                gradient = QLinearGradient(0, 0, 0, title_height)
                base_color = QColor(40, 40, 40)
                gradient.setColorAt(0, QColor(60, 60, 60))
                gradient.setColorAt(1, base_color)

                painter.fillRect(title_rect, gradient)

                # Draw title text with glow effect
                self.draw_text(
                    painter, title_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    f"MFD - {self.current_page.value}",
                    glow=True
                )

                # Draw separator line with enhanced effect
                line = QLineF(QPointF(0, title_rect.bottom()),
                             QPointF(float(self.width()), title_rect.bottom()))

                self.draw_line(
                    painter, line.p1(), line.p2(),
                    width=1.5,
                    glow=True
                )
            else:
                # Fall back to original drawing
                painter.fillRect(title_rect, QColor(40, 40, 40))
                painter.setPen(self.hud_color)
                painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter,
                               f"MFD - {self.current_page.value}")

                line = QLineF(QPointF(0, title_rect.bottom()),
                             QPointF(float(self.width()), title_rect.bottom()))
                painter.drawLine(line)

        except Exception as e:
            logger.error(f"Error drawing title: {str(e)}")
            raise

    def draw_menu(self, painter: QPainter):
        """Draw MFD menu options with enhanced visuals"""
        try:
            # Calculate menu dimensions
            title_height = float(self.height()) / 12
            menu_width = float(self.width()) / 5

            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)

            # Draw menu background
            menu_rect = QRectF(0, title_height, menu_width, float(self.height()) - title_height)

            if use_gradients:
                # Create gradient background for menu
                gradient = QLinearGradient(0, title_height, 0, self.height())
                gradient.setColorAt(0, QColor(35, 35, 35))
                gradient.setColorAt(1, QColor(25, 25, 25))

                painter.fillRect(menu_rect, gradient)

                # Draw menu separator with glow
                separator = QLineF(
                    QPointF(menu_rect.right(), menu_rect.top()),
                    QPointF(menu_rect.right(), menu_rect.bottom())
                )

                self.draw_line(
                    painter, separator.p1(), separator.p2(),
                    width=1.5,
                    glow=True
                )
            else:
                # Fall back to original drawing
                painter.fillRect(menu_rect, QColor(30, 30, 30))
                painter.setPen(self.hud_color)

                separator = QLineF(
                    QPointF(menu_rect.right(), menu_rect.top()),
                    QPointF(menu_rect.right(), menu_rect.bottom())
                )
                painter.drawLine(separator)

            if self.current_page == DisplayPage.RADAR:
                # Draw radar sub-menu with enhanced visuals
                self._draw_radar_menu(painter, menu_rect)
            else:
                # Draw main menu with enhanced visuals
                self._draw_main_menu(painter, menu_rect)

        except Exception as e:
            logger.error(f"Error drawing menu: {str(e)}")
            raise

    def _draw_main_menu(self, painter: QPainter, menu_rect: QRectF):
        """Draw main menu items with enhanced visuals"""
        try:
            # Calculate menu item dimensions
            item_height = min((menu_rect.height() - 20) / len(self.pages), 40)
            y = menu_rect.top() + 10

            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            corner_radius = self._theme_manager.get_style_param("corner_radius", 0.0)

            # Draw menu items
            for page in self.pages:
                item_rect = QRectF(0, y, menu_rect.width(), item_height)

                # Highlight current page
                if page == self.current_page:
                    if use_gradients:
                        # Create gradient for selected item
                        gradient = QLinearGradient(0, y, menu_rect.width(), y)
                        gradient.setColorAt(0, QColor(60, 60, 60))
                        gradient.setColorAt(0.8, QColor(50, 50, 50))
                        gradient.setColorAt(1, QColor(40, 40, 40))

                        # Draw with rounded corners if enabled
                        if corner_radius > 0:
                            path = QPainterPath()
                            path.addRoundedRect(item_rect, corner_radius, corner_radius)
                            painter.fillPath(path, gradient)
                        else:
                            painter.fillRect(item_rect, gradient)

                        painter.setPen(self._theme_manager.get_color("warning"))
                    else:
                        # Fall back to original drawing
                        painter.fillRect(item_rect, QColor(60, 60, 60))
                        painter.setPen(self.warning_color)
                else:
                    painter.setPen(self.hud_color)

                # Draw menu text
                text_rect = item_rect.adjusted(10, 0, -10, 0)

                if use_gradients and page == self.current_page:
                    # Draw selected item text with glow
                    self.draw_text(
                        painter, text_rect,
                        Qt.AlignmentFlag.AlignVCenter,
                        page.value,
                        glow=True,
                        color=self._theme_manager.get_color("warning")
                    )
                else:
                    # Draw regular or fall back to original
                    if use_gradients:
                        self.draw_text(
                            painter, text_rect,
                            Qt.AlignmentFlag.AlignVCenter,
                            page.value,
                            glow=False
                        )
                    else:
                        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, page.value)

                y += item_height

        except Exception as e:
            logger.error(f"Error drawing main menu: {str(e)}")
            raise

    def _draw_radar_menu(self, painter: QPainter, menu_rect: QRectF):
        """Draw radar sub-menu items with enhanced visuals"""
        try:
            # Calculate menu item dimensions
            item_height = min((menu_rect.height() - 20) / len(self.radar_types), 40)
            y = menu_rect.top() + 10

            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            corner_radius = self._theme_manager.get_style_param("corner_radius", 0.0)

            # Draw menu items
            for radar_type in self.radar_types:
                item_rect = QRectF(0, y, menu_rect.width(), item_height)

                # Highlight current radar type
                if radar_type == self.current_radar_type:
                    if use_gradients:
                        # Create gradient for selected item
                        gradient = QLinearGradient(0, y, menu_rect.width(), y)
                        gradient.setColorAt(0, QColor(60, 60, 60))
                        gradient.setColorAt(0.8, QColor(50, 50, 50))
                        gradient.setColorAt(1, QColor(40, 40, 40))

                        # Draw with rounded corners if enabled
                        if corner_radius > 0:
                            path = QPainterPath()
                            path.addRoundedRect(item_rect, corner_radius, corner_radius)
                            painter.fillPath(path, gradient)
                        else:
                            painter.fillRect(item_rect, gradient)

                        painter.setPen(self._theme_manager.get_color("warning"))
                    else:
                        # Fall back to original drawing
                        painter.fillRect(item_rect, QColor(60, 60, 60))
                        painter.setPen(self.warning_color)
                else:
                    painter.setPen(self.hud_color)

                # Draw menu text
                text_rect = item_rect.adjusted(10, 0, -10, 0)

                if use_gradients and radar_type == self.current_radar_type:
                    # Draw selected item text with glow
                    self.draw_text(
                        painter, text_rect,
                        Qt.AlignmentFlag.AlignVCenter,
                        radar_type.value,
                        glow=True,
                        color=self._theme_manager.get_color("warning")
                    )
                else:
                    # Draw regular or fall back to original
                    if use_gradients:
                        self.draw_text(
                            painter, text_rect,
                            Qt.AlignmentFlag.AlignVCenter,
                            radar_type.value,
                            glow=False
                        )
                    else:
                        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, radar_type.value)

                y += item_height

        except Exception as e:
            logger.error(f"Error drawing radar menu: {str(e)}")
            raise

    def draw_page_content(self, painter: QPainter):
        """Draw current page content"""
        try:
            # Calculate content area dimensions
            title_height = float(self.height()) / 12
            menu_width = float(self.width()) / 5
            margin = 20.0

            content_rect = QRectF(
                menu_width + margin,
                title_height + margin,
                float(self.width()) - menu_width - margin * 2,
                float(self.height()) - title_height - margin * 2
            )

            painter.setPen(self.hud_color)

            # Save state before page-specific drawing
            painter.save()

            if self.current_page == DisplayPage.NAV:
                self.draw_nav_page(painter, content_rect)
            elif self.current_page == DisplayPage.RADAR:
                self.draw_radar_page(painter, content_rect)
            elif self.current_page == DisplayPage.SYSTEMS:
                self.draw_systems_page(painter, content_rect)
            elif self.current_page == DisplayPage.WEAPONS:
                self.draw_weapons_page(painter, content_rect)
            elif self.current_page == DisplayPage.COMMS:
                self.draw_comms_page(painter, content_rect)
            elif self.current_page == DisplayPage.MISSION:
                self.draw_mission_page(painter, content_rect)
            elif self.current_page == DisplayPage.SETTINGS:
                self.draw_settings_page(painter, content_rect)

            # Restore state after page-specific drawing
            painter.restore()

        except Exception as e:
            logger.error(f"Error drawing page content: {str(e)}")
            raise

    def draw_nav_page(self, painter: QPainter, rect: QRectF):
        """Draw navigation page content with enhanced visuals"""
        try:
            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)

            # Draw page title with enhanced visuals
            title_rect = rect.adjusted(10, 10, -10, -10)

            if use_gradients:
                self.draw_text(
                    painter, title_rect,
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                    "Navigation Display",
                    glow=True
                )
            else:
                painter.drawText(title_rect,
                               Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                               "Navigation Display")

            # Draw compass rose with enhanced visuals
            center = rect.center()
            radius = min(rect.width(), rect.height()) / 3

            # Draw compass circle with enhanced visuals
            compass_rect = QRectF(
                center.x() - radius,
                center.y() - radius,
                radius * 2,
                radius * 2
            )

            if use_gradients:
                self._visual_effects.draw_enhanced_ellipse(
                    painter, compass_rect,
                    glow=True
                )

                # Draw additional inner circle for depth effect
                inner_radius = radius * 0.9
                inner_rect = QRectF(
                    center.x() - inner_radius,
                    center.y() - inner_radius,
                    inner_radius * 2,
                    inner_radius * 2
                )
                painter.setPen(self.hud_color)
                painter.drawEllipse(inner_rect)

                # Draw radial lines for more futuristic look
                for angle in range(0, 360, 30):  # Every 30 degrees
                    rad_angle = math.radians(angle)
                    start_point = QPointF(
                        center.x() + inner_radius * math.cos(rad_angle),
                        center.y() + inner_radius * math.sin(rad_angle)
                    )
                    end_point = QPointF(
                        center.x() + radius * math.cos(rad_angle),
                        center.y() + radius * math.sin(rad_angle)
                    )

                    # Draw line with slight glow
                    self.draw_line(
                        painter, start_point, end_point,
                        width=1.0,
                        glow=False
                    )
            else:
                painter.drawEllipse(compass_rect)

            # Draw cardinal points with enhanced visuals
            points = [("N", 0), ("E", 90), ("S", 180), ("W", 270)]
            for label, angle in points:
                rad_angle = math.radians(angle - 90)
                point_x = center.x() + radius * 1.2 * math.cos(rad_angle)
                point_y = center.y() + radius * 1.2 * math.sin(rad_angle)

                # Create text rectangle for better positioning
                text_rect = QRectF(
                    point_x - 15,
                    point_y - 15,
                    30,
                    30
                )

                if use_gradients:
                    self.draw_text(
                        painter, text_rect,
                        Qt.AlignmentFlag.AlignCenter,
                        label,
                        glow=True
                    )
                else:
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

        except Exception as e:
            logger.error(f"Error drawing nav page: {str(e)}")
            raise

    def draw_systems_page(self, painter: QPainter, rect: QRectF):
        """Draw systems page — live data from ECU, GCAS, and PerformanceMonitor."""
        try:
            ecu_data, gcas_alerts, exceedances = {}, [], []
            try:
                from FMOFP.Systems.engineManagement.ecu.engineControlUnit import get_engine_control_unit
                ecu_data = get_engine_control_unit().get_data()
            except Exception:
                logger.debug("MFD: ECU not yet running", exc_info=True)
            try:
                from FMOFP.Systems.flightControlSys.groundCollisionAvoidanceSys.groundCollisionAvoidanceSys import get_gcas
                gcas_alerts = get_gcas().get_alerts()
            except Exception:
                logger.debug("MFD: GCAS not yet running", exc_info=True)
            try:
                from FMOFP.Systems.flightControlSys.performaneMonitoring.performaneMonitoring import get_performance_monitor
                exceedances = get_performance_monitor().get_exceedances()
            except Exception:
                logger.debug("MFD: PerformanceMonitor not yet running", exc_info=True)

            f_hd  = QFont("Monospace", 8)
            f_val = QFont("Monospace", 9, QFont.Weight.Bold)
            line_h = 18.0
            y = rect.top() + 8

            def section(title):
                nonlocal y
                painter.setFont(f_hd)
                painter.setPen(QPen(QColor(100, 100, 100)))
                painter.drawText(QRectF(rect.left() + 6, y, rect.width() - 12, line_h),
                                 Qt.AlignmentFlag.AlignVCenter, title)
                y += line_h + 2

            def row(label, value, ok=True):
                nonlocal y
                col = QColor(0, 255, 100) if ok else QColor(255, 80, 80)
                painter.setFont(f_hd)
                painter.setPen(QPen(QColor(100, 100, 100)))
                painter.drawText(QRectF(rect.left() + 10, y, rect.width() * 0.55, line_h),
                                 Qt.AlignmentFlag.AlignVCenter, label)
                painter.setFont(f_val)
                painter.setPen(QPen(col))
                painter.drawText(QRectF(rect.left() + rect.width() * 0.57, y,
                                        rect.width() * 0.40, line_h),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, value)
                y += line_h + 1

            section("─── ENGINE ──────────")
            row("N1",     f"{ecu_data.get('n1_pct', 0):5.1f} %",   ecu_data.get('n1_pct', 0) < 100)
            row("EGT",    f"{ecu_data.get('egt_c', 0):5.0f} °C",   ecu_data.get('egt_c', 0) < 800)
            row("OIL PSI",f"{ecu_data.get('oil_psi', 0):5.1f}",    ecu_data.get('oil_psi', 0) > 40)
            row("VIB",    f"{ecu_data.get('vibration', 0):5.2f}",   ecu_data.get('vibration', 0) < 0.8)
            y += 4

            section("─── FCS / GCAS ──────")
            if gcas_alerts:
                for a in gcas_alerts[:3]:
                    row(a.get("code", "?"), a.get("message", ""), ok=False)
            else:
                row("GCAS", "NOMINAL", ok=True)

            if exceedances:
                y += 4
                section("─── EXCEEDANCES ─────")
                for exc in exceedances[:3]:
                    row(exc["parameter"].upper()[:10],
                        f"{exc['value']:.1f}/{exc['limit']:.0f}", ok=False)

        except Exception as e:
            logger.error(f"Error drawing systems page: {str(e)}")
            raise

    def draw_weapons_page(self, painter: QPainter, rect: QRectF):
        """Draw weapons page content"""
        try:
            # Draw page title
            title_rect = rect.adjusted(10, 10, -10, -10)
            painter.drawText(title_rect,
                           Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                           "Weapons Status")

            # Calculate station dimensions
            stations = ["1", "2", "3", "4", "5"]
            station_size = min(rect.width() / (len(stations) * 2), 30)
            spacing = (rect.width() - (station_size * len(stations))) / (len(stations) + 1)

            # Draw weapon stations
            x = rect.left() + spacing
            for station in stations:
                station_rect = QRectF(
                    x,
                    rect.center().y() - station_size/2,
                    station_size,
                    station_size
                )
                painter.drawRect(station_rect)
                painter.drawText(station_rect, Qt.AlignmentFlag.AlignCenter, station)
                x += station_size + spacing

        except Exception as e:
            logger.error(f"Error drawing weapons page: {str(e)}")
            raise

    def draw_comms_page(self, painter: QPainter, rect: QRectF):
        """Draw communications page — live data from CommsService."""
        try:
            comms_data = {}
            try:
                from FMOFP.Systems.comms.messaging_service import get_comms_service
                comms_data = get_comms_service().get_data()
            except Exception:
                logger.debug("MFD: CommsService not yet running", exc_info=True)

            radio    = comms_data.get("radio",    {})
            satcom   = comms_data.get("satcom",   {})
            datalink = comms_data.get("datalink", {})

            f_hd  = QFont("Monospace", 8)
            f_val = QFont("Monospace", 9, QFont.Weight.Bold)
            line_h = 18.0
            y = rect.top() + 8

            def section(title):
                nonlocal y
                painter.setFont(f_hd)
                painter.setPen(QPen(QColor(100, 100, 100)))
                painter.drawText(QRectF(rect.left() + 6, y, rect.width() - 12, line_h),
                                 Qt.AlignmentFlag.AlignVCenter, title)
                y += line_h + 2

            def row(label, value, ok=True):
                nonlocal y
                col = QColor(0, 255, 100) if ok else QColor(255, 200, 0)
                painter.setFont(f_hd)
                painter.setPen(QPen(QColor(100, 100, 100)))
                painter.drawText(QRectF(rect.left() + 10, y, rect.width() * 0.55, line_h),
                                 Qt.AlignmentFlag.AlignVCenter, label)
                painter.setFont(f_val)
                painter.setPen(QPen(col))
                painter.drawText(QRectF(rect.left() + rect.width() * 0.57, y,
                                        rect.width() * 0.40, line_h),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, value)
                y += line_h + 1

            section("─── RADIO ───────────")
            row("FREQ",   f"{radio.get('frequency', 0):.3f} MHz", True)
            row("MODE",   radio.get("mode", "---"), True)
            row("SIG",    f"{radio.get('signal_strength', 0):.0f}%",
                radio.get("signal_strength", 0) > 20)
            row("STATUS", "ACTIVE" if radio.get("active") else "SQUELCH",
                radio.get("active", False))
            y += 4

            section("─── SATCOM ──────────")
            connected = satcom.get("connection_status") == "connected"
            row("LINK",    satcom.get("connection_status", "---").upper(), connected)
            row("SAT ID",  str(satcom.get("satellite_id", "---")), connected)
            row("RATE",    f"{satcom.get('data_rate_kbps', 0):.0f} kbps", connected)
            row("LATENCY", f"{satcom.get('latency_ms', 0):.0f} ms", connected)
            y += 4

            section("─── DATA LINK ───────")
            dl_active = datalink.get("link_status") == "active"
            row("STATUS", datalink.get("link_status", "---").upper(), dl_active)
            row("TX PKT",  str(datalink.get("packets_sent", 0)), True)
            row("RX PKT",  str(datalink.get("packets_received", 0)), True)
            row("ERR",     f"{datalink.get('error_rate', 0):.2f}%", datalink.get("error_rate", 0) < 1.0)

        except Exception as e:
            logger.error(f"Error drawing comms page: {str(e)}")
            raise

    def draw_engine_page(self, painter: QPainter, rect: QRectF):
        """Draw engine page — live N1/N2/EGT/fuel from ECU."""
        try:
            ecu = {}
            try:
                from FMOFP.Systems.engineManagement.ecu.engineControlUnit import get_engine_control_unit
                ecu = get_engine_control_unit().get_data()
            except Exception:
                logger.debug("MFD: ECU not yet running (engine page)", exc_info=True)

            f_hd  = QFont("Monospace", 8)
            f_val = QFont("Monospace", 10, QFont.Weight.Bold)
            f_big = QFont("Monospace", 12, QFont.Weight.Bold)
            line_h = 20.0
            y = rect.top() + 8

            def row(label, value, col):
                nonlocal y
                painter.setFont(f_hd)
                painter.setPen(QPen(QColor(100, 100, 100)))
                painter.drawText(QRectF(rect.left() + 10, y, rect.width() * 0.5, line_h),
                                 Qt.AlignmentFlag.AlignVCenter, label)
                painter.setFont(f_val)
                painter.setPen(QPen(col))
                painter.drawText(QRectF(rect.left() + rect.width() * 0.52, y,
                                        rect.width() * 0.45, line_h),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, value)
                y += line_h + 2

            # Thrust bar
            thrust = ecu.get("thrust_pct", 0)
            bar_w = rect.width() - 20
            bar_h = 20
            bar_r = QRectF(rect.left() + 10, y, bar_w, bar_h)
            painter.setPen(QPen(QColor(60, 60, 60)))
            painter.setBrush(QColor(30, 30, 30))
            painter.drawRect(bar_r)
            fill_col = (QColor(255, 60, 60) if thrust > 90 else
                        QColor(255, 200, 0) if thrust > 75 else QColor(0, 200, 80))
            painter.setBrush(fill_col)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(QRectF(rect.left() + 10, y, bar_w * thrust / 100, bar_h))
            painter.setFont(f_big)
            painter.setPen(QPen(QColor(240, 240, 240)))
            painter.drawText(bar_r, Qt.AlignmentFlag.AlignCenter,
                             f"THRUST  {thrust:.1f}%")
            y += bar_h + 8

            green = QColor(0, 255, 100)
            amber = QColor(255, 200, 0)
            red   = QColor(255, 60, 60)

            n1  = ecu.get("n1_pct", 0)
            n2  = ecu.get("n2_pct", 0)
            egt = ecu.get("egt_c", 0)
            ff  = ecu.get("ff_kgh", 0)
            op  = ecu.get("oil_psi", 0)
            ot  = ecu.get("oil_temp_c", 0)
            vib = ecu.get("vibration", 0)
            eff = ecu.get("compressor_eff", 0)

            row("N1 FAN SPEED",  f"{n1:6.1f} %",   green if n1 < 100 else red)
            row("N2 CORE SPEED", f"{n2:6.1f} %",   green if n2 < 100 else red)
            row("EGT",           f"{egt:6.0f} °C",  red if egt > 800 else amber if egt > 750 else green)
            row("FUEL FLOW",     f"{ff:6.0f} kg/h", green)
            row("OIL PRESSURE",  f"{op:6.1f} psi",  red if op < 40 else amber if op < 50 else green)
            row("OIL TEMP",      f"{ot:6.1f} °C",   red if ot > 130 else green)
            row("VIBRATION",     f"{vib:6.2f} EU",   amber if vib > 0.8 else green)
            row("COMP EFF",      f"{eff:6.1f} %",    amber if eff < 80 else green)

        except Exception as e:
            logger.error(f"Error drawing engine page: {str(e)}")
            raise

    def draw_mission_page(self, painter: QPainter, rect: QRectF):
        """Draw mission planning page with ROUTE / TARGETS / OOB sub-tabs."""
        try:
            # ── fetch live data ────────────────────────────────────────────
            mission = {}
            oob_data = {'summary': {}, 'friendly': [], 'enemy': [], 'neutral': []}
            try:
                from FMOFP.Systems.missionPlanning.missionService import get_mission_service
                svc     = get_mission_service()
                mission = svc.get_data()
                oob_data = svc.get_oob()
            except Exception:
                logger.debug("MFD: MissionService not yet running", exc_info=True)

            # ── colour palette ─────────────────────────────────────────────
            green  = QColor(0, 255, 100)
            cyan   = QColor(0, 220, 255)
            amber  = QColor(255, 200, 0)
            red    = QColor(255, 60, 60)
            dim    = QColor(100, 100, 100)
            white  = QColor(220, 220, 220)
            panel  = QColor(14, 18, 24)

            f_hd   = QFont("Monospace", 8)
            f_val  = QFont("Monospace", 9, QFont.Weight.Bold)
            f_big  = QFont("Monospace", 11, QFont.Weight.Bold)
            f_tab  = QFont("Monospace", 8, QFont.Weight.Bold)
            line_h = 16.0

            # ── mission phase header ───────────────────────────────────────
            phase     = mission.get("phase", "UNKNOWN")
            phase_col = (green if phase == "COMPLETE" else
                         amber if phase in ("OBJECTIVE", "EGRESS") else cyan)
            painter.setFont(f_big)
            painter.setPen(QPen(phase_col))
            painter.drawText(
                QRectF(rect.left() + 6, rect.top() + 4, rect.width() - 12, 22),
                Qt.AlignmentFlag.AlignVCenter, f"MISSION  {phase}"
            )

            # ── tab bar ────────────────────────────────────────────────────
            TABS      = ['ROUTE', 'TARGETS', 'OOB']
            tab_top   = rect.top() + 30
            tab_h     = 18.0
            tab_w     = rect.width() / len(TABS)

            for i, tab in enumerate(TABS):
                tx      = rect.left() + i * tab_w
                tr      = QRectF(tx, tab_top, tab_w - 2, tab_h)
                active  = (tab == self._mission_tab)
                bg_col  = QColor(20, 40, 30) if active else panel
                bd_col  = green if active else dim
                tx_col  = green if active else dim
                painter.setPen(QPen(bd_col, 1))
                painter.setBrush(bg_col)
                painter.drawRect(tr)
                painter.setFont(f_tab)
                painter.setPen(QPen(tx_col))
                painter.drawText(tr, Qt.AlignmentFlag.AlignCenter, tab)

            # Content area below tab bar
            content = QRectF(rect.left(), tab_top + tab_h + 4,
                             rect.width(), rect.height() - 30 - tab_h - 4)

            # ── helper closures ────────────────────────────────────────────
            y_ref = [content.top() + 4]

            def section(title):
                painter.setFont(f_hd)
                painter.setPen(QPen(dim))
                painter.drawText(
                    QRectF(content.left() + 6, y_ref[0],
                           content.width() - 12, line_h),
                    Qt.AlignmentFlag.AlignVCenter, title
                )
                y_ref[0] += line_h + 2

            def row(label, value, col=None):
                vc = col if col is not None else green
                l_r = QRectF(content.left() + 10, y_ref[0],
                              content.width() * 0.48, line_h)
                v_r = QRectF(content.left() + content.width() * 0.50,
                              y_ref[0], content.width() * 0.47, line_h)
                painter.setFont(f_hd)
                painter.setPen(QPen(dim))
                painter.drawText(l_r, Qt.AlignmentFlag.AlignVCenter, label)
                painter.setFont(f_val)
                painter.setPen(QPen(vc))
                painter.drawText(v_r,
                                 Qt.AlignmentFlag.AlignVCenter |
                                 Qt.AlignmentFlag.AlignRight, value)
                y_ref[0] += line_h + 1

            def clip_bottom():
                return y_ref[0] < content.bottom() - line_h

            # ── ROUTE tab ─────────────────────────────────────────────────
            if self._mission_tab == 'ROUTE':
                route_data = mission.get("route", {})
                waypoints  = route_data.get("route", [])      if isinstance(route_data, dict) else []
                active_wp  = route_data.get("active_index", 0) if isinstance(route_data, dict) else 0
                dist_nm    = route_data.get("distance_to_next_nm")  if isinstance(route_data, dict) else None
                bearing    = route_data.get("bearing_to_next_deg")  if isinstance(route_data, dict) else None

                pos = mission.get("current_position", {})
                section("─── POSITION ────────")
                row("LAT",  f"{pos.get('lat', 0):.4f}°")
                row("LON",  f"{pos.get('lon', 0):.4f}°")
                row("ALT",  f"{pos.get('alt_ft', 0):.0f} ft")
                y_ref[0] += 4

                section(f"─── WAYPOINTS ({len(waypoints)}) ──")
                if dist_nm is not None and bearing is not None:
                    row("NEXT WP", f"{dist_nm:.1f} nm  {bearing:.0f}°", cyan)

                for i, wp in enumerate(waypoints):
                    if not clip_bottom():
                        break
                    is_active = (i == active_wp)
                    col    = cyan if is_active else dim
                    marker = "►" if is_active else " "
                    name   = wp.get("name", f"WP{i+1}")
                    alt    = wp.get("alt_ft", 0)
                    wtype  = wp.get("type", "")
                    painter.setFont(f_val if is_active else f_hd)
                    painter.setPen(QPen(col))
                    painter.drawText(
                        QRectF(content.left() + 6, y_ref[0],
                               content.width() - 12, line_h),
                        Qt.AlignmentFlag.AlignVCenter,
                        f"{marker}{i+1:2d}. {name:<8} {alt:>6.0f}ft  {wtype}"
                    )
                    y_ref[0] += line_h + 1

                if not waypoints:
                    painter.setFont(f_hd)
                    painter.setPen(QPen(dim))
                    painter.drawText(
                        QRectF(content.left() + 10, y_ref[0],
                               content.width() - 20, line_h),
                        Qt.AlignmentFlag.AlignVCenter, "No waypoints loaded"
                    )

            # ── TARGETS tab ────────────────────────────────────────────────
            elif self._mission_tab == 'TARGETS':
                targets = mission.get("targets", [])
                section(f"─── TARGETS ({len(targets)}) ────")

                if not targets:
                    painter.setFont(f_hd)
                    painter.setPen(QPen(dim))
                    painter.drawText(
                        QRectF(content.left() + 10, y_ref[0],
                               content.width() - 20, line_h),
                        Qt.AlignmentFlag.AlignVCenter, "No targets designated"
                    )
                else:
                    # Column headers
                    painter.setFont(f_hd)
                    painter.setPen(QPen(dim))
                    hdr = QRectF(content.left() + 6, y_ref[0],
                                 content.width() - 12, line_h)
                    painter.drawText(hdr, Qt.AlignmentFlag.AlignVCenter,
                                     f"{'ID':<6} {'TYPE':<10} {'PRI':>3}  {'STATUS'}")
                    y_ref[0] += line_h + 2

                    for tgt in targets:
                        if not clip_bottom():
                            break
                        status   = tgt.get("status", "PENDING")
                        if hasattr(status, 'value'):
                            status = status.value
                        status   = str(status).split('.')[-1]
                        tcol     = (green if status in ("DESTROYED", "COMPLETE") else
                                    red   if status == "ENGAGED"                  else
                                    amber if status == "ACQUIRED"                 else cyan)
                        t_id     = str(tgt.get("id",       "?"))[:6]
                        t_type   = str(tgt.get("type",     "UNK"))[:10]
                        t_pri    = str(tgt.get("priority", "-"))
                        painter.setFont(f_val)
                        painter.setPen(QPen(tcol))
                        painter.drawText(
                            QRectF(content.left() + 6, y_ref[0],
                                   content.width() - 12, line_h),
                            Qt.AlignmentFlag.AlignVCenter,
                            f"{t_id:<6} {t_type:<10} {t_pri:>3}  {status}"
                        )
                        y_ref[0] += line_h + 1

                        # Lat/lon detail line
                        if clip_bottom():
                            lat = tgt.get("lat", tgt.get("position", [0, 0])[0]
                                          if isinstance(tgt.get("position"), list) else 0)
                            lon = tgt.get("lon", tgt.get("position", [0, 0, 0])[1]
                                          if isinstance(tgt.get("position"), list) else 0)
                            painter.setFont(f_hd)
                            painter.setPen(QPen(dim))
                            painter.drawText(
                                QRectF(content.left() + 16, y_ref[0],
                                       content.width() - 22, line_h),
                                Qt.AlignmentFlag.AlignVCenter,
                                f"  {lat:.4f}° / {lon:.4f}°"
                            )
                            y_ref[0] += line_h + 2

            # ── OOB tab ────────────────────────────────────────────────────
            elif self._mission_tab == 'OOB':
                summary  = oob_data.get("summary",  mission.get("oob_summary", {}))
                friendly = oob_data.get("friendly", [])
                enemy    = oob_data.get("enemy",    [])
                neutral  = oob_data.get("neutral",  [])

                section("─── ORDER OF BATTLE ─")

                # Summary counts
                f_cnt = summary.get("FRIENDLY", len(friendly))
                e_cnt = summary.get("ENEMY",    len(enemy))
                n_cnt = summary.get("NEUTRAL",  len(neutral))
                row("FRIENDLY", f"{f_cnt:3d} units", green)
                row("ENEMY",    f"{e_cnt:3d} units", red)
                row("NEUTRAL",  f"{n_cnt:3d} units", amber)
                y_ref[0] += 6

                def unit_block(units, label, col, max_rows=4):
                    if not units:
                        return
                    section(f"─── {label} ──────────")
                    for u in units[:max_rows]:
                        if not clip_bottom():
                            return
                        u_id   = str(u.get("id",   "?"))[:6]
                        u_type = str(u.get("type", "UNK"))[:12]
                        u_stat = str(u.get("status", "ACTIVE"))[:8]
                        painter.setFont(f_val)
                        painter.setPen(QPen(col))
                        painter.drawText(
                            QRectF(content.left() + 6, y_ref[0],
                                   content.width() - 12, line_h),
                            Qt.AlignmentFlag.AlignVCenter,
                            f"{u_id:<6} {u_type:<12} {u_stat}"
                        )
                        y_ref[0] += line_h + 1
                    if len(units) > max_rows and clip_bottom():
                        painter.setFont(f_hd)
                        painter.setPen(QPen(dim))
                        painter.drawText(
                            QRectF(content.left() + 10, y_ref[0],
                                   content.width() - 20, line_h),
                            Qt.AlignmentFlag.AlignVCenter,
                            f"  +{len(units) - max_rows} more..."
                        )
                        y_ref[0] += line_h + 2

                unit_block(friendly, "FRIENDLY", green)
                unit_block(enemy,    "ENEMY",    red)
                unit_block(neutral,  "NEUTRAL",  amber)

                if not (friendly or enemy or neutral):
                    painter.setFont(f_hd)
                    painter.setPen(QPen(dim))
                    painter.drawText(
                        QRectF(content.left() + 10, y_ref[0],
                               content.width() - 20, line_h),
                        Qt.AlignmentFlag.AlignVCenter, "No units in OOB"
                    )

        except Exception as e:
            logger.error(f"Error drawing mission page: {str(e)}")

    def draw_settings_page(self, painter: QPainter, rect: QRectF):
        """Draw settings page with display type options in a grid layout"""
        try:
            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)

            # Draw page title
            title_rect = rect.adjusted(10, 10, -10, 40)
            if use_gradients:
                self.draw_text(
                    painter, title_rect,
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                    "Display Settings",
                    glow=True
                )
            else:
                painter.drawText(title_rect,
                               Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                               "Display Settings")

            # Calculate grid dimensions
            grid_margin = 15  # Reduced from 30
            section_height = 90  # Reduced from 120

            # Calculate column widths (2 columns)
            col_width = (rect.width() - (grid_margin * 3)) / 2

            # Row 1: Theme selection (left) and PFD (right)
            row1_y = rect.top() + 50

            # Draw theme section (top left)
            self._draw_theme_section(
                painter,
                QRectF(rect.left() + grid_margin, row1_y, col_width, section_height),
                "Visual Theme",
                ["classic", "modern", "night"]  # Removed "futuristic"
            )

            # Draw PFD section (top right)
            self._draw_display_type_section(
                painter,
                QRectF(rect.left() + col_width + (grid_margin * 2), row1_y, col_width, section_height),
                "Primary Flight Display",
                "pfd",
                ["standard", "holographic"]
            )

            # Row 2: MFD only (centered)
            row2_y = row1_y + section_height + grid_margin

            # Draw MFD section (centered in row 2)
            mfd_rect = QRectF(
                rect.left() + (rect.width() - col_width) / 2,  # Center horizontally
                row2_y,
                col_width,
                section_height
            )

            self._draw_display_type_section(
                painter,
                mfd_rect,
                "Multi-Function Display",
                "mfd",
                ["standard", "holographic"]
            )

        except Exception as e:
            logger.error(f"Error drawing settings page: {str(e)}")
            raise

    def _draw_display_type_section(self, painter: QPainter, rect: QRectF,
                                 title: str, category: str, options: List[str]):
        """Draw a display type selection section"""
        try:
            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            corner_radius = self._theme_manager.get_style_param("corner_radius", 0.0)

            # Get current display type for this category
            current_type = self._theme_manager.get_display_type(category, "standard")

            # Draw section background
            if use_gradients:
                # Create gradient background
                gradient = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
                gradient.setColorAt(0, QColor(40, 40, 40, 180))
                gradient.setColorAt(1, QColor(30, 30, 30, 180))

                # Draw with rounded corners if enabled
                if corner_radius > 0:
                    path = QPainterPath()
                    path.addRoundedRect(rect, corner_radius, corner_radius)
                    painter.fillPath(path, gradient)
                else:
                    painter.fillRect(rect, gradient)

                # Draw border with glow
                self.draw_rect(
                    painter, rect,
                    color=self._theme_manager.get_color("hud"),
                    fill=False,
                    corner_radius=corner_radius
                )
            else:
                # Fall back to original drawing
                painter.fillRect(rect, QColor(40, 40, 40, 180))
                painter.setPen(self.hud_color)
                painter.drawRect(rect)

            # Draw section title
            title_rect = rect.adjusted(10, 5, -10, -rect.height() + 25)
            if use_gradients:
                self.draw_text(
                    painter, title_rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    title,
                    glow=True
                )
            else:
                painter.drawText(title_rect,
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                               title)

            # Calculate option dimensions - more compact for grid layout
            option_width = (rect.width() - 30) / len(options)
            option_height = 40  # Reduced from 60
            option_y = rect.top() + 30  # Reduced from 40

            # Store option rectangles for click handling
            if not hasattr(self, '_settings_option_rects'):
                self._settings_option_rects = {}

            if category not in self._settings_option_rects:
                self._settings_option_rects[category] = []
            else:
                self._settings_option_rects[category].clear()

            # Draw options
            for i, option in enumerate(options):
                option_x = rect.left() + 15 + (i * option_width)
                option_rect = QRectF(option_x, option_y, option_width - 5, option_height)

                # Store option rect for click handling
                self._settings_option_rects[category].append((option_rect, option))

                # Highlight current option
                if option == current_type:
                    if use_gradients:
                        # Create gradient for selected item
                        gradient = QLinearGradient(option_rect.left(), option_rect.top(),
                                                 option_rect.right(), option_rect.bottom())
                        gradient.setColorAt(0, QColor(60, 60, 60))
                        gradient.setColorAt(1, QColor(50, 50, 50))

                        # Draw with rounded corners if enabled
                        if corner_radius > 0:
                            path = QPainterPath()
                            path.addRoundedRect(option_rect, corner_radius, corner_radius)
                            painter.fillPath(path, gradient)
                        else:
                            painter.fillRect(option_rect, gradient)

                        # Draw border with glow
                        self.draw_rect(
                            painter, option_rect,
                            color=self._theme_manager.get_color("warning"),
                            fill=False,
                            corner_radius=corner_radius
                        )
                    else:
                        # Fall back to original drawing
                        painter.fillRect(option_rect, QColor(60, 60, 60))
                        painter.setPen(self.warning_color)
                        painter.drawRect(option_rect)
                else:
                    # Draw normal option
                    if use_gradients:
                        # Draw with rounded corners if enabled
                        if corner_radius > 0:
                            path = QPainterPath()
                            path.addRoundedRect(option_rect, corner_radius, corner_radius)
                            painter.fillPath(path, QColor(45, 45, 45))
                        else:
                            painter.fillRect(option_rect, QColor(45, 45, 45))

                        # Draw border
                        self.draw_rect(
                            painter, option_rect,
                            color=self._theme_manager.get_color("hud"),
                            fill=False,
                            corner_radius=corner_radius
                        )
                    else:
                        # Fall back to original drawing
                        painter.fillRect(option_rect, QColor(45, 45, 45))
                        painter.setPen(self.hud_color)
                        painter.drawRect(option_rect)

                # Draw option text
                text_rect = option_rect.adjusted(3, 3, -3, -3)

                # Capitalize first letter of option for display
                display_text = option[0].upper() + option[1:]

                if use_gradients and option == current_type:
                    # Draw selected option text with glow
                    self.draw_text(
                        painter, text_rect,
                        Qt.AlignmentFlag.AlignCenter,
                        display_text,
                        glow=True,
                        color=self._theme_manager.get_color("warning")
                    )
                else:
                    # Draw regular option text
                    if use_gradients:
                        self.draw_text(
                            painter, text_rect,
                            Qt.AlignmentFlag.AlignCenter,
                            display_text,
                            glow=False
                        )
                    else:
                        painter.setPen(self.hud_color)
                        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, display_text)

        except Exception as e:
            logger.error(f"Error drawing display type section: {str(e)}")
            raise

    def _draw_theme_section(self, painter: QPainter, rect: QRectF,
                          title: str, options: List[str]):
        """Draw a theme selection section"""
        try:
            # Get theme parameters
            use_gradients = self._theme_manager.get_style_param("use_gradients", False)
            corner_radius = self._theme_manager.get_style_param("corner_radius", 0.0)

            # Get current theme
            current_theme = self._theme_manager._current_theme.value

            # Draw section background
            if use_gradients:
                # Create gradient background
                gradient = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
                gradient.setColorAt(0, QColor(40, 40, 40, 180))
                gradient.setColorAt(1, QColor(30, 30, 30, 180))

                # Draw with rounded corners if enabled
                if corner_radius > 0:
                    path = QPainterPath()
                    path.addRoundedRect(rect, corner_radius, corner_radius)
                    painter.fillPath(path, gradient)
                else:
                    painter.fillRect(rect, gradient)

                # Draw border with glow
                self.draw_rect(
                    painter, rect,
                    color=self._theme_manager.get_color("hud"),
                    fill=False,
                    corner_radius=corner_radius
                )
            else:
                # Fall back to original drawing
                painter.fillRect(rect, QColor(40, 40, 40, 180))
                painter.setPen(self.hud_color)
                painter.drawRect(rect)

            # Draw section title
            title_rect = rect.adjusted(10, 5, -10, -rect.height() + 25)
            if use_gradients:
                self.draw_text(
                    painter, title_rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    title,
                    glow=True
                )
            else:
                painter.drawText(title_rect,
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                               title)

            # Calculate option dimensions - more compact for grid layout
            option_width = (rect.width() - 30) / len(options)
            option_height = 40  # Reduced from 60
            option_y = rect.top() + 30  # Reduced from 40

            # Store option rectangles for click handling
            if not hasattr(self, '_theme_option_rects'):
                self._theme_option_rects = []
            else:
                self._theme_option_rects.clear()

            # Draw options
            for i, option in enumerate(options):
                option_x = rect.left() + 15 + (i * option_width)
                option_rect = QRectF(option_x, option_y, option_width - 5, option_height)

                # Store option rect for click handling
                self._theme_option_rects.append((option_rect, option))

                # Highlight current option
                if option == current_theme:
                    if use_gradients:
                        # Create gradient for selected item
                        gradient = QLinearGradient(option_rect.left(), option_rect.top(),
                                                 option_rect.right(), option_rect.bottom())
                        gradient.setColorAt(0, QColor(60, 60, 60))
                        gradient.setColorAt(1, QColor(50, 50, 50))

                        # Draw with rounded corners if enabled
                        if corner_radius > 0:
                            path = QPainterPath()
                            path.addRoundedRect(option_rect, corner_radius, corner_radius)
                            painter.fillPath(path, gradient)
                        else:
                            painter.fillRect(option_rect, gradient)

                        # Draw border with glow
                        self.draw_rect(
                            painter, option_rect,
                            color=self._theme_manager.get_color("warning"),
                            fill=False,
                            corner_radius=corner_radius
                        )
                    else:
                        # Fall back to original drawing
                        painter.fillRect(option_rect, QColor(60, 60, 60))
                        painter.setPen(self.warning_color)
                        painter.drawRect(option_rect)
                else:
                    # Draw normal option
                    if use_gradients:
                        # Draw with rounded corners if enabled
                        if corner_radius > 0:
                            path = QPainterPath()
                            path.addRoundedRect(option_rect, corner_radius, corner_radius)
                            painter.fillPath(path, QColor(45, 45, 45))
                        else:
                            painter.fillRect(option_rect, QColor(45, 45, 45))

                        # Draw border
                        self.draw_rect(
                            painter, option_rect,
                            color=self._theme_manager.get_color("hud"),
                            fill=False,
                            corner_radius=corner_radius
                        )
                    else:
                        # Fall back to original drawing
                        painter.fillRect(option_rect, QColor(45, 45, 45))
                        painter.setPen(self.hud_color)
                        painter.drawRect(option_rect)

                # Draw option text
                text_rect = option_rect.adjusted(3, 3, -3, -3)

                # Capitalize first letter of option for display
                display_text = option[0].upper() + option[1:]

                if use_gradients and option == current_theme:
                    # Draw selected option text with glow
                    self.draw_text(
                        painter, text_rect,
                        Qt.AlignmentFlag.AlignCenter,
                        display_text,
                        glow=True,
                        color=self._theme_manager.get_color("warning")
                    )
                else:
                    # Draw regular option text
                    if use_gradients:
                        self.draw_text(
                            painter, text_rect,
                            Qt.AlignmentFlag.AlignCenter,
                            display_text,
                            glow=False
                        )
                    else:
                        painter.setPen(self.hud_color)
                        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, display_text)

        except Exception as e:
            logger.error(f"Error drawing theme section: {str(e)}")
            raise

    def mousePressEvent(self, event):
        """Handle mouse press events"""
        try:
            logger.warning(f"[MFD] ALL CLICKS - Position: ({event.position().x():.1f}, {event.position().y():.1f}), Widget size: ({self.width()}, {self.height()})")

            # Let base class handle the event first
            super().mousePressEvent(event)

            # Calculate menu dimensions
            title_height = float(self.height()) / 12
            menu_width = float(self.width()) / 5
            margin = 20.0

            # Check if click is in menu area
            if event.position().x() < menu_width and event.position().y() > title_height:
                if self.current_page == DisplayPage.RADAR:
                    # Handle radar sub-menu clicks
                    self._handle_radar_menu_click(event, title_height, menu_width)
                else:
                    # Handle main menu clicks
                    self._handle_main_menu_click(event, title_height, menu_width)
            # Handle mission page tab bar clicks
            elif self.current_page == DisplayPage.MISSION:
                self._handle_mission_tab_click(event, title_height, menu_width, margin)
            # Handle clicks in the settings page
            elif self.current_page == DisplayPage.SETTINGS:
                self._handle_settings_click(event, title_height, menu_width, margin)
            # Handle clicks in the radar display area when on radar page
            elif self.current_page == DisplayPage.RADAR and self._current_radar_display:
                # Calculate content area
                content_rect = QRectF(
                    menu_width + margin,
                    title_height + margin,
                    float(self.width()) - menu_width - margin * 2,
                    float(self.height()) - title_height - margin * 2
                )

                # Use full content area for radar display since we removed the static text elements
                radar_content_rect = content_rect.adjusted(10, 10, -10, -10)

                # This is necessary because the legend tab might be positioned outside the content area
                original_pos = QPointF(event.position())

                # Log the click coordinates for debugging
                logger.warning(f"[MFD] Radar click - Original: ({original_pos.x():.1f}, {original_pos.y():.1f})")
                logger.warning(f"[MFD] Content rect: ({radar_content_rect.left():.1f}, {radar_content_rect.top():.1f}, {radar_content_rect.width():.1f}, {radar_content_rect.height():.1f})")

                # Pass to weather radar display if applicable
                if isinstance(self._current_radar_display, WeatherRadarDisplay):
                    # First try to handle as a legend click using ORIGINAL coordinates
                    legend_manager = self._current_radar_display.legend_manager
                    if legend_manager and legend_manager.handle_click(original_pos):
                        logger.warning(f"[MFD] Legend click handled at original position: ({original_pos.x():.1f}, {original_pos.y():.1f})")
                        self.update()  # Update display if click was handled
                        return

                    # If not a legend click and click is in content area, use adjusted coordinates for regular click handling
                    if radar_content_rect.contains(event.position()):
                        adjusted_pos = QPointF(
                            event.position().x() - radar_content_rect.left(),
                            event.position().y() - radar_content_rect.top()
                        )
                        logger.warning(f"[MFD] Using adjusted position for radar click: ({adjusted_pos.x():.1f}, {adjusted_pos.y():.1f})")

                        # Try regular click handling with adjusted coordinates
                        if self._current_radar_display.handle_mouse_click(adjusted_pos):
                            logger.warning(f"[MFD] Radar display click handled at adjusted position")
                            self.update()  # Update display if click was handled
                            return

            event.accept()

        except Exception as e:
            logger.error(f"Error handling mouse press: {str(e)}")
            event.accept()

    def _handle_mission_tab_click(self, event, title_height: float,
                                   menu_width: float, margin: float):
        """Handle clicks on the ROUTE / TARGETS / OOB tab bar in the mission page."""
        try:
            content_left = menu_width + margin
            content_w    = float(self.width()) - menu_width - margin * 2
            tab_top      = title_height + margin + 30   # matches draw_mission_page
            tab_h        = 18.0
            TABS         = ['ROUTE', 'TARGETS', 'OOB']
            tab_w        = content_w / len(TABS)

            cx = event.position().x()
            cy = event.position().y()

            if tab_top <= cy <= tab_top + tab_h and cx >= content_left:
                idx = int((cx - content_left) / tab_w)
                if 0 <= idx < len(TABS):
                    self._mission_tab = TABS[idx]
                    self.update()
        except Exception as e:
            logger.error(f"Error handling mission tab click: {str(e)}")

    def _handle_main_menu_click(self, event, title_height: float, menu_width: float):
        """Handle clicks in the main menu"""
        try:
            item_height = min((float(self.height()) - title_height - 20) / len(self.pages), 40)
            item_index = int((event.position().y() - title_height - 10) // item_height)

            if 0 <= item_index < len(self.pages):
                selected_page = self.pages[item_index]
                self.current_page = selected_page

                # MODIFIED: Automatically select weather radar when clicking on Radar page
                if selected_page == DisplayPage.RADAR:
                    logger.warning("Automatically selecting Weather Radar")
                    self.current_radar_type = RadarType.WEATHER
                    self._update_radar_type()

                self.update()
        except Exception as e:
            logger.error(f"Error handling main menu click: {str(e)}")

    def _handle_radar_menu_click(self, event, title_height: float, menu_width: float):
        """Handle clicks in the radar sub-menu"""
        try:
            item_height = min((float(self.height()) - title_height - 20) / len(self.radar_types), 40)
            item_index = int((event.position().y() - title_height - 10) // item_height)

            if 0 <= item_index < len(self.radar_types):
                selected_type = self.radar_types[item_index]

                if selected_type == RadarType.BACK:
                    # Return to main menu
                    self.current_page = DisplayPage.NAV
                else:
                    # Update radar type
                    self.current_radar_type = selected_type
                    self._update_radar_type()

                self.update()

        except Exception as e:
            logger.error(f"Error handling radar menu click: {str(e)}")

    def _handle_settings_click(self, event, title_height: float, menu_width: float, margin: float):
        """Handle clicks in the settings page"""
        try:
            # Calculate content area
            content_rect = QRectF(
                menu_width + margin,
                title_height + margin,
                float(self.width()) - menu_width - margin * 2,
                float(self.height()) - title_height - margin * 2
            )

            # Get click position
            click_pos = QPointF(event.position())

            # Check if click is in content area
            if not content_rect.contains(click_pos):
                return

            # Check if click is on a display type option
            if hasattr(self, '_settings_option_rects'):
                for category, options in self._settings_option_rects.items():
                    for option_rect, option_value in options:
                        if option_rect.contains(click_pos):
                            # Update display type in theme manager
                            self._theme_manager.set_display_type(category, option_value)
                            logger.info(f"Updated {category} display type to {option_value}")

                            # Invalidate display caches
                            if category == "radar":
                                RadarDisplayFactory.invalidate_cache()
                            elif category == "pfd":
                                # Use signal service to notify about PFD display type change
                                from .display_signal_service import DisplaySignalService
                                DisplaySignalService.get_instance().emit_display_type_changed("pfd", option_value)
                                logger.info(f"Emitted signal for PFD display type change to {option_value}")

                                # Also invalidate the cache directly as a fallback
                                from .pfd_display_factory import PFDDisplayFactory
                                PFDDisplayFactory.invalidate_cache()
                                logger.info("Invalidated PFD display cache")
                            elif category == "mfd":
                                # Use signal service to notify about MFD display type change
                                from .display_signal_service import DisplaySignalService
                                DisplaySignalService.get_instance().emit_display_type_changed("mfd", option_value)
                                logger.info(f"Emitted signal for MFD display type change to {option_value}")

                                # Also invalidate the cache directly as a fallback
                                from .mfd_display_factory import MFDDisplayFactory
                                MFDDisplayFactory.invalidate_cache()
                                logger.info("Invalidated MFD display cache")
                            elif category == "hud":
                                # Use signal service to notify about HUD display type change
                                from .display_signal_service import DisplaySignalService
                                DisplaySignalService.get_instance().emit_display_type_changed("hud", option_value)
                                logger.info(f"Emitted signal for HUD display type change to {option_value}")

                                # Also invalidate the cache directly as a fallback
                                from .hud_display_factory import HUDDisplayFactory
                                HUDDisplayFactory.invalidate_cache()
                                logger.info("Invalidated HUD display cache")

                            # Update display
                            self.update()
                            return

            # Check if click is on a theme option
            if hasattr(self, '_theme_option_rects'):
                for option_rect, option_value in self._theme_option_rects:
                    if option_rect.contains(click_pos):
                        # Map option value to DisplayTheme
                        theme_map = {
                            "classic": DisplayTheme.CLASSIC,
                            "modern": DisplayTheme.MODERN,
                            "night": DisplayTheme.NIGHT
                        }

                        if option_value in theme_map:
                            # Set theme
                            self._theme_manager.set_theme(theme_map[option_value])
                            logger.info(f"Updated theme to {option_value}")

                            # Update display
                            self.update()
                            return

        except Exception as e:
            logger.error(f"Error handling settings click: {str(e)}")
            logger.error(traceback.format_exc())

    def _update_radar_type(self):
        """Update the current radar type and display with enhanced cleanup"""
        try:
            # Store the previous radar type for cleanup
            previous_radar_type = self._current_radar_type
            previous_display = self._current_radar_display

            # Log the radar type change
            logger.warning(f"Changing radar type from {previous_radar_type.__name__ if previous_radar_type else 'None'} to {self.current_radar_type.value}")


            if previous_radar_type:
                try:
                    # Get the display tree manager
                    from .display_nodes.display_tree_manager import get_display_tree_manager
                    tree_manager = get_display_tree_manager()

                    # Reset the previous radar branch
                    radar_type_name = f"{previous_radar_type.__name__.split('_')[0].lower()}_radar"
                    logger.warning(f"Resetting display tree branch for {radar_type_name}")

                    # Use the new reset_radar_branch method
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(tree_manager.reset_radar_branch(radar_type_name))
                    else:
                        loop.run_until_complete(tree_manager.reset_radar_branch(radar_type_name))

                    logger.warning(f"Reset display tree branch for {radar_type_name}")
                except Exception as reset_error:
                    logger.error(f"Error resetting display tree branch: {reset_error}")
                    logger.error(traceback.format_exc())


            try:
                from .radar.radar_display_data_coordinator import get_radar_display_data_coordinator
                coordinator = get_radar_display_data_coordinator()
                coordinator.reset_data()
                logger.warning("Reset all data in radar display data coordinator")
            except Exception as coord_error:
                logger.error(f"Error resetting radar display data coordinator: {coord_error}")
                logger.error(traceback.format_exc())

            # Clear the radar display cache to ensure we get a fresh instance
            logger.warning("Clearing radar display cache")
            RadarDisplayFactory.clear_cache()

            # Map RadarType to specific radar mode type
            if self.current_radar_type == RadarType.WEATHER:
                self._current_radar_type = weather_radarMode
            elif self.current_radar_type == RadarType.TARGETING:
                self._current_radar_type = targeting_radarMode
            elif self.current_radar_type == RadarType.TFR:
                self._current_radar_type = tfr_radarMode
            elif self.current_radar_type == RadarType.SAR:
                self._current_radar_type = sar_radarMode
            elif self.current_radar_type == RadarType.AEWC:
                self._current_radar_type = aewc_radarMode

            # This ensures any references to the old display are removed
            self._current_radar_display = None

            # Force garbage collection to clean up any lingering references
            import gc
            gc.collect()
            logger.warning("Forced garbage collection before creating new display")

            # Create a new display instance for the selected radar type
            logger.warning(f"Creating new display for mode type: {self._current_radar_type.__name__}")
            new_display = RadarDisplayFactory.create_display(self._current_radar_type.STANDBY)

            if not new_display:
                logger.error(f"Failed to create new display for {self._current_radar_type.__name__}")
                return

            logger.warning(f"Successfully created new display: {type(new_display).__name__}")

            # Update the current display and mode
            self._current_radar_display = new_display
            self.radar_data.mode = self._current_radar_type.STANDBY

            # Force a repaint to ensure the new display is shown
            self.update()
            if hasattr(self, 'repaint'):
                self.repaint()

            logger.warning(f"Updated radar type to {self.current_radar_type.value}")

        except Exception as e:
            logger.error(f"Error updating radar type: {str(e)}")
            logger.error(traceback.format_exc())

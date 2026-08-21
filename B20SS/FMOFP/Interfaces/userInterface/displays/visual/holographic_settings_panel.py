"""
Holographic settings panel with advanced 3D visual effects

File Relationships:
- Extends settings_panel.py (base settings panel)
- Uses enhanced_theme_manager.py instead of theme_manager.py
- Used by holographic_radar_display.py and other holographic displays
- Provides theme mapping between base DisplayTheme and EnhancedDisplayTheme
"""
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QFont
from typing import Dict, List, Optional, Tuple, Any, Callable
import math
from .settings_panel import SettingsPanel, SettingsOption
from .theme_manager import get_theme_manager, DisplayTheme
from .enhanced_theme_manager import get_enhanced_theme_manager, EnhancedDisplayTheme
from .enhanced_effects import get_enhanced_visual_effects
from Utils.logger.sys_logger import get_logger

logger = get_logger()

# Theme mapping between base DisplayTheme and EnhancedDisplayTheme
THEME_MAPPING = {
    "classic": EnhancedDisplayTheme.CLASSIC,
    "modern": EnhancedDisplayTheme.MODERN,
    "night": EnhancedDisplayTheme.STEALTH,
    "holographic": EnhancedDisplayTheme.HOLOGRAPHIC,
    "tactical": EnhancedDisplayTheme.TACTICAL  # Added tactical mapping
}

# Reverse mapping for getting base theme name from enhanced theme
REVERSE_THEME_MAPPING = {
    EnhancedDisplayTheme.CLASSIC: "classic",
    EnhancedDisplayTheme.MODERN: "modern",
    EnhancedDisplayTheme.STEALTH: "night",
    EnhancedDisplayTheme.HOLOGRAPHIC: "holographic",
    EnhancedDisplayTheme.TACTICAL: "tactical",  # Proper mapping
    EnhancedDisplayTheme.CUSTOM: "custom"  # Proper mapping
}

class HolographicSettingsPanel(SettingsPanel):
    """Interactive holographic settings panel with 3D visual effects"""
    
    def __init__(self):
        """Initialize holographic settings panel"""
        super().__init__()
        
        # Use both theme managers - base for compatibility, enhanced for actual functionality
        self._base_theme_manager = get_theme_manager()
        self._enhanced_theme_manager = get_enhanced_theme_manager()
        self._visual_effects = get_enhanced_visual_effects()
        
        # Holographic properties
        self._depth_offset = 0.0  # Depth offset for 3D effect
        self._parallax_offset_x = 0.0  # Parallax offset for mouse movement
        self._parallax_offset_y = 0.0  # Parallax offset for mouse movement
        self._hover_category = -1  # Currently hovered category
        self._hover_option = -1  # Currently hovered option
        
        # Animation properties
        self._pulse_time = 0.0  # Pulse time for animations
        self._last_update_time = 0.0  # Last update time
        
        # Customize appearance
        self.title = "HOLOGRAPHIC DISPLAY SETTINGS"
        self.width = 350  # Slightly wider for holographic effects
        self.height = 450  # Slightly taller for holographic effects
        
        # Add practical categories for aircraft MFD
        self.categories = ["DISPLAY", "MODE SETTINGS"]
        
        # Reference to parent for context-aware settings
        self.parent = None
    
    def add_setting(self, id: str, label: str, value_type: str, current_value: Any,
                  options: Optional[List[Tuple[str, Any]]] = None,
                  min_value: Optional[float] = None, max_value: Optional[float] = None,
                  on_change: Optional[Callable[[Any], None]] = None):
        """Add a new setting to the panel"""
        # Create setting option
        option = SettingsOption(
            id, label, value_type, current_value, 
            options, min_value, max_value, on_change
        )
        
        # Add to options list
        self.options.append(option)
    
    def update(self, delta_time: float):
        """Update panel animations with holographic effects"""
        # Update base panel animations
        super().update(delta_time)
        
        # Update holographic effects
        self._pulse_time += delta_time * 2.0
        if self._pulse_time > 1000.0:
            self._pulse_time = 0.0
            
        # Update depth offset with subtle animation
        self._depth_offset = math.sin(self._pulse_time) * 0.1
    
    def draw(self, painter: QPainter, rect: QRectF):
        """Draw holographic settings panel with enhanced visual effects"""
        if not self.visible:
            return
            
        # Calculate panel rect with animation
        panel_width = self.width * self.animation_progress
        panel_height = self.height
        
        # Center panel in rect if position not specified
        if self.position == (0, 0):
            x = (rect.width() - panel_width) / 2
            y = (rect.height() - panel_height) / 2
        else:
            x, y = self.position
        
        panel_rect = QRectF(x, y, panel_width, panel_height)
        
        # Save painter state
        painter.save()
        
        try:
            # Draw panel background with enhanced effects
            background_color = QColor(self._enhanced_theme_manager.get_color("overlay_background"))
            painter.fillRect(panel_rect, background_color)
            
            # Draw panel frame with holographic effects
            self._visual_effects.draw_angular_frame(
                painter,
                panel_rect,
                color=self._enhanced_theme_manager.get_color("hud"),
                corner_style="hexagonal",
                glow=True
            )
            
            # Draw holographic corner accents
            self._draw_corner_accents(painter, panel_rect)
            
            # Draw title with holographic effects
            title_rect = QRectF(
                panel_rect.x() + 10,
                panel_rect.y() + 10,
                panel_rect.width() - 20,
                30
            )
            
            self._visual_effects.draw_enhanced_text(
                painter,
                title_rect,
                Qt.AlignmentFlag.AlignCenter,
                self.title,
                glow=True,
                glow_color=self._enhanced_theme_manager.get_color("hud")
            )
            
            # Draw categories with holographic effects
            self._draw_holographic_categories(painter, panel_rect)
            
            # Draw options for current category with holographic effects
            self._draw_holographic_options(painter, panel_rect)
            
        finally:
            # Restore painter state
            painter.restore()
    
    def _draw_corner_accents(self, painter: QPainter, rect: QRectF):
        """Draw holographic corner accents"""
        # Get corner size based on rect dimensions
        corner_size = min(rect.width(), rect.height()) * 0.05
        
        # Get accent color with pulse effect
        pulse_factor = self._visual_effects.get_pulse_factor(
            rate=1.5,
            min_value=0.7,
            max_value=1.0
        )
        
        accent_color = QColor(self._enhanced_theme_manager.get_color("data_primary"))
        accent_color.setAlpha(int(accent_color.alpha() * pulse_factor))
        
        # Draw corner accents with glow
        # Top-left corner
        self._visual_effects.draw_enhanced_line(
            painter,
            QPointF(rect.left() + 5, rect.top() + corner_size + 5),
            QPointF(rect.left() + 5, rect.top() + 5),
            color=accent_color,
            width=2.0,
            glow=True
        )
        
        self._visual_effects.draw_enhanced_line(
            painter,
            QPointF(rect.left() + 5, rect.top() + 5),
            QPointF(rect.left() + corner_size + 5, rect.top() + 5),
            color=accent_color,
            width=2.0,
            glow=True
        )
        
        # Top-right corner
        self._visual_effects.draw_enhanced_line(
            painter,
            QPointF(rect.right() - corner_size - 5, rect.top() + 5),
            QPointF(rect.right() - 5, rect.top() + 5),
            color=accent_color,
            width=2.0,
            glow=True
        )
        
        self._visual_effects.draw_enhanced_line(
            painter,
            QPointF(rect.right() - 5, rect.top() + 5),
            QPointF(rect.right() - 5, rect.top() + corner_size + 5),
            color=accent_color,
            width=2.0,
            glow=True
        )
        
        # Bottom-right corner
        self._visual_effects.draw_enhanced_line(
            painter,
            QPointF(rect.right() - 5, rect.bottom() - corner_size - 5),
            QPointF(rect.right() - 5, rect.bottom() - 5),
            color=accent_color,
            width=2.0,
            glow=True
        )
        
        self._visual_effects.draw_enhanced_line(
            painter,
            QPointF(rect.right() - 5, rect.bottom() - 5),
            QPointF(rect.right() - corner_size - 5, rect.bottom() - 5),
            color=accent_color,
            width=2.0,
            glow=True
        )
        
        # Bottom-left corner
        self._visual_effects.draw_enhanced_line(
            painter,
            QPointF(rect.left() + corner_size + 5, rect.bottom() - 5),
            QPointF(rect.left() + 5, rect.bottom() - 5),
            color=accent_color,
            width=2.0,
            glow=True
        )
        
        self._visual_effects.draw_enhanced_line(
            painter,
            QPointF(rect.left() + 5, rect.bottom() - 5),
            QPointF(rect.left() + 5, rect.bottom() - corner_size - 5),
            color=accent_color,
            width=2.0,
            glow=True
        )
    
    def _draw_holographic_categories(self, painter: QPainter, panel_rect: QRectF):
        """Draw settings categories with holographic effects"""
        # Create categories rect
        categories_rect = QRectF(
            panel_rect.x() + 10,
            panel_rect.y() + 50,
            panel_rect.width() - 20,
            30
        )
        
        # Draw categories background with fallback
        try:
            background_color = QColor(self._enhanced_theme_manager.get_color("menu_background"))
        except Exception:
            # Fallback to overlay_background with reduced opacity
            background_color = QColor(self._enhanced_theme_manager.get_color("overlay_background"))
            background_color.setAlpha(int(background_color.alpha() * 0.7))
        painter.fillRect(categories_rect, background_color)
        
        # Draw categories frame with holographic effects
        self._visual_effects.draw_enhanced_rect(
            painter,
            categories_rect,
            color=self._enhanced_theme_manager.get_color("hud"),
            fill=False
        )
        
        # Draw category tabs
        if not self.categories:
            return
            
        tab_width = categories_rect.width() / len(self.categories)
        
        for i, category in enumerate(self.categories):
            # Create tab rect
            tab_rect = QRectF(
                categories_rect.x() + i * tab_width,
                categories_rect.y(),
                tab_width,
                categories_rect.height()
            )
            
            # Draw tab background if selected or hovered
            if i == self.current_category or i == self._hover_category:
                try:
                    highlight_color = QColor(self._enhanced_theme_manager.get_color("menu_highlight"))
                except Exception:
                    # Fallback to data_primary with reduced opacity
                    highlight_color = QColor(self._enhanced_theme_manager.get_color("data_primary"))
                    highlight_color.setAlpha(int(highlight_color.alpha() * 0.3))
                painter.fillRect(tab_rect, highlight_color)
                
                # Draw highlight border with holographic effects
                self._visual_effects.draw_enhanced_rect(
                    painter,
                    tab_rect,
                    color=self._enhanced_theme_manager.get_color("data_primary"),
                    fill=False,
                    glow=True
                )
            
            # Draw tab text with holographic effects
            self._visual_effects.draw_enhanced_text(
                painter,
                tab_rect,
                Qt.AlignmentFlag.AlignCenter,
                category,
                glow=i == self.current_category,
                glow_color=self._enhanced_theme_manager.get_color("data_primary") if i == self.current_category else self._enhanced_theme_manager.get_color("hud")
            )
    
    def _draw_holographic_options(self, painter: QPainter, panel_rect: QRectF):
        """Draw settings options for current category with holographic effects"""
        # Create options rect
        options_rect = QRectF(
            panel_rect.x() + 10,
            panel_rect.y() + 90,
            panel_rect.width() - 20,
            panel_rect.height() - 100
        )
        
        # Get options for current category
        category_options = self._get_category_options()
        
        # Draw options
        option_height = 40
        for i, option in enumerate(category_options):
            # Create option rect
            option_rect = QRectF(
                options_rect.x(),
                options_rect.y() + i * option_height,
                options_rect.width(),
                option_height
            )
            
            # Draw option background if focused or hovered
            if option.is_focused or i == self._hover_option:
                try:
                    highlight_color = QColor(self._enhanced_theme_manager.get_color("menu_highlight"))
                except Exception:
                    # Fallback to data_primary with reduced opacity
                    highlight_color = QColor(self._enhanced_theme_manager.get_color("data_primary"))
                    highlight_color.setAlpha(int(highlight_color.alpha() * 0.3))
                painter.fillRect(option_rect, highlight_color)
                
                # Draw highlight border with holographic effects
                self._visual_effects.draw_enhanced_rect(
                    painter,
                    option_rect,
                    color=self._enhanced_theme_manager.get_color("data_primary"),
                    fill=False,
                    glow=True
                )
            
            # Draw option label with holographic effects
            label_rect = QRectF(
                option_rect.x() + 10,
                option_rect.y(),
                option_rect.width() / 2 - 10,
                option_rect.height()
            )
            
            self._visual_effects.draw_enhanced_text(
                painter,
                label_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                option.label,
                glow=option.is_focused,
                glow_color=self._enhanced_theme_manager.get_color("data_primary") if option.is_focused else self._enhanced_theme_manager.get_color("hud")
            )
            
            # Draw option value with holographic effects
            value_rect = QRectF(
                option_rect.x() + option_rect.width() / 2,
                option_rect.y(),
                option_rect.width() / 2 - 10,
                option_rect.height()
            )
            
            # Draw different controls based on value type
            if option.value_type == 'toggle':
                self._draw_holographic_toggle(painter, value_rect, option)
            elif option.value_type == 'select':
                self._draw_holographic_select(painter, value_rect, option)
            elif option.value_type == 'range':
                self._draw_holographic_range(painter, value_rect, option)
    
    def _draw_holographic_toggle(self, painter: QPainter, rect: QRectF, option: SettingsOption):
        """Draw toggle control with holographic effects"""
        # Draw toggle background
        toggle_width = 60
        toggle_height = 24
        
        toggle_rect = QRectF(
            rect.x() + rect.width() - toggle_width,
            rect.y() + (rect.height() - toggle_height) / 2,
            toggle_width,
            toggle_height
        )
        
        # Draw background
        background_color = QColor(30, 30, 30)
        painter.fillRect(toggle_rect, background_color)
        
        # Draw border with holographic effects
        self._visual_effects.draw_enhanced_rect(
            painter,
            toggle_rect,
            color=self._enhanced_theme_manager.get_color("hud"),
            fill=False
        )
        
        # Draw toggle state
        if option.current_value:
            # ON state
            toggle_color = self._enhanced_theme_manager.get_color("data_primary")
            toggle_label = "ON"
            toggle_position = 0.7  # 70% to the right
        else:
            # OFF state
            toggle_color = self._enhanced_theme_manager.get_color("menu_text")
            toggle_label = "OFF"
            toggle_position = 0.3  # 30% to the right
        
        # Draw toggle indicator with holographic effects
        indicator_size = toggle_height - 6
        indicator_rect = QRectF(
            toggle_rect.x() + 3 + (toggle_rect.width() - indicator_size - 6) * toggle_position,
            toggle_rect.y() + 3,
            indicator_size,
            indicator_size
        )
        
        self._visual_effects.draw_enhanced_rect(
            painter,
            indicator_rect,
            color=toggle_color,
            fill=True,
            glow=option.current_value
        )
        
        # Draw toggle label with holographic effects
        self._visual_effects.draw_enhanced_text(
            painter,
            toggle_rect,
            Qt.AlignmentFlag.AlignCenter,
            toggle_label,
            glow=option.current_value,
            glow_color=toggle_color
        )
    
    def _draw_holographic_select(self, painter: QPainter, rect: QRectF, option: SettingsOption):
        """Draw select control with holographic effects"""
        # Draw value text
        value_text = option.get_current_value_label()
        
        # Draw arrows
        arrow_width = 20
        arrow_height = rect.height()
        
        # Left arrow
        left_arrow_rect = QRectF(
            rect.x(),
            rect.y(),
            arrow_width,
            arrow_height
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            left_arrow_rect,
            Qt.AlignmentFlag.AlignCenter,
            "◀",
            glow=option.is_focused,
            glow_color=self._enhanced_theme_manager.get_color("data_primary")
        )
        
        # Right arrow
        right_arrow_rect = QRectF(
            rect.x() + rect.width() - arrow_width,
            rect.y(),
            arrow_width,
            arrow_height
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            right_arrow_rect,
            Qt.AlignmentFlag.AlignCenter,
            "▶",
            glow=option.is_focused,
            glow_color=self._enhanced_theme_manager.get_color("data_primary")
        )
        
        # Value text with holographic effects
        value_text_rect = QRectF(
            rect.x() + arrow_width,
            rect.y(),
            rect.width() - arrow_width * 2,
            arrow_height
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            value_text_rect,
            Qt.AlignmentFlag.AlignCenter,
            value_text,
            glow=option.is_focused,
            glow_color=self._enhanced_theme_manager.get_color("data_primary")
        )
    
    def _draw_holographic_range(self, painter: QPainter, rect: QRectF, option: SettingsOption):
        """Draw range slider control with holographic effects"""
        # Draw slider background
        slider_height = 10
        slider_rect = QRectF(
            rect.x(),
            rect.y() + (rect.height() - slider_height) / 2,
            rect.width(),
            slider_height
        )
        
        # Draw background
        background_color = QColor(30, 30, 30)
        painter.fillRect(slider_rect, background_color)
        
        # Draw border with holographic effects
        self._visual_effects.draw_enhanced_rect(
            painter,
            slider_rect,
            color=self._enhanced_theme_manager.get_color("hud"),
            fill=False
        )
        
        # Calculate fill position
        if option.min_value is not None and option.max_value is not None:
            fill_position = (option.current_value - option.min_value) / (option.max_value - option.min_value)
            fill_position = max(0.0, min(1.0, fill_position))
            
            # Draw filled portion
            fill_rect = QRectF(
                slider_rect.x(),
                slider_rect.y(),
                slider_rect.width() * fill_position,
                slider_rect.height()
            )
            
            fill_color = self._enhanced_theme_manager.get_color("data_primary")
            painter.fillRect(fill_rect, fill_color)
            
            # Draw slider handle with holographic effects
            handle_size = slider_height * 2
            handle_rect = QRectF(
                slider_rect.x() + (slider_rect.width() - handle_size) * fill_position,
                slider_rect.y() + (slider_rect.height() - handle_size) / 2,
                handle_size,
                handle_size
            )
            
            self._visual_effects.draw_enhanced_ellipse(
                painter,
                handle_rect,
                color=self._enhanced_theme_manager.get_color("data_primary"),
                fill=True,
                glow=option.is_focused
            )
        
        # Draw value text with holographic effects
        value_text = f"{option.current_value:.1f}" if isinstance(option.current_value, float) else str(option.current_value)
        value_text_rect = QRectF(
            rect.x(),
            rect.y() + slider_rect.height() + 5,
            rect.width(),
            rect.height() - slider_rect.height() - 5
        )
        
        self._visual_effects.draw_enhanced_text(
            painter,
            value_text_rect,
            Qt.AlignmentFlag.AlignCenter,
            value_text,
            glow=option.is_focused,
            glow_color=self._enhanced_theme_manager.get_color("data_primary")
        )
    
    def _on_theme_changed(self, theme_name: str):
        """Handle theme change by mapping between base and enhanced theme systems
        
        This is the key method that bridges the gap between the two theme systems.
        It maps the base theme name (e.g., "night") to the enhanced theme enum
        (e.g., EnhancedDisplayTheme.STEALTH) and updates both theme managers.
        """
        logger.info(f"[HOLO_SETTINGS_PANEL] Changing theme to {theme_name}")
        logger.info(f"[HOLO_SETTINGS_PANEL] Current theme before change: {self._enhanced_theme_manager.get_theme().name}")
        
        # Map base theme name to enhanced theme enum
        if theme_name in THEME_MAPPING:
            enhanced_theme = THEME_MAPPING[theme_name]
            logger.info(f"[HOLO_SETTINGS_PANEL] Mapped to enhanced theme: {enhanced_theme.name}")
            
            # Update enhanced theme manager
            self._enhanced_theme_manager.set_theme(enhanced_theme)
            logger.info(f"[HOLO_SETTINGS_PANEL] Enhanced theme manager updated to: {enhanced_theme.name}")
            
            # Update base theme manager for compatibility
            # This ensures both theme systems stay in sync
            base_theme_map = {
                "classic": DisplayTheme.CLASSIC,
                "modern": DisplayTheme.MODERN,
                "night": DisplayTheme.NIGHT,
                "holographic": DisplayTheme.MODERN,  # Map to MODERN as fallback
                "tactical": DisplayTheme.MODERN      # Map to MODERN as fallback
            }
            
            if theme_name in base_theme_map:
                base_theme = base_theme_map[theme_name]
                self._base_theme_manager.set_theme(base_theme)
                logger.info(f"[HOLO_SETTINGS_PANEL] Base theme manager updated to: {base_theme.name}")
            
            # Update parent display if available - IMPROVED IMPLEMENTATION
            if self.parent:
                logger.info(f"[HOLO_SETTINGS_PANEL] Parent display found, updating with new theme: {theme_name}")
                
                # Try multiple methods to update the parent's theme
                updated = False
                
                # Method 1: Direct theme change method
                if hasattr(self.parent, "_on_theme_changed"):
                    try:
                        logger.info("[HOLO_SETTINGS_PANEL] Parent has _on_theme_changed method, calling it directly")
                        self.parent._on_theme_changed(theme_name)
                        updated = True
                    except Exception as e:
                        logger.error(f"[HOLO_SETTINGS_PANEL] Error calling parent _on_theme_changed: {str(e)}")
                
                # Method 2: Update theme managers directly
                if not updated and hasattr(self.parent, "_theme_manager") and hasattr(self.parent, "_enhanced_theme_manager"):
                    try:
                        logger.info("[HOLO_SETTINGS_PANEL] Updating parent theme managers directly")
                        if theme_name in base_theme_map:
                            self.parent._theme_manager.set_theme(base_theme_map[theme_name])
                        if theme_name in THEME_MAPPING:
                            self.parent._enhanced_theme_manager.set_theme(THEME_MAPPING[theme_name])
                        updated = True
                    except Exception as e:
                        logger.error(f"[HOLO_SETTINGS_PANEL] Error updating parent theme managers: {str(e)}")
                
                # Method 3: Use set_theme method if available
                if not updated and hasattr(self.parent, "set_theme"):
                    try:
                        logger.info("[HOLO_SETTINGS_PANEL] Calling set_theme on parent")
                        self.parent.set_theme(theme_name)
                        updated = True
                    except Exception as e:
                        logger.error(f"[HOLO_SETTINGS_PANEL] Error calling parent set_theme: {str(e)}")
                
                # Force update of colors from theme
                try:
                    if hasattr(self.parent, "update_colors_from_theme"):
                        logger.info("[HOLO_SETTINGS_PANEL] Calling update_colors_from_theme on parent")
                        self.parent.update_colors_from_theme()
                except Exception as e:
                    logger.error(f"[HOLO_SETTINGS_PANEL] Error updating parent colors: {str(e)}")
                
                # Force a repaint with explicit repaint method if available
                try:
                    logger.info("[HOLO_SETTINGS_PANEL] Requesting parent update")
                    self.parent.update()
                    if hasattr(self.parent, "repaint"):
                        logger.info("[HOLO_SETTINGS_PANEL] Forcing parent repaint")
                        self.parent.repaint()
                except Exception as e:
                    logger.error(f"[HOLO_SETTINGS_PANEL] Error repainting parent: {str(e)}")
                
            logger.info(f"[HOLO_SETTINGS_PANEL] Theme change complete: {theme_name} (enhanced: {enhanced_theme.name})")
        else:
            logger.error(f"[HOLO_SETTINGS_PANEL] Unknown theme name: {theme_name}")
            
    def _on_display_type_changed(self, display_type: str):
        """Handle display type change with improved parent update mechanism
        
        This method switches between standard and holographic display types.
        It updates the theme manager and forces a display refresh.
        """
        logger.info(f"[HOLO_SETTINGS_PANEL] Changing display type to {display_type}")
        
        # Update theme manager with new display type
        from ..visual.theme_manager import get_theme_manager
        theme_manager = get_theme_manager()
        
        # Set the display type for radar
        theme_manager.set_display_type("radar", display_type)
        logger.info(f"Set radar display type to: {display_type}")
        
        # Also set the display type for MFD to ensure consistency
        theme_manager.set_display_type("mfd", display_type)
        logger.info(f"Set mfd display type to: {display_type}")
        
        logger.info(f"[HOLO_SETTINGS_PANEL] Set radar display type to {display_type}")
        
        # Clear the radar display cache to force recreation
        from ..radar.radar_display_factory import RadarDisplayFactory
        RadarDisplayFactory.clear_cache()
        logger.info("Cleared entire radar display cache")
        
        # Also clear the MFD display cache to force recreation
        from ..mfd_display_factory import MFDDisplayFactory
        MFDDisplayFactory.invalidate_cache()
        logger.info("Invalidated MFD display cache")
        
        # Log the change
        logger.info(f"Display type changed for radar: '{display_type}'")
        logger.info(f"Display type changed for mfd: '{display_type}'")
        
        # Notify parent display if available - IMPROVED IMPLEMENTATION
        if self.parent:
            logger.info(f"[HOLO_SETTINGS_PANEL] Parent display found, updating with new display type: {display_type}")
            
            # Try multiple methods to update the parent display
            updated = False
            
            # Method 1: Use specific display switching methods
            if display_type == "standard" and hasattr(self.parent, "switch_to_standard_display"):
                try:
                    logger.info("[HOLO_SETTINGS_PANEL] Calling switch_to_standard_display on parent")
                    self.parent.switch_to_standard_display()
                    updated = True
                except Exception as e:
                    logger.error(f"[HOLO_SETTINGS_PANEL] Error switching to standard display: {str(e)}")
            elif display_type == "holographic" and hasattr(self.parent, "switch_to_holographic_display"):
                try:
                    logger.info("[HOLO_SETTINGS_PANEL] Calling switch_to_holographic_display on parent")
                    self.parent.switch_to_holographic_display()
                    updated = True
                except Exception as e:
                    logger.error(f"[HOLO_SETTINGS_PANEL] Error switching to holographic display: {str(e)}")
            # Try with set_display_type method
            elif hasattr(self.parent, "set_display_type"):
                try:
                    logger.info(f"[HOLO_SETTINGS_PANEL] Calling set_display_type({display_type}) on parent")
                    self.parent.set_display_type(display_type)
                    updated = True
                except Exception as e:
                    logger.error(f"[HOLO_SETTINGS_PANEL] Error calling set_display_type: {str(e)}")
            
            # Method 2: Use generic update_display_type method
            if not updated and hasattr(self.parent, "update_display_type"):
                try:
                    logger.info("[HOLO_SETTINGS_PANEL] Calling update_display_type on parent")
                    self.parent.update_display_type(display_type)
                    updated = True
                except Exception as e:
                    logger.error(f"[HOLO_SETTINGS_PANEL] Error updating display type: {str(e)}")
            
            # Method 3: Use display signal service
            if not updated:
                try:
                    from ..display_signal_service import DisplaySignalService
                    signal_service = DisplaySignalService.get_instance()
                    # Emit signals for both radar and MFD
                    logger.info(f"[HOLO_SETTINGS_PANEL] Emitting display_type_changed signal: radar={display_type}")
                    signal_service.emit_display_type_changed("radar", display_type)
                    logger.info(f"[HOLO_SETTINGS_PANEL] Emitting display_type_changed signal: mfd={display_type}")
                    signal_service.emit_display_type_changed("mfd", display_type)
                    updated = True
                except Exception as e:
                    logger.error(f"[HOLO_SETTINGS_PANEL] Error emitting display type signal: {str(e)}")
            
            # If no method worked, log a warning but don't fail
            if not updated:
                logger.warning("[HOLO_SETTINGS_PANEL] Parent does not have suitable display switching method")
                # Try a direct property update as last resort
                try:
                    if hasattr(self.parent, "display_type"):
                        self.parent.display_type = display_type
                        logger.info(f"[HOLO_SETTINGS_PANEL] Set parent display_type property directly to {display_type}")
                except Exception as e:
                    logger.error(f"[HOLO_SETTINGS_PANEL] Error setting display_type property: {str(e)}")
            
            # Force update of parent display
            try:
                logger.info("[HOLO_SETTINGS_PANEL] Requesting parent update")
                self.parent.update()
                if hasattr(self.parent, "repaint"):
                    logger.info("[HOLO_SETTINGS_PANEL] Forcing parent repaint")
                    self.parent.repaint()
            except Exception as e:
                logger.error(f"[HOLO_SETTINGS_PANEL] Error repainting parent: {str(e)}")
                
        logger.info(f"[HOLO_SETTINGS_PANEL] Display type change complete: {display_type}")
    
    def _get_category_options(self) -> List[SettingsOption]:
        """Get options for current category with practical MFD settings"""
        if not self.categories or self.current_category >= len(self.categories):
            return []
            
        category = self.categories[self.current_category]
        
        # Filter options by category
        if category == "DISPLAY":
            # Return display options including theme and display type
            display_options = []
            
            # First, check if we have a theme option
            theme_option = None
            for option in self.options:
                if option.id == "theme":
                    theme_option = option
                    break
            
            # If no theme option was found, add a default one
            if not theme_option:
                # Get current theme from enhanced theme manager
                current_enhanced_theme = self._enhanced_theme_manager.get_theme()
                
                # Map enhanced theme to base theme name
                current_theme_name = REVERSE_THEME_MAPPING.get(
                    current_enhanced_theme, "holographic"
                )
                
                # Create the theme option directly with a direct callback
                theme_option = SettingsOption(
                    "theme", 
                    "Theme", 
                    "select", 
                    current_theme_name,
                    options=[
                        ("Classic", "classic"), 
                        ("Modern", "modern"), 
                        ("Night", "night"), 
                        ("Holographic", "holographic")
                    ],
                    on_change=lambda value: self._on_theme_changed(value)
                )
                
                # Add the option to the list
                self.options.append(theme_option)
                
                # Log that we added the theme setting with a callback
                logger.info(f"[HOLO_SETTINGS_PANEL] Added theme setting with direct lambda callback")
                
                # Get the newly added theme option
                for option in self.options:
                    if option.id == "theme":
                        theme_option = option
                        break
            
            # Add the theme option to our display options
            if theme_option:
                display_options.append(theme_option)
                
            # Check if we have a display_type option
            display_type_option = None
            for option in self.options:
                if option.id == "display_type":
                    display_type_option = option
                    break
                    
            # If no display_type option was found, add a default one
            if not display_type_option:
                # Get current display type from theme manager
                from ..visual.theme_manager import get_theme_manager
                theme_manager = get_theme_manager()
                current_display_type = theme_manager.get_display_type("radar", "holographic")
                
                # Add display type setting with proper callback
                self.add_setting(
                    "display_type",
                    "Display Type",
                    "select",
                    current_display_type,
                    options=[
                        ("Standard", "standard"),
                        ("Holographic", "holographic")
                    ],
                    on_change=self._on_display_type_changed
                )
                
                # Log that we added the display type setting
                logger.info("[HOLO_SETTINGS_PANEL] Added display type setting")
                
                # Get the newly added display type option
                for option in self.options:
                    if option.id == "display_type":
                        display_type_option = option
                        break
                        
            # Add the display type option to our display options
            if display_type_option:
                display_options.append(display_type_option)
            
            # Add other display-related options
            display_related_ids = [
                "theme", "display_type"
            ]
            
            # Add all display-related options (except those we already added)
            for option in self.options:
                if option.id in display_related_ids and option.id not in ["theme", "display_type"]:
                    # Log the callback status for debugging
                    logger.info(f"[HOLO_SETTINGS_PANEL] Adding option {option.id} with callback: {option.on_change is not None}")
                    if option.on_change is not None:
                        logger.info(f"[HOLO_SETTINGS_PANEL] Callback for {option.id}: {option.on_change}")
                    display_options.append(option)
            
            # Remove the log message that's causing spam
            return display_options
        elif category == "MODE SETTINGS":
            # Return all mode-specific settings
            mode_options = []
            
            # Mode-specific settings IDs
            mode_related_ids = [
                "target_filtering", "waypoint_display", "alert_threshold",
                "encryption_level", "weapon_selection"
            ]
            
            # Add all mode-related options
            for option in self.options:
                if option.id in mode_related_ids:
                    # Log the callback status for debugging
                    logger.info(f"[HOLO_SETTINGS_PANEL] Adding mode option {option.id} with callback: {option.on_change is not None}")
                    if option.on_change is not None:
                        logger.info(f"[HOLO_SETTINGS_PANEL] Callback for {option.id}: {option.on_change}")
                    mode_options.append(option)
            
            logger.info(f"[HOLO_SETTINGS] Found {len(mode_options)} mode options")
            return mode_options
            
        return []
    
    def handle_click(self, pos: QPointF) -> bool:
        """Handle mouse click on holographic settings panel with enhanced effects"""
        if not self.visible or self.animation_progress < 0.9:
            return False
            
        # Calculate panel rect
        panel_width = self.width
        panel_height = self.height
        
        # Center panel if position not specified
        if self.position == (0, 0):
            x = (800 - panel_width) / 2  # Assuming 800x600 display
            y = (600 - panel_height) / 2
        else:
            x, y = self.position
        
        panel_rect = QRectF(x, y, panel_width, panel_height)
        
        # Check if click is within panel
        if not panel_rect.contains(pos):
            self.hide()
            return True
        
        # Check if click is on categories
        categories_rect = QRectF(
            panel_rect.x() + 10,
            panel_rect.y() + 50,
            panel_rect.width() - 20,
            30
        )
        
        if categories_rect.contains(pos) and self.categories:
            # Calculate which category was clicked
            tab_width = categories_rect.width() / len(self.categories)
            category_index = int((pos.x() - categories_rect.x()) / tab_width)
            
            if 0 <= category_index < len(self.categories):
                self.current_category = category_index
                return True
        
        # Check if click is on options
        options_rect = QRectF(
            panel_rect.x() + 10,
            panel_rect.y() + 90,
            panel_rect.width() - 20,
            panel_rect.height() - 100
        )
        
        if options_rect.contains(pos):
            # Get options for current category
            category_options = self._get_category_options()
            
            # Calculate which option was clicked
            option_height = 40
            option_index = int((pos.y() - options_rect.y()) / option_height)
            
            if 0 <= option_index < len(category_options):
                option = category_options[option_index]
                
                # Reset focus for all options
                for opt in self.options:
                    opt.is_focused = False
                
                # Set focus for clicked option
                option.is_focused = True
                
                # Handle click based on option type and position
                if option.value_type == 'toggle':
                    # Toggle value
                    option.set_value(not option.current_value)
                    return True
                elif option.value_type == 'select':
                    # Check if click is on left or right arrow
                    value_rect = QRectF(
                        options_rect.x() + options_rect.width() / 2,
                        options_rect.y() + option_index * option_height,
                        options_rect.width() / 2 - 10,
                        option_height
                    )
                    
                    arrow_width = 20
                    
                    # Left arrow
                    left_arrow_rect = QRectF(
                        value_rect.x(),
                        value_rect.y(),
                        arrow_width,
                        value_rect.height()
                    )
                    
                    # Right arrow
                    right_arrow_rect = QRectF(
                        value_rect.x() + value_rect.width() - arrow_width,
                        value_rect.y(),
                        arrow_width,
                        value_rect.height()
                    )
                    
                    if left_arrow_rect.contains(pos):
                        # Special handling for theme option
                        if option.id == "theme":
                            # Find current index
                            current_index = -1
                            for i, (_, value) in enumerate(option.options):
                                if value == option.current_value:
                                    current_index = i
                                    break
                            
                            # Move to previous index
                            if current_index >= 0:
                                prev_index = (current_index - 1) % len(option.options)
                                _, prev_value = option.options[prev_index]
                                
                                # Update value
                                option.current_value = prev_value
                                
                                # Call callback directly
                                if option.id == "theme" and hasattr(self, "_on_theme_changed"):
                                    logger.info(f"[HOLO_SETTINGS_PANEL] Directly calling theme callback with {prev_value}")
                                    self._on_theme_changed(prev_value)
                                else:
                                    option.previous_value()
                        else:
                            option.previous_value()
                        return True
                    elif right_arrow_rect.contains(pos):
                        # Special handling for theme option
                        if option.id == "theme":
                            # Find current index
                            current_index = -1
                            for i, (_, value) in enumerate(option.options):
                                if value == option.current_value:
                                    current_index = i
                                    break
                            
                            # Move to next index
                            if current_index >= 0:
                                next_index = (current_index + 1) % len(option.options)
                                _, next_value = option.options[next_index]
                                
                                # Update value
                                option.current_value = next_value
                                
                                # Call callback directly
                                if option.id == "theme" and hasattr(self, "_on_theme_changed"):
                                    logger.info(f"[HOLO_SETTINGS_PANEL] Directly calling theme callback with {next_value}")
                                    self._on_theme_changed(next_value)
                                else:
                                    option.next_value()
                        else:
                            option.next_value()
                        return True
                elif option.value_type == 'range':
                    # Check if click is on slider
                    slider_rect = QRectF(
                        options_rect.x() + options_rect.width() / 2,
                        options_rect.y() + option_index * option_height + (option_height - 10) / 2,
                        options_rect.width() / 2 - 10,
                        10
                    )
                    
                    if slider_rect.contains(pos):
                        # Calculate position on slider (0.0 to 1.0)
                        position = (pos.x() - slider_rect.x()) / slider_rect.width()
                        position = max(0.0, min(1.0, position))
                        
                        # Set value based on position
                        option.set_value_from_position(position)
                        return True
        
        return False
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events for hover effects"""
        if not self.visible:
            return
            
        # Convert event position to QPointF
        pos = QPointF(event.position())
        
        # Calculate panel rect
        panel_width = self.width
        panel_height = self.height
        
        # Center panel if position not specified
        if self.position == (0, 0):
            x = (800 - panel_width) / 2  # Assuming 800x600 display
            y = (600 - panel_height) / 2
        else:
            x, y = self.position
        
        panel_rect = QRectF(x, y, panel_width, panel_height)
        
        # Check if mouse is within panel
        if not panel_rect.contains(pos):
            self._hover_category = -1
            self._hover_option = -1
            return
        
        # Check if mouse is over categories
        categories_rect = QRectF(
            panel_rect.x() + 10,
            panel_rect.y() + 50,
            panel_rect.width() - 20,
            30
        )
        
        if categories_rect.contains(pos) and self.categories:
            # Calculate which category is hovered
            tab_width = categories_rect.width() / len(self.categories)
            category_index = int((pos.x() - categories_rect.x()) / tab_width)
            
            if 0 <= category_index < len(self.categories):
                self._hover_category = category_index
                self._hover_option = -1
                return
        else:
            self._hover_category = -1
        
        # Check if mouse is over options
        options_rect = QRectF(
            panel_rect.x() + 10,
            panel_rect.y() + 90,
            panel_rect.width() - 20,
            panel_rect.height() - 100
        )
        
        if options_rect.contains(pos):
            # Get options for current category
            category_options = self._get_category_options()
            
            # Calculate which option is hovered
            option_height = 40
            option_index = int((pos.y() - options_rect.y()) / option_height)
            
            if 0 <= option_index < len(category_options):
                self._hover_option = option_index
                return
        else:
            self._hover_option = -1

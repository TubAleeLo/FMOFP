"""
Settings panel for futuristic displays
"""
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QFont
from typing import Dict, List, Optional, Tuple, Any, Callable
import math
import traceback
from .theme_manager import get_theme_manager
from .effects import VisualEffects
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class SettingsOption:
    """Represents a single setting option"""
    
    def __init__(self, 
                id: str, 
                label: str, 
                value_type: str,
                current_value: Any,
                options: Optional[List[Tuple[str, Any]]] = None,
                min_value: Optional[float] = None,
                max_value: Optional[float] = None,
                on_change: Optional[Callable[[Any], None]] = None):
        """Initialize setting option
        
        Args:
            id: Unique identifier for the setting
            label: Display label for the setting
            value_type: Type of value ('toggle', 'select', 'range')
            current_value: Current value of the setting
            options: List of (label, value) tuples for 'select' type
            min_value: Minimum value for 'range' type
            max_value: Maximum value for 'range' type
            on_change: Callback function when value changes
        """
        self.id = id
        self.label = label
        self.value_type = value_type
        self.current_value = current_value
        self.options = options or []
        self.min_value = min_value
        self.max_value = max_value
        self.on_change = on_change
        
        # UI state
        self.is_focused = False
        self.is_active = False
        self.hover_value = None  # For range sliders
        
    def get_current_value_label(self) -> str:
        """Get label for current value"""
        if self.value_type == 'toggle':
            return "ON" if self.current_value else "OFF"
        elif self.value_type == 'select' and self.options:
            for label, value in self.options:
                if value == self.current_value:
                    return label
            return str(self.current_value)
        elif self.value_type == 'range':
            if isinstance(self.current_value, (int, float)):
                return str(self.current_value)
            return str(self.current_value)
        return str(self.current_value)
    
    def next_value(self):
        """Cycle to next value"""
        if self.value_type == 'toggle':
            self.set_value(not self.current_value)
        elif self.value_type == 'select' and self.options:
            # Find current index
            current_index = -1
            for i, (_, value) in enumerate(self.options):
                if value == self.current_value:
                    current_index = i
                    break
            
            # Move to next option
            next_index = (current_index + 1) % len(self.options)
            self.set_value(self.options[next_index][1])
        elif self.value_type == 'range' and self.min_value is not None and self.max_value is not None:
            # Increment by 10% of range
            value_range = self.max_value - self.min_value
            increment = value_range * 0.1
            new_value = min(self.max_value, self.current_value + increment)
            self.set_value(new_value)
    
    def previous_value(self):
        """Cycle to previous value"""
        if self.value_type == 'toggle':
            self.set_value(not self.current_value)
        elif self.value_type == 'select' and self.options:
            # Find current index
            current_index = -1
            for i, (_, value) in enumerate(self.options):
                if value == self.current_value:
                    current_index = i
                    break
            
            # Move to previous option
            prev_index = (current_index - 1) % len(self.options)
            self.set_value(self.options[prev_index][1])
        elif self.value_type == 'range' and self.min_value is not None and self.max_value is not None:
            # Decrement by 10% of range
            value_range = self.max_value - self.min_value
            decrement = value_range * 0.1
            new_value = max(self.min_value, self.current_value - decrement)
            self.set_value(new_value)
    
    def set_value(self, value):
        """Set value and trigger callback"""
        from Utils.logger.sys_logger import get_logger
        logger = get_logger()
        
        logger.info(f"[SETTINGS_OPTION] Setting value for {self.id} from {self.current_value} to {value}")
        
        if value != self.current_value:
            old_value = self.current_value
            self.current_value = value
            logger.info(f"[SETTINGS_OPTION] Value changed for {self.id}, calling callback: {self.on_change is not None}")
            
            if self.on_change:
                try:
                    # Log the callback function to help debug
                    logger.info(f"[SETTINGS_OPTION] Callback function for {self.id}: {self.on_change}")
                    
                    # Call the callback with the new value
                    self.on_change(value)
                    logger.info(f"[SETTINGS_OPTION] Callback for {self.id} completed successfully")
                except Exception as e:
                    logger.error(f"[SETTINGS_OPTION] Error in callback for {self.id}: {str(e)}")
                    logger.error(f"[SETTINGS_OPTION] Exception traceback: {traceback.format_exc()}")
                    # Revert to old value on error
                    self.current_value = old_value
                    logger.info(f"[SETTINGS_OPTION] Reverted {self.id} to {old_value} due to callback error")
        else:
            logger.info(f"[SETTINGS_OPTION] Value for {self.id} unchanged (already {value})")
    
    def set_value_from_position(self, position: float):
        """Set value based on position (0.0 to 1.0) for range type"""
        if self.value_type == 'range' and self.min_value is not None and self.max_value is not None:
            # Calculate value from position
            value_range = self.max_value - self.min_value
            new_value = self.min_value + position * value_range
            self.set_value(new_value)

class SettingsPanel:
    """Interactive settings panel for display customization"""
    
    def __init__(self):
        """Initialize settings panel"""
        self.visible = False
        self.width = 300
        self.height = 400
        self.position = (0, 0)  # (x, y) position
        self.title = "DISPLAY SETTINGS"
        
        # Visual effects
        self._visual_effects = VisualEffects()
        self._theme_manager = get_theme_manager()
        
        # Settings categories
        self.categories = []
        self.current_category = 0
        
        # Settings options
        self.options = []
        self.focused_option = -1
        
        # Animation state
        self.animation_progress = 0.0  # 0.0 to 1.0
        self.target_animation = 1.0
        self.animation_speed = 5.0  # units per second
        
        # Initialize with default settings
        self._initialize_settings()
    
    def _initialize_settings(self):
        """Initialize settings categories and options"""
        # Create categories
        self.categories = ["VISUAL", "LAYOUT", "DATA", "SYSTEM"]
        
        # Create options
        self.options = []
        
        # Visual settings
        self.options.append(SettingsOption(
            "theme",
            "Theme",
            "select",
            "modern",  # Changed default from "futuristic" to "modern"
            [
                ("Classic", "classic"),
                ("Modern", "modern"),
                ("Night", "night")
                # Removed "Futuristic" option as requested
            ]
        ))
        
        self.options.append(SettingsOption(
            "grid_type",
            "Grid Type",
            "select",
            "hexagonal",
            [
                ("Hexagonal", "hexagonal"),
                ("Circular", "circular"),
                ("Radial", "radial")
            ]
        ))
        
        self.options.append(SettingsOption(
            "use_glow",
            "Glow Effects",
            "toggle",
            True
        ))
        
        self.options.append(SettingsOption(
            "use_animations",
            "Animations",
            "toggle",
            True
        ))
        
        # Layout settings
        self.options.append(SettingsOption(
            "show_terrain",
            "Terrain Profile",
            "toggle",
            True
        ))
        
        self.options.append(SettingsOption(
            "show_side_panel",
            "Side Panel",
            "toggle",
            False
        ))
        
        self.options.append(SettingsOption(
            "information_density",
            "Information Density",
            "select",
            "tactical",
            [
                ("Minimal", "minimal"),
                ("Standard", "standard"),
                ("Tactical", "tactical"),
                ("Maximum", "maximum")
            ]
        ))
        
        # Data settings
        self.options.append(SettingsOption(
            "data_fusion_level",
            "Data Fusion Level",
            "select",
            1,
            [
                ("Level 1 (Basic)", 1),
                ("Level 2 (Enhanced)", 2),
                ("Level 3 (Advanced)", 3)
            ]
        ))
        
        self.options.append(SettingsOption(
            "range_scale",
            "Range Scale (NM)",
            "select",
            40,
            [
                ("10 NM", 10),
                ("20 NM", 20),
                ("40 NM", 40),
                ("80 NM", 80),
                ("160 NM", 160)
            ]
        ))
        
        # System settings
        self.options.append(SettingsOption(
            "refresh_rate",
            "Refresh Rate",
            "select",
            "high",
            [
                ("Standard", "standard"),
                ("High", "high"),
                ("Ultra", "ultra")
            ]
        ))
        
        self.options.append(SettingsOption(
            "brightness",
            "Brightness",
            "range",
            0.8,
            min_value=0.1,
            max_value=1.0
        ))
    
    def show(self, position: Tuple[int, int] = None):
        """Show settings panel at specified position"""
        self.visible = True
        if position:
            self.position = position
        self.animation_progress = 0.0
        self.target_animation = 1.0
    
    def hide(self):
        """Hide settings panel"""
        self.target_animation = 0.0
    
    def update(self, delta_time: float):
        """Update panel animations"""
        # Update animation progress
        if self.animation_progress < self.target_animation:
            self.animation_progress = min(self.target_animation, 
                                        self.animation_progress + self.animation_speed * delta_time)
        elif self.animation_progress > self.target_animation:
            self.animation_progress = max(self.target_animation, 
                                        self.animation_progress - self.animation_speed * delta_time)
            
        # Hide panel when animation completes
        if self.animation_progress <= 0.0 and self.target_animation <= 0.0:
            self.visible = False
    
    def draw(self, painter: QPainter, rect: QRectF):
        """Draw settings panel"""
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
        
        # Draw panel background
        background_color = QColor(self._theme_manager.get_color("overlay_background"))
        painter.fillRect(panel_rect, background_color)
        
        # Draw panel frame
        self._visual_effects.draw_angular_frame(
            painter,
            panel_rect,
            color=self._theme_manager.get_color("hud"),
            corner_style="angular",
            glow=True
        )
        
        # Draw title
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
            glow_color=self._theme_manager.get_color("hud")
        )
        
        # Draw categories
        self._draw_categories(painter, panel_rect)
        
        # Draw options for current category
        self._draw_options(painter, panel_rect)
    
    def _draw_categories(self, painter: QPainter, panel_rect: QRectF):
        """Draw settings categories"""
        # Create categories rect
        categories_rect = QRectF(
            panel_rect.x() + 10,
            panel_rect.y() + 50,
            panel_rect.width() - 20,
            30
        )
        
        # Draw categories background
        background_color = QColor(self._theme_manager.get_color("menu_background"))
        painter.fillRect(categories_rect, background_color)
        
        # Draw categories frame
        self._visual_effects.draw_enhanced_rect(
            painter,
            categories_rect,
            color=self._theme_manager.get_color("hud"),
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
            
            # Draw tab background if selected
            if i == self.current_category:
                highlight_color = QColor(self._theme_manager.get_color("menu_highlight"))
                painter.fillRect(tab_rect, highlight_color)
                
                # Draw highlight border
                self._visual_effects.draw_enhanced_rect(
                    painter,
                    tab_rect,
                    color=self._theme_manager.get_color("data_primary"),
                    fill=False,
                    glow=True
                )
            
            # Draw tab text
            self._visual_effects.draw_enhanced_text(
                painter,
                tab_rect,
                Qt.AlignmentFlag.AlignCenter,
                category,
                glow=i == self.current_category,
                glow_color=self._theme_manager.get_color("data_primary") if i == self.current_category else self._theme_manager.get_color("hud")
            )
    
    def _draw_options(self, painter: QPainter, panel_rect: QRectF):
        """Draw settings options for current category"""
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
            
            # Draw option background
            if option.is_focused:
                highlight_color = QColor(self._theme_manager.get_color("menu_highlight"))
                painter.fillRect(option_rect, highlight_color)
                
                # Draw highlight border
                self._visual_effects.draw_enhanced_rect(
                    painter,
                    option_rect,
                    color=self._theme_manager.get_color("data_primary"),
                    fill=False,
                    glow=True
                )
            
            # Draw option label
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
                glow=False,
                glow_color=self._theme_manager.get_color("hud")
            )
            
            # Draw option value
            value_rect = QRectF(
                option_rect.x() + option_rect.width() / 2,
                option_rect.y(),
                option_rect.width() / 2 - 10,
                option_rect.height()
            )
            
            # Draw different controls based on value type
            if option.value_type == 'toggle':
                self._draw_toggle_control(painter, value_rect, option)
            elif option.value_type == 'select':
                self._draw_select_control(painter, value_rect, option)
            elif option.value_type == 'range':
                self._draw_range_control(painter, value_rect, option)
    
    def _draw_toggle_control(self, painter: QPainter, rect: QRectF, option: SettingsOption):
        """Draw toggle control"""
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
        
        # Draw border
        self._visual_effects.draw_enhanced_rect(
            painter,
            toggle_rect,
            color=self._theme_manager.get_color("hud"),
            fill=False
        )
        
        # Draw toggle state
        if option.current_value:
            # ON state
            toggle_color = self._theme_manager.get_color("data_primary")
            toggle_label = "ON"
            toggle_position = 0.7  # 70% to the right
        else:
            # OFF state
            toggle_color = self._theme_manager.get_color("menu_text")
            toggle_label = "OFF"
            toggle_position = 0.3  # 30% to the right
        
        # Draw toggle indicator
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
        
        # Draw toggle label
        self._visual_effects.draw_enhanced_text(
            painter,
            toggle_rect,
            Qt.AlignmentFlag.AlignCenter,
            toggle_label,
            glow=option.current_value,
            glow_color=toggle_color
        )
    
    def _draw_select_control(self, painter: QPainter, rect: QRectF, option: SettingsOption):
        """Draw select control"""
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
            glow_color=self._theme_manager.get_color("data_primary")
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
            glow_color=self._theme_manager.get_color("data_primary")
        )
        
        # Value text
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
            glow_color=self._theme_manager.get_color("data_primary")
        )
    
    def _draw_range_control(self, painter: QPainter, rect: QRectF, option: SettingsOption):
        """Draw range slider control"""
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
        
        # Draw border
        self._visual_effects.draw_enhanced_rect(
            painter,
            slider_rect,
            color=self._theme_manager.get_color("hud"),
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
            
            fill_color = self._theme_manager.get_color("data_primary")
            painter.fillRect(fill_rect, fill_color)
            
            # Draw slider handle
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
                color=self._theme_manager.get_color("data_primary"),
                fill=True,
                glow=option.is_focused
            )
        
        # Draw value text
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
            glow_color=self._theme_manager.get_color("data_primary")
        )
    
    def _get_category_options(self) -> List[SettingsOption]:
        """Get options for current category"""
        if not self.categories or self.current_category >= len(self.categories):
            return []
            
        category = self.categories[self.current_category]
        
        # Filter options by category
        if category == "VISUAL":
            return [option for option in self.options if option.id in ["theme", "grid_type", "use_glow", "use_animations"]]
        elif category == "LAYOUT":
            return [option for option in self.options if option.id in ["show_terrain", "show_side_panel", "information_density"]]
        elif category == "DATA":
            return [option for option in self.options if option.id in ["data_fusion_level", "range_scale"]]
        elif category == "SYSTEM":
            return [option for option in self.options if option.id in ["refresh_rate", "brightness"]]
            
        return []
    
    def handle_click(self, pos: QPointF) -> bool:
        """Handle mouse click on settings panel
        
        Returns:
            True if click was handled, False otherwise
        """
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
                        option.previous_value()
                        return True
                    elif right_arrow_rect.contains(pos):
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
    
    def get_option(self, option_id: str) -> Optional[SettingsOption]:
        """Get option by ID"""
        for option in self.options:
            if option.id == option_id:
                return option
        return None
    
    def set_option_value(self, option_id: str, value: Any):
        """Set option value by ID"""
        option = self.get_option(option_id)
        if option:
            option.set_value(value)
    
    def set_option_callback(self, option_id: str, callback: Callable[[Any], None]):
        """Set option callback by ID"""
        option = self.get_option(option_id)
        if option:
            option.on_change = callback
            
    def add_setting(self, id: str, label: str, value_type: str, current_value: Any,
                  options: Optional[List[Tuple[str, Any]]] = None,
                  min_value: Optional[float] = None, max_value: Optional[float] = None,
                  on_change: Optional[Callable[[Any], None]] = None):
        """Add a new setting to the panel
        
        Args:
            id: Unique identifier for the setting
            label: Display label for the setting
            value_type: Type of value ('toggle', 'select', 'range')
            current_value: Current value of the setting
            options: List of (label, value) tuples for 'select' type
            min_value: Minimum value for 'range' type
            max_value: Maximum value for 'range' type
            on_change: Callback function when value changes
        """
        # Create setting option
        option = SettingsOption(
            id, label, value_type, current_value, 
            options, min_value, max_value, on_change
        )
        
        # Add to options list
        self.options.append(option)
        
        # Log that we added the setting
        logger.info(f"Added setting: {id} ({value_type}) with callback: {on_change is not None}")

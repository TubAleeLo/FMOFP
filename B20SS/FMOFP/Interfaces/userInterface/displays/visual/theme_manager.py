"""
Theme manager for display visual enhancements
"""
from enum import Enum, auto
from typing import Dict, Any, Optional, List
import json
import traceback
import os
from PyQt6.QtGui import QColor, QFont, QGradient, QLinearGradient
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class DisplayTheme(Enum):
    """Available display themes"""
    CLASSIC = "classic"    # Traditional green monochrome
    MODERN = "modern"      # Blue-teal enhanced theme
    NIGHT = "night"        # Night operations optimized

class VisualThemeManager:
    """Manages visual themes for displays without affecting data flows"""
    
    def __init__(self):
        self._current_theme = DisplayTheme.CLASSIC
        self._themes = {}
        self._load_themes()
        
    def _load_themes(self):
        """Load theme definitions from configuration files"""
        try:
            # Default themes hardcoded as fallback
            self._themes = {
                DisplayTheme.CLASSIC: self._get_classic_theme(),
                DisplayTheme.MODERN: self._get_modern_theme(),
                DisplayTheme.NIGHT: self._get_night_theme()
            }
            
            # Try to load from configuration if available
            config_path = os.path.join(os.path.dirname(__file__), 'theme_config.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    theme_data = json.load(f)
                    # Process and override defaults with loaded data
                    for theme_name, theme_values in theme_data.items():
                        try:
                            theme_enum = DisplayTheme(theme_name)
                            if theme_enum in self._themes:
                                # Update existing theme with loaded values
                                self._update_theme_from_config(self._themes[theme_enum], theme_values)
                        except ValueError:
                            logger.warning(f"Unknown theme name in config: {theme_name}")
                    
            logger.info(f"Loaded {len(self._themes)} visual themes")
        except Exception as e:
            logger.error(f"Error loading themes: {str(e)}")
            # Ensure defaults are available
    
    def _update_theme_from_config(self, theme: Dict[str, Any], config_values: Dict[str, Any]):
        """Update theme dictionary with values from config"""
        # Update colors
        if 'colors' in config_values and isinstance(config_values['colors'], dict):
            for color_name, color_value in config_values['colors'].items():
                if isinstance(color_value, list) and len(color_value) >= 3:
                    # RGB or RGBA format
                    r, g, b = color_value[0:3]
                    a = color_value[3] if len(color_value) > 3 else 255
                    theme['colors'][color_name] = QColor(r, g, b, a)
                elif isinstance(color_value, str):
                    # Hex format
                    theme['colors'][color_name] = QColor(color_value)
        
        # Update fonts
        if 'fonts' in config_values and isinstance(config_values['fonts'], dict):
            for font_name, font_value in config_values['fonts'].items():
                if isinstance(font_value, dict):
                    family = font_value.get('family', 'Arial')
                    size = font_value.get('size', 10)
                    weight = font_value.get('weight', 50)
                    italic = font_value.get('italic', False)
                    
                    font = QFont(family, size)
                    font.setWeight(weight)
                    font.setItalic(italic)
                    
                    theme['fonts'][font_name] = font
        
        # Update styles
        if 'styles' in config_values and isinstance(config_values['styles'], dict):
            for style_name, style_value in config_values['styles'].items():
                theme['styles'][style_name] = style_value
            
    def _get_classic_theme(self) -> Dict[str, Any]:
        """Current classic theme - matches existing visuals"""
        return {
            "colors": {
                "hud": QColor(0, 255, 0, 200),  # Classic green
                "warning": QColor(255, 255, 0, 200),  # Yellow
                "caution": QColor(255, 165, 0, 200),  # Orange
                "critical": QColor(255, 0, 0, 200),  # Red
                "background": QColor(0, 0, 0),  # Black
                "sky": QColor(0, 128, 255),  # Blue
                "ground": QColor(139, 69, 19),  # Brown
                "menu_background": QColor(30, 30, 30),  # Dark gray
                "menu_highlight": QColor(60, 60, 60),  # Medium gray
                "menu_text": QColor(0, 255, 0, 200),  # Green
                "menu_text_highlight": QColor(255, 255, 0, 200),  # Yellow
            },
            "fonts": {
                "primary": QFont("Arial", 10),
                "heading": QFont("Arial", 12, QFont.Weight.Bold),
                "data": QFont("Courier New", 10),
                "menu": QFont("Arial", 10),
            },
            "styles": {
                "line_width": 1.0,
                "use_gradients": False,
                "use_shadows": False,
                "use_animations": False,
                "corner_radius": 0.0,
                "menu_item_height": 40.0,
                "menu_width": 150.0,
            },
            "display_types": {
                "pfd": "standard",
                "mfd": "standard",
                "hud": "standard"
            }
        }
    
    def _get_modern_theme(self) -> Dict[str, Any]:
        """New futuristic theme with enhanced visuals"""
        # Create modern blue-teal gradient for HUD elements
        hud_gradient = QLinearGradient(0, 0, 0, 1)
        hud_gradient.setColorAt(0, QColor(0, 210, 255, 220))  # Bright teal
        hud_gradient.setColorAt(1, QColor(0, 150, 200, 220))  # Deeper blue
        
        return {
            "colors": {
                "hud": QColor(0, 210, 255, 220),  # Bright teal
                "hud_gradient": hud_gradient,
                "warning": QColor(255, 180, 0, 220),  # Amber
                "caution": QColor(255, 100, 0, 220),  # Orange-red
                "critical": QColor(255, 30, 30, 220),  # Bright red
                "background": QColor(0, 0, 0),  # Black
                "sky": QColor(20, 80, 180),  # Deeper blue
                "ground": QColor(120, 70, 20),  # Richer brown
                "friendly": QColor(30, 150, 255, 220),  # Electric blue
                "enemy": QColor(220, 30, 30, 220),  # Crimson
                "neutral": QColor(200, 200, 220, 220),  # Cool white
                "menu_background": QColor(25, 25, 25),  # Darker gray
                "menu_highlight": QColor(40, 40, 60),  # Blue-tinted gray
                "menu_text": QColor(0, 210, 255, 220),  # Bright teal
                "menu_text_highlight": QColor(255, 180, 0, 220),  # Amber
            },
            "fonts": {
                "primary": QFont("Roboto", 10),
                "heading": QFont("Roboto", 12, QFont.Weight.Bold),
                "data": QFont("Roboto Mono", 10),
                "menu": QFont("Roboto", 10),
            },
            "styles": {
                "line_width": 1.5,
                "use_gradients": True,
                "use_shadows": True,
                "shadow_blur": 3.0,
                "shadow_offset_x": 1.0,
                "shadow_offset_y": 1.0,
                "use_animations": True,
                "animation_duration": 200,  # ms
                "corner_radius": 2.0,
                "menu_item_height": 40.0,
                "menu_width": 150.0,
            },
            "display_types": {
                "pfd": "holographic",
                "mfd": "holographic",
                "hud": "holographic"
            }
        }
    
    def _get_night_theme(self) -> Dict[str, Any]:
        """Night operations optimized theme"""
        return {
            "colors": {
                "hud": QColor(255, 0, 0, 180),  # Dark red for night vision
                "warning": QColor(200, 100, 0, 180),  # Dark amber
                "caution": QColor(180, 50, 0, 180),  # Dark orange
                "critical": QColor(150, 0, 0, 180),  # Darker red
                "background": QColor(0, 0, 0),  # Black
                "sky": QColor(10, 20, 40),  # Very dark blue
                "ground": QColor(30, 20, 10),  # Very dark brown
                "menu_background": QColor(10, 10, 10),  # Very dark gray
                "menu_highlight": QColor(30, 20, 20),  # Dark red-tinted gray
                "menu_text": QColor(255, 0, 0, 180),  # Dark red
                "menu_text_highlight": QColor(200, 100, 0, 180),  # Dark amber
            },
            "fonts": {
                "primary": QFont("Roboto", 10),
                "heading": QFont("Roboto", 12, QFont.Weight.Bold),
                "data": QFont("Roboto Mono", 10),
                "menu": QFont("Roboto", 10),
            },
            "styles": {
                "line_width": 1.0,  # Thinner lines for night mode
                "use_gradients": True,
                "use_shadows": False,  # No shadows in night mode
                "use_animations": True,
                "animation_duration": 300,  # Slower animations for night mode
                "corner_radius": 0.0,  # No rounded corners for night mode
                "menu_item_height": 40.0,
                "menu_width": 150.0,
            },
            "display_types": {
                "pfd": "standard",
                "mfd": "standard",
                "hud": "standard"
            }
        }
        
    # Removed _get_futuristic_theme method as it's no longer needed
        
    def get_current_theme(self) -> Dict[str, Any]:
        """Get current theme settings"""
        return self._themes.get(self._current_theme, self._get_classic_theme())
    
    def set_theme(self, theme: DisplayTheme) -> bool:
        """Set active theme"""
        if theme in self._themes:
            self._current_theme = theme
            logger.info(f"Set display theme to: {theme.value}")
            return True
        return False
    
    def get_color(self, color_name: str) -> QColor:
        """Get color from current theme with improved fallback handling"""
        theme = self.get_current_theme()
        
        # Try to get color from current theme
        if color_name in theme.get("colors", {}):
            return theme["colors"][color_name]
        
        # Fallback to standard colors based on color name
        fallback_colors = {
            # Menu elements
            "menu_background": QColor(20, 20, 20),
            "menu_highlight": QColor(40, 40, 40),
            "menu_text": QColor(200, 200, 200),
            "menu_text_highlight": QColor(255, 255, 0, 200),
            "menu_border": QColor(60, 60, 60),
            
            # Status indicators
            "caution": QColor(255, 165, 0, 200),
            "warning": QColor(255, 255, 0, 200),
            "critical": QColor(255, 0, 0, 200),
            "system_normal": QColor(0, 255, 0, 200),
            
            # HUD elements
            "hud": QColor(0, 255, 0, 200),
            "horizon_line": QColor(0, 255, 0, 200),
            "altitude_tape": QColor(0, 255, 0, 200),
            "airspeed_tape": QColor(0, 255, 0, 200),
            "heading_indicator": QColor(0, 255, 0, 200),
            
            # Target classifications
            "friendly": QColor(0, 255, 0),
            "enemy": QColor(255, 0, 0),
            "neutral": QColor(255, 255, 255),
            "unknown": QColor(255, 255, 0),
            
            # Data visualization
            "data_primary": QColor(0, 255, 0, 200),
            "data_secondary": QColor(0, 200, 0, 200),
            "data_tertiary": QColor(0, 150, 0, 200),
            "overlay_background": QColor(0, 0, 0, 150),
            
            # Tactical elements
            "target_tracking": QColor(0, 200, 255),
            "tactical_overlay": QColor(255, 100, 0),
            "energy_state": QColor(255, 255, 0),
            "waypoint": QColor(0, 200, 255)
        }
        
        if color_name in fallback_colors:
            logger.warning(f"Color '{color_name}' not found in theme {self._current_theme.value}, using standard fallback")
            return fallback_colors[color_name]
            
        # Default to classic green as final fallback
        logger.warning(f"Color '{color_name}' not found in theme {self._current_theme.value}")
        return QColor(0, 255, 0, 200)  # Default to classic green
    
    def get_font(self, font_name: str) -> QFont:
        """Get font from current theme"""
        theme = self.get_current_theme()
        return theme.get("fonts", {}).get(font_name, QFont("Arial", 10))  # Default font
    
    def get_style_param(self, param_name: str, default=None) -> Any:
        """Get style parameter from current theme"""
        theme = self.get_current_theme()
        return theme.get("styles", {}).get(param_name, default)
    
    def get_display_type(self, category: str, default="standard") -> str:
        """Get display type for a specific category (pfd, mfd, radar, hud)"""
        try:
            # Get display type from theme settings or from explicitly set display types
            theme = self.get_current_theme()
            display_type = theme.get("display_types", {}).get(category, default)
            
            # Only log when display type changes to reduce log spam
            if not hasattr(self, '_last_display_types'):
                self._last_display_types = {}
                
            if category not in self._last_display_types or self._last_display_types[category] != display_type:
                logger.info(f"Display type changed for {category}: '{display_type}'")
                self._last_display_types[category] = display_type
                
            return display_type
        except Exception as e:
            logger.error(f"Error getting display type for {category}: {str(e)}")
            logger.error(traceback.format_exc())
            return default
    
    def set_display_type(self, category: str, display_type: str) -> bool:
        """Set display type for a specific category"""
        if self._current_theme in self._themes:
            theme = self._themes[self._current_theme]
            if "display_types" not in theme:
                theme["display_types"] = {}
            theme["display_types"][category] = display_type
            logger.info(f"Set {category} display type to: {display_type}")
            return True
        return False
    
    def get_available_display_types(self) -> List[str]:
        """Get list of available display types"""
        return ["standard", "holographic"] 

# Singleton instance
_theme_manager = None

def get_theme_manager() -> VisualThemeManager:
    """Get the singleton theme manager instance"""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = VisualThemeManager()
    return _theme_manager

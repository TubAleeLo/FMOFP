"""
Enhanced theme manager for advanced displays with holographic capabilities
"""
from PyQt6.QtGui import QColor
from enum import Enum, auto
from typing import Dict, Any, Optional
import math
import time
from Utils.logger.sys_logger import get_logger

logger = get_logger()

# Log throttling variables
_last_log_times = {}
_log_throttle_interval = 5.0  # Seconds between similar log messages

def throttled_log(level, message, key=None):
    """
    Log a message with throttling to prevent excessive similar log messages.
    
    Args:
        level: The logging level (e.g., logger.debug, logger.info, logger.warning)
        message: The message to log
        key: Optional key to identify this type of message (defaults to message itself)
    
    Returns:
        True if the message was logged, False if it was throttled
    """
    global _last_log_times
    
    # Use message as key if none provided
    if key is None:
        key = message
        
    current_time = time.time()
    last_time = _last_log_times.get(key, 0)
    
    # Check if enough time has passed since the last similar message
    if current_time - last_time >= _log_throttle_interval:
        # Update the last log time for this message
        _last_log_times[key] = current_time
        
        # Log the message
        level(message)
        return True
    
    return False

class EnhancedDisplayTheme(Enum):
    """Enhanced display themes for aircraft displays"""
    CLASSIC = auto()       # Traditional  HUD style
    MODERN = auto()        # Modern clean style
    TACTICAL = auto()      # Combat-focused style
    HOLOGRAPHIC = auto()   # Advanced holographic style
    STEALTH = auto()       # Low-visibility night operations style
    CUSTOM = auto()        # User-defined style

class EnhancedThemeManager:
    """Enhanced theme manager for advanced displays with holographic capabilities"""
    
    def __init__(self):
        """Initialize enhanced theme manager"""
        # Default to holographic theme
        self._current_theme = EnhancedDisplayTheme.HOLOGRAPHIC
        
        # Initialize color schemes for different themes
        self._color_schemes = {
            EnhancedDisplayTheme.CLASSIC: {
                "background": QColor(0, 0, 0),
                "grid": QColor(30, 30, 30),
                "hud": QColor(0, 255, 0),
                "data_primary": QColor(0, 255, 0),
                "data_secondary": QColor(0, 200, 0),
                "data_tertiary": QColor(0, 150, 0),
                "warning": QColor(255, 255, 0),
                "critical": QColor(255, 0, 0),
                "caution": QColor(255, 165, 0, 200),
                "sky": QColor(0, 0, 100),
                "ground": QColor(100, 50, 0),
                "horizon_line": QColor(0, 255, 0),
                "altitude_tape": QColor(0, 255, 0),
                "airspeed_tape": QColor(0, 255, 0),
                "heading_indicator": QColor(0, 255, 0),
                "system_normal": QColor(0, 255, 0),
                "overlay_background": QColor(0, 0, 0, 150),
                "target_tracking": QColor(0, 200, 255),
                "tactical_overlay": QColor(255, 100, 0),
                "energy_state": QColor(255, 255, 0),
                "menu_background": QColor(30, 30, 30),
                "menu_highlight": QColor(60, 60, 60),
                "menu_text": QColor(0, 255, 0),
                "menu_text_highlight": QColor(255, 255, 0, 200),
                "menu_border": QColor(60, 60, 60),
                "friendly": QColor(0, 255, 0),
                "enemy": QColor(255, 0, 0),
                "neutral": QColor(255, 255, 255),
                "unknown": QColor(255, 255, 0)
            },
            
            EnhancedDisplayTheme.MODERN: {
                "background": QColor(10, 15, 20),
                "grid": QColor(30, 40, 50),
                "hud": QColor(0, 200, 255),
                "data_primary": QColor(0, 200, 255),
                "data_secondary": QColor(0, 150, 200),
                "data_tertiary": QColor(0, 100, 150),
                "warning": QColor(255, 200, 0),
                "critical": QColor(255, 50, 50),
                "caution": QColor(255, 100, 0, 220),
                "sky": QColor(20, 40, 80),
                "ground": QColor(60, 40, 20),
                "horizon_line": QColor(0, 200, 255),
                "altitude_tape": QColor(0, 200, 255),
                "airspeed_tape": QColor(0, 200, 255),
                "heading_indicator": QColor(0, 200, 255),
                "system_normal": QColor(100, 255, 100),
                "overlay_background": QColor(10, 15, 20, 180),
                "target_tracking": QColor(255, 150, 0),
                "tactical_overlay": QColor(255, 100, 0),
                "energy_state": QColor(255, 200, 0),
                "menu_background": QColor(25, 25, 25),
                "menu_highlight": QColor(40, 40, 60),
                "menu_text": QColor(0, 200, 255),
                "menu_text_highlight": QColor(255, 200, 0, 220),
                "menu_border": QColor(50, 50, 70),
                "friendly": QColor(30, 150, 255, 220),
                "enemy": QColor(220, 30, 30, 220),
                "neutral": QColor(200, 200, 220, 220),
                "unknown": QColor(255, 200, 0, 220)
            },
            
            EnhancedDisplayTheme.TACTICAL: {
                "background": QColor(0, 0, 0),
                "grid": QColor(40, 40, 40),
                "hud": QColor(255, 100, 0),
                "data_primary": QColor(255, 150, 0),
                "data_secondary": QColor(200, 100, 0),
                "data_tertiary": QColor(150, 75, 0),
                "warning": QColor(255, 255, 0),
                "critical": QColor(255, 0, 0),
                "caution": QColor(255, 120, 0, 220),
                "sky": QColor(0, 0, 50),
                "ground": QColor(50, 30, 0),
                "horizon_line": QColor(255, 150, 0),
                "altitude_tape": QColor(255, 150, 0),
                "airspeed_tape": QColor(255, 150, 0),
                "heading_indicator": QColor(255, 150, 0),
                "system_normal": QColor(0, 255, 0),
                "overlay_background": QColor(0, 0, 0, 180),
                "target_tracking": QColor(255, 0, 0),
                "tactical_overlay": QColor(255, 0, 0),
                "energy_state": QColor(255, 255, 0),
                "menu_background": QColor(20, 20, 20),
                "menu_highlight": QColor(50, 30, 20),
                "menu_text": QColor(255, 150, 0),
                "menu_text_highlight": QColor(255, 255, 0, 220),
                "menu_border": QColor(70, 40, 20),
                "friendly": QColor(0, 255, 0),
                "enemy": QColor(255, 0, 0),
                "neutral": QColor(255, 255, 0),
                "unknown": QColor(255, 200, 0)
            },
            
            EnhancedDisplayTheme.HOLOGRAPHIC: {
                "background": QColor(0, 10, 20),
                "grid": QColor(0, 50, 100, 100),
                "hud": QColor(0, 200, 255),
                "data_primary": QColor(0, 220, 255),
                "data_secondary": QColor(100, 200, 255),
                "data_tertiary": QColor(150, 200, 255),
                "warning": QColor(255, 200, 0),
                "critical": QColor(255, 50, 50),
                "caution": QColor(255, 150, 0, 220),
                "sky": QColor(0, 30, 60),
                "ground": QColor(20, 15, 10),
                "horizon_line": QColor(0, 200, 255),
                "altitude_tape": QColor(0, 200, 255),
                "airspeed_tape": QColor(0, 200, 255),
                "heading_indicator": QColor(0, 200, 255),
                "system_normal": QColor(100, 255, 100),
                "overlay_background": QColor(0, 10, 20, 150),
                "target_tracking": QColor(255, 150, 0),
                "tactical_overlay": QColor(255, 100, 0),
                "energy_state": QColor(255, 200, 0),
                "menu_background": QColor(0, 30, 50, 180),
                "menu_highlight": QColor(0, 150, 220, 100),
                "menu_text": QColor(0, 200, 255),
                "menu_text_highlight": QColor(255, 200, 0, 220),
                "menu_border": QColor(0, 100, 150, 180),
                "friendly": QColor(30, 150, 255, 220),
                "enemy": QColor(220, 30, 30, 220),
                "neutral": QColor(200, 200, 220, 220),
                "unknown": QColor(255, 200, 0, 220)
            },
            
            EnhancedDisplayTheme.STEALTH: {
                "background": QColor(0, 0, 0),
                "grid": QColor(20, 20, 20),
                "hud": QColor(255, 0, 0, 180),
                "data_primary": QColor(255, 0, 0, 180),
                "data_secondary": QColor(200, 0, 0, 180),
                "data_tertiary": QColor(150, 0, 0, 180),
                "warning": QColor(255, 100, 0, 180),
                "critical": QColor(255, 200, 0, 180),
                "caution": QColor(180, 50, 0, 180),
                "sky": QColor(10, 0, 0),
                "ground": QColor(20, 0, 0),
                "horizon_line": QColor(255, 0, 0, 180),
                "altitude_tape": QColor(255, 0, 0, 180),
                "airspeed_tape": QColor(255, 0, 0, 180),
                "heading_indicator": QColor(255, 0, 0, 180),
                "system_normal": QColor(150, 0, 0, 180),
                "overlay_background": QColor(0, 0, 0, 150),
                "target_tracking": QColor(255, 100, 0, 180),
                "tactical_overlay": QColor(255, 100, 0, 180),
                "energy_state": QColor(255, 100, 0, 180),
                "menu_background": QColor(10, 10, 10),
                "menu_highlight": QColor(30, 20, 20),
                "menu_text": QColor(255, 0, 0, 180),
                "menu_text_highlight": QColor(255, 100, 0, 180),
                "menu_border": QColor(40, 20, 20),
                "friendly": QColor(150, 0, 0, 180),
                "enemy": QColor(255, 0, 0, 180),
                "neutral": QColor(100, 0, 0, 180),
                "unknown": QColor(200, 100, 0, 180)
            },
            
            EnhancedDisplayTheme.CUSTOM: {
                # Will be populated by user settings
                "background": QColor(0, 0, 0),
                "grid": QColor(30, 30, 30),
                "hud": QColor(0, 255, 0),
                "data_primary": QColor(0, 255, 0),
                "data_secondary": QColor(0, 200, 0),
                "data_tertiary": QColor(0, 150, 0),
                "warning": QColor(255, 255, 0),
                "critical": QColor(255, 0, 0),
                "caution": QColor(255, 165, 0, 220),  # Added caution color
                "sky": QColor(0, 0, 100),
                "ground": QColor(100, 50, 0),
                "horizon_line": QColor(0, 255, 0),
                "altitude_tape": QColor(0, 255, 0),
                "airspeed_tape": QColor(0, 255, 0),
                "heading_indicator": QColor(0, 255, 0),
                "system_normal": QColor(0, 255, 0),
                "overlay_background": QColor(0, 0, 0, 150),
                "target_tracking": QColor(0, 200, 255),
                "tactical_overlay": QColor(255, 100, 0),
                "energy_state": QColor(255, 255, 0),
                "menu_background": QColor(20, 20, 20),  # Added menu_background
                "menu_highlight": QColor(40, 40, 40),   # Added menu_highlight
                "menu_text": QColor(0, 255, 0)          # Added menu_text
            }
        }
        
        # Initialize style parameters for different themes
        self._style_params = {
            EnhancedDisplayTheme.CLASSIC: {
                "use_gradients": False,
                "use_shadows": False,
                "use_glow": False,
                "use_angular_design": False,
                "use_holographic_elements": False,
                "use_parallax_effects": False,
                "use_pulse_effects": False,
                "corner_radius": 0.0,
                "line_width": 1.0,
                "glow_intensity": 0.0,
                "shadow_offset_x": 0.0,
                "shadow_offset_y": 0.0,
                "shadow_blur": 0.0,
                "grid_type": "standard",
                "animation_speed": 1.0,
                "pulse_rate": 1.0
            },
            
            EnhancedDisplayTheme.MODERN: {
                "use_gradients": True,
                "use_shadows": True,
                "use_glow": True,
                "use_angular_design": False,
                "use_holographic_elements": False,
                "use_parallax_effects": False,
                "use_pulse_effects": True,
                "corner_radius": 4.0,
                "line_width": 1.5,
                "glow_intensity": 0.3,
                "shadow_offset_x": 1.0,
                "shadow_offset_y": 1.0,
                "shadow_blur": 2.0,
                "grid_type": "standard",
                "animation_speed": 1.0,
                "pulse_rate": 0.5
            },
            
            EnhancedDisplayTheme.TACTICAL: {
                "use_gradients": True,
                "use_shadows": False,
                "use_glow": True,
                "use_angular_design": True,
                "use_holographic_elements": False,
                "use_parallax_effects": False,
                "use_pulse_effects": True,
                "corner_radius": 0.0,
                "line_width": 1.5,
                "glow_intensity": 0.4,
                "shadow_offset_x": 0.0,
                "shadow_offset_y": 0.0,
                "shadow_blur": 0.0,
                "grid_type": "hexagonal",
                "animation_speed": 1.2,
                "pulse_rate": 1.0
            },
            
            EnhancedDisplayTheme.HOLOGRAPHIC: {
                "use_gradients": True,
                "use_shadows": True,
                "use_glow": True,
                "use_angular_design": True,
                "use_holographic_elements": True,
                "use_parallax_effects": True,
                "use_pulse_effects": True,
                "corner_radius": 0.0,
                "line_width": 1.5,
                "glow_intensity": 0.5,
                "shadow_offset_x": 1.0,
                "shadow_offset_y": 1.0,
                "shadow_blur": 3.0,
                "grid_type": "hexagonal",
                "animation_speed": 1.0,
                "pulse_rate": 0.8
            },
            
            EnhancedDisplayTheme.STEALTH: {
                "use_gradients": True,
                "use_shadows": False,
                "use_glow": True,
                "use_angular_design": True,
                "use_holographic_elements": False,
                "use_parallax_effects": False,
                "use_pulse_effects": True,
                "corner_radius": 0.0,
                "line_width": 1.0,
                "glow_intensity": 0.2,
                "shadow_offset_x": 0.0,
                "shadow_offset_y": 0.0,
                "shadow_blur": 0.0,
                "grid_type": "radial",
                "animation_speed": 0.8,
                "pulse_rate": 0.5
            },
            
            EnhancedDisplayTheme.CUSTOM: {
                # Will be populated by user settings
                "use_gradients": True,
                "use_shadows": True,
                "use_glow": True,
                "use_angular_design": True,
                "use_holographic_elements": True,
                "use_parallax_effects": True,
                "use_pulse_effects": True,
                "corner_radius": 0.0,
                "line_width": 1.5,
                "glow_intensity": 0.5,
                "shadow_offset_x": 1.0,
                "shadow_offset_y": 1.0,
                "shadow_blur": 3.0,
                "grid_type": "hexagonal",
                "animation_speed": 1.0,
                "pulse_rate": 0.8
            }
        }
        
        # Initialize depth parameters
        self._depth_enabled = True
        self._depth_intensity = 0.5
        self._depth_color_shift = 0.2
        
        logger.info(f"Enhanced theme manager initialized with {self._current_theme.name} theme")
    
    def set_theme(self, theme: EnhancedDisplayTheme) -> None:
        """Set the current theme"""
        self._current_theme = theme
        logger.info(f"Theme set to {theme.name}")
    
    def get_theme(self) -> EnhancedDisplayTheme:
        """Get the current theme"""
        return self._current_theme
    
    def get_color(self, color_name: str) -> QColor:
        """Get a color from the current theme with improved fallback handling"""
        # Use throttled logging to prevent log spam
        should_log = True
        log_key = f"color_not_found_{self._current_theme.name}_{color_name}"
        
        # Try to get color from current theme
        if color_name in self._color_schemes[self._current_theme]:
            return QColor(self._color_schemes[self._current_theme][color_name])
        
        # Fallback 1: Try to find the color in similar themes
        # Define theme similarity groups for better fallbacks
        theme_groups = {
            EnhancedDisplayTheme.CLASSIC: [EnhancedDisplayTheme.MODERN, EnhancedDisplayTheme.CUSTOM],
            EnhancedDisplayTheme.MODERN: [EnhancedDisplayTheme.HOLOGRAPHIC, EnhancedDisplayTheme.CLASSIC],
            EnhancedDisplayTheme.TACTICAL: [EnhancedDisplayTheme.STEALTH, EnhancedDisplayTheme.HOLOGRAPHIC],
            EnhancedDisplayTheme.HOLOGRAPHIC: [EnhancedDisplayTheme.MODERN, EnhancedDisplayTheme.TACTICAL],
            EnhancedDisplayTheme.STEALTH: [EnhancedDisplayTheme.TACTICAL, EnhancedDisplayTheme.HOLOGRAPHIC],
            EnhancedDisplayTheme.CUSTOM: [EnhancedDisplayTheme.MODERN, EnhancedDisplayTheme.CLASSIC]
        }
        
        # Try similar themes first
        if self._current_theme in theme_groups:
            for similar_theme in theme_groups[self._current_theme]:
                if color_name in self._color_schemes[similar_theme]:
                    if should_log:
                        throttled_log(logger.warning, f"Color '{color_name}' not found in theme {self._current_theme.name}, using fallback from similar theme {similar_theme.name}", log_key)
                    return QColor(self._color_schemes[similar_theme][color_name])
        
        # Fallback 2: Try to find the color in any theme
        for theme in self._color_schemes:
            if theme != self._current_theme and color_name in self._color_schemes[theme]:
                if should_log:
                    throttled_log(logger.warning, f"Color '{color_name}' not found in theme {self._current_theme.name}, using fallback from {theme.name}", log_key)
                return QColor(self._color_schemes[theme][color_name])
        
        # Fallback 3: Use comprehensive fallback colors based on color name
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
            "waypoint": QColor(0, 200, 255),
            
            # Environment
            "sky": QColor(0, 0, 100),
            "ground": QColor(100, 50, 0),
            "grid": QColor(30, 30, 30),
            "background": QColor(0, 0, 0)
        }
        
        if color_name in fallback_colors:
            if should_log:
                throttled_log(logger.warning, f"Color '{color_name}' not found in any theme, using standard fallback", log_key)
            return fallback_colors[color_name]
        
        # Fallback 4: Try to infer color from name patterns
        color_patterns = {
            "background": fallback_colors["background"],
            "highlight": fallback_colors["menu_highlight"],
            "text": fallback_colors["menu_text"],
            "border": fallback_colors["menu_border"],
            "primary": fallback_colors["data_primary"],
            "secondary": fallback_colors["data_secondary"],
            "warning": fallback_colors["warning"],
            "caution": fallback_colors["caution"],
            "critical": fallback_colors["critical"],
            "normal": fallback_colors["system_normal"]
        }
        
        for pattern, color in color_patterns.items():
            if pattern in color_name:
                if should_log:
                    throttled_log(logger.warning, f"Color '{color_name}' not found, inferring from pattern '{pattern}'", log_key)
                return QColor(color)
        
        # Final fallback: white
        if should_log:
            throttled_log(logger.warning, f"Color '{color_name}' not found in theme {self._current_theme.name}, using white", log_key)
        return QColor(255, 255, 255)  # Default to white
    
    def set_color(self, color_name: str, color: QColor) -> None:
        """Set a color in the current theme"""
        if self._current_theme == EnhancedDisplayTheme.CUSTOM:
            self._color_schemes[self._current_theme][color_name] = QColor(color)
            logger.info(f"Set custom color '{color_name}' to {color.name()}")
        else:
            logger.warning(f"Cannot set color in non-custom theme {self._current_theme.name}")
    
    def get_style_param(self, param_name: str, default_value: Any = None) -> Any:
        """Get a style parameter from the current theme"""
        if param_name in self._style_params[self._current_theme]:
            return self._style_params[self._current_theme][param_name]
        else:
            logger.warning(f"Style parameter '{param_name}' not found in theme {self._current_theme.name}")
            return default_value
    
    def set_style_param(self, param_name: str, value: Any) -> None:
        """Set a style parameter in the current theme"""
        # Allow setting style parameters for any theme
        if param_name in self._style_params[self._current_theme]:
            self._style_params[self._current_theme][param_name] = value
            logger.info(f"Set style parameter '{param_name}' to {value} in theme {self._current_theme.name}")
        else:
            logger.warning(f"Style parameter '{param_name}' not found in theme {self._current_theme.name}")
    
    def is_depth_enabled(self) -> bool:
        """Check if depth effects are enabled"""
        return self._depth_enabled
    
    def set_depth_enabled(self, enabled: bool) -> None:
        """Enable or disable depth effects"""
        self._depth_enabled = enabled
        logger.info(f"Depth effects {'enabled' if enabled else 'disabled'}")
    
    def get_depth_intensity(self) -> float:
        """Get the depth effect intensity"""
        return self._depth_intensity
    
    def set_depth_intensity(self, intensity: float) -> None:
        """Set the depth effect intensity"""
        self._depth_intensity = max(0.0, min(1.0, intensity))
        logger.info(f"Depth intensity set to {self._depth_intensity}")
    
    def create_color_with_depth(self, color_name: str, depth: float) -> QColor:
        """Create a color with depth effect applied"""
        if not self._depth_enabled:
            return self.get_color(color_name)
            
        # Get base color
        base_color = self.get_color(color_name)
        
        # Apply depth effect
        effective_depth = depth * self._depth_intensity
        
        if effective_depth > 0:
            # Foreground (closer) - brighter and more saturated
            brightness_factor = 1.0 + effective_depth * 0.3
            saturation_factor = 1.0 + effective_depth * 0.2
            
            # Get HSL components
            hue = base_color.hue()
            saturation = min(255, int(base_color.saturation() * saturation_factor))
            lightness = min(255, int(base_color.lightness() * brightness_factor))
            
            # Create new color
            result = QColor()
            result.setHsl(
                hue,
                saturation,
                lightness,
                base_color.alpha()
            )
            
            return result
        elif effective_depth < 0:
            # Background (further) - darker and less saturated
            brightness_factor = 1.0 + effective_depth * 0.5  # Note: effective_depth is negative
            saturation_factor = 1.0 + effective_depth * 0.3  # Note: effective_depth is negative
            
            # Get HSL components
            hue = base_color.hue()
            saturation = max(0, int(base_color.saturation() * saturation_factor))
            lightness = max(0, int(base_color.lightness() * brightness_factor))
            
            # Create new color
            result = QColor()
            result.setHsl(
                hue,
                saturation,
                lightness,
                base_color.alpha()
            )
            
            return result
        else:
            # No depth effect
            return QColor(base_color)
    
    def get_animation_speed(self) -> float:
        """Get the animation speed multiplier"""
        return self.get_style_param("animation_speed", 1.0)

# Singleton instance
_enhanced_theme_manager = None

def get_enhanced_theme_manager() -> EnhancedThemeManager:
    """Get the singleton enhanced theme manager instance"""
    global _enhanced_theme_manager
    if _enhanced_theme_manager is None:
        _enhanced_theme_manager = EnhancedThemeManager()
    return _enhanced_theme_manager

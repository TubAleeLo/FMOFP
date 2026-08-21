"""
Visual Settings Manager

Centralized manager for display visual settings.
Provides a single source of truth for all visual overlay settings.
"""

import time
import traceback
from typing import Dict, Any, List, Callable
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class VisualSettingsManager:
    """Central manager for all display visual settings"""
    
    # Define all possible visual settings with defaults
    DEFAULT_SETTINGS = {
        'overlay': 'standby',
        'show_status': True,
        'show_legend': False,
        'show_values': False,
        'opacity': 1.0,
        'show_vil': False,
        'show_vil_legend': False,
        'show_vil_values': False,
        'show_scan_line': False,
        'show_intensity_scale': False,
        'show_terrain_scale': False
    }
    
    # Mode-specific setting presets
    MODE_SETTINGS = {
        'STANDBY': {
            'overlay': 'standby',
            'show_status': True,
            'show_legend': False,
            'show_values': False,
            'opacity': 1.0,
            # Data visibility settings
            'show_vil': False,
            'show_precipitation': False,
            'show_storm_cells': False,
            'show_turbulence': False,
            'show_windshear': False,
            'show_terrain': False,
            'show_cloud_tops': False,
            'show_lightning': False,
            'show_icing': False,
            # Display element settings
            'show_scan_line': False,
            'show_intensity_scale': False,
            'show_terrain_scale': False,
            # Legend-specific settings
            'show_vil_legend': False,
            'show_precipitation_legend': False,
            'show_intensity_legend': False,
            'show_turbulence_legend': False,
            'show_windshear_legend': False,
            'show_terrain_legend': False,
            # Value display settings
            'show_vil_values': False,
            'show_precipitation_values': False,
            'show_intensity_values': False,
            'show_turbulence_values': False,
            'show_windshear_values': False,
            'show_terrain_values': False,
            # Legend rendering strategy
            'legend_render_strategy': 'standard'
        },
        'SURVEILLANCE': {
            'overlay': 'surveillance',
            'show_status': True,
            'show_legend': True,
            'show_values': True,
            'opacity': 1.0,
            # Data visibility settings
            'show_vil': True,
            'show_precipitation': True,
            'show_storm_cells': True,
            'show_turbulence': False,
            'show_windshear': False,
            'show_terrain': False,
            'show_cloud_tops': False,
            'show_lightning': True,
            'show_icing': False,
            # Display element settings
            'show_scan_line': True,
            'show_intensity_scale': True,
            'show_terrain_scale': False,
            # Legend-specific settings
            'show_vil_legend': True,
            'show_precipitation_legend': True,
            'show_intensity_legend': True,
            'show_turbulence_legend': False,
            'show_windshear_legend': False,
            'show_terrain_legend': False,
            # Value display settings
            'show_vil_values': True,
            'show_precipitation_values': True,
            'show_intensity_values': True,
            'show_turbulence_values': False,
            'show_windshear_values': False,
            'show_terrain_values': False,
            # Legend rendering strategy
            'legend_render_strategy': 'standard'
        },
        'MAPPING': {
            'overlay': 'mapping',
            'show_status': True,
            'show_legend': True,
            'show_values': True,
            'opacity': 0.8,
            # Data visibility settings
            'show_vil': True,
            'show_precipitation': True,
            'show_storm_cells': False,
            'show_turbulence': False,
            'show_windshear': False,
            'show_terrain': True,
            'show_cloud_tops': True,
            'show_lightning': True,
            'show_icing': False,
            # Display element settings
            'show_scan_line': False,
            'show_intensity_scale': False,
            'show_terrain_scale': True,
            # Legend-specific settings
            'show_vil_legend': True,
            'show_precipitation_legend': False,
            'show_intensity_legend': False,
            'show_turbulence_legend': False,
            'show_windshear_legend': False,
            'show_terrain_legend': True,
            # Value display settings
            'show_vil_values': True,
            'show_precipitation_values': False,
            'show_intensity_values': False,
            'show_turbulence_values': False,
            'show_windshear_values': False,
            'show_terrain_values': True,
            # Legend rendering strategy
            'legend_render_strategy': 'standard'
        },
        'TURBULENCE': {
            'overlay': 'turbulence',
            'show_status': True,
            'show_legend': True,
            'show_values': True,
            'opacity': 1.0,
            # Data visibility settings
            'show_vil': False,
            'show_precipitation': False,
            'show_storm_cells': True,
            'show_turbulence': True,
            'show_windshear': False,
            'show_terrain': False,
            'show_cloud_tops': False,
            'show_lightning': True,
            'show_icing': True,
            # Display element settings
            'show_scan_line': False,
            'show_intensity_scale': True,
            'show_terrain_scale': False,
            # Legend-specific settings
            'show_vil_legend': False,
            'show_precipitation_legend': False,
            'show_intensity_legend': True,
            'show_turbulence_legend': True,
            'show_windshear_legend': False,
            'show_terrain_legend': False,
            # Value display settings
            'show_vil_values': False,
            'show_precipitation_values': False,
            'show_intensity_values': True,
            'show_turbulence_values': True,
            'show_windshear_values': False,
            'show_terrain_values': False,
            # Legend rendering strategy
            'legend_render_strategy': 'standard'
        },
        'WINDSHEAR': {
            'overlay': 'windshear',
            'show_status': True,
            'show_legend': True,
            'show_values': True,
            'opacity': 1.0,
            # Data visibility settings
            'show_vil': False,
            'show_precipitation': True,
            'show_storm_cells': True,
            'show_turbulence': False,
            'show_windshear': True,
            'show_terrain': False,
            'show_cloud_tops': False,
            'show_lightning': True,
            'show_icing': False,
            # Display element settings
            'show_scan_line': False,
            'show_intensity_scale': True,
            'show_terrain_scale': False,
            # Legend-specific settings
            'show_vil_legend': False,
            'show_precipitation_legend': False,
            'show_intensity_legend': True,
            'show_turbulence_legend': False,
            'show_windshear_legend': True,
            'show_terrain_legend': False,
            # Value display settings
            'show_vil_values': False,
            'show_precipitation_values': False,
            'show_intensity_values': True,
            'show_turbulence_values': False,
            'show_windshear_values': True,
            'show_terrain_values': False,
            # Legend rendering strategy
            'legend_render_strategy': 'standard'
        }
    }
    
    def __init__(self, radar_type: str):
        """Initialize the visual settings manager.
        
        Args:
            radar_type: The type of radar (e.g., 'weather_radar')
        """
        self.radar_type = radar_type
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.observers: List[Callable[[Dict[str, Any]], None]] = []
        self._tree_manager = None
        self._visual_node = None
        self._last_update_time = time.time()
        logger.info(f"[VISUAL_SETTINGS] Initialized manager for {radar_type}")
        
    def get_visual_node(self):
        """Get the current visual node for this radar type.
        
        Returns:
            The visual node for this radar type, or None if not found
        """
        try:
            if not self._tree_manager:
                from ..display_nodes.display_tree_manager import get_display_tree_manager
                self._tree_manager = get_display_tree_manager()
                
            radar = self._tree_manager.root.get_child(self.radar_type)
            if radar:
                self._visual_node = radar.get_child("visual")
                return self._visual_node
            else:
                logger.warning(f"[VISUAL_SETTINGS] Radar node not found for {self.radar_type}")
                return None
        except Exception as e:
            logger.error(f"[VISUAL_SETTINGS] Error getting visual node: {str(e)}")
            logger.error(traceback.format_exc())
            return None
        
    def get_settings(self) -> Dict[str, Any]:
        """Get the current settings.
        
        Returns:
            A copy of the current settings dictionary
        """
        return self.settings.copy()
        
    def apply_mode_settings(self, mode: str) -> Dict[str, Any]:
        """Apply mode-specific settings and return the new settings (synchronous version).
        
        Args:
            mode: The radar mode (e.g., 'SURVEILLANCE', 'MAPPING', 'STANDBY')
            
        Returns:
            A copy of the updated settings dictionary
        """
        try:
            # Normalize mode name to uppercase
            mode_upper = mode.upper() if isinstance(mode, str) else 'STANDBY'
            
            # Get mode-specific settings or fallback to STANDBY
            mode_settings = self.MODE_SETTINGS.get(mode_upper, self.MODE_SETTINGS['STANDBY'])
            
            # Log the mode change
            logger.info(f"[VISUAL_SETTINGS] Applying {mode_upper} settings for {self.radar_type}")
            
            # Update settings
            self.settings.update(mode_settings)
            self._last_update_time = time.time()
            
            # Update legend manager if available
            try:
                from ..radar.legend_manager import get_legend_manager
                legend_manager = get_legend_manager(self.radar_type)
                if legend_manager:
                    legend_manager.update_legend_state(mode_upper)
                    logger.info(f"[VISUAL_SETTINGS] Updated legend manager for mode: {mode_upper}")
            except ImportError:
                logger.warning(f"[VISUAL_SETTINGS] Could not import legend_manager")
            except Exception as e:
                logger.error(f"[VISUAL_SETTINGS] Error updating legend manager: {str(e)}")
            
            # Notify observers
            self._notify_observers()
            
            return self.settings.copy()
        except Exception as e:
            logger.error(f"[VISUAL_SETTINGS] Error applying mode settings: {str(e)}")
            logger.error(traceback.format_exc())
            return self.settings.copy()
            
    async def apply_mode_settings_async(self, mode: str) -> Dict[str, Any]:
        """Apply mode-specific settings and return the new settings (asynchronous version).
        
        Args:
            mode: The radar mode (e.g., 'SURVEILLANCE', 'MAPPING', 'STANDBY')
            
        Returns:
            A copy of the updated settings dictionary
        """
        try:
            # Normalize mode name to uppercase
            mode_upper = mode.upper() if isinstance(mode, str) else 'STANDBY'
            
            # Get mode-specific settings or fallback to STANDBY
            mode_settings = self.MODE_SETTINGS.get(mode_upper, self.MODE_SETTINGS['STANDBY'])
            
            # Log the mode change
            logger.info(f"[VISUAL_SETTINGS] Applying {mode_upper} settings for {self.radar_type}")
            
            # Update settings
            self.settings.update(mode_settings)
            self._last_update_time = time.time()
            
            # Apply to visual node
            await self.update_visual_node()
            
            # Update legend manager if available
            try:
                from ..radar.legend_manager import get_legend_manager
                legend_manager = get_legend_manager(self.radar_type)
                if legend_manager:
                    legend_manager.update_legend_state(mode_upper)
                    logger.info(f"[VISUAL_SETTINGS] Updated legend manager for mode: {mode_upper}")
            except ImportError:
                logger.error(f"[VISUAL_SETTINGS] Could not import legend_manager")
            except Exception as e:
                logger.error(f"[VISUAL_SETTINGS] Error updating legend manager: {str(e)}")
            
            # Notify observers
            self._notify_observers()
            
            return self.settings.copy()
        except Exception as e:
            logger.error(f"[VISUAL_SETTINGS] Error applying mode settings asynchronously: {str(e)}")
            logger.error(traceback.format_exc())
            return self.settings.copy()
        
    async def update_visual_node(self) -> None:
        """Update the visual node with current settings."""
        try:
            visual_node = self.get_visual_node()
            if visual_node:
                logger.info(f"[VISUAL_SETTINGS] Updating visual node for {self.radar_type}")
                await visual_node.update(self.settings)
                logger.info(f"[VISUAL_SETTINGS] Visual node updated successfully")
            else:
                logger.warning(f"[VISUAL_SETTINGS] Cannot update visual node: not found")
        except Exception as e:
            logger.error(f"[VISUAL_SETTINGS] Error updating visual node: {str(e)}")
            logger.error(traceback.format_exc())
            
    def update_settings(self, new_settings: Dict[str, Any], apply_to_node: bool = False) -> Dict[str, Any]:
        """Update settings synchronously (without applying to visual node).
        
        This is a synchronous version of update_settings that can be called from non-async methods.
        It does not apply changes to the visual node by default.
        
        Args:
            new_settings: Dictionary of settings to update
            apply_to_node: Whether to apply the settings to the visual node (ignored in sync version)
            
        Returns:
            A copy of the updated settings dictionary
        """
        try:
            # Log the update
            logger.info(f"[VISUAL_SETTINGS] Updating settings synchronously for {self.radar_type}: {new_settings}")
            
            # Update settings
            self.settings.update(new_settings)
            self._last_update_time = time.time()
            
            # Notify observers
            self._notify_observers()
            
            return self.settings.copy()
        except Exception as e:
            logger.error(f"[VISUAL_SETTINGS] Error updating settings synchronously: {str(e)}")
            logger.error(traceback.format_exc())
            return self.settings.copy()
            
    async def update_settings_async(self, new_settings: Dict[str, Any], apply_to_node: bool = True) -> Dict[str, Any]:
        """Update settings asynchronously and optionally apply to the visual node.
        
        Args:
            new_settings: Dictionary of settings to update
            apply_to_node: Whether to apply the settings to the visual node
            
        Returns:
            A copy of the updated settings dictionary
        """
        try:
            # Log the update
            logger.info(f"[VISUAL_SETTINGS] Updating settings asynchronously for {self.radar_type}: {new_settings}")
            
            # Update settings
            self.settings.update(new_settings)
            self._last_update_time = time.time()
            
            # Apply to node if requested
            if apply_to_node:
                await self.update_visual_node()
                
            # Notify observers
            self._notify_observers()
            
            return self.settings.copy()
        except Exception as e:
            logger.error(f"[VISUAL_SETTINGS] Error updating settings asynchronously: {str(e)}")
            logger.error(traceback.format_exc())
            return self.settings.copy()
    
    def add_observer(self, observer: Callable[[Dict[str, Any]], None]) -> None:
        """Add an observer to be notified of settings changes.
        
        Args:
            observer: Callback function that takes settings dictionary as argument
        """
        if observer not in self.observers:
            self.observers.append(observer)
            logger.info(f"[VISUAL_SETTINGS] Added observer to {self.radar_type} settings")
    
    def remove_observer(self, observer: Callable[[Dict[str, Any]], None]) -> None:
        """Remove an observer.
        
        Args:
            observer: Observer to remove
        """
        if observer in self.observers:
            self.observers.remove(observer)
            logger.info(f"[VISUAL_SETTINGS] Removed observer from {self.radar_type} settings")
    
    def _notify_observers(self) -> None:
        """Notify all observers of settings changes."""
        settings_copy = self.settings.copy()
        for observer in self.observers:
            try:
                observer(settings_copy)
            except Exception as e:
                logger.error(f"[VISUAL_SETTINGS] Error notifying observer: {str(e)}")
                logger.error(traceback.format_exc())
    
    def get_last_update_time(self) -> float:
        """Get the timestamp of the last settings update.
        
        Returns:
            Timestamp of the last update
        """
        return self._last_update_time
    
    def __repr__(self) -> str:
        """String representation of the manager.
        
        Returns:
            String representation
        """
        return f"VisualSettingsManager(radar_type={self.radar_type}, settings={self.settings})"


class VisualSettingsManagerFactory:
    """Factory for VisualSettingsManager instances"""
    
    _instances: Dict[str, VisualSettingsManager] = {}
    
    @classmethod
    def get_manager(cls, radar_type: str) -> VisualSettingsManager:
        """Get or create a VisualSettingsManager for a radar type.
        
        Args:
            radar_type: The type of radar (e.g., 'weather_radar')
            
        Returns:
            VisualSettingsManager instance for the specified radar type
        """
        if radar_type not in cls._instances:
            cls._instances[radar_type] = VisualSettingsManager(radar_type)
            logger.info(f"[VISUAL_SETTINGS] Created new manager for {radar_type}")
        return cls._instances[radar_type]
    
    @classmethod
    def get_all_managers(cls) -> Dict[str, VisualSettingsManager]:
        """Get all VisualSettingsManager instances.
        
        Returns:
            Dictionary of all VisualSettingsManager instances
        """
        return cls._instances.copy()


def get_visual_settings_manager(radar_type: str) -> VisualSettingsManager:
    """Get a VisualSettingsManager for a radar type.
    
    Args:
        radar_type: The type of radar (e.g., 'weather_radar')
        
    Returns:
        VisualSettingsManager instance for the specified radar type
    """
    return VisualSettingsManagerFactory.get_manager(radar_type)

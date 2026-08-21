"""
Mode Node

Specialized node for handling display mode state.
Tracks mode transitions and maintains mode history.
"""

import time
import importlib
import traceback
from typing import Any, Dict, Optional, Union
from .display_node_base import DisplayNode
from Systems.radarManagement.radar_enums import (
    weather_radarMode, targeting_radarMode,
    tfr_radarMode, sar_radarMode, aewc_radarMode
)
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class ModeNode(DisplayNode):
    """Node for managing display mode state"""
    
    def __init__(self, name: str, parent: Optional[DisplayNode] = None):
        """Initialize mode node.
        
        Args:
            name: Node identifier
            parent: Optional parent node
        """
        super().__init__(name, parent)
        self.previous_mode = None
        self.mode_enum = None
        self.transition_timestamp = None
        self.mode_history = []  # List of (mode, timestamp) tuples
        self.max_history = 10  # Keep last 10 mode changes
        
        # Node creation is logged by base class

    async def update(self, mode_data: Union[Dict[str, Any], str], notify: bool = True) -> None:
        """Update mode state.
        
        Args:
            mode_data: Mode update data (can be dict or string)
            notify: Whether to notify subscribers
        """
        try:
            with self._lock:
                # Store previous mode
                self.previous_mode = self.value
                
                # Handle string mode data
                if isinstance(mode_data, str):
                    current_mode = mode_data
                    mode_enum_name = None
                    mode_value = None
                    source_system = None
                    logger.info(f"[MODE_NODE] Received string mode data: {current_mode}")
                else:
                    # Extract mode data from dictionary
                    current_mode = mode_data.get('current_mode')
                    mode_enum_name = mode_data.get('mode_enum')
                    mode_value = mode_data.get('mode_value')
                    source_system = mode_data.get('source_system')
                    logger.info(f"[MODE_NODE] Received dict mode data: {mode_data}")
                
                if not current_mode:
                    logger.error("[MODE_NODE] Missing current_mode in update data")
                    return
                
                # Log mode state update first
                logger.info(f"[MODE_NODE] Starting Mode state update to {current_mode}")
                
                # Get mode enum class
                if mode_enum_name:
                    self.mode_enum = self._get_mode_enum(mode_enum_name)
                elif source_system:
                    # Try to get enum from source system
                    enum_name = f"{source_system}_mode"
                    self.mode_enum = self._get_mode_enum(enum_name)
                    logger.info(f"[MODE_NODE] Using enum from source system: {enum_name}")
                elif mode_value is not None:
                    # If we have a mode value but no enum, try to determine enum from value
                    self.mode_enum = self._get_mode_enum(mode_value)
                    logger.info(f"[MODE_NODE] Using enum determined from mode value: {mode_value}")
                elif mode_value is not None:
                    # If we have a mode value but no enum, try to determine enum from value
                    self.mode_enum = self._get_mode_enum(mode_value)
                    logger.info(f"[MODE_NODE] Using enum determined from mode value: {mode_value}")
                
                # Handle mode value
                if mode_value is not None:
                    # Convert string to int if needed
                    if isinstance(mode_value, str):
                        try:
                            mode_value = int(mode_value)
                        except ValueError:
                            logger.error(f"[MODE_NODE] Invalid mode value string: {mode_value}")
                            mode_value = None
                
                # Validate mode with enum
                if self.mode_enum:
                    try:
                        if mode_value is not None:
                            # Try to get enum by value
                            try:
                                mode_instance = self.mode_enum(mode_value)
                                if mode_instance.name != current_mode:
                                    logger.warning(f"[MODE_NODE] Mode name mismatch: {current_mode} != {mode_instance.name}")
                                    # If we're explicitly setting a mode, trust the requested mode name over the enum
                                    # This is critical for cross-system communication where enum values may not match
                                    logger.info(f"[MODE_NODE] Using explicitly requested mode: {current_mode}")
                                    # Don't override the current_mode with mode_instance.name
                            except ValueError:
                                # The mode value doesn't exist in this radar's enum
                                # This is expected for cross-radar-type communication
                                logger.warning(f"[MODE_NODE] Mode value {mode_value} not found in {self.mode_enum.__name__}")
                                
                                # Try to get universal RadarDisplayMode to understand what this value represents
                                try:
                                    from FMOFP.local_messaging.radar_display_modes import RadarDisplayMode
                                    for universal_mode in RadarDisplayMode:
                                        if universal_mode.value == mode_value:
                                            logger.info(f"[MODE_NODE] Found value {mode_value} in RadarDisplayMode as {universal_mode.name}")
                                            # We want to continue with the current mode string, but log what it represents
                                            logger.info(f"[MODE_NODE] Cross-radar mode: {universal_mode.name} ({mode_value}) accepted")
                                            break
                                except (ImportError, AttributeError) as radar_err:
                                    logger.warning(f"[MODE_NODE] Could not load RadarDisplayMode: {radar_err}")
                                
                                # Continue with the requested mode string regardless
                                logger.info(f"[MODE_NODE] Accepting cross-radar mode value: {mode_value}")
                        else:
                            # Try to get enum by name
                            try:
                                mode_instance = getattr(self.mode_enum, current_mode)
                                mode_value = mode_instance.value
                            except AttributeError:
                                # The mode name doesn't exist in this radar's enum
                                # This is expected for cross-radar-type communication
                                logger.warning(f"[MODE_NODE] Mode name {current_mode} not found in {self.mode_enum.__name__}")
                                
                                # Try to get a universal mode value for this name if possible
                                try:
                                    from FMOFP.local_messaging.radar_display_modes import RadarDisplayMode
                                    if hasattr(RadarDisplayMode, current_mode):
                                        universal_mode = getattr(RadarDisplayMode, current_mode)
                                        mode_value = universal_mode.value
                                        logger.info(f"[MODE_NODE] Found universal mode value {mode_value} for {current_mode}")
                                    else:
                                        # Try the radar_mode_converter which has more sophisticated mapping
                                        from FMOFP.local_messaging.radar_mode_converter import mode_to_value
                                        converter_value = mode_to_value(current_mode)
                                        if converter_value is not None:
                                            mode_value = converter_value
                                            logger.info(f"[MODE_NODE] Used converter to get mode value {mode_value} for {current_mode}")
                                except (ImportError, AttributeError) as radar_err:
                                    logger.warning(f"[MODE_NODE] Could not access radar mode utilities: {radar_err}")
                    except (ValueError, AttributeError) as e:
                        logger.error(f"[MODE_NODE] Mode validation failed: {e}")
                        # Don't fall back to previous mode or STANDBY if we have an explicit mode request
                        # This is critical for cross-system communication
                        logger.info(f"[MODE_NODE] Continuing with requested mode: {current_mode}")
                
                # Update mode state
                self.value = current_mode
                self.transition_timestamp = time.time()
                logger.info(f"[MODE_NODE] Mode state updated: {current_mode}")
                
                # Update history
                self.mode_history.append((current_mode, self.transition_timestamp))
                if len(self.mode_history) > self.max_history:
                    self.mode_history.pop(0)
                
                # Log mode transition
                logger.info(f"[MODE_NODE] {self.name} transitioned: {self.previous_mode} -> {current_mode}")
                logger.info(f"[MODE_NODE] Mode transition complete")

            # Notify subscribers OUTSIDE the `with self._lock` block — same
            # fix Round 12 applied to DisplayNode.update() in
            # display_node_base.py, which this override was missed by
            # (found August 2026 live-boot re-verification). Round 12 also
            # made _notify_subscribers() itself briefly acquire self._lock
            # to snapshot the subscriber set; self._lock is a non-reentrant
            # threading.Lock, so awaiting the notify while still holding
            # the lock here self-deadlocked on the first mode update
            # delivered through this override. (The early `return` above
            # still skips notification entirely, as before.)
            if notify:
                await self._notify_subscribers()

        except Exception as e:
            self.metadata.error_count += 1
            self.metadata.last_error = str(e)
            logger.error(f"[MODE_NODE] Error updating mode {self.name}: {str(e)}")
            logger.error(traceback.format_exc())
            raise
        
    def _get_mode_enum(self, enum_name: Optional[Union[str, int]]) -> Optional[type]:
        """Get mode enum class from name or value.
        
        Args:
            enum_name: Name of enum class (str) or mode value (int)
                
        Returns:
            Mode enum class for the appropriate radar type
        """
        # Integer handling - map mode value directly to radar type enum
        if isinstance(enum_name, int):
            mode_value = enum_name
            logger.info(f"[MODE_NODE] Received int mode value: {mode_value}")
            
            # Map mode value ranges to specific radar enum types
            if 0 <= mode_value <= 9:  # Universal base modes
                logger.info(f"[MODE_NODE] Mode value {mode_value} is a Universal Base Mode")
                return weather_radarMode  # These exist in all radar enums
            elif 10 <= mode_value <= 19:  # Weather radar modes
                logger.info(f"[MODE_NODE] Mode value {mode_value} is a Weather Radar Mode")
                return weather_radarMode
            elif 20 <= mode_value <= 29:  # TFR radar modes
                logger.info(f"[MODE_NODE] Mode value {mode_value} is a TFR Radar Mode")
                return tfr_radarMode
            elif 30 <= mode_value <= 39:  # SAR radar modes
                logger.info(f"[MODE_NODE] Mode value {mode_value} is a SAR Radar Mode")
                return sar_radarMode
            elif 40 <= mode_value <= 49:  # Targeting radar modes
                logger.info(f"[MODE_NODE] Mode value {mode_value} is a Targeting Radar Mode")
                return targeting_radarMode
            elif 50 <= mode_value <= 59:  # AEWC radar modes
                logger.info(f"[MODE_NODE] Mode value {mode_value} is an AEWC Radar Mode")
                return aewc_radarMode
            else:
                logger.warning(f"[MODE_NODE] Unknown mode value {mode_value}, defaulting to weather_radarMode")
                return weather_radarMode
        
        # String handling (existing functionality)
        if not enum_name:
            return None
            
        # Try static enum map first
        enum_map = {
            'weather_radarMode': weather_radarMode,
            'targeting_radarMode': targeting_radarMode,
            'tfr_radarMode': tfr_radarMode,
            'sar_radarMode': sar_radarMode,
            'aewc_radarMode': aewc_radarMode,
        }
        
        enum_class = enum_map.get(enum_name)
        if enum_class:
            return enum_class
            
        # Try dynamic import
        try:
            module = importlib.import_module('Systems.radarManagement.radar_enums')
            enum_class = getattr(module, enum_name)
            return enum_class
        except (ImportError, AttributeError) as e:
            logger.warning(f"[MODE_NODE] Could not get enum {enum_name}, using fallback: {e}")
            # Use weather_radarMode as fallback
            return weather_radarMode


    def get_state(self) -> Dict[str, Any]:
        """Get complete mode state.
        
        Returns:
            Dict containing mode state
        """
        with self._lock:
            state = super().get_state()
            state.update({
                'previous_mode': self.previous_mode,
                'mode_enum': self.mode_enum.__name__ if self.mode_enum else None,
                'transition_timestamp': self.transition_timestamp,
                'mode_history': self.mode_history
            })
            return state

    def get_mode_history(self) -> list:
        """Get mode transition history.
        
        Returns:
            List of (mode, timestamp) tuples
        """
        with self._lock:
            return self.mode_history.copy()

    def get_time_in_mode(self) -> float:
        """Get time spent in current mode.
        
        Returns:
            Seconds since last mode change
        """
        if self.transition_timestamp is None:
            return 0
        return time.time() - self.transition_timestamp

    async def update_state(self, mode_data: Union[Dict[str, Any], str]) -> None:
        """Alias for update() to maintain consistency with router interface."""
        await self.update(mode_data)

    def __repr__(self) -> str:
        """String representation of mode node.
        
        Returns:
            Node description string
        """
        return (f"ModeNode(name={self.name}, current={self.value}, "
                f"previous={self.previous_mode}, time_in_mode={self.get_time_in_mode():.1f}s)")

"""
Visual Node

Specialized node for handling display visual elements.
Manages overlays, elements, and visual state.
"""

import time
import traceback
from typing import Any, Dict, Optional, Set
from .display_node_base import DisplayNode
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class VisualNode(DisplayNode):
    """Node for managing display visual elements"""
    
    def __init__(self, name: str, parent: Optional[DisplayNode] = None):
        """Initialize visual node.
        
        Args:
            name: Node identifier
            parent: Optional parent node
        """
        super().__init__(name, parent)
        self.overlay_type = None
        self.elements: Set[str] = set()
        self.colors: Dict[str, str] = {}
        self.opacity = 1.0
        self.show_legend = False
        self.show_values = False
        self.last_render_time = None
        
        # Node creation is logged by base class

    async def update(self, visual_data: Dict[str, Any], notify: bool = True) -> None:
        """Update visual state.
        
        Args:
            visual_data: Visual update data
            notify: Whether to notify subscribers
        """
        try:
            with self._lock:
                # Log visual state update first
                logger.info(f"[DISPLAY_NODE] Updating visual: {visual_data}")
                
                # Check if this is a VIL data update
                is_vil_data_update = False
                if 'show_vil' in visual_data and visual_data.get('show_vil', False):
                    is_vil_data_update = True
                    logger.info("[VISUAL_NODE] Detected VIL data update")
                
                # Update overlay type and mode-specific settings
                new_overlay = visual_data.get('overlay')
                if new_overlay != self.overlay_type:
                    self.overlay_type = new_overlay
                    
                    # Apply mode-specific settings
                    if new_overlay == 'surveillance':
                        self.show_legend = visual_data.get('show_legend', True)
                        self.show_values = visual_data.get('show_values', True)
                        self.opacity = visual_data.get('opacity', 1.0)
                    elif new_overlay == 'mapping':
                        self.show_legend = visual_data.get('show_legend', True)
                        self.show_values = visual_data.get('show_values', False)
                        self.opacity = visual_data.get('opacity', 0.8)
                    elif new_overlay == 'standby':
                        if is_vil_data_update:
                            logger.info("[VISUAL_NODE] Preserving VIL settings during standby mode update")
                            self.show_legend = visual_data.get('show_legend', False)
                            self.show_values = visual_data.get('show_values', False)
                            self.opacity = visual_data.get('opacity', 1.0)
                        else:
                            self.show_legend = False
                            self.show_values = False
                            self.opacity = 1.0
                
                # Update elements with validation
                new_elements = set()
                for element in visual_data.get('elements', []):
                    if isinstance(element, str):
                        new_elements.add(element)
                    else:
                        logger.warning(f"[VISUAL_NODE] Invalid element type: {type(element)}")
                
                added = new_elements - self.elements
                removed = self.elements - new_elements
                if added:
                    logger.info(f"[VISUAL_NODE] Added elements: {added}")
                if removed:
                    logger.info(f"[VISUAL_NODE] Removed elements: {removed}")
                self.elements = new_elements
                logger.info("[VISUAL_NODE] Element update complete")
                
                # Log color update
                logger.info("[VISUAL_NODE] Updating colors")
                
                # Update colors
                new_colors = visual_data.get('colors', {})
                if new_colors != self.colors:
                    logger.info(f"[VISUAL_NODE] Updated colors: {new_colors}")
                    self.colors = new_colors
                
                # Update display options
                self.opacity = visual_data.get('opacity', 1.0)
                self.show_legend = visual_data.get('show_legend', False)
                self.show_values = visual_data.get('show_values', False)
                
                # Store complete visual data
                self.value = visual_data
                self.last_render_time = time.time()
                
                # Log visual update completion
                logger.info(f"[DISPLAY_NODE] Updated visual: {self.overlay_type}")

            # Notify subscribers OUTSIDE the `with self._lock` block — same
            # fix Round 12 applied to DisplayNode.update() in
            # display_node_base.py, which this override was missed by
            # (found August 2026 live-boot re-verification). Round 12 also
            # made _notify_subscribers() itself briefly acquire self._lock
            # to snapshot the subscriber set; self._lock is a non-reentrant
            # threading.Lock, so awaiting the notify while still holding
            # the lock here self-deadlocked on the FIRST visual update of
            # boot (display_tree_manager.initialize_radar_branch), hanging
            # initialize_system() forever.
            if notify:
                await self._notify_subscribers()

        except Exception as e:
            self.metadata.error_count += 1
            self.metadata.last_error = str(e)
            logger.error(f"[VISUAL_NODE] Error updating visuals {self.name}: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def get_state(self) -> Dict[str, Any]:
        """Get complete visual state.
        
        Returns:
            Dict containing visual state
        """
        with self._lock:
            state = super().get_state()
            state.update({
                'overlay_type': self.overlay_type,
                'elements': list(self.elements),
                'colors': self.colors,
                'opacity': self.opacity,
                'show_legend': self.show_legend,
                'show_values': self.show_values,
                'last_render_time': self.last_render_time
            })
            return state

    def has_element(self, element: str) -> bool:
        """Check if element is present.
        
        Args:
            element: Element to check
            
        Returns:
            True if element exists
        """
        return element in self.elements

    def get_color(self, element: str) -> Optional[str]:
        """Get color for element.
        
        Args:
            element: Element to get color for
            
        Returns:
            Color string or None if not found
        """
        return self.colors.get(element)

    def get_render_age(self) -> Optional[float]:
        """Get time since last render.
        
        Returns:
            Seconds since last render or None if never rendered
        """
        if self.last_render_time is None:
            return None
        return time.time() - self.last_render_time

    async def update_state(self, visual_data: Dict[str, Any]) -> None:
        """Alias for update() to maintain consistency with router interface."""
        await self.update(visual_data)

    def __repr__(self) -> str:
        """String representation of visual node.
        
        Returns:
            Node description string
        """
        age = self.get_render_age()
        age_str = f"{age:.1f}s ago" if age is not None else "never"
        return (f"VisualNode(name={self.name}, overlay={self.overlay_type}, "
                f"elements={len(self.elements)}, last_render={age_str})")

"""
FMS Orientation Behavior

Handles the connection between FMS data and display orientation nodes.
Creates and updates the orientation node structure based on FMS data.
"""

import asyncio
import traceback
from typing import Dict, Any, Optional
from FMOFP.Systems.flightManagementSys.flightManagementSystem import get_flightManagementSystem
from FMOFP.Interfaces.userInterface.displays.display_nodes.display_tree_manager import get_display_tree_manager
from FMOFP.Interfaces.userInterface.displays.display_nodes.orientation_node import OrientationNode
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class FMSOrientationBehavior:
    """Behavior handler for connecting FMS to display orientation nodes"""
    
    def __init__(self):
        """Initialize FMS orientation behavior"""
        self.fms = get_flightManagementSystem()
        self.tree_manager = get_display_tree_manager()
        self.update_interval = 0.05  # 20Hz update rate
        self.running = False
        self.task = None
        
        # Ensure the orientation node structure is created
        self._ensure_orientation_nodes()
        logger.info("[FMS_BEHAVIOR] FMS Orientation Behavior initialized")
    
    def _ensure_orientation_nodes(self) -> None:
        """Create orientation nodes if they don't exist"""
        try:
            # Get or create flight_orientation branch
            root = self.tree_manager.root
            if not root.get_child("flight_orientation"):
                orientation_root = OrientationNode("flight_orientation", parent=root)
                root.add_child(orientation_root)
                logger.info("[FMS_BEHAVIOR] Created flight_orientation root node")
            else:
                orientation_root = root.get_child("flight_orientation")
            
            # Create attitude node if it doesn't exist
            if not orientation_root.get_child("attitude"):
                attitude_node = OrientationNode("attitude", parent=orientation_root)
                orientation_root.add_child(attitude_node)
                logger.info("[FMS_BEHAVIOR] Created attitude node")
            
            # Create position node if it doesn't exist
            if not orientation_root.get_child("position"):
                position_node = OrientationNode("position", parent=orientation_root)
                orientation_root.add_child(position_node)
                logger.info("[FMS_BEHAVIOR] Created position node")
            
            # Create velocity node if it doesn't exist
            if not orientation_root.get_child("velocity"):
                velocity_node = OrientationNode("velocity", parent=orientation_root)
                orientation_root.add_child(velocity_node)
                logger.info("[FMS_BEHAVIOR] Created velocity node")
            
            # Create tactical node if it doesn't exist
            if not orientation_root.get_child("tactical"):
                tactical_node = OrientationNode("tactical", parent=orientation_root)
                orientation_root.add_child(tactical_node)
                logger.info("[FMS_BEHAVIOR] Created tactical node")
            
            logger.info("[FMS_BEHAVIOR] Orientation node structure verified")
        except Exception as e:
            logger.error(f"[FMS_BEHAVIOR] Error creating orientation nodes: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def _update_orientation_nodes(self) -> None:
        """Update orientation nodes with current FMS data"""
        try:
            # Get current FMS flight data
            flight_data = self.fms.get_flight_data()
            
            # Get orientation nodes
            orientation_root = self.tree_manager.root.get_child("flight_orientation")
            if not orientation_root:
                logger.error("[FMS_BEHAVIOR] Orientation root node not found!")
                return
            
            # Update attitude node
            attitude_node = orientation_root.get_child("attitude")
            if attitude_node and 'attitude' in flight_data:
                await attitude_node.set_parameters(flight_data['attitude'])
            
            # Update position node
            position_node = orientation_root.get_child("position")
            if position_node and 'navigation' in flight_data:
                # Extract position-related data from navigation
                position_data = {
                    'altitude': flight_data['navigation'].get('altitude', 0),
                    'heading': flight_data['navigation'].get('heading', 0),
                    'latitude': flight_data['navigation'].get('latitude', 0),
                    'longitude': flight_data['navigation'].get('longitude', 0),
                    'track': flight_data['navigation'].get('track', 0)
                }
                await position_node.set_parameters(position_data)
            
            # Update velocity node
            velocity_node = orientation_root.get_child("velocity")
            if velocity_node and 'velocity' in flight_data:
                await velocity_node.set_parameters(flight_data['velocity'])
            
            # Update tactical node
            tactical_node = orientation_root.get_child("tactical")
            if tactical_node and 'tactical' in flight_data:
                await tactical_node.set_parameters(flight_data['tactical'])
            
        except Exception as e:
            logger.error(f"[FMS_BEHAVIOR] Error updating orientation nodes: {str(e)}")
            logger.error(traceback.format_exc())
    
    async def _update_loop(self) -> None:
        """Main update loop for FMS data to orientation nodes"""
        logger.info("[FMS_BEHAVIOR] Starting FMS orientation update loop")
        while self.running:
            try:
                start_time = asyncio.get_event_loop().time()
                
                # Update orientation nodes with current FMS data
                await self._update_orientation_nodes()
                
                # Calculate time to sleep to maintain update rate
                elapsed = asyncio.get_event_loop().time() - start_time
                sleep_time = max(0, self.update_interval - elapsed)
                await asyncio.sleep(sleep_time)
            except Exception as e:
                logger.error(f"[FMS_BEHAVIOR] Error in update loop: {str(e)}")
                logger.error(traceback.format_exc())
                await asyncio.sleep(1)  # Sleep longer on error
        
        logger.info("[FMS_BEHAVIOR] FMS orientation update loop ended")
    
    def start(self) -> None:
        """Start the FMS orientation behavior"""
        if not self.running:
            self.running = True
            self.task = asyncio.create_task(self._update_loop())
            logger.info("[FMS_BEHAVIOR] FMS Orientation Behavior started")
    
    def stop(self) -> None:
        """Stop the FMS orientation behavior"""
        if self.running:
            self.running = False
            if self.task:
                self.task.cancel()
            logger.info("[FMS_BEHAVIOR] FMS Orientation Behavior stopped")
    
    def is_running(self) -> bool:
        """Check if behavior is running"""
        return self.running

# Singleton pattern
_fms_orientation_behavior = None

def get_fms_orientation_behavior():
    """Get singleton instance of FMS Orientation Behavior"""
    global _fms_orientation_behavior
    if _fms_orientation_behavior is None:
        _fms_orientation_behavior = FMSOrientationBehavior()
    return _fms_orientation_behavior

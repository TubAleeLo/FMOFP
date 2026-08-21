"""
Radar Event Manager

Manages radar event routing and subscription handling.
Provides centralized event management for all radar types.
"""

from typing import Dict, Any, Set
from FMOFP.core.event_driven_communication import Event, get_event_bus
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Interfaces.userInterface.displays.radar.radar_data_handler.base_radar_data_handler import BaseRadarDataHandler

logger = get_logger()

class RadarEventManager:
    def __init__(self, event_bus=None):
        """Initialize radar event manager.
        
        Args:
            event_bus: Optional event bus instance. If None, gets global instance.
        """
        self.event_bus = event_bus or get_event_bus()
        self.handlers: Dict[str, BaseRadarDataHandler] = {}
        self.topics: Dict[str, Set[str]] = {}  # radar_type -> topics
        self.topic_registry: Dict[str, Dict[str, Any]] = {}
        self.display_handlers: Dict[str, callable] = {}  # display_id -> handler
        
        # Load topic registry
        self._load_topic_registry()
        logger.info("Initialized RadarEventManager")

    def _load_topic_registry(self):
        """Load topic registry from configuration."""
        from .radar_topic_registry import RADAR_TOPIC_REGISTRY
        self.topic_registry = RADAR_TOPIC_REGISTRY
        logger.info("Loaded topic registry")

    def register_radar_handler(self, radar_type: str, handler: BaseRadarDataHandler):
        """Register radar handler with validation.
        
        Args:
            radar_type (str): Type of radar
            handler (BaseRadarDataHandler): Handler instance
            
        Raises:
            ValueError: If radar type is unknown
        """
        if radar_type not in self.topic_registry:
            raise ValueError(f"Unknown radar type: {radar_type}")
            
        self.handlers[radar_type] = handler
        self.topics[radar_type] = set()
        
        # Subscribe to all topics for this radar type
        for topic_type in ['data_types', 'commands', 'events']:
            for topic in self.topic_registry[radar_type][topic_type]:
                self._subscribe_to_topic(radar_type, topic)
                
        logger.info(f"Registered handler for {radar_type}")

    def _subscribe_to_topic(self, radar_type: str, topic: str):
        """Subscribe handler to topic.
        
        Args:
            radar_type (str): Type of radar
            topic (str): Topic to subscribe to
        """
        try:
            handler = self.handlers[radar_type]
            topic_name = f"{radar_type}_{topic}"
            
            # Subscribe through event bus
            self.event_bus.subscribe(topic_name, handler._handle_event)
            self.topics[radar_type].add(topic)
            
            logger.info(f"Subscribed {radar_type} to topic: {topic}")
            
        except Exception as e:
            logger.error(f"Error subscribing to topic: {e}")
            raise

    async def publish_event(self, radar_type: str, topic: str, data: Dict[str, Any]):
        """Publish radar event.
        
        Args:
            radar_type (str): Type of radar
            topic (str): Event topic
            data (Dict[str, Any]): Event data
        """
        try:
            if radar_type not in self.handlers:
                raise ValueError(f"No handler registered for {radar_type}")
                
            if topic not in self.topics[radar_type]:
                raise ValueError(f"Topic {topic} not registered for {radar_type}")
                
            # Create and publish event
            event = Event(
                topic=f"{radar_type}_{topic}",
                data=data
            )
            self.event_bus.publish(event)
            
            logger.info(f"Published event: {radar_type}_{topic}")
            
        except Exception as e:
            logger.error(f"Error publishing event: {e}")
            raise

    async def subscribe_display(self, radar_type: str, display_id: str, handler: callable):
        """Subscribe display to radar updates.
        
        Args:
            radar_type (str): Type of radar
            display_id (str): Display identifier
            handler (callable): Display update handler
        """
        try:
            if radar_type not in self.handlers:
                raise ValueError(f"No handler registered for {radar_type}")
                
            radar_handler = self.handlers[radar_type]
            
            # Store display handler
            self.display_handlers[display_id] = handler
            
            # Subscribe to display updates topic
            topic_name = f"{radar_type}_display_update"
            self.event_bus.subscribe(topic_name, 
                lambda event: self._handle_display_update(event, display_id))
                
            # Add to handler's subscribed displays
            radar_handler.subscribed_displays.add(display_id)
            
            logger.info(f"Subscribed display {display_id} to {radar_type}")
            
        except Exception as e:
            logger.error(f"Error subscribing display: {e}")
            raise

    async def unsubscribe_display(self, radar_type: str, display_id: str):
        """Unsubscribe display from radar updates.
        
        Args:
            radar_type (str): Type of radar
            display_id (str): Display identifier
        """
        try:
            if radar_type not in self.handlers:
                raise ValueError(f"No handler registered for {radar_type}")
                
            radar_handler = self.handlers[radar_type]
            
            # Remove from subscribed displays
            radar_handler.subscribed_displays.discard(display_id)
            
            # Remove display handler
            self.display_handlers.pop(display_id, None)
            
            # Unsubscribe from event bus
            topic_name = f"{radar_type}_display_update"
            self.event_bus.unsubscribe(topic_name, 
                lambda event: self._handle_display_update(event, display_id))
                
            logger.info(f"Unsubscribed display {display_id} from {radar_type}")
            
        except Exception as e:
            logger.error(f"Error unsubscribing display: {e}")
            raise

    async def _handle_display_update(self, event: Event, display_id: str):
        """Handle display update event.
        
        Args:
            event (Event): Display update event
            display_id (str): Display identifier
        """
        try:
            # Extract radar type from topic
            topic_parts = event.topic.split('_')
            if len(topic_parts) < 2:
                logger.error(f"Invalid topic format: {event.topic}")
                return
                
            radar_type = '_'.join(topic_parts[:2])
            
            # Get handler
            handler = self.handlers.get(radar_type)
            if not handler:
                logger.error(f"No handler for {radar_type}")
                return
                
            # Check if display is still subscribed
            if display_id not in handler.subscribed_displays:
                logger.warning(f"Display {display_id} no longer subscribed")
                return
                
            # Get display handler
            display_handler = self.display_handlers.get(display_id)
            if not display_handler:
                logger.error(f"No handler for display {display_id}")
                return
                
            # Forward update to display
            await display_handler(event.data)
            
        except Exception as e:
            logger.error(f"Error handling display update: {e}")
            raise

    def is_healthy(self) -> bool:
        """Check if manager is healthy.
        
        Returns:
            bool: True if manager is healthy
        """
        try:
            return (
                self.event_bus and 
                self.event_bus.is_running() and
                bool(self.handlers) and
                all(handler.is_healthy() for handler in self.handlers.values())
            )
        except Exception as e:
            logger.error(f"Error checking health: {e}")
            return False

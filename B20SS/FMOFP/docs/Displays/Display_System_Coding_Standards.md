# Display System Coding Standards

## 1. Thread Safety Standards

### 1.1 Thread Verification
```python
# Required pattern for UI operations
if QThread.currentThread() is not QApplication.instance().thread():
    raise RuntimeError("Operation must be performed in main thread")
```

### 1.2 State Changes
```python
# Required pattern for state changes
def set_mode(self, mode: DisplayMode):
    if QThread.currentThread() is not QApplication.instance().thread():
        raise RuntimeError("Display operations must be done in the main thread")
    self.display_mode = mode
    self._safe_update()
```

### 1.3 Safe Updates
```python
def _safe_update(self):
    if self._running and self.isVisible():
        QMetaObject.invokeMethod(self, "update", Qt.ConnectionType.QueuedConnection)
```

## 2. Error Handling Standards

### 2.1 Paint Event Handling
```python
def paintEvent(self, event):
    if not self._running:
        return
        
    painter = QPainter()
    try:
        painter.begin(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.paint_display(painter)
    except Exception as e:
        logger.error(f"Error in paint_display: {str(e)}")
        logger.error(traceback.format_exc())
        self._paint_error = True
        self._error_message = f"Display Error: {str(e)}"
    finally:
        if painter.isActive():
            painter.end()
```

### 2.2 Message Handler Error Handling
```python
def _handle_radar_mode_update(self, data: Dict):
    try:
        radar_type = data.get('radar_type')
        mode = data.get('mode')
        
        if not radar_type or mode is None:
            logger.error("Invalid radar mode update format")
            return
            
        self.radar_data.mode = mode
        self.update()
    except Exception as e:
        logger.error(f"Error handling radar mode update: {str(e)}")
```

## 3. Resource Management

### 3.1 Display Lifecycle
```python
def start(self):
    logger.debug(f"{self.display_type.value}: Starting display")
    self._running = True
    self._update_timer.start()
    self.show()
    self.raise_()
    
def stop(self):
    logger.debug(f"{self.display_type.value}: Stopping display")
    self._running = False
    self._update_timer.stop()
    self.hide()
```

### 3.2 Radar Resource Management
```python
def _setup_radar_handlers(self):
    try:
        if self.radar_handler and self.radar_handler.async_handler:
            self.radar_handler.async_handler.register_handler(
                "radar_mode_update",
                self._handle_radar_mode_update
            )
            logger.info("Radar message handlers registered")
    except Exception as e:
        logger.error(f"Error setting up radar handlers: {str(e)}")
```

## 4. Display Implementation Standards

### 4.1 Window Setup
```python
def setup_display(self):
    self.setWindowFlags(
        Qt.WindowType.Window |
        Qt.WindowType.WindowStaysOnTopHint |
        Qt.WindowType.FramelessWindowHint
    )
    self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
    self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
```

### 4.2 Paint Methods
```python
def paint_display(self, painter: QPainter):
    painter.save()
    try:
        self.draw_title(painter)
        self.draw_menu(painter)
        self.draw_page_content(painter)
    finally:
        painter.restore()
```

## 5. Radar Display Standards

### 5.1 Radar Data Handling
```python
def _get_radar_data(self) -> Dict:
    try:
        if isinstance(self.radar_data.mode, weather_radarMode):
            return {'weather_data': self.radar_data.weather_data}
        elif isinstance(self.radar_data.mode, targeting_radarMode):
            return {'targets': self.radar_data.targets}
        return {}
    except Exception as e:
        logger.error(f"Error getting radar data: {str(e)}")
        return {}
```

### 5.2 Mode Mapping
```python
def _map_radar_mode(self, mode: RadarMode) -> Optional[Enum]:
    try:
        if mode == RadarMode.STANDBY:
            return self._current_radar_type.STANDBY
        elif mode == RadarMode.ACTIVE:
            if self._current_radar_type == weather_radarMode:
                return weather_radarMode.SURVEILLANCE
            # Additional mappings...
    except Exception as e:
        logger.error(f"Error mapping radar mode: {str(e)}")
        return None
```

## 6. Menu Implementation Standards

### 6.1 Menu Drawing
```python
def draw_menu(self, painter: QPainter):
    try:
        menu_rect = self._calculate_menu_rect()
        if self.current_page == DisplayPage.RADAR:
            self._draw_radar_menu(painter, menu_rect)
        else:
            self._draw_main_menu(painter, menu_rect)
    except Exception as e:
        logger.error(f"Error drawing menu: {str(e)}")
```

### 6.2 Menu Interaction
```python
def mousePressEvent(self, event):
    try:
        if event.position().x() < self.menu_width:
            if self.current_page == DisplayPage.RADAR:
                self._handle_radar_menu_click(event)
            else:
                self._handle_main_menu_click(event)
        event.accept()
    except Exception as e:
        logger.error(f"Error handling mouse press: {str(e)}")
```

## 7. Logging Standards

### 7.1 Operation Logging
```python
logger.debug(f"{self.display_type.value}: Setting up display")
logger.info("Display Manager initialized")
logger.error(f"Error in paint_display: {str(e)}")
```

### 7.2 Error Logging
```python
except Exception as e:
    logger.error(f"Error in operation: {str(e)}")
    logger.error(traceback.format_exc())
    raise  # Re-raise if critical

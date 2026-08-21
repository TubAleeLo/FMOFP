class SimulatedRadar:
    def __init__(self, config):
        self.config = config
        self.mode = None
        self.simulated_environment = None
        
    def configure_environment(self, terrain, weather, targets):
        self.simulated_environment = {
            'terrain': terrain,
            'weather': weather,  
            'targets': targets
        }
    
    def get_raw_data(self, radar_mode, beam_position):
        # Subclasses should override this to return simulated raw data  
        # based on the current simulated environment and radar mode/position
        pass
    
    def override_mode(self, mode):
        self.mode = mode
        
"""CI test — SimulatedWeatherRadar unit assertions."""
import sys
sys.path.insert(0, '.')

config = {'azimuth_resolution_deg': 1.0, 'elevation_resolution_deg': 1.0}

from FMOFP.Systems.radarManagement.weather.SimulatedWeatherRadar import Simulatedweather_radar
from FMOFP.Systems.radarManagement.weather.weather_radar import weather_radarMode

radar = Simulatedweather_radar(config)
radar.configure_environment(
    terrain={},
    weather={
        'precipitation_rate_mmh': 10.0,
        'wind_speed_ms': 15.0,
        'wind_direction_deg': 270.0,
        'turbulence_intensity': 0.3,
    },
    targets={}
)

assert radar.get_raw_data(weather_radarMode.STANDBY, (0, 0)) is None, \
    "STANDBY mode should return None"

result = radar.get_raw_data(weather_radarMode.SURVEILLANCE, (45.0, 2.0))
assert result is not None, "Active mode should return data"
dbz, v_r = result
assert isinstance(dbz, float), "Reflectivity must be float"
assert isinstance(v_r, float), "Velocity must be float"
assert 30.0 < dbz < 50.0, f"dBZ out of expected range: {dbz}"

radar2 = Simulatedweather_radar(config)
radar2.configure_environment(terrain={}, weather={}, targets={})
r2 = radar2.get_raw_data(weather_radarMode.SURVEILLANCE, (0, 0))
assert r2 is not None
dbz2, _ = r2
assert dbz2 < 0.0, f"Clear-air dBZ should be negative: {dbz2}"

print("SimulatedWeatherRadar: all assertions passed")

import math
import random

from FMOFP.Systems.radarManagement.SimulatedRadar import SimulatedRadar
from FMOFP.Systems.radarManagement.weather.weather_radar import weather_radarMode


class Simulatedweather_radar(SimulatedRadar):
    """
    Simulated weather radar that produces reflectivity and radial-velocity
    data from a synthetic meteorological environment.

    The environment dict (set via configure_environment) may contain:
        precipitation_rate_mmh  – rain rate in mm/h  (default 0)
        wind_speed_ms           – wind speed in m/s   (default 0)
        wind_direction_deg      – wind direction      (default 0)
        turbulence_intensity    – 0-1 scale           (default 0)

    If no environment has been configured the radar returns (0, 0) for
    every beam position (i.e. clear-air return).
    """

    # Marshall–Palmer Z-R relation constants  (Z = a * R^b)
    _MP_A = 200.0
    _MP_B = 1.6

    def __init__(self, config):
        super().__init__(config)
        self.reflectivity = None
        self.velocity = None
        # Angular resolution from config (degrees per bin)
        self._az_res  = config.get("azimuth_resolution_deg",  1.0) if isinstance(config, dict) else 1.0
        self._el_res  = config.get("elevation_resolution_deg", 1.0) if isinstance(config, dict) else 1.0

    # ------------------------------------------------------------------ #
    # Public interface                                                     #
    # ------------------------------------------------------------------ #

    def get_raw_data(self, radar_mode, beam_position):
        """Return (reflectivity_dBZ, radial_velocity_ms) for the beam position.

        Returns None when the radar is in STANDBY mode or the environment
        has not been configured.
        """
        if radar_mode == weather_radarMode.STANDBY:
            return None

        weather_slice = self._get_weather_slice(beam_position)

        self.reflectivity = self._calculate_reflectivity(weather_slice)
        self.velocity      = self._calculate_velocity(weather_slice)

        return self.reflectivity, self.velocity

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _get_weather_slice(self, beam_position):
        """Extract a 2-D slice of the weather environment for this beam.

        beam_position is a (azimuth_deg, elevation_deg) tuple.
        Returns a dict with the meteorological fields for the slice, or an
        empty dict when no environment has been configured.
        """
        if not self.simulated_environment:
            return {}

        weather = self.simulated_environment.get('weather') or {}
        if not isinstance(weather, dict):
            return {}

        azimuth, elevation = beam_position if beam_position else (0.0, 0.0)

        # Quantise to the radar's angular resolution bins
        az_bin = round(azimuth  / self._az_res) * self._az_res
        el_bin = round(elevation / self._el_res) * self._el_res

        # Apply a simple azimuth-dependent modulation so the precipitation
        # field varies around the beam — avoids a perfectly uniform field.
        az_rad       = math.radians(az_bin)
        el_rad       = math.radians(el_bin)
        spatial_mod  = 0.5 + 0.5 * abs(math.sin(az_rad + el_rad * 0.5))

        precip_rate  = weather.get('precipitation_rate_mmh', 0.0) * spatial_mod
        wind_speed   = weather.get('wind_speed_ms',          0.0)
        wind_dir     = weather.get('wind_direction_deg',     0.0)
        turbulence   = weather.get('turbulence_intensity',   0.0)

        return {
            'precipitation_rate_mmh': max(0.0, precip_rate),
            'wind_speed_ms':          max(0.0, wind_speed),
            'wind_direction_deg':     wind_dir % 360,
            'turbulence_intensity':   max(0.0, min(1.0, turbulence)),
            'azimuth_deg':            az_bin,
            'elevation_deg':          el_bin,
        }

    def _calculate_reflectivity(self, weather_slice):
        """Convert precipitation rate to radar reflectivity in dBZ.

        Uses the Marshall–Palmer Z-R relation:
            Z  = a * R^b     (mm^6 / m^3)
            dBZ = 10 * log10(Z)

        Clear-air returns a nominal noise floor of –32 dBZ.
        Turbulence adds a small positive bias (enhanced clear-air return).
        """
        if not weather_slice:
            return -32.0   # noise floor, no precipitation

        R = weather_slice.get('precipitation_rate_mmh', 0.0)

        if R <= 0.0:
            # Clear-air turbulence still produces a measurable return
            turb = weather_slice.get('turbulence_intensity', 0.0)
            return -32.0 + turb * 8.0   # –32 to –24 dBZ range

        Z    = self._MP_A * (R ** self._MP_B)
        dBZ  = 10.0 * math.log10(max(Z, 1e-6))

        # Add small Gaussian noise to simulate real radar variability
        dBZ += random.gauss(0.0, 0.5)

        return round(dBZ, 2)

    def _calculate_velocity(self, weather_slice):
        """Derive radial (Doppler) velocity in m/s from wind speed and direction.

        The radial component is:
            V_r = V * cos(wind_dir - beam_azimuth)

        Turbulence adds spectral broadening modelled as zero-mean Gaussian noise.
        Returns 0.0 for a clear-air, no-wind slice.
        """
        if not weather_slice:
            return 0.0

        V      = weather_slice.get('wind_speed_ms',        0.0)
        phi    = weather_slice.get('wind_direction_deg',   0.0)
        az     = weather_slice.get('azimuth_deg',          0.0)
        turb   = weather_slice.get('turbulence_intensity', 0.0)

        # Radial component (positive = away from radar)
        angle_diff = math.radians(phi - az)
        V_r        = V * math.cos(angle_diff)

        # Turbulence broadening (spectral noise)
        V_r += random.gauss(0.0, turb * 2.0)

        return round(V_r, 2)

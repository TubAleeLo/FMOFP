"""
Radar-to-Display Bridge
=======================

Provides a direct, synchronous path from all radar data handlers into the
RadarDisplayDataCoordinator that sits inside the UI layer.

WHY THIS EXISTS
---------------
The original flow tried to push radar data back through the MIL-STD-1553B
Remote-Terminal sender (RT → BC direction) and then rely on a chain of async
routing services to land in the coordinator.  That chain has two problems:

1.  The RT sender sends *toward* the Bus Controller, not toward the display.
    Data was never actually arriving at the coordinator.

2.  The VILResponseService → DisplayMessageHandler → MessageRoutingService
    → VILResponseService path creates a message loop that the loop-prevention
    decorators eventually kill, silently dropping the data.

This bridge short-circuits both problems by importing the coordinator directly.
It is intentionally framework-agnostic (no asyncio, no Qt) so it can be called
from any thread.

SUPPORTED RADARS
----------------
Weather  : push_vil_data, push_precipitation_data
Targeting: push_targeting_data
SAR      : push_sar_data
TFR      : push_tfr_data
AEWC     : push_aewc_data

All push functions accept either typed radar message objects or plain dicts.
"""

import time
import traceback
from typing import Any, List

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_coordinator():
    """Lazily import and return the RadarDisplayDataCoordinator singleton."""
    try:
        from FMOFP.Interfaces.userInterface.displays.radar.radar_display_data_coordinator import (
            get_radar_display_data_coordinator,
        )
        return get_radar_display_data_coordinator()
    except Exception as exc:
        logger.error(f"[BRIDGE] Cannot import RadarDisplayDataCoordinator: {exc}")
        return None


def _object_to_dict(item: Any, data_type: str) -> dict:
    """
    Convert a data object (WeatherRadarVILData, PrecipitationData, or plain
    dict) to the dictionary format expected by the coordinator.
    """
    if isinstance(item, dict):
        return item  # already the right format

    d: dict = {}

    # --- position ---
    if hasattr(item, "position"):
        pos = item.position
        if hasattr(pos, "tolist"):
            d["position"] = tuple(pos.tolist())
        elif isinstance(pos, (list, tuple)) and len(pos) >= 2:
            d["position"] = tuple(pos)
        else:
            d["position"] = (0.0, 0.0)
    elif hasattr(item, "x") and hasattr(item, "y"):
        d["position"] = (float(item.x), float(item.y))
    else:
        d["position"] = (0.0, 0.0)

    # --- id ---
    if hasattr(item, "id") and item.id:
        d["id"] = item.id
    elif hasattr(item, "request_id") and item.request_id:
        d["id"] = item.request_id

    # --- timestamp ---
    d["timestamp"] = getattr(item, "timestamp", time.time())

    # --- type-specific fields ---
    if data_type == "vil":
        d["value"] = float(getattr(item, "value", 0.0))
        d["layer_count"] = int(getattr(item, "layer_count", 1))
        d["intensity"] = float(getattr(item, "intensity", 0.5))
        d["show_values"] = bool(getattr(item, "show_values", True))

    elif data_type == "precipitation":
        raw_type = getattr(item, "type", None) or getattr(item, "precip_type", "rain")
        d["type"] = raw_type
        d["precip_type"] = raw_type
        d["rate"] = float(getattr(item, "rate", 0.0))
        d["intensity"] = float(getattr(item, "intensity", 0.5))
        d["show_values"] = bool(getattr(item, "show_values", True))

    return d


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def push_vil_data(vil_objects: List[Any], request_id: str) -> bool:
    """
    Push a list of VIL data objects/dicts directly into the display coordinator.

    Args:
        vil_objects:  List of WeatherRadarVILData instances or dicts.
        request_id:   The originating request UUID (required by coordinator).

    Returns:
        True if at least one item was stored, False otherwise.
    """
    if not vil_objects:
        logger.warning("[BRIDGE] push_vil_data called with empty list — nothing to store")
        return False

    if not request_id:
        logger.error("[BRIDGE] push_vil_data called without request_id — cannot store")
        return False

    coordinator = _get_coordinator()
    if coordinator is None:
        return False

    try:
        # Convert objects to dicts and stamp IDs
        processed = []
        for i, item in enumerate(vil_objects):
            d = _object_to_dict(item, "vil")
            if "id" not in d or not d["id"]:
                d["id"] = f"{request_id}_{i}"
            processed.append(d)

        count = coordinator.store_data("vil", processed, request_id)
        logger.info(f"[BRIDGE] Stored {count} VIL items for request {request_id}")
        return count > 0

    except Exception as exc:
        logger.error(f"[BRIDGE] Error pushing VIL data: {exc}")
        logger.error(traceback.format_exc())
        return False


def push_precipitation_data(precip_objects: List[Any], request_id: str) -> bool:
    """
    Push a list of precipitation data objects/dicts directly into the display
    coordinator.

    Args:
        precip_objects:  List of PrecipitationData instances or dicts.
        request_id:      The originating request UUID (required by coordinator).

    Returns:
        True if at least one item was stored, False otherwise.
    """
    if not precip_objects:
        logger.warning("[BRIDGE] push_precipitation_data called with empty list — nothing to store")
        return False

    if not request_id:
        logger.error("[BRIDGE] push_precipitation_data called without request_id — cannot store")
        return False

    coordinator = _get_coordinator()
    if coordinator is None:
        return False

    try:
        processed = []
        for i, item in enumerate(precip_objects):
            d = _object_to_dict(item, "precipitation")
            if "id" not in d or not d["id"]:
                d["id"] = f"{request_id}_{i}"
            processed.append(d)

        count = coordinator.store_data("precipitation", processed, request_id)
        logger.info(f"[BRIDGE] Stored {count} precipitation items for request {request_id}")
        return count > 0

    except Exception as exc:
        logger.error(f"[BRIDGE] Error pushing precipitation data: {exc}")
        logger.error(traceback.format_exc())
        return False


# ---------------------------------------------------------------------------
# Targeting Radar
# ---------------------------------------------------------------------------

def push_targeting_data(targets: List[Any], request_id: str) -> bool:
    """
    Push targeting radar track/lock data directly into the display coordinator.

    The display widget (TargetingRadarDisplay) expects items of the form:
        {'position': (x, y, z), 'velocity': (vx, vy, vz),
         'identity': str, 'classification': str, 'confidence': float,
         'target_id': str, 'id': str}

    Args:
        targets:     List of TargetingRadarTrackData / TargetingRadarLockData
                     instances, or plain dicts with the required keys.
        request_id:  Originating request UUID.

    Returns:
        True if at least one item was stored, False otherwise.
    """
    if not targets:
        logger.warning("[BRIDGE] push_targeting_data called with empty list")
        return False
    if not request_id:
        logger.error("[BRIDGE] push_targeting_data called without request_id")
        return False

    coordinator = _get_coordinator()
    if coordinator is None:
        return False

    try:
        processed = []
        for i, item in enumerate(targets):
            if isinstance(item, dict):
                d = dict(item)
            else:
                d = {}
                # Position — 3-D for targeting
                pos = getattr(item, "target_position", None) or getattr(item, "position", None)
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    d["position"] = tuple(pos)
                else:
                    d["position"] = (0.0, 0.0, 0.0)

                vel = getattr(item, "target_velocity", None) or getattr(item, "velocity", None)
                if isinstance(vel, (list, tuple)) and len(vel) >= 3:
                    d["velocity"] = tuple(vel)
                else:
                    d["velocity"] = (0.0, 0.0, 0.0)

                d["target_id"]      = str(getattr(item, "target_id", "") or "")
                d["identity"]       = str(getattr(item, "identity", "UNKNOWN"))
                d["classification"] = str(getattr(item, "classification", "UNKNOWN"))
                d["confidence"]     = float(getattr(item, "confidence", 1.0))
                d["lock_status"]    = str(getattr(item, "lock_status", ""))
                d["timestamp"]      = getattr(item, "timestamp", time.time())

            # Ensure ID
            if "id" not in d or not d["id"]:
                d["id"] = f"{request_id}_{i}"

            processed.append(d)

        count = coordinator.store_data("targeting", processed, request_id)
        logger.info(f"[BRIDGE] Stored {count} targeting items for request {request_id}")
        return count > 0

    except Exception as exc:
        logger.error(f"[BRIDGE] Error pushing targeting data: {exc}")
        logger.error(traceback.format_exc())
        return False


# ---------------------------------------------------------------------------
# SAR Radar
# ---------------------------------------------------------------------------

def push_sar_data(imagery_objects: List[Any], request_id: str) -> bool:
    """
    Push SAR imagery data directly into the display coordinator.

    The display widget (SARRadarDisplay) expects items of the form:
        {'image_data': list|ndarray, 'image_shape': tuple,
         'resolution': float, 'geo_reference': dict, 'id': str}

    Args:
        imagery_objects:  List of SARRadarImagery instances or dicts.
        request_id:       Originating request UUID.

    Returns:
        True if at least one item was stored, False otherwise.
    """
    if not imagery_objects:
        logger.warning("[BRIDGE] push_sar_data called with empty list")
        return False
    if not request_id:
        logger.error("[BRIDGE] push_sar_data called without request_id")
        return False

    coordinator = _get_coordinator()
    if coordinator is None:
        return False

    try:
        processed = []
        for i, item in enumerate(imagery_objects):
            if isinstance(item, dict):
                d = dict(item)
            else:
                d = {}
                # Convert numpy image to list so it survives deepcopy in coordinator
                img = getattr(item, "image_data", None)
                if hasattr(img, "tolist"):
                    d["image_data"] = img.tolist()
                else:
                    d["image_data"] = img or []

                shape = getattr(item, "image_shape", None)
                d["image_shape"]   = tuple(shape) if shape else (0, 0)
                d["resolution"]    = float(getattr(item, "resolution", 1.0))
                d["geo_reference"] = getattr(item, "geo_reference", {}) or {}
                d["image_uuid"]    = str(getattr(item, "image_uuid", ""))
                d["timestamp"]     = getattr(item, "timestamp", time.time())
                # SAR items have no meaningful 2-D position — use origin as sentinel
                d["position"]      = (0.0, 0.0)

            if "id" not in d or not d["id"]:
                d["id"] = f"{request_id}_{i}"

            processed.append(d)

        count = coordinator.store_data("sar", processed, request_id)
        logger.info(f"[BRIDGE] Stored {count} SAR items for request {request_id}")
        return count > 0

    except Exception as exc:
        logger.error(f"[BRIDGE] Error pushing SAR data: {exc}")
        logger.error(traceback.format_exc())
        return False


# ---------------------------------------------------------------------------
# TFR Radar
# ---------------------------------------------------------------------------

def push_tfr_data(tfr_objects: List[Any], request_id: str) -> bool:
    """
    Push TFR elevation-profile / terrain-warning data into the display coordinator.

    The display widget (TFRRadarDisplay) expects items of the form:
        {'elevation': float, 'distance': float,
         'warning_type': str|None, 'id': str}

    Each TFRRadarElevationProfile is expanded into one dict per point.
    Each TFRRadarTerrainWarning is stored as a single dict.

    Args:
        tfr_objects:  List of TFRRadarElevationProfile / TFRRadarTerrainWarning
                      instances, or pre-expanded dicts.
        request_id:   Originating request UUID.

    Returns:
        True if at least one item was stored, False otherwise.
    """
    if not tfr_objects:
        logger.warning("[BRIDGE] push_tfr_data called with empty list")
        return False
    if not request_id:
        logger.error("[BRIDGE] push_tfr_data called without request_id")
        return False

    coordinator = _get_coordinator()
    if coordinator is None:
        return False

    try:
        processed = []
        idx = 0
        for item in tfr_objects:
            if isinstance(item, dict):
                d = dict(item)
                if "id" not in d or not d["id"]:
                    d["id"] = f"{request_id}_{idx}"
                # Ensure position exists for coordinator validation
                if "position" not in d:
                    dist = d.get("distance", float(idx))
                    elev = d.get("elevation", 0.0)
                    d["position"] = (float(dist), float(elev))
                processed.append(d)
                idx += 1
            elif hasattr(item, "profile_data"):
                # TFRRadarElevationProfile — expand into one dict per point
                for dist, elev in (item.profile_data or []):
                    d = {
                        "distance":     float(dist),
                        "elevation":    float(elev),
                        "warning_type": None,
                        "scan_width":   float(getattr(item, "scan_width", 0.0)),
                        "position":     (float(dist), float(elev)),
                        "timestamp":    getattr(item, "timestamp", time.time()),
                        "id":           f"{request_id}_{idx}",
                    }
                    processed.append(d)
                    idx += 1
            elif hasattr(item, "warning_type"):
                # TFRRadarTerrainWarning — single entry
                dist = float(getattr(item, "distance", 0.0))
                elev = float(getattr(item, "elevation", 0.0))
                d = {
                    "distance":     dist,
                    "elevation":    elev,
                    "warning_type": str(getattr(item, "warning_type", "")),
                    "position":     (dist, elev),
                    "timestamp":    getattr(item, "timestamp", time.time()),
                    "id":           f"{request_id}_{idx}",
                }
                processed.append(d)
                idx += 1

        if not processed:
            logger.warning("[BRIDGE] push_tfr_data produced no processable items")
            return False

        count = coordinator.store_data("tfr", processed, request_id)
        logger.info(f"[BRIDGE] Stored {count} TFR items for request {request_id}")
        return count > 0

    except Exception as exc:
        logger.error(f"[BRIDGE] Error pushing TFR data: {exc}")
        logger.error(traceback.format_exc())
        return False


# ---------------------------------------------------------------------------
# AEWC Radar
# ---------------------------------------------------------------------------

def push_aewc_data(aewc_objects: List[Any], request_id: str) -> bool:
    """
    Push AEWC track / sector-scan data into the display coordinator.

    The display widget (AEWCRadarDisplay) expects items of the form:
        {'position': (x, y, z), 'velocity': (vx, vy, vz),
         'track_type': str, 'track_confidence': float,
         'track_id': str, 'sector_id': str|None, 'id': str}

    AEWCRadarTrackData objects may carry multiple positions (track history);
    the most recent position is used as the primary location.

    Args:
        aewc_objects:  List of AEWCRadarTrackData / AEWCRadarSectorScan
                       instances, or plain dicts.
        request_id:    Originating request UUID.

    Returns:
        True if at least one item was stored, False otherwise.
    """
    if not aewc_objects:
        logger.warning("[BRIDGE] push_aewc_data called with empty list")
        return False
    if not request_id:
        logger.error("[BRIDGE] push_aewc_data called without request_id")
        return False

    coordinator = _get_coordinator()
    if coordinator is None:
        return False

    try:
        processed = []
        for i, item in enumerate(aewc_objects):
            if isinstance(item, dict):
                d = dict(item)
            else:
                d = {}
                if hasattr(item, "track_positions"):
                    # AEWCRadarTrackData — use most recent position
                    positions = item.track_positions or []
                    velocities = getattr(item, "track_velocities", []) or []
                    pos = tuple(positions[-1]) if positions else (0.0, 0.0, 0.0)
                    vel = tuple(velocities[-1]) if velocities else (0.0, 0.0, 0.0)
                    d["position"]         = pos
                    d["velocity"]         = vel
                    d["track_positions"]  = [tuple(p) for p in positions]
                    d["track_velocities"] = [tuple(v) for v in velocities]
                    d["track_timestamps"] = list(getattr(item, "track_timestamps", []) or [])
                    d["track_id"]         = str(getattr(item, "track_id", "") or "")
                    d["track_type"]       = str(getattr(item, "track_type", "UNKNOWN"))
                    d["track_confidence"] = float(getattr(item, "track_confidence", 1.0))
                    d["sector_id"]        = None
                elif hasattr(item, "sector_data"):
                    # AEWCRadarSectorScan — store metadata; raw data as list
                    sector_d = getattr(item, "sector_data", None)
                    if hasattr(sector_d, "tolist"):
                        sector_d = sector_d.tolist()
                    d["sector_data"]   = sector_d or []
                    d["sector_bounds"] = getattr(item, "sector_bounds", {}) or {}
                    d["scan_resolution"] = float(getattr(item, "scan_resolution", 1.0))
                    d["scan_uuid"]     = str(getattr(item, "scan_uuid", ""))
                    d["position"]      = (0.0, 0.0, 0.0)
                    d["sector_id"]     = str(getattr(item, "scan_uuid", ""))
                else:
                    d["position"] = (0.0, 0.0, 0.0)

                d["timestamp"] = getattr(item, "timestamp", time.time())

            if "id" not in d or not d["id"]:
                d["id"] = f"{request_id}_{i}"
            # Ensure 2-D position exists for coordinator (uses first two components)
            if "position" not in d:
                d["position"] = (0.0, 0.0)

            processed.append(d)

        count = coordinator.store_data("aewc", processed, request_id)
        logger.info(f"[BRIDGE] Stored {count} AEWC items for request {request_id}")
        return count > 0

    except Exception as exc:
        logger.error(f"[BRIDGE] Error pushing AEWC data: {exc}")
        logger.error(traceback.format_exc())
        return False


# ---------------------------------------------------------------------------
# Storm Cell data
# ---------------------------------------------------------------------------

def push_cells_data(cell_objects, request_id: str) -> bool:
    """
    Push storm cell data directly into the display coordinator.

    The display widget and CellDataProcessor expect items of the form:
        {'position': (x, y), 'intensity': float, 'size': float,
         'reflectivity': float, 'velocity': (vx, vy),
         'cell_id': int, 'id': str}

    Args:
        cell_objects:  List of StormCell dataclass instances (from StormCellTracker)
                       or plain dicts with the required keys.
        request_id:    Originating request UUID.

    Returns:
        True if at least one item was stored, False otherwise.
    """
    if not cell_objects:
        logger.warning("[BRIDGE] push_cells_data called with empty list — nothing to store")
        return False

    if not request_id:
        logger.error("[BRIDGE] push_cells_data called without request_id — cannot store")
        return False

    coordinator = _get_coordinator()
    if coordinator is None:
        return False

    try:
        processed = []
        for i, item in enumerate(cell_objects):
            if isinstance(item, dict):
                d = dict(item)
            else:
                # StormCell dataclass from stormCellTracking.py
                pos = getattr(item, "position", None)
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    d = {"position": (float(pos[0]), float(pos[1]))}
                else:
                    d = {"position": (0.0, 0.0)}

                vel = getattr(item, "velocity", (0.0, 0.0))
                if isinstance(vel, (list, tuple)) and len(vel) >= 2:
                    d["velocity"] = (float(vel[0]), float(vel[1]))
                else:
                    d["velocity"] = (0.0, 0.0)

                d["cell_id"]           = int(getattr(item, "cell_id", i))
                d["reflectivity"]      = float(getattr(item, "reflectivity", 0.0))
                d["intensity"]         = float(getattr(item, "intensity", 0.0))
                d["size"]              = float(getattr(item, "size", 1.0))
                d["altitude"]          = float(getattr(item, "altitude", 0.0))
                d["vertical_development"] = float(
                    getattr(item, "vertical_development", 0.0))
                d["timestamp"]         = getattr(item, "last_update", time.time())

            if "id" not in d or not d["id"]:
                d["id"] = f"{request_id}_{i}"

            processed.append(d)

        count = coordinator.store_data("cells", processed, request_id)
        logger.info(f"[BRIDGE] Stored {count} storm cell items for request {request_id}")
        return count > 0

    except Exception as exc:
        logger.error(f"[BRIDGE] Error pushing cells data: {exc}")
        logger.error(traceback.format_exc())
        return False


def push_windshear_data(event_dicts: list, request_id: str) -> bool:
    """
    Push WindShearEvent data into the display coordinator ('windshear' store).

    Each item should be a dict with keys:
        position (x_nm, y_nm), intensity (0-1), shear_knots (float),
        severity ('LOW'|'MODERATE'|'SEVERE'), is_microburst (bool),
        altitude_ft (float), event_id (int)

    Args:
        event_dicts: List of wind-shear event dicts (from _process_windshear_data).
        request_id:  Originating request UUID.

    Returns:
        True if at least one item was stored, False otherwise.
    """
    if not event_dicts:
        logger.debug("[BRIDGE] push_windshear_data called with empty list — nothing to store")
        return False

    if not request_id:
        logger.error("[BRIDGE] push_windshear_data called without request_id")
        return False

    coordinator = _get_coordinator()
    if coordinator is None:
        return False

    try:
        processed = []
        for i, item in enumerate(event_dicts):
            d = dict(item) if isinstance(item, dict) else {}
            if "position" not in d:
                d["position"] = (0.0, 0.0)
            if "id" not in d or not d["id"]:
                d["id"] = f"ws_{request_id}_{i}"
            processed.append(d)

        count = coordinator.store_data("windshear", processed, request_id)
        logger.info(f"[BRIDGE] Stored {count} wind-shear events for request {request_id}")
        return count > 0

    except Exception as exc:
        logger.error(f"[BRIDGE] Error pushing wind-shear data: {exc}")
        logger.error(traceback.format_exc())
        return False


def push_turbulence_data(cell_dicts: list, request_id: str) -> bool:
    """
    Push TurbulenceCell data into the display coordinator ('turbulence' store).

    Each item should be a dict with keys:
        position (x_nm, y_nm), intensity (0-1 EDR proxy), category
        ('LIGHT'|'MODERATE'|'SEVERE'|'EXTREME'), altitude_ft (float), cell_id (int)

    Args:
        cell_dicts: List of turbulence cell dicts (from _process_turbulence_data).
        request_id: Originating request UUID.

    Returns:
        True if at least one item was stored, False otherwise.
    """
    if not cell_dicts:
        logger.debug("[BRIDGE] push_turbulence_data called with empty list — nothing to store")
        return False

    if not request_id:
        logger.error("[BRIDGE] push_turbulence_data called without request_id")
        return False

    coordinator = _get_coordinator()
    if coordinator is None:
        return False

    try:
        processed = []
        for i, item in enumerate(cell_dicts):
            d = dict(item) if isinstance(item, dict) else {}
            if "position" not in d:
                d["position"] = (0.0, 0.0)
            if "id" not in d or not d["id"]:
                d["id"] = f"turb_{request_id}_{i}"
            processed.append(d)

        count = coordinator.store_data("turbulence", processed, request_id)
        logger.info(f"[BRIDGE] Stored {count} turbulence cells for request {request_id}")
        return count > 0

    except Exception as exc:
        logger.error(f"[BRIDGE] Error pushing turbulence data: {exc}")
        logger.error(traceback.format_exc())
        return False


def push_windshear_data(event_dicts: list, request_id: str) -> bool:
    """
    Push WindShearEvent data into the display coordinator ('windshear' store).

    Each item should be a dict with keys:
        position (x_nm, y_nm), intensity (0-1), shear_knots (float),
        severity ('LOW'|'MODERATE'|'SEVERE'), is_microburst (bool),
        altitude_ft (float), event_id (int)
    """
    if not event_dicts:
        logger.debug("[BRIDGE] push_windshear_data: empty list")
        return False
    if not request_id:
        logger.error("[BRIDGE] push_windshear_data: missing request_id")
        return False
    coordinator = _get_coordinator()
    if coordinator is None:
        return False
    try:
        processed = []
        for i, item in enumerate(event_dicts):
            d = dict(item) if isinstance(item, dict) else {}
            if "position" not in d:
                d["position"] = (0.0, 0.0)
            if "id" not in d or not d["id"]:
                d["id"] = f"ws_{request_id}_{i}"
            processed.append(d)
        count = coordinator.store_data("windshear", processed, request_id)
        logger.info(f"[BRIDGE] Stored {count} wind-shear events for request {request_id}")
        return count > 0
    except Exception as exc:
        logger.error(f"[BRIDGE] Error pushing wind-shear data: {exc}")
        logger.error(traceback.format_exc())
        return False


def push_turbulence_data(cell_dicts: list, request_id: str) -> bool:
    """
    Push TurbulenceCell data into the display coordinator ('turbulence' store).

    Each item should be a dict with keys:
        position (x_nm, y_nm), intensity (0-1 EDR proxy),
        category ('LIGHT'|'MODERATE'|'SEVERE'|'EXTREME'), altitude_ft, cell_id
    """
    if not cell_dicts:
        logger.debug("[BRIDGE] push_turbulence_data: empty list")
        return False
    if not request_id:
        logger.error("[BRIDGE] push_turbulence_data: missing request_id")
        return False
    coordinator = _get_coordinator()
    if coordinator is None:
        return False
    try:
        processed = []
        for i, item in enumerate(cell_dicts):
            d = dict(item) if isinstance(item, dict) else {}
            if "position" not in d:
                d["position"] = (0.0, 0.0)
            if "id" not in d or not d["id"]:
                d["id"] = f"turb_{request_id}_{i}"
            processed.append(d)
        count = coordinator.store_data("turbulence", processed, request_id)
        logger.info(f"[BRIDGE] Stored {count} turbulence cells for request {request_id}")
        return count > 0
    except Exception as exc:
        logger.error(f"[BRIDGE] Error pushing turbulence data: {exc}")
        logger.error(traceback.format_exc())
        return False

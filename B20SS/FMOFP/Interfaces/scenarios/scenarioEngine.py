"""
Scenario Engine

Parses and executes XML scenario files, injecting events into live systems
at defined times or trigger conditions.

Supports:
  - Training scenarios  (trainingScenario.xml)
  - Failure scenarios   (failureScenario.xml)
  - Custom scenario XML (any well-formed file)

Event types:
  radar_contact   — inject a threat into RadarDataFusion
  system_failure  — flag a component as failed
  weather_cell    — inject a precipitation / turbulence cell
  threat_launch   — trigger RWR contact
  waypoint        — add a mission waypoint
  message         — log an instructor message
  phase_change    — advance mission phase

Usage:
  engine = get_scenario_engine()
  engine.load('trainingScenario.xml')
  engine.start()
  engine.stop()

Singleton: get_scenario_engine()
"""

import os
import threading
import time
import uuid
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from FMOFP.Utils.logger.sys_logger import get_logger
import FMOFP.Utils.common.fetching as fetching

logger = get_logger()

_scenario_engine = None

SCENARIO_DIR = os.path.join(
    fetching.fetch_fmofp_path(), 'Interfaces', 'scenarios'
)


# ── Event dataclass ──────────────────────────────────────────────────────────

@dataclass
class ScenarioEvent:
    event_id:   str
    event_type: str
    trigger_s:  float          # seconds after scenario start
    params:     Dict[str, Any] = field(default_factory=dict)
    fired:      bool = False


# ── Engine ───────────────────────────────────────────────────────────────────

class ScenarioEngine:

    def __init__(self):
        self._lock    = threading.Lock()
        self._running = threading.Event()
        self._thread  = None

        self._events:   List[ScenarioEvent] = []
        self._start_ts: Optional[float]     = None
        self._name:     str                 = ""
        self._log:      List[Dict]          = []   # event replay log

    # ------------------------------------------------------------------ load

    def load(self, filename: str) -> bool:
        """
        Load a scenario XML file by name (looked up in the scenarios directory)
        or by absolute path.
        """
        if not os.path.isabs(filename):
            path = os.path.join(SCENARIO_DIR, filename)
        else:
            path = filename

        if not os.path.exists(path):
            logger.error(f"[SCENARIO] File not found: {path}")
            return False

        try:
            tree = ET.parse(path)
            root = tree.getroot()
            events = self._parse(root)
            with self._lock:
                self._events  = sorted(events, key=lambda e: e.trigger_s)
                self._name    = root.get('name', os.path.basename(path))
                self._log     = []
            logger.info(f"[SCENARIO] Loaded '{self._name}' — {len(events)} events")
            return True
        except Exception as e:
            logger.error(f"[SCENARIO] Parse error for {path}: {e}")
            return False

    def _parse(self, root: ET.Element) -> List[ScenarioEvent]:
        """Convert XML elements to ScenarioEvent objects."""
        events: List[ScenarioEvent] = []

        for elem in root.findall('.//event'):
            try:
                eid   = elem.get('id', str(uuid.uuid4())[:8])
                etype = elem.get('type', 'message')
                t_s   = float(elem.get('time_s', '0'))
                params: Dict[str, Any] = {}
                for child in elem:
                    # Try numeric conversion; fall back to string
                    text = child.text or ""
                    try:
                        params[child.tag] = float(text) if '.' in text else int(text)
                    except ValueError:
                        params[child.tag] = text
                events.append(ScenarioEvent(eid, etype, t_s, params))
            except Exception as e:
                logger.warning(f"[SCENARIO] Skipping malformed event: {e}")

        return events

    # ------------------------------------------------------------------ run

    def _dispatch(self, event: ScenarioEvent):
        """Fire a single event into the appropriate live system."""
        logger.info(
            f"[SCENARIO] T+{event.trigger_s:.0f}s  [{event.event_type}]  "
            f"id={event.event_id}  params={event.params}"
        )
        self._log.append({
            'ts': time.time(), 'event_id': event.event_id,
            'event_type': event.event_type, 'params': event.params
        })

        try:
            if event.event_type == 'radar_contact':
                self._inject_radar_contact(event.params)
            elif event.event_type == 'threat_launch':
                self._inject_threat(event.params)
            elif event.event_type == 'weather_cell':
                self._inject_weather(event.params)
            elif event.event_type == 'waypoint':
                self._inject_waypoint(event.params)
            elif event.event_type == 'phase_change':
                self._inject_phase(event.params)
            elif event.event_type == 'system_failure':
                self._inject_failure(event.params)
            elif event.event_type == 'message':
                msg = event.params.get('text', event.params.get('message', ''))
                logger.info(f"[SCENARIO] INSTRUCTOR: {msg}")
            else:
                logger.warning(f"[SCENARIO] Unknown event type: {event.event_type}")
        except Exception as e:
            logger.error(f"[SCENARIO] Dispatch error for {event.event_id}: {e}")

    # ---- injectors ----

    def _inject_radar_contact(self, p: Dict):
        try:
            # RadarDataFusion is a pull-based system: it has no external
            # ingestion API (there is no ingest_targeting_data method).
            # It pulls from RadarManagementSystem.radars[*].current_targets
            # on each fusion epoch, so a scenario contact must be written
            # into a radar's current_targets table to actually show up.
            from FMOFP.Systems.radarManagement.radarControl import (
                get_radar_management_system,
            )
            ctrl = get_radar_management_system()
            radars = getattr(ctrl, "radars", {})
            radar_name = next(
                (name for name in radars
                 if "targeting" in name or "aewc" in name),
                None,
            )
            if radar_name is None:
                logger.debug(
                    "[SCENARIO] radar_contact inject skipped: "
                    "no targeting/aewc radar available"
                )
                return

            track_id = p.get('track_id', str(uuid.uuid4())[:6])
            radars[radar_name].current_targets[track_id] = {
                'position':       (p.get('x', 50.0), p.get('y', 50.0), p.get('alt_ft', 20000.0)),
                'velocity':       (p.get('vx', 0.0), p.get('vy', 0.0), p.get('vz', 0.0)),
                'classification': p.get('classification', 'UNKNOWN'),
                'identity':       p.get('identity', 'UNKNOWN'),
                'rcs':            float(p.get('rcs', 5.0)),
                'is_stealth':     bool(p.get('is_stealth', False)),
                'last_update':    time.time(),
            }
            logger.debug(f"[SCENARIO] Injected radar contact: {track_id} into {radar_name}")
        except Exception as e:
            logger.debug(f"[SCENARIO] radar_contact inject error: {e}")

    def _inject_threat(self, p: Dict):
        try:
            from FMOFP.Systems.defensiveSys.defensiveService import get_defensive_service
            dfs = get_defensive_service()
            # Directly add to RWR contact table
            from FMOFP.Systems.defensiveSys.defensiveService import RWRContact
            cid = f"SCEN-{p.get('name', 'THR')}"
            contact = RWRContact(
                contact_id  = cid,
                bearing_deg = float(p.get('bearing_deg', 0)),
                range_nm    = float(p.get('range_nm', 30)),
                band        = p.get('band', 'X'),
                threat_type = p.get('threat_type', 'SAM'),
                priority    = int(p.get('priority', 1)),
                hostile     = True,
            )
            with dfs._lock:
                dfs._contacts[cid] = contact
            logger.debug(f"[SCENARIO] Injected threat: {cid}")
        except Exception as e:
            logger.debug(f"[SCENARIO] threat_launch inject error: {e}")

    def _inject_weather(self, p: Dict):
        try:
            from FMOFP.local_messaging.routing.radar_to_display_bridge import push_cells_data
            cell = {
                'position':   (float(p.get('x', 0)), float(p.get('y', 0))),
                'intensity':  float(p.get('intensity', 0.7)),
                'reflectivity': float(p.get('reflectivity', 45)),
                'size':       float(p.get('size', 5.0)),
                'velocity':   (0.0, 0.0),
                'cell_id':    0,
                'category':   p.get('category', 'MODERATE'),
            }
            push_cells_data([cell], str(uuid.uuid4()))
            logger.debug("[SCENARIO] Injected weather cell")
        except Exception as e:
            logger.debug(f"[SCENARIO] weather_cell inject error: {e}")

    def _inject_waypoint(self, p: Dict):
        try:
            from FMOFP.Systems.missionPlanning.missionService import get_mission_service
            ms = get_mission_service()
            ms.add_waypoint(
                lat    = float(p.get('lat', 35.0)),
                lon    = float(p.get('lon', -97.0)),
                alt_ft = float(p.get('alt_ft', 10000)),
                name   = p.get('name', 'WP'),
            )
            logger.debug(f"[SCENARIO] Injected waypoint: {p.get('name')}")
        except Exception as e:
            logger.debug(f"[SCENARIO] waypoint inject error: {e}")

    def _inject_phase(self, p: Dict):
        try:
            from FMOFP.Systems.missionPlanning.missionService import get_mission_service
            get_mission_service().set_phase(p.get('phase', 'INGRESS'))
        except Exception as e:
            logger.debug(f"[SCENARIO] phase_change inject error: {e}")

    def _inject_failure(self, p: Dict):
        # Intentionally log-only. Investigated wiring this into
        # Systems/avionics/hardwareHealth/LRUstatus.py's LRUStatusMonitor
        # (the closest thing to a "system health" registry in this
        # codebase) during the August 2026 audit: its LRU.health field is
        # unconditionally recomputed from each subsystem's own live
        # get_status() on every poll cycle (_poll_lru(), running
        # continuously at POLL_HZ) — there is no override hook, so
        # directly setting .health here would just get silently
        # overwritten on the next poll tick, at most a fraction of a
        # second later. Building a real "forced fault" override that
        # _poll_lru() respects is a legitimate follow-up feature, but is
        # new functionality (not a broken call to fix) and was judged
        # out of scope for that pass. Until then, "system_failure"
        # scenario events are instructor-visible log messages only and
        # do not affect any live system state.
        system = p.get('system', 'unknown')
        logger.warning(f"[SCENARIO] SIMULATED FAILURE: {system} — {p.get('description', '')}")

    # ------------------------------------------------------------------ loop

    def _update_loop(self):
        logger.info(f"[SCENARIO] Running '{self._name}'")
        self._start_ts = time.time()

        while not self._running.is_set():
            elapsed = time.time() - self._start_ts
            fired_any = False

            with self._lock:
                for event in self._events:
                    if not event.fired and elapsed >= event.trigger_s:
                        event.fired = True
                        fired_any   = True
                        self._dispatch(event)

                all_fired = all(e.fired for e in self._events)

            if all_fired and self._events:
                logger.info(f"[SCENARIO] '{self._name}' complete — all events fired")
                break

            time.sleep(0.1)

        logger.info("[SCENARIO] Engine loop exited")

    # ------------------------------------------------------------------ public API

    def start(self):
        if self._thread and self._thread.is_alive():
            logger.warning("[SCENARIO] Already running")
            return
        if not self._events:
            logger.warning("[SCENARIO] No events loaded — call load() first")
            return
        self._running.clear()
        # Reset fired flags
        with self._lock:
            for e in self._events:
                e.fired = False
        self._thread = threading.Thread(
            target=self._update_loop, daemon=True, name="SCENARIO_Engine")
        self._thread.start()
        logger.info("[SCENARIO] Scenario engine started")

    def stop(self):
        self._running.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("[SCENARIO] Scenario engine stopped")

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            fired = sum(1 for e in self._events if e.fired)
            total = len(self._events)
            elapsed = (time.time() - self._start_ts) if self._start_ts else 0
        return {
            'running':       self._thread is not None and self._thread.is_alive(),
            'scenario_name': self._name,
            'events_total':  total,
            'events_fired':  fired,
            'elapsed_s':     round(elapsed, 1),
            'log':           list(self._log),
        }

    def get_log(self) -> List[Dict]:
        with self._lock:
            return list(self._log)


def get_scenario_engine() -> ScenarioEngine:
    global _scenario_engine
    if _scenario_engine is None:
        _scenario_engine = ScenarioEngine()
    return _scenario_engine

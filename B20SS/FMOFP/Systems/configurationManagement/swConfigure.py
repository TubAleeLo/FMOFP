import sys
import FMOFP.Utils.common.fetching as fetching
import os
import xml.etree.ElementTree as ET
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

_swcm_instance = None

# swcmConfig.xml lives alongside this file. The previous relative path,
# "Systems/configurationManagement/swcmConfig.xml", was missing the "FMOFP/" segment (only
# B20SS/FMOFP/Systems/... exists, not B20SS/Systems/...), so it raised
# FileNotFoundError on every construction -- and this class isn't
# currently instantiated anywhere in the codebase, so the bug was
# entirely latent (production readiness reanalysis, dead-subsystem
# audit). Resolving relative to this file's own directory, matching
# the pattern already used in bitControl.py / DBM.py / baseStartUp.py,
# fixes this regardless of working directory if this class is ever
# wired up.
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "swcmConfig.xml")

class SoftwareConfigManager:
    def __init__(self):
        pass
        
        tree = ET.parse(_CONFIG_PATH)
        config = tree.getroot()
        
        self.components = []
        for comp in config.findall("components/component"):
            name = comp.find("name").text
            desc = comp.find("description").text
            version = comp.find("currentVersion").text
            self.components.append({"name": name, "description": desc, "version": version})
            
        self.data_loads = []
        for load in config.findall("dataLoads/load"):
            load_id = load.find("id").text
            desc = load.find("description").text
            date = load.find("date").text
            status = load.find("status").text
            load_specs = []
            for spec in load.findall("loadSpecs"):
                comp_name = spec.find("component").text
                comp_ver = spec.find("version").text
                load_specs.append({"component": comp_name, "version": comp_ver})
            self.data_loads.append({"id": load_id, "description": desc, "date": date, "status": status, "specs": load_specs})
            
        self.update_sequence = [step.text for step in config.findall("updateSequence/step")]
        
    def display_component_status(self):
        logger.info("Current Software Versions:")
        for comp in self.components:
            logger.info(f"  {comp['description']}: {comp['version']}")
            
    def display_data_loads(self):
        logger.info("\nApproved Data Loads:")
        for load in self.data_loads:
            logger.info(f"  Load {load['id']} - {load['description']} ({load['date']})")
            logger.info(f"    Status: {load['status']}")
            logger.info("    Components:")
            for spec in load["specs"]:
                logger.info(f"      {spec['component']} - {spec['version']}")
                
    def perform_update(self, load_id):
        load = next((l for l in self.data_loads if l["id"] == str(load_id)), None)
        if load:
            logger.info(f"\nApplying data load {load['id']}")
            for step in self.update_sequence:
                logger.info(f"  {step}...")
                # Simulate update sequence
                
            logger.info("Software update completed successfully!")
            
            # Update current versions based on load specs 
            for comp in self.components:
                new_ver = next((s["version"] for s in load["specs"] if s["component"] == comp["name"]), None)
                if new_ver:
                    logger.info(f"  {comp['description']} updated to version {new_ver}")
                    comp["version"] = new_ver
                    
        else:
            logger.warning(f"Invalid data load ID: {load_id}")
        
    def run(self):
        self.display_component_status()
        self.display_data_loads()
        
        self.perform_update("20191015")
        
        self.display_component_status()
        
def get_software_config_manager() -> "SoftwareConfigManager":
    """
    Singleton accessor for system_manager.py's boot sequence.

    Deliberately does NOT spawn a background thread the way the other
    subsystem singletons in this codebase do. run() applies a specific
    hardcoded historical data load ("20191015") as a one-shot demo/
    self-test -- looping that on a timer would "apply" the same software
    update over and over forever, which doesn't correspond to any real
    software configuration management behavior and would just spam
    misleading "Software update completed successfully!" log lines.
    Construction alone (parsing swcmConfig.xml, populating self.components
    and self.data_loads) is enough to make this available as a queryable
    inventory; display_component_status()/display_data_loads()/
    perform_update() remain available to be called on demand (e.g. from a
    maintenance CLI or a future data-load-request message handler).
    """
    global _swcm_instance
    if _swcm_instance is None:
        _swcm_instance = SoftwareConfigManager()
        logger.info("Software Configuration Manager initialised "
                    f"({len(_swcm_instance.components)} components, "
                    f"{len(_swcm_instance.data_loads)} approved data loads)")
    return _swcm_instance


if __name__ == "__main__":
    manager = SoftwareConfigManager()
    manager.run()
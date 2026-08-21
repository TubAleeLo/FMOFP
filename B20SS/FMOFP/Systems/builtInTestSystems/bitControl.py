import os
import xml.etree.ElementTree as ET
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

# bitsConfig.xml lives alongside this file. The previous relative path,
# "Systems/builtInTestSystems/bitsConfig.xml", was missing the "FMOFP/"
# segment (the real path is FMOFP/Systems/builtInTestSystems/...) so it
# raised FileNotFoundError on every construction regardless of working
# directory. eicas.py's BITS polling wraps BuiltInTestController() in a
# broad `except Exception: logger.debug(...)`, so the entire Built-In Test
# display feature failed silently -- self._bits_results never populated,
# with no visible error (production readiness punch list, item 3 audit).
# Resolving relative to this file's own directory, matching the pattern
# already used in DBM.py / baseStartUp.py / metadata_codec.py, fixes this
# regardless of the process's working directory.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BITS_CONFIG_PATH = os.path.join(_HERE, "bitsConfig.xml")


class BuiltInTestController:
    def __init__(self):
        tree = ET.parse(_BITS_CONFIG_PATH)
        config = tree.getroot()

        self.self_tests = []
        for test in config.findall("selfTests/test"):
            test_id   = test.find("id").text
            desc      = test.find("description").text
            system    = test.find("system").text
            components = [c.text for c in test.findall("components/component")]
            self.self_tests.append({
                "id": test_id, "description": desc,
                "system": system, "components": components
            })

        self.periodic_tests = []
        for test in config.findall("periodicTests/test"):
            test_id  = test.find("id").text
            desc     = test.find("description").text
            systems  = [s.text for s in test.findall("systems/system")]
            interval = int(test.find("interval").text)
            self.periodic_tests.append({
                "id": test_id, "description": desc,
                "systems": systems, "interval": interval
            })

        self.interface_tests = []
        for test in config.findall("interfaceTests/test"):
            test_id    = test.find("id").text
            desc       = test.find("description").text
            system1    = test.find("system1").text
            system2    = test.find("system2").text
            components = [c.text for c in test.findall("components/component")]
            self.interface_tests.append({
                "id": test_id, "description": desc,
                "system1": system1, "system2": system2, "components": components
            })

        # Lazy reference — populated on first use to avoid circular imports
        self._post  = None
        self._pbit  = None
        self._ibit  = None

    # ── BIT engine accessors ──────────────────────────────────────────────────

    def _get_post(self):
        if self._post is None:
            from FMOFP.Systems.avionics.hardwareHealth.builtInTesting import PowerOnSelfTest
            self._post = PowerOnSelfTest()
        return self._post

    def _get_pbit(self):
        if self._pbit is None:
            from FMOFP.Systems.avionics.hardwareHealth.builtInTesting import PeriodicBIT
            self._pbit = PeriodicBIT()
        return self._pbit

    def _get_ibit(self):
        if self._ibit is None:
            from FMOFP.Systems.avionics.hardwareHealth.builtInTesting import InitiatedBIT
            self._ibit = InitiatedBIT()
        return self._ibit

    # ── Test runners ──────────────────────────────────────────────────────────

    def run_self_tests(self):
        """Run POST suite via PowerOnSelfTest and log each result."""
        results = self._get_post().run(self.self_tests)
        for r in results:
            level = logger.info if r.status.value == "PASS" else logger.warning
            level(f"[BIT] {r.test_id}/{r.component}: {r.status.value}"
                  + (f" — {r.detail}" if r.detail and r.detail != "nominal" else ""))
        return results

    def run_periodic_tests(self):
        """Run any due periodic tests via PeriodicBIT."""
        results = self._get_pbit().run_due(self.periodic_tests)
        for r in results:
            level = logger.info if r.status.value == "PASS" else logger.warning
            level(f"[BIT] {r.test_id}/{r.component}: {r.status.value}"
                  + (f" — {r.detail}" if r.detail and r.detail != "nominal" else ""))
        return results

    def run_interface_tests(self):
        """Run interface tests as part of an initiated BIT."""
        results = self._get_ibit().run_all(
            self.self_tests, self.periodic_tests, self.interface_tests
        )
        for r in results:
            level = logger.info if r.status.value == "PASS" else logger.warning
            level(f"[BIT] {r.test_id}/{r.component}: {r.status.value}"
                  + (f" — {r.detail}" if r.detail and r.detail != "nominal" else ""))
        return results

    def run(self):
        """Run the full BIT suite in sequence."""
        logger.info("[BIT] Initiating Built-In Tests")

        post_results  = self.run_self_tests()
        logger.info("[BIT] Power-On Self Tests complete")

        pbit_results  = self.run_periodic_tests()
        ibit_results  = self.run_interface_tests()

        all_results   = post_results + pbit_results + ibit_results
        passed = sum(1 for r in all_results if r.status.value == "PASS")
        failed = len(all_results) - passed

        if failed == 0:
            logger.info(f"[BIT] All {passed} tests passed")
        else:
            logger.warning(f"[BIT] {passed} passed, {failed} failed/aborted — review warnings above")

        return all_results

    def get_last_results(self):
        """Return most recent POST results (or empty list if POST not yet run)."""
        if self._post and self._post.is_complete():
            return self._post.get_results()
        return []

    def get_summary_strings(self):
        """Return EICAS-style result strings from the last POST run."""
        if self._post and self._post.is_complete():
            return self._post.summary_strings()
        return []


if __name__ == "__main__":
    controller = BuiltInTestController()
    controller.run()

# FMOFP package marker.
#
# Single source of truth for the application version. Versioning scheme:
# semantic-ish MAJOR.MINOR.PATCH, introduced August 2026 (production-
# readiness follow-up) — the project previously had no version identifier
# anywhere in code, so "which build is running?" was unanswerable and the
# user manual could only say "Development Build".
#
#   1.0.0  — retroactively: the December 2024 state the user manual v1.0
#            documented.
#   1.1.0  — August 2026: post-audit build. All 20 production-readiness
#            audit rounds, the SystemStateManager boot-deadlock fix, the
#            full-suite CI runner, and the subsystem wiring work.
#   1.2.0  — August 21 2026: completion build. Closes the last open items
#            in PLANNING.md — the MIL-STD-1553B bus adapter layer
#            (bus_adapter.py + busAdapterConfig.xml), functional scenario
#            failure injection (LRU forced-fault overrides), the
#            cold-start SQLite connection-pool fix, the debug-CLI test
#            menu cleanup, and the log-noise/shutdown-reporting fixes.
#            First build with a clean boot log: zero ERRORs end to end.
#
# Bump this when behavior changes meaningfully; keep the user manual's
# front matter (FMOFP_User_Manual/00_Title_and_TOC.md) in step.

__version__ = "1.2.0"

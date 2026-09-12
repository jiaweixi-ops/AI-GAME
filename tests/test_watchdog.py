import unittest

from gar_ai.watchdog import Watchdog, WatchdogConfig


class FakeClock:
    def __init__(self): self.value = 0.0
    def __call__(self): return self.value
    def advance(self, seconds): self.value += seconds


class WatchdogTests(unittest.TestCase):
    def test_no_progress(self):
        clock = FakeClock()
        wd = Watchdog(WatchdogConfig(no_progress_sec=10), now=clock)
        clock.advance(11)
        self.assertIn("NO_PROGRESS", {e.code for e in wd.evaluate()})

    def test_loop_pattern(self):
        wd = Watchdog(WatchdogConfig(no_progress_sec=999, min_actions_for_loop=6))
        for _ in range(3):
            wd.record_action("place_verified", {"x": 1, "y": 2})
            wd.record_action("scan_area", {"center": [1, 2], "radius": 5})
        self.assertIn("LOOP_DETECTED", {e.code for e in wd.evaluate()})

    def test_state_recurrence(self):
        wd = Watchdog(WatchdogConfig(no_progress_sec=999, recurrence_threshold=4))
        state = {"research": {"progress": 0.1, "state": "starved"}, "power": {}, "resources": {}, "entities": []}
        for i in range(4):
            wd.record_action("query_recipe", {"name": str(i)})
            wd.record_state(state)
        self.assertIn("STATE_RECURRENCE", {e.code for e in wd.evaluate()})


if __name__ == "__main__": unittest.main()

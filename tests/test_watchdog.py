import unittest

from gar_ai.watchdog import Watchdog, WatchdogConfig


class FakeClock:
    def __init__(self): self.value = 0.0
    def __call__(self): return self.value


class WatchdogTests(unittest.TestCase):
    def test_abab_detected_after_two_repetitions(self):
        wd = Watchdog(WatchdogConfig(no_progress_sec=999))
        for name in ["A", "B", "A", "B"]: wd.record_action(name, {})
        self.assertEqual(wd.evaluate()[0].code, "LOOP_DETECTED")

    def test_width_three_pattern_detected_after_two_repetitions(self):
        wd = Watchdog(WatchdogConfig(no_progress_sec=999))
        for name in ["place", "fail", "scan", "place", "fail", "scan"]: wd.record_action(name, {})
        self.assertEqual(wd.evaluate()[0].code, "LOOP_DETECTED")

    def test_task_scope_resets_history(self):
        wd = Watchdog(WatchdogConfig(no_progress_sec=999)); wd.begin_task("one")
        for name in ["A", "B", "A"]: wd.record_action(name, {})
        wd.begin_task("two"); wd.record_action("B", {})
        self.assertFalse(any(e.code == "LOOP_DETECTED" for e in wd.evaluate()))

    def test_no_progress(self):
        clock = FakeClock(); wd = Watchdog(WatchdogConfig(no_progress_sec=5), now=clock); clock.value = 6
        self.assertTrue(any(e.code == "NO_PROGRESS" for e in wd.evaluate()))


if __name__ == "__main__": unittest.main()

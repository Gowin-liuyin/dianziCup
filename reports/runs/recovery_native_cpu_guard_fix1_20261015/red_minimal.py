"""Replay the review's exact two bounded hard-exit failures before changing production."""

from probe_review_windows import attempt

body = (
    "sys.setswitchinterval(60)\n"
    "while time.process_time()<2.25:\n    pass\n"
    "print('WORK_COMPLETED_AFTER_BUDGET',time.process_time(),flush=True)\n"
)
for index in range(2):
    attempt(f"red_guard_abrupt_exit_{index}", body, fault="abrupt_exit")

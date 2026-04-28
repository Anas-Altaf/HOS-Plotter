"""FMCSA HOS rule constants (49 CFR 395.3) — property-carrying driver."""

DRIVE_LIMIT_MIN = 11 * 60          # 11 hours
WINDOW_LIMIT_MIN = 14 * 60         # 14 hours on-duty window
BREAK_AFTER_DRIVE_MIN = 8 * 60     # 8 hours of driving triggers break
BREAK_DURATION_MIN = 30
OFF_DUTY_RESET_MIN = 10 * 60       # 10 hours to reset
RESTART_MIN = 34 * 60              # 34-hour cycle restart

CYCLE_70_8_MAX_MIN = 70 * 60
CYCLE_70_8_DAYS = 8
CYCLE_60_7_MAX_MIN = 60 * 60
CYCLE_60_7_DAYS = 7

PICKUP_MIN = 60
DROPOFF_MIN = 60
FUEL_INTERVAL_MI = 1000.0
FUEL_DURATION_MIN = 15

STATUS_OFF = "OFF"
STATUS_SB = "SB"
STATUS_DRIVE = "D"
STATUS_ON = "ON"


def cycle_max_min(cycle_type: str) -> int:
    return CYCLE_70_8_MAX_MIN if cycle_type == "70_8" else CYCLE_60_7_MAX_MIN


def cycle_window_days(cycle_type: str) -> int:
    return CYCLE_70_8_DAYS if cycle_type == "70_8" else CYCLE_60_7_DAYS

"""Shared tracking / pitch / responsibility constants (one place for match assumptions)."""

from __future__ import annotations

# Pitch & timing (assumed; not read from FIFA files)
PITCH_LENGTH_M = 105.0
PITCH_WIDTH_M = 68.0
FRAME_RATE = 50.0

# Viewer kit defaults
DEFAULT_TEAM_COLORS = {
    "home": {"colorShirt": "#B73B92", "colorNumber": "#fff"},
    "away": {"colorShirt": "#3395AB", "colorNumber": "#fff"},
}

# Fix / validate kinematics
MAX_PLAYER_SPEED_MPS = 14.0
MAX_BALL_SPEED_MPS = 50.0
MAX_PLAYER_STEP_M = MAX_PLAYER_SPEED_MPS / FRAME_RATE + 0.05
MAX_BALL_STEP_M = MAX_BALL_SPEED_MPS / FRAME_RATE + 0.05
SPEED_MISMATCH_FIX_MPS = 5.0
SPEED_MISMATCH_REPORT_MPS = 3.0

# Responsibility reachability / marking
PITCH_LENGTH = PITCH_LENGTH_M
HALF_LENGTH = PITCH_LENGTH / 2.0
HALF_WIDTH = PITCH_WIDTH_M / 2.0
V_MAX = 7.5
ALPHA_REACH = 1.3
T_MAX = 5.0
DT = 0.05
MIN_RADIUS = 1.0
EPSILON_SECONDS = 0.30
MAJORITY_WINDOW = 50
MAJORITY_VOTES = 30
MUTUAL_HELP_MAX_EDGE_M2 = 30.0**2
HULL_MARGIN_M = 5.0
HULL_RING_SAMPLES = 16
MARKING_K = 2
MARKING_ALPHA = 1.5

# Zones defaults
ZONES_STRIDE = 1
ZONES_XPOINTS = 50

PARQUET_BATCH_FRAMES = 2000

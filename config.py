"""Central config -- tune these instead of hunting through the code."""

from pathlib import Path

BASE_DIR = Path(__file__).parent

# --- Paths ---
FACES_DIR = BASE_DIR / "data" / "faces"
ENCODINGS_PATH = BASE_DIR / "data" / "encodings.pickle"

# --- Recognition tuning ---
# Lower = stricter match (fewer false accepts, more "Unknown").
# Higher = looser match (fewer false rejects, more risk of mixing up look-alikes).
# 0.6 is face_recognition's own default; 0.5 is noticeably stricter.
TOLERANCE = 0.45

# How many consecutive frames the SAME person must match before we
# consider them "confirmed" and call on_confirmed(). Stops one lucky/bad
# frame from marking the wrong person.
CONFIRM_FRAMES = 3

# Process every Nth frame at reduced size, to keep the loop near real-time
# on modest hardware. 1 = every frame (slower, more accurate timing).
PROCESS_EVERY_N_FRAMES = 2
FRAME_RESIZE_SCALE = 0.25  # shrink frame to 1/4 size before detection

# Face detection model: "hog" is CPU-fast (good default, works without CUDA).
# "cnn" is much more accurate but needs a GPU to run at usable speed.
DETECTION_MODEL = "hog"

# --- Liveness detection (anti-spoofing) ---
# Deliberately modest: a blink-based check using MediaPipe Face Mesh,
# gating attendance until the person in frame blinks at least once.
ENABLE_LIVENESS = True

# Eye Aspect Ratio (EAR) threshold: below this, an eye counts as closed.
BLINK_EAR_THRESHOLD = 0.21

# Minimum consecutive processed frames the eye must stay below threshold
# for a dip to count as a real blink, not just noisy landmark jitter.
BLINK_CONSEC_FRAMES = 2

# How many processed frames to wait for a blink after identity is
# confirmed, before giving up and requiring re-confirmation.
LIVENESS_TIMEOUT_FRAMES = 60

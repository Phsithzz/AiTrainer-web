"""Squat form analysis on client-sent pose landmarks.

Ported from the test/squat-service branch, which ran the same logic on frames the
server decoded with MediaPipe. Clients now send the 33 landmarks themselves, so the
logic is unchanged and only the input differs:

- the original squat model (squat_model.pkl) on raw landmarks, 33 x (x, y, z, visibility)
- standing (UP) is treated as good, so the model can't flag a bad back while standing
- a lifted heel is flagged from the knee-ankle-toe angle
- a rounded back is flagged from the shoulder-hip-knee angle, only while down
- a rep is bad only after 2+ consecutive bad frames with confidence >= 0.65
"""
import numpy as np
import joblib
from pathlib import Path

from services.landmarks import coerce_landmarks, serialize_landmarks

BASE_DIR = Path(__file__).parent.parent
MODEL_PATH = BASE_DIR / "models" / "squat_model.pkl"
ENCODER_PATH = BASE_DIR / "models" / "label_encoder.pkl"

try:
    _MODEL = joblib.load(MODEL_PATH)
    _LABEL_ENCODER = joblib.load(ENCODER_PATH)
    print(f"[OK] Loaded squat model (original) | Classes: {list(_LABEL_ENCODER.classes_)}")
except Exception as e:
    raise RuntimeError(f"Could not load the squat model from {MODEL_PATH} / {ENCODER_PATH}: {e}")

CLASS_CONFIG = {
    "squat_good":     {"feedback": "",                "count_rep": True},
    "squat_bad_heel": {"feedback": "ส้นเท้าลอย!",    "count_rep": True},
    "squat_bad_back": {"feedback": "หลังงอ!",         "count_rep": True},
    "squat_bad_foot": {"feedback": "เท้าไม่ติดพื้น!", "count_rep": False},
}
DEFAULT_CONFIG = {"feedback": "", "count_rep": False}

SMOOTH_N = 7
GOOD_THRESHOLD = 0.65      # a bad frame only counts at or above this confidence
BAD_FRAMES_TO_FLAG = 2     # consecutive bad frames needed to call the rep bad
DOWN_RATIO = 0.88          # down when hip_y > knee_y * DOWN_RATIO
HEEL_ANGLE_LIMIT = 120.0   # knee-ankle-toe angle above this = heel lifted
BACK_ANGLE_LIMIT = 60.0    # shoulder-hip-knee angle below this while down = rounded back


def is_body_fully_visible(landmarks) -> bool:
    lm = landmarks.landmark
    t = 0.5
    left = lm[11].visibility > t and lm[23].visibility > t and lm[25].visibility > t and lm[27].visibility > t
    right = lm[12].visibility > t and lm[24].visibility > t and lm[26].visibility > t and lm[28].visibility > t
    return left or right


def _angle(a, b, c) -> float:
    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = abs(radians * 180.0 / np.pi)
    return 360.0 - angle if angle > 180.0 else angle


class RepCounter:
    def __init__(self):
        self.reset()

    def reset(self):
        self.reps = 0
        self.state = "UP"
        self.good_count = 0
        self.bad_count = 0
        self.is_bad_rep = False
        self.bad_label_memory = None
        self.bad_details = {}
        self.bad_frames_count = 0

    def update(self, landmarks_list: list, label: str, confidence: float) -> tuple[bool, str]:
        hip_y = (landmarks_list[23]["y"] + landmarks_list[24]["y"]) / 2
        knee_y = (landmarks_list[25]["y"] + landmarks_list[26]["y"]) / 2
        is_down = hip_y > knee_y * DOWN_RATIO
        new_rep = False
        rep_label = "squat_good"

        if self.state == "UP" and is_down:
            self.state = "DOWN"
            self.is_bad_rep = False
            self.bad_label_memory = None
            self.bad_frames_count = 0

        if self.state == "DOWN":
            if label != "squat_good" and confidence >= GOOD_THRESHOLD:
                self.bad_frames_count += 1
                if self.bad_frames_count >= BAD_FRAMES_TO_FLAG:
                    self.is_bad_rep = True
                    if self.bad_label_memory is None:
                        self.bad_label_memory = label
            else:
                self.bad_frames_count = 0

            if not is_down:
                self.state = "UP"
                self.reps += 1
                new_rep = True
                if self.is_bad_rep:
                    self.bad_count += 1
                    rep_label = self.bad_label_memory
                    self.bad_details[rep_label] = self.bad_details.get(rep_label, 0) + 1
                else:
                    self.good_count += 1

        return new_rep, rep_label

    def to_dict(self) -> dict:
        return {
            "reps": self.reps,
            "good_count": self.good_count,
            "bad_count": self.bad_count,
            "bad_details": self.bad_details,
            "state": self.state,
        }


class SquatPredictor:
    def __init__(self, model=None, label_encoder=None):
        self.model = model if model is not None else _MODEL
        self.le = label_encoder if label_encoder is not None else _LABEL_ENCODER
        self.pred_buffer = []
        self.counter = RepCounter()

    def predict(self, client_landmarks) -> dict:
        landmarks = coerce_landmarks(client_landmarks)
        lm_list = serialize_landmarks(landmarks)

        if not is_body_fully_visible(landmarks):
            return {
                "pose_detected": False,
                "label": "no_pose",
                "confidence": 0.0,
                "feedback": "",
                "proba": {},
                "landmarks": lm_list,
                **self.counter.to_dict(),
            }

        vec = np.array([[v for p in lm_list for v in (p["x"], p["y"], p["z"], p["visibility"])]])
        proba = self.model.predict_proba(vec)
        self.pred_buffer.append(int(np.argmax(proba)))
        if len(self.pred_buffer) > SMOOTH_N:
            self.pred_buffer.pop(0)
        smooth_idx = max(set(self.pred_buffer), key=self.pred_buffer.count)
        label = self.le.inverse_transform([smooth_idx])[0]
        confidence = float(proba[0][smooth_idx])

        lms = landmarks.landmark
        if self.counter.state == "UP":
            label, confidence = "squat_good", 1.0

        left_ankle = _angle((lms[25].x, lms[25].y), (lms[27].x, lms[27].y), (lms[31].x, lms[31].y))
        right_ankle = _angle((lms[26].x, lms[26].y), (lms[28].x, lms[28].y), (lms[32].x, lms[32].y))
        if (left_ankle + right_ankle) / 2 > HEEL_ANGLE_LIMIT:
            label, confidence = "squat_bad_heel", 0.99

        if self.counter.state == "DOWN":
            shoulder = ((lms[11].x + lms[12].x) / 2, (lms[11].y + lms[12].y) / 2)
            hip = ((lms[23].x + lms[24].x) / 2, (lms[23].y + lms[24].y) / 2)
            knee = ((lms[25].x + lms[26].x) / 2, (lms[25].y + lms[26].y) / 2)
            if _angle(shoulder, hip, knee) < BACK_ANGLE_LIMIT:
                label, confidence = "squat_bad_back", 0.99

        new_rep, rep_label = self.counter.update(lm_list, label, confidence)
        if new_rep:
            label = rep_label
        elif self.counter.state == "DOWN" and self.counter.is_bad_rep:
            label, confidence = self.counter.bad_label_memory, 0.99

        cfg = CLASS_CONFIG.get(rep_label, DEFAULT_CONFIG)
        feedback = cfg["feedback"] if new_rep and rep_label != "squat_good" else ""
        proba_dict = {cls: float(proba[0][i]) for i, cls in enumerate(self.le.classes_)}

        return {
            "pose_detected": True,
            "label": label,
            "confidence": confidence,
            "feedback": feedback,
            "proba": proba_dict,
            "landmarks": lm_list,
            **self.counter.to_dict(),
        }

    def reset(self):
        self.pred_buffer.clear()
        self.counter.reset()

    def close(self):
        pass

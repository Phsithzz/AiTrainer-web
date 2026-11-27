"""Squat behaviour ported from the test/squat-service branch, on client-sent landmarks.

Branch logic: the original squat model on raw landmarks (33 x {x, y, z, visibility}),
plus rules: treat standing (UP) as good, flag a lifted heel from the ankle angle,
flag a rounded back from the trunk angle only while down, and only call a rep bad
after 2+ consecutive bad frames with confidence >= 0.65.
"""
import numpy as np
import pytest
from sklearn.preprocessing import LabelEncoder

from services.squat_service import RepCounter, SquatPredictor

CLASSES = ["squat_bad_back", "squat_bad_foot", "squat_bad_heel", "squat_good"]


class FakeModel:
    """Always predicts one class with the given probability."""

    def __init__(self, label, p=0.9):
        self.label, self.p = label, p

    def predict_proba(self, vec):
        assert vec.shape == (1, 132), "the original model takes 33 landmarks x 4 values"
        probs = np.full((1, len(CLASSES)), (1 - self.p) / (len(CLASSES) - 1))
        probs[0, CLASSES.index(self.label)] = self.p
        return probs


def encoder():
    le = LabelEncoder()
    le.fit(CLASSES)
    return le


def pose(hip_y=0.6, knee_y=0.75, heel_up=False, lean_forward=False):
    """33 visible landmarks shaped like a person seen from the side."""
    lm = [{"x": 0.5, "y": 0.3, "z": 0.0, "visibility": 0.99} for _ in range(33)]
    shoulder = (0.5, 0.35) if not lean_forward else (0.62, 0.62)
    for i in (11, 12):
        lm[i].update(x=shoulder[0], y=shoulder[1])
    for i in (23, 24):
        lm[i].update(x=0.5, y=hip_y)
    for i in (25, 26):
        lm[i].update(x=0.55, y=knee_y)
    for i in (27, 28):
        lm[i].update(x=0.5, y=0.9)
    foot = (0.55, 0.98) if heel_up else (0.6, 0.91)  # toes down = heel lifted
    for i in (31, 32):
        lm[i].update(x=foot[0], y=foot[1])
    return lm


STANDING = dict(hip_y=0.6, knee_y=0.75)   # hip well above knee -> UP
SQUATTING = dict(hip_y=0.74, knee_y=0.75)  # hip near knee level -> DOWN


def predictor(label="squat_good", p=0.9):
    return SquatPredictor(model=FakeModel(label, p), label_encoder=encoder())


# ---------------------------------------------------------------- RepCounter

def run_counter(frames):
    counter = RepCounter()
    for lm, label, conf in frames:
        counter.update(lm, label, conf)
    return counter


def test_good_rep_is_counted_on_the_way_up():
    c = run_counter([(pose(**STANDING), "squat_good", 1.0),
                     (pose(**SQUATTING), "squat_good", 0.9),
                     (pose(**STANDING), "squat_good", 1.0)])
    assert (c.reps, c.good_count, c.bad_count) == (1, 1, 0)


def test_single_bad_frame_does_not_spoil_a_rep():
    c = run_counter([(pose(**SQUATTING), "squat_bad_back", 0.9),
                     (pose(**SQUATTING), "squat_good", 0.9),
                     (pose(**STANDING), "squat_good", 1.0)])
    assert (c.good_count, c.bad_count) == (1, 0)


def test_two_consecutive_confident_bad_frames_make_a_bad_rep():
    c = run_counter([(pose(**SQUATTING), "squat_bad_back", 0.9),
                     (pose(**SQUATTING), "squat_bad_back", 0.9),
                     (pose(**STANDING), "squat_good", 1.0)])
    assert (c.good_count, c.bad_count) == (0, 1)
    assert c.bad_details == {"squat_bad_back": 1}


def test_low_confidence_bad_frames_are_ignored():
    c = run_counter([(pose(**SQUATTING), "squat_bad_back", 0.5),
                     (pose(**SQUATTING), "squat_bad_back", 0.5),
                     (pose(**STANDING), "squat_good", 1.0)])
    assert (c.good_count, c.bad_count) == (1, 0)


# ---------------------------------------------------------------- SquatPredictor

def test_default_predictor_uses_the_original_squat_model():
    result = SquatPredictor().predict(pose(**STANDING))
    assert set(result["proba"]) == set(CLASSES)  # only the original model knows squat_bad_foot


def test_standing_is_treated_as_good_even_if_the_model_says_bad():
    result = predictor("squat_bad_back").predict(pose(**STANDING))
    assert result["label"] == "squat_good"
    assert result["state"] == "UP"


def test_lifted_heel_is_flagged_from_the_ankle_angle():
    result = predictor("squat_good").predict(pose(**STANDING, heel_up=True))
    assert result["label"] == "squat_bad_heel"


def test_rounded_back_is_flagged_only_while_down():
    p = predictor("squat_good")
    p.predict(pose(**STANDING))
    first_down = p.predict(pose(**SQUATTING, lean_forward=True))  # still masked: state was UP
    assert first_down["label"] == "squat_good"
    result = p.predict(pose(**SQUATTING, lean_forward=True))
    assert result["state"] == "DOWN"
    assert result["label"] == "squat_bad_back"


def test_body_not_fully_visible_is_not_analysed():
    lm = pose(**STANDING)
    for i in (11, 12, 23, 24, 25, 26, 27, 28):
        lm[i]["visibility"] = 0.1
    result = predictor("squat_bad_back").predict(lm)
    assert result["pose_detected"] is False
    assert result["label"] == "no_pose"
    assert result["reps"] == 0


def test_full_rep_round_trip_reports_counts_and_feedback():
    p = predictor("squat_bad_back", p=0.9)
    p.predict(pose(**STANDING))
    p.predict(pose(**SQUATTING))
    p.predict(pose(**SQUATTING))
    result = p.predict(pose(**STANDING))
    assert (result["reps"], result["good_count"], result["bad_count"]) == (1, 0, 1)
    assert result["label"] == "squat_bad_back"
    assert result["feedback"] == "หลังงอ!"
    assert result["bad_details"] == {"squat_bad_back": 1}


def test_wrong_landmark_count_is_rejected():
    with pytest.raises(ValueError):
        predictor().predict(pose()[:10])

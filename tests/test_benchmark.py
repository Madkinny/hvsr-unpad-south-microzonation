"""The grader must give the reference full marks and diagnose the flawed example."""
import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "benchmark" / "hvsr_qc_task"

spec = importlib.util.spec_from_file_location("grader", TASK / "grader.py")
grader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grader)


def test_reference_scores_full_marks(tmp_path):
    ref = pd.read_csv(grader.REFERENCE)[grader.COLUMNS]
    path = tmp_path / "reference.csv"
    ref.to_csv(path, index=False)
    score, _ = grader.grade(path)
    assert score == 80


def test_flawed_example_is_caught():
    score, results = grader.grade(TASK / "examples" / "flawed_submission.csv")
    by_name = {name.split()[0]: (frac, detail) for name, _, frac, detail in results}
    assert score < 40
    assert by_name["A3"][0] == 0                      # duplicate IDs dropped
    assert by_name["A4"][0] == 0                      # typo stations dropped
    assert "false northing" in by_name["A7"][1]       # projection diagnosed

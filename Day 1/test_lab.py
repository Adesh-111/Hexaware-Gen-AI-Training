import json

import lab


def test_dataset_self_check():
    lab.self_check(lab.load_cases())


def test_numeric_and_vector_verifiers():
    assert lab.verify_answer({"expected_answer": 12, "tolerance": 1e-9, "verifier": "numeric"}, "The answer is 12.")
    assert lab.verify_answer({"expected_answer": [4, 6], "tolerance": 1e-9, "verifier": "vector"}, "4, 6")
    assert not lab.verify_answer({"expected_answer": 12, "tolerance": 1e-9, "verifier": "numeric"}, "13")


def test_schema_rejects_extra_fields():
    payload = {"final_answer": "1", "solution_steps": [], "assumptions": [], "verification": "", "leak": "hidden"}
    try:
        lab.parse_response(json.dumps(payload))
    except ValueError:
        pass
    else:
        raise AssertionError("extra schema fields were accepted")

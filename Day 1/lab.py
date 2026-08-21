"""Lab 2: evaluate concise, verifiable math solutions with the OpenAI API."""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATASET_PATH = Path(__file__).with_name("dataset.jsonl")
OUTPUT_DIR = Path(__file__).with_name("outputs")

SCHEMA = {
    "type": "object",
    "properties": {
        "final_answer": {"type": "string"},
        "solution_steps": {"type": "array", "items": {"type": "string"}},
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "verification": {"type": "string"},
    },
    "required": ["final_answer", "solution_steps", "assumptions", "verification"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You solve multi-step mathematics problems accurately. Do not reveal private chain-of-thought. "
    "Return only the requested JSON object: concise solution steps with key equations, explicit assumptions, "
    "a final answer, and a short verification statement. Never invent missing information."
)


@dataclass
class CaseResult:
    case_id: str
    category: str
    difficulty: str
    final_answer: Any = None
    valid_schema: bool = False
    verified: bool = False
    error_type: str | None = None
    latency_seconds: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_response: str | None = None


def load_cases(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def parse_response(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("response is not a JSON object")
    required = {"final_answer", "solution_steps", "assumptions", "verification"}
    if set(payload) != required or not isinstance(payload["final_answer"], str):
        raise ValueError("response does not match the required schema")
    if not all(isinstance(payload[key], list) for key in ("solution_steps", "assumptions")):
        raise ValueError("steps and assumptions must be arrays")
    if not isinstance(payload["verification"], str):
        raise ValueError("verification must be a string")
    return payload


def numbers(value: str) -> list[float]:
    matches = re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", value.replace(",", " "))
    return [float(item) for item in matches]


def verify_answer(case: dict[str, Any], answer: str) -> bool:
    expected = case["expected_answer"]
    tolerance = float(case.get("tolerance", 1e-9))
    verifier = case["verifier"]
    if verifier == "text":
        return answer.strip().upper() == str(expected).upper()
    observed = numbers(answer)
    if verifier == "numeric":
        return len(observed) >= 1 and math.isclose(observed[-1], float(expected), rel_tol=tolerance, abs_tol=tolerance)
    if verifier == "vector":
        return len(observed) >= len(expected) and all(
            math.isclose(actual, float(want), rel_tol=tolerance, abs_tol=tolerance)
            for actual, want in zip(observed[-len(expected):], expected)
        )
    raise ValueError(f"unknown verifier: {verifier}")


def build_input(case: dict[str, Any]) -> list[dict[str, str]]:
    return [{"role": "user", "content": f"Problem: {case['problem']}"}]


def usage_tokens(response: Any) -> tuple[int | None, int | None]:
    usage = getattr(response, "usage", None)
    if not usage:
        return None, None
    input_tokens = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None)
    return input_tokens, output_tokens


def request_case(client: Any, provider: str, model: str, case: dict[str, Any], timeout: float, retries: int) -> tuple[dict[str, Any], Any, float]:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        started = time.perf_counter()
        try:
            if provider == "openai":
                response = client.responses.create(
                    model=model,
                    instructions=SYSTEM_PROMPT,
                    input=build_input(case),
                    text={"format": {"type": "json_schema", "name": "math_solution", "strict": True, "schema": SCHEMA}},
                    timeout=timeout,
                )
                response_text = response.output_text
            else:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}, *build_input(case)],
                    response_format={"type": "json_schema", "json_schema": {"name": "math_solution", "strict": True, "schema": SCHEMA}},
                    timeout=timeout,
                )
                response_text = response.choices[0].message.content or ""
            parsed = parse_response(response_text)
            return parsed, response, time.perf_counter() - started
        except (json.JSONDecodeError, ValueError):
            raise
        except Exception as exc:  # API, timeout, and malformed-response failures are recorded per case.
            last_error = exc
            if attempt < retries:
                time.sleep(2**attempt)
    raise RuntimeError(str(last_error)) from last_error


def evaluate(client: Any, provider: str, cases: list[dict[str, Any]], model: str, timeout: float, retries: int) -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in cases:
        result = CaseResult(case["id"], case["category"], case["difficulty"])
        try:
            payload, response, latency = request_case(client, provider, model, case, timeout, retries)
            result.final_answer = payload["final_answer"]
            result.raw_response = json.dumps(payload)
            result.valid_schema = True
            result.verified = verify_answer(case, result.final_answer)
            result.latency_seconds = latency
            result.input_tokens, result.output_tokens = usage_tokens(response)
            if not result.verified:
                result.error_type = "wrong_answer"
        except json.JSONDecodeError:
            result.error_type = "malformed_json"
        except RuntimeError as exc:
            result.error_type = "api_or_timeout: " + str(exc)[:200]
        except (TypeError, ValueError):
            result.error_type = "invalid_answer"
        results.append(result)
    return results


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    total = len(results)
    verified = sum(item.verified for item in results)
    by_category: dict[str, dict[str, int]] = {}
    for item in results:
        bucket = by_category.setdefault(item.category, {"total": 0, "verified": 0})
        bucket["total"] += 1
        bucket["verified"] += int(item.verified)
    latencies = [item.latency_seconds for item in results if item.latency_seconds is not None]
    return {
        "total_cases": total,
        "verified_cases": verified,
        "accuracy": verified / total if total else 0.0,
        "schema_valid_rate": sum(item.valid_schema for item in results) / total if total else 0.0,
        "mean_latency_seconds": sum(latencies) / len(latencies) if latencies else None,
        "error_types": {key: sum(item.error_type == key for item in results) for key in {item.error_type for item in results if item.error_type}},
        "by_category": by_category,
    }


def self_check(cases: list[dict[str, Any]]) -> None:
    assert len(cases) >= 10
    assert {case["category"] for case in cases} >= {"arithmetic", "algebra", "geometry", "probability", "statistics"}
    assert sum(case["difficulty"] == "adversarial" for case in cases) >= 3
    for case in cases:
        assert {"id", "problem", "expected_answer", "verifier"} <= case.keys()
        assert verify_answer(case, str(case["expected_answer"]))
    example = {"final_answer": "6", "solution_steps": ["3x = 18"], "assumptions": [], "verification": "Substitution works."}
    assert parse_response(json.dumps(example)) == example
    try:
        parse_response("not json")
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("malformed JSON was accepted")
    print(f"Self-check passed: {len(cases)} cases, verifiers, schema, and malformed-response handling.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--provider", choices=("openai", "grok"), default=os.getenv("LAB_PROVIDER", "openai"))
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    default_model = "gpt-4.1-mini" if args.provider == "openai" else "grok-4-1-fast-reasoning"
    args.model = args.model or os.getenv(f"{args.provider.upper()}_MODEL", default_model)
    cases = load_cases(args.dataset)
    if args.self_check:
        self_check(cases)
        return 0
    api_key_name = "OPENAI_API_KEY" if args.provider == "openai" else "XAI_API_KEY"
    if not os.getenv(api_key_name):
        print(f"{api_key_name} is required for an API run. Use --self-check to validate offline.", file=sys.stderr)
        return 2
    from openai import OpenAI
    random.seed(0)
    client = OpenAI(api_key=os.environ[api_key_name], base_url="https://api.x.ai/v1" if args.provider == "grok" else None)
    results = evaluate(client, args.provider, cases, args.model, args.timeout, args.retries)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    report = {"experiment": "lab2_chain_of_thought_math", "provider": args.provider, "model": args.model, "dataset": str(args.dataset), "results": [vars(item) for item in results], "summary": summarize(results)}
    output_path = args.output_dir / f"run_{stamp}.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Detailed report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

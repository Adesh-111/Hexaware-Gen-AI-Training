# Lab 2: Chain of Thought for Math Problems

This lab evaluates whether an OpenAI model produces correct, concise, and verifiable solutions to multi-step mathematics problems. It explicitly does **not** ask the model to expose private chain-of-thought. The model returns a structured answer containing a final answer, short solution steps, assumptions, and a verification note.

## Objective and hypotheses

- **Objective:** measure verified mathematical accuracy, schema compliance, error types, latency, and token usage across several problem domains.
- **H1:** structured prompts with explicit verification requests produce a high verified-answer rate.
- **H2:** adversarial cases expose more domain or representation errors than ordinary cases.
- **H3:** external deterministic verifiers are more reliable than judging correctness from prose alone.
- **Success criteria:** at least 90% verified accuracy overall, at least 95% schema validity, and category-level results reported with no silent failures. These are evaluation targets, not claims about any model.

## Project structure

```text
lab.py             API runner, schema validation, verifiers, metrics, self-check
app.py             Streamlit dashboard for running and reviewing experiments
dataset.jsonl      Reproducible cases and expected answers
test_lab.py        Offline tests for the experiment logic
requirements.txt   Python dependencies
outputs/           Generated JSON reports (created at runtime)
```

## Methodology

The dataset contains 13 cases across arithmetic, algebra, geometry, probability, statistics, and logic. Three are deliberately adversarial: an extraneous-root trap, a constrained rectangle, and a domain exception at `x = 3`. Cases store an expected answer, tolerance, and verifier type. Numeric answers are compared with `math.isclose`; vectors compare each reported number; text cases use normalized exact comparison.

Each request uses a system instruction and JSON schema. The response contract is deliberately narrow:

```json
{
  "final_answer": "string",
  "solution_steps": ["concise step"],
  "assumptions": ["explicit assumption"],
  "verification": "short independent check"
}
```

The evaluator separates model-reported reasoning from external verification. A correct-looking explanation does not pass unless `final_answer` passes the case verifier. API, timeout, malformed JSON, schema, and invalid-answer failures are recorded per case so one failure does not erase the run.

## Run it

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:OPENAI_API_KEY = "your-key"
py lab.py
```

Launch the UI locally:

```powershell
streamlit run app.py
```

Then open the local URL shown by Streamlit, usually `http://localhost:8501`. Use **Run offline self-check** to validate the lab without a key, or enter an OpenAI/Grok key in the sidebar and choose **Start model run**. Reports are saved in `outputs/` and can be selected from the dashboard.

The same lab can run against Grok through xAI's OpenAI-compatible API:

```powershell
$env:XAI_API_KEY = "your-xai-key"
py lab.py --provider grok --model grok-4-1-fast-reasoning
```

Use `OPENAI_MODEL` or `GROK_MODEL` to set a provider-specific default. The evaluator and dataset stay identical, making provider comparisons meaningful. API keys are read from environment variables and are never written to reports.

Useful options:

```powershell
py lab.py --self-check
py lab.py --model gpt-4.1-mini --retries 2 --timeout 60
py lab.py --provider grok --model grok-4-1-fast-reasoning --retries 2 --timeout 60
py -m pytest -q
```

The API run writes `outputs/run_<UTC timestamp>.json`. It contains per-case responses and a summary with verified accuracy, schema-valid rate, mean latency, error counts, and category breakdown. Keep the dataset and model name with the report for reproducibility. A timestamp is used only for unique filenames; the case order and random seed are fixed.

## Example expected output

```text
Self-check passed: 13 cases, verifiers, schema, and malformed-response handling.
```

An API summary has this shape:

```json
{
  "total_cases": 13,
  "verified_cases": 12,
  "accuracy": 0.9230769231,
  "schema_valid_rate": 1.0,
  "mean_latency_seconds": 1.8,
  "error_types": {"wrong_answer": 1},
  "by_category": {"algebra": {"total": 5, "verified": 4}}
}
```

The numbers above are illustrative, not measured results.

## Interpretation and recommendations

Report overall accuracy with category and difficulty slices. Inspect every failed case and classify it as arithmetic, algebraic, geometry, probability, statistics, domain/constraint, formatting, or API failure. Compare repeated runs to measure consistency; do not infer reliability from one run. Latency and token usage are secondary operational metrics. For stronger evidence, add independent problem variants, run each case multiple times when sampling is enabled, compare models using the same dataset, and manually audit a sample of explanations. Never mark a case correct solely because the prose sounds plausible.

## Self-check coverage

`--self-check` verifies dataset coverage, expected-answer/verifier agreement, JSON schema acceptance, and malformed JSON rejection without making network calls. `pytest` additionally checks numeric, vector, wrong-answer, and extra-field behavior. This is a design check, not a substitute for manual review or an API run.

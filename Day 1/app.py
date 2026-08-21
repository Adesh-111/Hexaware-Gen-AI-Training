from __future__ import annotations

import json
import os
import time
from pathlib import Path

import streamlit as st

from lab import DATASET_PATH, OUTPUT_DIR, evaluate, load_cases, self_check, summarize

st.set_page_config(page_title="Math Reasoning Lab", page_icon="∑", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@400;500;600;700&display=swap');
    :root { --ink:#101316; --paper:#f4f0e8; --acid:#c8f169; --coral:#ff765f; --muted:#8b918e; }
    .stApp { background:var(--ink); color:var(--paper); }
    [data-testid="stSidebar"] { background:#171b1d; border-right:1px solid #303638; }
    [data-testid="stSidebar"] * { font-family:'Space Grotesk',sans-serif; }
    h1,h2,h3,p,div,span,label { font-family:'Space Grotesk',sans-serif; }
    code, .mono { font-family:'DM Mono',monospace !important; }
    h1 { font-size:clamp(2.8rem,6vw,6.5rem) !important; line-height:.92 !important; letter-spacing:-.06em; margin-bottom:.5rem; }
    h2 { letter-spacing:-.03em; }
    .eyebrow { color:var(--acid); font-family:'DM Mono',monospace; font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; }
    .lede { color:#b9c0ba; font-size:1.08rem; max-width:680px; }
    .rule { border-top:1px solid #303638; margin:1.4rem 0 2rem; }
    .metric { background:#1b2022; border:1px solid #303638; padding:1.1rem 1.2rem; min-height:112px; }
    .metric-label { color:var(--muted); text-transform:uppercase; font:500 .68rem 'DM Mono',monospace; letter-spacing:.1em; }
    .metric-value { color:var(--paper); font-size:2.2rem; font-weight:600; margin-top:.35rem; }
    .metric-value.good { color:var(--acid); }
    .metric-value.warn { color:var(--coral); }
    .case-card { background:#1b2022; border-left:3px solid var(--acid); padding:1rem 1.2rem; margin:.55rem 0; }
    .case-card.fail { border-left-color:var(--coral); }
    .case-id { font:500 .75rem 'DM Mono',monospace; color:var(--acid); }
    .case-problem { color:var(--paper); margin:.35rem 0; }
    .small { color:var(--muted); font-size:.82rem; }
    .stButton > button { border-radius:0; background:var(--acid); color:var(--ink); border:0; font-weight:700; }
    .stButton > button:hover { background:#e0ff98; color:var(--ink); }
    div[data-testid="stExpander"] { border-color:#303638; background:#171b1d; border-radius:0; }
    </style>
    """,
    unsafe_allow_html=True,
)


def latest_reports() -> list[Path]:
    return sorted(OUTPUT_DIR.glob("run_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)


def metric_card(label: str, value: str, tone: str = "") -> None:
    st.markdown(f'<div class="metric"><div class="metric-label">{label}</div><div class="metric-value {tone}">{value}</div></div>', unsafe_allow_html=True)


def run_experiment(provider: str, model: str, api_key: str, timeout: float, retries: int) -> None:
    if not api_key:
        st.error("Add an API key in the sidebar before starting a model run.")
        return
    from openai import OpenAI

    key_name = "OPENAI_API_KEY" if provider == "openai" else "XAI_API_KEY"
    os.environ[key_name] = api_key
    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1" if provider == "grok" else None)
    cases = load_cases(DATASET_PATH)
    with st.status(f"Running {len(cases)} cases on {model}...", expanded=True) as status:
        results = evaluate(client, provider, cases, model, timeout, retries)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        report = {"experiment": "lab2_chain_of_thought_math", "provider": provider, "model": model, "dataset": str(DATASET_PATH), "results": [vars(item) for item in results], "summary": summarize(results)}
        output_path = OUTPUT_DIR / f"run_{stamp}.json"
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        status.update(label="Run complete", state="complete")
    st.session_state["selected_report"] = str(output_path)
    st.rerun()


cases = load_cases(DATASET_PATH)
reports = latest_reports()

with st.sidebar:
    st.markdown('<div class="eyebrow">Experiment controls</div>', unsafe_allow_html=True)
    provider = st.selectbox("Provider", ["openai", "grok"], format_func=str.title)
    default_model = "gpt-4.1-mini" if provider == "openai" else "grok-4-1-fast-reasoning"
    model = st.text_input("Model", value=default_model)
    api_key = st.text_input("API key", type="password", help="Used only for this process; never written to reports.")
    timeout = st.number_input("Timeout (seconds)", min_value=5, max_value=300, value=60)
    retries = st.number_input("Retries", min_value=0, max_value=5, value=2)
    st.markdown("<div class='rule'></div>", unsafe_allow_html=True)
    if st.button("Run offline self-check", use_container_width=True):
        try:
            self_check(cases)
            st.success(f"Self-check passed for {len(cases)} cases.")
        except AssertionError as exc:
            st.error(f"Self-check failed: {exc}")
    if st.button("Start model run", use_container_width=True):
        run_experiment(provider, model, api_key, float(timeout), int(retries))

st.markdown('<div class="eyebrow">Lab 02 / evaluation console</div>', unsafe_allow_html=True)
st.title("Can the model\nshow its work?", anchor=False)
st.markdown('<p class="lede">A compact test bench for multi-step mathematics. The model gives concise, inspectable steps; deterministic Python verification decides whether the answer passes.</p>', unsafe_allow_html=True)
st.markdown('<div class="rule"></div>', unsafe_allow_html=True)

if reports:
    report_options = {path.name: path for path in reports}
    selected = st.selectbox("Report", list(report_options), index=0)
    report = json.loads(report_options[selected].read_text(encoding="utf-8"))
    summary = report["summary"]
    st.markdown(f'<div class="small mono">{report.get("provider", "unknown").upper()} / {report.get("model", "unknown")} / {selected}</div>', unsafe_allow_html=True)
    st.write("")
    columns = st.columns(4)
    with columns[0]: metric_card("Verified accuracy", f'{summary["accuracy"]:.0%}', "good" if summary["accuracy"] >= .9 else "warn")
    with columns[1]: metric_card("Cases passed", f'{summary["verified_cases"]}/{summary["total_cases"]}')
    with columns[2]: metric_card("Schema valid", f'{summary["schema_valid_rate"]:.0%}', "good" if summary["schema_valid_rate"] >= .95 else "warn")
    with columns[3]: metric_card("Mean latency", f'{summary["mean_latency_seconds"]:.1f}s' if summary["mean_latency_seconds"] is not None else "n/a")
    st.write("")
    left, right = st.columns([1, 1.35])
    with left:
        st.subheader("Accuracy by category")
        category_rows = []
        for category, values in summary["by_category"].items():
            category_rows.append({"category": category, "accuracy": values["verified"] / values["total"], "passed": values["verified"], "total": values["total"]})
        st.bar_chart(category_rows, x="category", y="accuracy", y_label="verified rate", height=260)
        st.dataframe(category_rows, hide_index=True, use_container_width=True)
    with right:
        st.subheader("Case review")
        for result in report["results"]:
            case = next(item for item in cases if item["id"] == result["case_id"])
            status = "PASS" if result["verified"] else "FAIL"
            css_class = "" if result["verified"] else "fail"
            st.markdown(f'<div class="case-card {css_class}"><span class="case-id">{status} · {case["id"]} · {case["difficulty"]}</span><div class="case-problem">{case["problem"]}</div><span class="small">Model answer: {result.get("final_answer") or "No answer"} &nbsp; {result.get("error_type") or "verified externally"}</span></div>', unsafe_allow_html=True)
            with st.expander(f"Inspect {case['id']}"):
                st.write("Expected:", case["expected_answer"])
                st.write("Model response:", result.get("raw_response") or "No response")
else:
    st.info("No model reports yet. Run the offline self-check, or add a provider key and start a model run from the sidebar.")
    st.subheader("Test set at a glance")
    st.dataframe([{key: case[key] for key in ("id", "category", "difficulty", "verifier")} for case in cases], hide_index=True, use_container_width=True)

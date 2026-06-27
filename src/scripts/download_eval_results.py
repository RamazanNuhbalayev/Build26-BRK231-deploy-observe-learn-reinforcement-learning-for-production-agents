#!/usr/bin/env python3
"""
Download all eval run results for a given evaluation in parallel.
Each run's output items are saved to a separate JSON file.

Usage:
    python scripts/download_eval_results.py [eval_name]

Default eval_name: retail-multi-model-eval-20260529-073055
"""

import os
import sys
import json
import requests
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

# Config
PROJECT_ENDPOINT = os.getenv("PROJECT_ENDPOINT")
BASE_URL = f"{PROJECT_ENDPOINT}/openai"
EVAL_NAME = sys.argv[1] if len(sys.argv) > 1 else "retail-multi-model-eval-20260529-073055"
OUTPUT_DIR = Path(f".eval-results/{EVAL_NAME}")
API_VERSION = "2025-11-15-preview"

credential = DefaultAzureCredential()


def get_headers():
    token = credential.get_token("https://ai.azure.com/.default").token
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def find_eval_id(eval_name):
    """Find eval ID by name."""
    url = f"{BASE_URL}/evals?api-version={API_VERSION}&limit=50"
    resp = requests.get(url, headers=get_headers())
    resp.raise_for_status()
    for e in resp.json().get("data", []):
        if e.get("name") == eval_name:
            return e["id"]
    raise ValueError(f"Eval '{eval_name}' not found")


def list_runs(eval_id):
    """List all runs for an eval."""
    url = f"{BASE_URL}/evals/{eval_id}/runs?api-version={API_VERSION}"
    resp = requests.get(url, headers=get_headers())
    resp.raise_for_status()
    return resp.json().get("data", [])


def download_output_items(eval_id, run_id, run_name):
    """Download all output items for a run with pagination."""
    items = []
    after = None
    page = 0

    while True:
        url = f"{BASE_URL}/evals/{eval_id}/runs/{run_id}/output_items?api-version={API_VERSION}&limit=100"
        if after:
            url += f"&after={after}"

        for attempt in range(3):
            try:
                resp = requests.get(url, headers=get_headers(), timeout=60)
                resp.raise_for_status()
                break
            except Exception as e:
                if attempt == 2:
                    raise
                print(f"  ⚠ Retry {attempt+1} for {run_name} page {page}: {e}")
                time.sleep(2 ** attempt)

        data = resp.json()
        batch = data.get("data", [])
        items.extend(batch)
        page += 1

        if not data.get("has_more", False) or not batch:
            break
        after = batch[-1]["id"]

    return items


def download_run(eval_id, run):
    """Download a single run's results."""
    run_id = run["id"]
    run_name = run.get("name", run_id)
    model_name = run_name.replace(f"-20260529-073055", "").replace("eval-", "")

    print(f"⬇  Downloading: {model_name} ({run['result_counts']['total']} items)...")
    start = time.time()

    items = download_output_items(eval_id, run_id, run_name)

    # Save output items
    output_file = OUTPUT_DIR / f"{model_name}.json"
    with open(output_file, "w") as f:
        json.dump(items, f, indent=2)

    elapsed = time.time() - start
    print(f"✅ {model_name}: {len(items)} items saved ({elapsed:.1f}s)")

    return {
        "model": model_name,
        "run_id": run_id,
        "run_name": run_name,
        "status": run.get("status"),
        "result_counts": run.get("result_counts", {}),
        "file": str(output_file),
        "items_downloaded": len(items),
    }


def main():
    print(f"🔍 Finding eval: {EVAL_NAME}")
    eval_id = find_eval_id(EVAL_NAME)
    print(f"   Eval ID: {eval_id}")

    runs = list_runs(eval_id)
    print(f"   Found {len(runs)} runs\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Download all runs in parallel (one thread per run)
    summaries = []
    with ThreadPoolExecutor(max_workers=min(len(runs), 6)) as executor:
        futures = {executor.submit(download_run, eval_id, run): run for run in runs}
        for future in as_completed(futures):
            try:
                summary = future.result()
                summaries.append(summary)
            except Exception as e:
                run = futures[future]
                print(f"❌ Failed: {run.get('name', run['id'])}: {e}")

    # Save summary
    summaries.sort(key=lambda x: x["model"])
    summary_file = OUTPUT_DIR / "summary.json"
    with open(summary_file, "w") as f:
        json.dump(summaries, f, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ Done! {len(summaries)}/{len(runs)} runs downloaded to {OUTPUT_DIR}/")
    print(f"   Summary: {summary_file}")
    print(f"\nResults:")
    for s in summaries:
        rc = s["result_counts"]
        print(f"   {s['model']:<30} passed={rc.get('passed',0):>3} failed={rc.get('failed',0):>3} total={rc.get('total',0):>3}")


if __name__ == "__main__":
    main()

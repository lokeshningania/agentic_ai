
import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


# ==========================================================
# CONFIGURATION
# ==========================================================

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
OUTPUT_DIR = ROOT / "scripts"

WORKING_FILE = OUTPUT_DIR / "gemini_working_models.csv"
FULL_REPORT_FILE = OUTPUT_DIR / "gemini_agent_model_report.csv"

API_BASE = "https://generativelanguage.googleapis.com/v1beta"

PRIORITY_MODELS = [
    "gemini-3.1-pro-preview",
    "gemini-3.1-pro",
    "gemini-3-pro",
    "gemini-3.1-flash",
    "gemini-3-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

REASONING_PROMPT = """
Solve these three problems. Return the final answers clearly.

1. Calculate 17 multiplied by 19.
2. Find the next number: 2, 6, 12, 20, 30, ?
3. Five machines make five products in five minutes.
   How long will 100 machines take to make 100 products?
"""

EXPECTED_ANSWERS = ["323", "42", "5"]

TOOL_DECLARATION = {
    "functionDeclarations": [
        {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "city": {
                        "type": "STRING",
                        "description": "Name of the city",
                    }
                },
                "required": ["city"],
            },
        }
    ]
}

REPORT_FIELDS = [
    "model",
    "advertised_methods",
    "reasoning",
    "reasoning_latency",
    "tool_calling",
    "tool_latency",
    "structured_output",
    "structured_latency",
    "embedding",
    "embedding_dimensions",
    "embedding_latency",
    "error",
]

WORKING_FIELDS = [
    "model",
    "reasoning",
    "reasoning_latency",
    "tool_calling",
    "tool_latency",
    "structured_output",
    "structured_latency",
    "embedding",
    "embedding_dimensions",
    "embedding_latency",
]


# ==========================================================
# ENVIRONMENT
# ==========================================================

def load_api_key():
    if not ENV_FILE.exists():
        raise FileNotFoundError(f".env not found: {ENV_FILE}")

    for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)

        if key.strip() == "GOOGLE_API_KEY":
            value = value.strip().strip('"').strip("'")

            if value:
                return value

    raise ValueError("GOOGLE_API_KEY is missing or empty in .env")


# ==========================================================
# API
# ==========================================================

class APIError(Exception):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")


def api_request(path, api_key, payload=None):
    url = f"{API_BASE}/{path}"

    request = urllib.request.Request(
        url,
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST" if payload is not None else "GET",
    )

    data = (
        json.dumps(payload).encode("utf-8")
        if payload is not None
        else None
    )

    started = time.perf_counter()

    try:
        with urllib.request.urlopen(
            request,
            data=data,
            timeout=90,
        ) as response:
            body = json.loads(response.read().decode("utf-8"))
            return body, time.perf_counter() - started

    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            message = body.get("error", {}).get("message", str(exc))
        except Exception:
            message = str(exc)

        raise APIError(exc.code, message) from None

    except Exception as exc:
        raise RuntimeError(str(exc)) from None


def generate(model, api_key, payload):
    return api_request(
        f"models/{urllib.parse.quote(model, safe='')}:generateContent",
        api_key,
        payload,
    )


def classify_error(exc):
    if isinstance(exc, APIError):
        if exc.status_code == 404:
            return "UNAVAILABLE"

        if exc.status_code == 429:
            return "QUOTA_BLOCKED"

        if exc.status_code == 403:
            return "ACCESS_DENIED"

        if exc.status_code == 401:
            return "ACCESS_DENIED"

        if exc.status_code == 400:
            return "REQUEST_REJECTED"

    return "ERROR"


def error_text(exc):
    return str(exc).replace("\n", " ")[:1500]


# ==========================================================
# MODEL DISCOVERY
# ==========================================================

def discover_models(api_key):
    models = []
    page_token = None

    while True:
        path = "models?pageSize=1000"

        if page_token:
            path += "&pageToken=" + urllib.parse.quote(page_token)

        response, _ = api_request(path, api_key)

        models.extend(response.get("models", []))
        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return models


def model_priority(model_name):
    name = model_name.lower()

    for index, preferred in enumerate(PRIORITY_MODELS):
        if name == preferred:
            return index

    return len(PRIORITY_MODELS) + 1


def sort_models(models):
    usable = [model for model in models if model.get("name")]

    return sorted(
        usable,
        key=lambda model: (
            model_priority(model["name"].removeprefix("models/")),
            model["name"],
        ),
    )


# ==========================================================
# RESPONSE HELPERS
# ==========================================================

def response_text(response):
    parts = []

    for candidate in response.get("candidates", []):
        content = candidate.get("content", {})

        for part in content.get("parts", []):
            if part.get("text"):
                parts.append(part["text"])

    return "\n".join(parts)


# ==========================================================
# REASONING TEST
# ==========================================================

def test_reasoning(model, api_key):
    response, latency = generate(
        model,
        api_key,
        {
            "contents": [{
                "parts": [{"text": REASONING_PROMPT}]
            }],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 500,
            },
        },
    )

    answer = response_text(response)
    normalized = re.sub(r"[, ]+", "", answer)

    passed = all(
        expected in normalized
        for expected in EXPECTED_ANSWERS
    )

    return {
        "status": "PASS" if passed else "FAIL",
        "latency": round(latency, 3),
        "answer": answer[:1500],
    }


# ==========================================================
# TOOL CALLING TEST
# ==========================================================

def test_tool_calling(model, api_key):
    response, latency = generate(
        model,
        api_key,
        {
            "contents": [{
                "parts": [{
                    "text": (
                        "What is the weather in New Delhi? "
                        "Use the get_weather function."
                    )
                }]
            }],
            "tools": [TOOL_DECLARATION],
            "toolConfig": {
                "functionCallingConfig": {
                    "mode": "ANY",
                    "allowedFunctionNames": ["get_weather"],
                }
            },
        },
    )

    function_calls = []

    for candidate in response.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            function_call = part.get("functionCall")

            if function_call:
                function_calls.append(function_call)

    passed = any(
        call.get("name") == "get_weather"
        for call in function_calls
    )

    return {
        "status": "PASS" if passed else "FAIL",
        "latency": round(latency, 3),
    }


# ==========================================================
# STRUCTURED OUTPUT TEST
# ==========================================================

def test_structured_output(model, api_key):
    response, latency = generate(
        model,
        api_key,
        {
            "contents": [{
                "parts": [{
                    "text": (
                        "Return JSON with keys 'name' and 'age'. "
                        "Use name Alice and age 30."
                    )
                }]
            }],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "maxOutputTokens": 100,
            },
        },
    )

    answer = response_text(response)

    try:
        parsed = json.loads(answer)

        passed = (
            parsed.get("name") == "Alice"
            and parsed.get("age") == 30
        )
    except (json.JSONDecodeError, AttributeError):
        passed = False

    return {
        "status": "PASS" if passed else "FAIL",
        "latency": round(latency, 3),
    }


# ==========================================================
# EMBEDDING TEST
# ==========================================================

def test_embedding(model, api_key):
    response, latency = api_request(
        f"models/{urllib.parse.quote(model, safe='')}:embedContent",
        api_key,
        {
            "model": f"models/{model}",
            "content": {
                "parts": [{
                    "text": "Testing Gemini embedding access."
                }]
            },
        },
    )

    vector = response.get("embedding", {}).get("values", [])

    return {
        "status": "PASS" if vector else "FAIL",
        "dimensions": len(vector),
        "latency": round(latency, 3),
    }


# ==========================================================
# CSV MANAGEMENT
# ==========================================================

def initialize_outputs():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for path, fields in [
        (FULL_REPORT_FILE, REPORT_FIELDS),
        (WORKING_FILE, WORKING_FIELDS),
    ]:
        with path.open("w", newline="", encoding="utf-8-sig") as file:
            csv.DictWriter(file, fieldnames=fields).writeheader()


def append_report(record):
    with FULL_REPORT_FILE.open(
        "a",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=REPORT_FIELDS)
        writer.writerow(record)
        file.flush()


def upsert_working_model(record):
    """Add or update a working model without creating duplicate rows."""
    existing = []

    if WORKING_FILE.exists():
        with WORKING_FILE.open(
            "r",
            newline="",
            encoding="utf-8-sig",
        ) as file:
            existing = list(csv.DictReader(file))

    updated = {
        key: record.get(key, "")
        for key in WORKING_FIELDS
    }

    replaced = False

    for index, row in enumerate(existing):
        if row.get("model") == record["model"]:
            existing[index] = updated
            replaced = True
            break

    if not replaced:
        existing.append(updated)

    with WORKING_FILE.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(file, fieldnames=WORKING_FIELDS)
        writer.writeheader()
        writer.writerows(existing)


# ==========================================================
# MODEL TESTING
# ==========================================================

def initial_record(metadata):
    model = metadata["name"].removeprefix("models/")
    methods = metadata.get("supportedGenerationMethods", [])

    supports_generation = "generateContent" in methods
    supports_embedding = "embedContent" in methods

    return {
        "model": model,
        "advertised_methods": ", ".join(methods),

        "reasoning": "READY" if supports_generation else "NOT_SUPPORTED",
        "reasoning_latency": "",

        "tool_calling": "READY" if supports_generation else "NOT_SUPPORTED",
        "tool_latency": "",

        "structured_output": "READY" if supports_generation else "NOT_SUPPORTED",
        "structured_latency": "",

        "embedding": "READY" if supports_embedding else "NOT_SUPPORTED",
        "embedding_dimensions": "",
        "embedding_latency": "",

        "error": "",
    }


def record_test_error(record, capability, exc):
    status = classify_error(exc)
    message = error_text(exc)

    record[capability] = status

    if record["error"]:
        record["error"] += " | "

    record["error"] += f"{capability}: {message}"

    return status


def mark_generation_unavailable(record, status, message):
    for field in ("reasoning", "tool_calling", "structured_output"):
        if record[field] == "READY":
            record[field] = status

    if message and message not in record["error"]:
        if record["error"]:
            record["error"] += " | "
        record["error"] += message


def test_model(metadata, api_key, skip_tool_tests, skip_embeddings):
    record = initial_record(metadata)
    model = record["model"]

    if "generateContent" in metadata.get("supportedGenerationMethods", []):
        print("  Reasoning test...", flush=True)

        try:
            result = test_reasoning(model, api_key)
            record["reasoning"] = result["status"]
            record["reasoning_latency"] = result["latency"]

            print(
                f"  Reasoning: {record['reasoning']}",
                flush=True,
            )

        except Exception as exc:
            status = record_test_error(record, "reasoning", exc)

            print(f"  Reasoning: {status}", flush=True)

            if status == "UNAVAILABLE":
                mark_generation_unavailable(
                    record,
                    "UNAVAILABLE",
                    "Model is unavailable for generateContent.",
                )
                return record

        if not skip_tool_tests:
            print("  Function calling test...", flush=True)

            try:
                result = test_tool_calling(model, api_key)
                record["tool_calling"] = result["status"]
                record["tool_latency"] = result["latency"]

                print(
                    f"  Tool calling: {record['tool_calling']}",
                    flush=True,
                )

            except Exception as exc:
                status = record_test_error(record, "tool_calling", exc)
                print(f"  Tool calling: {status}", flush=True)

                if status == "UNAVAILABLE":
                    mark_generation_unavailable(
                        record,
                        "UNAVAILABLE",
                        "Model is unavailable for generateContent.",
                    )
                    return record

            print("  Structured output test...", flush=True)

            try:
                result = test_structured_output(model, api_key)
                record["structured_output"] = result["status"]
                record["structured_latency"] = result["latency"]

                print(
                    f"  Structured output: {record['structured_output']}",
                    flush=True,
                )

            except Exception as exc:
                status = record_test_error(
                    record,
                    "structured_output",
                    exc,
                )
                print(f"  Structured output: {status}", flush=True)

                if status == "UNAVAILABLE":
                    mark_generation_unavailable(
                        record,
                        "UNAVAILABLE",
                        "Model is unavailable for generateContent.",
                    )
                    return record

        else:
            record["tool_calling"] = "NOT_TESTED_BY_OPTION"
            record["structured_output"] = "NOT_TESTED_BY_OPTION"

    if "embedContent" in metadata.get("supportedGenerationMethods", []):
        if skip_embeddings:
            record["embedding"] = "NOT_TESTED_BY_OPTION"
        else:
            print("  Embedding test...", flush=True)

            try:
                result = test_embedding(model, api_key)
                record["embedding"] = result["status"]
                record["embedding_dimensions"] = result["dimensions"]
                record["embedding_latency"] = result["latency"]

                print(
                    f"  Embedding: {record['embedding']} "
                    f"({record['embedding_dimensions']} dimensions)",
                    flush=True,
                )

            except Exception as exc:
                status = record_test_error(record, "embedding", exc)
                print(f"  Embedding: {status}", flush=True)

    return record


# ==========================================================
# IMMEDIATE NOTIFICATION
# ==========================================================

def announce_working_model(record):
    print("\n" + "=" * 75, flush=True)
    print("WORKING REASONING MODEL FOUND!", flush=True)
    print(f"Model: {record['model']}", flush=True)
    print(f"Reasoning: {record['reasoning']}", flush=True)
    print(f"Tool calling: {record['tool_calling']}", flush=True)
    print(f"Structured output: {record['structured_output']}", flush=True)
    print(f"Saved to: {WORKING_FILE}", flush=True)
    print("=" * 75 + "\n", flush=True)


# ==========================================================
# MAIN
# ==========================================================

def main():
    parser = argparse.ArgumentParser(
        description="Discover Gemini models for agentic AI workloads."
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between models in seconds.",
    )

    parser.add_argument(
        "--skip-tool-tests",
        action="store_true",
        help="Skip function calling and structured output tests.",
    )

    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip embedding tests.",
    )

    args = parser.parse_args()

    print("=" * 75)
    print("GEMINI AGENT MODEL DISCOVERY")
    print("=" * 75, flush=True)

    try:
        api_key = load_api_key()
        print("API key loaded successfully (hidden).")

        models = sort_models(discover_models(api_key))

    except Exception as exc:
        print(f"\n[ERROR] {exc}")
        sys.exit(1)

    initialize_outputs()

    print(f"\nDiscovered {len(models)} models.")
    print("Testing priority models first.")
    print("Retired models will be marked UNAVAILABLE.")
    print("Unsupported capabilities will be marked NOT_SUPPORTED.\n")

    working_count = 0

    for index, metadata in enumerate(models, start=1):
        model = metadata["name"].removeprefix("models/")

        print(
            f"\n[{index}/{len(models)}] {model}",
            flush=True,
        )

        record = test_model(
            metadata,
            api_key,
            args.skip_tool_tests,
            args.skip_embeddings,
        )

        if record["reasoning"] == "PASS":
            working_count += 1
            upsert_working_model(record)
            announce_working_model(record)

        append_report(record)

        time.sleep(max(0, args.delay))

    print("\n" + "=" * 75)
    print("DISCOVERY COMPLETED")
    print("=" * 75)
    print(f"Models examined: {len(models)}")
    print(f"Models passing reasoning: {working_count}")
    print(f"Working models: {WORKING_FILE}")
    print(f"Full report: {FULL_REPORT_FILE}")


if __name__ == "__main__":
    main()

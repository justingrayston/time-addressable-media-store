# Coding Agent Guidelines (AGENT.md)

Welcome, Agent! This repository implements the Google Cloud Platform (GCP) reference backend for the BBC's Time Addressable Media Store (TAMS) specification.

To maintain the security, reliability, and functional correctness of this codebase, please adhere to the following mandatory guidelines.

---

## 1. Context Gathering First

Before suggesting or implementing any codebase changes:
1. **Read [README.md](README.md) first**: Familiarize yourself with the deployment stages (Terraform infrastructure vs. Cloud Run images), environment variable configurations, and local execution paths.
2. **Review [app/main.py](app/main.py)**: Ensure you fully understand the API models, routes, and query patterns.

---

## 2. Mandatory Security & Code Quality Standards

When writing, refactoring, or optimizing endpoints, you must proactively audit your work against these core security policies:

### A. Input Sanitization & Path Traversal Prevention
* **Segment Object IDs**: Always validate segment `object_id` fields against `UUID_REGEX` (`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`) to prevent directory traversal attempts (e.g. `../../another-flow/sensitive-file`) from injecting invalid paths into Cloud Storage signed URL formats.
* **Tag Names**: Strict input sanitization is mandatory for document-level tags. Tag names must match `TAG_NAME_REGEX` (`^[a-zA-Z0-9_-]+$`) to prevent dot-notation injection into nested field updates in Cloud Firestore (e.g. updating fields like `tags.some.field`).

### B. Plaintext Secrets Mitigation
* **Credential Protection**: Webhook API keys (`api_key_value`) must **never** be stored in Firestore as plaintext or exposed in API response models (like `Webhook`).
* **Symmetric Encryption**: Always encrypt webhook keys on write/update using AES symmetric Fernet encryption, derived from `WEBHOOK_ENCRYPTION_KEY`. Ensure keys can be decrypted at runtime by internal event triggers, but never leak back to clients.

### C. Resource Efficiency & Firestore Query Limits
* **Range Filters**: Avoid fetching and filtering records memory-side in Python. Offload query boundaries directly to Firestore using index-friendly inequality filters (`timerange_start` / `timerange_end`).
* **Memory Protection (No OOMs)**: Never load entire databases into RAM. Always apply reasonable `limit` constraints on stream/list retrievals.
* **Streaming Deletes**: For sub-range deletes, use `.stream()` to sequentially purge matching Firestore references, avoiding batch memory exhaustion.

---

## 3. Local Test Suite & Coverage Verification

We maintain a target of **97%+ code coverage** across the application logic. Under no circumstances should tests be bypassed or coverage degraded.

### Running the Test Suite Offline
We have implemented clean, stateful, offline mocks for Firestore, GCS, and Google IAM Authentication inside [tests/conftest.py](tests/conftest.py). **Never make actual outbound calls to real GCP APIs or metadata endpoints during testing.**

To execute tests and verify your changes:
```bash
# 1. Activate the python virtual environment
source venv/bin/activate

# 2. Run the test suite with coverage reporting
PYTHONPATH=. pytest tests/ -v --cov=app --cov-report=term-missing
```

### Writing New Tests
If you add or alter an endpoint in `app/main.py`, you must update [tests/test_main.py](tests/test_main.py) to cover your new code. Assertions must cover:
* Success paths.
* Error/validation handling (e.g., input format failures, not found states).
* Correct mock state updates (e.g., verifying database documents actually got set/deleted in `mock_gcp_services.store`).

import pytest
import datetime
import uuid
import base64
import hashlib
from cryptography.fernet import Fernet
from app.main import TAG_NAME_REGEX, UUID_REGEX

def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == ["service", "flows", "sources", "flow-delete-requests"]

def test_get_service_default(client, mock_gcp_services):
    # Ensure Firestore is empty for service/info
    mock_gcp_services.store.clear()
    
    response = client.get("/service")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "TAMS GCP Service"
    assert data["api_version"] == "8.0"
    assert data["type"] == "urn:x-tams:service.gcp"
    
    # Check that it got saved in Firestore
    saved_doc = mock_gcp_services.store.get("service/info")
    assert saved_doc is not None
    assert saved_doc["name"] == "TAMS GCP Service"

def test_get_service_existing(client, mock_gcp_services):
    mock_gcp_services.store["service/info"] = {
        "name": "Custom TAMS Service",
        "description": "My custom service",
        "type": "urn:x-tams:service.custom",
        "api_version": "9.0",
        "min_object_timeout": "100:0"
    }
    response = client.get("/service")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Custom TAMS Service"
    assert data["api_version"] == "9.0"

def test_post_service(client, mock_gcp_services):
    mock_gcp_services.store["service/info"] = {
        "name": "Initial Name",
        "description": "Initial Description"
    }
    
    # 1. Update name and description
    response = client.post("/service", json={"name": "New Name", "description": "New Desc"})
    assert response.status_code == 200
    assert response.json() == {"message": "Service info updated"}
    
    saved = mock_gcp_services.store["service/info"]
    assert saved["name"] == "New Name"
    assert saved["description"] == "New Desc"

    # 2. Post empty updates
    response = client.post("/service", json={})
    assert response.status_code == 200
    assert response.json() == {"message": "No updates provided"}

def test_sources_endpoints(client, mock_gcp_services):
    # Setup mock sources
    mock_gcp_services.store["sources/source-1"] = {
        "id": "source-1",
        "format": "video",
        "label": "Source One",
        "description": "First source"
    }
    mock_gcp_services.store["sources/source-2"] = {
        "id": "source-2",
        "format": "audio",
        "label": "Source Two",
        "description": "Second source"
    }

    # 1. Get Sources
    response = client.get("/sources?limit=2")
    assert response.status_code == 200
    assert len(response.json()) == 2

    # 2. Get Single Source (Exists)
    response = client.get("/sources/source-1")
    assert response.status_code == 200
    assert response.json()["id"] == "source-1"

    # 3. Get Single Source (Not Exists)
    response = client.get("/sources/source-missing")
    assert response.status_code == 404
    assert response.json()["detail"] == "Source not found"

    # 4. Put Source Label
    response = client.put("/sources/source-1/label", json="Updated Label")
    assert response.status_code == 204
    assert mock_gcp_services.store["sources/source-1"]["label"] == "Updated Label"

    # Put label for missing source
    response = client.put("/sources/source-missing/label", json="Bad Label")
    assert response.status_code == 404

    # 5. Delete Source Label
    response = client.delete("/sources/source-1/label")
    assert response.status_code == 204
    assert "label" not in mock_gcp_services.store["sources/source-1"]

    # Delete label for missing source
    response = client.delete("/sources/source-missing/label")
    assert response.status_code == 404

    # 6. Put Source Description
    response = client.put("/sources/source-1/description", json="Updated Description")
    assert response.status_code == 204
    assert mock_gcp_services.store["sources/source-1"]["description"] == "Updated Description"

    # Put description for missing source
    response = client.put("/sources/source-missing/description", json="Bad Desc")
    assert response.status_code == 404

    # 7. Delete Source Description
    response = client.delete("/sources/source-1/description")
    assert response.status_code == 204
    assert "description" not in mock_gcp_services.store["sources/source-1"]

    # Delete description for missing source
    response = client.delete("/sources/source-missing/description")
    assert response.status_code == 404

def test_sources_tags_endpoints(client, mock_gcp_services):
    mock_gcp_services.store["sources/source-tags"] = {
        "id": "source-tags",
        "format": "video",
        "tags": {}
    }

    # 1. Put Valid Tag
    response = client.put("/sources/source-tags/tags/valid_tag-123", json="some-value")
    assert response.status_code == 204
    assert mock_gcp_services.store["sources/source-tags"]["tags"]["valid_tag-123"] == "some-value"

    # 2. Put Invalid Tag Name (containing dot/special characters)
    response = client.put("/sources/source-tags/tags/invalid.tag", json="some-value")
    assert response.status_code == 400
    assert "Invalid tag name format" in response.json()["detail"]

    # Put tag for missing source
    response = client.put("/sources/source-missing/tags/some-tag", json="val")
    assert response.status_code == 404

    # 3. Delete Tag
    response = client.delete("/sources/source-tags/tags/valid_tag-123")
    assert response.status_code == 204
    assert "valid_tag-123" not in mock_gcp_services.store["sources/source-tags"]["tags"]

    # Delete Invalid Tag Name (prevent dot injection in delete too)
    response = client.delete("/sources/source-tags/tags/invalid.tag")
    assert response.status_code == 400

    # Delete tag for missing source
    response = client.delete("/sources/source-missing/tags/some-tag")
    assert response.status_code == 404

def test_flows_endpoints(client, mock_gcp_services):
    # Setup database state
    mock_gcp_services.store.clear()

    flow_id = "flow-123"
    source_id = "source-123"
    flow_payload = {
        "id": flow_id,
        "source_id": source_id,
        "format": "video/mp2t",
        "label": "My Flow"
    }

    # 1. Put Flow - Brand New (Source does not exist -> auto-created)
    response = client.put(f"/flows/{flow_id}", json=flow_payload)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["id"] == flow_id
    assert "created" in res_data
    
    # Check flow saved
    assert f"flows/{flow_id}" in mock_gcp_services.store
    # Check source auto-created
    assert f"sources/{source_id}" in mock_gcp_services.store
    assert mock_gcp_services.store[f"sources/{source_id}"]["label"] == f"Auto-created Source for Flow {flow_id}"

    # 2. Put Flow - Update existing
    flow_payload["label"] = "My Updated Flow"
    response = client.put(f"/flows/{flow_id}", json=flow_payload)
    assert response.status_code == 204
    assert mock_gcp_services.store[f"flows/{flow_id}"]["label"] == "My Updated Flow"
    assert "metadata_updated" in mock_gcp_services.store[f"flows/{flow_id}"]

    # 3. Get Flows List
    response = client.get("/flows")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == flow_id

    # 4. Get Flow (Exists)
    response = client.get(f"/flows/{flow_id}")
    assert response.status_code == 200
    assert response.json()["label"] == "My Updated Flow"

    # Get Flow (Not Exists)
    response = client.get("/flows/flow-missing")
    assert response.status_code == 404

    # 5. Delete Flow (Exists)
    response = client.delete(f"/flows/{flow_id}")
    assert response.status_code == 204
    assert f"flows/{flow_id}" not in mock_gcp_services.store

    # Delete Flow (Not Exists)
    response = client.delete(f"/flows/{flow_id}")
    assert response.status_code == 404

def test_segments_create_validation(client, mock_gcp_services):
    flow_id = "flow-segments"
    # Seed flow
    mock_gcp_services.store[f"flows/{flow_id}"] = {
        "id": flow_id,
        "source_id": "src-123",
        "format": "video/mp2t"
    }

    # 1. Post single segment with invalid flow ID (404)
    response = client.post("/flows/missing-flow/segments", json={
        "object_id": str(uuid.uuid4()),
        "timerange": "0:0_10:0"
    })
    assert response.status_code == 404
    assert response.json()["detail"] == "Flow not found"

    # 2. Post segment with invalid object_id format (directory traversal attempt)
    response = client.post(f"/flows/{flow_id}/segments", json={
        "object_id": "../another-flow/sensitive-file",
        "timerange": "0:0_10:0"
    })
    assert response.status_code == 200
    failed = response.json().get("failed_segments", [])
    assert len(failed) == 1
    assert failed[0]["object_id"] == "../another-flow/sensitive-file"
    assert "Invalid object_id format" in failed[0]["error"]

    # 3. Post segment with invalid timerange format
    response = client.post(f"/flows/{flow_id}/segments", json={
        "object_id": str(uuid.uuid4()),
        "timerange": "invalid-timerange-syntax"
    })
    assert response.status_code == 200
    failed = response.json().get("failed_segments", [])
    assert len(failed) == 1
    assert "invalid-timerange-syntax" in failed[0]["timerange"]
    assert failed[0]["error"] != ""

def test_segments_create_overlap(client, mock_gcp_services):
    flow_id = "flow-segments"
    mock_gcp_services.store[f"flows/{flow_id}"] = {
        "id": flow_id,
        "source_id": "src-123",
        "format": "video/mp2t"
    }

    # Set up an existing segment
    # 0:0 to 10:0 maps to nanoseconds: 0 to 10000000000
    existing_obj_id = str(uuid.uuid4())
    mock_gcp_services.store["segments/seg-existing"] = {
        "flow_id": flow_id,
        "object_id": existing_obj_id,
        "timerange": "0:0_10:0",
        "timerange_start": 0,
        "timerange_end": 10000000000
    }

    # Attempt to post overlapping segment: 5:0 to 15:0 (starts at 5000000000)
    overlapping_obj_id = str(uuid.uuid4())
    response = client.post(f"/flows/{flow_id}/segments", json={
        "object_id": overlapping_obj_id,
        "timerange": "5:0_15:0"
    })
    assert response.status_code == 200
    failed = response.json().get("failed_segments", [])
    assert len(failed) == 1
    assert failed[0]["object_id"] == overlapping_obj_id
    assert "overlaps" in failed[0]["error"]

    # Post non-overlapping segment: 15:0 to 20:0 (starts at 15000000000)
    new_obj_id = str(uuid.uuid4())
    response = client.post(f"/flows/{flow_id}/segments", json={
        "object_id": new_obj_id,
        "timerange": "15:0_20:0"
    })
    assert response.status_code == 201
    assert response.json() == {"message": "Segments created successfully"}

def test_segments_get_timerange_limit(client, mock_gcp_services):
    flow_id = "flow-get-segments"
    # Seed several segments
    # s1: 0-10, s2: 10-20, s3: 20-30
    mock_gcp_services.store["segments/s1"] = {
        "flow_id": flow_id,
        "object_id": str(uuid.uuid4()),
        "timerange": "0:0_10:0",
        "timerange_start": 0,
        "timerange_end": 10000000000
    }
    mock_gcp_services.store["segments/s2"] = {
        "flow_id": flow_id,
        "object_id": str(uuid.uuid4()),
        "timerange": "10:0_20:0",
        "timerange_start": 10000000000,
        "timerange_end": 20000000000
    }
    mock_gcp_services.store["segments/s3"] = {
        "flow_id": flow_id,
        "object_id": str(uuid.uuid4()),
        "timerange": "20:0_30:0",
        "timerange_start": 20000000000,
        "timerange_end": 30000000000
    }

    # 1. Get all with limit=2
    response = client.get(f"/flows/{flow_id}/segments?limit=2")
    assert response.status_code == 200
    assert len(response.json()) == 2

    # 2. Get with timerange filter (overlaps with 15:0_25:0 -> matches s2 and s3)
    response = client.get(f"/flows/{flow_id}/segments?timerange=15:0_25:0")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    ranges = [item["timerange"] for item in data]
    assert "10:0_20:0" in ranges
    assert "20:0_30:0" in ranges

    # 3. Get with invalid timerange format
    response = client.get(f"/flows/{flow_id}/segments?timerange=badrange")
    assert response.status_code == 400
    assert "Invalid timerange" in response.json()["detail"]

def test_segments_get_presigned(client, mock_gcp_services, monkeypatch):
    flow_id = "flow-presigned"
    obj_id = str(uuid.uuid4())
    mock_gcp_services.store["segments/s_presigned"] = {
        "flow_id": flow_id,
        "object_id": obj_id,
        "timerange": "0:0_10:0",
        "timerange_start": 0,
        "timerange_end": 10000000000
    }

    # 1. Request presigned URL (without service account config)
    response = client.get(f"/flows/{flow_id}/segments?presigned=True")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "get_urls" in data[0]
    expected_url = f"https://storage.googleapis.com/test-bucket/{flow_id}/{obj_id}?method=GET&content-type=video/mp2t"
    assert data[0]["get_urls"][0]["url"] == expected_url

    # 2. Request presigned URL (WITH service account config)
    monkeypatch.setenv("SERVICE_ACCOUNT_EMAIL", "sa@test-project.iam.gserviceaccount.com")
    response = client.get(f"/flows/{flow_id}/segments?presigned=True")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "get_urls" in data[0]

def test_segments_delete(client, mock_gcp_services):
    flow_id = "flow-delete"
    # Seed 3 segments
    mock_gcp_services.store["segments/d1"] = {
        "flow_id": flow_id,
        "object_id": str(uuid.uuid4()),
        "timerange": "0:0_10:0",
        "timerange_start": 0,
        "timerange_end": 10000000000
    }
    mock_gcp_services.store["segments/d2"] = {
        "flow_id": flow_id,
        "object_id": str(uuid.uuid4()),
        "timerange": "10:0_20:0",
        "timerange_start": 10000000000,
        "timerange_end": 20000000000
    }
    mock_gcp_services.store["segments/d3"] = {
        "flow_id": flow_id,
        "object_id": str(uuid.uuid4()),
        "timerange": "20:0_30:0",
        "timerange_start": 20000000000,
        "timerange_end": 30000000000
    }

    # 1. Delete with invalid timerange
    response = client.delete(f"/flows/{flow_id}/segments?timerange=invalid")
    assert response.status_code == 400

    # 2. Delete subrange: 10:0 to 20:0 (only d2 is fully contained)
    # TAMS deletion criteria: query.where("timerange_start", ">=", start_ns).where("timerange_end", "<=", end_ns)
    # d2 is start=10, end=20.
    response = client.delete(f"/flows/{flow_id}/segments?timerange=10:0_20:0")
    assert response.status_code == 204
    assert "segments/d2" not in mock_gcp_services.store
    assert "segments/d1" in mock_gcp_services.store
    assert "segments/d3" in mock_gcp_services.store

    # 3. Delete all segments for the flow
    response = client.delete(f"/flows/{flow_id}/segments")
    assert response.status_code == 204
    assert "segments/d1" not in mock_gcp_services.store
    assert "segments/d3" not in mock_gcp_services.store

def test_storage_backends(client, mock_gcp_services):
    # Clear collection
    mock_gcp_services.store.clear()

    # 1. Seed & fetch storage backends (first call seeds default)
    response = client.get("/service/storage-backends")
    assert response.status_code == 200
    backends = response.json()
    assert len(backends) == 1
    assert backends[0]["id"] == "default-gcs-backend"
    
    assert "storage_backends/default-gcs-backend" in mock_gcp_services.store

    # 2. Fetch again (this call parses documents from the database)
    response = client.get("/service/storage-backends")
    assert response.status_code == 200
    backends = response.json()
    assert len(backends) == 1
    assert backends[0]["id"] == "default-gcs-backend"

def test_webhooks_crud(client, mock_gcp_services):
    mock_gcp_services.store.clear()

    webhook_payload = {
        "url": "https://callback.my/events",
        "api_key_name": "x-api-key",
        "api_key_value": "secret_plain_key",
        "events": ["segments.created"]
    }

    # 1. Create Webhook (POST)
    response = client.post("/service/webhooks", json=webhook_payload)
    assert response.status_code == 201
    webhook_res = response.json()
    webhook_id = webhook_res["id"]
    assert webhook_res["url"] == webhook_payload["url"]
    assert "api_key_value" not in webhook_res  # Plaintext key must NOT be leaked in standard responses

    # Check ciphertext is in firestore
    saved_doc = mock_gcp_services.store[f"webhooks/{webhook_id}"]
    assert saved_doc["api_key_value"] != "secret_plain_key"
    
    # Verify we can decrypt it using the Fernet instance in main
    from app.main import fernet
    decrypted = fernet.decrypt(saved_doc["api_key_value"].encode()).decode()
    assert decrypted == "secret_plain_key"

    # 2. Get Webhooks List (GET)
    response = client.get("/service/webhooks")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == webhook_id
    assert "api_key_value" not in response.json()[0]

    # 3. Get Single Webhook
    response = client.get(f"/service/webhooks/{webhook_id}")
    assert response.status_code == 200
    assert response.json()["id"] == webhook_id
    assert "api_key_value" not in response.json()

    # Get Single Webhook (Not Found)
    response = client.get("/service/webhooks/missing-webhook")
    assert response.status_code == 404

    # 4. Update Webhook (PUT)
    webhook_payload["api_key_value"] = "new_secret_key"
    response = client.put(f"/service/webhooks/{webhook_id}", json=webhook_payload)
    assert response.status_code == 200
    assert response.json()["id"] == webhook_id
    assert "api_key_value" not in response.json()

    # Verify re-encryption in Firestore
    saved_doc = mock_gcp_services.store[f"webhooks/{webhook_id}"]
    decrypted = fernet.decrypt(saved_doc["api_key_value"].encode()).decode()
    assert decrypted == "new_secret_key"

    # Update Webhook (Not Found)
    response = client.put("/service/webhooks/missing-webhook", json=webhook_payload)
    assert response.status_code == 404

    # 5. Delete Webhook (DELETE)
    response = client.delete(f"/service/webhooks/{webhook_id}")
    assert response.status_code == 204
    assert f"webhooks/{webhook_id}" not in mock_gcp_services.store

    # Delete Webhook (Not Found)
    response = client.delete(f"/service/webhooks/{webhook_id}")
    assert response.status_code == 404

def test_allocate_storage(client, mock_gcp_services, monkeypatch):
    flow_id = "flow-storage"
    
    # 1. Allocate for missing flow
    response = client.post(f"/flows/{flow_id}/storage", json={"limit": 2})
    assert response.status_code == 404
    assert response.json()["detail"] == "Flow not found"

    # Seed flow
    mock_gcp_services.store[f"flows/{flow_id}"] = {
        "id": flow_id,
        "source_id": "src-123",
        "format": "video/mp2t"
    }

    # 2. Allocate with limit (without service account config)
    response = client.post(f"/flows/{flow_id}/storage", json={"limit": 2})
    assert response.status_code == 201
    media_objects = response.json()["media_objects"]
    assert len(media_objects) == 2
    for obj in media_objects:
        assert "object_id" in obj
        assert "put_url" in obj
        url = obj["put_url"]["url"]
        assert url.startswith("https://storage.googleapis.com/test-bucket/")
        assert "method=PUT" in url
        assert "content-type=video/mp2t" in url

    # 3. Allocate with limit (WITH service account config)
    monkeypatch.setenv("SERVICE_ACCOUNT_EMAIL", "sa@test-project.iam.gserviceaccount.com")
    response = client.post(f"/flows/{flow_id}/storage", json={"limit": 1})
    assert response.status_code == 201
    media_objects = response.json()["media_objects"]
    assert len(media_objects) == 1

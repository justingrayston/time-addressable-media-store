import pytest
from fastapi.testclient import TestClient
import uuid
import sys
from unittest.mock import MagicMock

# Create a mock sentinel for firestore.DELETE_FIELD
class DeleteFieldSentinel:
    def __repr__(self):
        return "<DELETE_FIELD>"

DELETE_FIELD = DeleteFieldSentinel()

# Mock Firestore classes
class MockDocumentSnapshot:
    def __init__(self, reference, data, exists):
        self.reference = reference
        self._data = data
        self.exists = exists

    def to_dict(self):
        return dict(self._data) if self._data is not None else None

class MockDocumentReference:
    def __init__(self, collection, doc_id, client):
        self.collection = collection
        self.id = doc_id
        self.client = client

    def get(self):
        doc_path = f"{self.collection.name}/{self.id}"
        if doc_path in self.client.store:
            return MockDocumentSnapshot(self, self.client.store[doc_path], True)
        return MockDocumentSnapshot(self, None, False)

    def set(self, data, merge=False):
        doc_path = f"{self.collection.name}/{self.id}"
        if merge and doc_path in self.client.store:
            self.client.store[doc_path].update(data)
        else:
            self.client.store[doc_path] = dict(data)

    def update(self, data):
        doc_path = f"{self.collection.name}/{self.id}"
        if doc_path not in self.client.store:
            raise Exception("Document not found")
        
        doc_data = self.client.store[doc_path]
        for k, v in data.items():
            if v is DELETE_FIELD:
                if "." in k:
                    parent, child = k.split(".", 1)
                    if parent in doc_data and isinstance(doc_data[parent], dict) and child in doc_data[parent]:
                        del doc_data[parent][child]
                else:
                    if k in doc_data:
                        del doc_data[k]
            elif "." in k:
                parent, child = k.split(".", 1)
                if parent not in doc_data or not isinstance(doc_data[parent], dict):
                    doc_data[parent] = {}
                doc_data[parent][child] = v
            else:
                doc_data[k] = v

    def delete(self):
        doc_path = f"{self.collection.name}/{self.id}"
        if doc_path in self.client.store:
            del self.client.store[doc_path]

class MockCollectionReference:
    def __init__(self, name, client):
        self.name = name
        self.client = client

    def document(self, doc_id):
        return MockDocumentReference(self, doc_id, self.client)

    def add(self, data):
        doc_id = str(uuid.uuid4())
        doc_ref = self.document(doc_id)
        doc_ref.set(data)
        return None, doc_ref

    def where(self, field, op, value):
        return MockQuery(self.name, self.client).where(field, op, value)

    def limit(self, limit_val):
        return MockQuery(self.name, self.client).limit(limit_val)

    def get(self):
        return MockQuery(self.name, self.client).get()

    def stream(self):
        return MockQuery(self.name, self.client).stream()

class MockQuery:
    def __init__(self, collection_name, client, constraints=None, limit_val=None):
        self.collection_name = collection_name
        self.client = client
        self.constraints = constraints or []
        self.limit_val = limit_val

    def where(self, field, op, value):
        new_constraints = list(self.constraints)
        new_constraints.append((field, op, value))
        return MockQuery(self.collection_name, self.client, new_constraints, self.limit_val)

    def limit(self, limit_val):
        return MockQuery(self.collection_name, self.client, self.constraints, limit_val)

    def _execute(self):
        docs = []
        prefix = f"{self.collection_name}/"
        for doc_path, data in sorted(self.client.store.items()):
            if doc_path.startswith(prefix):
                doc_id = doc_path[len(prefix):]
                doc_ref = MockDocumentReference(MockCollectionReference(self.collection_name, self.client), doc_id, self.client)
                docs.append(MockDocumentSnapshot(doc_ref, data, True))

        filtered = []
        for doc in docs:
            data = doc.to_dict()
            match = True
            for field, op, val in self.constraints:
                field_val = data.get(field)
                if op == "==":
                    if field_val != val:
                        match = False
                        break
                elif op == "<=":
                    if field_val is None or field_val > val:
                        match = False
                        break
                elif op == ">=":
                    if field_val is None or field_val < val:
                        match = False
                        break
                elif op == "<":
                    if field_val is None or field_val >= val:
                        match = False
                        break
                elif op == ">":
                    if field_val is None or field_val <= val:
                        match = False
                        break
            if match:
                filtered.append(doc)

        if self.limit_val is not None:
            filtered = filtered[:self.limit_val]

        return filtered

    def get(self):
        return self._execute()

    def stream(self):
        return iter(self._execute())

class MockFirestoreClient:
    def __init__(self, database=None):
        self.database = database
        self.store = {}

    def collection(self, collection_name):
        return MockCollectionReference(collection_name, self)

# Mock GCS classes
class MockBlob:
    def __init__(self, bucket, name):
        self.bucket = bucket
        self.name = name

    def generate_signed_url(self, **kwargs):
        method = kwargs.get("method", "GET")
        content_type = kwargs.get("content_type", "video/mp2t")
        return f"https://storage.googleapis.com/{self.bucket.name}/{self.name}?method={method}&content-type={content_type}"

class MockBucket:
    def __init__(self, name):
        self.name = name

    def blob(self, name):
        return MockBlob(self, name)

class MockStorageClient:
    def bucket(self, name):
        return MockBucket(name)

# Fixtures
@pytest.fixture(autouse=True)
def mock_gcp_services(monkeypatch):
    # Set mock environment variables
    monkeypatch.setenv("FIRESTORE_DB_NAME", "test-db")
    monkeypatch.setenv("TAMS_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("WEBHOOK_ENCRYPTION_KEY", "test-key-of-any-arbitrary-length-to-be-hashed")

    # Mock the firestore client
    mock_db = MockFirestoreClient()
    monkeypatch.setattr("google.cloud.firestore.Client", lambda database=None: mock_db)
    
    # Mock firestore.DELETE_FIELD
    monkeypatch.setattr("google.cloud.firestore.DELETE_FIELD", DELETE_FIELD)

    # Mock the storage client
    monkeypatch.setattr("google.cloud.storage.Client", lambda: MockStorageClient())

    # Mock google.auth and transport requests to avoid real GCP metadata/credentials calls
    class MockCredentials:
        def __init__(self):
            self.token = "test-token"
        def refresh(self, request):
            pass

    import google.auth
    import google.auth.transport.requests
    
    mock_creds = MockCredentials()
    monkeypatch.setattr(google.auth, "default", lambda: (mock_creds, "test-project"))
    monkeypatch.setattr(google.auth.transport.requests, "Request", MagicMock)

    # Re-import app.main so that it picks up the mocked firestore and storage clients
    if "app.main" in sys.modules:
        del sys.modules["app.main"]

    import app.main
    app.main.db = mock_db
    
    yield mock_db

@pytest.fixture
def client():
    import app.main
    from fastapi.testclient import TestClient
    with TestClient(app.main.app) as c:
        yield c

# Wait, TestClient should be returned directly
@pytest.fixture
def test_client():
    import app.main
    return TestClient(app.main.app)

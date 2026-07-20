import os
import sys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add api directory to sys.path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import Base, get_db
from api.main import app
from api.models import Transaction

# Setup test database
TEST_DB_FILE = "test_fraud_detection.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///./{TEST_DB_FILE}"

# Remove existing test DB file if it exists
if os.path.exists(TEST_DB_FILE):
    try:
        os.remove(TEST_DB_FILE)
    except OSError:
        pass

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override get_db dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create tables in the test in-memory database
Base.metadata.create_all(bind=engine)

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "model_loaded" in data

def test_predict():
    # Simple transaction payload
    payload = {
        "Time": 1.0,
        "Amount": 100.0,
        **{f"V{i}": 0.0 for i in range(1, 29)}
    }
    
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "predicted_class" in data
    assert "predicted_probability" in data
    assert "is_fraud" in data
    assert data["is_fraud"] is False or data["is_fraud"] is True

def test_simulate():
    response = client.post("/simulate?fraud_probability=0.2")
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "amount" in data
    assert "predicted_class" in data

def test_transactions():
    # Ensure there is at least one transaction
    client.post("/simulate")
    
    response = client.get("/transactions?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert "amount" in data[0]

def test_statistics():
    # Run a prediction to make sure we have data
    client.post("/simulate")
    
    response = client.get("/statistics")
    assert response.status_code == 200
    data = response.json()
    assert "total_transactions" in data
    assert "fraud_count" in data
    assert "fraud_rate" in data
    assert data["total_transactions"] >= 1

if __name__ == "__main__":
    print("Running API tests...")
    test_health()
    print("Health check endpoint OK!")
    test_predict()
    print("Predict endpoint OK!")
    test_simulate()
    print("Simulate endpoint OK!")
    test_transactions()
    print("Transactions list endpoint OK!")
    test_statistics()
    print("Statistics endpoint OK!")
    
    # Cleanup test DB file
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
            print("Cleanup: Removed test database file.")
        except OSError as e:
            print(f"Cleanup warning: Could not remove test database file: {e}")
            
    print("All backend API endpoints verified successfully!")

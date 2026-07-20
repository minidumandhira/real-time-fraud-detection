import uvicorn
import os

if __name__ == "__main__":
    # Start FastAPI server on port 8000
    print("Starting Fraud Detection System API...")
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

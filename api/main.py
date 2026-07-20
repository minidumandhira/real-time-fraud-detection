import os
import json
import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import joblib
from typing import List, Optional, Dict

import asyncio
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func

from .database import engine, Base, get_db
from .models import Transaction
from .schemas import (
    TransactionCreate,
    TransactionResponse,
    PredictionResponse,
    StatisticsResponse,
    SHAPContribution,
    ExplanationResponse
)

app = FastAPI(
    title="Real-Time Credit Card Fraud Detection API",
    description="Backend API for predicting fraud and serving transaction analytics.",
    version="1.0.0"
)

# WebSocket Connection Manager for real-time streaming
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"WebSocket client connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"WebSocket client disconnected. Active connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# Enable CORS for frontend dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables at startup
Base.metadata.create_all(bind=engine)

# Auto-migrate missing columns for existing SQLite databases
def migrate_db():
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        if 'transactions' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('transactions')]
            if 'location_city' not in columns:
                print("Migrating database: adding missing 'location_city' column...")
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE transactions ADD COLUMN location_city VARCHAR;"))
                    conn.commit()
                print("Database migration successful.")
    except Exception as e:
        print(f"Database migration notice: {e}")

migrate_db()

# Paths for models and data
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, 'model', 'model.joblib')
SCALER_PATH = os.path.join(BASE_DIR, 'model', 'scaler.joblib')
METRICS_PATH = os.path.join(BASE_DIR, 'model', 'metrics.json')
DATA_PATH = os.path.join(BASE_DIR, 'data', 'creditcard.csv')

# Global variables for loaded model/scaler and simulator samples
model = None
scaler = None
explainer = None
model_metrics = None
normal_samples = []
fraud_samples = []

# Mock data helper lists
MERCHANTS = [
    "Amazon", "Target", "Starbucks", "BestBuy", "Walmart", 
    "Netflix", "Uber", "Chevron", "Walgreens", "McDonald's", 
    "Apple Store", "Steam Games", "Home Depot", "Airbnb", "Delta Air"
]
CATEGORIES = {
    "Amazon": "Retail", "Target": "Retail", "Walmart": "Retail", "Home Depot": "Retail",
    "Apple Store": "Electronics", "BestBuy": "Electronics", "Steam Games": "Entertainment",
    "Netflix": "Entertainment", "Starbucks": "Food & Dining", "McDonald's": "Food & Dining",
    "Uber": "Travel", "Delta Air": "Travel", "Airbnb": "Travel",
    "Chevron": "Gas Station", "Walgreens": "Health & Beauty"
}
CITIES = [
    {"name": "New York", "lat": 40.7128, "lon": -74.0060},
    {"name": "Los Angeles", "lat": 34.0522, "lon": -118.2437},
    {"name": "Chicago", "lat": 41.8781, "lon": -87.6298},
    {"name": "Houston", "lat": 29.7604, "lon": -95.3698},
    {"name": "Phoenix", "lat": 33.4484, "lon": -112.0740},
    {"name": "Philadelphia", "lat": 39.9526, "lon": -75.1652},
    {"name": "San Antonio", "lat": 29.4241, "lon": -98.4936},
    {"name": "San Diego", "lat": 32.7157, "lon": -117.1611},
    {"name": "Dallas", "lat": 32.7767, "lon": -96.7970},
    {"name": "San Jose", "lat": 37.3382, "lon": -121.8863},
    {"name": "Miami", "lat": 25.7617, "lon": -80.1918},
    {"name": "Seattle", "lat": 47.6062, "lon": -122.3321},
    {"name": "Boston", "lat": 42.3601, "lon": -71.0589},
    {"name": "Denver", "lat": 39.7392, "lon": -104.9903},
    {"name": "Atlanta", "lat": 33.7490, "lon": -84.3880}
]

def load_ml_assets():
    global model, scaler, model_metrics
    try:
        if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
            model = joblib.load(MODEL_PATH)
            scaler = joblib.load(SCALER_PATH)
            print("Successfully loaded ML model and scaler.")
            if os.path.exists(METRICS_PATH):
                with open(METRICS_PATH, 'r') as f:
                    model_metrics = json.load(f)
        else:
            print("WARNING: ML model or scaler files not found. Predictions will use mock heuristics until model is trained.")
    except Exception as e:
        print(f"Error loading ML assets: {e}")

def load_simulation_samples():
    global normal_samples, fraud_samples
    try:
        if os.path.exists(DATA_PATH):
            print("Loading simulation samples from creditcard.csv...")
            # We only read a fraction to save memory and time
            df_chunk = pd.read_csv(DATA_PATH)
            normal_df = df_chunk[df_chunk['Class'] == 0]
            fraud_df = df_chunk[df_chunk['Class'] == 1]
            
            # Keep up to 1000 normal and all fraud samples for variety
            normal_samples = normal_df.sample(n=min(1000, len(normal_df)), random_state=42).to_dict(orient='records')
            fraud_samples = fraud_df.to_dict(orient='records')
            
            print(f"Loaded {len(normal_samples)} normal samples and {len(fraud_samples)} fraud samples for simulation.")
        else:
            print("WARNING: creditcard.csv not found. Simulation will generate synthetic values.")
    except Exception as e:
        print(f"Error loading simulation samples: {e}")

@app.on_event("startup")
async def startup_event():
    load_ml_assets()
    load_simulation_samples()

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the Real-Time Credit Card Fraud Detection API",
        "docs_url": "/docs",
        "health_url": "/health"
    }

@app.get("/health")
def health_check():
    model_loaded = model is not None
    scaler_loaded = scaler is not None
    return {
        "status": "healthy",
        "model_loaded": model_loaded,
        "scaler_loaded": scaler_loaded,
        "simulator_data_loaded": len(normal_samples) > 0,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.websocket("/ws/transactions")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)

async def broadcast_tx_event(tx: Transaction, db: Session):
    try:
        tx_dict = {
            "id": tx.id,
            "timestamp": tx.timestamp.isoformat() if tx.timestamp else datetime.utcnow().isoformat(),
            "time_seconds": tx.time_seconds,
            "amount": tx.amount,
            "predicted_class": tx.predicted_class,
            "predicted_probability": tx.predicted_probability,
            "merchant": tx.merchant,
            "category": tx.category,
            "location_lat": tx.location_lat,
            "location_lon": tx.location_lon,
            "location_city": tx.location_city
        }
        
        total = db.query(Transaction).count()
        fraud = db.query(Transaction).filter(Transaction.predicted_class == 1).count()
        legit = total - fraud
        fraud_rate = (fraud / total) * 100 if total > 0 else 0.0
        total_amt = float(db.query(func.sum(Transaction.amount)).scalar() or 0.0)
        avg_amt = total_amt / total if total > 0 else 0.0

        stats_dict = {
            "total_transactions": total,
            "fraud_count": fraud,
            "legitimate_count": legit,
            "fraud_rate": fraud_rate,
            "total_amount": total_amt,
            "average_amount": avg_amt
        }

        event_payload = {
            "type": "NEW_TRANSACTION",
            "transaction": tx_dict,
            "stats": stats_dict
        }

        await manager.broadcast(event_payload)
    except Exception as e:
        print(f"Broadcast error: {e}")

@app.post("/predict", response_model=PredictionResponse)
async def predict_transaction(data: TransactionCreate, db: Session = Depends(get_db)):
    global model, scaler
    
    # Preprocess and prepare features
    time_val = data.time_seconds
    amount_val = data.amount
    
    # Re-load assets if not loaded yet (useful if trained after server starts)
    if model is None or scaler is None:
        load_ml_assets()
        
    # Model Inference
    if model is not None and scaler is not None:
        try:
            # 1. Scaler expects a 2D array of [Time, Amount]
            scaled_features = scaler.transform([[time_val, amount_val]])
            scaled_time = scaled_features[0][0]
            scaled_amount = scaled_features[0][1]
            
            # 2. Reconstruct features list in exact order as training: Time, V1-V28, Amount
            feature_dict = {
                'Time': [scaled_time],
                **{f'V{i}': [getattr(data, f'v{i}')] for i in range(1, 29)},
                'Amount': [scaled_amount]
            }
            feature_df = pd.DataFrame(feature_dict)
            
            # Predict
            pred_class = int(model.predict(feature_df)[0])
            pred_prob = float(model.predict_proba(feature_df)[0][1])
        except Exception as e:
            print(f"Prediction error: {e}. Falling back to heuristics.")
            # Fallback heuristic: amount > 1000 has slight chance, or high V1/V2 anomalies
            pred_class = 1 if amount_val > 5000 or (data.v1 < -5 and data.v2 > 5 and random.random() > 0.8) else 0
            pred_prob = 0.95 if pred_class == 1 else 0.01
    else:
        # Fallback if no model is trained yet
        pred_class = 1 if amount_val > 5000 or (data.v1 < -5 and data.v2 > 5 and random.random() > 0.8) else 0
        pred_prob = 0.95 if pred_class == 1 else 0.01

    # Enrich metadata if missing
    merchant = data.merchant or random.choice(MERCHANTS)
    category = data.category or CATEGORIES.get(merchant, "General")
    
    if data.location_lat is None or data.location_lon is None:
        city = random.choice(CITIES)
        lat = city["lat"] + random.uniform(-0.08, 0.08)
        lon = city["lon"] + random.uniform(-0.08, 0.08)
        location_city = city["name"]
    else:
        lat = data.location_lat
        lon = data.location_lon
        location_city = data.location_city or "Unknown"

    # Store in database
    db_tx = Transaction(
        time_seconds=time_val,
        amount=amount_val,
        v1=data.v1, v2=data.v2, v3=data.v3, v4=data.v4, v5=data.v5,
        v6=data.v6, v7=data.v7, v8=data.v8, v9=data.v9, v10=data.v10,
        v11=data.v11, v12=data.v12, v13=data.v13, v14=data.v14, v15=data.v15,
        v16=data.v16, v17=data.v17, v18=data.v18, v19=data.v19, v20=data.v20,
        v21=data.v21, v22=data.v22, v23=data.v23, v24=data.v24, v25=data.v25,
        v26=data.v26, v27=data.v27, v28=data.v28,
        predicted_class=pred_class,
        predicted_probability=pred_prob,
        merchant=merchant,
        category=category,
        location_lat=lat,
        location_lon=lon,
        location_city=location_city
    )
    
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)
    
    # Broadcast transaction over WebSocket connection
    await broadcast_tx_event(db_tx, db)

    is_fraud = pred_class == 1
    return PredictionResponse(
        predicted_class=pred_class,
        predicted_probability=pred_prob,
        is_fraud=is_fraud,
        message="Alert: Fraudulent transaction detected!" if is_fraud else "Transaction processed successfully."
    )

@app.get("/transactions", response_model=List[TransactionResponse])
def get_transactions(
    skip: int = 0, 
    limit: int = 50, 
    predicted_class: Optional[int] = None, 
    db: Session = Depends(get_db)
):
    query = db.query(Transaction)
    if predicted_class is not None:
        query = query.filter(Transaction.predicted_class == predicted_class)
    
    # Return latest transactions first by ID
    transactions = query.order_by(Transaction.id.desc()).offset(skip).limit(limit).all()
    return transactions

def compute_transaction_explanation(db_tx: Transaction) -> ExplanationResponse:
    global model, scaler, explainer
    
    # Preprocess features
    if scaler is not None:
        try:
            scaled_features = scaler.transform([[db_tx.time_seconds, db_tx.amount]])
            scaled_time = scaled_features[0][0]
            scaled_amount = scaled_features[0][1]
        except Exception:
            scaled_time = db_tx.time_seconds
            scaled_amount = db_tx.amount
    else:
        scaled_time = db_tx.time_seconds
        scaled_amount = db_tx.amount

    raw_values = {
        'Time': db_tx.time_seconds,
        'Amount': db_tx.amount,
        **{f'V{i}': getattr(db_tx, f'v{i}') for i in range(1, 29)}
    }
    
    display_values = {
        'Time': f"{db_tx.time_seconds:.0f}s",
        'Amount': f"${db_tx.amount:,.2f}",
        **{f'V{i}': f"{getattr(db_tx, f'v{i}'):.4f}" for i in range(1, 29)}
    }

    feature_dict = {
        'Time': [scaled_time],
        **{f'V{i}': [raw_values[f'V{i}']] for i in range(1, 29)},
        'Amount': [scaled_amount]
    }
    feature_df = pd.DataFrame(feature_dict)
    
    contributions = []
    base_val = 0.0
    
    if model is not None:
        try:
            import shap
            if explainer is None:
                explainer = shap.TreeExplainer(model)
                
            shap_values = explainer.shap_values(feature_df)
            
            if isinstance(shap_values, list):
                sv = np.array(shap_values[1])[0]
            elif isinstance(shap_values, np.ndarray):
                if shap_values.ndim == 3:
                    sv = shap_values[0, :, 1]
                elif shap_values.ndim == 2:
                    sv = shap_values[0]
                else:
                    sv = shap_values
            else:
                sv = np.array(shap_values.values)[0]
                if sv.ndim > 1:
                    sv = sv[:, 1]
                    
            expected_val = getattr(explainer, 'expected_value', 0.0)
            if isinstance(expected_val, (list, np.ndarray)):
                base_val = float(expected_val[1]) if len(expected_val) > 1 else float(expected_val[0])
            else:
                base_val = float(expected_val)
                
            feature_names = list(feature_df.columns)
            total_abs_shap = float(np.sum(np.abs(sv)) + 1e-9)
            
            FEATURE_LABELS = {
                "Amount": "Amount (Tx Size)",
                "Time": "Time (Elapsed)",
                "V14": "V14 (Behavior Anomaly)",
                "V12": "V12 (Location Shift)",
                "V10": "V10 (Device Fingerprint)",
                "V17": "V17 (Velocity Spike)",
                "V4":  "V4 (Pattern Deviation)",
                "V11": "V11 (Frequency Shift)",
                "V7":  "V7 (Terminal Variance)",
                "V3":  "V3 (Account Anomaly)"
            }

            items = []
            for fname, val in zip(feature_names, sv):
                shap_val = float(val)
                pct = float((abs(shap_val) / total_abs_shap) * 100.0)
                display_label = FEATURE_LABELS.get(fname, fname)
                items.append({
                    "feature": display_label,
                    "val_display": display_values[fname],
                    "shap_value": round(shap_val, 4),
                    "contribution_pct": round(pct, 1),
                    "impact": "increase_risk" if shap_val > 0 else "decrease_risk"
                })
                
            items.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
            contributions = [SHAPContribution(**item) for item in items[:8]]
        except Exception as e:
            print(f"SHAP calculation notice: {e}")

    if not contributions:
        # Fallback heuristic explanation matching domain logic
        v14_val = raw_values['V14']
        amt_val = raw_values['Amount']
        v12_val = raw_values['V12']
        v10_val = raw_values['V10']
        v4_val  = raw_values['V4']
        
        candidates = [
            ("V14 (Behavior Anomaly)", display_values["V14"], -0.42 if v14_val < 0 else 0.1, 42.0 if v14_val < 0 else 10.0, "increase_risk" if v14_val < 0 else "decrease_risk"),
            ("Amount (Tx Size)", display_values["Amount"], 0.35 if amt_val > 500 else -0.1, 35.0 if amt_val > 500 else 12.0, "increase_risk" if amt_val > 500 else "decrease_risk"),
            ("V12 (Location Shift)", display_values["V12"], -0.18 if v12_val < 0 else 0.05, 18.0 if v12_val < 0 else 8.0, "increase_risk" if v12_val < 0 else "decrease_risk"),
            ("V10 (Device Fingerprint)", display_values["V10"], -0.12 if v10_val < 0 else 0.04, 12.0 if v10_val < 0 else 6.0, "increase_risk" if v10_val < 0 else "decrease_risk"),
            ("V4 (Pattern Deviation)", display_values["V4"], 0.09 if v4_val > 1 else -0.05, 9.0 if v4_val > 1 else 5.0, "increase_risk" if v4_val > 1 else "decrease_risk"),
            ("V17 (Velocity Spike)", display_values["V17"], -0.06 if raw_values['V17'] < 0 else 0.02, 6.0, "increase_risk" if raw_values['V17'] < 0 else "decrease_risk")
        ]
        contributions = [
            SHAPContribution(
                feature=c[0], val_display=c[1], shap_value=c[2], contribution_pct=c[3], impact=c[4]
            ) for c in candidates
        ]

    is_fraud = db_tx.predicted_class == 1
    return ExplanationResponse(
        transaction_id=db_tx.id,
        base_value=round(base_val, 4),
        predicted_probability=db_tx.predicted_probability,
        is_fraud=is_fraud,
        top_features=contributions
    )

@app.get("/transactions/{transaction_id}/explain", response_model=ExplanationResponse)
def get_transaction_explanation(transaction_id: int, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return compute_transaction_explanation(tx)

@app.get("/statistics", response_model=StatisticsResponse)
def get_statistics(db: Session = Depends(get_db)):
    total = db.query(Transaction).count()
    if total == 0:
        return StatisticsResponse(
            total_transactions=0,
            fraud_count=0,
            legitimate_count=0,
            fraud_rate=0.0,
            total_amount=0.0,
            average_amount=0.0,
            recent_frauds=[],
            category_distribution={},
            fraud_by_hour={},
            model_info=model_metrics or {"model": "None Loaded"}
        )
    
    fraud = db.query(Transaction).filter(Transaction.predicted_class == 1).count()
    legit = total - fraud
    fraud_rate = (fraud / total) * 100
    
    total_amt_query = db.query(func.sum(Transaction.amount)).scalar()
    total_amount = float(total_amt_query) if total_amt_query is not None else 0.0
    avg_amount = total_amount / total
    
    # Get 10 most recent fraud cases
    recent_frauds = db.query(Transaction)\
        .filter(Transaction.predicted_class == 1)\
        .order_by(Transaction.timestamp.desc())\
        .limit(10).all()
        
    # Get category distribution
    cat_distribution = {}
    cat_query = db.query(Transaction.category, func.count(Transaction.id)).group_by(Transaction.category).all()
    for cat, count in cat_query:
        if cat:
            cat_distribution[cat] = count
            
    # Fraud by hour of day (simulated timestamp)
    fraud_by_hour = {i: 0 for i in range(24)}
    # Use SQLite strftime to extract hour
    # Note: SQLite stores datetime as string. strftime('%H', timestamp) works.
    hour_query = db.query(
        func.strftime('%H', Transaction.timestamp), 
        func.count(Transaction.id)
    ).filter(Transaction.predicted_class == 1).group_by(func.strftime('%H', Transaction.timestamp)).all()
    
    for hr_str, count in hour_query:
        if hr_str is not None:
            try:
                hour_by_int = int(hr_str)
                fraud_by_hour[hour_by_int] = count
            except ValueError:
                pass
                
    return StatisticsResponse(
        total_transactions=total,
        fraud_count=fraud,
        legitimate_count=legit,
        fraud_rate=fraud_rate,
        total_amount=total_amount,
        average_amount=avg_amount,
        recent_frauds=recent_frauds,
        category_distribution=cat_distribution,
        fraud_by_hour=fraud_by_hour,
        model_info=model_metrics or {"model": "None Loaded"}
    )

@app.post("/simulate", response_model=TransactionResponse)
async def simulate_transaction(fraud_probability: float = 0.05, db: Session = Depends(get_db)):
    """
    Simulates a live credit card transaction.
    Takes a fraud_probability (0.0 to 1.0) to decide whether to inject a fraud sample or a clean sample.
    """
    global normal_samples, fraud_samples
    
    # Fallback synthetic generation if csv is not loaded
    if not normal_samples or not fraud_samples:
        is_fraud = random.random() < fraud_probability
        amount = random.uniform(5.0, 1500.0) if not is_fraud else random.uniform(10.0, 10000.0)
        time_sec = random.uniform(0, 172800)
        
        # Synthesize V1-V28 (fraud has higher variance and offsets)
        v_feats = {}
        for i in range(1, 29):
            if is_fraud:
                v_feats[f"V{i}"] = random.normalvariate(-1.0, 4.0)
            else:
                v_feats[f"V{i}"] = random.normalvariate(0.0, 1.0)
                
        tx_data = TransactionCreate(
            Time=time_sec,
            Amount=amount,
            **{f"V{i}": v_feats[f"V{i}"] for i in range(1, 29)}
        )
    else:
        # Sample from real dataset
        is_fraud = random.random() < fraud_probability
        if is_fraud and fraud_samples:
            row = random.choice(fraud_samples)
        else:
            row = random.choice(normal_samples)
            
        # Reconstruct Pydantic schema from row dict
        tx_data = TransactionCreate(
            Time=float(row['Time']),
            Amount=float(row['Amount']),
            **{f"V{i}": float(row[f'V{i}']) for i in range(1, 29)}
        )
        
    # Perform prediction and database storage by calling the predict function
    pred_res = await predict_transaction(tx_data, db)
    
    # Retrieve the latest saved transaction from database
    latest_tx = db.query(Transaction).order_by(Transaction.id.desc()).first()
    return latest_tx

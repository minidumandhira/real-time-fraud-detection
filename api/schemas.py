from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict

# Input Schema for Prediction
class TransactionCreate(BaseModel):
    time_seconds: float = Field(..., alias="Time")
    amount: float = Field(..., alias="Amount")
    v1: float = Field(..., alias="V1")
    v2: float = Field(..., alias="V2")
    v3: float = Field(..., alias="V3")
    v4: float = Field(..., alias="V4")
    v5: float = Field(..., alias="V5")
    v6: float = Field(..., alias="V6")
    v7: float = Field(..., alias="V7")
    v8: float = Field(..., alias="V8")
    v9: float = Field(..., alias="V9")
    v10: float = Field(..., alias="V10")
    v11: float = Field(..., alias="V11")
    v12: float = Field(..., alias="V12")
    v13: float = Field(..., alias="V13")
    v14: float = Field(..., alias="V14")
    v15: float = Field(..., alias="V15")
    v16: float = Field(..., alias="V16")
    v17: float = Field(..., alias="V17")
    v18: float = Field(..., alias="V18")
    v19: float = Field(..., alias="V19")
    v20: float = Field(..., alias="V20")
    v21: float = Field(..., alias="V21")
    v22: float = Field(..., alias="V22")
    v23: float = Field(..., alias="V23")
    v24: float = Field(..., alias="V24")
    v25: float = Field(..., alias="V25")
    v26: float = Field(..., alias="V26")
    v27: float = Field(..., alias="V27")
    v28: float = Field(..., alias="V28")
    
    # Optional metadata
    merchant: Optional[str] = None
    category: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    location_city: Optional[str] = None

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "Time": 0.0,
                "Amount": 149.62,
                "V1": -1.359807,
                "V2": -0.072781,
                "V3": 2.536347,
                "V4": 1.378155,
                "V5": -0.338321,
                "V6": 0.462388,
                "V7": 0.239599,
                "V8": 0.098698,
                "V9": 0.363787,
                "V10": 0.090794,
                "V11": -0.551600,
                "V12": -0.617801,
                "V13": -0.991390,
                "V14": -0.311169,
                "V15": 1.468177,
                "V16": -0.470401,
                "V17": 0.207971,
                "V18": 0.025791,
                "V19": 0.403993,
                "V20": 0.251412,
                "V21": -0.018307,
                "V22": 0.277838,
                "V23": -0.110474,
                "V24": 0.066928,
                "V25": 0.128539,
                "V26": -0.189115,
                "V27": 0.133558,
                "V28": -0.021053,
                "merchant": "Amazon",
                "category": "Retail",
                "location_lat": 40.7128,
                "location_lon": -74.0060,
                "location_city": "New York"
            }
        }

# Response Schema for API Response
class TransactionResponse(BaseModel):
    id: int
    timestamp: datetime
    time_seconds: float
    amount: float
    predicted_class: int
    predicted_probability: float
    merchant: Optional[str]
    category: Optional[str]
    location_lat: Optional[float]
    location_lon: Optional[float]
    location_city: Optional[str]

    class Config:
        from_attributes = True

# Response for Model prediction results
class PredictionResponse(BaseModel):
    predicted_class: int
    predicted_probability: float
    is_fraud: bool
    message: str

# Aggregated Stats
class StatisticsResponse(BaseModel):
    total_transactions: int
    fraud_count: int
    legitimate_count: int
    fraud_rate: float
    total_amount: float
    average_amount: float
    recent_frauds: List[TransactionResponse]
    category_distribution: Dict[str, int]
    fraud_by_hour: Dict[int, int]
    model_info: Dict

# SHAP Explainability Schemas
class SHAPContribution(BaseModel):
    feature: str
    val_display: str
    shap_value: float
    contribution_pct: float
    impact: str

class ExplanationResponse(BaseModel):
    transaction_id: int
    base_value: float
    predicted_probability: float
    is_fraud: bool
    top_features: List[SHAPContribution]

# Real-Time Credit Card Fraud Detection System

Full-stack real-time Credit Card Fraud Detection System combining Machine Learning (Random Forest / XGBoost / LightGBM), SHAP Explainable AI (XAI), a FastAPI backend with WebSocket streaming & Redis Pub/Sub, and an interactive Vite + React dashboard with Leaflet map visualization.

---

## 🌟 Key Features

- **Real-Time Fraud Classification**: Machine learning model classifies incoming transactions in real time with high F1-Score (82.46%) and ROC-AUC (0.977).
- **🧠 SHAP Explainable AI (XAI)**: Detailed feature attribution score breakdown per transaction, explaining exactly *why* a transaction was flagged (e.g., V14 anomaly, velocity spike, transaction amount).
- **⚡ Real-Time WebSocket & Redis Streaming**: Low-latency event streaming (`/ws/transactions`) pushes incoming transactions to all connected dashboard clients instantly (< 10 ms).
- **🗺️ Interactive Geographic Fraud Map**: Leaflet map plots transaction locations with clean dots for legitimate transactions and pulsing radar rings for fraud alerts.
- **🎯 Interactive Ticker & Map Directing**: Double-clicking any item in the Live Ticker smoothly flies the map to that transaction's exact location coordinates.
- **🔍 Transaction Inspection & Explanation Modal**: Double-clicking a transaction opens a full breakdown displaying the ML risk confidence bar, SHAP feature impact breakdown, merchant details, category, city location, and coordinates.
- **🐳 Multi-Container Docker Support**: Docker Compose configuration bundling Redis, FastAPI backend, and React dashboard.

---

## 🏗️ Architecture

```text
Transaction Stream ──► FastAPI API / WebSockets ──► RobustScaler + ML Model ──► SHAP Explainer ──► SQLite DB ──► WebSocket Broadcast ──► React Dashboard
                               ▲                                                                                         │
                               └──────────────────────── Redis Pub/Sub Event Bus ────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

### Frontend (Dashboard)
- **React 19 + Vite**
- **Leaflet & React-Leaflet** (Dark map tiles & pulsing radar markers)
- **Recharts** (Distribution & hourly alert trends)
- **Lucide React** (Icons)
- **Axios & WebSockets**

### Backend & Infrastructure
- **Python 3.11**
- **FastAPI** (ASGI web & WebSocket server)
- **SQLAlchemy & SQLite**
- **Redis 7** (Event Pub/Sub)
- **Uvicorn**

### Machine Learning & Data Science
- **Scikit-learn** (Random Forest Classifier)
- **SHAP** (SHapley Additive exPlanations for XAI)
- **Imbalanced-Learn (SMOTE)** (Synthetic Minority Over-sampling Technique)
- **RobustScaler** (Feature scaling robust to outliers)
- **XGBoost & LightGBM** (Baseline comparisons)
- **Pandas & NumPy**

---

## 📊 Model Performance

| Metric | Value |
| :--- | :--- |
| **Accuracy** | 99.9350% |
| **Precision** | 76.9912% |
| **Recall** | 88.7755% |
| **F1-Score** | 82.4645% |
| **ROC-AUC** | 0.977382 |

*Selected Model: **Random Forest Classifier** trained with SMOTE on Kaggle `creditcard.csv` (284,807 transactions).*

---

## 🔌 API Reference Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Backend health check & ML assets load status |
| `POST` | `/predict` | Classify transaction & store in database |
| `GET` | `/transactions` | List latest processed transactions |
| `GET` | `/transactions/{id}/explain` | Compute SHAP feature contributions for a transaction |
| `GET` | `/statistics` | Return fraud rates, category distribution & hourly trends |
| `POST` | `/simulate` | Inject simulated transaction (fraud/legit sample) |
| `WS` | `/ws/transactions` | Real-time WebSocket event stream |

---

## 🚀 Getting Started

### Option A: Using Docker Compose (Recommended)
```bash
docker-compose up --build
```
- **Dashboard**: [http://localhost](http://localhost)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Option B: Running Locally (Development Mode)

#### 1. Backend
```bash
pip install -r requirements.txt
python app.py
```

#### 2. Frontend Dashboard
```bash
cd dashboard
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 📁 Project Structure

```text
FRAUD detection/
├── api/                  # FastAPI backend service & schemas
│   ├── database.py       # SQLAlchemy engine & SQLite configuration
│   ├── main.py           # FastAPI routes, WebSocket manager & SHAP explainer
│   ├── models.py         # Transaction ORM models
│   └── schemas.py        # Pydantic request/response schemas
├── dashboard/            # Vite + React frontend dashboard
│   ├── src/              # React components & Leaflet maps
│   └── Dockerfile        # Nginx multi-stage build container
├── data/                 # Kaggle creditcard.csv dataset
├── model/                # ML training pipeline & joblib artifacts
│   ├── model.joblib      # Saved Random Forest model
│   ├── scaler.joblib     # Saved RobustScaler
│   └── train.py          # Model comparison & training script
├── docker-compose.yml    # Redis, API, and Dashboard container definitions
├── app.py                # Local API entry point
└── requirements.txt      # Python dependencies
```

---

## 📄 License
MIT License


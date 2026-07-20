import os
import json
import time
import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import RobustScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from imblearn.over_sampling import SMOTE

# Define paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, 'data', 'creditcard.csv')
MODEL_DIR = os.path.join(BASE_DIR, 'model')

def train_pipeline():
    print("=" * 60)
    print("Credit Card Fraud Detection - Model Training Pipeline")
    print("=" * 60)
    
    # 1. Load Dataset
    print(f"\n1. Loading dataset from {DATA_PATH}...")
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}. Please make sure creditcard.csv is placed there.")
    
    start_time = time.time()
    df = pd.read_csv(DATA_PATH)
    elapsed = time.time() - start_time
    print(f"Loaded {df.shape[0]:,} rows and {df.shape[1]} columns in {elapsed:.2f} seconds.")
    
    # Check class distribution
    class_counts = df['Class'].value_counts()
    fraud_pct = (class_counts.get(1, 0) / len(df)) * 100
    print(f"Class Distribution: Legitimate={class_counts.get(0, 0):,} ({100 - fraud_pct:.4f}%), Fraud={class_counts.get(1, 0):,} ({fraud_pct:.4f}%)")
    
    # 2. Train/Test Split
    print("\n2. Splitting dataset into train and test sets (Stratified 80/20)...")
    X = df.drop(columns=['Class'])
    y = df['Class']
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train set: {X_train.shape[0]:,} samples, Test set: {X_test.shape[0]:,} samples.")
    
    # 3. Feature Scaling
    print("\n3. Scaling 'Time' and 'Amount' features using RobustScaler...")
    # Amount has high outliers, RobustScaler is suited since it uses median and IQR
    scaler = RobustScaler()
    
    # We copy the datasets to avoid pandas copy warnings
    X_train = X_train.copy()
    X_test = X_test.copy()
    
    # Scale Time and Amount
    X_train[['Time', 'Amount']] = scaler.fit_transform(X_train[['Time', 'Amount']])
    X_test[['Time', 'Amount']] = scaler.transform(X_test[['Time', 'Amount']])
    
    # 4. Handle Imbalance using SMOTE
    print("\n4. Applying SMOTE to balance the training set...")
    start_time = time.time()
    smote = SMOTE(random_state=42, sampling_strategy=0.1) # Oversample fraud to 10% of majority class to balance speed and accuracy
    X_train_res, y_train_res = smote.fit_resample(X_train, y_train)
    elapsed = time.time() - start_time
    res_counts = pd.Series(y_train_res).value_counts()
    print(f"SMOTE finished in {elapsed:.2f} seconds.")
    print(f"Resampled Class Distribution: Legitimate={res_counts.get(0, 0):,}, Fraud={res_counts.get(1, 0):,}")
    
    # 5. Initialize Models
    models = {
        'Random Forest': RandomForestClassifier(
            n_estimators=100, 
            max_depth=10, 
            random_state=42, 
            n_jobs=-1
        ),
        'XGBoost': XGBClassifier(
            n_estimators=150, 
            max_depth=6, 
            learning_rate=0.1, 
            random_state=42, 
            n_jobs=-1,
            eval_metric='logloss'
        ),
        'LightGBM': LGBMClassifier(
            n_estimators=150, 
            max_depth=6, 
            learning_rate=0.1, 
            random_state=42, 
            n_jobs=-1,
            verbose=-1
        )
    }
    
    # 6. Train and Evaluate
    results = {}
    best_f1 = 0
    best_model_name = None
    best_model = None
    
    for name, model in models.items():
        print(f"\n--- Training {name} ---")
        start_time = time.time()
        # Train
        model.fit(X_train_res, y_train_res)
        train_time = time.time() - start_time
        print(f"Trained {name} in {train_time:.2f} seconds.")
        
        # Predict
        y_pred = model.predict(X_test)
        y_prob = model.predict_proba(X_test)[:, 1] if hasattr(model, 'predict_proba') else y_pred
        
        # Metrics
        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred)
        rec = recall_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)
        roc_auc = roc_auc_score(y_test, y_prob)
        cm = confusion_matrix(y_test, y_pred)
        
        print(f"Results for {name}:")
        print(f"  Accuracy:  {acc:.6f}")
        print(f"  Precision: {prec:.6f}")
        print(f"  Recall:    {rec:.6f}")
        print(f"  F1-Score:  {f1:.6f}")
        print(f"  ROC-AUC:   {roc_auc:.6f}")
        print(f"  Confusion Matrix:\n{cm}")
        
        results[name] = {
            'accuracy': float(acc),
            'precision': float(prec),
            'recall': float(rec),
            'f1_score': float(f1),
            'roc_auc': float(roc_auc),
            'confusion_matrix': cm.tolist(),
            'train_time_seconds': float(train_time)
        }
        
        # Save best model based on F1-Score
        if f1 > best_f1:
            best_f1 = f1
            best_model_name = name
            best_model = model

    print("\n" + "=" * 60)
    print(f"Best Model Selected: {best_model_name} with F1-Score: {best_f1:.6f}")
    print("=" * 60)
    
    # 7. Save Best Model and Scaler
    print(f"\nSaving best model ({best_model_name}) and RobustScaler...")
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    model_save_path = os.path.join(MODEL_DIR, 'model.joblib')
    scaler_save_path = os.path.join(MODEL_DIR, 'scaler.joblib')
    metrics_save_path = os.path.join(MODEL_DIR, 'metrics.json')
    
    joblib.dump(best_model, model_save_path)
    joblib.dump(scaler, scaler_save_path)
    
    # Add meta information to the saved metrics
    run_meta = {
        'best_model_name': best_model_name,
        'dataset_statistics': {
            'total_rows': int(len(df)),
            'fraud_count': int(class_counts.get(1, 0)),
            'legit_count': int(class_counts.get(0, 0)),
            'fraud_percentage': float(fraud_pct)
        },
        'model_performances': results
    }
    
    with open(metrics_save_path, 'w') as f:
        json.dump(run_meta, f, indent=4)
        
    print(f"Model saved to: {model_save_path}")
    print(f"Scaler saved to: {scaler_save_path}")
    print(f"Metrics saved to: {metrics_save_path}")
    print("\nTraining completed successfully!")

if __name__ == '__main__':
    train_pipeline()

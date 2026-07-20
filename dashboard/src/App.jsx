import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  useMap
} from 'react-leaflet';
import L from 'leaflet';
import {
  ShieldAlert,
  CheckCircle2,
  CreditCard,
  Percent,
  DollarSign,
  Play,
  Square,
  AlertTriangle,
  TrendingUp,
  MapPin,
  Activity,
  X,
  Navigation
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  Cell
} from 'recharts';

import 'leaflet/dist/leaflet.css';

// Base API URL
const API_BASE_URL = 'http://127.0.0.1:8000';

// Pre-configure Leaflet icons to bypass Vite asset path bugs
const createCleanMarker = () => {
  return L.divIcon({
    className: 'clean-marker',
    html: `<div style="
      width: 10px;
      height: 10px;
      background-color: #10b981;
      border: 2px solid #ffffff;
      border-radius: 50%;
      box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
    "></div>`,
    iconSize: [10, 10],
    iconAnchor: [5, 5]
  });
};

const createFraudMarker = () => {
  return L.divIcon({
    className: 'pulse-icon',
    iconSize: [14, 14],
    iconAnchor: [7, 7]
  });
};

// MapController component for smooth flyTo navigation when a transaction is selected
function MapController({ focusedTx }) {
  const map = useMap();
  useEffect(() => {
    if (focusedTx && focusedTx.location_lat && focusedTx.location_lon) {
      map.flyTo([focusedTx.location_lat, focusedTx.location_lon], 11, {
        duration: 1.5
      });
    }
  }, [focusedTx, map]);
  return null;
}

function App() {
  const [transactions, setTransactions] = useState([]);
  const [stats, setStats] = useState({
    total_transactions: 0,
    fraud_count: 0,
    legitimate_count: 0,
    fraud_rate: 0.0,
    total_amount: 0.0,
    average_amount: 0.0,
    recent_frauds: [],
    category_distribution: {},
    fraud_by_hour: {},
    model_info: { best_model_name: "None Loaded" }
  });
  const [isSimulating, setIsSimulating] = useState(false);
  const [fraudProb, setFraudProb] = useState(0.15); // default 15% fraud probability in simulator
  const [systemStatus, setSystemStatus] = useState("Connecting...");
  const [alertTx, setAlertTx] = useState(null);

  // Selection and navigation state
  const [focusedTx, setFocusedTx] = useState(null);
  const [detailModalTx, setDetailModalTx] = useState(null);
  const [explanationData, setExplanationData] = useState(null);
  const [loadingExplanation, setLoadingExplanation] = useState(false);
  const markerRefs = useRef({});
  const tickerRefs = useRef({});
  const pendingFraudAlertRef = useRef(null);

  // Helper to handle modal closing and auto-focusing pending fraud alerts
  const handleCloseModal = () => {
    setDetailModalTx(null);
    if (pendingFraudAlertRef.current) {
      const nextTx = pendingFraudAlertRef.current;
      pendingFraudAlertRef.current = null;
      setFocusedTx(nextTx);
    }
  };

  // Fetch SHAP explanation when modal opens
  useEffect(() => {
    if (detailModalTx) {
      setLoadingExplanation(true);
      setExplanationData(null);
      axios.get(`${API_BASE_URL}/transactions/${detailModalTx.id}/explain`)
        .then(res => {
          setExplanationData(res.data);
        })
        .catch(err => {
          console.error("Error fetching explanation:", err);
        })
        .finally(() => {
          setLoadingExplanation(false);
        });
    }
  }, [detailModalTx]);

  const simulationRef = useRef(null);
  const audioRef = useRef(null);

  // Initialize audio for alert sound
  useEffect(() => {
    audioRef.current = {
      playAlert: () => {
        try {
          const ctx = new (window.AudioContext || window.webkitAudioContext)();
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();

          osc.type = 'sawtooth';
          osc.frequency.setValueAtTime(350, ctx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(800, ctx.currentTime + 0.3);

          gain.gain.setValueAtTime(0.15, ctx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);

          osc.connect(gain);
          gain.connect(ctx.destination);

          osc.start();
          osc.stop(ctx.currentTime + 0.4);
        } catch (e) {
          console.log("Audio alert blocked by browser autoplay policy.");
        }
      }
    };
  }, []);

  // Open marker popup and scroll ticker item into view when focused transaction changes
  useEffect(() => {
    if (focusedTx) {
      if (markerRefs.current[focusedTx.id]) {
        try {
          markerRefs.current[focusedTx.id].openPopup();
        } catch (e) { }
      }
      if (tickerRefs.current[focusedTx.id]) {
        try {
          tickerRefs.current[focusedTx.id].scrollIntoView({
            behavior: 'smooth',
            block: 'nearest'
          });
        } catch (e) { }
      }
    }
  }, [focusedTx]);

  // Handler for double click or explicit selection of a ticker item
  const handleSelectTx = (tx) => {
    setFocusedTx(tx);
    setDetailModalTx(tx);
  };

  // Fetch stats and initial transactions
  const loadDashboardData = async () => {
    try {
      const [statsRes, txsRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/statistics`),
        axios.get(`${API_BASE_URL}/transactions?limit=50`)
      ]);
      setStats(statsRes.data);
      setTransactions(txsRes.data);
      setSystemStatus("Active");
    } catch (err) {
      console.error("Error loading API data:", err);
      setSystemStatus("API Offline");
    }
  };

  // Connect to WebSocket stream for real-time push updates
  useEffect(() => {
    loadDashboardData();

    let ws = null;
    let reconnectTimer = null;

    const connectWS = () => {
      try {
        const wsUrl = API_BASE_URL.replace(/^http/, 'ws') + '/ws/transactions';
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          console.log("⚡ Real-Time WebSocket stream connected!");
          setSystemStatus("Active (WebSocket)");
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === "NEW_TRANSACTION") {
              const newTx = data.transaction;
              setTransactions(prev => {
                const filtered = prev.filter(t => t.id !== newTx.id);
                return [newTx, ...filtered].slice(0, 50);
              });
              if (data.stats) {
                setStats(prev => ({
                  ...prev,
                  ...data.stats
                }));
              }
              const isFraud = Number(newTx.predicted_class) === 1 || newTx.is_fraud === true;
              if (isFraud) {
                audioRef.current.playAlert();
                setAlertTx(newTx);
                pendingFraudAlertRef.current = newTx;
                setTimeout(() => setAlertTx(null), 4000);
              }
            }
          } catch (e) {
            console.error("Error parsing WebSocket message:", e);
          }
        };

        ws.onclose = () => {
          setSystemStatus("Reconnecting...");
          reconnectTimer = setTimeout(connectWS, 3000);
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch (e) {
        console.error("Failed to establish WebSocket connection:", e);
      }
    };

    connectWS();

    const interval = setInterval(loadDashboardData, 10000);

    return () => {
      if (ws) ws.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
      clearInterval(interval);
    };
  }, []);

  // Trigger one transaction simulation
  const simulateSingleTx = async () => {
    try {
      const response = await axios.post(`${API_BASE_URL}/simulate?fraud_probability=${fraudProb}`);
      const newTx = response.data;

      setTransactions(prev => {
        const filtered = prev.filter(t => t.id !== newTx.id);
        return [newTx, ...filtered].slice(0, 50);
      });

      const statsRes = await axios.get(`${API_BASE_URL}/statistics`);
      setStats(statsRes.data);

      const isFraud = Number(newTx.predicted_class) === 1 || newTx.is_fraud === true;
      if (isFraud) {
        audioRef.current.playAlert();
        setAlertTx(newTx);
        pendingFraudAlertRef.current = newTx;
        setTimeout(() => setAlertTx(null), 4000);
      }
    } catch (err) {
      console.error("Simulation request failed:", err);
    }
  };

  const toggleSimulation = () => {
    if (isSimulating) {
      clearInterval(simulationRef.current);
      setIsSimulating(false);
    } else {
      setIsSimulating(true);
      simulateSingleTx();
      simulationRef.current = setInterval(simulateSingleTx, 2000);
    }
  };

  useEffect(() => {
    return () => {
      if (simulationRef.current) clearInterval(simulationRef.current);
    };
  }, []);

  const formatMoney = (val) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(val);
  };

  const categoryData = Object.entries(stats.category_distribution).map(([name, value]) => ({
    name,
    count: value
  }));

  const hourlyData = Object.entries(stats.fraud_by_hour).map(([hour, count]) => ({
    hour: `${hour}:00`,
    alerts: count
  }));

  const modelName = stats.model_info.best_model_name || "Random Forest";

  const getCityName = (tx) => {
    if (!tx) return "Unknown Location";
    if (tx.location_city) return tx.location_city;
    if (!tx.location_lat || !tx.location_lon) return "Unknown Location";
    const cities = [
      { name: "New York, NY", lat: 40.7128, lon: -74.0060 },
      { name: "Los Angeles, CA", lat: 34.0522, lon: -118.2437 },
      { name: "Chicago, IL", lat: 41.8781, lon: -87.6298 },
      { name: "Houston, TX", lat: 29.7604, lon: -95.3698 },
      { name: "Phoenix, AZ", lat: 33.4484, lon: -112.0740 },
      { name: "Philadelphia, PA", lat: 39.9526, lon: -75.1652 },
      { name: "San Antonio, TX", lat: 29.4241, lon: -98.4936 },
      { name: "San Diego, CA", lat: 32.7157, lon: -117.1611 },
      { name: "Dallas, TX", lat: 32.7767, lon: -96.7970 },
      { name: "San Jose, CA", lat: 37.3382, lon: -121.8863 },
      { name: "Miami, FL", lat: 25.7617, lon: -80.1918 },
      { name: "Seattle, WA", lat: 47.6062, lon: -122.3321 },
      { name: "Boston, MA", lat: 42.3601, lon: -71.0589 },
      { name: "Denver, CO", lat: 39.7392, lon: -104.9903 },
      { name: "Atlanta, GA", lat: 33.7490, lon: -84.3880 }
    ];
    let closest = cities[0];
    let minDistance = Infinity;
    cities.forEach(c => {
      const d = Math.hypot(c.lat - tx.location_lat, c.lon - tx.location_lon);
      if (d < minDistance) {
        minDistance = d;
        closest = c;
      }
    });
    return closest.name;
  };

  const formatTime = (ts) => {
    if (!ts) return new Date().toLocaleTimeString();
    try {
      const d = new Date(ts);
      return isNaN(d.getTime()) ? new Date().toLocaleTimeString() : d.toLocaleTimeString();
    } catch (e) {
      return new Date().toLocaleTimeString();
    }
  };

  return (
    <div className="dashboard-wrapper">
      {/* Real-time Overlay Screen Alert for Fraud */}
      {alertTx && (
        <div style={{
          position: 'fixed',
          top: '24px',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 9999,
          background: 'rgba(239, 68, 68, 0.95)',
          color: 'white',
          padding: '16px 24px',
          borderRadius: '12px',
          boxShadow: '0 10px 25px rgba(239, 68, 68, 0.4), 0 0 20px rgba(255,255,255,0.2)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          backdropFilter: 'blur(8px)',
          border: '1px solid rgba(255,255,255,0.2)',
          animation: 'slide-in 0.2s ease-out'
        }}>
          <ShieldAlert size={28} style={{ animation: 'bounce 0.5s infinite' }} />
          <div>
            <h4 style={{ margin: 0, fontSize: '15px', fontWeight: '700' }}>FRAUD CRITICAL ALERT</h4>
            <p style={{ margin: '2px 0 0 0', fontSize: '12px', opacity: 0.9 }}>
              Suspicious activity at {alertTx.merchant} in {getCityName(alertTx)} for {formatMoney(alertTx.amount)} (Prob: {(alertTx.predicted_probability * 100).toFixed(1)}%)
            </p>
          </div>
        </div>
      )}

      {/* Detailed Transaction Modal */}
      {detailModalTx && (
        <div className="modal-backdrop" onClick={handleCloseModal}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-box">
                <div className={`modal-status-icon ${detailModalTx.predicted_class === 1 ? 'danger' : 'success'}`}>
                  {detailModalTx.predicted_class === 1 ? <ShieldAlert size={24} /> : <CheckCircle2 size={24} />}
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '18px', color: 'var(--text-main)' }}>{detailModalTx.merchant}</h3>
                  <p style={{ margin: '2px 0 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>
                    Transaction ID: #{detailModalTx.id} • {formatTime(detailModalTx.timestamp)}
                  </p>
                </div>
              </div>
              <button className="modal-close-btn" onClick={handleCloseModal}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              {/* Risk Score Banner */}
              <div className={`risk-banner ${detailModalTx.predicted_class === 1 ? 'risk-danger' : 'risk-success'}`}>
                <div className="risk-banner-header">
                  <span style={{ fontWeight: 600 }}>ML Model Risk Assessment</span>
                  <strong style={{ fontSize: '14px' }}>{(detailModalTx.predicted_probability * 100).toFixed(1)}% Risk Score</strong>
                </div>
                <div className="risk-bar-track">
                  <div
                    className="risk-bar-fill"
                    style={{
                      width: `${(detailModalTx.predicted_probability * 100).toFixed(1)}%`,
                      background: detailModalTx.predicted_class === 1 ? 'linear-gradient(90deg, #f59e0b, #ef4444)' : 'linear-gradient(90deg, #3b82f6, #10b981)'
                    }}
                  />
                </div>
                <p className="risk-description">
                  {detailModalTx.predicted_class === 1
                    ? "⚠️ High probability of fraudulent behavior detected based on transaction velocity and feature anomalies."
                    : "✅ Standard legitimate transaction pattern verified by machine learning model."}
                </p>
              </div>

              {/* Transaction Metadata Grid */}
              <div className="detail-grid">
                <div className="detail-item">
                  <span className="detail-label">Amount</span>
                  <span className="detail-value highlight-amount">{formatMoney(detailModalTx.amount)}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Category</span>
                  <span className="detail-value">{detailModalTx.category || "General"}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Location / City</span>
                  <span className="detail-value" style={{ color: '#60a5fa' }}>
                    📍 {getCityName(detailModalTx)}
                  </span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Coordinates</span>
                  <span className="detail-value font-mono">
                    {detailModalTx.location_lat?.toFixed(4)}°, {detailModalTx.location_lon?.toFixed(4)}°
                  </span>
                </div>
              </div>

              {/* SHAP Model Explainability (XAI) Waterfall Chart */}
              <div style={{
                background: 'rgba(15, 23, 42, 0.6)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '12px',
                padding: '16px',
                marginTop: '10px'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <h4 style={{ margin: 0, fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-main)' }}>
                    <Activity size={16} color="var(--color-primary)" />
                    SHAP Feature Contribution (XAI)
                  </h4>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Top decision factors
                  </span>
                </div>

                {loadingExplanation ? (
                  <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--text-muted)', fontSize: '13px' }}>
                    Computing SHAP feature contributions...
                  </div>
                ) : explanationData && explanationData.top_features ? (
                  <div>
                    {/* Top Impact Summary Pill */}
                    {explanationData.top_features.length > 0 && (
                      <div style={{
                        background: 'rgba(59, 130, 246, 0.1)',
                        border: '1px solid rgba(59, 130, 246, 0.2)',
                        borderRadius: '8px',
                        padding: '10px 12px',
                        fontSize: '12px',
                        marginBottom: '14px',
                        lineHeight: '1.5'
                      }}>
                        <strong>Key Driver:</strong> <span style={{ color: '#60a5fa' }}>{explanationData.top_features[0].feature} = {explanationData.top_features[0].val_display}</span> contributed <strong style={{ color: explanationData.top_features[0].impact === 'increase_risk' ? 'var(--color-danger)' : 'var(--color-success)' }}>+{explanationData.top_features[0].contribution_pct}%</strong> to the fraud score.
                      </div>
                    )}

                    {/* SHAP Horizontal Waterfall Bar Chart */}
                    <div style={{ width: '100%', height: '220px' }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          layout="vertical"
                          data={explanationData.top_features}
                          margin={{ top: 5, right: 30, left: 40, bottom: 5 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                          <XAxis type="number" stroke="var(--text-muted)" fontSize={10} tickLine={false} unit="%" />
                          <YAxis type="category" dataKey="feature" stroke="var(--text-muted)" fontSize={11} tickLine={false} width={65} />
                          <Tooltip
                            content={({ active, payload }) => {
                              if (active && payload && payload.length) {
                                const data = payload[0].payload;
                                return (
                                  <div style={{
                                    background: '#0d1326',
                                    border: '1px solid rgba(255,255,255,0.12)',
                                    borderRadius: '8px',
                                    padding: '8px 12px',
                                    fontSize: '12px'
                                  }}>
                                    <div style={{ fontWeight: 700, color: 'white' }}>Feature: {data.feature}</div>
                                    <div>Input Value: <span style={{ color: '#60a5fa' }}>{data.val_display}</span></div>
                                    <div>SHAP Weight: <span style={{ fontFamily: 'monospace' }}>{data.shap_value}</span></div>
                                    <div>Contribution: <strong style={{ color: data.impact === 'increase_risk' ? '#ef4444' : '#10b981' }}>{data.contribution_pct}% ({data.impact === 'increase_risk' ? 'Increased Risk' : 'Decreased Risk'})</strong></div>
                                  </div>
                                );
                              }
                              return null;
                            }}
                          />
                          <Bar dataKey="contribution_pct" radius={[0, 4, 4, 0]} maxBarSize={20}>
                            {explanationData.top_features.map((entry, index) => (
                              <Cell
                                key={`cell-${index}`}
                                fill={entry.impact === 'increase_risk' ? 'var(--color-danger)' : 'var(--color-success)'}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>

                    {/* Non-technical Dataset Anonymization Note */}
                    <div style={{
                      marginTop: '12px',
                      padding: '10px 14px',
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid rgba(255, 255, 255, 0.07)',
                      borderRadius: '8px',
                      fontSize: '11px',
                      color: 'var(--text-muted)',
                      lineHeight: '1.5'
                    }}>
                      <strong style={{ color: '#93c5fd' }}>ℹ️ Note on Anonymized Features:</strong> Features <code style={{ background: 'rgba(255,255,255,0.08)', padding: '2px 5px', borderRadius: '4px', color: '#f8fafc' }}>V1–V28</code> are anonymized principal components (PCA transformed) from the Kaggle Credit Card Fraud dataset, generated to protect customer financial privacy while retaining ML predictive signals.
                    </div>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '20px 0', color: 'var(--text-muted)', fontSize: '12px' }}>
                    No SHAP explanation data available.
                  </div>
                )}
              </div>
            </div>

            <div className="modal-footer">
              <button
                className="btn btn-primary"
                onClick={() => {
                  const txToFocus = detailModalTx;
                  handleCloseModal();
                  if (txToFocus) setFocusedTx(txToFocus);
                }}
              >
                <Navigation size={14} />
                Focus & Zoom on Map
              </button>
              <button
                className="btn btn-secondary"
                onClick={handleCloseModal}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <header className="dashboard-header">
        <div className="header-title-section">
          <h1>
            <Activity className="trend-up" size={28} />
            Real-Time Fraud Shield
          </h1>
          <p>Credit card transaction monitoring with machine learning explainability (Model: {modelName})</p>
        </div>

        <div className="system-status">
          <div className="simulation-panel">
            <div className="prob-slider">
              <span>Simulated Fraud Rate:</span>
              <input
                type="range"
                min="0.01"
                max="0.5"
                step="0.01"
                value={fraudProb}
                onChange={(e) => setFraudProb(parseFloat(e.target.value))}
              />
              <span style={{ fontWeight: '700', color: 'var(--color-primary)' }}>{(fraudProb * 100).toFixed(0)}%</span>
            </div>

            <button
              className={`btn ${isSimulating ? 'btn-stop' : 'btn-primary'}`}
              onClick={toggleSimulation}
            >
              {isSimulating ? (
                <>
                  <Square size={14} fill="white" />
                  Stop Feed
                </>
              ) : (
                <>
                  <Play size={14} fill="white" />
                  Live Simulator
                </>
              )}
            </button>
          </div>

          <div className="status-indicator">
            <div className="status-dot" style={{
              backgroundColor: systemStatus === "Active" ? "var(--color-success)" : "var(--color-danger)"
            }}></div>
            System: {systemStatus}
          </div>
        </div>
      </header>

      {/* Metrics Cards Grid */}
      <section className="metrics-grid">
        <div className="glass-card metric-card">
          <div className="metric-info">
            <h4>Total Monitored</h4>
            <div className="metric-value">{stats.total_transactions.toLocaleString()}</div>
            <div className="metric-trend">
              <TrendingUp size={12} className="trend-down" />
              <span>Incoming live stream</span>
            </div>
          </div>
          <div className="metric-icon-box metric-primary">
            <CreditCard size={24} />
          </div>
        </div>

        <div className="glass-card metric-card">
          <div className="metric-info">
            <h4>Fraudulent Cases</h4>
            <div className="metric-value" style={{ color: 'var(--color-danger)' }}>
              {stats.fraud_count.toLocaleString()}
            </div>
            <div className="metric-trend">
              <AlertTriangle size={12} className="trend-up" />
              <span>Suspicious transactions flagged</span>
            </div>
          </div>
          <div className="metric-icon-box metric-danger">
            <ShieldAlert size={24} />
          </div>
        </div>

        <div className="glass-card metric-card">
          <div className="metric-info">
            <h4>Fraud Ratio</h4>
            <div className="metric-value">{stats.fraud_rate.toFixed(2)}%</div>
            <div className="metric-trend">
              <span>System-wide frequency</span>
            </div>
          </div>
          <div className="metric-icon-box metric-warning">
            <Percent size={24} />
          </div>
        </div>

        <div className="glass-card metric-card">
          <div className="metric-info">
            <h4>Total Value</h4>
            <div className="metric-value">{formatMoney(stats.total_amount)}</div>
            <div className="metric-trend">
              <span>Avg: {formatMoney(stats.average_amount)} / tx</span>
            </div>
          </div>
          <div className="metric-icon-box metric-success">
            <DollarSign size={24} />
          </div>
        </div>
      </section>

      {/* Main Grid: Map & Live Ticker */}
      <section className="dashboard-grid">
        {/* Left Side: Map Container */}
        <div className="glass-card">
          <div className="glass-card-header">
            <h3>
              <MapPin size={18} color="var(--color-primary)" />
              Geographic Fraud Alerts Map
            </h3>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Real-time location visualization</span>
          </div>

          <div className="map-container">
            <MapContainer
              center={[37.0902, -95.7129]}
              zoom={4}
              scrollWheelZoom={true}
              style={{ height: "100%", width: "100%" }}
            >
              <MapController focusedTx={focusedTx} />
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              />

              {/* Plot transactions */}
              {transactions
                .filter(tx => tx.location_lat && tx.location_lon)
                .slice(0, 35)
                .map((tx) => {
                  const isFraud = Number(tx.predicted_class) === 1 || tx.is_fraud === true;
                  return (
                    <Marker
                      key={tx.id}
                      ref={(ref) => {
                        if (ref) {
                          markerRefs.current[tx.id] = ref;
                        }
                      }}
                      position={[tx.location_lat, tx.location_lon]}
                      icon={isFraud ? createFraudMarker() : createCleanMarker()}
                      eventHandlers={{
                        click: () => {
                          setFocusedTx(tx);
                        },
                        dblclick: () => {
                          handleSelectTx(tx);
                        }
                      }}
                    >
                      <Popup>
                        <div style={{ color: '#0f172a', fontFamily: 'sans-serif', fontSize: '12px' }}>
                          <strong style={{ color: isFraud ? '#ef4444' : '#10b981' }}>
                            {isFraud ? "🚩 SUSPICIOUS TRANSACTION" : "✅ LEGIT TRANSACTION"}
                          </strong>
                          <br />
                          <strong>Merchant:</strong> {tx.merchant}<br />
                          <strong>Location:</strong> 📍 {getCityName(tx)}<br />
                          <strong>Amount:</strong> {formatMoney(tx.amount)}<br />
                          <strong>Category:</strong> {tx.category}<br />
                          <strong>Probability:</strong> {(tx.predicted_probability * 100).toFixed(1)}%<br />
                          <strong>Timestamp:</strong> {formatTime(tx.timestamp)}
                        </div>
                      </Popup>
                    </Marker>
                  );
                })}
            </MapContainer>
          </div>
        </div>

        {/* Right Side: Real-time Live Ticker */}
        <div className="glass-card">
          <div className="glass-card-header">
            <h3>
              <Activity size={18} color="var(--color-primary)" />
              Live Transaction Ticker
            </h3>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              Double-click to inspect & locate on map
            </span>
          </div>

          <div className="ticker-container">
            {transactions.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)', fontSize: '13px' }}>
                Waiting for incoming transaction stream...
              </div>
            ) : (
              transactions.map((tx) => {
                const isFraud = Number(tx.predicted_class) === 1 || tx.is_fraud === true;
                const isFocused = focusedTx?.id === tx.id;
                return (
                  <div
                    key={tx.id}
                    ref={(el) => {
                      if (el) tickerRefs.current[tx.id] = el;
                    }}
                    className={`ticker-item ${isFraud ? 'fraud-alert' : ''} ${isFocused ? 'active-focused' : ''}`}
                    onClick={() => setFocusedTx(tx)}
                    onDoubleClick={() => handleSelectTx(tx)}
                    title="Click to locate on map • Double-click for details"
                    style={{ cursor: 'pointer' }}
                  >
                    <div className="ticker-item-left">
                      <div className="ticker-icon" style={{
                        background: isFraud ? 'rgba(239,68,68,0.1)' : 'rgba(16,185,129,0.1)',
                        color: isFraud ? 'var(--color-danger)' : 'var(--color-success)',
                        border: `1px solid ${isFraud ? 'rgba(239,68,68,0.2)' : 'rgba(16,185,129,0.2)'}`
                      }}>
                        {isFraud ? <ShieldAlert size={16} /> : <CheckCircle2 size={16} />}
                      </div>
                      <div className="ticker-details">
                        <h5>{tx.merchant}</h5>
                        <p>{tx.category} • 📍 {getCityName(tx)} • {formatTime(tx.timestamp)}</p>
                      </div>
                    </div>

                    <div className="ticker-item-right">
                      <div className="ticker-amount" style={{
                        color: isFraud ? 'var(--color-danger)' : 'var(--text-main)'
                      }}>
                        {formatMoney(tx.amount)}
                      </div>
                      <div className="ticker-probability" style={{
                        color: isFraud ? 'var(--color-danger)' : 'var(--text-muted)'
                      }}>
                        {isFraud ? `Fraud Risk: ${(tx.predicted_probability * 100).toFixed(0)}%` : 'Verified'}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </section>


      {/* Analytics Charts Grid */}
      <section className="charts-grid">
        {/* Chart 1: Fraud category breakdown */}
        <div className="glass-card">
          <div className="glass-card-header">
            <h3>Transaction Categories Distribution</h3>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Distribution across commercial categories</span>
          </div>
          <div style={{ width: '100%', height: '300px' }}>
            {categoryData.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '100px 0', color: 'var(--text-muted)' }}>No statistics data available.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={categoryData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                  <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={11} tickLine={false} />
                  <YAxis stroke="var(--text-muted)" fontSize={11} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#0d1326', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px' }}
                    labelStyle={{ color: 'white', fontWeight: 700 }}
                  />
                  <Bar dataKey="count" fill="var(--color-primary)" radius={[4, 4, 0, 0]} maxBarSize={30} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Chart 2: Fraud cases hourly distribution */}
        <div className="glass-card">
          <div className="glass-card-header">
            <h3>Fraud Distribution by Time of Day</h3>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Aggregated alert count by transaction hour</span>
          </div>
          <div style={{ width: '100%', height: '300px' }}>
            {hourlyData.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '100px 0', color: 'var(--text-muted)' }}>No statistics data available.</div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={hourlyData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorAlerts" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--color-danger)" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="var(--color-danger)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                  <XAxis dataKey="hour" stroke="var(--text-muted)" fontSize={11} tickLine={false} />
                  <YAxis stroke="var(--text-muted)" fontSize={11} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#0d1326', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px' }}
                    labelStyle={{ color: 'white', fontWeight: 700 }}
                  />
                  <Area type="monotone" dataKey="alerts" stroke="var(--color-danger)" fillOpacity={1} fill="url(#colorAlerts)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

export default App;

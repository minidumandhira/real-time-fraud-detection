from sqlalchemy import Column, Integer, Float, String, DateTime
from datetime import datetime
from .database import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    time_seconds = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)
    
    # PCA features V1-V28
    v1 = Column(Float, nullable=False)
    v2 = Column(Float, nullable=False)
    v3 = Column(Float, nullable=False)
    v4 = Column(Float, nullable=False)
    v5 = Column(Float, nullable=False)
    v6 = Column(Float, nullable=False)
    v7 = Column(Float, nullable=False)
    v8 = Column(Float, nullable=False)
    v9 = Column(Float, nullable=False)
    v10 = Column(Float, nullable=False)
    v11 = Column(Float, nullable=False)
    v12 = Column(Float, nullable=False)
    v13 = Column(Float, nullable=False)
    v14 = Column(Float, nullable=False)
    v15 = Column(Float, nullable=False)
    v16 = Column(Float, nullable=False)
    v17 = Column(Float, nullable=False)
    v18 = Column(Float, nullable=False)
    v19 = Column(Float, nullable=False)
    v20 = Column(Float, nullable=False)
    v21 = Column(Float, nullable=False)
    v22 = Column(Float, nullable=False)
    v23 = Column(Float, nullable=False)
    v24 = Column(Float, nullable=False)
    v25 = Column(Float, nullable=False)
    v26 = Column(Float, nullable=False)
    v27 = Column(Float, nullable=False)
    v28 = Column(Float, nullable=False)
    
    # Predictions
    predicted_class = Column(Integer, nullable=False, index=True) # 0 = Legitimate, 1 = Fraud
    predicted_probability = Column(Float, nullable=False)
    
    # Metadata for dashboard
    merchant = Column(String, nullable=True)
    category = Column(String, nullable=True)
    location_lat = Column(Float, nullable=True)
    location_lon = Column(Float, nullable=True)
    location_city = Column(String, nullable=True)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

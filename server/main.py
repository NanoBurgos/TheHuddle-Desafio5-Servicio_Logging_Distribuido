
from fastapi import FastAPI, Header, HTTPException, Depends
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional, List

DATABASE_URL = "sqlite:///./logs.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

VALID_TOKENS = {
    "service-a-token": "service-a",
    "service-b-token": "service-b",
    "service-c-token": "service-c"
}

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False)
    service = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    message = Column(String, nullable=False)
    received_at = Column(DateTime, default=datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Distributed Logging MVP")

class LogCreate(BaseModel):
    timestamp: datetime
    service: str
    severity: str
    message: str

class LogResponse(LogCreate):
    id: int
    received_at: datetime

    class Config:
        from_attributes = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_token(authorization: str = Header(...)):
    if not authorization.startswith("Token "):
        raise HTTPException(status_code=401, detail={"error": "Quién sos, bro?"})
    token = authorization.split(" ")[1]
    if token not in VALID_TOKENS:
        raise HTTPException(status_code=401, detail={"error": "Quién sos, bro?"})
    return VALID_TOKENS[token]

@app.post("/logs", response_model=LogResponse)
def create_log(log: LogCreate, db: Session = Depends(get_db), service_name: str = Depends(verify_token)):
    if log.service != service_name:
        raise HTTPException(status_code=403, detail="Service name does not match token")
    
    db_log = Log(
        timestamp=log.timestamp,
        service=log.service,
        severity=log.severity,
        message=log.message
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log

@app.get("/logs", response_model=List[LogResponse])
def read_logs(
    timestamp_start: Optional[datetime] = None,
    timestamp_end: Optional[datetime] = None,
    received_at_start: Optional[datetime] = None,
    received_at_end: Optional[datetime] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db)
):

    query = db.query(Log)

    if timestamp_start:
        query = query.filter(Log.timestamp >= timestamp_start)

    if timestamp_end:
        query = query.filter(Log.timestamp <= timestamp_end)

    if received_at_start:
        query = query.filter(Log.received_at >= received_at_start)

    if received_at_end:
        query = query.filter(Log.received_at <= received_at_end)

    if severity:
        query = query.filter(Log.severity == severity)

    return query.order_by(Log.timestamp.desc()).all()

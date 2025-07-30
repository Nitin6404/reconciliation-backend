from sqlalchemy import Column, Integer, String, Float, Date
from .database import Base

class Ledger(Base):
    __tablename__ = "ledger"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date)
    description = Column(String)
    amount = Column(Float)
    vendor = Column(String)

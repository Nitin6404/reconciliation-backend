from sqlalchemy import Column, Integer, String, Float, Date, UniqueConstraint
from .database import Base

class Ledger(Base):
    __tablename__ = "ledger"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date)
    description = Column(String)
    amount = Column(Float)
    vendor = Column(String)
    message_id = Column(String, unique=True, nullable=True)

    __table_args__ = (
        UniqueConstraint('message_id', name='uix_message_id'),
    )

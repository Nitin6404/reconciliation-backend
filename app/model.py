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
    transaction_id = Column(String, nullable=True)  # ✅ New
    payment_method = Column(String, nullable=True)  # ✅ New
    last_digits = Column(String, nullable=True)     # ✅ New
    currency = Column(String, default="INR")        # ✅ New

    __table_args__ = (
        UniqueConstraint('message_id', name='uix_message_id'),
    )

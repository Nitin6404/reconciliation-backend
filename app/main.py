import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from fastapi import FastAPI, Depends, File, UploadFile
from .database import SessionLocal, engine, Base
from .email_reader import fetch_receipt_pdfs
import csv
from typing import List
from io import StringIO
from .reconciliation import reconcile_transactions
from fastapi.middleware.cors import CORSMiddleware

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def root():
    return {"message": "Ledger Reconciliation System is Live!"}

@app.get("/fetch-emails")
def fetch_emails():
    fetch_receipt_pdfs()
    return {"message": "Fetched and parsed email receipts"}

@app.post("/upload-bank-statement")
def upload_bank_statement(
    file: UploadFile = File(...),
    db: SessionLocal = Depends(get_db)
):
    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(StringIO(content))

    bank_txns = []
    for row in reader:
        bank_txns.append({
            "date": row.get("Date"),
            "description": row.get("Description"),
            "amount": float(row.get("Amount")),
        })

    reconciliation_result = reconcile_transactions(bank_txns, db)
    return {"reconciliation": reconciliation_result}

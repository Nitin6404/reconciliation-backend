# main.py (updated)
import os
from dotenv import load_dotenv
from pathlib import Path
from fastapi import FastAPI, Depends, File, UploadFile, BackgroundTasks


env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


from .database import SessionLocal, engine, Base
from .email_reader import fetch_receipt_pdfs, parse_and_store_receipt
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

# Load env vars
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Dependency
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
def fetch_emails(background_tasks: BackgroundTasks):
    background_tasks.add_task(fetch_receipt_pdfs)
    return {"message": "Scheduled email fetch task."}

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

@app.post("/upload-receipt")
def upload_receipt(
    file: UploadFile = File(...),
    db: SessionLocal = Depends(get_db)
):
    file_data = file.file.read()
    parsed = parse_and_store_receipt(file_data, db=db)

    if not parsed:
        return {"message": "Failed to parse receipt"}

    return {"message": "Receipt parsed and stored", "data": parsed}

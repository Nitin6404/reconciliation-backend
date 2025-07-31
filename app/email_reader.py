# app/email_reader.py
import os
import base64
from datetime import datetime
from io import BytesIO
import json
import typing_extensions as typing

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google import genai
from google.genai import types

from .model import Ledger
from .database import SessionLocal

import tempfile
from .logging_config import logger

from contextlib import contextmanager

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
client = genai.Client()

class ReceiptInfo(typing.TypedDict):
    date: str
    amount: float
    description: str
    vendor: str

def parse_with_gemini_pdf(file_data: bytes) -> dict | None:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(file_data)
            temp_path = temp_file.name

        uploaded = client.files.upload(file=temp_path)

        prompt = """You are a financial receipt parser AI. Given the PDF receipt below, extract the following fields:
        - date: in YYYY-MM-DD
        - amount: float (no symbols)
        - description: What the payment was for
        - vendor: Razorpay, Stripe, Amazon, etc.
        Return JSON with only these keys."""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, uploaded],
            config=types.GenerateContentConfig(
                temperature=0.2,
                top_p=1,
                max_output_tokens=2048,
                response_mime_type="application/json",
                response_schema=ReceiptInfo,
            ),
        )
        logger.info(f"Gemini parsed PDF successfully: {response.text}")
        return json.loads(response.text)

    except Exception as e:
        logger.error(f"Gemini failed: {e}")
        return None

def extract_data_from_pdf(file_data: bytes) -> dict:
    from pdfplumber import open as pdf_open
    try:
        with pdf_open(BytesIO(file_data)) as pdf:
            text = "\n".join(p.extract_text() or '' for p in pdf.pages)
        lines = text.splitlines()
        amount = 0.0
        for line in lines:
            if "total" in line.lower():
                try:
                    import re
                    match = re.search(r"(\d+[,.]?\d*)", line)
                    if match:
                        amount = float(match.group(1).replace(",", ""))
                except:
                    continue
        return {
            "date": str(datetime.today().date()),
            "description": lines[0][:100] if lines else "Unknown",
            "amount": amount,
            "vendor": "Unknown"
        }
    except Exception as e:
        logger.error("Fallback failed:", e)
        return None

def authenticate_gmail():
    token_path = 'token.json'
    if os.path.exists(token_path):
        return Credentials.from_authorized_user_file(token_path, SCOPES)
    flow = InstalledAppFlow.from_client_secrets_file("app/credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)
    with open(token_path, 'w') as token:
        token.write(creds.to_json())
    return creds

def fetch_receipt_pdfs():
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)

    senders = ["justsomefaltuka@gmail.com"]

    @contextmanager
    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    with get_db() as db:
        existing_ids = {
            r[0] for r in db.query(Ledger.message_id).filter(Ledger.message_id != None).all()
        }

    for sender in senders:
        query = f"from:{sender} has:attachment filename:pdf"
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])

        for msg in messages:
            if msg['id'] in existing_ids:
                logger.info(f"Skipping message {msg['id']}")
                continue

            msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
            for part in msg_data['payload'].get('parts', []):
                if part['filename'].endswith('.pdf'):
                    att_id = part['body']['attachmentId']
                    attachment = service.users().messages().attachments().get(
                        userId='me', messageId=msg['id'], id=att_id).execute()
                    file_data = base64.urlsafe_b64decode(attachment['data'])

                    try:
                        parsed = parse_with_gemini_pdf(file_data) or extract_data_from_pdf(file_data)
                        if parsed:
                            entry = Ledger(
                                date=parsed['date'],
                                description=parsed['description'],
                                amount=parsed['amount'],
                                vendor=parsed['vendor'],
                                message_id=msg['id']  # ✅ Include this!
                            )
                            db.add(entry)
                    except Exception as e:
                        logger.error(f"Failed to parse email {msg['id']}: {e}")

    db.commit()
    db.close()

def parse_and_store_receipt(file_data: bytes, db):
    try:
        result = parse_with_gemini_pdf(file_data)
    except Exception as e:
        logger.error("Gemini failed:", e)
        result = extract_data_from_pdf(file_data)

    if not result:
        return None

    entry = Ledger(
        date=result['date'],
        description=result['description'],
        amount=result['amount'],
        vendor=result['vendor']
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {
        "date": entry.date,
        "description": entry.description,
        "amount": entry.amount,
        "vendor": entry.vendor
    }

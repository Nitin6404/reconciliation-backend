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
    transaction_id: str
    payment_method: str
    last_digits: str
    currency: str

def parse_with_gemini_pdf(file_data: bytes) -> dict | None:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(file_data)
            temp_path = temp_file.name
        logger.info(f"Gemini parsed PDF successfully: {temp_path}")

        uploaded = client.files.upload(file=temp_path)
        logger.info(f"Gemini uploaded PDF successfully: {uploaded}")

        prompt = """You are a financial receipt parser AI.

            From the PDF receipt, extract and return the following JSON:

            - date: Date of transaction in YYYY-MM-DD
            - amount: Total transaction amount as a float
            - description: Payment purpose (e.g., Uber Ride, Amazon Order)
            - vendor: Platform or merchant name (e.g., Razorpay, Stripe, Flipkart)
            - transaction_id: The transaction or invoice number
            - payment_method: The payment method used (e.g., UPI, Visa, NetBanking)
            - last_digits: Last 4 digits of card/UPI used if available
            - currency: ISO currency code (e.g., INR, USD)

            Return only valid JSON.
            """

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
            "vendor": "Unknown",
            "transaction_id": "Unknown",
            "payment_method": "Unknown",
            "last_digits": "Unknown",
            "currency": "INR"
        }
    except Exception as e:
        logger.error("Fallback failed:", e)
        return None

def authenticate_gmail():
    # token_path = 'token.json'
    # if os.path.exists(token_path):
    #     return Credentials.from_authorized_user_file(token_path, SCOPES)
    # flow = InstalledAppFlow.from_client_secrets_file("app/credentials.json", SCOPES)
    # creds = flow.run_local_server(port=0)
    creds = Credentials.from_authorized_user_info(json.loads(os.getenv("GOOGLE_TOKEN_JSON")), scopes=SCOPES)
    # with open(token_path, 'w') as token:
    #     token.write(creds.to_json())
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
        logger.info(f"Found {len(results.get('messages', []))} messages")
        messages = results.get('messages', [])
        logger.info(f"Processing {len(messages)} messages")

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
                        logger.info(f"Gemini parsed PDF successfully: {parsed}")
                        if parsed:
                            entry = Ledger(
                                date=parsed["date"],
                                amount=parsed["amount"],
                                description=parsed["description"],
                                vendor=parsed["vendor"],
                                transaction_id=parsed.get("transaction_id"),
                                payment_method=parsed.get("payment_method"),
                                last_digits=parsed.get("last_digits"),
                                currency=parsed.get("currency", "INR"),
                                message_id=msg['id']
                            )
                            db.add(entry)
                    except Exception as e:
                        logger.error(f"Failed to parse email {msg['id']}: {e}")

    db.commit()
    db.close()

def parse_and_store_receipt(file_data: bytes, db):
    try:
        result = parse_with_gemini_pdf(file_data)
        logger.info(f"Gemini parsed PDF successfully: {result}")
    except Exception as e:
        logger.error("Gemini failed:", e)
        result = extract_data_from_pdf(file_data)
        logger.info(f"Fallback parsed PDF successfully: {result}")

    if not result:
        return None

    entry = Ledger(
        date=result["date"],
        amount=result["amount"],
        description=result["description"],
        vendor=result["vendor"],
        transaction_id=result.get("transaction_id"),
        payment_method=result.get("payment_method"),
        last_digits=result.get("last_digits"),
        currency=result.get("currency", "INR"),
        message_id=msg['id']
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {
        "date": entry.date,
        "description": entry.description,
        "amount": entry.amount,
        "vendor": entry.vendor,
        "transaction_id": entry.transaction_id,
        "payment_method": entry.payment_method,
        "last_digits": entry.last_digits,
        "currency": entry.currency,
        "message_id": entry.message_id
    }

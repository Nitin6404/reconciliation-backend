import os
import base64
import pdfplumber
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from .model import Ledger
from .database import SessionLocal
from datetime import datetime
from io import BytesIO

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate_gmail():
    creds = None
    token_path = 'token.json'

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file("app/credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    
    return creds

def extract_data_from_pdf(file_data):
    try:
        with pdfplumber.open(BytesIO(file_data)) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() + "\n"
            # Example naive parsing logic (you’ll improve this)
            print(f"PDF Text Extracted: {text}")
            lines = text.splitlines()
            date = datetime.today().date()
            description = lines[0][:50] if lines else "Unknown"
            amount = 0.0
            for line in lines:
                if "total" in line.lower():
                    try:
                        amount = float(''.join(filter(str.isdigit, line.split()[-1])))
                    except:
                        pass
            return {"date": date, "description": description, "amount": amount, "vendor": "Unknown"}
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return None  # or handle as needed
   

def fetch_receipt_pdfs():
    creds = authenticate_gmail()
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(
    userId='me', 
    q="has:attachment filename:pdf from:justsomefaltuka@gmail.com"
).execute()
    print(results)
    messages = results.get('messages', [])
    print(messages)
    
    db = SessionLocal()
    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
        for part in msg_data['payload'].get('parts', []):
            if part['filename'].endswith('.pdf'):
                att_id = part['body']['attachmentId']
                attachment = service.users().messages().attachments().get(userId='me', messageId=msg['id'], id=att_id).execute()
                file_data = base64.urlsafe_b64decode(attachment['data'])
                parsed = extract_data_from_pdf(file_data)

                if parsed is None: 
                    print("Skipping file: Could not parse PDF.")
                    print(f"Parsed Result: {parsed}")
                    continue
                
                entry = Ledger(
                    date=parsed['date'],
                    description=parsed['description'],
                    amount=parsed['amount'],
                    vendor=parsed['vendor']
                )
                print(entry)
                db.add(entry)
    db.commit()
    db.close()

from .model import Ledger
from sqlalchemy.orm import Session
from datetime import datetime

def reconcile_transactions(bank_txns, db: Session):
    matched = []
    only_in_ledger = []
    only_in_bank = bank_txns.copy()

    ledger_txns = db.query(Ledger).all()

    for l in ledger_txns:
        found_match = False
        for b in only_in_bank:
            if (
                str(l.date) == b['date']
                and abs(float(l.amount) - float(b['amount'])) < 0.01
                and (l.transaction_id == b.get('transaction_id') or l.description in b['description'])
            ):
                matched.append({
                    "date": l.date,
                    "description": l.description,
                    "amount": l.amount,
                    "status": "Matched"
                })
                only_in_bank.remove(b)
                found_match = True
                break
        if not found_match:
            only_in_ledger.append({
                "date": l.date,
                "description": l.description,
                "amount": l.amount,
                "status": "Only in Ledger"
            })

    for b in only_in_bank:
        only_in_ledger.append({
            "date": b['date'],
            "description": b['description'],
            "amount": b['amount'],
            "status": "Only in Bank"
        })

    return matched + only_in_ledger

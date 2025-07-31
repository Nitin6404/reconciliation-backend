# app/utils/csv_parser.py

import pandas as pd
from io import StringIO

# date = Column(Date)
# description = Column(String)
# amount = Column(Float)
# vendor = Column(String)

REQUIRED_COLUMNS = {"Date", "Description", "Amount"}

def infer_csv_structure(df: pd.DataFrame) -> pd.DataFrame:
    if "Debit Amount" in df.columns and "Credit Amount" in df.columns:
        df["Amount"] = df["Credit Amount"].fillna(0) - df["Debit Amount"].fillna(0)
    elif "Amount" not in df.columns:
        raise ValueError("Unsupported CSV structure: Amount column missing")

    df["Description"] = df.get("Category", "Unknown")
    df["date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    return df[["date", "Description", "Amount"]].rename(columns=str.lower)

def parse_csv_file(file_bytes: bytes) -> list[dict]:
    try:
        decoded = file_bytes.decode("utf-8")
        df = pd.read_csv(StringIO(decoded))
        df.columns = df.columns.str.strip()

        if not REQUIRED_COLUMNS.issubset(df.columns):
            missing = REQUIRED_COLUMNS - set(df.columns)
            raise ValueError(f"Missing columns: {', '.join(missing)}")

        # Optional cleaning
        df = df.dropna(subset=["Date", "Amount"])  # Drop rows with missing critical info
        df["Amount"] = df["Amount"].astype(float)

        # Convert to list of dicts in lower case field names
        df.columns = df.columns.str.lower()
        return df[["date", "description", "amount"]].to_dict(orient="records")
    except Exception as e:
        raise ValueError(f"Failed to parse CSV: {e}")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

#  docker run --name postgresdb -e POSTGRES_PASSWORD=your_secure_password -e POSTGRES_DB=ledgerdb -p 5432:5432 -d postgres
DATABASE_URL = "postgresql://postgres:your_secure_password@localhost:5432/ledgerdb"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

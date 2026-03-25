"""
tests/conftest.py — shared fixtures
"""
import pytest, sys, os, random
from pathlib import Path
from faker import Faker
# tests/conftest.py

import asyncio
from dotenv import load_dotenv
import sys, os

# --- Path Setup ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
# ---

from src.event_store import EventStore
sys.path.insert(0, str(Path(__file__).parent.parent))

random.seed(42); Faker.seed(42)

@pytest.fixture
def db_url():
    return os.environ.get("TEST_DB_URL", "postgresql://localhost/apex_ledger_test")

@pytest.fixture
def sample_companies():
    from datagen.company_generator import generate_companies
    return generate_companies(10)

@pytest.fixture
def event_store_class():
    """Returns the EventStore class. Swap for real once implemented."""
    from ledger.event_store import EventStore
    return EventStore

@pytest.fixture
async def event_store():
    """A pytest fixture that provides a clean, connected EventStore for each test."""
    load_dotenv()
    from scripts.init_db import main as init_db
    await init_db()
    
    db_url = os.environ.get("DATABASE_URL")
    store = EventStore(db_url)
    await store.connect()
    yield store
    await store.close()
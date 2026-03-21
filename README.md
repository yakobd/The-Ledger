# The Ledger — Tenx Academy Week 5

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Start Postgres
docker run -d -e POSTGRES_PASSWORD=apex -e POSTGRES_DB=apex_ledger -p 5432:5432 postgres:16

# 3. Setup env
cp .env.example .env
# Add your ANTHROPIC_API_KEY

# 4. Generate data + schema
PYTHONPATH=src python datagen/generate_all.py --db-url postgresql://postgres:apex@localhost/apex_ledger

# 5. Run tests
PYTHONPATH=src pytest tests/ -v

# 6. Locked dependencies (for reproducible builds)
# requirements.lock.txt was generated with uv
```

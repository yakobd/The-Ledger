# The Ledger: Week 5 - Event-Sourced Agentic System

This project is an implementation of a complete, event-sourced multi-agent system for processing loan applications, as per the Tenx Academy TRP Week 5 challenge. It includes a robust event store, multiple specialist agents, an LLM-powered orchestrator, a projection system, and an auditable API.

## Core Architecture

- **Event Sourcing & CQRS:** The system is built on a pure event sourcing pattern using PostgreSQL. All state changes are recorded as immutable events. The Command Query Responsibility Segregation (CQRS) pattern is used to separate write operations (Commands) from read operations (Projections).
- **Multi-Agent System:** The loan processing workflow is handled by a series of autonomous agents built with LangGraph, including specialists for document processing, fraud detection, and compliance.
- **LLM-Powered Decisions:** A final `DecisionOrchestratorAgent` synthesizes the findings from all specialist agents and uses a Large Language Model (via OpenRouter) to make a final, reasoned decision.
- **Projections:** An asynchronous `ProjectionDaemon` builds and maintains read models (e.g., for application summaries and agent performance) for efficient querying.

## Setup Instructions

### 1. Prerequisites

- Python 3.12+
- PostgreSQL server running and accessible.
- A running `conda` or other virtual environment manager.

### 2. Initial Setup

Clone the repository and set up the environment.

```bash
# Clone the repository
git clone <your_repo_url>
cd The-Ledger

# Create and activate a conda environment
conda create -n ledger python=3.12
conda activate ledger

# Install all dependencies using the lock file
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file in the root of the project with the following content, replacing the placeholders with your actual credentials:

```
# .env
DATABASE_URL="postgresql://postgres:apex@localhost/apex_ledger"
OPENROUTER_API_KEY="sk-or-v1-..."
OPENROUTER_API_BASE="https://openrouter.ai/api/v1"
```

### 4. Database Provisioning

This project includes a script to automatically drop and recreate the entire database schema.

```bash
# Run this from the project root
python -m scripts.init_db
```

## Running the System

### Running the Full Test Suite

The simplest way to verify the entire system is to run the `pytest` suite. This will execute tests for concurrency, upcasting, the Gas Town pattern, and the full MCP lifecycle.

```bash
pytest
```

### Running Individual Components

**1. Generate Seed Data (Optional)**
To populate the database with a variety of sample applications:

```bash
python -m datagen.generate_all
```

**2. Run the Projection Daemon**
To run the background process that builds read models:

```bash
python -m scripts.run_daemon
```

**3. Run the MCP Server**
To start the main API server:

```bash
uvicorn src.mcp.server:app --reload
```

- API Docs will be available at `http://127.0.0.1:8000/docs`.

### Example API Queries

**Get Full Application History:**

```
GET http://127.0.0.1:8000/applications/APEX-0007/history
```

**Get Application Summary (from Projection):**

```
GET http://127.0.0.1:8000/resources/applications/APEX-0007/summary
```

**Get Agent Performance Ledger:**

```
GET http://127.0.0.1:8000/resources/agents/performance
```

# Veridian Corp — AI-Powered Internal IT Service Agent

Complete project using the requested stack, with the original pages and the new **New Request → Submit & Analyze** flow. No Docker is required.

## Technologies
- Frontend: React + Vite
- Backend: Python + FastAPI
- Database: MongoDB Community Server locally or MongoDB Atlas
- Authentication: JWT
- AI: OpenAI API called only from FastAPI; deterministic policy-grounded fallback if no key is configured

## Requirements
- Node.js 18+ and npm
- Python 3.11+ (Python 3.12 is also suitable for this project's dependencies)
- MongoDB Community Server running locally, or an Atlas database URI
- Optional: OpenAI API key

## Start on Windows (no Docker)

### 1. Start MongoDB
Ensure the MongoDB service is running in Windows Services. MongoDB Compass is only the GUI; the MongoDB Server service must be running too.

### 2. Configure backend
Open `backend/.env`. For a local MongoDB server, use:

```env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=veridian_it_agent
```

Keep your existing JWT settings. To use actual OpenAI analysis, add your key to `OPENAI_API_KEY` in this backend `.env` only. Never put the OpenAI key in React or a `VITE_*` variable. If no key is set, the policy-grounded fallback runs.

### 3. Start backend
From the project root, double-click `start-backend.bat`; or open a terminal:

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
# If .env is missing, copy .env.example to .env.
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Do not overwrite an already configured `backend/.env` with `.env.example`.

### 4. Start frontend
Open a second terminal in the project root or double-click `start-frontend.bat`:

```powershell
npm install
npm run dev
```

Open http://localhost:5173. FastAPI docs are at http://localhost:8000/docs, and health check at http://localhost:8000/api/health.

## Demo login
- Username: `admin`
- Password: `ChangeMe123!`

These are local demo credentials. Change them and the JWT secret before any public deployment.

## Pages and features
- Login with JWT authentication
- Dashboard with request summaries and action distribution
- Requests list with search and action/status filters
- **New Request button:** create a request with employee name, email and problem description; FastAPI saves it in MongoDB, runs policy analysis, returns the assigned request ID (e.g. REQ-16), and records submission and AI analysis events in the audit log
- Request detail with AI recommendation, matched policy, confidence, reasoning and reviewer actions
- Knowledge Base / Policies
- Audit Log and CSV export endpoint
- Seed data for 15 assignment requests, 10 tickets, 10 knowledge-base policies and the Asset Management policy extract
- REQ-01 laptop refresh policy conflict and vague REQ-15 are intended for human review

## AI behavior
The backend retrieves policies from MongoDB and calls OpenAI when `OPENAI_API_KEY` is configured. It validates structured output and flags low-confidence or conflicting cases for human review. Without a key or when the LLM call fails, the policy-grounded fallback is used. The frontend never calls OpenAI directly.

## API highlights
- `POST /api/auth/login` — sign in
- `GET /api/dashboard/summary` — dashboard counts
- `GET /api/requests` — list requests
- `POST /api/requests` — create and analyze a new request (authenticated)
- `GET /api/requests/{request_id}` — request details
- `POST /api/requests/{request_id}/analyze` — re-run analysis
- `POST /api/requests/{request_id}/review` — approve/override reviewer decision
- `GET /api/policies` — knowledge base
- `GET /api/audit` — audit history
- `GET /api/audit/export` — CSV export

## Deployment notes
To make the site available to other people, deploy React frontend and FastAPI backend to hosting services and use MongoDB Atlas (your local `localhost` database is not internet-accessible). Configure the frontend API proxy/base URL for your hosting setup, backend CORS allowed origins, a strong unique JWT secret, changed demo credentials, HTTPS and the backend-only OpenAI key. The included demo login is not suitable for a public production deployment; add proper account provisioning/roles before exposing it publicly.

## Troubleshooting
- `MongoDB unavailable`: start the MongoDB Server Windows service; Compass alone is not the database server.
- `ModuleNotFoundError`: from `backend`, run `pip install -r requirements.txt` in the same Python environment used for Uvicorn.
- Frontend API errors: ensure FastAPI is running on port 8000 and Vite on port 5173.
- PowerShell activation blocked: run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate `.venv`.

This is a demo prototype, not a production-hardened ITSM platform.

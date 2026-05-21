# brainstorm: debug-backend-startup

## Goal
Diagnose and fix the issue preventing `simo/backend/main.py` from starting the Uvicorn server on port 8091.

## What I already know
- Backend `main.py` uses `uvicorn.run(app, host="0.0.0.0", port=8091)`.
- `netstat -an | findstr :8091` returned empty (nothing listening).
- User reports "it didn't work".

## Requirements
- Identify why `main.py` fails to start.
- Fix the issue.

## Technical Notes
- Current code: `uvicorn.run(app, host="0.0.0.0", port=8091)`
- Common culprits: Port already in use, permission issues, invalid host binding.

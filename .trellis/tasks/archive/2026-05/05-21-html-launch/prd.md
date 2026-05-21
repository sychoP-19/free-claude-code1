# brainstorm: create-html-launchpad

## Goal
Create a simple HTML file that provides a UI to launch the Simo backend and frontend processes, making it easier to start the application.

## What I already know
- Backend runs on `python simo/backend/main.py`.
- Frontend runs on `python simo/frontend/main.py`.
- User wants an HTML-based launcher.

## Requirements
- Create `launch_simo.html`.
- The HTML should have buttons or links to trigger the backend and frontend scripts.
- *Note:* Standard browsers cannot directly execute local Python scripts for security reasons. I need to explain this limitation and propose a workaround (e.g., a `.bat` or `.sh` script that the HTML file triggers, or simply creating a batch file launcher).

## Technical Notes
- Browsers cannot execute local `python` commands directly due to sandboxing.
- Solution: Create `launch_simo.bat` (Windows batch script) that the user can click, and if they really want an HTML launcher, we'd need a local web server to trigger these commands, which might be overkill.

## Open Questions
- Is a `.bat` file on your desktop sufficient, or do you strictly need an `.html` file? (If HTML, we'll need a small helper tool).

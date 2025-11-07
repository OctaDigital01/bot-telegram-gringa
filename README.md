**Overview**
- Telegram bot with a WebApp (mini app) wrapper for checkout links.
- Implements `/start` flow: sends image, marketing message, and three buttons that open in a Telegram mini app.

**Files**
- `script.py` — bot + mini app server (Flask) combined.
- `.env` — environment variables (pre-filled token). Update `WEBAPP_BASE_URL` if using HTTPS tunnel.
- `requirements.txt` — Python dependencies.

**Environment**
- Python 3.10+
- Telegram bot token in `.env` as `BOT_TOKEN`.

**Install**
- `pip install -r requirements.txt`

**Run (local)**
- `python script.py`
- Health check: open `http://localhost:8080/health`

**WebApp (mini app) URL / HTTPS**
- Telegram requires HTTPS for WebApp buttons.
- The bot will automatically fall back to normal URL buttons if `WEBAPP_BASE_URL` is not HTTPS (so `/start` still works without errors).
- To enable true WebApp buttons locally, use ngrok in one of two ways:
  1) Manual
     - `ngrok http 8080`
     - Set `.env` `WEBAPP_BASE_URL` to the HTTPS ngrok URL (e.g., `https://<id>.ngrok-free.app`)
     - Restart `python script.py`
  2) Automatic
     - Set in `.env`: `USE_NGROK=true` (and optionally `NGROK_AUTHTOKEN` if you have one)
     - Start `python script.py`; it will launch ngrok and set `WEBAPP_BASE_URL` at runtime

**/start Flow**
- Sends the image by file_id
- Sends the marketing text
- Sends three buttons that open a WebApp page that immediately opens the corresponding checkout link
  - If HTTPS is unavailable, buttons open the checkout links directly (no mini app wrapper)

**Next Steps (later phases)**
- Payment verification callback handling
- Remarketing sequences & re-entry points
- Persisted user states and analytics

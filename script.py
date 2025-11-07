import logging
import os
import threading
from urllib.parse import quote
import json

from dotenv import load_dotenv
from flask import Flask, request, render_template_string, jsonify
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from typing import Optional

try:
    # Optional dependency, only used if USE_NGROK=true
    from pyngrok import ngrok
except Exception:  # pragma: no cover
    ngrok = None  # type: ignore


# ----------------------
# Environment / Settings
# ----------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_BASE_URL = os.getenv("WEBAPP_BASE_URL", "http://localhost:8080").rstrip("/")
PORT = int(os.getenv("PORT", "8080"))
USE_NGROK = os.getenv("USE_NGROK", "false").lower() in {"1", "true", "yes", "on"}
NGROK_AUTHTOKEN = os.getenv("NGROK_AUTHTOKEN", "").strip()

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN is not set. Add it to .env")


# ----------------------
# Logging
# ----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bot")


# ----------------------
# Flask Mini App
# ----------------------
app = Flask(__name__)

WEBAPP_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Payment</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
      html, body { height: 100%; margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
      .wrap { display: flex; height: 100%; align-items: center; justify-content: center; background: #0e0f13; color: #fff; text-align: center; padding: 24px; }
      .card { max-width: 520px; width: 100%; background: #151821; border-radius: 14px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.4); }
      .title { font-size: 1.25rem; margin-bottom: 10px; }
      .btn { display: inline-block; margin-top: 16px; background: #2eaadc; color: #fff; text-decoration: none; padding: 12px 18px; border-radius: 10px; }
      .hint { font-size: .9rem; opacity: .8; margin-top: 8px; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="card">
        <div class="title">Opening secure checkout…</div>
        <div class="hint">If it doesn’t open automatically, use the button below.</div>
        <a class="btn" id="openBtn" href="{{ target }}" rel="noopener noreferrer">Open Payment</a>
      </div>
    </div>
    <script>
      (function(){
        const params = new URLSearchParams(window.location.search);
        const target = params.get('target');
        const pkg = params.get('pkg');
        try { window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.expand(); } catch(e) {}
        if (pkg) {
          try { localStorage.setItem('selected_pkg', pkg); } catch(e) {}
        }
        if (target) {
          // Navega dentro do próprio webview para manter a experiência de mini app
          try { window.location.replace(target); } catch(e) { window.location.href = target; }
        }
      })();
    </script>
  </body>
  </html>
"""


@app.get("/webapp")
def webapp_page():
    target = request.args.get("target", "")
    return render_template_string(WEBAPP_HTML, target=target)


@app.get("/health")
def health():
    return jsonify(status="ok"), 200


WEBAPP_SUCCESS_HTML = """
<!doctype html>
<html lang=\"pt-br\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Pagamento aprovado</title>
    <script src=\"https://telegram.org/js/telegram-web-app.js\"></script>
    <style>
      html, body { height: 100%; margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; background:#0e0f13; color:#fff; }
      .wrap { display:flex; align-items:center; justify-content:center; height:100%; padding:24px; }
      .card { max-width:520px; width:100%; background:#151821; border-radius:14px; padding:24px; box-shadow:0 10px 30px rgba(0,0,0,.4); text-align:center; }
      .title { font-size:1.25rem; margin-bottom:8px; }
      .desc { opacity:.9; }
      .btn { margin-top:18px; background:#2eaadc; color:#fff; border:none; padding:12px 18px; border-radius:10px; cursor:pointer; }
    </style>
  </head>
  <body>
    <div class=\"wrap\">
      <div class=\"card\">
        <div class=\"title\">Pagamento aprovado! ✅</div>
        <div class=\"desc\">Estamos confirmando com o bot…</div>
        <button class=\"btn\" id=\"closeBtn\" style=\"display:none\">Fechar</button>
      </div>
    </div>
    <script>
      (function(){
        const params = new URLSearchParams(window.location.search);
        const order_id = params.get('order_id') || params.get('tx') || params.get('transaction_id');
        const amount = params.get('amount') || params.get('value');
        const currency = params.get('currency') || 'USD';
        let pkg = params.get('pkg');
        if (!pkg) {
          try { pkg = localStorage.getItem('selected_pkg') || undefined; } catch(e) {}
        }
        let userId = undefined;
        try { userId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id; } catch(e) {}

        const payload = {
          source: 'webapp',
          type: 'payment',
          status: 'approved',
          pkg: pkg,
          order_id: order_id,
          amount: amount,
          currency: currency,
          tg_user_id: userId
        };

        try { window.Telegram?.WebApp?.expand?.(); } catch(e) {}
        try {
          window.Telegram?.WebApp?.sendData?.(JSON.stringify(payload));
        } catch(e) {
          console.warn('Falha ao enviar dados ao bot:', e);
        }

        // Opcional: exibir botão para fechar o WebView após alguns segundos
        setTimeout(function(){
          try { document.getElementById('closeBtn').style.display = 'inline-block'; } catch(e) {}
        }, 1200);
        document.getElementById('closeBtn').addEventListener('click', function(){
          try { window.Telegram?.WebApp?.close?.(); } catch(e) { window.close(); }
        });
      })();
    </script>
  </body>
  </html>
"""


@app.get("/pagamento-aprovado")
def pagamento_aprovado():
    return render_template_string(WEBAPP_SUCCESS_HTML)


def run_flask():
    # Development server (suitable for local testing). Use a proper WSGI server for production.
    app.run(host="0.0.0.0", port=PORT, debug=False)


# ----------------------
# Telegram Bot Handlers
# ----------------------
PACKAGE_1_URL = "https://global.tribopay.com.br/gkfgj"
PACKAGE_2_URL = "https://global.tribopay.com.br/zve76"
PACKAGE_3_URL = "https://global.tribopay.com.br/a8yym"

START_IMAGE_FILE_ID = (
    "AgACAgEAAxkBAAMCaQ4FagpjV6SWuhYflzLrZfuD7AUAApwLaxv4E3FEFRhqkb8YIXgBAAMCAAN5AAM2BA"
)

START_TEXT = (
    "😉 I have 3 options just for you:\n\n"
    "✨ Package 1 🙈 • $2.99\n"
    "4 Images\n"
    "_________________________________\n\n"
    "✨ Package 2 🔥😈 • $4.99\n"
    "6 Images + 2 Videos\n"
    "_________________________________\n\n"
    "✨ Package 3 🔥😈🥵 • $6.99\n"
    "10 Images + 4 Videos + 1 Bonus + Direct and exclusive contact with me\n\n\n"
    "👇🏼🔥 Choose what you want and let me make you cum 😈💦"
)


def _is_https(url: str) -> bool:
    return url.lower().startswith("https://")


def _webapp_button(text: str, target_url: str, pkg_code: str) -> InlineKeyboardButton:
    # If we have an HTTPS WebApp base, open via web_app; otherwise fall back to a normal URL button.
    if _is_https(WEBAPP_BASE_URL):
        # Inclui qual pacote foi escolhido, para persistirmos localmente e enviar na página de sucesso
        wrapped = f"{WEBAPP_BASE_URL}/webapp?target={quote(target_url, safe='')}&pkg={quote(pkg_code, safe='')}"
        return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=wrapped))
    else:
        # Fallback ensures no Telegram error; opens the HTTPS checkout directly.
        return InlineKeyboardButton(text=text, url=target_url)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # 1) Send image by file_id
        await update.message.reply_photo(START_IMAGE_FILE_ID)

        # 2) Prepare buttons that open links via the Telegram WebApp
        keyboard = [
            [_webapp_button("Package 1 🙈 • $2.99", PACKAGE_1_URL, "pkg1")],
            [_webapp_button("Package 2 🔥😈 • $4.99", PACKAGE_2_URL, "pkg2")],
            [_webapp_button("Package 3 🔥😈🥵 • $6.99", PACKAGE_3_URL, "pkg3")],
        ]

        # 3) Send message with buttons
        await update.message.reply_text(
            START_TEXT,
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True,
        )
    except Exception as e:
        logger.exception("Error in /start handler: %s", e)


async def on_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if not msg or not msg.web_app_data:
        return
    raw = msg.web_app_data.data
    try:
        data = json.loads(raw)
    except Exception:
        data = {"raw": raw}

    status = str(data.get("status", "")).lower()
    pkg = data.get("pkg")
    order_id = data.get("order_id")
    amount = data.get("amount")
    currency = data.get("currency", "")

    if status == "approved":
        parts = ["✅ Pagamento aprovado!"]
        if pkg:
            parts.append(f"Pacote: {pkg}")
        if order_id:
            parts.append(f"Pedido: {order_id}")
        if amount:
            parts.append(f"Valor: {amount} {currency}".strip())
        text = "\n".join(parts)
        await msg.reply_text(text)
        # Neste ponto, você poderia liberar o conteúdo, salvar no banco, etc.
    else:
        await msg.reply_text("Recebi dados do WebApp. Status: " + (status or "(vazio)"))


def _maybe_enable_ngrok() -> Optional[str]:
    global WEBAPP_BASE_URL
    if not USE_NGROK:
        return None
    if ngrok is None:
        logger.warning("USE_NGROK=true but pyngrok not installed; skipping ngrok setup.")
        return None
    try:
        if not NGROK_AUTHTOKEN:
            logger.warning("USE_NGROK=true mas NGROK_AUTHTOKEN não definido. Ignorando ngrok.")
            return None
        ngrok.set_auth_token(NGROK_AUTHTOKEN)
        public_tunnel = ngrok.connect(addr=PORT, bind_tls=True)
        public_url = public_tunnel.public_url  # typically https
        if not _is_https(public_url):
            logger.warning("ngrok URL is not HTTPS, got %s", public_url)
        else:
            WEBAPP_BASE_URL = public_url.rstrip("/")
            logger.info("ngrok enabled. WEBAPP_BASE_URL set to %s", WEBAPP_BASE_URL)
        return public_url
    except Exception as e:
        logger.exception("Failed to start ngrok: %s", e)
        return None


def main() -> None:
    # Start Flask app (mini app) in background
    threading.Thread(target=run_flask, name="flask-thread", daemon=True).start()
    # Optionally start ngrok to get HTTPS for WebApp buttons
    _maybe_enable_ngrok()
    logger.info("Mini app running at %s (PORT=%s)", WEBAPP_BASE_URL, PORT)

    # Start Telegram bot (polling)
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.ALL, on_webapp_data))

    logger.info("Bot is starting (polling mode)…")
    application.run_polling()


if __name__ == "__main__":
    main()

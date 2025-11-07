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
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    JobQueue,
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
    level=logging.INFO,  # Root em INFO para exibir nossos logs de início/fluxo
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bot")
logger.setLevel(logging.INFO)

# Silenciar verbosidade de bibliotecas de terceiros
for name in (
    "httpx",
    "telegram",
    "telegram.ext",
    "apscheduler",
    "werkzeug",
    "pyngrok",
):
    try:
        lib_logger = logging.getLogger(name)
        lib_logger.setLevel(logging.WARNING)
        lib_logger.propagate = False
    except Exception:
        pass


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

# --------------
# After-Payment
# --------------
FINAL_APPROVED_TEXT = (
    "Okay, my love, I've received it! 😘\n\n"
    "Send me a private message and I'll send it to you, okay?\n\n"
    "Click the button below and send me a message so I can send it to you. 🔥❤️"
)
FINAL_BUTTON_TEXT = "SEND MESSAGE NOW ✅🔥"
FINAL_BUTTON_URL = "https://t.me/m/WRcFptmbMjUx"

# --------------
# Remarketing (5 min)
# --------------
REMARKETING_DELAY_SECONDS = 30
REMARKETING_IMAGE_FILE_ID = (
    "AgACAgEAAxkBAAMxaQ4i50grFk5EaqZmu5xzBFXlt00AAs0Laxv4E3FEm8zDU3lj9xcBAAMCAAN5AAM2BA"
)
REMARKETING_TEXT = (
    "💝 I've reserved a special gift for you!\n\n"
    "I've gone crazy and lowered the price of package 03 🔥😈🥵 to the same price as package 01 🙈: from $6.99 to just $2.99 ​​🔥\n"
    "It's the complete combo with all the videos, bonuses, and my direct contact just for you, no one else involved… I want you around, reply to me privately and I'll make you c..um a lot. 💋\n\n"
    "Click the button and secure yours, because after that I'll delete this message and return to the normal price 😈💦"
)
REMARKETING_BUTTON_TEXT = "THE BEST PACK FOR $2.99 ​​🔥😈🥵"
REMARKETING_URL = "https://checkouttseguro.shop/pagamento-aprovado/"

# Track users who completed payment (in-memory)
completed_users = set()
scheduled_jobs = {}


def _is_https(url: str) -> bool:
    return url.lower().startswith("https://")


def _build_markups_for_start():
    """Return (reply_markup, inline_markup) where only one will be used.
    - If HTTPS: use ReplyKeyboardMarkup with KeyboardButton.web_app (required for sendData -> web_app_data)
    - Else: use InlineKeyboardMarkup with URL buttons (fallback)
    """
    # URLs dos pacotes
    pkgs = [
        ("Package 1 🙈 • $2.99", PACKAGE_1_URL, "pkg1"),
        ("Package 2 🔥😈 • $4.99", PACKAGE_2_URL, "pkg2"),
        ("Package 3 🔥😈🥵 • $6.99", PACKAGE_3_URL, "pkg3"),
    ]

    if _is_https(WEBAPP_BASE_URL):
        # WebApp via Reply Keyboard (necessário para sendData -> web_app_data chegar ao bot)
        kb_rows = []
        for text, url, code in pkgs:
            wrapped = f"{WEBAPP_BASE_URL}/webapp?target={quote(url, safe='')}&pkg={quote(code, safe='')}"
            kb_rows.append([KeyboardButton(text=text, web_app=WebAppInfo(url=wrapped))])
        reply_kb = ReplyKeyboardMarkup(kb_rows, resize_keyboard=True, one_time_keyboard=True)
        return reply_kb, None
    else:
        # Sem HTTPS: usar inline com URLs normais
        rows = [[InlineKeyboardButton(text=text, url=url)] for text, url, _ in pkgs]
        inline_kb = InlineKeyboardMarkup(rows)
        return None, inline_kb


def _remarketing_reply_markup():
    """Reply keyboard with single WebApp button when HTTPS; else inline URL button."""
    if _is_https(WEBAPP_BASE_URL):
        wrapped = f"{WEBAPP_BASE_URL}/webapp?target={quote(REMARKETING_URL, safe='')}"
        kb = ReplyKeyboardMarkup(
            [[KeyboardButton(text=REMARKETING_BUTTON_TEXT, web_app=WebAppInfo(url=wrapped))]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        return kb, None
    else:
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text=REMARKETING_BUTTON_TEXT, url=REMARKETING_URL)]]
        )
        return None, kb


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        user_id = update.effective_user.id if update.effective_user else None
        chat_id = update.effective_chat.id if update.effective_chat else None
        username = update.effective_user.username if update.effective_user else None

        # If user already completed, just stop silently
        if user_id in completed_users:
            return

        # 1) Send image by file_id
        await update.message.reply_photo(START_IMAGE_FILE_ID)

        # 2) Prepare buttons (ReplyKeyboard if HTTPS for WebApp sendData)
        reply_kb, inline_kb = _build_markups_for_start()

        # 3) Send message with appropriate keyboard
        if reply_kb is not None:
            await update.message.reply_text(
                START_TEXT,
                reply_markup=reply_kb,
                disable_web_page_preview=True,
            )
        else:
            await update.message.reply_text(
                START_TEXT,
                reply_markup=inline_kb,
                disable_web_page_preview=True,
            )

        # 4) Schedule remarketing if not completed
        if user_id and chat_id and context.application.job_queue:
            logger.info("START user_id=%s username=%s chat_id=%s", user_id, username, chat_id)
            # Cancel previous job if exists
            old = scheduled_jobs.pop(user_id, None)
            if old:
                try:
                    old.schedule_removal()
                except Exception:
                    pass
            job = context.application.job_queue.run_once(
                callback=remarketing_job,
                when=REMARKETING_DELAY_SECONDS,
                chat_id=chat_id,
                name=f"remarketing-{user_id}",
                data={"user_id": user_id, "chat_id": chat_id},
            )
            scheduled_jobs[user_id] = job
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
        # Mark as completed and cancel any scheduled remarketing
        user_id = update.effective_user.id if update.effective_user else None
        username = update.effective_user.username if update.effective_user else None
        if user_id:
            completed_users.add(user_id)
            job = scheduled_jobs.pop(user_id, None)
            if job:
                try:
                    job.schedule_removal()
                except Exception:
                    pass

        # Send final message with button (inline)
        final_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text=FINAL_BUTTON_TEXT, url=FINAL_BUTTON_URL)]]
        )
        await msg.reply_text(FINAL_APPROVED_TEXT, reply_markup=final_markup)
        logger.info(
            "PAID user_id=%s username=%s order_id=%s amount=%s currency=%s",
            user_id,
            username,
            order_id,
            amount,
            currency,
        )
        # End of flow for this user
    else:
        # Não registrar/logar para manter o log limpo; ignore estados diferentes
        return




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
    # Garantir JobQueue ativo mesmo se o extra não for detectado
    if application.job_queue is None:
        jq = JobQueue()
        jq.set_application(application)
        application.job_queue = jq
    application.add_handler(CommandHandler("start", start))
    # Handler específico para web_app_data (quando disponível)
    try:
        application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, on_webapp_data))
    except Exception:
        # Fallback para capturar em qualquer mensagem
        application.add_handler(MessageHandler(filters.ALL, on_webapp_data))
    logger.info("Bot is starting (polling mode)…")
    application.run_polling()


async def remarketing_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data or {}
    user_id = data.get("user_id")
    chat_id = data.get("chat_id")

    # Skip if already completed
    if user_id in completed_users:
        return

    # Send remarketing image + text + button
    try:
        await context.bot.send_photo(chat_id=chat_id, photo=REMARKETING_IMAGE_FILE_ID)
    except Exception:
        pass

    reply_kb, inline_kb = _remarketing_reply_markup()
    if reply_kb is not None:
        await context.bot.send_message(chat_id=chat_id, text=REMARKETING_TEXT, reply_markup=reply_kb, disable_web_page_preview=True)
    else:
        await context.bot.send_message(chat_id=chat_id, text=REMARKETING_TEXT, reply_markup=inline_kb, disable_web_page_preview=True)
    return

    logger.info("Bot is starting (polling mode)…")
    application.run_polling()


if __name__ == "__main__":
    main()

import os
import hmac
import asyncio
from threading import Thread
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application
from bot.handlers import setup_bot

load_dotenv()

app = Flask(__name__)

# Fetch environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Log startup webhook configuration
print("=== Webhook Startup Log ===")
if WEBHOOK_URL:
    print(f"Expected Webhook URL: {WEBHOOK_URL}")
else:
    print("Expected Webhook URL: Not configured (register manually via set_webhook.py)")

if WEBHOOK_SECRET:
    secret_prefix = WEBHOOK_SECRET[:3] if len(WEBHOOK_SECRET) >= 3 else WEBHOOK_SECRET
    print(f"Expected Webhook Secret Prefix: '{secret_prefix}...'")
else:
    print("Expected Webhook Secret Prefix: None (validation disabled)")
print("===========================")

# Global containers for telegram application and loop
telegram_app = None
loop = None

def start_telegram_loop():
    """Initializes and runs the asyncio event loop for python-telegram-bot in a background thread."""
    global telegram_app, loop
    if not BOT_TOKEN:
        print("BOT_TOKEN not set; skipping Telegram Bot initialization.")
        return
        
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        telegram_app = Application.builder().token(BOT_TOKEN).updater(None).build()
        setup_bot(telegram_app)
        
        async def init_and_start():
            await telegram_app.initialize()
            await telegram_app.start()
            
        loop.run_until_complete(init_and_start())
        print("Telegram bot application initialized and started successfully.")
        loop.run_forever()
    except Exception as e:
        print(f"Failed to start telegram bot background loop: {e}")

# Start the background thread if bot token is provided
if BOT_TOKEN:
    bot_thread = Thread(target=start_telegram_loop, daemon=True)
    bot_thread.start()
else:
    print("Warning: BOT_TOKEN env var is missing. Webhook will return 500 error if hit.")

@app.route('/health', methods=['GET'])
def health():
    """Simple health check route."""
    return jsonify({"status": "ok"}), 200

@app.route('/', methods=['GET'])
def index():
    """Home landing page for the bot service."""
    bot_username = "bot"
    if telegram_app and telegram_app.bot:
        try:
            # Try to get the username of the bot dynamically
            bot_username = telegram_app.bot.username or "bot"
        except Exception:
            pass
    tg_link = f"https://t.me/{bot_username}"
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SEO Auditor Bot</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            body {{
                margin: 0;
                font-family: 'Outfit', sans-serif;
                background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
                color: #f8fafc;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                text-align: center;
            }}
            .container {{
                z-index: 10;
                padding: 2rem;
                max-width: 600px;
            }}
            h1 {{
                font-size: 3rem;
                font-weight: 800;
                margin: 0 0 1rem 0;
                background: linear-gradient(to right, #38bdf8, #818cf8);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            p {{
                font-size: 1.2rem;
                color: #94a3b8;
                line-height: 1.6;
                margin: 0 0 2.5rem 0;
            }}
            .btn {{
                display: inline-block;
                background: linear-gradient(to right, #6366f1, #4f46e5);
                color: white;
                text-decoration: none;
                padding: 0.8rem 2rem;
                border-radius: 50px;
                font-weight: 600;
                font-size: 1.1rem;
                box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
                transition: transform 0.2s, box-shadow 0.2s;
            }}
            .btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(99, 102, 241, 0.6);
            }}
            .status {{
                margin-top: 3rem;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0.5rem;
                font-size: 0.9rem;
                color: #10b981;
            }}
            .dot {{
                width: 8px;
                height: 8px;
                background-color: #10b981;
                border-radius: 50%;
                box-shadow: 0 0 10px #10b981;
                animation: pulse 2s infinite;
            }}
            @keyframes pulse {{
                0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
                70% {{ transform: scale(1); box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }}
                100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>SEO Auditor Bot</h1>
            <p>Your ultimate on-page SEO analyzer. Get instant scoring, element hierarchy checks, alt-text analysis, and detailed recommendations right inside Telegram.</p>
            <a href="{tg_link}" class="btn" target="_blank">Open in Telegram</a>
            <div class="status">
                <span class="dot"></span>
                <span>Bot Service is Active</span>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram webhook endpoint."""
    if not telegram_app:
        return jsonify({"error": "Bot application not initialized"}), 500
        
    # Verify Secret Token if WEBHOOK_SECRET is set
    if WEBHOOK_SECRET:
        secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        is_valid = False
        if secret_header:
            is_valid = hmac.compare_digest(secret_header, WEBHOOK_SECRET)
            
        if not is_valid:
            received_prefix = secret_header[:3] if secret_header else "None"
            expected_prefix = WEBHOOK_SECRET[:3] if WEBHOOK_SECRET else "None"
            app.logger.warning(
                f"Webhook secret token mismatch! Expected prefix: '{expected_prefix}...', "
                f"Received header prefix: '{received_prefix}...'"
            )
            return jsonify({"error": "Unauthorized"}), 401
            
    try:
        update_data = request.get_json(force=True)
        update = Update.de_json(update_data, telegram_app.bot)
        
        # Dispatch the update asynchronously to the background event loop
        asyncio.run_coroutine_threadsafe(telegram_app.process_update(update), loop)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        app.logger.error(f"Error processing webhook update: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

import os
import sys

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from dotenv import load_dotenv
from telegram.ext import Application
from bot.handlers import setup_bot

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    load_dotenv()
    
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        print("Error: BOT_TOKEN is missing from .env file.")
        sys.exit(1)
        
    print("--------------------------------------------------")
    print("[INFO] Starting Telegram Bot in POLLING mode...")
    print(" - Best for local testing without webhooks or ngrok!")
    print(" - Message your bot on Telegram to start auditing.")
    print("Press Ctrl+C to stop the bot.")
    print("--------------------------------------------------\n")
    
    try:
        # Build the application (without updater=None so it defaults to polling)
        application = Application.builder().token(bot_token).build()
        setup_bot(application)
        
        # Start the bot in polling mode
        application.run_polling()
    except Exception as e:
        logger.error(f"Failed to start bot in polling mode: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

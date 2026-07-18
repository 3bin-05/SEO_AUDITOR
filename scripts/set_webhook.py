import os
import sys
import requests
from dotenv import load_dotenv

# Load environmental variables from .env if present
load_dotenv()

def main():
    if len(sys.argv) < 2:
        print("Usage: python set_webhook.py <webhook_url>")
        print("Example: python set_webhook.py https://my-app.render.com/webhook")
        sys.exit(1)
        
    webhook_url = sys.argv[1]
    bot_token = os.getenv("BOT_TOKEN")
    secret_token = os.getenv("WEBHOOK_SECRET")
    
    if not bot_token:
        print("Error: BOT_TOKEN environment variable is not set. Please set it in .env.")
        sys.exit(1)
        
    if not secret_token:
        print("Warning: WEBHOOK_SECRET not set in environment. Webhook requests won't be validated.")
        
    api_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
    payload = {
        "url": webhook_url
    }
    if secret_token:
        payload["secret_token"] = secret_token
        
    print(f"Setting webhook to: {webhook_url}")
    if secret_token:
        print("Including secret token for payload validation.")
        
    try:
        response = requests.post(api_url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        print(f"Telegram API Response: {result}")
        if result.get("ok"):
            print("Success! Webhook has been registered.")
        else:
            print(f"Failed to register webhook: {result.get('description')}")
            sys.exit(1)
    except Exception as e:
        print(f"Error making request to Telegram API: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

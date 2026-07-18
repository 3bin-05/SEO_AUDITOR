import os
import sys
from datetime import datetime
import requests
from dotenv import load_dotenv

# Load environmental variables from .env if present
load_dotenv()

def main():
    bot_token = os.getenv("BOT_TOKEN")
    
    if not bot_token:
        print("Error: BOT_TOKEN environment variable is not set. Please set it in .env.")
        sys.exit(1)
        
    api_url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
    
    print("Fetching webhook information from Telegram API...")
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if not result.get("ok"):
            print(f"Failed to get webhook info: {result.get('description')}")
            sys.exit(1)
            
        info = result.get("result", {})
        
        print("\n=== Telegram Webhook Info ===")
        print(f"URL:                  {info.get('url') or 'None (Webhook not set / Polling mode)'}")
        print(f"Has Custom Cert:      {info.get('has_custom_certificate', False)}")
        print(f"Pending Updates:      {info.get('pending_update_count', 0)}")
        print(f"Max Connections:      {info.get('max_connections') or 'Default'}")
        
        allowed = info.get("allowed_updates")
        print(f"Allowed Updates:      {allowed if allowed is not None else 'All'}")
        
        last_error_msg = info.get("last_error_message")
        last_error_date_ts = info.get("last_error_date")
        
        if last_error_msg:
            print(f"Last Error Message:   {last_error_msg}")
        else:
            print("Last Error Message:   None")
            
        if last_error_date_ts:
            dt = datetime.fromtimestamp(last_error_date_ts)
            print(f"Last Error Date:      {dt.strftime('%Y-%m-%d %H:%M:%S')} (system local time)")
        else:
            print("Last Error Date:      None")
            
        print("\nRaw API Response:")
        print(result)
        print("=============================")
        
    except Exception as e:
        print(f"Error making request to Telegram API: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

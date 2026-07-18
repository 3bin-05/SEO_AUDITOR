import logging
import time
import urllib.parse
import validators
from threading import Lock
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, Application
from telegram.constants import ParseMode

from seo.scraper import scrape_page, ScrapeError
from seo.analyzer import analyze_seo
from bot.formatter import format_report
from db.firestore_client import save_scan, get_history, get_last_scan, delete_history

# Configure Logger
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# In-memory rate limiting state
# Mapping of user_id -> list of float timestamps of scans
rate_limit_records = {}
rate_limit_lock = Lock()

def check_rate_limit(user_id: str) -> tuple[bool, int]:
    """
    Checks if a user has exceeded the rate limit of 5 scans per 10 minutes.
    Returns a tuple (is_limited, retry_after_seconds).
    """
    now = time.time()
    window = 10 * 60  # 10 minutes
    max_scans = 5
    
    with rate_limit_lock:
        if user_id not in rate_limit_records:
            rate_limit_records[user_id] = [now]
            return False, 0
            
        # Filter out timestamps older than the sliding window
        timestamps = [t for t in rate_limit_records[user_id] if now - t < window]
        rate_limit_records[user_id] = timestamps
        
        if len(timestamps) >= max_scans:
            oldest_scan = timestamps[0]
            retry_after = int(window - (now - oldest_scan))
            return True, max(1, retry_after)
            
        rate_limit_records[user_id].append(now)
        return False, 0

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    welcome_text = (
        "👋 *Welcome to the SEO Auditor Bot!*\n\n"
        "I can audit your website's on-page SEO in real time and store your scan history.\n\n"
        "*Commands*:\n"
        "• `/check <url>` - Run real-time SEO audit on a URL\n"
        "• `/history` - View your last 5 scans\n"
        "• `/last` - Re-show your last scan's breakdown\n"
        "• `/help` - Show command reference & score meanings\n"
        "• `/delete` - Delete your scan history\n\n"
        "*Quick Usage*:\n"
        "Send `/check https://example.com` to analyze a page."
    )
    try:
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error in start_command: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message when the command /help is issued."""
    help_text = (
        "❓ *SEO Auditor Bot - Help & Command Reference*\n\n"
        "*Commands*:\n"
        "• `/start` - Show welcome message\n"
        "• `/help` - Show this help menu\n"
        "• `/check <url>` - Run real-time SEO audit on a URL (Max 5 per 10 minutes)\n"
        "• `/history` - View your last 5 scans from Firestore\n"
        "• `/last` - Re-show your most recent scan's breakdown\n"
        "• `/delete` - Clear your scan history from Firestore\n\n"
        "*SEO Score Explanation*:\n"
        "The score is on a scale of 0 to 100, representing alignment with SEO best practices:\n"
        "• *90–100 (A)*: Excellent optimization\n"
        "• *75–89 (B)*: Good optimization, minor issues\n"
        "• *60–74 (C)*: Moderate optimization, needs improvement\n"
        "• *40–59 (D)*: Poor optimization, critical issues\n"
        "• *<40 (F)*: Very poor/unoptimized\n\n"
        "Checks cover: Title, Meta Description, Headings, Images, Canonical tags, Open Graph, Structured Data, HTTPS, Viewport, robots.txt/sitemap.xml, Content length, and URL structure."
    )
    try:
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Error in help_command: {e}")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs a real-time audit of a URL and responds with the SEO breakdown report."""
    if not context.args:
        await update.message.reply_text("❌ Please specify a URL to check.\nExample: `/check https://example.com`", parse_mode=ParseMode.MARKDOWN)
        return
        
    user_id = str(update.effective_user.id)
    username = update.effective_user.username
    
    # 1. Rate Limiting Check
    is_limited, retry_after = check_rate_limit(user_id)
    if is_limited:
        await update.message.reply_text(
            f"⚠️ *Rate Limit Exceeded*\nYou can scan up to 5 sites every 10 minutes.\n"
            f"Please wait *{retry_after} seconds* before running another scan.",
            parse_mode=ParseMode.MARKDOWN
        )
        logger.warning(f"Scan rate-limited | User: {user_id} ({username}) | Retry after: {retry_after}s")
        return
        
    raw_url = context.args[0].strip()
    
    # 2. Input Sanitization
    # Auto-prepend scheme if omitted (e.g. google.com or www.google.com -> https://google.com)
    sanitized_url = raw_url
    if not (sanitized_url.startswith("http://") or sanitized_url.startswith("https://")):
        sanitized_url = "https://" + sanitized_url
        
    # Pre-scraper URL validation
    is_valid = validators.url(sanitized_url)
    if is_valid is not True:
        await update.message.reply_text(
            f"❌ *Invalid URL Format*\nURL `{raw_url}` is not formatted correctly. "
            "Please provide a valid domain name or absolute HTTP/HTTPS URL.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    # Send intermediate progress message
    progress_msg = await update.message.reply_text(f"🔍 Auditing SEO for `{sanitized_url}`... Please wait.", parse_mode=ParseMode.MARKDOWN)
    
    start_time = time.time()
    try:
        # Scrape page HTML
        scrape_data = scrape_page(sanitized_url)
        # Audit SEO rules
        analysis_result = analyze_seo(scrape_data)
        # Format output message
        messages = format_report(sanitized_url, analysis_result)
        
        # Remove progress message
        await progress_msg.delete()
        
        # Send formatted report messages
        for msg in messages:
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
            
        elapsed = time.time() - start_time
        logger.info(
            f"Scan SUCCESS | URL: {sanitized_url} | Time: {elapsed:.2f}s | "
            f"Score: {analysis_result['score']} | User: {user_id} ({username})"
        )
        
        # Asynchronously save to Firestore (reply first, then save)
        try:
            save_scan(user_id, sanitized_url, analysis_result, username)
        except Exception as db_err:
            logger.error(f"Failed to save scan to Firestore: {db_err}")
            
    except ScrapeError as e:
        elapsed = time.time() - start_time
        logger.warning(
            f"Scan FAILED | URL: {sanitized_url} | Time: {elapsed:.2f}s | "
            f"Error: ScrapeError({str(e)}) | User: {user_id} ({username})"
        )
        await progress_msg.edit_text(f"❌ *Scan Failed*\n{str(e)}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(
            f"Scan ERROR | URL: {sanitized_url} | Time: {elapsed:.2f}s | "
            f"Exception: {str(e)} | User: {user_id} ({username})", exc_info=True
        )
        await progress_msg.edit_text("❌ An unexpected error occurred while processing your request. Please try again later.", parse_mode=ParseMode.MARKDOWN)

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches and displays the user's last 5 scan records from Firestore."""
    user_id = str(update.effective_user.id)
    history = get_history(user_id, limit=5)
    
    if not history:
        await update.message.reply_text("📋 You have no scan history yet. Scan a site using `/check <url>`.", parse_mode=ParseMode.MARKDOWN)
        return
        
    msg_lines = ["📋 *Your Recent SEO Scans*:\n"]
    for idx, scan in enumerate(history, 1):
        scanned_at = scan.get("scanned_at")
        time_str = "Recent"
        if scanned_at:
            try:
                time_str = scanned_at.strftime("%Y-%m-%d %H:%M UTC")
            except AttributeError:
                time_str = str(scanned_at)
                
        url = scan.get("url", "")
        # Escape markdown formatting
        url_escaped = url.replace("_", "\\_").replace("*", "\\*")
        msg_lines.append(
            f"{idx}. *{url_escaped}*\n"
            f"   • Score: {scan.get('score')}/100 (Grade: {scan.get('grade')})\n"
            f"   • Scanned: {time_str}\n"
        )
    await update.message.reply_text("\n".join(msg_lines), parse_mode=ParseMode.MARKDOWN)

async def last_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetches the user's most recent scan and re-displays the breakdown report (avoids re-scraping)."""
    user_id = str(update.effective_user.id)
    scan = get_last_scan(user_id)
    
    if not scan:
        await update.message.reply_text("📋 No previous scans found. Run a new audit using `/check <url>` first.", parse_mode=ParseMode.MARKDOWN)
        return
        
    url = scan.get("url", "")
    messages = format_report(url, scan)
    for msg in messages:
        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes all scan history for the user from Firestore."""
    user_id = str(update.effective_user.id)
    success = delete_history(user_id)
    if success:
        await update.message.reply_text("🗑 *History Cleared*\nYour scan history has been permanently deleted from our database.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("❌ Failed to delete history. Please try again later.", parse_mode=ParseMode.MARKDOWN)

def setup_bot(application: Application) -> None:
    """Register commands with the Telegram application dispatcher."""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("last", last_command))
    application.add_handler(CommandHandler("delete", delete_command))

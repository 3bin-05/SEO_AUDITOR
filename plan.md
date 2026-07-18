# SEO Auditor Telegram Bot — Technical Plan

## 1. What this bot does

A Telegram bot where a user sends `/check <url>`, the bot scrapes that page's
HTML/metadata in real time, runs it through a rule-based SEO scoring engine,
and returns a score + a breakdown of flaws (missing meta description, no
alt text, bad title length, etc.). Every scan is written to Firestore so
`/history` can pull back a user's past scans in real time.

## 2. Key decision: rule-based scoring, not ML

SEO auditing is a checklist problem, not a prediction problem — there's no
ambiguity in "does this page have a meta description" or "is the title
50–60 characters." Tools like Screaming Frog, Ahrefs Site Audit, and
Lighthouse all use deterministic rule engines for exactly this reason:
it's more accurate, fully explainable ("here's *why* you lost points"),
and needs zero training data.

**No model, no dataset, no training pipeline is needed for the core product.**

Optional (Phase 8, skip if you don't want it): a lightweight *readability*
score using the `textstat` library (Flesch reading ease) for body content —
this is a formula, not a trained model, so it still doesn't need a dataset.
If you ever genuinely want ML (e.g. classifying "spammy keyword stuffing"),
that's a real project on its own with a labeled dataset — call it out
separately later rather than folding it into v1.

## 3. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Bot framework | `python-telegram-bot` v21 (async) | Standard, webhook-ready, active |
| Web server | Flask | You specified this; hosts the Telegram webhook endpoint |
| WSGI server (prod) | gunicorn | Flask dev server isn't production-safe |
| Scraping | `requests` + `BeautifulSoup4` (`lxml` parser) | Fast enough for single-page metadata reads |
| Database | Firestore (via `firebase-admin` SDK) | You specified this; real-time reads for history |
| Readability (optional) | `textstat` | Formula-based, no training needed |
| Config | `python-dotenv` | Keep secrets out of code |
| URL validation | `validators` | Guards against malformed/malicious input |
| Deployment | Render or Railway (free tier works) | Persistent HTTPS URL required for Telegram webhooks |

No GPU, no LM Studio model, no local inference needed here — this is
pure I/O + rule evaluation, so it stays light and cheap to run.

## 4. System architecture

```
Telegram User
     |
     v
Telegram Bot API  --webhook POST-->  Flask app (/webhook route)
                                            |
                                            v
                                    Update Router
                                    (command dispatch)
                                            |
                        +-------------------+-------------------+
                        |                   |                   |
                   /check <url>         /history            /start /help
                        |                   |
                        v                   v
                 Scraper Module      Firestore Query
                 (fetch + parse)     (last N scans for user_id)
                        |
                        v
                 SEO Analyzer
                 (rule engine, scoring)
                        |
                        v
                 Report Formatter
                 (Telegram Markdown message)
                        |
                        v
                 Firestore Write
                 (save scan to history)
                        |
                        v
                 Reply to user
```

## 5. SEO analysis engine — the rulebook

Each check returns: `status` (pass / warning / fail), `points`, `message`.
Total score is normalized to /100. Suggested weight distribution:

| Category | Weight | Checks |
|---|---|---|
| Title tag | 10 | Present, 50–60 chars, unique-looking (not generic like "Home") |
| Meta description | 10 | Present, 150–160 chars, not duplicate of title |
| Headings | 10 | Exactly one `<h1>`, logical H1→H6 nesting, H1 not empty |
| Images | 10 | % of `<img>` tags with non-empty `alt` attributes |
| Canonical tag | 5 | Present, self-referencing or valid absolute URL |
| Open Graph / Twitter cards | 10 | `og:title`, `og:description`, `og:image`, `twitter:card` present |
| Structured data | 10 | Valid `<script type="application/ld+json">` present and parses |
| HTTPS | 5 | Site served over HTTPS, no mixed content in scanned assets |
| Mobile viewport | 5 | `<meta name="viewport">` present and sane |
| robots.txt / sitemap.xml | 10 | Both reachable at root, robots.txt doesn't block everything |
| Content length | 10 | Visible body text word count ≥ ~300 words (thin-content flag) |
| URL structure | 5 | No excessive query params/session IDs, reasonably short/readable |

Each failed check produces a human-readable flaw with a suggested fix,
e.g.: *"Missing meta description — search engines will auto-generate a
snippet, which usually hurts click-through rate. Add a 150–160 character
`<meta name='description'>` summarizing the page."*

Grade bands: 90–100 A, 75–89 B, 60–74 C, 40–59 D, <40 F.

## 6. Firestore data model

```
users/{telegram_user_id}
    first_seen: timestamp
    username: string
    scan_count: number

scans/{auto_id}
    user_id: string (telegram user id, indexed)
    url: string
    score: number
    grade: string
    breakdown: array<map>   # [{check, status, points, message}, ...]
    scanned_at: timestamp
```

Query pattern for `/history`: `scans` where `user_id == <id>` order by
`scanned_at desc` limit 5 (paginate with `startAfter` if you add a "more"
button later).

## 7. Firestore security rules

**Important nuance:** your bot backend talks to Firestore through the
`firebase-admin` Python SDK using a service account. Admin SDK access
**bypasses security rules entirely** — rules only govern *client-side*
SDKs (web/mobile apps authenticating as an end user). So for the bot
alone, these rules are not load-bearing. They matter the moment you add
a companion web dashboard where a logged-in user reads their own
Firestore data directly from the browser.

Written defensively for that future case — locked down by default,
readable only by the owning user, writable by nobody client-side (all
writes stay server-side via the bot):

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    match /users/{userId} {
      allow read: if request.auth != null && request.auth.uid == userId;
      allow write: if false; // bot (Admin SDK) writes only
    }

    match /scans/{scanId} {
      allow read: if request.auth != null
                   && request.auth.uid == resource.data.user_id;
      allow write: if false; // bot (Admin SDK) writes only
    }

    // Deny everything else by default
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

If you never build a client-facing app, you can set the entire ruleset to
`allow read, write: if false;` for all paths — the bot won't notice,
since Admin SDK ignores rules anyway. Deploy rules via
`firebase deploy --only firestore:rules` once you have the Firebase CLI
set up (Antigravity will scaffold the `firestore.rules` file; you run
the deploy yourself since it needs your Firebase login).

## 8. Bot commands

| Command | Behavior |
|---|---|
| `/start` | Welcome message, quick usage example |
| `/help` | List commands + explain what the score means |
| `/check <url>` | Run full audit, return score + flaws, save to Firestore |
| `/history` | Last 5 scans for this user, pulled live from Firestore |
| `/last` | Re-show the most recent scan's full breakdown (avoids re-scraping) |
| `/delete` | Clear this user's scan history from Firestore |
| *(optional)* `/compare <url1> <url2>` | Side-by-side score comparison |

## 9. Project structure

```
seo-bot/
├── app.py                  # Flask entrypoint, webhook route
├── bot/
│   ├── __init__.py
│   ├── handlers.py         # command handlers
│   └── formatter.py        # turns analysis dict into Telegram markdown
├── seo/
│   ├── __init__.py
│   ├── scraper.py          # fetch + BeautifulSoup parse
│   └── analyzer.py         # rule engine + scoring
├── db/
│   ├── __init__.py
│   └── firestore_client.py # save_scan(), get_history(), delete_history()
├── firestore.rules
├── .env.example
├── requirements.txt
├── Procfile                # for Render/Railway
└── README.md
```

## 10. Deployment plan

1. Create bot via BotFather → get `BOT_TOKEN` (you're doing this).
2. Create Firebase project → Firestore in Native mode → generate service
   account JSON (you're doing this).
3. Push repo to GitHub.
4. Deploy to Render (Web Service, Python runtime, `gunicorn app:app`).
5. Set env vars on Render: `BOT_TOKEN`, `FIREBASE_CREDENTIALS_JSON`
   (paste the service account JSON as a single-line string),
   `WEBHOOK_SECRET` (random string for verifying Telegram's requests).
6. Call `setWebhook` once against `https://api.telegram.org/bot<token>/setWebhook?url=<render-url>/webhook` (a one-off script does this).
7. Test end-to-end with `/check` against a real site.

## 11. Build phases (matches the Antigravity prompt phase-by-phase)

1. **Scaffold** — repo structure, Flask skeleton, health-check route, `.env.example`.
2. **Telegram plumbing** — webhook route, `python-telegram-bot` dispatcher wired in, `/start` and `/help` working end-to-end (no SEO logic yet).
3. **Scraper module** — fetch a URL safely (timeout, size limit, SSRF-safe: block localhost/private IP ranges), parse metadata with BeautifulSoup.
4. **Analyzer module** — implement the full rulebook from Section 5, return structured breakdown + score/grade.
5. **Report formatter** — turn the breakdown into a readable Telegram message (Markdown, emoji status indicators, grouped by pass/warning/fail).
6. **Firestore integration** — `firestore_client.py` with `save_scan`, `get_history`, `delete_history`; wire into `/check`, `/history`, `/delete`.
7. **Hardening** — input validation, rate limiting per user (avoid scrape abuse), error handling for unreachable/slow sites, logging.
8. *(Optional)* **Readability add-on** — `textstat` Flesch score folded into the Content Length category.
9. **Deployment config** — `Procfile`, `requirements.txt` pinned, `firestore.rules`, README with setup steps, webhook-registration script.

## 12. Explicitly out of scope for v1 (flag if you want them later)

- Google PageSpeed Insights integration (needs its own API key + quota, real page-speed data instead of estimated)
- Broken-link crawling beyond the single page (expensive, needs a queue/worker)
- Competitor comparison / historical trend charts
- Any trained ML model — not needed here, see Section 2

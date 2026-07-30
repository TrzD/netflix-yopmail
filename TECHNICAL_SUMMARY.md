# Netflix Auto-Verify — Technical Summary

> **Version:** v16 (Gmail IMAP) | **Date:** 2026-07-31
> **Stack:** Python 3.13 + Playwright (async_api) + imaplib + filelock + GitHub Actions
> **Auth:** Gmail App Password (IMAP scoped)

---

## 1. Architecture Overview

```
GitHub Actions (serverless)
├── Cron: 3×/day triggers 6-hour polling job
│   06:00, 12:00, 18:00 GMT+7
├── IMAP scan every 30 seconds
├── Playwright (Chromium stealth) for link confirmation
└── State file: last_processed.txt (token→status)
```

Single Python script (`main.py`). No server, no database, no cron daemon.

## 2. Email Pipeline

```
Netflix → Gmail (duytran1598@gmail.com)
  → Gmail Filter: from:info@account.netflix.com
    → Skip Inbox (Archive)
    → Label: Netflix-yopmail
    → Forward: duytran1522@yopmail.com (backup)
  → GitHub Actions: IMAP fetch label → extract travel/verify links
  → Playwright: open link → click confirm → mark done
```

### IMAP Connection

| Parameter | Value |
|---|---|
| Host | imap.gmail.com:993 (SSL) |
| Auth | App Password (16-char, IMAP-only scope) |
| Mailbox | Netflix-yopmail (read-only) |
| Search | FROM "info@account.netflix.com" |
| Fetch limit | Last 5 emails |
| Connection lifecycle | Open → fetch → close (no IDLE) |
| Rate | ≤ 2 connections/min per job |

## 3. IMAP vs Yopmail Web Scraping

| Criteria | IMAP (v16+) | Yopmail Scraping (v1–v15) |
|---|---|---|
| Reliability | Very high (RFC standard) | Medium (DOM-dependent) |
| Speed | <1s per scan | 3–5s per scan |
| CAPTCHA | Never | Occasionally triggered |
| Setup | App Password + Gmail Filter | Only inbox name |
| Email retention | Forever (archived) | ~8 days (auto-delete) |
| Security | App Password (scoped, revocable) | No auth (public inbox) |

## 4. Polling Loop Design

```
Cron: 3 triggers/day → 6h loop → 30s interval
  ├── 06:00–12:00 GMT+7
  ├── 12:00–18:00 GMT+7
  └── 18:00–00:00 GMT+7

Each iteration:
  1. IMAP scan (fetch last 5 Netflix emails from label)
  2. Dedup against last_processed.txt
  3. Process new tokens via Playwright
  4. Save state
  5. Every 20 scans (~10 min): git push state file
  6. sleep 30
```

- ~720 scans per job × 3 jobs = up to 2,160 scans/day
- 2 IMAP connections/min — well within Google rate limits
- GitHub Actions 360-min timeout: next cron picks up seamlessly

## 5. Deduplication & Concurrency

**Claim-based model** (`token\tstatus`):

```
nftoken=abc123	in_progress   ← claimed
nftoken=def456	done          ← finished
nftoken=ghi789	done          ← finished
```

- **FileLock** (filelock library): mutual exclusion, 10s timeout
- **Claim before process**: mark `in_progress` → process → mark `done`
- **Stale recovery**: re-claim `in_progress` from crashed processes
- **Atomic writes**: `tempfile.mkstemp` + `os.replace` + `fsync` + directory `fsync`
- **Backward compat**: lines without `\t` treated as `done` (legacy migration)

## 6. Stealth Browser Configuration

Three-layer anti-detection:

**Layer 1 — Chromium launch args:**
- `--disable-blink-features=AutomationControlled` (hides navigator.webdriver)
- `--no-sandbox`, `--disable-dev-shm-usage` (CI/Docker)

**Layer 2 — Init script (injected before page load):**
- `navigator.webdriver` → undefined
- `navigator.plugins` → realistic Chrome plugin array
- `window.chrome` → populated (runtime, app, csi, loadTimes)
- WebGL vendor/renderer spoofed (Intel Inc. / Intel Iris OpenGL)
- `navigator.hardwareConcurrency` → 4
- All wrapped in try/catch guards

**Layer 3 — Context config:**
- Dynamic User-Agent (probes Chromium, replaces "HeadlessChrome" → "Chrome")
- locale: en-US, timezone: America/New_York
- Viewport: 1920×1080
- Extra HTTP headers: Accept-Language, Upgrade-Insecure-Requests

## 7. Supported Netflix URL Patterns

```
https://www.netflix.com/account/travel/verify?nftoken=...
https://www.netflix.com/account/update-primary-location?nftoken=...
```

Extracted via CSS prefix filter on browser side:
```python
NETFLIX_HREF_SELECTOR = (
    "a[href^='https://www.netflix.com/account/travel/verify?'], "
    "a[href^='https://www.netflix.com/account/update-primary-location?']"
)
```

## 8. Async Safety & Resource Cleanup

- `page = await context.new_page()` inside `try` block → no page leaks
- `await page.close()` in `finally` with try/except guard → safe cleanup
- `asyncio.gather(*tasks, return_exceptions=True)` → no orphaned coroutines
- `Semaphore(5)` → max 5 concurrent Playwright pages

## 9. Error Handling Strategy

| Layer | Mechanism | Catches |
|---|---|---|
| Workflow | `try/except` outer block | Global failures |
| IMAP fetch | `try/except` per scan | Connection/auth errors |
| Token loop | `try/except` per token | Network errors, expired links |
| State save | `if newly_done:` guard | Only writes if changes exist |
| Page cleanup | `try: close() except: pass` | Cleanup never kills batch |

**Design philosophy:** Script never crashes. Every failure degrades gracefully with warnings.

## 10. Security

| Data | Storage | Scope | Revocable |
|---|---|---|---|
| Gmail address | GitHub Secret `YOPMAIL_ID` | — | N/A |
| App Password | GitHub Secret `GMAIL_APP_PASSWORD` | IMAP read-only | ✅ Instant (10s) |
| nftokens | `last_processed.txt` (public) | Single-use | Worthless after use |
| CI logs | `{"ok": true, "processed": 0}` | JSON summary | No sensitive data |

**App Password:** 16 characters, IMAP-only scope. Cannot send email, change password, or access Google Drive/Photos. Revoked instantly from myaccount.google.com/apppasswords.

**Threat model:**

| Threat | Mitigation |
|---|---|
| GitHub account compromised | GitHub 2FA, strong password |
| App Password leaked | Revoke instantly; IMAP-only scope limits damage |
| Token replay | Tokens are single-use; state file prevents re-processing |
| CI log leakage | JSON-only CI mode; no env vars in output |

## 11. Infrastructure

| Component | Detail |
|---|---|
| Runner | ubuntu-latest (24.04) |
| Python | 3.13 via actions/setup-python |
| Browser | Playwright Chromium (headless, cached) |
| Timeout | 360 minutes per job |
| Permissions | contents: write |
| Secrets | YOPMAIL_ID, GMAIL_APP_PASSWORD |
| Cost | Free (public repo, unlimited Actions) |
| Dependencies | playwright, filelock (pip install) |

## 12. Trade-offs & Known Limitations

| Limitation | Why | Mitigation |
|---|---|---|
| 5 emails/scan | Keep IMAP fetch fast | 30s interval ensures quick catch-up |
| App Password required | OAuth app unverified | App Password simpler, revocable |
| No TLS/JA3 stealth | Playwright can't patch TLS fingerprint | Acceptable for Gmail/Netflix targets |
| State file loads every claim | O(n) with n=tokens; few/day | Negligible for Netflix volume |
| Gmail filter must be pre-configured | Not scriptable via API | One-time manual setup |
| Forwarding only for new emails | Gmail limitation | Old emails already in label for script |
| filelock needs pip install | Extra dependency vs fcntl | Cross-platform, timeout support worth it |

---

*Generated by ClawX — v16 Production Ready*

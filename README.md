# Netflix Auto-Verify qua Gmail IMAP 🤖📬

> 🇻🇳 **Tiếng Việt trước** — English below ⬇️

---

## 🇻🇳 Dành cho người không rành kỹ thuật

### Công cụ này làm gì?

Netflix thường xuyên gửi email yêu cầu bạn xác nhận *"đây có phải bạn không?"* khi phát hiện thiết bị ở vị trí mới — nhất là khi bạn hay đi du lịch hoặc dùng VPN. Bạn phải bấm vào link trong email để xác nhận, nếu không Netflix có thể chặn thiết bị đó.

**Công cụ này làm thay bạn**: nó tự động đọc email Netflix, tìm link xác nhận, và bấm *"Yes, this was me"* — tất cả tự động, bạn không cần mở máy tính.

### Bạn cần làm gì?

**Không cần gì cả.** Công cụ đã được cài đặt sẵn. Nó tự chạy 3 lần mỗi ngày (6h sáng, 12h trưa, 6h tối — giờ Việt Nam), mỗi lần quét email liên tục trong 6 tiếng. Bạn không phải nhớ, không cần mở laptop.

### Nó hoạt động thế nào? (Giải thích đơn giản)

```
Netflix gửi email → tài khoản Gmail của bạn
        ↓
Gmail tự động gắn nhãn "Netflix-yopmail" (nhờ bộ lọc có sẵn)
        ↓
Công cụ quét nhãn này mỗi 30 giây (trong khung giờ chạy)
        ↓
Tìm thấy link → tự mở trình duyệt, bấm "Yes, this was me"
        ↓
Ghi nhận đã xong → không bấm lại lần sau
        ↓
🎉 Bạn không phải làm gì!
```

### Thông tin của bạn có an toàn không?

- ✅ **Gmail của bạn** được lưu trong **GitHub Secret** — mã hóa, không ai thấy được
- ✅ **App Password** (mật khẩu ứng dụng Gmail) cũng trong GitHub Secret — chỉ có quyền đọc email, không thể gửi mail, không thể đổi mật khẩu
- ✅ Code công khai nhưng không chứa thông tin cá nhân nào
- ✅ Log chạy trên GitHub Actions chỉ hiện kết quả dạng JSON: `{"ok": true, "emails_checked": 5, "processed": 0}` — không lộ email, link, hay token Netflix
- ✅ Nếu App Password bị lộ: bạn có thể **thu hồi ngay lập tức** từ Google Account → Security → App Passwords, chỉ mất 10 giây
- ✅ Token Netflix sau khi đã xác nhận sẽ không bao giờ bị xử lý lại

### Tôi muốn tự fork về dùng thì sao?

1. Fork repo này
2. Vào repo của bạn → Settings → Secrets and variables → Actions → New repository secret
3. Tạo 2 secret:
   - `YOPMAIL_ID`: địa chỉ Gmail của bạn (giữ tên cũ để tương thích ngược)
   - `GMAIL_APP_PASSWORD`: App Password 16 ký tự từ Google Account
4. **Thiết lập Gmail Filter** (xem hướng dẫn bên dưới)
5. Vào Actions tab, bật workflow lên là chạy!

#### Hướng dẫn tạo Gmail Filter + App Password

**App Password:**
1. Vào https://myaccount.google.com/security
2. Bật 2-Step Verification nếu chưa có
3. Vào "App passwords" → tạo app password mới (chọn "Mail", "Other")
4. Copy 16 ký tự (không có dấu cách), paste vào GitHub Secret `GMAIL_APP_PASSWORD`

**Gmail Filter:**
1. Vào Gmail → Cài đặt (bánh răng) → See all settings → Filters and Blocked Addresses
2. Tạo filter mới:
   - From: `info@account.netflix.com`
   - ✅ Skip the Inbox (Archive it)
   - ✅ Apply the label: tạo label mới tên `Netflix-yopmail`
   - ✅ Forward to: địa chỉ email backup của bạn (tùy chọn, để có bản sao)

### Chi phí?

**0 đồng.** GitHub Actions miễn phí cho repo công khai, không giới hạn số phút chạy. App Password của Google cũng miễn phí.

---

## 🇬🇧 English

### What does this tool do?

Netflix periodically sends *"Is this you?"* verification emails when it detects new devices or locations — especially common if you travel often or use a VPN. You usually need to manually click the confirmation link, or Netflix may block that device.

**This tool does it for you**: it reads your Netflix emails via Gmail IMAP, finds verification links, and clicks *"Yes, this was me"* — fully automated, no laptop required.

### What do I need to do?

**Nothing.** The tool is pre-configured and runs 3 times a day (6 AM, 12 PM, 6 PM — GMT+7), each run polling your inbox continuously for 6 hours. No reminders needed, no manual checks.

### How it works (simple version)

```
Netflix sends email → your Gmail account
        ↓
Gmail filter auto-labels it "Netflix-yopmail"
        ↓
Tool scans the label every 30 seconds (during active windows)
        ↓
Finds link → opens browser, clicks "Yes, this was me"
        ↓
Marks as done → never clicks again
        ↓
🎉 Zero effort from you!
```

### Is my information safe?

- ✅ **Your Gmail address** is stored as a **GitHub Secret** — encrypted at rest, invisible to everyone
- ✅ **App Password** is also a GitHub Secret — scoped to IMAP read-only (cannot send email, cannot change your password)
- ✅ Public code contains zero personal information
- ✅ GitHub Actions logs output only JSON summaries: `{"ok": true, "emails_checked": 5, "processed": 0}` — no emails, links, or tokens exposed
- ✅ If App Password leaks: revoke it instantly from Google Account → Security → App Passwords — 10 seconds and you're safe
- ✅ Processed Netflix tokens are never re-processed

### Want to fork and use it yourself?

1. Fork this repo
2. Go to your repo → Settings → Secrets and variables → Actions → New repository secret
3. Create 2 secrets:
   - `YOPMAIL_ID`: your Gmail address (legacy name kept for backward compatibility)
   - `GMAIL_APP_PASSWORD`: 16-character App Password from your Google Account
4. **Set up the Gmail Filter** (see guide below)
5. Enable the workflow in the Actions tab — done!

#### Gmail Filter + App Password Setup Guide

**App Password:**
1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification if not already on
3. Go to "App passwords" → generate a new app password (select "Mail", "Other")
4. Copy the 16-character string (no spaces), paste into GitHub Secret `GMAIL_APP_PASSWORD`

**Gmail Filter:**
1. Gmail → Settings (gear icon) → See all settings → Filters and Blocked Addresses
2. Create a new filter:
   - From: `info@account.netflix.com`
   - ✅ Skip the Inbox (Archive it)
   - ✅ Apply the label: create a new label named `Netflix-yopmail`
   - ✅ Forward to: your backup email (optional, for your own copy)

### Cost?

**Free.** GitHub Actions is unlimited for public repositories. Google App Passwords are also free.

---

## 🔧 Technical Deep Dive

### Architecture Overview

```
GitHub Actions (serverless)
├── Cron: 3×/day triggers 6-hour polling job
│   06:00, 12:00, 18:00 GMT+7
├── Polling loop: IMAP scan every 30 seconds
├── Playwright (Chromium stealth) for link confirmation
└── State file: last_processed.txt (token→status)
```

The entire system is a single Python script (`main.py`) orchestrated by GitHub Actions. No server, no database, no cron daemon — just a workflow file, environment secrets, and a flat text file for state.

### Email Pipeline

The pipeline is designed for reliability and zero-maintenance operation:

1. **Netflix sends verification email** → `info@account.netflix.com` → user's Gmail inbox
2. **Gmail filter rules** (pre-configured by user):
   - Match: `from:info@account.netflix.com`
   - Actions: **Skip Inbox** (archive) + **Apply label** `Netflix-yopmail` + **Forward to** backup address (optional)
   - This ensures emails bypass the main inbox and land directly in a dedicated label — clean separation of concerns
3. **GitHub Actions triggers** → `main.py --ci` runs:
   - IMAP login via App Password (no OAuth complexity)
   - `SELECT "Netflix-yopmail"` (read-only, never modifies emails)
   - `SEARCH FROM "info@account.netflix.com"` → fetch last 5 email UIDs
   - `FETCH` RFC822 → parse MIME → extract `text/html` body → regex Netflix verification links
4. **Playwright browser automation**:
   - For each unprocessed link: open in stealth Chromium
   - Detect confirm button → click → verify URL change → mark token as `done`
   - Handle edge cases: expired links, already-verified pages, missing buttons

### IMAP vs Web Scraping Comparison

This project originally used **Yopmail web scraping** (v1–v15). v16 migrated to **Gmail IMAP** for significantly better reliability and performance.

| Criteria | IMAP (new — v16+) | Yopmail Web Scraping (old — v1–v15) |
|---|---|---|
| Reliability | Very high (IMAP RFC standard) | Medium (DOM changes break selectors) |
| Speed | <1s per scan | 3–5s per scan |
| CAPTCHA | Never | Occasionally triggered |
| Setup complexity | App Password + Gmail Filter | Only inbox name |
| Portability | Any Gmail account | Yopmail only |
| Email retention | Forever (archived with label) | ~8 days (Yopmail auto-deletes) |
| Security model | App Password (scoped, revocable) | No auth (public inbox) |

### Security Analysis

Security is designed around the principle of **least privilege** and **easy revocation**.

#### Credential Storage

| Secret | Storage | Scope | Impact if leaked |
|---|---|---|---|
| `YOPMAIL_ID` | GitHub Secret | — (public identifier) | Minimal — just an email address |
| `GMAIL_APP_PASSWORD` | GitHub Secret | IMAP read-only | Can read emails in the labeled mailbox only |

**GitHub Secrets** are:
- Encrypted at rest using AES-256
- Only decrypted at runtime and injected as environment variables
- Not visible in logs, not accessible via API
- Never printed by the script (CI mode outputs JSON with no env data)

#### App Password Characteristics

- 16-character string generated by Google (e.g., `abcd efgh ijkl mnop`)
- **Scoped to IMAP only** — cannot read other emails, cannot send mail, cannot change account password, cannot access Google Drive/Photos/etc.
- Does **not** bypass 2FA — it's a secondary credential that works _alongside_ 2FA
- Can be **revoked instantly** from Google Account → Security → App Passwords
- No OAuth refresh tokens, no long-lived credentials — single string, single point of control

#### State File Security

`last_processed.txt` is public in the repository but contains **only nftoken hashes** (e.g., `abc123def456...`). These tokens are:
- Single-use verification tokens from Netflix
- Worthless after processing
- Meaningless without the corresponding Netflix account session
- Not personally identifiable

An attacker reading this file learns nothing useful — just opaque strings with `done`/`in_progress` labels.

#### CI Log Security

All GitHub Actions logs in CI mode output only JSON:

```json
{"ok": true, "emails_checked": 5, "processed": 0}
```

This contains:
- No email addresses
- No verification links
- No Netflix tokens
- No App Passwords
- No personal information of any kind

#### Threat Model & Mitigations

| Threat | Likelihood | Impact | Mitigation |
|---|---|---|---|
| GitHub account compromised | Low | High — attacker reads Secrets | GitHub 2FA, strong password, PAT with minimal scope |
| App Password leaked | Low | Medium — IMAP read access to labeled emails | Instant revoke from Google Account; scoped to IMAP only |
| Token replay attack | Very low | Minimal — tokens are single-use | Tokens expire after first use; state file prevents re-processing |
| CI log leakage | Very low | Minimal — no sensitive data in logs | JSON-only CI mode; no env vars in output |
| IMAP MITM | Very low | Medium — could read emails in transit | IMAP over SSL (port 993); certificate validation built into Python's `imaplib` |

### Deduplication & Concurrency

The system uses a **claim-based deduplication** model to ensure exactly-once processing, even when multiple cron jobs overlap or a process crashes mid-flight.

#### Core Mechanism

```
┌──────────────────────────────────────────────────────┐
│                  last_processed.txt                   │
│                                                       │
│  nftoken=abc123	in_progress   ← claimed, being processed │
│  nftoken=def456	done          ← finished             │
│  nftoken=ghi789	done          ← finished             │
└──────────────────────────────────────────────────────┘
```

#### Components

1. **FileLock** (`filelock` library): mutual exclusion for state file reads/writes. Prevents two concurrent jobs (overlapping cron windows) from racing on the state file. Timeout: 10 seconds — if lock can't be acquired, the operation is skipped gracefully.

2. **Claim-based processing**: Before processing a token, it's marked `in_progress`. If it's already `done`, it's skipped. If it's `in_progress` (stale from a crashed process), it's re-claimed.

3. **try/finally release**: Every claimed token is guaranteed to be released in a `finally` block. If the process crashes mid-confirmation, the `in_progress` status is cleared, allowing the next cron job to retry.

4. **Atomic writes**: State file updates use `tempfile.mkstemp` + `os.replace` + `fsync` — ensuring the file is never left in a corrupted partial-write state, even if the machine loses power.

5. **Backward compatibility**: Lines without a tab separator are treated as `done` (legacy format migration).

### Polling Loop Design

```
Cron: 3 triggers/day
  ├── 06:00 GMT+7 (23:00 UTC)
  ├── 12:00 GMT+7 (05:00 UTC)
  └── 18:00 GMT+7 (11:00 UTC)

Each job:
  while true:
    1. IMAP scan (fetch last 5 Netflix emails)
    2. Dedup against last_processed.txt
    3. Process new tokens via Playwright
    4. Save state
    5. Every 20 scans (~10 min): git push state file
    6. sleep 30 seconds
```

- **3 cron triggers × 6h loop × 30s interval** = ~720 scans per day per job = up to **2,160 scans/day** total
- **30-second interval**: 2 IMAP connections per minute — well within Google's rate limits (hundreds/minute for IMAP)
- **State push every 20 scans** (~10 minutes): persists progress to the repo, ensuring minimal data loss if the runner dies
- **GitHub Actions 360-minute timeout**: the 6-hour job window. When the runner kills the job, the next cron picks up seamlessly — `in_progress` tokens are released and retried

### IMAP Connection Details

```python
mail = imaplib.IMAP4_SSL("imap.gmail.com")  # port 993, SSL
mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
mail.select('"Netflix-yopmail"', readonly=True)
mail.search(None, 'FROM', 'info@account.netflix.com')
# Fetch last 5 email UIDs only
for mid in data[0].split()[-5:]:
    mail.fetch(mid, "(RFC822)")
```

| Parameter | Value |
|---|---|
| Host | `imap.gmail.com:993` (SSL) |
| Auth | App Password (16 characters, no spaces in code) |
| Mailbox | `Netflix-yopmail` (read-only) |
| Search | `FROM "info@account.netflix.com"` |
| Fetch limit | Last 5 emails |
| Connection lifecycle | Opened, fetch, closed — no IDLE, no persistent connection |
| Rate | ≤ 2 connections/minute per job |

The connection is opened, the fetch is performed, and the connection is immediately closed via `mail.close()` + `mail.logout()` in a `finally` block. No IDLE mode is used — keeping things simple and stateless.

### Stealth Browser Configuration

Netflix's anti-bot detection looks for automation markers. The Playwright Chromium instance is configured to appear as a real Chrome browser:

```python
browser = await p.chromium.launch(headless=True, args=[
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--password-store=basic",
    "--use-mock-keychain",
    "--no-sandbox",
    "--disable-dev-shm-usage",
])

context = await browser.new_context(
    user_agent=ua.replace("HeadlessChrome", "Chrome"),
    locale="en-US",
    timezone_id="America/New_York",
    viewport={"width": 1920, "height": 1080},
    extra_http_headers={
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
    },
)
```

**Anti-detection measures injected via `add_init_script`:**
- `navigator.webdriver` → `false`
- `navigator.plugins` → realistic Chrome plugin array
- `window.chrome` → populated with expected `runtime`, `app`, `csi`, `loadTimes` objects
- `navigator.permissions.query` → patched for notifications
- `WebGLRenderingContext.getParameter` → spoofed GPU vendor (`Intel Inc.` / `Intel Iris OpenGL`)
- `navigator.hardwareConcurrency` → `4`
- `navigator.languages` → `['en-US', 'en']`

All anti-detection scripts are wrapped in `try/catch` guards — if one API is unavailable (e.g., `WebGL2RenderingContext` on older Chromium), it silently skips instead of aborting the entire injection.

---

## 📋 Version History

| Version | Changes |
|---|---|
| v16 | **Gmail IMAP replaces Yopmail web scraping** — App Password auth, IMAP fetch via `imaplib`, Gmail filter for auto-labeling, 30s polling interval |
| v15 | Gmail filter setup: auto-label `Netflix-yopmail` + forward to backup email |
| v14 | Polling loop architecture: 6-hour jobs × 3/day, state push every ~10 min |
| v13 | CI mode (`--ci` flag), GitHub Actions, public repository |
| v12 | Round 5 Claude Opus review — 11 fixes (token leak prevention, visibility filter, page leak fix) |
| v6–v11 | Rounds 1–4 code review — 85+ fixes, semaphore refactor for concurrency, `in_progress` leak fix |
| v5 | Initial release — Yopmail web scraping + Netflix automation |

---

## 📁 Repository Structure

```
netflix-yopmail/
├── main.py                     # All logic — single-file (IMAP + Playwright + state management)
├── last_processed.txt          # State — processed nftokens (tab-separated: token→status)
├── .github/workflows/
│   └── netflix.yml             # CI — 3×/day cron triggers + 6h polling loop
├── .gitignore
└── README.md
```

### Key Files

| File | Purpose |
|---|---|
| `main.py` | Single-file Python script containing all logic: IMAP email fetching, token extraction, Playwright browser automation (stealth), deduplication, state management, CI mode. ~500 lines, zero external dependencies beyond `playwright` and `filelock`. |
| `last_processed.txt` | Flat text file — tab-separated `token\tstatus` pairs. Tracks which Netflix tokens have been processed. Public but contains only opaque token hashes. |
| `.github/workflows/netflix.yml` | GitHub Actions workflow definition. 3 cron triggers at 06:00/12:00/18:00 GMT+7, each running a `while true` loop with 30-second intervals. Auto-commits state file every ~10 minutes. 360-minute timeout. |
| `.gitignore` | Excludes Python cache, IDE files, lock files, and local OAuth/IMAP test helpers. |

---

## 📊 Performance Metrics

| Metric | Value |
|---|---|
| IMAP scan time | < 1 second |
| Browser confirm time | 3–5 seconds per link |
| Max concurrent tabs | 5 (Semaphore-gated) |
| Scans per day (per job) | ~720 |
| Total scans per day | Up to 2,160 |
| Email fetch limit | Last 5 per scan |
| State sync interval | Every 20 scans (~10 minutes) |
| GitHub Actions runtime | Free (unlimited for public repos) |
| Memory usage | ~200 MB (Chromium headless) |

---

## 🔒 Privacy Note

This tool was built for **personal use**. It processes only Netflix verification emails from a single Gmail account. No data is sent to any third party — all processing happens within GitHub Actions' ephemeral Ubuntu runners. Netflix tokens are never logged, stored externally, or transmitted beyond the verification click itself.

If you fork this repo, you are responsible for your own email security. Use a strong GitHub password, enable 2FA, and scope any Personal Access Tokens to the minimum required permissions.

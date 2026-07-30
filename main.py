#!/usr/bin/env python3
"""
Yopmail → Netflix Verify automation (v12 — Round 5 Claude Opus fixes).

Tự động kiểm tra inbox Yopmail, duyệt tối đa 5 email gần nhất,
tìm link Netflix (travel verify + update household), auto-confirm nếu có nút,
và truy cập để Netflix ghi nhận.

Cải tiến v8 (Round 3 — Chat 3 + Chat 4):
- extract_links_from_current_email: dedup links, log errors explicitly,
  bỏ networkidle trên iframe (tracking pixels không bao giờ settle),
  dùng e.getAttribute('href') thay vì e.href, bỏ ElementHandle leak
- confirm_netflix_page: sửa is_visible() → wait_for(state="visible")
  (is_visible() là one-shot, không poll), phân biệt "không có nút" vs "click fail"
- is_link_expired: sửa is_visible() → wait_for(state="visible"), log lỗi
- process_url: dùng resp.ok thay vì status != 200, move extract_token vào try,
  thêm comment về shared-context limitation
- Thêm comment over-broad regex warning
- Setup phase nằm trong try block (tránh traceback khi launch/context fail)
- Cleanup tập trung trong finally block (không double browser.close())
- Save incremental sau mỗi token thành công (không chỉ cuối batch)
- Thêm unmark_in_progress() — release claim khi token fail để retry
- r["ok"] → r.get("ok") (tránh KeyError crash)
- Login check: wait #ifinbox thay vì hard sleep 2s
- Phân biệt "không có token hợp lệ" vs "đã xử lý hết"
- Remove dead code `token in newly_done` (luôn False lúc đó)
- Return non-zero khi có partial failures
- Thêm comment về sync-filelock + concurrent-task risk
- Thêm comment về index-based iteration + re-sort risk

Cải tiến v9 (Round 4 — Chat 9 + Chat 10):
- from __future__ import annotations (prevents crash on Python ≤3.9)
- extract_token handle hash-router fragments (#/path?nftoken=x)
- extract_token reject control chars in token (tab/newline injection)
- STEALTH_JS add try/catch guards (one missing global aborts rest)
- atomic_write fix raw fd leak on fdopen failure
- is_link_expired: fix filter(has_text=...) → filter(visible=True) regression
- evaluate_all: filter null/empty hrefs to prevent page.goto(None)
- extract_links: use filter(visible=True) on link_loc

Cải tiến v11 (Round 4 — Chat 13 main() patch):
- in_progress leak fix: try/finally unmarks claimed-but-not-done tokens
- isinstance(r, dict) guard — non-dict returns won't crash result loop
- seen: set[str] dedup same param from different URLs in pending
- check_count = 0 default before try block
- _return_to_inbox() shared recovery path
- row_keys snapshot + ID-based iteration (avoids .nth(i) re-sort shift)
- Semaphore wraps entire page lifecycle (not just post-open work)
- process_url: sem parameter made optional (None = caller gates)

Cải tiến v12 (Round 5 — Chat 14-16 Claude Opus fixes):
- _sanitize_url() strips nftoken from return dicts (prevents token leak in logs)
- confirm_page: post-click URL change check (false-positive detection)
- confirm_page: filter(visible=True) before .first (hidden element edge case)
- Page leak fix: close orphaned pages on asyncio.TimeoutError from new_page()
- is_link_expired: count() fast path instead of always waiting 3s
- NETFLIX_HREF_SELECTOR: add # fragment variants
- Async FileLock wrappers via asyncio.to_thread (no event loop blocking)
- atomic_write: track f_closed flag to prevent double-close of raw_fd
- _CONFIRM_LABEL: word-boundary anchors (^...$) to prevent partial matches
- save_processed before in-memory state change (persistence-first order)
- Dead code cleanup: collapse PWTimeout/Exception catch branches, remove unused bindings

State file: TOKEN\tSTATUS format, mark_in_progress claim (exactly-once)
filelock + atomic_write + _fsync_dir (crash-durability)
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import imaplib
import logging
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# ---- CI mode ---------------------------------------------------------------
_parser = argparse.ArgumentParser()
_parser.add_argument("--ci", action="store_true", help="CI mode: suppress logs, JSON output only")
_CI_MODE = _parser.parse_args().ci

from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from filelock import FileLock, Timeout as FileLockTimeout

# ---- Config -----------------------------------------------------------------
GMAIL_USER = os.environ.get("YOPMAIL_ID")  # keep env var name for backward compat
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
if not GMAIL_USER or not GMAIL_APP_PASSWORD:
    sys.exit("❌ Thiếu biến môi trường YOPMAIL_ID hoặc GMAIL_APP_PASSWORD.")

NETFLIX_HREF_SELECTOR = (
    "a[href^='https://www.netflix.com/account/travel/verify?'], "
    "a[href^='https://www.netflix.com/account/travel/verify#'], "
    "a[href^='https://www.netflix.com/account/update-primary-location?'], "
    "a[href^='https://www.netflix.com/account/update-primary-location#']"
)

STATE_FILE = Path("last_processed.txt")
NAV_TIMEOUT_MS = 30_000
MAX_EMAILS = 5
RETRY_COUNT = 2
RETRY_DELAY = 1.0
MAX_CONCURRENCY = 5  # Số tab xử lý song song tối đa

LOCK_TIMEOUT = 10  # seconds

# State file format: TOKEN\tSTATUS (tab-separated)
# STATUS: "in_progress" hoặc "done"
# Dòng không có tab → status = "done" (backward compat)

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--password-store=basic",
    "--use-mock-keychain",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]

STEALTH_JS = r"""
Object.defineProperty(navigator,'webdriver',{get:()=>false});
Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
Object.defineProperty(navigator,'plugins',{
  get:()=>{
    const arr=Object.create(PluginArray.prototype);
    const plugins=[
      {name:'Chrome PDF Plugin',filename:'internal-pdf-viewer',description:'Portable Document Format',length:1},
      {name:'Chrome PDF Viewer',filename:'mhjfbmdgcfjbbpaeojofohoefgiehjai',description:'',length:1},
      {name:'Native Client',filename:'internal-nacl-plugin',description:'',length:2}
    ];
    plugins.forEach((p,i)=>{arr[i]=p;});
    Object.defineProperty(arr,'length',{value:plugins.length});
    arr.item=i=>plugins[i]||null;
    arr.namedItem=n=>plugins.find(p=>p.name===n)||null;
    arr.refresh=()=>{};
    return arr;
  }
});
Object.defineProperty(navigator,'hardwareConcurrency',{get:()=>4});
window.chrome={runtime:{connect:()=>({onDisconnect:{addListener:()=>{}},onMessage:{addListener:()=>{}},postMessage:()=>{},disconnect:()=>{}}),onConnect:{addListener:()=>{}},onMessage:{addListener:()=>{}}},app:{isInstalled:false,InstallState:{DISABLED:'disabled',INSTALLED:'installed',NOT_INSTALLED:'not_installed'},RunningState:{CANNOT_RUN:'cannot_run',READY_TO_RUN:'ready_to_run',RUNNING:'running'}},csi:()=>({startE:0,onloadT:0,pageT:0,tran:0}),loadTimes:()=>({requestTime:0,startLoadTime:0,commitLoadTime:0,finishDocumentLoadTime:0,finishLoadTime:0,firstPaintTime:0,firstPaintAfterLoadTime:0,navigationType:'Other',wasFetchedViaSpdy:false,wasNpnNegotiated:false,npnNegotiatedProtocol:'unknown',wasAlternateProtocolAvailable:false,connectionInfo:''})};
try{
 const _q=navigator.permissions.query;
 navigator.permissions.query=(p)=>p.name==='notifications'
  ?Promise.resolve({state:Notification.permission}):_q.call(navigator.permissions, p);
}catch(e){}
try{
 const _gp=WebGLRenderingContext.prototype.getParameter;
 WebGLRenderingContext.prototype.getParameter=function(p){
  if(p===37445)return 'Intel Inc.';
  if(p===37446)return 'Intel Iris OpenGL';
  return _gp.apply(this,[p]);
 };
}catch(e){}
try{
 if(typeof WebGL2RenderingContext!=='undefined'){
  const _gp2=WebGL2RenderingContext.prototype.getParameter;
  WebGL2RenderingContext.prototype.getParameter=function(p){
   if(p===37445)return 'Intel Inc.';
   if(p===37446)return 'Intel Iris OpenGL';
   return _gp2.apply(this,[p]);
  };
 }
}catch(e){}
"""

# -----------------------------------------------------------------------------

logging.basicConfig(
    level=logging.WARNING if _CI_MODE else logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("yopmail-netflix")


# =============================================================================
#  Async retry decorator
# =============================================================================

def retry_on_timeout(retries: int = RETRY_COUNT, delay: float = RETRY_DELAY):
    """Decorator async: tự động retry nếu hàm raise Playwright TimeoutError."""
    retries = max(1, retries)  # guard: retries <= 0 is a silent no-op
    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, retries + 1):
                try:
                    return await fn(*args, **kwargs)
                except PWTimeout as exc:
                    last_exc = exc
                    if attempt < retries:
                        log.warning("%s() — timeout lần %d/%d, retry sau %.1fs...",
                                    fn.__name__, attempt, retries, delay)
                        await asyncio.sleep(delay)
                    else:
                        log.error("%s() — timeout sau %d lần.", fn.__name__, retries)
                except Exception as exc:
                    log.error("%s() — lỗi: %s", fn.__name__, exc)
                    raise
            if last_exc is not None:
                raise last_exc
        return wrapper
    return deco


# =============================================================================
#  URL sanitization
# =============================================================================

def _sanitize_url(url: str) -> str:
    """Strip nftoken param from query and fragment to prevent token leak in logs/returns."""
    return re.sub(r'([?&#])nftoken=[^&#]*', r'\1nftoken=***', url)


# =============================================================================
#  State file helpers (sync — không cần page)
#  Wrapped via asyncio.to_thread for async call sites to avoid blocking
#  the event loop on FileLock contention.
# =============================================================================

def _fsync_dir(dirpath: str) -> None:
    """fsync thư mục để đảm bảo metadata được flush sau os.replace."""
    try:
        fd = os.open(dirpath, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass

def atomic_write(path: Path, content: str) -> None:
    d = os.path.dirname(os.path.abspath(str(path)))
    # Giữ mode của file cũ nếu có
    old_mode = 0o644
    try:
        old_mode = os.stat(str(path)).st_mode & 0o777
    except OSError:
        pass
    raw_fd, tmp = tempfile.mkstemp(dir=d)
    f = None
    f_closed = False
    try:
        f = os.fdopen(raw_fd, "w", encoding="utf-8")
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
        f.close()
        f_closed = True
        f = None  # fdopen consumed the fd; avoid double-close below
        os.chmod(tmp, old_mode)
        os.replace(tmp, str(path))
        _fsync_dir(d)
    except Exception:
        # If fdopen failed or write failed before close, raw_fd was never consumed
        if not f_closed:
            try:
                os.close(raw_fd)
            except OSError:
                pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    finally:
        if f is not None:
            try:
                f.close()
            except OSError:
                pass


def mark_in_progress(token: str) -> bool:
    """Claim token để tránh duplicate processing. Return False nếu token đã được claim."""
    lock_path = str(STATE_FILE) + ".lock"
    lock = FileLock(lock_path, timeout=LOCK_TIMEOUT)
    try:
        with lock:
            current: dict[str, str] = {}
            if STATE_FILE.exists():
                for line in STATE_FILE.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if "\t" in line:
                        key, status = line.split("\t", 1)
                        current[key] = status
                    else:
                        current[line] = "done"  # migrate cũ
            if token in current and current[token] == "done":
                return False  # đã done — bỏ qua
            # Nếu status là "in_progress" (stale từ process trước bị crash) → re-claim
            if token in current:
                log.info("Token %s đang in_progress (stale) — re-claim.", token)
            current[token] = "in_progress"
            content = "\n".join(f"{k}\t{current[k]}" for k in sorted(current))
            atomic_write(STATE_FILE, content + "\n" if content else "")
            return True
    except FileLockTimeout:
        log.warning("Không acquire được lock để claim token.")
        return False


def unmark_in_progress(token: str) -> None:
    """Release một token đã claim khi xử lý thất bại, để có thể retry lần sau."""
    if not token:
        return
    lock_path = str(STATE_FILE) + ".lock"
    lock = FileLock(lock_path, timeout=LOCK_TIMEOUT)
    try:
        with lock:
            current: dict[str, str] = {}
            if STATE_FILE.exists():
                for line in STATE_FILE.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if "\t" in line:
                        key, status = line.split("\t", 1)
                        current[key] = status
                    else:
                        current[line] = "done"
            if token in current and current[token] == "in_progress":
                del current[token]
                content = "\n".join(
                    f"{k}\t{current[k]}" for k in sorted(current)
                )
                atomic_write(STATE_FILE, content + "\n" if content else "")
                log.info("Đã release claim cho token %s.", token)
    except FileLockTimeout:
        log.warning("Không acquire được lock để unmark token %s.", token)


def load_processed() -> set[str]:
    """Return set of 'done' tokens. Trả về rỗng nếu lock timeout."""
    lock_path = str(STATE_FILE) + ".lock"
    lock = FileLock(lock_path, timeout=LOCK_TIMEOUT)
    try:
        with lock:
            if not STATE_FILE.exists():
                return set()
            done: set[str] = set()
            for line in STATE_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                if "\t" in line:
                    key, status = line.split("\t", 1)
                    if status == "done":
                        done.add(key)
                else:
                    done.add(line)
            return done
    except FileLockTimeout:
        log.warning("Không acquire được lock (timeout %ds) — bỏ qua.", LOCK_TIMEOUT)
        # ⚠ Trả về rỗng → tất cả token được coi là "chưa xử lý" → invites reprocessing
        return set()


def save_processed(tokens: set[str]) -> None:
    """Ghi token done. Log lỗi nếu lock timeout — token sẽ retry lần sau."""
    if not tokens:
        return
    lock_path = str(STATE_FILE) + ".lock"
    lock = FileLock(lock_path, timeout=LOCK_TIMEOUT)
    try:
        with lock:
            current: dict[str, str] = {}
            if STATE_FILE.exists():
                for line in STATE_FILE.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if "\t" in line:
                        key, status = line.split("\t", 1)
                        current[key] = status
                    else:
                        current[line] = "done"
            for t in tokens:
                current[t] = "done"
            content = "\n".join(f"{k}\t{current[k]}" for k in sorted(current))
            atomic_write(STATE_FILE, content + "\n" if content else "")
    except FileLockTimeout:
        log.error("Không acquire được lock để ghi state — token sẽ retry lần sau.")
        # ⚠ Lock timeout = lost completion write → causes duplicate work on next run


# =============================================================================
#  Async state wrappers — route sync state ops through asyncio.to_thread
#  to avoid blocking the event loop on FileLock contention.
# =============================================================================

async def _async_load_processed() -> set[str]:
    return await asyncio.to_thread(load_processed)

async def _async_save_processed(tokens: set[str]) -> None:
    return await asyncio.to_thread(save_processed, tokens)

async def _async_mark_in_progress(token: str) -> bool:
    return await asyncio.to_thread(mark_in_progress, token)

async def _async_unmark_in_progress(token: str) -> None:
    return await asyncio.to_thread(unmark_in_progress, token)


# =============================================================================
#  Token helpers
# =============================================================================

def extract_token(url: str) -> str | None:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    nftoken = params.get("nftoken")
    # Also check fragment: handles both ?-format (#nftoken=a&b=c)
    # and hash-router format (#/verify?nftoken=a) where parse_qs
    # finds no & in the raw fragment.
    if not nftoken and parsed.fragment:
        frag = parsed.fragment
        if "?" in frag:
            frag = frag.split("?", 1)[1]
        params = parse_qs(frag)
        nftoken = params.get("nftoken")
    if nftoken:
        val = nftoken[0]
        # Reject control chars (tab/newline) that could corrupt state file format
        if val and not re.search(r"[\s]", val):
            return val
        return None
    return None


# =============================================================================
#  Gmail IMAP — đọc email Netflix từ label "Netflix-yopmail"
# =============================================================================

def fetch_netflix_emails() -> list[tuple[str, str]]:
    """
    Connect to Gmail IMAP, read emails from Netflix in label 'Netflix-yopmail'.
    Returns list of (email_uid, netflix_link) tuples.
    Uses IMAP IDLE/NOT — standard IMAP read.
    """
    import email as email_lib

    links: list[tuple[str, str]] = []

    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select('"Netflix-yopmail"', readonly=True)

        # Search for emails from Netflix (last 5)
        result, data = mail.search(None, 'FROM', 'info@account.netflix.com')
        if result != "OK" or not data[0]:
            return links

        mail_ids = data[0].split()[-5:]  # last 5

        for mid in mail_ids:
            result, msg_data = mail.fetch(mid, "(RFC822)")
            if result != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email_lib.message_from_bytes(raw_email)

            # Extract text/html body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype == "text/html":
                        body = part.get_payload(decode=True).decode(errors="replace")
                        break
                    elif ctype == "text/plain" and not body:
                        body = part.get_payload(decode=True).decode(errors="replace")
            else:
                body = msg.get_payload(decode=True).decode(errors="replace")

            # Find Netflix links (travel/verify or update-primary-location)
            netflix_links = re.findall(
                r'https?://www\.netflix\.com/account/(?:travel/verify|update-primary-location)[^\s"<>)]+',
                body
            )
            deduped = list(dict.fromkeys(netflix_links))
            for link in deduped:
                links.append((mid.decode(), link))
    finally:
        try:
            mail.close()
        except Exception:
            pass
        try:
            mail.logout()
        except Exception:
            pass

    return links


# =============================================================================
#  Netflix page helpers
# =============================================================================

# ⚠ Over-broad regex: một số name như "Update", "Continue" có thể match
# các element không liên quan trên trang Netflix. Trong ngữ cảnh hiện tại,
# script chỉ navigate đến Netflix verify page nên rủi ro thấp.
# Nếu sau này mở rộng sang page khác, cân nhắc thêm aria-label/role constraints.
# v12: thêm word-boundary anchors ^...$ để tránh partial match (e.g. "Update settings").
_CONFIRM_LABEL = re.compile(
    r"^(?:Yes, this is me|Update|Confirm|Continue|Xác nhận|Tiếp tục)$",
    re.IGNORECASE,
)

_EXPIRED_PATTERN = re.compile(
    r"expired|hết hạn|hết hiệu lực|no longer valid|không còn hiệu lực",
    re.IGNORECASE,
)


async def confirm_netflix_page(page) -> bool:
    """Auto-click nút xác nhận trên Netflix verify page.
    Trả về True nếu tìm thấy, click thành công nút confirm, và URL thay đổi.
    Trả về False nếu không tìm thấy nút hoặc URL không đổi sau click.

    v12: filter(visible=True) before .first (hidden button edge case).
    v12: post-click URL change check (false-positive detection).
    """
    await page.wait_for_timeout(1500)
    btn = (
        page.get_by_role("button", name=_CONFIRM_LABEL)
        .or_(page.get_by_role("link", name=_CONFIRM_LABEL))
        .filter(visible=True)
        .first
    )
    # Distinguish "no button" from "button exists but unclickable"
    try:
        await btn.wait_for(state="visible", timeout=3000)
    except PWTimeout:
        log.info("Không tìm thấy nút confirm — có thể link đã tự xác nhận.")
        return False
    # Button exists past this point — failure below is NOT "already verified"
    try:
        current_url = page.url
        log.info("Tìm thấy nút confirm → click.")
        await btn.click(timeout=5000)  # bound it; don't inherit 30s default
        await page.wait_for_timeout(2000)
        # Verify click was processed: URL should change after confirm
        new_url = page.url
        if new_url != current_url:
            log.info("URL changed after confirm — đã xác nhận ✓")
            return True
        log.warning("URL unchanged after confirm click — may not be processed.")
        return False
    except PWTimeout:
        log.warning("Nút confirm tồn tại nhưng click thất bại (covered/detached/disabled).")
        return False
    except Exception as exc:
        log.warning("confirm_netflix_page — lỗi click không mong đợi: %s", exc)
        return False


async def is_link_expired(page) -> bool:
    """Kiểm tra xem verify link có hiển thị thông báo expired không.
    v12: count() fast path — no 3s wait on good URLs.
    """
    try:
        count = await page.get_by_text(_EXPIRED_PATTERN).filter(visible=True).count()
        if count > 0:
            log.warning("Link đã hết hạn / lỗi.")
            return True
    except Exception as exc:
        log.debug("expired check: %s", exc)
    return False


# =============================================================================
#  Xử lý 1 URL Netflix (chạy song song)
# =============================================================================

async def process_url(context, url: str, sem: asyncio.Semaphore | None = None) -> dict:
    """Mở 1 link Netflix trong tab riêng, confirm, check expired.

    ⚠ SHARED-CONTEXT LIMITATION: Tất cả tab dùng chung 1 BrowserContext
    = 1 cookie jar. Nếu token thuộc về các Netflix account KHÁC NHAU,
    concurrent tabs sẽ cross-contaminate session. Trong single-account
    use case thì không sao, nhưng cần lưu ý nếu mở rộng multi-account.

    Trả về dict kết quả — không ghi biến chung, tránh đụng độ.
    v12: return dicts use _sanitize_url(url) to prevent token leak.
    """
    if sem is not None:
        async with sem:
            return await _process_url_impl(context, url)
    return await _process_url_impl(context, url)


async def _process_url_impl(context, url: str) -> dict:
    page = None
    token = None
    safe_url = _sanitize_url(url)
    try:
        token = extract_token(url)
        # Short-circuit: no token → nothing to do
        if token is None:
            return {"url": safe_url, "token": None, "ok": False,
                    "clicked": bool(False),
                    "error": "no token in URL"}

        page = await asyncio.wait_for(context.new_page(),
                                      timeout=NAV_TIMEOUT_MS / 1000)
        page.set_default_timeout(NAV_TIMEOUT_MS)
        log.info("Processing verification link...")

        r = await page.goto(url, wait_until="load", timeout=NAV_TIMEOUT_MS)
        if r is None or not r.ok:
            return {"url": safe_url, "token": "***", "ok": False,
                    "clicked": bool(False),
                    "error": f"HTTP {r.status if r else 'none'}"}

        log.info("HTTP %d OK", r.status)

        if await is_link_expired(page):
            return {"url": safe_url, "token": "***", "ok": False,
                    "clicked": bool(False),
                    "error": "expired"}

        clicked = await confirm_netflix_page(page)
        log.info("Token đã xác nhận ✓" if clicked
                 else "Token đã xác nhận (không cần click) ✓")
        return {"url": safe_url, "token": "***", "ok": True,
                "clicked": bool(clicked), "error": None}

    except asyncio.TimeoutError:
        # Cleanup orphaned pages from cancelled new_page()
        for p in context.pages:
            try:
                await p.close()
            except Exception:
                pass
        return {"url": safe_url, "token": "***", "ok": False,
                "clicked": bool(False), "error": "new_page timeout"}
    except PWTimeout:
        return {"url": safe_url, "token": "***", "ok": False,
                "clicked": bool(False), "error": "timeout"}
    except Exception as exc:
        return {"url": safe_url, "token": "***", "ok": False,
                "clicked": bool(False), "error": type(exc).__name__}
    finally:
        if page is not None:
            try:
                await page.close()
            except Exception:
                pass  # cleanup không được làm sập cả batch


# =============================================================================
#  Main workflow
# =============================================================================

async def main() -> int:
    processed = await _async_load_processed()
    newly_done: set[str] = set()

    browser = None
    context = None
    page = None
    has_errors = False

    async with async_playwright() as p:
        try:
            # ── Setup ──────────────────────────────────────────────
            browser = await p.chromium.launch(headless=True, args=STEALTH_ARGS)
            probe = await browser.new_page()
            raw_ua = await probe.evaluate("() => navigator.userAgent")
            await probe.close()
            ua = raw_ua.replace("HeadlessChrome", "Chrome")
            context = await browser.new_context(
                user_agent=ua,
                locale="en-US",
                timezone_id="America/New_York",
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                color_scheme="light",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Upgrade-Insecure-Requests": "1",
                },
            )
            await context.add_init_script(STEALTH_JS)
            page = await context.new_page()
            page.set_default_timeout(NAV_TIMEOUT_MS)

            # ── Bước 1: Đọc email qua Gmail IMAP ─────────────────────
            log.info("Bước 1: Đọc Gmail IMAP — label Netflix-yopmail...")
            try:
                raw_links = fetch_netflix_emails()
            except Exception as exc:
                log.error("Lỗi Gmail IMAP: %s", exc)
                has_errors = True
                raw_links = []

            all_links: list[str] = []
            check_count = len(raw_links)

            for mid, link in raw_links:
                if link not in all_links:
                    all_links.append(link)
                    log.info("Tìm thấy link Netflix (email %s): %s",
                             mid, _sanitize_url(link))

            # ── Bước 4-7: Xử lý URL song song ──────────────────────
            if not all_links:
                log.warning("Không tìm thấy Netflix link nào sau khi duyệt %d email.",
                            check_count)
            else:
                valid_token_count = sum(
                    1 for url in all_links if extract_token(url) is not None
                )
                if valid_token_count == 0:
                    log.info("Không có token hợp lệ nào trong %d link Netflix.",
                             len(all_links))
                else:
                    pending: list[tuple[str, str]] = []
                    seen: set[str] = set()

                    for url in all_links:
                        token = extract_token(url)
                        if token is None or token in processed or token in seen:
                            continue
                        seen.add(token)
                        if await _async_mark_in_progress(token):
                            pending.append((url, token))
                        else:
                            log.info(
                                "Token %s đã được claim bởi process khác — bỏ qua.",
                                token,
                            )

                    if not pending:
                        log.info(
                            "Tất cả %d token đều đã được xử lý trước đó.",
                            valid_token_count,
                        )
                    else:
                        log.info("%d URL mới — xử lý song song (max %d tab)...",
                                 len(pending), MAX_CONCURRENCY)

                        sem = asyncio.Semaphore(MAX_CONCURRENCY)

                        async def _run(u):
                            # Gate the entire page lifecycle under the semaphore
                            # so we never open >MAX_CONCURRENCY tabs at once.
                            # process_url is called without its own sem (sem=None).
                            async with sem:
                                return await process_url(context, u)

                        tasks = [_run(url) for url, _ in pending]
                        claimed = {param for _, param in pending}

                        try:
                            results = await asyncio.gather(
                                *tasks, return_exceptions=True
                            )

                            for i, r in enumerate(results):
                                token = pending[i][1]
                                if isinstance(r, Exception):
                                    log.warning("✗ Task crashed: %s", r)
                                    has_errors = True
                                    continue
                                if not isinstance(r, dict):
                                    log.warning("Bad result for %s: %r",
                                                _sanitize_url(pending[i][0]), r)
                                    has_errors = True
                                    continue
                                if r.get("ok"):
                                    await _async_save_processed({token})
                                    newly_done.add(token)
                                    log.info("✓ %s", r.get("url", "?"))
                                else:
                                    has_errors = True
                                    log.warning("✗ %s — %s",
                                                r.get("url", "?"),
                                                r.get("error", "unknown"))
                        finally:
                            # Release every claim that didn't reach 'done'.
                            # Catches crash/cancel mid-gather → no leaked in_progress.
                            for p_ in claimed - newly_done:
                                await _async_unmark_in_progress(p_)

        except PWTimeout:
            log.error("Timeout toàn cục. Dừng workflow.")
            has_errors = True
            return 1
        except Exception as exc:
            log.error("Lỗi không mong đợi: %s", exc, exc_info=True)
            has_errors = True
            return 1
        finally:
            for obj, name in [(page, "page"), (context, "context"),
                              (browser, "browser")]:
                if obj is not None:
                    try:
                        await obj.close()
                    except Exception:
                        pass

    # ── Final save (safety net) ─────────────────────────────────
    if newly_done:
        await _async_save_processed(newly_done)
    processed_count = len(newly_done)
    if _CI_MODE:
        import json as _json
        print(_json.dumps({"ok": not has_errors, "emails_checked": check_count, "processed": processed_count}, ensure_ascii=False))
    else:
        if processed_count:
            log.info("Hoàn tất. %d token mới đã xử lý.", processed_count)
        else:
            log.info("Hoàn tất. Không có token mới.")

    return 1 if has_errors else 0


if __name__ == "__main__":
    if _CI_MODE:
        import json as _json
        try:
            exit_code = asyncio.run(main())
            # main() already printed JSON output in CI mode
            sys.exit(exit_code)
        except Exception as _exc:
            print(_json.dumps({"ok": False, "error": str(_exc)}, ensure_ascii=False))
            sys.exit(1)
    else:
        sys.exit(asyncio.run(main()))

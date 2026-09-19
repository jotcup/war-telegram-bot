# -*- coding: utf-8 -*-
"""
ربات جنگ جهانی (World War Strategy Bot) برای تلگرام — نسخه‌ی تک‌فایلی.
این فایل حاصل ادغام تمام ماژول‌های پروژه در یک فایل پایتونیه تا اجرا روی
Pydroid 3 ساده‌تر باشه (فقط همین یک فایل رو باز و Run کن).

نکته: توکن ربات، آیدی ادمین‌ها، شماره کارت پرداخت و کانال اخبار پایین‌تر
در بخش «تنظیمات» همین فایل قرار دارن.
"""
import sqlite3
import os
import time
import threading
import random
import shutil
import traceback
import requests


# ======================================================================
# بخش برگرفته از: config.py
# ======================================================================
# -*- coding: utf-8 -*-
"""
تنظیمات محرمانه ربات.
توکن و آیدی ادمین‌ها فقط اینجا نگه‌داری می‌شن و در بقیه‌ی کد Hard-code نمی‌شن.
"""

# توکن ربات تلگرام (از @BotFather تلگرام گرفته شده)
BOT_TOKEN = "8760251210:AAF2fNsjBdPejOMaYJTTHQPjz00XAwgpfxA"

# آیدی عددی ادمین‌های اصلی بازی (می‌تونی چند نفر اضافه کنی)
ADMIN_IDS = [7443146366, 8524573838, 5856916684]

# آدرس پایه‌ی API تلگرام
TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"

# آیدی کانال رسمی برای انتشار اخبار/بیانیه‌ها (اختیاری - اگر نداری خالی بذار "")
NEWS_CHANNEL = "@worldwarrr74"

# مسیر دیتابیس دائمی
# روی Railway یک Volume را روی /app/data Mount کن و DB_PATH=/app/data/warbot.db بگذار.
# در اجرای محلی/Pydroid اگر DB_PATH تنظیم نشده باشد، همان warbot.db کنار برنامه استفاده می‌شود.
DB_PATH = os.getenv("DB_PATH", "warbot.db")

# پوشه دیتابیس را در صورت نیاز خودکار می‌سازیم.
_db_dir = os.path.dirname(os.path.abspath(DB_PATH))
os.makedirs(_db_dir, exist_ok=True)

# فاصله‌ی زمانی هر tick اقتصادی/تولید (ثانیه) - هر چند وقت یک‌بار درآمد/تولید محاسبه بشه
TICK_INTERVAL_SECONDS = 900  # هر ۱۵ دقیقه

# فاصله‌ی poll از سرور تلگرام (ثانیه)
POLL_TIMEOUT = 20

# ---------------------------------------------------------------- پرداخت‌ها
# توکن درگاه پرداخت تلگرام برای پرداخت‌های کاربران (کشورهای VIP و پک‌ها).
# این مقدار به‌عنوان provider_token در متد sendInvoice تلگرام فرستاده می‌شه.
# قبل از فعال کردن خرید، توکن درگاه پرداخت تلگرام را اینجا قرار بده.
TELEGRAM_PROVIDER_TOKEN = ""  # توکن درگاه پرداخت تلگرام؛ برای پرداخت واقعی تنظیم شود
TELEGRAM_CURRENCY = "IRR"  # ارز فاکتور
# شماره کارتی که وجه خریدهای کاربران (VIP/پک‌ها) دستی بهش واریز می‌شه.
# چون تلگرام برای ریال ایران درگاه پرداخت رسمی نداره، پرداخت از این مسیر
# به‌صورت «کارت‌به‌کارت + تایید دستی ادمین» انجام می‌شه (نه sendInvoice واقعی).
PAYMENT_CARD_NUMBER = "6219861856566285"
PAYMENT_CARD_HOLDER = "آمی سما"

# قیمت‌ها به تومان (خودت در همینجا قابل تغییره)
VIP_COUNTRY_PRICE_TOMAN = 30
PACK_PRICE_TOMAN = 10
CUSTOM_COUNTRY_PRICE_TOMAN = 20

# نام کشورهایی که VIP (فقط با پرداخت پول واقعی قابل دریافت) هستن
VIP_COUNTRY_NAMES = ["روسیه", "آمریکا", "چین"]

# کشورهای ویژه‌ای که نقشی در بازی ندارن و فقط از طریق پنل ادمین به کسی داده می‌شن
SPECIAL_COUNTRY_NAMES = ["مالک", "ادمین", "ادمین ۲"]


# ======================================================================
# بخش برگرفته از: database.py
# ======================================================================
# -*- coding: utf-8 -*-
"""
لایه‌ی دیتابیس (SQLite).
مهم: همیشه از CREATE TABLE IF NOT EXISTS استفاده می‌شه تا با آپدیت نسخه‌ی برنامه،
دیتابیس قبلی پاک یا ریست نشه. هیچ DROP TABLE ای در مسیر عادی اجرا وجود نداره.
"""
import sqlite3
import time
import threading


_lock = threading.Lock()


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


_conn = get_conn()


def now():
    return int(time.time())


def init_db():
    with _lock:
        c = _conn.cursor()

        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            country_id INTEGER,
            is_admin INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            joined_at INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS countries (
            id INTEGER PRIMARY KEY,
            name TEXT,
            flag TEXT,
            iso2 TEXT,
            owner_id INTEGER,
            population REAL,
            treasury REAL DEFAULT 50000,
            tax_rate REAL DEFAULT 0.20,
            economy_score REAL DEFAULT 50,
            tech_score REAL DEFAULT 10,
            morale REAL DEFAULT 70,
            satisfaction REAL DEFAULT 60,
            military_budget_pct REAL DEFAULT 30,
            research_budget_pct REAL DEFAULT 15,
            hp REAL DEFAULT 1000,
            max_hp REAL DEFAULT 1000,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            conquests INTEGER DEFAULT 0,
            debt REAL DEFAULT 0,
            active INTEGER DEFAULT 1,
            is_special INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            country_id INTEGER,
            resource TEXT,
            amount REAL DEFAULT 0,
            PRIMARY KEY (country_id, resource)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS factories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country_id INTEGER,
            ftype TEXT,
            level INTEGER DEFAULT 1,
            built_at INTEGER,
            last_production INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS army (
            country_id INTEGER,
            unit_key TEXT,
            quantity INTEGER DEFAULT 0,
            PRIMARY KEY (country_id, unit_key)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS territories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            owner_id INTEGER,
            original_owner_id INTEGER,
            population REAL,
            economic_value REAL,
            strategic_value INTEGER DEFAULT 1,
            is_strait INTEGER DEFAULT 0,
            strait_bonus REAL DEFAULT 0
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS wars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attacker_id INTEGER,
            defender_id INTEGER,
            status TEXT DEFAULT 'active',
            started_at INTEGER,
            ended_at INTEGER,
            result TEXT,
            atk_casualties REAL DEFAULT 0,
            def_casualties REAL DEFAULT 0
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS relations (
            country_a INTEGER,
            country_b INTEGER,
            status TEXT DEFAULT 'neutral',
            updated_at INTEGER,
            PRIMARY KEY (country_a, country_b)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS diplomacy_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_id INTEGER,
            to_id INTEGER,
            kind TEXT,
            status TEXT DEFAULT 'pending',
            created_at INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS tech (
            country_id INTEGER,
            tech_key TEXT,
            level INTEGER DEFAULT 0,
            PRIMARY KEY (country_id, tech_key)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS research_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country_id INTEGER,
            tech_key TEXT,
            finishes_at INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            category TEXT,
            created_at INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS events_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            created_at INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS espionage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spy_country INTEGER,
            target_country INTEGER,
            action TEXT,
            success INTEGER,
            created_at INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS market (
            resource TEXT PRIMARY KEY,
            price REAL,
            supply REAL DEFAULT 1000,
            demand REAL DEFAULT 1000
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS trade_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country_id INTEGER,
            resource TEXT,
            action TEXT,
            amount REAL,
            price REAL,
            created_at INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            detail TEXT,
            created_at INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            kind TEXT,
            payload TEXT,
            amount_toman REAL,
            charge_id TEXT,
            created_at INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS pending_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            chat_id INTEGER,
            kind TEXT,
            payload TEXT,
            amount_toman REAL,
            status TEXT DEFAULT 'awaiting_claim',
            created_at INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS un_members (
            country_id INTEGER PRIMARY KEY,
            joined_at INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS un_resolutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposer_id INTEGER,
            title TEXT,
            description TEXT,
            status TEXT DEFAULT 'voting',
            created_at INTEGER,
            closed_at INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS un_votes (
            resolution_id INTEGER,
            country_id INTEGER,
            vote TEXT,
            PRIMARY KEY (resolution_id, country_id)
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS alliances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            leader_country_id INTEGER,
            created_at INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS alliance_members (
            alliance_id INTEGER,
            country_id INTEGER PRIMARY KEY,
            joined_at INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS alliance_join_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alliance_id INTEGER,
            country_id INTEGER,
            status TEXT DEFAULT 'pending',
            created_at INTEGER
        )""")

        c.execute("""
        CREATE TABLE IF NOT EXISTS event_images (
            category TEXT PRIMARY KEY,
            photo TEXT,
            updated_at INTEGER
        )""")

        _conn.commit()

    # --- migration امن برای دیتابیس‌های قدیمی‌تر: ستون‌های جدید رو بدون پاک‌کردن داده اضافه می‌کنه ---
    # (این دو خط عمداً خارج از "with _lock" هستن چون _add_column_if_missing خودش لاک می‌گیره)
    _add_column_if_missing("countries", "is_special", "INTEGER DEFAULT 0")
    _add_column_if_missing("countries", "is_vip", "INTEGER DEFAULT 0")


def _add_column_if_missing(table, column, coldef):
    with _lock:
        cols = [r["name"] for r in _conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            _conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coldef}")
            _conn.commit()


def query(sql, params=()):
    with _lock:
        cur = _conn.execute(sql, params)
        rows = cur.fetchall()
        return rows


def query_one(sql, params=()):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql, params=()):
    with _lock:
        cur = _conn.execute(sql, params)
        _conn.commit()
        return cur.lastrowid


def executemany(sql, seq_of_params):
    with _lock:
        _conn.executemany(sql, seq_of_params)
        _conn.commit()


def log_activity(user_id, action, detail=""):
    execute(
        "INSERT INTO activity_log (user_id, action, detail, created_at) VALUES (?,?,?,?)",
        (user_id, action, detail, now()),
    )

# ======================================================================
# بخش برگرفته از: data.py
# ======================================================================
# -*- coding: utf-8 -*-
"""
داده‌های ثابت بازی: کشورها، کارخانه‌ها، تجهیزات نظامی، درخت فناوری، منابع و تنگه‌های استراتژیک.
این فایل صرفاً «داده»‌ست، نه منطق. برای اضافه‌کردن کشور یا تجهیزات جدید کافیه همینجا اضافه کنی
یا از پنل ادمین (که از همین لیست‌ها می‌خونه) استفاده کنی.
"""


def flag_from_iso2(iso2):
    """تبدیل کد دو حرفی کشور به ایموجی پرچم (Regional Indicator Symbols)."""
    if not iso2 or len(iso2) != 2:
        return "🏳️"
    base = 0x1F1E6
    return "".join(chr(base + (ord(ch.upper()) - ord("A"))) for ch in iso2)


# (نام کشور, iso2, جمعیت میلیون‌نفر, ضریب اقتصاد پایه, ضریب نظامی پایه)
_RAW_COUNTRIES = [
    ("ایران", "IR", 88, 55, 60), ("آمریکا", "US", 335, 100, 100), ("چین", "CN", 1420, 95, 95),
    ("روسیه", "RU", 144, 60, 90), ("آلمان", "DE", 84, 85, 55), ("فرانسه", "FR", 68, 80, 60),
    ("انگلستان", "GB", 68, 80, 62), ("ژاپن", "JP", 124, 82, 58), ("کره جنوبی", "KR", 52, 70, 55),
    ("کره شمالی", "KP", 26, 25, 50), ("هند", "IN", 1428, 65, 70), ("پاکستان", "PK", 240, 35, 45),
    ("ترکیه", "TR", 85, 55, 58), ("عربستان سعودی", "SA", 36, 65, 50), ("امارات", "AE", 10, 60, 35),
    ("اسرائیل", "IL", 9, 65, 55), ("مصر", "EG", 112, 40, 45), ("عراق", "IQ", 43, 30, 35),
    ("سوریه", "SY", 22, 15, 25), ("اردن", "JO", 11, 30, 25), ("قطر", "QA", 3, 55, 20),
    ("کویت", "KW", 4, 50, 18), ("یمن", "YE", 34, 12, 20), ("افغانستان", "AF", 42, 10, 22),
    ("پاناما", "PA", 4, 40, 10), ("مکزیک", "MX", 128, 50, 40), ("برزیل", "BR", 216, 55, 50),
    ("آرژانتین", "AR", 46, 40, 30), ("کانادا", "CA", 39, 75, 45), ("استرالیا", "AU", 26, 75, 48),
    ("اسپانیا", "ES", 47, 65, 42), ("ایتالیا", "IT", 59, 68, 46), ("لهستان", "PL", 38, 55, 40),
    ("اوکراین", "UA", 36, 30, 35), ("رومانی", "RO", 19, 40, 28), ("یونان", "GR", 10, 45, 30),
    ("پرتغال", "PT", 10, 45, 22), ("هلند", "NL", 18, 70, 32), ("بلژیک", "BE", 12, 65, 25),
    ("سوئد", "SE", 10, 70, 32), ("نروژ", "NO", 5, 72, 25), ("فنلاند", "FI", 6, 65, 28),
    ("سوئیس", "CH", 9, 78, 20), ("اتریش", "AT", 9, 65, 18), ("چک", "CZ", 11, 55, 22),
    ("مجارستان", "HU", 10, 48, 20), ("دانمارک", "DK", 6, 68, 20), ("ایرلند", "IE", 5, 60, 12),
    ("قزاقستان", "KZ", 20, 40, 25), ("ازبکستان", "UZ", 36, 25, 20), ("آذربایجان", "AZ", 10, 35, 22),
    ("ارمنستان", "AM", 3, 20, 15), ("گرجستان", "GE", 4, 25, 12), ("لبنان", "LB", 5, 15, 15),
    ("لیبی", "LY", 7, 20, 20), ("الجزایر", "DZ", 45, 40, 38), ("مراکش", "MA", 37, 35, 28),
    ("تونس", "TN", 12, 25, 15), ("سودان", "SD", 48, 15, 20), ("اتیوپی", "ET", 128, 20, 30),
    ("نیجریه", "NG", 223, 30, 32), ("کنیا", "KE", 55, 22, 18), ("آفریقای جنوبی", "ZA", 60, 45, 30),
    ("غنا", "GH", 34, 20, 12), ("ویتنام", "VN", 100, 35, 35), ("تایلند", "TH", 72, 40, 30),
    ("اندونزی", "ID", 278, 45, 40), ("مالزی", "MY", 34, 45, 25), ("فیلیپین", "PH", 117, 30, 25),
    ("سنگاپور", "SG", 6, 80, 18), ("تایوان", "TW", 24, 60, 42), ("نیوزیلند", "NZ", 5, 55, 15),
    ("کلمبیا", "CO", 52, 35, 28), ("شیلی", "CL", 20, 45, 22), ("پرو", "PE", 34, 30, 18),
    ("ونزوئلا", "VE", 28, 18, 25), ("کوبا", "CU", 11, 15, 20), ("اکوادور", "EC", 18, 25, 12),
    ("ایسلند", "IS", 0.4, 40, 5),
    # --- گسترش لیست کشورها ---
    ("بولیوی", "BO", 12, 22, 15), ("پاراگوئه", "PY", 7, 25, 12), ("اروگوئه", "UY", 3, 35, 15),
    ("گواتمالا", "GT", 18, 20, 12), ("هندوراس", "HN", 10, 15, 10), ("نیکاراگوئه", "NI", 7, 13, 9),
    ("کاستاریکا", "CR", 5, 32, 8), ("السالوادور", "SV", 6, 15, 8), ("جامائیکا", "JM", 3, 20, 6),
    ("هائیتی", "HT", 11, 8, 6), ("جمهوری دومینیکن", "DO", 11, 25, 12),
    ("بحرین", "BH", 2, 45, 15), ("عمان", "OM", 5, 38, 22), ("فلسطین", "PS", 5, 10, 10),
    ("قرقیزستان", "KG", 7, 15, 12), ("تاجیکستان", "TJ", 10, 12, 12), ("ترکمنستان", "TM", 6, 25, 15),
    ("مغولستان", "MN", 3, 20, 12), ("نپال", "NP", 30, 15, 12), ("بنگلادش", "BD", 173, 30, 28),
    ("سریلانکا", "LK", 22, 22, 15), ("میانمار", "MM", 54, 15, 22), ("کامبوج", "KH", 17, 20, 10),
    ("لائوس", "LA", 8, 12, 8), ("برونئی", "BN", 0.5, 45, 8), ("پاپوآ گینه نو", "PG", 10, 15, 6),
    ("فیجی", "FJ", 0.9, 22, 5),
    ("بلاروس", "BY", 9, 25, 25), ("مولداوی", "MD", 3, 18, 8), ("صربستان", "RS", 7, 32, 22),
    ("کرواسی", "HR", 4, 42, 18), ("بوسنی", "BA", 3, 22, 12), ("اسلوونی", "SI", 2, 50, 10),
    ("اسلواکی", "SK", 5, 42, 16), ("بلغارستان", "BG", 7, 32, 18), ("لیتوانی", "LT", 3, 42, 12),
    ("لتونی", "LV", 2, 40, 10), ("استونی", "EE", 1, 45, 10), ("لوکزامبورگ", "LU", 0.7, 70, 6),
    ("مالت", "MT", 0.5, 45, 4), ("قبرس", "CY", 1, 40, 10), ("مقدونیه شمالی", "MK", 2, 22, 8),
    ("مونته‌نگرو", "ME", 0.6, 25, 6), ("آلبانی", "AL", 3, 20, 10),
    ("تانزانیا", "TZ", 67, 20, 18), ("اوگاندا", "UG", 48, 15, 15), ("زامبیا", "ZM", 20, 18, 10),
    ("زیمبابوه", "ZW", 16, 12, 12), ("موزامبیک", "MZ", 33, 12, 10), ("آنگولا", "AO", 36, 25, 20),
    ("کامرون", "CM", 28, 18, 15), ("ساحل عاج", "CI", 29, 22, 12), ("سنگال", "SN", 18, 18, 10),
    ("مالی", "ML", 23, 10, 12), ("نیجر", "NE", 26, 8, 10), ("چاد", "TD", 18, 8, 10),
    ("سومالی", "SO", 18, 6, 10), ("اریتره", "ER", 4, 8, 12), ("جیبوتی", "DJ", 1, 15, 8),
    ("روآندا", "RW", 14, 18, 10), ("بوتسوانا", "BW", 2, 30, 8), ("نامیبیا", "NA", 3, 25, 8),
    ("گابن", "GA", 2, 28, 8), ("موریتانی", "MR", 5, 15, 8), ("بنین", "BJ", 13, 15, 8),
    ("توگو", "TG", 9, 13, 6), ("گینه", "GN", 14, 10, 8), ("مدغاسکار", "MG", 30, 10, 8),
    ("مالاوی", "MW", 20, 9, 6), ("لسوتو", "LS", 2, 12, 4), ("اسواتینی", "SZ", 1, 15, 4),
]

COUNTRIES = []
for _name, _iso2, _pop, _econ, _mil in _RAW_COUNTRIES:
    COUNTRIES.append({
        "name": _name,
        "iso2": _iso2,
        "flag": flag_from_iso2(_iso2),
        "population": _pop * 1_000_000,
        "base_economy": _econ,
        "base_military": _mil,
    })

# پرچم اختصاصی برای ایران (درخواست کاربر)
for _c in COUNTRIES:
    if _c["name"] == "ایران":
        _c["flag"] = "🟥🟥🟥🟥🟥🟥🟥\n⬜⬜🦁☀️⬜⬜⬜\n🟩🟩🟩🟩🟩🟩🟩"

# منابع پایه‌ی بازی
RESOURCES = ["oil", "gas", "iron", "coal", "uranium", "food", "steel", "copper"]
RESOURCE_FA = {
    "oil": "🛢️ نفت", "gas": "🔥 گاز", "iron": "⛏️ آهن", "coal": "⚫ زغال‌سنگ",
    "uranium": "☢️ اورانیوم", "food": "🌾 غذا", "steel": "🔩 فولاد", "copper": "🟤 مس",
}
RESOURCE_BASE_PRICE = {
    "oil": 60, "gas": 40, "iron": 25, "coal": 15,
    "uranium": 400, "food": 8, "steel": 35, "copper": 90,
}

# کارخانه‌ها: کلید -> (نام فارسی, هزینه‌ی ساخت پایه, هزینه‌ی نگهداری, ظرفیت تولید هر tick, منبع مصرفی)
FACTORY_TYPES = {
    "weapon": {"name": "🔫 کارخانه اسلحه", "cost": 8000, "upkeep": 150, "output": 8, "consumes": {"iron": 4, "coal": 2}},
    "tank": {"name": "🛡️ کارخانه تانک", "cost": 20000, "upkeep": 400, "output": 2, "consumes": {"steel": 10, "iron": 6}},
    "aircraft": {"name": "✈️ کارخانه هواپیما", "cost": 45000, "upkeep": 900, "output": 1, "consumes": {"steel": 20, "copper": 8}},
    "navy": {"name": "🚢 کارخانه کشتی", "cost": 60000, "upkeep": 1200, "output": 1, "consumes": {"steel": 30, "copper": 10}},
    "ammo": {"name": "💣 کارخانه مهمات", "cost": 6000, "upkeep": 120, "output": 15, "consumes": {"iron": 3, "coal": 1}},
    "missile": {"name": "🚀 کارخانه موشک", "cost": 70000, "upkeep": 1500, "output": 1, "consumes": {"steel": 15, "uranium": 2, "copper": 5}},
    "equipment": {"name": "🎒 کارخانه تجهیزات نظامی", "cost": 10000, "upkeep": 200, "output": 10, "consumes": {"iron": 2, "steel": 2}},
}
# ظرفیت هر سطح کارخانه ۱.۴ برابر می‌شه، هزینه‌ی ارتقا هم همینطور

# ۱۰ نوع نیروی زمینی
GROUND_UNITS = [
    ("soldier", "🪖 سرباز", 50, 1),
    ("infantry", "🎖️ پیاده‌نظام", 80, 2),
    ("special_forces", "🥷 نیروی ویژه", 500, 6),
    ("apc", "🚙 نفربر زرهی", 1200, 8),
    ("artillery", "💥 توپخانه", 2500, 12),
    ("mlrs", "🎯 راکت‌انداز چندگانه", 4000, 16),
    ("light_tank", "🛞 تانک سبک", 6000, 20),
    ("main_tank", "🛡️ تانک اصلی", 12000, 30),
    ("heavy_tank", "🏋️ تانک سنگین", 20000, 42),
    ("air_defense", "🎯 پدافند هوایی", 9000, 22),
]

# ۱۰ جنگنده/بمب‌افکن نمایندگی از ۳۰ مدل درخواستی (قابل گسترش)
AIR_UNITS = [
    ("f16", "✈️ اف-۱۶", 15000, 25), ("f22", "✈️ اف-۲۲ رپتور", 60000, 55),
    ("f35", "✈️ اف-۳۵", 55000, 52), ("su35", "✈️ سوخو-۳۵", 45000, 48),
    ("su57", "✈️ سوخو-۵۷", 65000, 58), ("mig29", "✈️ میگ-۲۹", 20000, 28),
    ("j20", "✈️ جی-۲۰", 58000, 50), ("eurofighter", "✈️ یوروفایتر تایفون", 42000, 44),
    ("b2", "💣 بی-۲ اسپیریت", 120000, 80), ("apache", "🚁 هلیکوپتر آپاچی", 18000, 26),
]

# ۱۰ ناو/زیردریایی نمایندگی از ۳۰ مدل درخواستی
NAVY_UNITS = [
    ("frigate", "🚢 ناوچه", 25000, 22), ("destroyer", "🚢 ناوشکن", 55000, 40),
    ("cruiser", "🚢 رزم‌ناو", 90000, 55), ("submarine", "🌊 زیردریایی", 70000, 50),
    ("nuclear_sub", "☢️ زیردریایی اتمی", 200000, 85), ("carrier", "🛳️ ناو هواپیمابر", 500000, 120),
    ("corvette", "🚤 کوروت", 15000, 15), ("patrol_boat", "🚤 قایق گشت", 4000, 6),
    ("landing_ship", "⚓ ناو پشتیبانی", 30000, 20), ("minesweeper", "⚓ ناو مین‌روب", 12000, 10),
]

# ۱۰ موشک نمایندگی از ۳۰ مدل درخواستی
MISSILE_UNITS = [
    ("short_range", "🚀 موشک برد کوتاه", 8000, 30), ("medium_range", "🚀 موشک برد میان‌برد", 25000, 55),
    ("long_range", "🚀 موشک برد بلند", 60000, 90), ("cruise_missile", "🚀 موشک کروز", 35000, 65),
    ("ballistic", "🚀 موشک بالستیک", 80000, 110), ("hypersonic", "🚀 موشک ابرصوت", 150000, 150),
    ("anti_ship", "🚀 موشک ضدکشتی", 20000, 40), ("air_defense_missile", "🎯 موشک پدافند", 15000, 25),
    ("icbm", "☢️ موشک قاره‌پیما", 400000, 260), ("tactical_nuke", "☢️ کلاهک تاکتیکی", 1000000, 500),
]

ALL_UNITS = {}
for key, name, cost, power in GROUND_UNITS + AIR_UNITS + NAVY_UNITS + MISSILE_UNITS:
    ALL_UNITS[key] = {"name": name, "cost": cost, "power": power}

UNIT_CATEGORIES = {
    "ground": [u[0] for u in GROUND_UNITS],
    "air": [u[0] for u in AIR_UNITS],
    "navy": [u[0] for u in NAVY_UNITS],
    "missile": [u[0] for u in MISSILE_UNITS],
}

# درخت فناوری
TECH_TREE = {
    "military_tech": {"name": "🪖 فناوری نظامی", "max_level": 10, "base_cost": 15000, "effect": "military_power"},
    "economic_tech": {"name": "💰 فناوری اقتصادی", "max_level": 10, "base_cost": 12000, "effect": "economy_score"},
    "naval_tech": {"name": "🚢 فناوری دریایی", "max_level": 10, "base_cost": 15000, "effect": "navy_power"},
    "air_tech": {"name": "✈️ فناوری هوایی", "max_level": 10, "base_cost": 15000, "effect": "air_power"},
    "missile_tech": {"name": "🚀 فناوری موشکی", "max_level": 10, "base_cost": 20000, "effect": "missile_power"},
    "industrial_tech": {"name": "🏭 فناوری صنعتی", "max_level": 10, "base_cost": 10000, "effect": "factory_output"},
    "it_tech": {"name": "🖥️ فناوری اطلاعات", "max_level": 10, "base_cost": 10000, "effect": "espionage_power"},
}

# تنگه‌ها و نقاط استراتژیک؛ این‌ها به‌صورت territory با is_strait=1 ساخته می‌شن
STRAITS = [
    {"name": "تنگه هرمز", "strategic_value": 10, "strait_bonus": 0.25},
    {"name": "کانال سوئز", "strategic_value": 10, "strait_bonus": 0.25},
    {"name": "تنگه جبل‌الطارق", "strategic_value": 8, "strait_bonus": 0.20},
    {"name": "تنگه بسفر", "strategic_value": 8, "strait_bonus": 0.20},
    {"name": "تنگه داردانل", "strategic_value": 7, "strait_bonus": 0.18},
    {"name": "کانال پاناما", "strategic_value": 9, "strait_bonus": 0.22},
    {"name": "تنگه باب‌المندب", "strategic_value": 8, "strait_bonus": 0.20},
]

RANDOM_EVENTS = [
    {"name": "📉 بحران اقتصادی جهانی", "effect": "economy", "delta": -0.12},
    {"name": "🛢️ افزایش قیمت نفت", "effect": "oil_price", "delta": 0.30},
    {"name": "🌍 رکود جهانی", "effect": "economy", "delta": -0.08},
    {"name": "⛏️ کشف منابع جدید", "effect": "resource_find", "delta": 0.20},
    {"name": "🔥 انقلاب داخلی", "effect": "satisfaction", "delta": -0.25},
    {"name": "✊ شورش مردمی", "effect": "morale", "delta": -0.15},
    {"name": "📈 رشد اقتصادی جهانی", "effect": "economy", "delta": 0.10},
    {"name": "⚡ بحران سیاسی", "effect": "satisfaction", "delta": -0.10},
    {"name": "🔬 کشف فناوری جدید", "effect": "tech", "delta": 0.15},
    {"name": "🌪️ بلایای طبیعی", "effect": "treasury", "delta": -0.10},
]

# پک‌های خریدنی با پول واقعی (از طریق درخواست پول تلگرام). قیمت‌ها در بخش تنظیمات (PACK_PRICE_TOMAN) هست.
# امتیازهای شروع کشورهای VIP (فقط یک‌بار، در لحظه‌ی خرید/دریافت اعمال می‌شه)
VIP_STARTING_BONUS = {
    "چین": {"treasury_bonus": 300000},  # 🏦 اقتصاد برتر
    "روسیه": {"units": {"tactical_nuke": 1}},  # ☢️ ابرقدرت اتمی
    "آمریکا": {"units": {"f16": 4, "f22": 2, "apache": 3}},  # ✈️ ابرقدرت هوایی
}

PACKS = {
    "ground_pack": {
        "name": "🪖 پک زمینی", "desc": "تقویت سریع نیروی زمینی",
        "units": {"soldier": 100, "infantry": 40, "main_tank": 8, "artillery": 5},
    },
    "air_pack": {
        "name": "✈️ پک هوایی", "desc": "چند فروند جنگنده و بالگرد آماده",
        "units": {"f16": 4, "apache": 3},
    },
    "navy_pack": {
        "name": "🚢 پک دریایی", "desc": "تقویت ناوگان دریایی",
        "units": {"frigate": 3, "corvette": 4, "submarine": 1},
    },
    "missile_pack": {
        "name": "🚀 پک موشکی", "desc": "چند موشک برد کوتاه و میان‌برد",
        "units": {"short_range": 6, "medium_range": 3},
    },
    "economy_pack": {
        "name": "💰 پک اقتصادی", "desc": "تزریق مستقیم پول نقد به خزانه‌ی کشورت",
        "cash": 60000,
    },
}


def get_country_by_id(cid):
    if 1 <= cid <= len(COUNTRIES):
        return COUNTRIES[cid - 1]
    return None

# ======================================================================
# بخش برگرفته از: bale_api.py
# ======================================================================
# -*- coding: utf-8 -*-
"""
لایه‌ی ارتباط با API تلگرام.
این لایه از همون سبک API استاندارد ربات‌ها استفاده می‌کنه (getUpdates / sendMessage / ...).
"""
import time
import requests



def _url(method):
    return TELEGRAM_API_BASE.format(token=BOT_TOKEN, method=method)


def delete_webhook():
    """برای استفاده از long polling، وبهوک احتمالی قبلی را حذف می‌کند."""
    return _post("deleteWebhook", {"drop_pending_updates": False})


def get_me():
    return _post("getMe", {})


def _post(method, payload, retries=3):
    for attempt in range(retries):
        try:
            r = requests.post(_url(method), json=payload, timeout=POLL_TIMEOUT + 10)
            resp = r.json()
            if not resp.get("ok", False):
                print(f"[telegram_api] خطا در {method}: {resp}")
            return resp
        except Exception as e:
            print(f"[telegram_api] خطای شبکه در {method} (تلاش {attempt+1}): {e}")
            time.sleep(2)
    return {"ok": False, "result": None}


def get_updates(offset=None):
    payload = {"timeout": POLL_TIMEOUT}
    if offset is not None:
        payload["offset"] = offset
    resp = _post("getUpdates", payload)
    return resp.get("result", []) or []


def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _post("sendMessage", payload)


def edit_message_text(chat_id, message_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return _post("editMessageText", payload)


def answer_callback_query(callback_query_id, text=None, show_alert=False):
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = show_alert
    return _post("answerCallbackQuery", payload)


def send_to_channel(channel, text):
    if not channel:
        return None
    return send_message(channel, text)


def send_photo(chat_id, photo, caption=None, reply_markup=None):
    """
    ارسال عکس. photo می‌تونه یک URL باشه یا یک file_id که قبلاً از یک عکس دریافتی گرفتیم.
    """
    body = {"chat_id": chat_id, "photo": photo}
    if caption:
        body["caption"] = caption[:1024]
    if reply_markup is not None:
        body["reply_markup"] = reply_markup
    return _post("sendPhoto", body)


def send_invoice(chat_id, title, description, payload, amount_rial, reply_markup=None):
    """
    ارسال درخواست پرداخت (فاکتور) تلگرام.
    amount_rial: مبلغ کل به ریال (تلگرام واحد قیمت بر اساس ارز تنظیم‌شده در فاکتور است).
    provider_token در تلگرام باید توکن درگاه پرداخت باشد (TELEGRAM_PROVIDER_TOKEN در بخش تنظیمات).
    """
    body = {
        "chat_id": chat_id,
        "title": title[:32],
        "description": description[:255],
        "payload": payload[:128],
        "provider_token": TELEGRAM_PROVIDER_TOKEN,
        "currency": TELEGRAM_CURRENCY,
        "prices": [{"label": title[:32], "amount": int(amount_rial)}],
    }
    if reply_markup is not None:
        body["reply_markup"] = reply_markup
    return _post("sendInvoice", body)


def answer_pre_checkout_query(pre_checkout_query_id, ok=True, error_message=None):
    payload = {"pre_checkout_query_id": pre_checkout_query_id, "ok": ok}
    if error_message:
        payload["error_message"] = error_message
    return _post("answerPreCheckoutQuery", payload)

# ======================================================================
# بخش برگرفته از: keyboards.py
# ======================================================================
# -*- coding: utf-8 -*-
"""سازنده‌های دکمه‌های Inline."""


def kb(rows):
    """rows: لیستی از ردیف‌ها؛ هر ردیف لیستی از (متن, callback_data)."""
    return {
        "inline_keyboard": [
            [{"text": text, "callback_data": cb} for text, cb in row]
            for row in rows
        ]
    }


def main_menu_kb():
    return kb([
        [("🏠 اطلاعات کشور", "menu:info"), ("💰 خزانه و اقتصاد", "menu:economy")],
        [("🏭 کارخانه‌ها", "menu:factory"), ("⛏️ منابع", "menu:resources")],
        [("🪖 ارتش", "menu:army"), ("🛡️ دفاع", "menu:defense")],
        [("🔬 فناوری", "menu:tech"), ("🕵️ جاسوسی", "menu:spy")],
        [("🤝 دیپلماسی", "menu:diplomacy"), ("⚔️ جنگ", "menu:war")],
        [("🗺️ سرزمین‌ها", "menu:territory"), ("🚢 تجارت", "menu:trade")],
        [("📢 اخبار جهانی", "menu:news"), ("🏆 رتبه‌بندی", "menu:ranking")],
        [("📊 گزارش کشور", "menu:report"), ("⚙️ تنظیمات", "menu:settings")],
        [("🛒 فروشگاه ویژه", "menu:shop")],
        [("🏛️ سازمان ملل", "menu:un"), ("🏰 اتحادها", "menu:alliance")],
    ])


def back_kb(target="menu:main"):
    return kb([[("🔙 بازگشت", target)]])


def confirm_kb(yes_cb, no_cb="menu:main"):
    return kb([[("✅ تایید", yes_cb), ("❌ انصراف", no_cb)]])

# ======================================================================
# بخش برگرفته از: game.py
# ======================================================================
# -*- coding: utf-8 -*-
"""
منطق اصلی بازی: محاسبه‌ی درآمد، تولید کارخانه‌ها، قدرت نظامی، نتیجه‌ی جنگ و ...
"""
import random
import time



def now():
    return int(time.time())


# ---------------------------------------------------------------- کشور/کاربر

def get_user(user_id):
    return query_one("SELECT * FROM users WHERE user_id=?", (user_id,))


def ensure_user(user_id, username):
    u = get_user(user_id)
    if not u:
        execute(
            "INSERT INTO users (user_id, username, country_id, joined_at) VALUES (?,?,?,?)",
            (user_id, username or "", None, now()),
        )
        u = get_user(user_id)
    return u


def get_country(cid):
    return query_one("SELECT * FROM countries WHERE id=?", (cid,))


def get_country_by_owner(owner_id):
    return query_one("SELECT * FROM countries WHERE owner_id=?", (owner_id,))


def list_free_countries():
    return query(
        "SELECT * FROM countries WHERE owner_id IS NULL AND active=1 "
        "AND (is_special IS NULL OR is_special=0) ORDER BY id"
    )


def list_taken_countries():
    return query(
        "SELECT * FROM countries WHERE owner_id IS NOT NULL "
        "AND (is_special IS NULL OR is_special=0) ORDER BY id"
    )


def seed_countries_if_needed():
    """کشورهای پایه رو فقط اگه دیتابیس خالیه اضافه می‌کنه (بدون پاک‌کردن چیزی)."""
    existing = query_one("SELECT COUNT(*) c FROM countries")
    if existing and existing["c"] > 0:
        return
    for i, c in enumerate(COUNTRIES, start=1):
        execute(
            """INSERT INTO countries
               (id, name, flag, iso2, owner_id, population, treasury, economy_score, hp, max_hp)
               VALUES (?,?,?,?,NULL,?,?,?,?,?)""",
            (i, c["name"], c["flag"], c["iso2"], c["population"],
             30000 + c["base_economy"] * 300, c["base_economy"], 1000, 1000),
        )
        for r in RESOURCES:
            execute(
                "INSERT OR IGNORE INTO resources (country_id, resource, amount) VALUES (?,?,?)",
                (i, r, random.randint(200, 1500)),
            )
    # تنگه‌ها به‌صورت سرزمین‌های بدون مالک اضافه می‌شن
    for s in STRAITS:
        exists = query_one("SELECT id FROM territories WHERE name=?", (s["name"],))
        if not exists:
            execute(
                """INSERT INTO territories
                   (name, owner_id, original_owner_id, population, economic_value,
                    strategic_value, is_strait, strait_bonus)
                   VALUES (?,NULL,NULL,0,?,?,1,?)""",
                (s["name"], s["strategic_value"] * 5000, s["strategic_value"], s["strait_bonus"]),
            )
    for r in RESOURCES:
        exists = query_one("SELECT resource FROM market WHERE resource=?", (r,))
        if not exists:
            execute(
                "INSERT INTO market (resource, price, supply, demand) VALUES (?,?,?,?)",
                (r, RESOURCE_BASE_PRICE[r], 1000, 1000),
            )


def sync_country_flags():
    """
    اگه پرچم یه کشور تو بخش داده‌ها عوض بشه (مثلاً یه پرچم اختصاصی)، این تابع هر بار
    در استارت، دیتابیس‌های قدیمی رو هم با آخرین نسخه هماهنگ می‌کنه.
    """
    for c in COUNTRIES:
        execute("UPDATE countries SET flag=? WHERE name=? AND flag != ?", (c["flag"], c["name"], c["flag"]))


def ensure_special_and_vip_countries():
    """
    این تابع هر بار در استارت اجرا می‌شه (چه دیتابیس تازه باشه چه قدیمی):
    ۱) کشورهای VIP (روسیه/آمریکا/چین) رو علامت‌گذاری می‌کنه.
    ۲) کشورهای ویژه‌ی بدون‌نقش (مالک/ادمین/ادمین۲) رو اگه نبودن می‌سازه.
    هیچ داده‌ی موجودی رو پاک یا بازنویسی نمی‌کنه.
    """
    for name in VIP_COUNTRY_NAMES:
        execute("UPDATE countries SET is_vip=1 WHERE name=? AND (is_special IS NULL OR is_special=0)", (name,))

    for name in SPECIAL_COUNTRY_NAMES:
        exists = query_one("SELECT id FROM countries WHERE name=?", (name,))
        if not exists:
            execute(
                """INSERT INTO countries
                   (name, flag, iso2, owner_id, population, treasury, economy_score,
                    hp, max_hp, active, is_special, is_vip)
                   VALUES (?,?,?,NULL,0,0,0,0,0,1,1,0)""",
                (name, "🎖️", ""),
            )


def assign_country(user_id, country_id):
    c = get_country(country_id)
    if not c or c["owner_id"] is not None:
        return False, "این کشور دیگه در دسترس نیست."
    existing = get_country_by_owner(user_id)
    if existing and existing["id"] != country_id:
        return False, f"تو همین الان کشور {existing['flag']} {existing['name']} رو داری. هر بازیکن فقط می‌تونه یک کشور داشته باشه."
    execute("UPDATE countries SET owner_id=? WHERE id=?", (user_id, country_id))
    execute("UPDATE users SET country_id=? WHERE user_id=?", (country_id, user_id))
    log_activity(user_id, "select_country", c["name"])
    create_provinces_for_country(country_id)
    return True, c


# ------------------------------------------------------------------- منابع

def get_resources(country_id):
    rows = query("SELECT resource, amount FROM resources WHERE country_id=?", (country_id,))
    d = {r: 0 for r in RESOURCES}
    for row in rows:
        d[row["resource"]] = row["amount"]
    return d


def add_resource(country_id, resource, delta):
    execute(
        "INSERT INTO resources (country_id, resource, amount) VALUES (?,?,?) "
        "ON CONFLICT(country_id, resource) DO UPDATE SET amount = amount + ?",
        (country_id, resource, max(delta, 0), delta),
    )


# ----------------------------------------------------------------- کارخانه‌ها

def list_factories(country_id):
    return query("SELECT * FROM factories WHERE country_id=?", (country_id,))


def factory_build_cost(ftype, current_count):
    base = FACTORY_TYPES[ftype]["cost"]
    return int(base * (1.15 ** current_count))


def build_factory(country_id, ftype):
    c = get_country(country_id)
    current = query_one(
        "SELECT COUNT(*) n FROM factories WHERE country_id=? AND ftype=?", (country_id, ftype)
    )["n"]
    cost = factory_build_cost(ftype, current)
    if c["treasury"] < cost:
        return False, f"خزانه کافی نیست. هزینه: {cost:,} 💰"
    execute("UPDATE countries SET treasury = treasury - ? WHERE id=?", (cost, country_id))
    execute(
        "INSERT INTO factories (country_id, ftype, level, built_at, last_production) VALUES (?,?,1,?,?)",
        (country_id, ftype, now(), now()),
    )
    log_activity(c["owner_id"], "build_factory", ftype)
    return True, cost


def upgrade_factory(factory_id):
    f = query_one("SELECT * FROM factories WHERE id=?", (factory_id,))
    if not f:
        return False, "کارخانه پیدا نشد."
    c = get_country(f["country_id"])
    cost = int(FACTORY_TYPES[f["ftype"]]["cost"] * 0.6 * f["level"])
    if c["treasury"] < cost:
        return False, f"خزانه کافی نیست. هزینه ارتقا: {cost:,} 💰"
    execute("UPDATE countries SET treasury = treasury - ? WHERE id=?", (cost, f["country_id"]))
    execute("UPDATE factories SET level = level + 1 WHERE id=?", (factory_id,))
    return True, cost


# --------------------------------------------------------------------- ارتش

def get_army(country_id):
    rows = query("SELECT unit_key, quantity FROM army WHERE country_id=?", (country_id,))
    d = {row["unit_key"]: row["quantity"] for row in rows}
    return d


def buy_unit(country_id, unit_key, qty):
    if unit_key not in ALL_UNITS or qty <= 0:
        return False, "واحد نامعتبر."
    c = get_country(country_id)
    unit = ALL_UNITS[unit_key]
    total_cost = unit["cost"] * qty
    if c["treasury"] < total_cost:
        return False, f"خزانه کافی نیست. هزینه کل: {total_cost:,} 💰"
    execute("UPDATE countries SET treasury = treasury - ? WHERE id=?", (total_cost, country_id))
    execute(
        "INSERT INTO army (country_id, unit_key, quantity) VALUES (?,?,?) "
        "ON CONFLICT(country_id, unit_key) DO UPDATE SET quantity = quantity + ?",
        (country_id, unit_key, qty, qty),
    )
    log_activity(c["owner_id"], "buy_unit", f"{unit_key} x{qty}")
    return True, total_cost


def military_power(country_id):
    army = get_army(country_id)
    power = 0
    for key, qty in army.items():
        power += ALL_UNITS[key]["power"] * qty
    tech = query_one(
        "SELECT level FROM tech WHERE country_id=? AND tech_key='military_tech'", (country_id,)
    )
    tech_level = tech["level"] if tech else 0
    power *= (1 + tech_level * 0.05)
    return power


# ---------------------------------------------------------------- اقتصاد/تیک

def economic_tick():
    """محاسبه‌ی درآمد، هزینه‌ی نگهداری ارتش، تولید کارخانه و تحقیقات برای همه‌ی کشورهای دارای بازیکن (به‌جز کشورهای ویژه‌ی بدون‌نقش)."""
    countries = query(
        "SELECT * FROM countries WHERE owner_id IS NOT NULL AND active=1 "
        "AND (is_special IS NULL OR is_special=0)"
    )
    for c in countries:
        cid = c["id"]
        # درآمد مالیاتی بر اساس جمعیت و اقتصاد
        tax_income = (c["population"] / 1_000_000) * c["tax_rate"] * (c["economy_score"] / 10)
        # هزینه نگهداری ارتش
        army = get_army(cid)
        upkeep = sum(ALL_UNITS[k]["cost"] * 0.002 * q for k, q in army.items())
        # هزینه نگهداری کارخانه‌ها
        factories = list_factories(cid)
        factory_upkeep = sum(FACTORY_TYPES[f["ftype"]]["upkeep"] * f["level"] for f in factories)
        # تجارت تنگه‌ها
        strait_income = 0
        straits = query("SELECT * FROM territories WHERE owner_id=? AND is_strait=1", (cid,))
        for s in straits:
            strait_income += s["economic_value"] * 0.01

        net = tax_income - upkeep - factory_upkeep + strait_income
        new_treasury = c["treasury"] + net
        new_debt = c["debt"]
        if new_treasury < 0:
            new_debt += abs(new_treasury)
            new_treasury = 0

        execute(
            "UPDATE countries SET treasury=?, debt=? WHERE id=?",
            (new_treasury, new_debt, cid),
        )

        # تولید کارخانه‌ها (به شکل منابع ذخیره‌شده به‌عنوان تجهیزات آماده نمی‌شه؛
        # اینجا خروجی کارخانه به‌صورت سکه‌ی اضافه به خزانه منظور می‌شه چون تجهیزات با buy_unit خریداری می‌شن)
        for f in factories:
            ftype_data = FACTORY_TYPES[f["ftype"]]
            can_produce = True
            for res, need in ftype_data["consumes"].items():
                stock = query_one(
                    "SELECT amount FROM resources WHERE country_id=? AND resource=?", (cid, res)
                )
                if not stock or stock["amount"] < need * f["level"]:
                    can_produce = False
                    break
            if can_produce:
                for res, need in ftype_data["consumes"].items():
                    add_resource(cid, res, -need * f["level"])
                execute("UPDATE factories SET last_production=? WHERE id=?", (now(), f["id"]))

        # رشد جزئی جمعیت و رضایت بر اساس اقتصاد
        satisfaction_delta = 0.3 if net > 0 else -0.5
        execute(
            "UPDATE countries SET satisfaction = MAX(0, MIN(100, satisfaction + ?)) WHERE id=?",
            (satisfaction_delta, cid),
        )


def maybe_trigger_random_event():
    ev = random.choice(RANDOM_EVENTS)
    execute(
        "INSERT INTO events_log (name, description, created_at) VALUES (?,?,?)",
        (ev["name"], ev["effect"], now()),
    )
    countries = query(
        "SELECT * FROM countries WHERE owner_id IS NOT NULL AND (is_special IS NULL OR is_special=0)"
    )
    for c in countries:
        if ev["effect"] == "economy":
            execute("UPDATE countries SET economy_score = MAX(1, economy_score * ?) WHERE id=?",
                       (1 + ev["delta"], c["id"]))
        elif ev["effect"] == "satisfaction":
            execute("UPDATE countries SET satisfaction = MAX(0, MIN(100, satisfaction + ?)) WHERE id=?",
                       (ev["delta"] * 100, c["id"]))
        elif ev["effect"] == "morale":
            execute("UPDATE countries SET morale = MAX(0, MIN(100, morale + ?)) WHERE id=?",
                       (ev["delta"] * 100, c["id"]))
        elif ev["effect"] == "treasury":
            execute("UPDATE countries SET treasury = MAX(0, treasury * ?) WHERE id=?",
                       (1 + ev["delta"], c["id"]))
        elif ev["effect"] == "tech":
            pass  # می‌تونه بعدا به تحقیقات رایگان تبدیل بشه
    add_news(f"🎲 رویداد جهانی: {ev['name']}")
    return ev


# ---------------------------------------------------------------------- اخبار

EVENT_IMAGE_CATEGORIES = {
    "destruction": "☠️ نابودی کشور",
    "ownership_change": "🆕 تغییر مالکیت / انتخاب کشور",
    "war_win": "🏆 پیروزی در جنگ",
}


def get_event_image(category):
    row = query_one("SELECT photo FROM event_images WHERE category=?", (category,))
    return row["photo"] if row else None


def set_event_image(category, photo):
    execute(
        "INSERT INTO event_images (category, photo, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(category) DO UPDATE SET photo=?, updated_at=?",
        (category, photo, now(), photo, now()),
    )


def add_news(text, category="general"):
    execute(
        "INSERT INTO news (text, category, created_at) VALUES (?,?,?)",
        (text, category, now()),
    )
    if NEWS_CHANNEL:
        try:
            img = get_event_image(category) if category in EVENT_IMAGE_CATEGORIES else None
            if img:
                send_photo(NEWS_CHANNEL, img, caption=f"📢 {text}")
            else:
                send_to_channel(NEWS_CHANNEL, f"📢 {text}")
        except Exception as e:
            print(f"[add_news] خطا در ارسال خبر به کانال: {e}")


def latest_news(limit=10):
    return query("SELECT * FROM news ORDER BY id DESC LIMIT ?", (limit,))


# ------------------------------------------------------------------------ جنگ

def compute_war_power(country_id):
    c = get_country(country_id)
    mil = military_power(country_id)
    tech = query("SELECT tech_key, level FROM tech WHERE country_id=?", (country_id,))
    tech_bonus = 1 + 0.03 * sum(t["level"] for t in tech)
    economy_factor = 1 + (c["economy_score"] / 200)
    morale_factor = 0.5 + (c["morale"] / 100)
    allies = query(
        "SELECT * FROM relations WHERE (country_a=? OR country_b=?) AND status='alliance'",
        (country_id, country_id),
    )
    ally_bonus = 1 + 0.05 * len(allies)
    total = mil * tech_bonus * economy_factor * morale_factor * ally_bonus
    return total


def declare_war(attacker_id, defender_id):
    existing = query_one(
        "SELECT * FROM wars WHERE status='active' AND "
        "((attacker_id=? AND defender_id=?) OR (attacker_id=? AND defender_id=?))",
        (attacker_id, defender_id, defender_id, attacker_id),
    )
    if existing:
        return False, "همین الان جنگ فعالی بین این دو کشور وجود داره."
    war_id = execute(
        "INSERT INTO wars (attacker_id, defender_id, status, started_at) VALUES (?,?,'active',?)",
        (attacker_id, defender_id, now()),
    )
    execute(
        "INSERT INTO relations (country_a, country_b, status, updated_at) VALUES (?,?, 'war', ?) "
        "ON CONFLICT(country_a, country_b) DO UPDATE SET status='war', updated_at=?",
        (min(attacker_id, defender_id), max(attacker_id, defender_id), now(), now()),
    )
    atk = get_country(attacker_id)
    dfn = get_country(defender_id)
    add_news(f"⚔️ {atk['flag']} {atk['name']} به {dfn['flag']} {dfn['name']} اعلان جنگ کرد.")
    return True, war_id


def resolve_battle(war_id):
    """
    یک راند نبرد رو حل می‌کنه. آسیب هر دور مستقیماً متناسب با نسبت قدرت دو طرفه:
    هرچی یک طرف نسبت به طرف مقابل برتری بیشتری داشته باشه، آسیب بیشتری در همون
    دور می‌زنه (فتح خیلی سریع‌تر). اگه مدافع عملاً هیچ قدرتی نداشته باشه، تقریباً
    در همون دور اول فتح می‌شه.
    """
    war = query_one("SELECT * FROM wars WHERE id=?", (war_id,))
    if not war or war["status"] != "active":
        return None

    attacker = get_country(war["attacker_id"])
    defender = get_country(war["defender_id"])

    atk_power = compute_war_power(war["attacker_id"])
    def_power = compute_war_power(war["defender_id"]) * 1.15  # مزیت دفاعی

    atk_power_safe = max(atk_power, 0.01)
    def_power_safe = max(def_power, 0.01)
    ratio = atk_power_safe / def_power_safe  # هرچی بزرگ‌تر از ۱، مهاجم برتره؛ کوچیک‌تر از ۱ یعنی مدافع برتره

    BASE_DMG = 30
    dmg_to_defender = BASE_DMG * ratio
    dmg_to_attacker = BASE_DMG / ratio

    # کمی نوسان شانسی؛ فقط سهم رو کمی جابه‌جا می‌کنه، نتیجه رو کاملاً معکوس نمی‌کنه
    luck = random.uniform(-0.15, 0.15)
    dmg_to_defender *= (1 + luck)
    dmg_to_attacker *= max(0.0, 1 - luck)

    # سقف: حداکثر آسیب هر دور ۲ برابر maxHP، تا وقتی برتری خیلی زیاده فتح در همون دور اتفاق بیفته
    dmg_to_defender = min(dmg_to_defender, defender["max_hp"] * 2)
    dmg_to_attacker = min(dmg_to_attacker, attacker["max_hp"] * 2)

    new_defender_hp = max(0, defender["hp"] - dmg_to_defender)
    new_attacker_hp = max(0, attacker["hp"] - dmg_to_attacker)

    execute("UPDATE countries SET hp=? WHERE id=?", (new_defender_hp, war["defender_id"]))
    execute("UPDATE countries SET hp=? WHERE id=?", (new_attacker_hp, war["attacker_id"]))
    execute("UPDATE wars SET atk_casualties = atk_casualties + ?, def_casualties = def_casualties + ? WHERE id=?",
               (dmg_to_attacker, dmg_to_defender, war_id))

    winner = None
    if new_defender_hp <= 0:
        winner = "attacker"
    if new_attacker_hp <= 0:
        winner = "defender" if winner != "attacker" else "draw"

    result = {"ratio": ratio, "dmg_to_defender": dmg_to_defender,
              "dmg_to_attacker": dmg_to_attacker, "winner": winner}

    if winner:
        end_war(war_id, winner)
        result["ended"] = True
    else:
        result["ended"] = False
    return result


def end_war(war_id, winner):
    war = query_one("SELECT * FROM wars WHERE id=?", (war_id,))
    atk = get_country(war["attacker_id"])
    dfn = get_country(war["defender_id"])
    execute("UPDATE wars SET status='ended', ended_at=?, result=? WHERE id=?", (now(), winner, war_id))
    execute(
        "UPDATE relations SET status='neutral', updated_at=? WHERE country_a=? AND country_b=?",
        (now(), min(war["attacker_id"], war["defender_id"]), max(war["attacker_id"], war["defender_id"])),
    )

    if winner == "attacker":
        # مهاجم برنده شده: کشور مدافع کاملاً نابود می‌شه، همه‌ی سرزمین‌هاش تصرف می‌شه،
        # و خودش به یک کشور آزاد و بدون مالک تبدیل می‌شه (قابل انتخاب دوباره برای هرکسی، حتی همون بازیکن).
        execute(
            "UPDATE countries SET wins = wins + 1, conquests = conquests + 1, hp = max_hp * 0.5 WHERE id=?",
            (war["attacker_id"],),
        )
        captured_count = transfer_all_territories(war["defender_id"], war["attacker_id"])
        add_news(
            f"🏆 {atk['flag']} {atk['name']} کشور {dfn['flag']} {dfn['name']} را در جنگ کاملاً نابود و اشغال کرد "
            f"و {captured_count} منطقه را تصرف کرد.",
            category="war_win",
        )
        destroy_and_liberate_country(war["defender_id"])
        add_news(f"☠️ {dfn['flag']} {dfn['name']} به کشوری آزاد و بدون مالک تبدیل شد و دوباره قابل انتخابه.",
                 category="destruction")
    elif winner == "defender":
        execute("UPDATE countries SET wins = wins + 1, hp = max_hp * 0.5 WHERE id=?", (war["defender_id"],))
        execute("UPDATE countries SET losses = losses + 1, hp = max_hp * 0.5 WHERE id=?", (war["attacker_id"],))
        add_news(f"🛡️ {dfn['flag']} {dfn['name']} در برابر حمله‌ی {atk['flag']} {atk['name']} مقاومت کرد و پیروز شد.")
    else:
        execute("UPDATE countries SET hp = max_hp * 0.5 WHERE id IN (?,?)",
               (war["attacker_id"], war["defender_id"]))
        add_news(f"⚖️ جنگ میان {atk['flag']} {atk['name']} و {dfn['flag']} {dfn['name']} بدون برنده پایان یافت.")


def destroy_and_liberate_country(country_id):
    """
    وقتی کشوری در جنگ کاملاً نابود می‌شه: مالکش (اگه داشته) آزاد می‌شه تا بتونه
    دوباره از /start یک کشور انتخاب کنه، و خود کشور به حالت اولیه برمی‌گرده تا
    هر بازیکنی بتونه دوباره انتخابش کنه.
    """
    c = get_country(country_id)
    if not c:
        return
    old_owner = c["owner_id"]
    if old_owner:
        execute("UPDATE users SET country_id=NULL WHERE user_id=?", (old_owner,))
    execute(
        "UPDATE countries SET owner_id=NULL, treasury=50000, debt=0, hp=max_hp, wins=0, losses=0, "
        "conquests=0, satisfaction=60, morale=70, tax_rate=0.20, military_budget_pct=30, "
        "research_budget_pct=15 WHERE id=?",
        (country_id,),
    )
    execute("DELETE FROM army WHERE country_id=?", (country_id,))
    execute("DELETE FROM factories WHERE country_id=?", (country_id,))
    execute("DELETE FROM tech WHERE country_id=?", (country_id,))
    execute("DELETE FROM research_queue WHERE country_id=?", (country_id,))
    for r in RESOURCES:
        execute(
            "INSERT INTO resources (country_id, resource, amount) VALUES (?,?,?) "
            "ON CONFLICT(country_id, resource) DO UPDATE SET amount=?",
            (country_id, r, 200, 200),
        )


def country_name_taken(name):
    row = query_one("SELECT id FROM countries WHERE name=? AND active=1", (name,))
    return row is not None


def create_and_assign_custom_country(name, user_id):
    """
    ساخت یک کشور اختصاصی با نام دلخواه کاربر و اعطای رایگان و فوری‌اش به همون کاربر.
    """
    existing = get_country_by_owner(user_id)
    if existing:
        return False, f"تو همین الان کشور {existing['flag']} {existing['name']} رو داری."
    if country_name_taken(name):
        return False, "این اسم قبلاً استفاده شده؛ یه اسم دیگه امتحان کن."
    country_id = execute(
        """INSERT INTO countries
           (name, flag, iso2, owner_id, population, treasury, economy_score,
            hp, max_hp, active, is_special, is_vip)
           VALUES (?,?,?,NULL,?,?,?,?,?,1,0,0)""",
        (name, "🏳️", "", 10_000_000, 50000, 50, 1000, 1000),
    )
    for r in RESOURCES:
        execute(
            "INSERT OR IGNORE INTO resources (country_id, resource, amount) VALUES (?,?,?)",
            (country_id, r, 300),
        )
    return assign_country(user_id, country_id)

# ======================================================================
# بخش برگرفته از: diplomacy.py
# ======================================================================
# -*- coding: utf-8 -*-
"""سیستم دیپلماسی: درخواست اتحاد، پیمان عدم تجاوز، صلح، قطع رابطه، کمک مالی/نظامی."""
import time

REQUEST_KINDS = {
    "alliance": "🤝 اتحاد",
    "non_aggression": "📜 عدم‌تجاوز",
    "peace": "🕊️ صلح",
    "trade_pact": "🚢 پیمان تجاری",
}


def now():
    return int(time.time())


def get_relation(a, b):
    lo, hi = min(a, b), max(a, b)
    row = query_one("SELECT * FROM relations WHERE country_a=? AND country_b=?", (lo, hi))
    return row["status"] if row else "neutral"


def set_relation(a, b, status):
    lo, hi = min(a, b), max(a, b)
    execute(
        "INSERT INTO relations (country_a, country_b, status, updated_at) VALUES (?,?,?,?) "
        "ON CONFLICT(country_a, country_b) DO UPDATE SET status=?, updated_at=?",
        (lo, hi, status, now(), status, now()),
    )


def send_request(from_id, to_id, kind):
    if kind not in REQUEST_KINDS:
        return False, "نوع درخواست نامعتبر."
    existing = query_one(
        "SELECT * FROM diplomacy_requests WHERE from_id=? AND to_id=? AND kind=? AND status='pending'",
        (from_id, to_id, kind),
    )
    if existing:
        return False, "قبلاً چنین درخواستی ارسال شده و در انتظار پاسخه."
    rid = execute(
        "INSERT INTO diplomacy_requests (from_id, to_id, kind, status, created_at) VALUES (?,?,?,'pending',?)",
        (from_id, to_id, kind, now()),
    )
    return True, rid


def respond_request(request_id, accept):
    req = query_one("SELECT * FROM diplomacy_requests WHERE id=?", (request_id,))
    if not req or req["status"] != "pending":
        return False, "این درخواست دیگه معتبر نیست."
    new_status = "accepted" if accept else "rejected"
    execute("UPDATE diplomacy_requests SET status=? WHERE id=?", (new_status, request_id))
    if accept:
        status_map = {
            "alliance": "alliance", "non_aggression": "non_aggression",
            "peace": "neutral", "trade_pact": "trade_pact",
        }
        set_relation(req["from_id"], req["to_id"], status_map[req["kind"]])
        if req["kind"] == "peace":
            active_war = query_one(
                "SELECT * FROM wars WHERE status='active' AND "
                "((attacker_id=? AND defender_id=?) OR (attacker_id=? AND defender_id=?))",
                (req["from_id"], req["to_id"], req["to_id"], req["from_id"]),
            )
            if active_war:
                end_war(active_war["id"], "draw")
        a = get_country(req["from_id"])
        b = get_country(req["to_id"])
        add_news(f"🤝 {a['flag']} {a['name']} و {b['flag']} {b['name']} به توافق «{REQUEST_KINDS[req['kind']]}» رسیدند.")
    return True, new_status


def pending_requests_for(country_id):
    return query(
        "SELECT * FROM diplomacy_requests WHERE to_id=? AND status='pending' ORDER BY id DESC",
        (country_id,),
    )


def break_relation(a, b):
    set_relation(a, b, "neutral")


def send_aid(from_id, to_id, amount, kind="financial"):
    frm = get_country(from_id)
    if frm["treasury"] < amount:
        return False, "خزانه کافی نیست."
    execute("UPDATE countries SET treasury = treasury - ? WHERE id=?", (amount, from_id))
    execute("UPDATE countries SET treasury = treasury + ? WHERE id=?", (amount, to_id))
    to = get_country(to_id)
    add_news(f"💵 {frm['flag']} {frm['name']} کمک مالی به {to['flag']} {to['name']} ارسال کرد.")
    return True, amount


def relations_list(country_id):
    rows = query(
        "SELECT * FROM relations WHERE country_a=? OR country_b=?", (country_id, country_id)
    )
    result = []
    for r in rows:
        other = r["country_b"] if r["country_a"] == country_id else r["country_a"]
        result.append((other, r["status"]))
    return result

# ======================================================================
# بخش برگرفته از: espionage.py
# ======================================================================
# -*- coding: utf-8 -*-
"""سیستم جاسوسی: مشاهده‌ی ارتش/اقتصاد دشمن، سرقت اطلاعات، خرابکاری، ضدجاسوسی."""
import random
import time

ACTIONS = {
    "scout_army": {"name": "👁️ مشاهده ارتش", "cost": 3000, "risk": 0.25},
    "scout_economy": {"name": "👁️ مشاهده اقتصاد", "cost": 2000, "risk": 0.20},
    "steal_intel": {"name": "🗂️ سرقت اطلاعات", "cost": 6000, "risk": 0.40},
    "sabotage": {"name": "💥 خرابکاری اقتصادی", "cost": 10000, "risk": 0.55},
}


def now():
    return int(time.time())


def spy_power(country_id):
    tech = query_one(
        "SELECT level FROM tech WHERE country_id=? AND tech_key='it_tech'", (country_id,)
    )
    level = tech["level"] if tech else 0
    return 50 + level * 10


def perform_action(spy_country, target_country, action_key):
    if action_key not in ACTIONS:
        return False, "عملیات نامعتبر."
    act = ACTIONS[action_key]
    c = get_country(spy_country)
    if c["treasury"] < act["cost"]:
        return False, f"خزانه کافی نیست. هزینه: {act['cost']:,} 💰"
    execute("UPDATE countries SET treasury = treasury - ? WHERE id=?", (act["cost"], spy_country))

    my_power = spy_power(spy_country)
    their_power = spy_power(target_country) * 1.1  # مزیت ضدجاسوسی مدافع
    success_chance = max(0.1, min(0.9, my_power / (my_power + their_power) - act["risk"] * 0.3))
    success = random.random() < success_chance

    execute(
        "INSERT INTO espionage_log (spy_country, target_country, action, success, created_at) VALUES (?,?,?,?,?)",
        (spy_country, target_country, action_key, int(success), now()),
    )

    result_data = {}
    if success:
        if action_key == "scout_army":
            result_data["army"] = get_army(target_country)
        elif action_key == "scout_economy":
            t = get_country(target_country)
            result_data["economy"] = {
                "treasury": t["treasury"], "economy_score": t["economy_score"],
                "tax_rate": t["tax_rate"], "debt": t["debt"],
            }
        elif action_key == "steal_intel":
            t = get_country(target_country)
            result_data["army"] = get_army(target_country)
            result_data["economy"] = {"treasury": t["treasury"], "economy_score": t["economy_score"]}
        elif action_key == "sabotage":
            dmg = random.uniform(0.03, 0.08)
            execute("UPDATE countries SET treasury = treasury * ? WHERE id=?", (1 - dmg, target_country))
            result_data["damage_pct"] = round(dmg * 100, 1)
    else:
        # ریسک لو رفتن
        if random.random() < 0.5:
            target = get_country(target_country)
            spy = get_country(spy_country)
            add_news(f"🕵️ عملیات جاسوسی {spy['flag']} {spy['name']} علیه {target['flag']} {target['name']} لو رفت!")

    return success, result_data

# ======================================================================
# بخش برگرفته از: tech.py
# ======================================================================
# -*- coding: utf-8 -*-
"""درخت فناوری و تحقیقات."""
import time

RESEARCH_TIME_PER_LEVEL = 3600  # هر سطح یک ساعت (قابل تنظیم)


def now():
    return int(time.time())


def get_tech_level(country_id, tech_key):
    row = query_one("SELECT level FROM tech WHERE country_id=? AND tech_key=?", (country_id, tech_key))
    return row["level"] if row else 0


def get_all_tech(country_id):
    rows = query("SELECT tech_key, level FROM tech WHERE country_id=?", (country_id,))
    d = {t: 0 for t in TECH_TREE}
    for r in rows:
        d[r["tech_key"]] = r["level"]
    return d


def active_research(country_id):
    return query_one(
        "SELECT * FROM research_queue WHERE country_id=? ORDER BY id DESC LIMIT 1", (country_id,)
    )


def research_cost(tech_key, current_level):
    base = TECH_TREE[tech_key]["base_cost"]
    return int(base * (1.5 ** current_level))


def start_research(country_id, tech_key):
    if tech_key not in TECH_TREE:
        return False, "فناوری نامعتبر."
    active = active_research(country_id)
    if active and active["finishes_at"] > now():
        return False, "یک تحقیق دیگه در حال انجامه."
    level = get_tech_level(country_id, tech_key)
    if level >= TECH_TREE[tech_key]["max_level"]:
        return False, "این فناوری به حداکثر سطح رسیده."
    cost = research_cost(tech_key, level)
    c = get_country(country_id)
    if c["treasury"] < cost:
        return False, f"خزانه کافی نیست. هزینه: {cost:,} 💰"
    execute("UPDATE countries SET treasury = treasury - ? WHERE id=?", (cost, country_id))
    finish = now() + RESEARCH_TIME_PER_LEVEL
    execute(
        "INSERT INTO research_queue (country_id, tech_key, finishes_at) VALUES (?,?,?)",
        (country_id, tech_key, finish),
    )
    return True, finish


def collect_finished_research():
    """تحقیقات تمام‌شده رو اعمال می‌کنه؛ باید periodically صدا زده بشه."""
    rows = query("SELECT * FROM research_queue WHERE finishes_at <= ?", (now(),))
    for r in rows:
        execute(
            "INSERT INTO tech (country_id, tech_key, level) VALUES (?,?,1) "
            "ON CONFLICT(country_id, tech_key) DO UPDATE SET level = level + 1",
            (r["country_id"], r["tech_key"]),
        )
        execute("DELETE FROM research_queue WHERE id=?", (r["id"],))

# ======================================================================
# بخش برگرفته از: trade.py
# ======================================================================
# -*- coding: utf-8 -*-
"""تجارت جهانی و بازار منابع - قیمت‌ها بر اساس عرضه و تقاضا تغییر می‌کنن."""
import time

now = lambda: int(time.time())


def get_market():
    rows = query("SELECT * FROM market")
    return {r["resource"]: dict(r) for r in rows}


def buy_resource(country_id, resource, amount):
    if resource not in RESOURCES or amount <= 0:
        return False, "منبع نامعتبر."
    m = query_one("SELECT * FROM market WHERE resource=?", (resource,))
    price = m["price"]
    total = price * amount
    c = get_country(country_id)
    if c["treasury"] < total:
        return False, f"خزانه کافی نیست. هزینه: {total:,.0f} 💰"
    execute("UPDATE countries SET treasury = treasury - ? WHERE id=?", (total, country_id))
    add_resource(country_id, resource, amount)
    # خرید باعث افزایش تقاضا و کمی افزایش قیمت می‌شه
    new_price = price * (1 + min(0.02 * (amount / 100), 0.15))
    execute("UPDATE market SET price=?, demand = demand + ? WHERE resource=?", (new_price, amount, resource))
    execute(
        "INSERT INTO trade_log (country_id, resource, action, amount, price, created_at) VALUES (?,?,?,?,?,?)",
        (country_id, resource, "buy", amount, price, now()),
    )
    return True, total


def sell_resource(country_id, resource, amount):
    if resource not in RESOURCES or amount <= 0:
        return False, "منبع نامعتبر."
    res = get_resources(country_id)
    if res.get(resource, 0) < amount:
        return False, "این مقدار منبع رو نداری."
    m = query_one("SELECT * FROM market WHERE resource=?", (resource,))
    price = m["price"]
    total = price * amount * 0.9  # کمیسیون فروش
    add_resource(country_id, resource, -amount)
    execute("UPDATE countries SET treasury = treasury + ? WHERE id=?", (total, country_id))
    new_price = price * (1 - min(0.02 * (amount / 100), 0.15))
    execute("UPDATE market SET price=?, supply = supply + ? WHERE resource=?", (max(1, new_price), amount, resource))
    execute(
        "INSERT INTO trade_log (country_id, resource, action, amount, price, created_at) VALUES (?,?,?,?,?,?)",
        (country_id, resource, "sell", amount, price, now()),
    )
    return True, total

# ======================================================================
# بخش برگرفته از: territory.py
# ======================================================================
# -*- coding: utf-8 -*-
"""مدیریت سرزمین‌ها: استان‌های هر کشور و تنگه‌های استراتژیک."""
import random

PROVINCE_NAME_SUFFIXES = ["شمالی", "جنوبی", "شرقی", "غربی", "مرکزی"]


def create_provinces_for_country(country_id, count=4):
    """وقتی بازیکن کشوری رو انتخاب می‌کنه، چند استان اولیه براش ساخته می‌شه."""
    existing = query_one("SELECT COUNT(*) n FROM territories WHERE original_owner_id=?", (country_id,))
    if existing and existing["n"] > 0:
        return
    c = get_country(country_id)
    for i in range(count):
        suffix = PROVINCE_NAME_SUFFIXES[i % len(PROVINCE_NAME_SUFFIXES)]
        name = f"استان {suffix} {c['name']}"
        pop = c["population"] / count
        econ_val = random.randint(3000, 12000)
        execute(
            """INSERT INTO territories
               (name, owner_id, original_owner_id, population, economic_value, strategic_value, is_strait)
               VALUES (?,?,?,?,?,?,0)""",
            (name, country_id, country_id, pop, econ_val, random.randint(1, 5)),
        )


def list_owned(country_id):
    return query("SELECT * FROM territories WHERE owner_id=? ORDER BY is_strait DESC, id", (country_id,))


def list_straits():
    return query("SELECT * FROM territories WHERE is_strait=1 ORDER BY id")


def total_territory_value(country_id):
    rows = list_owned(country_id)
    return sum(r["economic_value"] for r in rows)


def territory_count(country_id):
    row = query_one("SELECT COUNT(*) n FROM territories WHERE owner_id=?", (country_id,))
    return row["n"] if row else 0


def capture_random_territory(winner_id, loser_id):
    """در پایان یک جنگ با پیروزی مهاجم، یک سرزمین (ترجیحاً غیر تنگه) از بازنده گرفته می‌شه."""
    terr = query_one(
        "SELECT * FROM territories WHERE owner_id=? AND is_strait=0 ORDER BY RANDOM() LIMIT 1", (loser_id,)
    )
    if not terr:
        terr = query_one(
            "SELECT * FROM territories WHERE owner_id=? ORDER BY RANDOM() LIMIT 1", (loser_id,)
        )
    if terr:
        execute("UPDATE territories SET owner_id=? WHERE id=?", (winner_id, terr["id"]))
        return terr
    return None


def transfer_all_territories(loser_id, winner_id):
    """وقتی یک کشور کاملاً نابود می‌شه، همه‌ی سرزمین‌هاش (از جمله تنگه‌ها) به فاتح منتقل می‌شه."""
    rows = query("SELECT id FROM territories WHERE owner_id=?", (loser_id,))
    if rows:
        execute("UPDATE territories SET owner_id=? WHERE owner_id=?", (winner_id, loser_id))
    return len(rows)

# ======================================================================
# بخش برگرفته از: ranking.py
# ======================================================================
# -*- coding: utf-8 -*-
"""رتبه‌بندی جهانی کشورها."""


def top_wealth(limit=10):
    return query(
        "SELECT * FROM countries WHERE owner_id IS NOT NULL AND (is_special IS NULL OR is_special=0) "
        "ORDER BY treasury DESC LIMIT ?", (limit,)
    )


def top_military(limit=10):
    countries = query("SELECT * FROM countries WHERE owner_id IS NOT NULL AND (is_special IS NULL OR is_special=0)")
    scored = [(c, military_power(c["id"])) for c in countries]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


def top_territory(limit=10):
    countries = query("SELECT * FROM countries WHERE owner_id IS NOT NULL AND (is_special IS NULL OR is_special=0)")
    scored = [(c, territory_count(c["id"])) for c in countries]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


def top_industry(limit=10):
    rows = query(
        """SELECT country_id, COUNT(*) n FROM factories
           GROUP BY country_id ORDER BY n DESC LIMIT ?""", (limit,)
    )
    return rows


def top_tech(limit=10):
    rows = query(
        """SELECT country_id, SUM(level) total FROM tech
           GROUP BY country_id ORDER BY total DESC LIMIT ?""", (limit,)
    )
    return rows


def top_wins(limit=10):
    return query(
        "SELECT * FROM countries WHERE owner_id IS NOT NULL AND (is_special IS NULL OR is_special=0) "
        "ORDER BY wins DESC LIMIT ?", (limit,)
    )


def top_overall_power(limit=10):
    """رتبه‌ی کلی: ترکیبی از پیروزی، رضایت مردم و قلمرو (نه صرفاً پول/قدرت خام)."""
    countries = query("SELECT * FROM countries WHERE owner_id IS NOT NULL AND (is_special IS NULL OR is_special=0)")
    scored = []
    for c in countries:
        terr = territory_count(c["id"])
        score = c["wins"] * 40 + c["satisfaction"] * 3 + c["conquests"] * 50 + terr * 10
        scored.append((c, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]

# ======================================================================
# بخش برگرفته از: shop.py
# ======================================================================
# -*- coding: utf-8 -*-
"""
فروشگاه: خرید کشورهای VIP (روسیه/آمریکا/چین) و پک‌های تجهیزات/اقتصادی با پول واقعی
از طریق سیستم پرداخت تلگرام (sendInvoice).
"""
import time



def now():
    return int(time.time())


def is_vip_country(country):
    return bool(country["is_vip"])


def start_vip_purchase(chat_id, user_id, country_id):
    c = get_country(country_id)
    if not c or c["owner_id"] is not None:
        send_message(chat_id, "⛔ این کشور دیگه در دسترس نیست.")
        return
    existing = get_country_by_owner(user_id)
    if existing and existing["id"] != country_id:
        send_message(chat_id, f"⛔ تو همین الان کشور {existing['flag']} {existing['name']} رو داری.")
        return
    amount_rial = VIP_COUNTRY_PRICE_TOMAN * 10
    payload = f"vipcountry:{country_id}:{user_id}"
    if TELEGRAM_PROVIDER_TOKEN:
        send_invoice(
            chat_id,
            title=f"کشور VIP: {c['name']}",
            description=f"دریافت کشور {c['flag']} {c['name']} به‌عنوان کشور ویژه (VIP)",
            payload=payload,
            amount_rial=amount_rial,
        )
        return
    start_manual_card_payment(chat_id, user_id, "vipcountry", payload, VIP_COUNTRY_PRICE_TOMAN,
                               title=f"کشور VIP: {c['flag']} {c['name']}")


def start_pack_purchase(chat_id, user_id, pack_key):
    if pack_key not in PACKS:
        send_message(chat_id, "⛔ پک نامعتبر.")
        return
    c = get_country_by_owner(user_id)
    if not c:
        send_message(chat_id, "⛔ اول باید یک کشور انتخاب کنی (/start).")
        return
    pack = PACKS[pack_key]
    amount_rial = PACK_PRICE_TOMAN * 10
    payload = f"pack:{pack_key}:{c['id']}"
    if TELEGRAM_PROVIDER_TOKEN:
        send_invoice(
            chat_id,
            title=pack["name"],
            description=pack["desc"],
            payload=payload,
            amount_rial=amount_rial,
        )
        return
    start_manual_card_payment(chat_id, user_id, "pack", payload, PACK_PRICE_TOMAN, title=pack["name"])


def start_manual_card_payment(chat_id, user_id, kind, payload, amount_toman, title):
    """
    وقتی درگاه رسمی (TELEGRAM_PROVIDER_TOKEN) تنظیم نشده، پرداخت به‌صورت
    کارت‌به‌کارت دستی انجام می‌شه: کاربر مبلغ رو به کارت واریز می‌کنه، دکمه‌ی
    «پرداخت کردم» رو می‌زنه، و ادمین از پنلش تایید/رد می‌کنه.
    """
    if not PAYMENT_CARD_NUMBER:
        send_message(chat_id, "⛔ سیستم پرداخت هنوز توسط ادمین تنظیم نشده.")
        return
    pending_id = execute(
        "INSERT INTO pending_payments (user_id, chat_id, kind, payload, amount_toman, status, created_at) "
        "VALUES (?,?,?,?,?, 'awaiting_claim', ?)",
        (user_id, chat_id, kind, payload, amount_toman, now()),
    )
    card_display = " ".join([PAYMENT_CARD_NUMBER[i:i+4] for i in range(0, len(PAYMENT_CARD_NUMBER), 4)])
    text = (
        f"💳 <b>{title}</b>\n\n"
        f"مبلغ: {amount_toman:,.0f} تومان\n"
        f"شماره کارت: <code>{card_display}</code>\n"
        f"به نام: {PAYMENT_CARD_HOLDER}\n\n"
        "بعد از واریز، دکمه‌ی زیر رو بزن تا به ادمین اطلاع داده بشه.\n"
        "⚠️ تا زمانی که ادمین تاییدش نکنه، خریدت نهایی نمی‌شه."
    )
    rows = [[{"text": "✅ پرداخت کردم", "callback_data": f"paidclaim:{pending_id}"}]]
    send_message(chat_id, text, reply_markup={"inline_keyboard": rows})


def claim_manual_payment(chat_id, user_id, pending_id):
    p = query_one("SELECT * FROM pending_payments WHERE id=?", (pending_id,))
    if not p or p["user_id"] != user_id:
        send_message(chat_id, "⛔ این درخواست پیدا نشد.")
        return
    if p["status"] != "awaiting_claim":
        send_message(chat_id, "این درخواست قبلاً بررسی شده.")
        return
    execute("UPDATE pending_payments SET status='pending_review' WHERE id=?", (pending_id,))
    send_message(chat_id, "✅ اطلاع دادیم به ادمین. بعد از تایید، خریدت اعمال می‌شه.")

    buyer = get_user(user_id)
    buyer_label = (buyer["username"] if buyer and buyer["username"] else str(user_id))
    admin_text = (
        f"💳 <b>درخواست پرداخت جدید</b>\n"
        f"کاربر: {buyer_label} (آیدی {user_id})\n"
        f"نوع: {p['kind']} — {p['payload']}\n"
        f"مبلغ ادعاشده: {p['amount_toman']:,.0f} تومان\n\n"
        "⚠️ حتماً قبل از تایید، واریزی رو تو حساب/کارتت چک کن."
    )
    admin_rows = [[
        {"text": "✅ تایید و اعطا", "callback_data": f"admin:payapprove:{pending_id}"},
        {"text": "❌ رد", "callback_data": f"admin:payreject:{pending_id}"},
    ]]
    for admin_id in ADMIN_IDS:
        try:
            send_message(admin_id, admin_text, reply_markup={"inline_keyboard": admin_rows})
        except Exception as e:
            print(f"[shop] خطا در اطلاع‌رسانی به ادمین {admin_id}: {e}")


def approve_manual_payment(admin_chat_id, pending_id):
    p = query_one("SELECT * FROM pending_payments WHERE id=?", (pending_id,))
    if not p:
        send_message(admin_chat_id, "درخواست پیدا نشد.")
        return
    if p["status"] not in ("pending_review", "awaiting_claim"):
        send_message(admin_chat_id, "این درخواست قبلاً بررسی شده.")
        return
    execute("UPDATE pending_payments SET status='approved' WHERE id=?", (pending_id,))
    fake_sp = {"invoice_payload": p["payload"], "total_amount": int(p["amount_toman"] * 10),
               "provider_payment_charge_id": f"manual-{pending_id}"}
    handle_successful_payment(p["chat_id"], p["user_id"], fake_sp)
    send_message(admin_chat_id, "✅ پرداخت تایید و اعمال شد.")


def reject_manual_payment(admin_chat_id, pending_id):
    p = query_one("SELECT * FROM pending_payments WHERE id=?", (pending_id,))
    if not p:
        send_message(admin_chat_id, "درخواست پیدا نشد.")
        return
    execute("UPDATE pending_payments SET status='rejected' WHERE id=?", (pending_id,))
    if p["kind"] == "customcountry":
        try:
            cid = int(p["payload"].split(":")[1])
            execute("UPDATE countries SET active=0 WHERE id=?", (cid,))
        except Exception:
            pass
    send_message(p["chat_id"], "❌ پرداختت تایید نشد. اگه فکر می‌کنی اشتباهه، به ادمین پیام بده.")
    send_message(admin_chat_id, "رد شد.")


def grant_pack(country_id, pack_key):
    pack = PACKS[pack_key]
    if "units" in pack:
        for unit_key, qty in pack["units"].items():
            execute(
                "INSERT INTO army (country_id, unit_key, quantity) VALUES (?,?,?) "
                "ON CONFLICT(country_id, unit_key) DO UPDATE SET quantity = quantity + ?",
                (country_id, unit_key, qty, qty),
            )
    if "cash" in pack:
        execute("UPDATE countries SET treasury = treasury + ? WHERE id=?", (pack["cash"], country_id))


def log_payment(user_id, kind, payload, amount_toman, charge_id):
    execute(
        "INSERT INTO payments (user_id, kind, payload, amount_toman, charge_id, created_at) VALUES (?,?,?,?,?,?)",
        (user_id, kind, payload, amount_toman, charge_id, now()),
    )


def handle_successful_payment(chat_id, user_id, successful_payment):
    payload = successful_payment.get("invoice_payload", "") or ""
    total_amount = successful_payment.get("total_amount", 0)
    charge_id = (
        successful_payment.get("provider_payment_charge_id")
        or successful_payment.get("telegram_payment_charge_id")
        or ""
    )
    amount_toman = (total_amount or 0) / 10

    parts = payload.split(":")
    if not parts:
        return
    kind = parts[0]

    if kind == "vipcountry" and len(parts) == 3:
        country_id, buyer_id = int(parts[1]), int(parts[2])
        ok, res = assign_country(buyer_id, country_id)
        log_payment(user_id, "vipcountry", payload, amount_toman, charge_id)
        if ok:
            c = res
            apply_vip_starting_bonus(c)
            add_news(f"💎 یک بازیکن با پرداخت VIP کنترل {c['flag']} {c['name']} را به دست گرفت.", category="ownership_change")
            send_message(chat_id, f"✅ پرداخت موفق بود! کشور {c['flag']} {c['name']} در اختیار توئه.")
        else:
            send_message(chat_id, f"⚠️ پرداخت ثبت شد ولی مشکلی پیش اومد: {res}\nلطفاً به ادمین پیام بده.")

    elif kind == "pack" and len(parts) == 3:
        pack_key, country_id = parts[1], int(parts[2])
        grant_pack(country_id, pack_key)
        log_payment(user_id, f"pack:{pack_key}", payload, amount_toman, charge_id)
        pack = PACKS[pack_key]
        send_message(chat_id, f"✅ پرداخت موفق بود! {pack['name']} به کشورت اضافه شد.")

    elif kind == "customcountry" and len(parts) == 3:
        # این مسیر دیگه استفاده نمی‌شه چون ساخت کشور اختصاصی رایگانه (بدون پرداخت انجام می‌شه)؛
        # فقط برای سازگاری با پرداخت‌های قدیمی نگه داشته شده.
        country_id, buyer_id = int(parts[1]), int(parts[2])
        ok, res = assign_country(buyer_id, country_id)
        log_payment(user_id, "customcountry", payload, amount_toman, charge_id)
        if ok:
            c = res
            execute("UPDATE countries SET is_special=0 WHERE id=?", (country_id,))
            add_news(f"🎨 یک بازیکن کشور اختصاصی «{c['name']}» را ساخت.", category="ownership_change")
            send_message(chat_id, f"✅ پرداخت موفق بود! کشور اختصاصی «{c['name']}» ساخته و در اختیار توئه.")
        else:
            send_message(chat_id, f"⚠️ پرداخت ثبت شد ولی مشکلی پیش اومد: {res}\nلطفاً به ادمین پیام بده.")
    else:
        log_payment(user_id, "unknown", payload, amount_toman, charge_id)
        send_message(chat_id, "✅ پرداخت دریافت شد.")


def apply_vip_starting_bonus(country):
    bonus = VIP_STARTING_BONUS.get(country["name"])
    if not bonus:
        return
    if "treasury_bonus" in bonus:
        execute("UPDATE countries SET treasury = treasury + ? WHERE id=?",
               (bonus["treasury_bonus"], country["id"]))
    if "units" in bonus:
        for unit_key, qty in bonus["units"].items():
            execute(
                "INSERT INTO army (country_id, unit_key, quantity) VALUES (?,?,?) "
                "ON CONFLICT(country_id, unit_key) DO UPDATE SET quantity = quantity + ?",
                (country["id"], unit_key, qty, qty),
            )

# ======================================================================
# بخش برگرفته از: un.py و alliance.py (سازمان ملل و اتحادها)
# ======================================================================
# -*- coding: utf-8 -*-
"""سازمان ملل: عضویت، قطعنامه‌ها، رای‌گیری، برگزاری جلسه."""


def now():
    return int(time.time())


def is_member(country_id):
    row = query_one("SELECT country_id FROM un_members WHERE country_id=?", (country_id,))
    return row is not None


def join(country_id):
    if is_member(country_id):
        return False, "این کشور از قبل عضو سازمان ملله."
    execute("INSERT INTO un_members (country_id, joined_at) VALUES (?,?)", (country_id, now()))
    c = get_country(country_id)
    add_news(f"🏛️ {c['flag']} {c['name']} به سازمان ملل پیوست.")
    return True, "عضو شدی."


def leave(country_id):
    if not is_member(country_id):
        return False, "عضو سازمان ملل نیستی."
    execute("DELETE FROM un_members WHERE country_id=?", (country_id,))
    return True, "از سازمان ملل خارج شدی."


def list_members():
    rows = query("SELECT country_id FROM un_members")
    return [get_country(r["country_id"]) for r in rows]


def member_count():
    row = query_one("SELECT COUNT(*) n FROM un_members")
    return row["n"] if row else 0


def propose_resolution(country_id, title, description):
    if not is_member(country_id):
        return False, "برای پیشنهاد قطعنامه باید عضو سازمان ملل باشی."
    rid = execute(
        "INSERT INTO un_resolutions (proposer_id, title, description, status, created_at) "
        "VALUES (?,?,?,'voting',?)",
        (country_id, title, description, now()),
    )
    c = get_country(country_id)
    add_news(f"📜 {c['flag']} {c['name']} قطعنامه‌ی «{title}» را به سازمان ملل پیشنهاد داد.")
    return True, rid


def list_active_resolutions():
    return query("SELECT * FROM un_resolutions WHERE status='voting' ORDER BY id DESC")


def list_resolutions(limit=15):
    return query("SELECT * FROM un_resolutions ORDER BY id DESC LIMIT ?", (limit,))


def get_resolution(rid):
    return query_one("SELECT * FROM un_resolutions WHERE id=?", (rid,))


def vote(resolution_id, country_id, choice):
    if not is_member(country_id):
        return False, "برای رای‌دادن باید عضو سازمان ملل باشی."
    r = get_resolution(resolution_id)
    if not r or r["status"] != "voting":
        return False, "این قطعنامه دیگه در حال رای‌گیری نیست."
    execute(
        "INSERT INTO un_votes (resolution_id, country_id, vote) VALUES (?,?,?) "
        "ON CONFLICT(resolution_id, country_id) DO UPDATE SET vote=?",
        (resolution_id, country_id, choice, choice),
    )
    return True, "رایت ثبت شد."


def vote_counts(resolution_id):
    rows = query("SELECT vote, COUNT(*) n FROM un_votes WHERE resolution_id=? GROUP BY vote", (resolution_id,))
    counts = {"yes": 0, "no": 0, "abstain": 0}
    for r in rows:
        counts[r["vote"]] = r["n"]
    return counts


def close_resolution(resolution_id):
    r = get_resolution(resolution_id)
    if not r or r["status"] != "voting":
        return False, "این قطعنامه دیگه در حال رای‌گیری نیست."
    counts = vote_counts(resolution_id)
    status = "passed" if counts["yes"] > counts["no"] else "failed"
    execute("UPDATE un_resolutions SET status=?, closed_at=? WHERE id=?", (status, now(), resolution_id))
    verdict = "✅ تصویب شد" if status == "passed" else "❌ رد شد"
    add_news(
        f"📜 قطعنامه‌ی «{r['title']}» {verdict} (موافق: {counts['yes']}، مخالف: {counts['no']}، ممتنع: {counts['abstain']})."
    )
    return True, status


def hold_meeting(country_id, topic):
    if not is_member(country_id):
        return False, "برای برگزاری جلسه باید عضو سازمان ملل باشی."
    c = get_country(country_id)
    add_news(f"📅 جلسه‌ی سازمان ملل با موضوع «{topic}» به درخواست {c['flag']} {c['name']} برگزار شد.")
    return True, "جلسه اعلام شد."
# -*- coding: utf-8 -*-
"""اتحادها (گروه چندنفره): ساخت، عضویت، لیدری، پیام همگانی، جلسه."""


def now():
    return int(time.time())


def get_alliance_of(country_id):
    row = query_one("SELECT alliance_id FROM alliance_members WHERE country_id=?", (country_id,))
    if not row:
        return None
    return query_one("SELECT * FROM alliances WHERE id=?", (row["alliance_id"],))


def get_alliance(alliance_id):
    return query_one("SELECT * FROM alliances WHERE id=?", (alliance_id,))


def list_alliances():
    return query("SELECT * FROM alliances ORDER BY id")


def list_members(alliance_id):
    rows = query("SELECT country_id FROM alliance_members WHERE alliance_id=?", (alliance_id,))
    return [get_country(r["country_id"]) for r in rows]


def is_leader(country_id, alliance_id):
    a = get_alliance(alliance_id)
    return bool(a and a["leader_country_id"] == country_id)


def create_alliance(country_id, name):
    if get_alliance_of(country_id):
        return False, "تو همین الان عضو یک اتحادی؛ اول ازش خارج شو."
    existing = query_one("SELECT id FROM alliances WHERE name=?", (name,))
    if existing:
        return False, "این اسم قبلاً برای یک اتحاد دیگه استفاده شده."
    alliance_id = execute(
        "INSERT INTO alliances (name, leader_country_id, created_at) VALUES (?,?,?)",
        (name, country_id, now()),
    )
    execute(
        "INSERT INTO alliance_members (alliance_id, country_id, joined_at) VALUES (?,?,?)",
        (alliance_id, country_id, now()),
    )
    c = get_country(country_id)
    add_news(f"🏰 اتحاد «{name}» به رهبری {c['flag']} {c['name']} تشکیل شد.")
    return True, alliance_id


def request_join(country_id, alliance_id):
    if get_alliance_of(country_id):
        return False, "تو همین الان عضو یک اتحادی."
    a = get_alliance(alliance_id)
    if not a:
        return False, "این اتحاد پیدا نشد."
    existing = query_one(
        "SELECT id FROM alliance_join_requests WHERE alliance_id=? AND country_id=? AND status='pending'",
        (alliance_id, country_id),
    )
    if existing:
        return False, "قبلاً درخواست دادی و منتظر پاسخ لیدر هستی."
    rid = execute(
        "INSERT INTO alliance_join_requests (alliance_id, country_id, status, created_at) VALUES (?,?,'pending',?)",
        (alliance_id, country_id, now()),
    )
    return True, rid


def pending_requests_for_leader(alliance_id):
    return query(
        "SELECT * FROM alliance_join_requests WHERE alliance_id=? AND status='pending' ORDER BY id",
        (alliance_id,),
    )


def respond_join_request(request_id, accept):
    req = query_one("SELECT * FROM alliance_join_requests WHERE id=?", (request_id,))
    if not req or req["status"] != "pending":
        return False, "این درخواست دیگه معتبر نیست."
    new_status = "accepted" if accept else "rejected"
    execute("UPDATE alliance_join_requests SET status=? WHERE id=?", (new_status, request_id))
    if accept:
        if get_alliance_of(req["country_id"]):
            return False, "این کشور همین الان عضو یک اتحاد دیگه‌ست."
        execute(
            "INSERT INTO alliance_members (alliance_id, country_id, joined_at) VALUES (?,?,?)",
            (req["alliance_id"], req["country_id"], now()),
        )
        c = get_country(req["country_id"])
        a = get_alliance(req["alliance_id"])
        add_news(f"🏰 {c['flag']} {c['name']} به اتحاد «{a['name']}» پیوست.")
    return True, new_status


def leave_alliance(country_id):
    a = get_alliance_of(country_id)
    if not a:
        return False, "تو عضو هیچ اتحادی نیستی."
    if a["leader_country_id"] == country_id:
        # لیدر که بره، کل اتحاد منحل می‌شه
        execute("DELETE FROM alliance_members WHERE alliance_id=?", (a["id"],))
        execute("DELETE FROM alliance_join_requests WHERE alliance_id=?", (a["id"],))
        execute("DELETE FROM alliances WHERE id=?", (a["id"],))
        add_news(f"🏰 اتحاد «{a['name']}» به دلیل خروج لیدر منحل شد.")
        return True, "اتحاد منحل شد (چون تو لیدر بودی)."
    execute("DELETE FROM alliance_members WHERE country_id=?", (country_id,))
    return True, "از اتحاد خارج شدی."


def broadcast_to_alliance(leader_country_id, text):
    a = get_alliance_of(leader_country_id)
    if not a or not is_leader(leader_country_id, a["id"]):
        return False, "فقط لیدر اتحاد می‌تونه پیام همگانی بده."
    members = list_members(a["id"])
    sent = 0
    for m in members:
        if m["id"] == leader_country_id:
            continue
        if m["owner_id"]:
            try:
                send_message(m["owner_id"], f"📢 <b>پیام لیدر اتحاد «{a['name']}»</b>\n\n{text}")
                sent += 1
            except Exception:
                pass
    return True, sent


def hold_alliance_meeting(leader_country_id, topic):
    a = get_alliance_of(leader_country_id)
    if not a or not is_leader(leader_country_id, a["id"]):
        return False, "فقط لیدر اتحاد می‌تونه جلسه برگزار کنه."
    ok, sent = broadcast_to_alliance(leader_country_id, f"📅 جلسه‌ی اتحاد با موضوع «{topic}» تشکیل شد.")
    add_news(f"📅 اتحاد «{a['name']}» جلسه‌ای با موضوع «{topic}» برگزار کرد.")
    return True, sent

# ======================================================================
# بخش برگرفته از: handlers.py
# ======================================================================
# -*- coding: utf-8 -*-
"""
تمام منطق نمایش منوها و پاسخ به دکمه‌ها/پیام‌های متنی بازیکنان (غیر از پنل ادمین).
"""
import time


# ورودی‌های متنی در انتظار (مثلاً «چند واحد بخرم؟»)
# ساختار: { user_id: {"action": "...", **extra} }
AWAITING = {}


def fmt_num(n):
    try:
        return f"{n:,.0f}"
    except Exception:
        return str(n)


def require_country(user_id):
    u = get_user(user_id)
    if not u or not u["country_id"]:
        return None
    return get_country(u["country_id"])


# ------------------------------------------------------------ شروع / انتخاب کشور

def cmd_start(chat_id, user_id, username):
    ensure_user(user_id, username)
    c = require_country(user_id)
    if c:
        send_main_menu(chat_id, c)
    else:
        send_country_selection(chat_id, page=0)


def country_list_kb(page=0, per_page=8):
    free = list_free_countries()
    start = page * per_page
    chunk = free[start:start + per_page]
    rows = []
    for c in chunk:
        label = f"{c['flag']} {c['name']}"
        if c["is_vip"]:
            label = f"💎 {label} (VIP)"
        rows.append([(label, f"selcountry:{c['id']}")])
    nav = []
    if page > 0:
        nav.append(("⬅️ قبلی", f"selpage:{page-1}"))
    if start + per_page < len(free):
        nav.append(("بعدی ➡️", f"selpage:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([("🎨 ساخت کشور اختصاصی (اسم دلخواه)", "customcountry:new")])
    rows.append([("📋 کشورهای گرفته‌شده", "seltaken:0")])
    return kb(rows)


def send_country_selection(chat_id, page=0):
    text = (
        "🌍 <b>به بازی جنگ جهانی خوش اومدی!</b>\n\n"
        "برای شروع، یکی از کشورهای آزاد زیر رو انتخاب کن.\n"
        "هر کشور فقط یک‌بار و توسط یک بازیکن قابل انتخابه."
    )
    send_message(chat_id, text, reply_markup=country_list_kb(page))


def show_taken_countries(chat_id, message_id=None):
    taken = list_taken_countries()
    if not taken:
        text = "😶 هنوز هیچ کشوری گرفته نشده."
    else:
        lines = ["📋 <b>کشورهای دارای بازیکن:</b>\n"]
        for c in taken:
            lines.append(f"{c['flag']} {c['name']}")
        text = "\n".join(lines)
    render(chat_id, message_id, text, back_kb("menu:main_or_select"))


def confirm_country_selection(chat_id, message_id, user_id, country_id):
    c = get_country(country_id)
    if not c or c["owner_id"] is not None:
        render(chat_id, message_id, "⛔ متاسفانه این کشور دیگه در دسترس نیست.", country_list_kb(0))
        return
    existing = get_country_by_owner(user_id)
    if existing and existing["id"] != country_id:
        render(chat_id, message_id,
               f"⛔ تو همین الان کشور {existing['flag']} {existing['name']} رو داری.\n"
               "هر بازیکن فقط می‌تونه یک کشور داشته باشه.",
               back_kb("menu:main"))
        return
    if c["is_vip"]:
        text = (
            f"💎 {c['flag']} <b>{c['name']}</b> (کشور VIP)\n"
            f"👥 جمعیت: {fmt_num(c['population'])}\n\n"
            f"این کشور فقط از طریق پرداخت قابل دریافته.\n"
            f"قیمت: {VIP_COUNTRY_PRICE_TOMAN:,} تومان"
        )
        rows = [[("💳 پرداخت و دریافت", f"buyvipcountry:{country_id}")], [("🔙 بازگشت", "menu:reselect")]]
        render(chat_id, message_id, text, kb(rows))
        return
    text = (
        f"{c['flag']} <b>{c['name']}</b>\n"
        f"👥 جمعیت: {fmt_num(c['population'])}\n"
        f"📈 ضریب اقتصاد پایه: {c['economy_score']}\n"
        f"💰 خزانه اولیه: {fmt_num(c['treasury'])}\n\n"
        "آیا این کشور رو انتخاب می‌کنی؟ (این انتخاب قابل تغییر نیست مگر با هماهنگی ادمین)"
    )
    render(chat_id, message_id, text, confirm_kb(f"confirmsel:{country_id}", "menu:reselect"))


def do_start_vip_purchase(chat_id, message_id, user_id, country_id):
    start_vip_purchase(chat_id, user_id, country_id)


def do_select_country(chat_id, message_id, user_id, username, country_id):
    ensure_user(user_id, username)
    ok, res = assign_country(user_id, country_id)
    if not ok:
        render(chat_id, message_id, f"⛔ {res}", country_list_kb(0))
        return
    c = res
    add_news(f"🆕 یک بازیکن جدید کنترل {c['flag']} {c['name']} را به دست گرفت.", category="ownership_change")
    render(chat_id, message_id, f"✅ تبریک! تو حالا رهبر {c['flag']} {c['name']} هستی.", main_menu_kb())


# ------------------------------------------------------------------- ابزار رندر

def render(chat_id, message_id, text, reply_markup=None):
    if message_id:
        r = edit_message_text(chat_id, message_id, text, reply_markup=reply_markup)
        if r and r.get("ok"):
            return
    send_message(chat_id, text, reply_markup=reply_markup)


def send_main_menu(chat_id, c, message_id=None):
    text = (
        f"{c['flag']} <b>{c['name']}</b>\n"
        "━━━━━━━━━━━━\n"
        f"💰 خزانه: {fmt_num(c['treasury'])}\n"
        f"🪖 قدرت نظامی: {fmt_num(military_power(c['id']))}\n"
        f"🗺️ قلمرو: {territory_count(c['id'])} منطقه\n"
        f"📈 اقتصاد: {fmt_num(c['economy_score'])}\n"
        f"❤️ سلامت کشور: {fmt_num(c['hp'])}/{fmt_num(c['max_hp'])}\n"
        f"😊 رضایت مردم: {fmt_num(c['satisfaction'])}%\n"
        "━━━━━━━━━━━━"
    )
    render(chat_id, message_id, text, main_menu_kb())


# ---------------------------------------------------------------- اطلاعات کشور

def show_info(chat_id, message_id, user_id):
    c = require_country(user_id)
    if not c:
        return
    owner = get_user(c["owner_id"])
    text = (
        f"{c['flag']} <b>{c['name']}</b>\n"
        f"👤 رهبر: {owner['username'] or owner['user_id']}\n"
        f"👥 جمعیت: {fmt_num(c['population'])}\n"
        f"💰 خزانه: {fmt_num(c['treasury'])}\n"
        f"💳 بدهی: {fmt_num(c['debt'])}\n"
        f"📈 اقتصاد: {fmt_num(c['economy_score'])}\n"
        f"😊 رضایت: {fmt_num(c['satisfaction'])}%\n"
        f"🪖 روحیه: {fmt_num(c['morale'])}%\n"
        f"❤️ سلامت: {fmt_num(c['hp'])}/{fmt_num(c['max_hp'])}\n"
        f"🏆 برد/باخت: {c['wins']}/{c['losses']}\n"
        f"🗺️ قلمرو: {territory_count(c['id'])} منطقه\n"
    )
    render(chat_id, message_id, text, back_kb())


# -------------------------------------------------------------- اقتصاد و بودجه

def show_economy(chat_id, message_id, user_id):
    c = require_country(user_id)
    if not c:
        return
    text = (
        f"💰 <b>اقتصاد و خزانه‌ی {c['name']}</b>\n\n"
        f"خزانه: {fmt_num(c['treasury'])}\n"
        f"بدهی: {fmt_num(c['debt'])}\n"
        f"نرخ مالیات: {c['tax_rate']*100:.0f}%\n"
        f"بودجه نظامی: {c['military_budget_pct']:.0f}%\n"
        f"بودجه تحقیقات: {c['research_budget_pct']:.0f}%\n"
        f"ضریب اقتصاد: {fmt_num(c['economy_score'])}\n\n"
        "درآمد هر دوره از مالیات، منهای هزینه‌ی نگهداری ارتش و کارخانه‌ها محاسبه می‌شه."
    )
    rows = [
        [("➕ مالیات", "tax:up"), ("➖ مالیات", "tax:down")],
        [("➕ بودجه نظامی", "milb:up"), ("➖ بودجه نظامی", "milb:down")],
        [("➕ بودجه تحقیقات", "resb:up"), ("➖ بودجه تحقیقات", "resb:down")],
        [("🔙 بازگشت", "menu:main")],
    ]
    render(chat_id, message_id, text, kb(rows))


def adjust_tax(user_id, direction):
    c = require_country(user_id)
    if not c:
        return
    delta = 0.02 if direction == "up" else -0.02
    new_rate = max(0.05, min(0.60, c["tax_rate"] + delta))
    execute("UPDATE countries SET tax_rate=? WHERE id=?", (new_rate, c["id"]))


def adjust_budget(user_id, field, direction):
    c = require_country(user_id)
    if not c:
        return
    delta = 5 if direction == "up" else -5
    current = c[field]
    new_val = max(0, min(80, current + delta))
    execute(f"UPDATE countries SET {field}=? WHERE id=?", (new_val, c["id"]))


# ------------------------------------------------------------------- منابع

def show_resources(chat_id, message_id, user_id):
    c = require_country(user_id)
    if not c:
        return
    res = get_resources(c["id"])
    lines = [f"⛏️ <b>منابع {c['name']}</b>\n"]
    for r in RESOURCES:
        lines.append(f"{RESOURCE_FA[r]}: {fmt_num(res[r])}")
    text = "\n".join(lines)
    rows = [[("🚢 رفتن به بازار تجارت", "menu:trade")], [("🔙 بازگشت", "menu:main")]]
    render(chat_id, message_id, text, kb(rows))


# ----------------------------------------------------------------- کارخانه‌ها

def show_factory_menu(chat_id, message_id, user_id):
    c = require_country(user_id)
    if not c:
        return
    owned = list_factories(c["id"])
    counts = {}
    for f in owned:
        counts[f["ftype"]] = counts.get(f["ftype"], 0) + 1
    lines = [f"🏭 <b>کارخانه‌های {c['name']}</b>\n"]
    if owned:
        for f in owned:
            info = FACTORY_TYPES[f["ftype"]]
            lines.append(f"{info['name']} — سطح {f['level']} (#{f['id']})")
    else:
        lines.append("هنوز کارخانه‌ای نساختی.")
    text = "\n".join(lines)

    rows = []
    for ftype, info in FACTORY_TYPES.items():
        cost = factory_build_cost(ftype, counts.get(ftype, 0))
        rows.append([(f"{info['name']} — {fmt_num(cost)} 💰", f"buildf:{ftype}")])
    rows.append([("🔙 بازگشت", "menu:main")])
    render(chat_id, message_id, text, kb(rows))


def do_build_factory(chat_id, message_id, user_id, ftype):
    c = require_country(user_id)
    if not c:
        return
    ok, res = build_factory(c["id"], ftype)
    if ok:
        show_factory_menu(chat_id, message_id, user_id)
    else:
        render(chat_id, message_id, f"⛔ {res}", back_kb("menu:factory"))


# --------------------------------------------------------------------- ارتش

CATEGORY_FA = {"ground": "🪖 زمینی", "air": "✈️ هوایی", "navy": "🚢 دریایی", "missile": "🚀 موشکی"}


def show_army_menu(chat_id, message_id, user_id):
    c = require_country(user_id)
    if not c:
        return
    text = f"🪖 <b>ارتش {c['name']}</b>\nدسته‌ی موردنظر رو انتخاب کن:"
    rows = [[(CATEGORY_FA[cat], f"armycat:{cat}")] for cat in UNIT_CATEGORIES]
    rows.append([("🔙 بازگشت", "menu:main")])
    render(chat_id, message_id, text, kb(rows))


def show_army_category(chat_id, message_id, user_id, cat):
    c = require_country(user_id)
    if not c:
        return
    army = get_army(c["id"])
    lines = [f"{CATEGORY_FA[cat]} — موجودی و خرید\n"]
    rows = []
    for key in UNIT_CATEGORIES[cat]:
        u = ALL_UNITS[key]
        qty = army.get(key, 0)
        lines.append(f"{u['name']}: {qty} عدد (قیمت واحد {fmt_num(u['cost'])})")
        rows.append([(f"🛒 خرید {u['name']}", f"buyunit:{key}")])
    rows.append([("🔙 بازگشت", "menu:army")])
    render(chat_id, message_id, "\n".join(lines), kb(rows))


def ask_unit_quantity(chat_id, message_id, user_id, unit_key):
    c = require_country(user_id)
    if not c:
        return
    u = ALL_UNITS[unit_key]
    AWAITING[user_id] = {"action": "buy_unit", "unit_key": unit_key, "chat_id": chat_id}
    text = (
        f"🛒 خرید {u['name']}\n"
        f"قیمت واحد: {fmt_num(u['cost'])} 💰\n"
        f"خزانه‌ی تو: {fmt_num(c['treasury'])} 💰\n\n"
        "چند عدد می‌خوای بخری؟ فقط عدد رو بفرست (یا برای انصراف /cancel بزن)."
    )
    render(chat_id, message_id, text, back_kb("menu:army"))


def do_buy_unit(chat_id, user_id, unit_key, qty):
    c = require_country(user_id)
    if not c:
        return
    ok, res = buy_unit(c["id"], unit_key, qty)
    if ok:
        send_message(chat_id, f"✅ {qty} عدد {ALL_UNITS[unit_key]['name']} خریداری شد. هزینه: {fmt_num(res)}")
    else:
        send_message(chat_id, f"⛔ {res}")


# -------------------------------------------------------------------- دفاع

def show_defense(chat_id, message_id, user_id):
    c = require_country(user_id)
    if not c:
        return
    army = get_army(c["id"])
    defense_units = {k: v for k, v in army.items() if k in ("air_defense", "main_tank", "heavy_tank", "air_defense_missile")}
    lines = [
        f"🛡️ <b>دفاع {c['name']}</b>\n",
        f"❤️ سلامت کشور: {fmt_num(c['hp'])}/{fmt_num(c['max_hp'])}",
        f"🪖 روحیه: {fmt_num(c['morale'])}%\n",
        "واحدهای دفاعی کلیدی:",
    ]
    for k, v in defense_units.items():
        lines.append(f"{ALL_UNITS[k]['name']}: {v}")
    if not defense_units:
        lines.append("هنوز واحد دفاعی خاصی نساختی؛ از بخش ارتش تانک/پدافند بخر.")
    render(chat_id, message_id, "\n".join(lines), back_kb())


# ------------------------------------------------------------------- فناوری

def show_tech_menu(chat_id, message_id, user_id):
    c = require_country(user_id)
    if not c:
        return
    levels = get_all_tech(c["id"])
    active = active_research(c["id"])
    lines = [f"🔬 <b>فناوری {c['name']}</b>\n"]
    rows = []
    for key, info in TECH_TREE.items():
        lvl = levels[key]
        lines.append(f"{info['name']}: سطح {lvl}/{info['max_level']}")
        cost = research_cost(key, lvl)
        rows.append([(f"🔍 تحقیق {info['name']} ({fmt_num(cost)}💰)", f"research:{key}")])
    if active and active["finishes_at"] > int(time.time()):
        remaining = active["finishes_at"] - int(time.time())
        lines.append(f"\n⏳ تحقیق «{TECH_TREE[active['tech_key']]['name']}» در حال انجام — {remaining//60} دقیقه مانده.")
    rows.append([("🔙 بازگشت", "menu:main")])
    render(chat_id, message_id, "\n".join(lines), kb(rows))


def do_research(chat_id, message_id, user_id, tech_key):
    c = require_country(user_id)
    if not c:
        return
    ok, res = start_research(c["id"], tech_key)
    if ok:
        render(chat_id, message_id, "✅ تحقیق شروع شد.", back_kb("menu:tech"))
    else:
        render(chat_id, message_id, f"⛔ {res}", back_kb("menu:tech"))


# ------------------------------------------------------------------ جاسوسی

def show_spy_menu(chat_id, message_id, user_id, page=0):
    c = require_country(user_id)
    if not c:
        return
    others = [x for x in list_taken_countries() if x["id"] != c["id"]]
    per_page = 8
    chunk = others[page*per_page:(page+1)*per_page]
    rows = [[(f"{o['flag']} {o['name']}", f"spytarget:{o['id']}")] for o in chunk]
    nav = []
    if page > 0:
        nav.append(("⬅️", f"spypage:{page-1}"))
    if (page+1)*per_page < len(others):
        nav.append(("➡️", f"spypage:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([("🔙 بازگشت", "menu:main")])
    render(chat_id, message_id, "🕵️ کشور هدف رو برای عملیات جاسوسی انتخاب کن:", kb(rows))


def show_spy_actions(chat_id, message_id, user_id, target_id):
    c = require_country(user_id)
    t = get_country(target_id)
    if not c or not t:
        return
    lines = [f"🕵️ عملیات علیه {t['flag']} {t['name']}\n"]
    rows = []
    for key, act in ACTIONS.items():
        lines.append(f"{act['name']} — هزینه {fmt_num(act['cost'])}💰")
        rows.append([(act["name"], f"spyact:{target_id}:{key}")])
    rows.append([("🔙 بازگشت", "menu:spy")])
    render(chat_id, message_id, "\n".join(lines), kb(rows))


def do_spy_action(chat_id, message_id, user_id, target_id, action_key):
    c = require_country(user_id)
    if not c:
        return
    success, result = perform_action(c["id"], target_id, action_key)
    t = get_country(target_id)
    if success:
        lines = [f"✅ عملیات «{ACTIONS[action_key]['name']}» موفق بود.\n"]
        if "army" in result:
            lines.append("🪖 ارتش هدف:")
            for k, v in result["army"].items():
                lines.append(f"  {ALL_UNITS[k]['name']}: {v}")
        if "economy" in result:
            lines.append("💰 اقتصاد هدف:")
            for k, v in result["economy"].items():
                lines.append(f"  {k}: {fmt_num(v)}")
        if "damage_pct" in result:
            lines.append(f"💥 {result['damage_pct']}٪ به خزانه‌ی هدف آسیب زده شد.")
        text = "\n".join(lines)
    else:
        text = "❌ عملیات جاسوسی شکست خورد."
    render(chat_id, message_id, text, back_kb("menu:spy"))


# ---------------------------------------------------------------- دیپلماسی

DIPLO_KINDS_FA = REQUEST_KINDS


def show_diplomacy_menu(chat_id, message_id, user_id, page=0):
    c = require_country(user_id)
    if not c:
        return
    pending = pending_requests_for(c["id"])
    lines = ["🤝 <b>دیپلماسی</b>\n"]
    rows = []
    if pending:
        lines.append("📨 درخواست‌های در انتظار پاسخ:")
        for p in pending:
            frm = get_country(p["from_id"])
            lines.append(f"  {frm['flag']} {frm['name']} — {DIPLO_KINDS_FA[p['kind']]}")
            rows.append([
                (f"✅ قبول ({frm['name']})", f"diploresp:{p['id']}:1"),
                (f"❌ رد ({frm['name']})", f"diploresp:{p['id']}:0"),
            ])
    others = [x for x in list_taken_countries() if x["id"] != c["id"]]
    per_page = 6
    chunk = others[page*per_page:(page+1)*per_page]
    for o in chunk:
        rel = get_relation(c["id"], o["id"])
        rows.append([(f"{o['flag']} {o['name']} ({rel})", f"diplotarget:{o['id']}")])
    nav = []
    if page > 0:
        nav.append(("⬅️", f"diplopage:{page-1}"))
    if (page+1)*per_page < len(others):
        nav.append(("➡️", f"diplopage:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([("🔙 بازگشت", "menu:main")])
    render(chat_id, message_id, "\n".join(lines), kb(rows))


def show_diplomacy_actions(chat_id, message_id, user_id, target_id):
    c = require_country(user_id)
    t = get_country(target_id)
    if not c or not t:
        return
    rel = get_relation(c["id"], target_id)
    text = f"🤝 روابط با {t['flag']} {t['name']}: <b>{rel}</b>"
    rows = [
        [("🤝 درخواست اتحاد", f"diploreq:{target_id}:alliance")],
        [("📜 پیمان عدم‌تجاوز", f"diploreq:{target_id}:non_aggression")],
        [("🕊️ پیشنهاد صلح", f"diploreq:{target_id}:peace")],
        [("🚢 پیمان تجاری", f"diploreq:{target_id}:trade_pact")],
        [("💵 کمک مالی", f"aidstart:{target_id}")],
        [("💔 قطع رابطه", f"diplobreak:{target_id}")],
        [("⚔️ اعلان جنگ", f"wartarget:{target_id}")],
        [("🔙 بازگشت", "menu:diplomacy")],
    ]
    render(chat_id, message_id, text, kb(rows))


def do_diplo_request(chat_id, message_id, user_id, target_id, kind):
    c = require_country(user_id)
    if not c:
        return
    ok, res = send_request(c["id"], target_id, kind)
    text = "✅ درخواست ارسال شد." if ok else f"⛔ {res}"
    render(chat_id, message_id, text, back_kb("menu:diplomacy"))


def do_diplo_respond(chat_id, message_id, user_id, request_id, accept):
    ok, res = respond_request(request_id, bool(accept))
    text = "✅ پاسخ ثبت شد." if ok else f"⛔ {res}"
    render(chat_id, message_id, text, back_kb("menu:diplomacy"))


def do_diplo_break(chat_id, message_id, user_id, target_id):
    c = require_country(user_id)
    if not c:
        return
    break_relation(c["id"], target_id)
    render(chat_id, message_id, "💔 رابطه قطع شد.", back_kb("menu:diplomacy"))


def ask_aid_amount(chat_id, message_id, user_id, target_id):
    AWAITING[user_id] = {"action": "send_aid", "target_id": target_id, "chat_id": chat_id}
    render(chat_id, message_id, "💵 چه مقدار کمک مالی می‌خوای بفرستی؟ عدد رو بفرست.", back_kb("menu:diplomacy"))


def do_send_aid(chat_id, user_id, target_id, amount):
    c = require_country(user_id)
    if not c:
        return
    ok, res = send_aid(c["id"], target_id, amount)
    text = f"✅ {fmt_num(amount)} 💰 کمک مالی ارسال شد." if ok else f"⛔ {res}"
    send_message(chat_id, text)


# --------------------------------------------------------------------- جنگ

def show_war_menu(chat_id, message_id, user_id, page=0):
    c = require_country(user_id)
    if not c:
        return
    active_wars = query(
        "SELECT * FROM wars WHERE status='active' AND (attacker_id=? OR defender_id=?)",
        (c["id"], c["id"]),
    )
    lines = ["⚔️ <b>جنگ</b>\n"]
    rows = []
    if active_wars:
        lines.append("🔥 جنگ‌های فعال:")
        for w in active_wars:
            other_id = w["defender_id"] if w["attacker_id"] == c["id"] else w["attacker_id"]
            other = get_country(other_id)
            lines.append(f"  در حال جنگ با {other['flag']} {other['name']}")
            rows.append([(f"💥 حمله به {other['name']}", f"battle:{w['id']}")])
    others = [x for x in list_taken_countries() if x["id"] != c["id"]]
    per_page = 6
    chunk = others[page*per_page:(page+1)*per_page]
    for o in chunk:
        rel = get_relation(c["id"], o["id"])
        if rel != "war":
            rows.append([(f"⚔️ اعلان جنگ به {o['flag']} {o['name']}", f"wartarget:{o['id']}")])
    nav = []
    if page > 0:
        nav.append(("⬅️", f"warpage:{page-1}"))
    if (page+1)*per_page < len(others):
        nav.append(("➡️", f"warpage:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([("🔙 بازگشت", "menu:main")])
    render(chat_id, message_id, "\n".join(lines), kb(rows))


def confirm_war(chat_id, message_id, user_id, target_id):
    c = require_country(user_id)
    t = get_country(target_id)
    if not c or not t:
        return
    rel = get_relation(c["id"], target_id)
    if rel == "alliance":
        render(chat_id, message_id, "⛔ نمی‌تونی به متحدت اعلان جنگ بدی؛ اول باید اتحاد رو بشکنی.", back_kb("menu:war"))
        return
    text = f"⚠️ آیا مطمئنی می‌خوای به {t['flag']} {t['name']} اعلان جنگ بدی؟"
    render(chat_id, message_id, text, confirm_kb(f"declarewar:{target_id}", "menu:war"))


def do_declare_war(chat_id, message_id, user_id, target_id):
    c = require_country(user_id)
    if not c:
        return
    ok, res = declare_war(c["id"], target_id)
    text = "⚔️ جنگ اعلام شد!" if ok else f"⛔ {res}"
    render(chat_id, message_id, text, back_kb("menu:war"))


def do_battle_round(chat_id, message_id, user_id, war_id):
    c = require_country(user_id)
    war = query_one("SELECT * FROM wars WHERE id=?", (war_id,))
    if not c or not war or c["id"] not in (war["attacker_id"], war["defender_id"]):
        return
    result = resolve_battle(war_id)
    if not result:
        render(chat_id, message_id, "این جنگ دیگه فعال نیست.", back_kb("menu:war"))
        return
    lines = [
        "💥 <b>نتیجه‌ی نبرد</b>",
        f"آسیب به مدافع: {fmt_num(result['dmg_to_defender'])}",
        f"آسیب به مهاجم: {fmt_num(result['dmg_to_attacker'])}",
    ]
    if result["ended"]:
        lines.append(f"🏁 جنگ به پایان رسید. برنده: {result['winner']}")
        rows = [[("🔙 بازگشت", "menu:war")]]
    else:
        rows = [[("💥 حمله دوباره", f"battle:{war_id}")], [("🔙 بازگشت", "menu:war")]]
    render(chat_id, message_id, "\n".join(lines), kb(rows))


# ------------------------------------------------------------------- سرزمین

def show_territory_menu(chat_id, message_id, user_id):
    c = require_country(user_id)
    if not c:
        return
    owned = list_owned(c["id"])
    lines = [f"🗺️ <b>سرزمین‌های {c['name']}</b>\n"]
    for t in owned:
        tag = "🌊 (تنگه استراتژیک)" if t["is_strait"] else ""
        lines.append(f"• {t['name']} {tag} — ارزش اقتصادی: {fmt_num(t['economic_value'])}")
    if not owned:
        lines.append("هنوز سرزمینی نداری.")
    straits = list_straits()
    lines.append("\n🌊 <b>تنگه‌های استراتژیک جهان:</b>")
    for s in straits:
        owner_txt = "آزاد"
        if s["owner_id"]:
            oc = get_country(s["owner_id"])
            owner_txt = f"{oc['flag']} {oc['name']}"
        lines.append(f"• {s['name']} — مالک: {owner_txt}")
    render(chat_id, message_id, "\n".join(lines), back_kb())


# --------------------------------------------------------------------- تجارت

def show_trade_menu(chat_id, message_id, user_id):
    c = require_country(user_id)
    if not c:
        return
    market = get_market()
    lines = ["🚢 <b>بازار جهانی</b>\n"]
    rows = []
    for r in RESOURCES:
        m = market.get(r, {"price": RESOURCE_BASE_PRICE[r]})
        lines.append(f"{RESOURCE_FA[r]}: {m['price']:.1f} 💰 / واحد")
        rows.append([
            (f"🛒 خرید {RESOURCE_FA[r]}", f"buyres:{r}"),
            (f"💰 فروش {RESOURCE_FA[r]}", f"sellres:{r}"),
        ])
    rows.append([("🔙 بازگشت", "menu:main")])
    render(chat_id, message_id, "\n".join(lines), kb(rows))


def ask_trade_amount(chat_id, message_id, user_id, resource, action):
    AWAITING[user_id] = {"action": f"trade_{action}", "resource": resource, "chat_id": chat_id}
    label = "خرید" if action == "buy" else "فروش"
    render(chat_id, message_id, f"چه مقدار {RESOURCE_FA[resource]} می‌خوای {label} کنی؟ عدد رو بفرست.", back_kb("menu:trade"))


def do_trade(chat_id, user_id, resource, action, amount):
    c = require_country(user_id)
    if not c:
        return
    if action == "buy":
        ok, res = buy_resource(c["id"], resource, amount)
    else:
        ok, res = sell_resource(c["id"], resource, amount)
    if ok:
        send_message(chat_id, f"✅ معامله انجام شد. مبلغ: {fmt_num(res)} 💰")
    else:
        send_message(chat_id, f"⛔ {res}")


# --------------------------------------------------------------------- اخبار

def show_news(chat_id, message_id, user_id):
    news = latest_news(15)
    lines = ["📢 <b>اخبار جهانی</b>\n"]
    for n in news:
        lines.append(f"• {n['text']}")
    if not news:
        lines.append("هنوز خبری منتشر نشده.")
    render(chat_id, message_id, "\n".join(lines), back_kb())


def ask_statement(chat_id, message_id, user_id):
    AWAITING[user_id] = {"action": "statement", "chat_id": chat_id}
    render(chat_id, message_id, "📰 متن بیانیه‌ی رسمی کشورت رو بفرست تا در کانال بازی منتشر بشه.", back_kb("menu:settings"))


def do_publish_statement(chat_id, user_id, text_msg):
    c = require_country(user_id)
    if not c:
        return
    full = f"📰 <b>بیانیه‌ی رسمی {c['flag']} {c['name']}</b>\n\n{text_msg}"
    add_news(f"📰 {c['flag']} {c['name']} یک بیانیه‌ی رسمی منتشر کرد.")
    if NEWS_CHANNEL:
        send_to_channel(NEWS_CHANNEL, full)
    send_message(chat_id, "✅ بیانیه منتشر شد.")


# ----------------------------------------------------------------- رتبه‌بندی

def show_ranking_menu(chat_id, message_id, user_id):
    rows = [
        [("💰 ثروتمندترین", "rank:wealth"), ("🪖 قدرتمندترین ارتش", "rank:military")],
        [("🌍 بزرگ‌ترین قلمرو", "rank:territory"), ("🏭 صنعتی‌ترین", "rank:industry")],
        [("🚀 پیشرفته‌ترین", "rank:tech"), ("⚔️ بیشترین پیروزی", "rank:wins")],
        [("👑 رتبه کلی قدرت", "rank:overall")],
        [("🔙 بازگشت", "menu:main")],
    ]
    render(chat_id, message_id, "🏆 <b>رتبه‌بندی جهانی</b>\nیک دسته رو انتخاب کن:", kb(rows))


def show_ranking(chat_id, message_id, user_id, rtype):
    lines = ["🏆 <b>نتایج رتبه‌بندی</b>\n"]
    if rtype == "wealth":
        for i, c in enumerate(top_wealth(), 1):
            lines.append(f"{i}. {c['flag']} {c['name']} — {fmt_num(c['treasury'])} 💰")
    elif rtype == "military":
        for i, (c, p) in enumerate(top_military(), 1):
            lines.append(f"{i}. {c['flag']} {c['name']} — قدرت {fmt_num(p)}")
    elif rtype == "territory":
        for i, (c, n) in enumerate(top_territory(), 1):
            lines.append(f"{i}. {c['flag']} {c['name']} — {n} منطقه")
    elif rtype == "industry":
        for i, row in enumerate(top_industry(), 1):
            c = get_country(row["country_id"])
            lines.append(f"{i}. {c['flag']} {c['name']} — {row['n']} کارخانه")
    elif rtype == "tech":
        for i, row in enumerate(top_tech(), 1):
            c = get_country(row["country_id"])
            lines.append(f"{i}. {c['flag']} {c['name']} — مجموع سطح {row['total']}")
    elif rtype == "wins":
        for i, c in enumerate(top_wins(), 1):
            lines.append(f"{i}. {c['flag']} {c['name']} — {c['wins']} پیروزی")
    elif rtype == "overall":
        for i, (c, s) in enumerate(top_overall_power(), 1):
            lines.append(f"{i}. {c['flag']} {c['name']} — امتیاز {fmt_num(s)}")
    if len(lines) == 1:
        lines.append("هنوز داده‌ای وجود نداره.")
    render(chat_id, message_id, "\n".join(lines), back_kb("menu:ranking"))


# --------------------------------------------------------------------- گزارش

def show_report(chat_id, message_id, user_id):
    c = require_country(user_id)
    if not c:
        return
    owner = get_user(c["owner_id"])
    active_wars = query(
        "SELECT * FROM wars WHERE status='active' AND (attacker_id=? OR defender_id=?)", (c["id"], c["id"])
    )
    allies = [x for x, s in relations_list(c["id"]) if s == "alliance"]
    enemies = [x for x, s in relations_list(c["id"]) if s == "war"]
    factories = list_factories(c["id"])
    text = (
        f"📊 <b>گزارش کامل {c['name']}</b>\n"
        f"👤 رهبر: {owner['username'] or owner['user_id']}\n"
        f"👥 جمعیت: {fmt_num(c['population'])}\n"
        f"💰 خزانه: {fmt_num(c['treasury'])}\n"
        f"📈 اقتصاد: {fmt_num(c['economy_score'])}\n"
        f"🗺️ قلمرو: {territory_count(c['id'])} منطقه\n"
        f"🪖 قدرت نظامی: {fmt_num(military_power(c['id']))}\n"
        f"🔬 فناوری: {sum(get_all_tech(c['id']).values())} سطح مجموع\n"
        f"🏭 تعداد کارخانه‌ها: {len(factories)}\n"
        f"⚔️ جنگ‌های فعال: {len(active_wars)}\n"
        f"🤝 متحدان: {len(allies)}\n"
        f"💢 دشمنان: {len(enemies)}\n"
    )
    render(chat_id, message_id, text, back_kb())


# -------------------------------------------------------------------- تنظیمات

def show_settings(chat_id, message_id, user_id):
    rows = [
        [("📰 انتشار بیانیه رسمی", "statement:new")],
        [("💰 مشاهده اقتصاد", "menu:economy")],
    ]
    if user_id in ADMIN_IDS:
        rows.append([("👑 پنل ادمین", "admin:main")])
    rows.append([("🔙 بازگشت", "menu:main")])
    render(chat_id, message_id, "⚙️ <b>تنظیمات کشور</b>", kb(rows))


# -------------------------------------------------------------------- فروشگاه

# -------------------------------------------------------------- سازمان ملل

def show_un_menu(chat_id, message_id, user_id):
    c = require_country(user_id)
    if not c:
        return
    member = is_member(c["id"])
    lines = [
        "🏛️ <b>سازمان ملل</b>",
        f"تعداد اعضا: {member_count()}",
        f"وضعیت تو: {'✅ عضو هستی' if member else '❌ عضو نیستی'}\n",
    ]
    rows = []
    if not member:
        rows.append([("🚪 عضویت در سازمان ملل", "un:join")])
    else:
        rows.append([("📜 پیشنهاد قطعنامه", "un:propose"), ("📅 برگزاری جلسه", "un:meeting")])
    active = list_active_resolutions()
    if active:
        lines.append("📜 <b>قطعنامه‌های در حال رای‌گیری:</b>")
        for r in active:
            counts = vote_counts(r["id"])
            lines.append(f"#{r['id']} «{r['title']}» — 👍{counts['yes']} 👎{counts['no']} 🤷{counts['abstain']}")
            if member:
                rows.append([
                    (f"👍 #{r['id']}", f"un:vote:{r['id']}:yes"),
                    (f"👎 #{r['id']}", f"un:vote:{r['id']}:no"),
                    (f"🤷 #{r['id']}", f"un:vote:{r['id']}:abstain"),
                ])
            if r["proposer_id"] == c["id"]:
                rows.append([(f"🔚 پایان رای‌گیری #{r['id']}", f"un:close:{r['id']}")])
    else:
        lines.append("فعلاً قطعنامه‌ی در حال رای‌گیری‌ای نیست.")
    rows.append([("🔙 بازگشت", "menu:main")])
    render(chat_id, message_id, "\n".join(lines), kb(rows))


def do_un_join(chat_id, message_id, user_id):
    c = require_country(user_id)
    if not c:
        return
    ok, res = join(c["id"])
    show_un_menu(chat_id, message_id, user_id)
    if not ok:
        send_message(chat_id, f"⛔ {res}")


def ask_un_propose(chat_id, message_id, user_id):
    AWAITING[user_id] = {"action": "un_propose", "chat_id": chat_id}
    render(chat_id, message_id,
           "📜 عنوان قطعنامه رو بفرست. اگه خواستی توضیح هم بدی، بعد از یک «|» بنویس.\n"
           "مثال: افزایش تعرفه‌ی نفت | برای تثبیت بازار جهانی",
           back_kb("menu:un"))


def do_un_propose(chat_id, user_id, text):
    c = require_country(user_id)
    if not c:
        return
    if "|" in text:
        title, desc = text.split("|", 1)
    else:
        title, desc = text, ""
    title = title.strip()[:80]
    ok, res = propose_resolution(c["id"], title, desc.strip())
    if ok:
        send_message(chat_id, "✅ قطعنامه ثبت شد و رای‌گیری شروع شد.")
    else:
        send_message(chat_id, f"⛔ {res}")


def ask_un_meeting(chat_id, message_id, user_id):
    AWAITING[user_id] = {"action": "un_meeting", "chat_id": chat_id}
    render(chat_id, message_id, "📅 موضوع جلسه‌ی سازمان ملل رو بفرست.", back_kb("menu:un"))


def do_un_meeting(chat_id, user_id, topic):
    c = require_country(user_id)
    if not c:
        return
    ok, res = hold_meeting(c["id"], topic.strip()[:100])
    send_message(chat_id, "✅ جلسه اعلام شد." if ok else f"⛔ {res}")


def do_un_vote(chat_id, message_id, user_id, resolution_id, choice):
    c = require_country(user_id)
    if not c:
        return
    ok, res = vote(resolution_id, c["id"], choice)
    show_un_menu(chat_id, message_id, user_id)
    if not ok:
        send_message(chat_id, f"⛔ {res}")


def do_un_close(chat_id, message_id, user_id, resolution_id):
    c = require_country(user_id)
    r = get_resolution(resolution_id)
    if not c or not r or r["proposer_id"] != c["id"]:
        return
    close_resolution(resolution_id)
    show_un_menu(chat_id, message_id, user_id)


# ------------------------------------------------------------------ اتحادها

def show_alliance_menu(chat_id, message_id, user_id):
    c = require_country(user_id)
    if not c:
        return
    a = get_alliance_of(c["id"])
    if a:
        members = list_members(a["id"])
        is_leader = a["leader_country_id"] == c["id"]
        lines = [f"🏰 <b>اتحاد «{a['name']}»</b>"]
        leader_c = get_country(a["leader_country_id"])
        lines.append(f"👑 لیدر: {leader_c['flag']} {leader_c['name']}")
        lines.append(f"👥 اعضا ({len(members)}):")
        for m in members:
            lines.append(f"  {m['flag']} {m['name']}")
        rows = []
        if is_leader:
            rows.append([("📢 پیام همگانی", "alliance:broadcast"), ("📅 برگزاری جلسه", "alliance:meeting")])
            pending = pending_requests_for_leader(a["id"])
            if pending:
                rows.append([(f"📋 درخواست‌های عضویت ({len(pending)})", "alliance:requests")])
        rows.append([("🚪 ترک اتحاد", "alliance:leave")])
        rows.append([("🔙 بازگشت", "menu:main")])
        render(chat_id, message_id, "\n".join(lines), kb(rows))
    else:
        alliances = list_alliances()
        lines = ["🏰 <b>اتحادها</b>\nتو عضو هیچ اتحادی نیستی.\n"]
        rows = [[("➕ ساخت اتحاد جدید", "alliance:create")]]
        if alliances:
            lines.append("اتحادهای موجود:")
            for al in alliances:
                leader_c = get_country(al["leader_country_id"])
                member_n = len(list_members(al["id"]))
                lines.append(f"«{al['name']}» — لیدر: {leader_c['flag']} {leader_c['name']} ({member_n} عضو)")
                rows.append([(f"🚪 درخواست عضویت در «{al['name']}»", f"alliance:join:{al['id']}")])
        rows.append([("🔙 بازگشت", "menu:main")])
        render(chat_id, message_id, "\n".join(lines), kb(rows))


def ask_alliance_create(chat_id, message_id, user_id):
    AWAITING[user_id] = {"action": "alliance_create", "chat_id": chat_id}
    render(chat_id, message_id, "🏰 اسم اتحادت رو بفرست (حداکثر ۳۰ کاراکتر).", back_kb("menu:alliance"))


def do_alliance_create(chat_id, user_id, name):
    c = require_country(user_id)
    if not c:
        return
    name = name.strip()
    if not name or len(name) > 30 or ":" in name:
        send_message(chat_id, "❗ اسم نامعتبره. دوباره امتحان کن یا /cancel بزن.")
        AWAITING[user_id] = {"action": "alliance_create", "chat_id": chat_id}
        return
    ok, res = create_alliance(c["id"], name)
    AWAITING.pop(user_id, None)
    send_message(chat_id, f"✅ اتحاد «{name}» ساخته شد و لیدرش تو هستی!" if ok else f"⛔ {res}")


def do_alliance_join_request(chat_id, message_id, user_id, alliance_id):
    c = require_country(user_id)
    if not c:
        return
    ok, res = request_join(c["id"], alliance_id)
    text = "✅ درخواست عضویت ارسال شد؛ منتظر تایید لیدر باش." if ok else f"⛔ {res}"
    render(chat_id, message_id, text, back_kb("menu:alliance"))


def show_alliance_requests(chat_id, message_id, user_id):
    c = require_country(user_id)
    if not c:
        return
    a = get_alliance_of(c["id"])
    if not a or a["leader_country_id"] != c["id"]:
        return
    pending = pending_requests_for_leader(a["id"])
    lines = ["📋 <b>درخواست‌های عضویت</b>\n"]
    rows = []
    for p in pending:
        pc = get_country(p["country_id"])
        lines.append(f"{pc['flag']} {pc['name']}")
        rows.append([
            (f"✅ قبول {pc['name']}", f"alliance:reqresp:{p['id']}:1"),
            (f"❌ رد {pc['name']}", f"alliance:reqresp:{p['id']}:0"),
        ])
    if not pending:
        lines.append("درخواستی در انتظار نیست.")
    rows.append([("🔙 بازگشت", "menu:alliance")])
    render(chat_id, message_id, "\n".join(lines), kb(rows))


def do_alliance_request_response(chat_id, message_id, user_id, request_id, accept):
    c = require_country(user_id)
    if not c:
        return
    ok, res = respond_join_request(request_id, bool(accept))
    show_alliance_requests(chat_id, message_id, user_id)
    if not ok:
        send_message(chat_id, f"⛔ {res}")


def do_alliance_leave(chat_id, message_id, user_id):
    c = require_country(user_id)
    if not c:
        return
    ok, res = leave_alliance(c["id"])
    render(chat_id, message_id, res, back_kb("menu:main"))


def ask_alliance_broadcast(chat_id, message_id, user_id):
    AWAITING[user_id] = {"action": "alliance_broadcast", "chat_id": chat_id}
    render(chat_id, message_id, "📢 متن پیام همگانی برای اعضای اتحادت رو بفرست.", back_kb("menu:alliance"))


def do_alliance_broadcast(chat_id, user_id, text):
    c = require_country(user_id)
    if not c:
        return
    ok, res = broadcast_to_alliance(c["id"], text)
    send_message(chat_id, f"✅ پیام برای {res} عضو ارسال شد." if ok else f"⛔ {res}")


def ask_alliance_meeting(chat_id, message_id, user_id):
    AWAITING[user_id] = {"action": "alliance_meeting", "chat_id": chat_id}
    render(chat_id, message_id, "📅 موضوع جلسه‌ی اتحاد رو بفرست.", back_kb("menu:alliance"))


def do_alliance_meeting(chat_id, user_id, topic):
    c = require_country(user_id)
    if not c:
        return
    ok, res = hold_alliance_meeting(c["id"], topic.strip()[:100])
    send_message(chat_id, "✅ جلسه اعلام شد." if ok else f"⛔ {res}")



def pack_contents_text(pack):
    """توضیح محتوای یک پک به‌صورت متن خوانا، مثلاً 'سرباز x100، تانک اصلی x8'."""
    if "units" in pack:
        parts = [f"{ALL_UNITS[k]['name']} x{q}" for k, q in pack["units"].items()]
        return "، ".join(parts)
    if "cash" in pack:
        return f"💰 {pack['cash']:,} واحد پول نقد مستقیم به خزانه"
    return ""


def show_shop_menu(chat_id, message_id, user_id):
    lines = [
        "🛒 <b>فروشگاه ویژه</b>\n",
        f"با خرید هر پک ({PACK_PRICE_TOMAN:,} تومان)، تجهیزات یا پول نقد مستقیم به کشورت اضافه می‌شه.\n",
    ]
    rows = []
    for key, pack in PACKS.items():
        lines.append(f"{pack['name']}: {pack_contents_text(pack)}")
        rows.append([(f"{pack['name']} — {PACK_PRICE_TOMAN:,} تومان", f"buypack:{key}")])
    rows.append([("🔙 بازگشت", "menu:main")])
    render(chat_id, message_id, "\n".join(lines), kb(rows))


def do_buy_pack(chat_id, message_id, user_id, pack_key):
    start_pack_purchase(chat_id, user_id, pack_key)


def ask_custom_country_name(chat_id, message_id, user_id):
    existing = get_country_by_owner(user_id)
    if existing:
        render(chat_id, message_id, f"⛔ تو همین الان کشور {existing['flag']} {existing['name']} رو داری.",
               back_kb("menu:main"))
        return
    AWAITING[user_id] = {"action": "custom_country_name", "chat_id": chat_id}
    render(chat_id, message_id,
           "🎨 اسم کشور اختصاصیت رو بفرست (حداکثر ۲۴ کاراکتر). این کشور کاملاً رایگانه!",
           back_kb("menu:reselect"))


def do_custom_country_name(chat_id, user_id, name):
    name = name.strip()
    if not name or len(name) > 24 or ":" in name or "\n" in name:
        send_message(chat_id, "❗ اسم نامعتبره (حداکثر ۲۴ کاراکتر، بدون «:» یا خط جدید). دوباره امتحان کن یا /cancel بزن.")
        AWAITING[user_id] = {"action": "custom_country_name", "chat_id": chat_id}
        return
    AWAITING.pop(user_id, None)
    ok, res = create_and_assign_custom_country(name, user_id)
    if ok:
        c = res
        add_news(f"🎨 یک بازیکن کشور اختصاصی «{c['name']}» را ساخت.", category="ownership_change")
        send_message(chat_id, f"✅ کشور اختصاصی «{c['name']}» ساخته شد و از همین الان مال توئه!")
        send_main_menu(chat_id, c)
    else:
        send_message(chat_id, f"⛔ {res}")


# ------------------------------------------------------------------ Dispatch

def handle_callback(chat_id, message_id, user_id, username, cb_data, callback_id):
    ensure_user(user_id, username)
    u = get_user(user_id)
    if u and u["is_banned"]:
        answer_callback_query(callback_id, "🚫 شما مسدود شده‌اید.", True)
        return

    parts = cb_data.split(":")
    action = parts[0]
    answer_callback_query(callback_id)

    if action == "admin":
        handle_admin_callback(chat_id, message_id, user_id, cb_data)
        return

    if action == "selpage":
        render(chat_id, message_id, "🌍 کشور موردنظر رو انتخاب کن:", country_list_kb(int(parts[1])))
    elif action == "seltaken":
        show_taken_countries(chat_id, message_id)
    elif action == "selcountry":
        confirm_country_selection(chat_id, message_id, user_id, int(parts[1]))
    elif action == "confirmsel":
        do_select_country(chat_id, message_id, user_id, username, int(parts[1]))
    elif cb_data == "menu:reselect" or cb_data == "menu:main_or_select":
        send_country_selection(chat_id, 0)
    elif cb_data == "menu:main":
        c = require_country(user_id)
        if c:
            send_main_menu(chat_id, c, message_id)
        else:
            send_country_selection(chat_id, 0)
    elif cb_data == "menu:info":
        show_info(chat_id, message_id, user_id)
    elif cb_data == "menu:economy":
        show_economy(chat_id, message_id, user_id)
    elif action == "tax":
        adjust_tax(user_id, parts[1]); show_economy(chat_id, message_id, user_id)
    elif action == "milb":
        adjust_budget(user_id, "military_budget_pct", parts[1]); show_economy(chat_id, message_id, user_id)
    elif action == "resb":
        adjust_budget(user_id, "research_budget_pct", parts[1]); show_economy(chat_id, message_id, user_id)
    elif cb_data == "menu:resources":
        show_resources(chat_id, message_id, user_id)
    elif cb_data == "menu:factory":
        show_factory_menu(chat_id, message_id, user_id)
    elif action == "buildf":
        do_build_factory(chat_id, message_id, user_id, parts[1])
    elif cb_data == "menu:army":
        show_army_menu(chat_id, message_id, user_id)
    elif action == "armycat":
        show_army_category(chat_id, message_id, user_id, parts[1])
    elif action == "buyunit":
        ask_unit_quantity(chat_id, message_id, user_id, parts[1])
    elif cb_data == "menu:defense":
        show_defense(chat_id, message_id, user_id)
    elif cb_data == "menu:tech":
        show_tech_menu(chat_id, message_id, user_id)
    elif action == "research":
        do_research(chat_id, message_id, user_id, parts[1])
    elif cb_data == "menu:spy":
        show_spy_menu(chat_id, message_id, user_id)
    elif action == "spypage":
        show_spy_menu(chat_id, message_id, user_id, int(parts[1]))
    elif action == "spytarget":
        show_spy_actions(chat_id, message_id, user_id, int(parts[1]))
    elif action == "spyact":
        do_spy_action(chat_id, message_id, user_id, int(parts[1]), parts[2])
    elif cb_data == "menu:diplomacy":
        show_diplomacy_menu(chat_id, message_id, user_id)
    elif action == "diplopage":
        show_diplomacy_menu(chat_id, message_id, user_id, int(parts[1]))
    elif action == "diplotarget":
        show_diplomacy_actions(chat_id, message_id, user_id, int(parts[1]))
    elif action == "diploreq":
        do_diplo_request(chat_id, message_id, user_id, int(parts[1]), parts[2])
    elif action == "diploresp":
        do_diplo_respond(chat_id, message_id, user_id, int(parts[1]), int(parts[2]))
    elif action == "diplobreak":
        do_diplo_break(chat_id, message_id, user_id, int(parts[1]))
    elif action == "aidstart":
        ask_aid_amount(chat_id, message_id, user_id, int(parts[1]))
    elif cb_data == "menu:war":
        show_war_menu(chat_id, message_id, user_id)
    elif action == "warpage":
        show_war_menu(chat_id, message_id, user_id, int(parts[1]))
    elif action == "wartarget":
        confirm_war(chat_id, message_id, user_id, int(parts[1]))
    elif action == "declarewar":
        do_declare_war(chat_id, message_id, user_id, int(parts[1]))
    elif action == "battle":
        do_battle_round(chat_id, message_id, user_id, int(parts[1]))
    elif cb_data == "menu:territory":
        show_territory_menu(chat_id, message_id, user_id)
    elif cb_data == "menu:trade":
        show_trade_menu(chat_id, message_id, user_id)
    elif action == "buyres":
        ask_trade_amount(chat_id, message_id, user_id, parts[1], "buy")
    elif action == "sellres":
        ask_trade_amount(chat_id, message_id, user_id, parts[1], "sell")
    elif cb_data == "menu:news":
        show_news(chat_id, message_id, user_id)
    elif cb_data == "statement:new":
        ask_statement(chat_id, message_id, user_id)
    elif cb_data == "menu:ranking":
        show_ranking_menu(chat_id, message_id, user_id)
    elif action == "rank":
        show_ranking(chat_id, message_id, user_id, parts[1])
    elif cb_data == "menu:report":
        show_report(chat_id, message_id, user_id)
    elif cb_data == "menu:settings":
        show_settings(chat_id, message_id, user_id)
    elif cb_data == "menu:shop":
        show_shop_menu(chat_id, message_id, user_id)
    elif action == "buypack":
        do_buy_pack(chat_id, message_id, user_id, parts[1])
    elif action == "buyvipcountry":
        do_start_vip_purchase(chat_id, message_id, user_id, int(parts[1]))
    elif action == "paidclaim":
        claim_manual_payment(chat_id, user_id, int(parts[1]))
    elif cb_data == "customcountry:new":
        ask_custom_country_name(chat_id, message_id, user_id)
    elif cb_data == "menu:un":
        show_un_menu(chat_id, message_id, user_id)
    elif cb_data == "un:join":
        do_un_join(chat_id, message_id, user_id)
    elif cb_data == "un:propose":
        ask_un_propose(chat_id, message_id, user_id)
    elif cb_data == "un:meeting":
        ask_un_meeting(chat_id, message_id, user_id)
    elif action == "un" and parts[1] == "vote":
        do_un_vote(chat_id, message_id, user_id, int(parts[2]), parts[3])
    elif action == "un" and parts[1] == "close":
        do_un_close(chat_id, message_id, user_id, int(parts[2]))
    elif cb_data == "menu:alliance":
        show_alliance_menu(chat_id, message_id, user_id)
    elif cb_data == "alliance:create":
        ask_alliance_create(chat_id, message_id, user_id)
    elif action == "alliance" and parts[1] == "join":
        do_alliance_join_request(chat_id, message_id, user_id, int(parts[2]))
    elif cb_data == "alliance:requests":
        show_alliance_requests(chat_id, message_id, user_id)
    elif action == "alliance" and parts[1] == "reqresp":
        do_alliance_request_response(chat_id, message_id, user_id, int(parts[2]), int(parts[3]))
    elif cb_data == "alliance:leave":
        do_alliance_leave(chat_id, message_id, user_id)
    elif cb_data == "alliance:broadcast":
        ask_alliance_broadcast(chat_id, message_id, user_id)
    elif cb_data == "alliance:meeting":
        ask_alliance_meeting(chat_id, message_id, user_id)
    else:
        pass


def handle_photo(chat_id, user_id, username, file_id):
    ensure_user(user_id, username)
    pending = AWAITING.get(user_id)
    if pending and pending.get("action") == "admin_set_event_image":
        handle_admin_photo(chat_id, user_id, pending, file_id)
        AWAITING.pop(user_id, None)


def handle_text(chat_id, user_id, username, text):
    ensure_user(user_id, username)
    u = get_user(user_id)
    if u and u["is_banned"]:
        return

    text = (text or "").strip()

    if text == "/start":
        cmd_start(chat_id, user_id, username)
        return
    if text == "/cancel":
        AWAITING.pop(user_id, None)
        send_message(chat_id, "لغو شد.")
        return
    if text == "/admin":
        if user_id in ADMIN_IDS:
            send_admin_panel(chat_id)
        return
    if text == "/menu":
        c = require_country(user_id)
        if c:
            send_main_menu(chat_id, c)
        else:
            send_country_selection(chat_id, 0)
        return

    pending = AWAITING.get(user_id)
    if not pending:
        # پیام آزاد بدون فلو فعال
        c = require_country(user_id)
        if c:
            send_message(chat_id, "برای دیدن پنل کشور /menu رو بزن.")
        else:
            send_message(chat_id, "برای شروع بازی /start رو بزن.")
        return

    action = pending["action"]
    try:
        if action == "buy_unit":
            qty = int(text)
            if qty <= 0:
                raise ValueError
            do_buy_unit(chat_id, user_id, pending["unit_key"], qty)
        elif action == "send_aid":
            amount = float(text)
            if amount <= 0:
                raise ValueError
            do_send_aid(chat_id, user_id, pending["target_id"], amount)
        elif action == "trade_buy":
            amount = float(text)
            if amount <= 0:
                raise ValueError
            do_trade(chat_id, user_id, pending["resource"], "buy", amount)
        elif action == "trade_sell":
            amount = float(text)
            if amount <= 0:
                raise ValueError
            do_trade(chat_id, user_id, pending["resource"], "sell", amount)
        elif action == "statement":
            do_publish_statement(chat_id, user_id, text)
        elif action == "custom_country_name":
            do_custom_country_name(chat_id, user_id, text)
        elif action == "un_propose":
            do_un_propose(chat_id, user_id, text)
        elif action == "un_meeting":
            do_un_meeting(chat_id, user_id, text)
        elif action == "alliance_create":
            do_alliance_create(chat_id, user_id, text)
        elif action == "alliance_broadcast":
            do_alliance_broadcast(chat_id, user_id, text)
        elif action == "alliance_meeting":
            do_alliance_meeting(chat_id, user_id, text)
        elif action.startswith("admin_"):
            handle_admin_text(chat_id, user_id, action, pending, text)
    except ValueError:
        send_message(chat_id, "❗ لطفاً یک عدد معتبر بفرست (یا /cancel برای انصراف).")
        return
    finally:
        self_managed = action.startswith("admin_") or action in ("custom_country_name", "alliance_create")
        if user_id in AWAITING and not self_managed:
            AWAITING.pop(user_id, None)
        elif action.startswith("admin_"):
            pass  # پنل ادمین خودش AWAITING رو مدیریت می‌کنه

# ======================================================================
# بخش برگرفته از: admin.py
# ======================================================================
# -*- coding: utf-8 -*-
"""پنل مدیریت کامل ادمین."""
import shutil
import time



def is_admin(user_id):
    return user_id in ADMIN_IDS


def send_admin_panel(chat_id, message_id=None):
    text = "👑 <b>پنل مدیریت</b>\nیکی از بخش‌ها رو انتخاب کن:"
    rows = [
        [("🌍 مدیریت کشورها", "admin:countries"), ("👥 بازیکنان", "admin:players")],
        [("⚔️ جنگ‌ها", "admin:wars"), ("🤝 روابط/اتحادها", "admin:relations")],
        [("📰 ارسال خبر", "admin:sendnews"), ("📢 پیام همگانی", "admin:broadcast")],
        [("🎲 رویداد جهانی", "admin:event"), ("📊 آمار بازی", "admin:stats")],
        [("📜 لاگ فعالیت‌ها", "admin:logs"), ("💾 پشتیبان دیتابیس", "admin:backup")],
        [("🎖️ کشورهای ویژه (مالک/ادمین)", "admin:special")],
        [("🖼️ عکس رویدادها", "admin:eventimages")],
        [("🔄 ریست فصل", "admin:resetseason")],
        [("🔙 بازگشت به بازی", "menu:main")],
    ]
    render(chat_id, message_id, text, kb(rows))


def handle_admin_callback(chat_id, message_id, user_id, cb_data):
    if not is_admin(user_id):
        render(chat_id, message_id, "⛔ فقط ادمین به این بخش دسترسی داره.", back_kb("menu:main"))
        return
    parts = cb_data.split(":")
    sub = parts[1] if len(parts) > 1 else "main"

    if sub == "main":
        send_admin_panel(chat_id, message_id)
    elif sub == "countries":
        show_countries_admin(chat_id, message_id, int(parts[2]) if len(parts) > 2 else 0)
    elif sub == "country":
        show_country_admin(chat_id, message_id, int(parts[2]))
    elif sub == "free":
        cid = int(parts[2])
        execute("UPDATE countries SET owner_id=NULL WHERE id=?", (cid,))
        execute("UPDATE users SET country_id=NULL WHERE country_id=?", (cid,))
        render(chat_id, message_id, "✅ کشور آزاد شد.", back_kb(f"admin:country:{cid}"))
    elif sub == "transfer":
        cid = int(parts[2])
        AWAITING[user_id] = {"action": "admin_transfer", "country_id": cid, "chat_id": chat_id}
        render(chat_id, message_id, "آیدی عددی مالک جدید رو بفرست:", back_kb(f"admin:country:{cid}"))
    elif sub == "settreasury":
        cid = int(parts[2])
        AWAITING[user_id] = {"action": "admin_settreasury", "country_id": cid, "chat_id": chat_id}
        render(chat_id, message_id, "مقدار جدید خزانه رو بفرست:", back_kb(f"admin:country:{cid}"))
    elif sub == "setres":
        cid = int(parts[2])
        rows = [[(RESOURCE_FA[r], f"admin:setres2:{cid}:{r}")] for r in RESOURCES]
        rows.append([("🔙 بازگشت", f"admin:country:{cid}")])
        render(chat_id, message_id, "کدوم منبع رو تغییر بدم؟", kb(rows))
    elif sub == "setres2":
        cid, res = int(parts[2]), parts[3]
        AWAITING[user_id] = {"action": "admin_setres", "country_id": cid, "resource": res, "chat_id": chat_id}
        render(chat_id, message_id, f"مقدار جدید {RESOURCE_FA[res]} رو بفرست:", back_kb(f"admin:country:{cid}"))
    elif sub == "setunit":
        cid = int(parts[2])
        rows = []
        for cat, keys in UNIT_CATEGORIES.items():
            for k in keys:
                rows.append([(ALL_UNITS[k]["name"], f"admin:setunit2:{cid}:{k}")])
        rows.append([("🔙 بازگشت", f"admin:country:{cid}")])
        render(chat_id, message_id, "کدوم واحد رو تغییر بدم؟ (پیمایش کن)", kb(rows[:25] + rows[-1:]))
    elif sub == "setunit2":
        cid, key = int(parts[2]), parts[3]
        AWAITING[user_id] = {"action": "admin_setunit", "country_id": cid, "unit_key": key, "chat_id": chat_id}
        render(chat_id, message_id, f"تعداد جدید {ALL_UNITS[key]['name']} رو بفرست:", back_kb(f"admin:country:{cid}"))
    elif sub == "sethp":
        cid = int(parts[2])
        AWAITING[user_id] = {"action": "admin_sethp", "country_id": cid, "chat_id": chat_id}
        render(chat_id, message_id, "مقدار جدید سلامت کشور (HP) رو بفرست:", back_kb(f"admin:country:{cid}"))
    elif sub == "delete":
        cid = int(parts[2])
        execute("UPDATE countries SET active=0, owner_id=NULL WHERE id=?", (cid,))
        render(chat_id, message_id, "✅ کشور غیرفعال شد (حذف نرم).", back_kb("admin:countries"))
    elif sub == "activate":
        cid = int(parts[2])
        execute("UPDATE countries SET active=1 WHERE id=?", (cid,))
        render(chat_id, message_id, "✅ کشور فعال شد.", back_kb(f"admin:country:{cid}"))
    elif sub == "players":
        show_players_admin(chat_id, message_id, int(parts[2]) if len(parts) > 2 else 0)
    elif sub == "player":
        show_player_admin(chat_id, message_id, int(parts[2]))
    elif sub == "ban":
        uid = int(parts[2])
        execute("UPDATE users SET is_banned=1 WHERE user_id=?", (uid,))
        render(chat_id, message_id, "🚫 کاربر بن شد.", back_kb(f"admin:player:{uid}"))
    elif sub == "unban":
        uid = int(parts[2])
        execute("UPDATE users SET is_banned=0 WHERE user_id=?", (uid,))
        render(chat_id, message_id, "✅ کاربر آن‌بن شد.", back_kb(f"admin:player:{uid}"))
    elif sub == "wars":
        show_wars_admin(chat_id, message_id)
    elif sub == "endwar":
        wid = int(parts[2])
        end_war(wid, "draw")
        render(chat_id, message_id, "✅ جنگ به‌صورت مساوی پایان یافت.", back_kb("admin:wars"))
    elif sub == "relations":
        show_relations_admin(chat_id, message_id, int(parts[2]) if len(parts) > 2 else 0)
    elif sub == "sendnews":
        AWAITING[user_id] = {"action": "admin_sendnews", "chat_id": chat_id}
        render(chat_id, message_id, "متن خبر رو بفرست تا در بخش اخبار جهانی منتشر بشه:", back_kb("admin:main"))
    elif sub == "broadcast":
        AWAITING[user_id] = {"action": "admin_broadcast", "chat_id": chat_id}
        render(chat_id, message_id, "متن پیام همگانی رو بفرست تا برای همه‌ی بازیکنان ارسال بشه:", back_kb("admin:main"))
    elif sub == "event":
        ev = maybe_trigger_random_event()
        render(chat_id, message_id, f"🎲 رویداد اجرا شد: {ev['name']}", back_kb("admin:main"))
    elif sub == "stats":
        show_stats_admin(chat_id, message_id)
    elif sub == "logs":
        show_logs_admin(chat_id, message_id)
    elif sub == "backup":
        do_backup(chat_id, message_id)
    elif sub == "special":
        show_special_countries_admin(chat_id, message_id)
    elif sub == "eventimages":
        show_event_images_admin(chat_id, message_id)
    elif sub == "setimg":
        category = parts[2]
        AWAITING[user_id] = {"action": "admin_set_event_image", "category": category, "chat_id": chat_id}
        render(chat_id, message_id,
                 f"یک عکس بفرست یا لینک (URL) عکس رو بفرست که برای «{EVENT_IMAGE_CATEGORIES[category]}» استفاده بشه.\n"
                 "برای پاک‌کردن عکس فعلی، کلمه‌ی «حذف» رو بفرست.",
                 back_kb("admin:eventimages"))
    elif sub == "payapprove":
        approve_manual_payment(chat_id, int(parts[2]))
    elif sub == "payreject":
        reject_manual_payment(chat_id, int(parts[2]))
    elif sub == "resetseason":
        render(chat_id, message_id, "⚠️ این کار همه‌ی کشورها رو آزاد می‌کنه و آمار فصل رو صفر می‌کنه. مطمئنی؟",
                  {"inline_keyboard": [[{"text": "✅ بله، ریست کن", "callback_data": "admin:doreset"},
                                          {"text": "❌ انصراف", "callback_data": "admin:main"}]]})
    elif sub == "doreset":
        do_reset_season()
        render(chat_id, message_id, "✅ فصل جدید شروع شد.", back_kb("admin:main"))
    else:
        send_admin_panel(chat_id, message_id)


def show_event_images_admin(chat_id, message_id):
    lines = ["🖼️ <b>عکس رویدادها</b>\nبرای هر دسته می‌تونی یک عکس تنظیم کنی که همراه خبر مربوطه تو کانال فرستاده بشه.\n"]
    rows = []
    for cat, label in EVENT_IMAGE_CATEGORIES.items():
        current = get_event_image(cat)
        status = "✅ تنظیم شده" if current else "❌ تنظیم نشده"
        lines.append(f"{label}: {status}")
        rows.append([(f"🖼️ {label}", f"admin:setimg:{cat}")])
    rows.append([("🔙 بازگشت", "admin:main")])
    render(chat_id, message_id, "\n".join(lines), kb(rows))


def handle_admin_photo(chat_id, user_id, pending, file_id):
    category = pending.get("category")
    if not category or category not in EVENT_IMAGE_CATEGORIES:
        return
    set_event_image(category, file_id)
    send_message(chat_id, f"✅ عکس برای «{EVENT_IMAGE_CATEGORIES[category]}» ذخیره شد.")


def show_special_countries_admin(chat_id, message_id):
    rows = []
    lines = ["🎖️ <b>کشورهای ویژه (بدون نقش در بازی)</b>\n"]
    for name in SPECIAL_COUNTRY_NAMES:
        c = query_one("SELECT * FROM countries WHERE name=?", (name,))
        if not c:
            continue
        owner_txt = str(c["owner_id"]) if c["owner_id"] else "کسی نداره"
        lines.append(f"{c['flag']} {c['name']} — مالک فعلی: {owner_txt}")
        rows.append([(f"👤 تغییر مالک {c['name']}", f"admin:transfer:{c['id']}")])
    rows.append([("🔙 بازگشت", "admin:main")])
    render(chat_id, message_id, "\n".join(lines), kb(rows))


def show_countries_admin(chat_id, message_id, page=0):
    all_c = query("SELECT * FROM countries ORDER BY id")
    per_page = 10
    chunk = all_c[page*per_page:(page+1)*per_page]
    rows = []
    for c in chunk:
        status = "🟢" if c["owner_id"] else ("🔴" if c["active"] else "⚫")
        rows.append([(f"{status} {c['flag']} {c['name']}", f"admin:country:{c['id']}")])
    nav = []
    if page > 0:
        nav.append(("⬅️", f"admin:countries:{page-1}"))
    if (page+1)*per_page < len(all_c):
        nav.append(("➡️", f"admin:countries:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([("🔙 بازگشت", "admin:main")])
    render(chat_id, message_id, "🌍 مدیریت کشورها (🟢دارای بازیکن 🔴آزاد ⚫غیرفعال):", kb(rows))


def show_country_admin(chat_id, message_id, cid):
    c = get_country(cid)
    if not c:
        render(chat_id, message_id, "کشور پیدا نشد.", back_kb("admin:countries"))
        return
    owner_txt = str(c["owner_id"]) if c["owner_id"] else "آزاد"
    text = (
        f"{c['flag']} <b>{c['name']}</b> (#{c['id']})\n"
        f"مالک: {owner_txt}\n"
        f"خزانه: {fmt_num(c['treasury'])}\n"
        f"HP: {fmt_num(c['hp'])}/{fmt_num(c['max_hp'])}\n"
        f"وضعیت: {'فعال' if c['active'] else 'غیرفعال'}"
    )
    rows = [
        [("👤 تغییر مالک", f"admin:transfer:{cid}"), ("🆓 آزاد کردن", f"admin:free:{cid}")],
        [("💰 تنظیم خزانه", f"admin:settreasury:{cid}"), ("⛏️ تنظیم منابع", f"admin:setres:{cid}")],
        [("🪖 تنظیم ارتش", f"admin:setunit:{cid}"), ("❤️ تنظیم HP", f"admin:sethp:{cid}")],
    ]
    if c["active"]:
        rows.append([("🗑️ غیرفعال‌سازی", f"admin:delete:{cid}")])
    else:
        rows.append([("♻️ فعال‌سازی", f"admin:activate:{cid}")])
    rows.append([("🔙 بازگشت", "admin:countries")])
    render(chat_id, message_id, text, kb(rows))


def show_players_admin(chat_id, message_id, page=0):
    users = query("SELECT * FROM users ORDER BY joined_at DESC")
    per_page = 10
    chunk = users[page*per_page:(page+1)*per_page]
    rows = []
    for u in chunk:
        label = f"{u['username'] or u['user_id']}"
        if u["is_banned"]:
            label = "🚫 " + label
        rows.append([(label, f"admin:player:{u['user_id']}")])
    nav = []
    if page > 0:
        nav.append(("⬅️", f"admin:players:{page-1}"))
    if (page+1)*per_page < len(users):
        nav.append(("➡️", f"admin:players:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([("🔙 بازگشت", "admin:main")])
    render(chat_id, message_id, f"👥 بازیکنان ({len(users)} نفر):", kb(rows))


def show_player_admin(chat_id, message_id, uid):
    u = get_user(uid)
    if not u:
        render(chat_id, message_id, "کاربر پیدا نشد.", back_kb("admin:players"))
        return
    country = get_country(u["country_id"]) if u["country_id"] else None
    text = (
        f"👤 کاربر: {u['username'] or uid}\n"
        f"آیدی: {uid}\n"
        f"کشور: {(country['flag'] + ' ' + country['name']) if country else 'ندارد'}\n"
        f"وضعیت: {'🚫 بن‌شده' if u['is_banned'] else '✅ فعال'}"
    )
    rows = []
    if u["is_banned"]:
        rows.append([("✅ آن‌بن", f"admin:unban:{uid}")])
    else:
        rows.append([("🚫 بن", f"admin:ban:{uid}")])
    rows.append([("🔙 بازگشت", "admin:players")])
    render(chat_id, message_id, text, kb(rows))


def show_wars_admin(chat_id, message_id):
    wars = query("SELECT * FROM wars WHERE status='active'")
    lines = ["⚔️ جنگ‌های فعال:\n"]
    rows = []
    for w in wars:
        a = get_country(w["attacker_id"])
        d = get_country(w["defender_id"])
        lines.append(f"#{w['id']}: {a['flag']}{a['name']} ⚔️ {d['flag']}{d['name']}")
        rows.append([(f"⛔ پایان جنگ #{w['id']}", f"admin:endwar:{w['id']}")])
    if not wars:
        lines.append("جنگ فعالی وجود نداره.")
    rows.append([("🔙 بازگشت", "admin:main")])
    render(chat_id, message_id, "\n".join(lines), kb(rows))


def show_relations_admin(chat_id, message_id, page=0):
    rels = query("SELECT * FROM relations WHERE status != 'neutral'")
    per_page = 12
    chunk = rels[page*per_page:(page+1)*per_page]
    lines = ["🤝 روابط فعال:\n"]
    for r in chunk:
        a = get_country(r["country_a"])
        b = get_country(r["country_b"])
        if a and b:
            lines.append(f"{a['flag']}{a['name']} ↔ {b['flag']}{b['name']}: {r['status']}")
    if not chunk:
        lines.append("رابطه‌ی خاصی ثبت نشده.")
    render(chat_id, message_id, "\n".join(lines), back_kb("admin:main"))


def show_stats_admin(chat_id, message_id):
    total_countries = query_one("SELECT COUNT(*) n FROM countries WHERE active=1")["n"]
    taken = query_one("SELECT COUNT(*) n FROM countries WHERE owner_id IS NOT NULL")["n"]
    users_n = query_one("SELECT COUNT(*) n FROM users")["n"]
    total_treasury = query_one("SELECT SUM(treasury) s FROM countries")["s"] or 0
    active_wars = query_one("SELECT COUNT(*) n FROM wars WHERE status='active'")["n"]
    total_wars = query_one("SELECT COUNT(*) n FROM wars")["n"]
    factories = query_one("SELECT COUNT(*) n FROM factories")["n"]
    text = (
        "📊 <b>آمار بازی</b>\n\n"
        f"کشورهای فعال: {total_countries}\n"
        f"کشورهای دارای بازیکن: {taken}\n"
        f"تعداد کاربران: {users_n}\n"
        f"مجموع خزانه‌ی همه‌ی کشورها: {fmt_num(total_treasury)}\n"
        f"جنگ‌های فعال: {active_wars} (مجموع تاریخی: {total_wars})\n"
        f"مجموع کارخانه‌های ساخته‌شده: {factories}\n"
    )
    render(chat_id, message_id, text, back_kb("admin:main"))


def show_logs_admin(chat_id, message_id):
    logs = query("SELECT * FROM activity_log ORDER BY id DESC LIMIT 20")
    lines = ["📜 آخرین فعالیت‌ها:\n"]
    for l in logs:
        lines.append(f"[{l['user_id']}] {l['action']}: {l['detail']}")
    if not logs:
        lines.append("لاگی ثبت نشده.")
    render(chat_id, message_id, "\n".join(lines), back_kb("admin:main"))


def do_backup(chat_id, message_id):
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.dirname(os.path.abspath(DB_PATH))
    backup_path = os.path.join(backup_dir, f"backup_{ts}.db")
    try:
        with _lock:
            dst = sqlite3.connect(backup_path)
            try:
                _conn.backup(dst)
            finally:
                dst.close()
        render(chat_id, message_id, f"✅ پشتیبان دائمی ذخیره شد: {backup_path}", back_kb("admin:main"))
    except Exception as e:
        render(chat_id, message_id, f"⛔ خطا در پشتیبان‌گیری: {e}", back_kb("admin:main"))


def do_reset_season():
    """فصل جدید: همه‌ی کشورها آزاد می‌شن و آمار/دارایی‌ها صفر می‌شه؛ خود کشورها و ساختار دیتابیس دست نمی‌خوره."""
    execute("UPDATE users SET country_id=NULL")
    execute(
        "UPDATE countries SET owner_id=NULL, treasury=50000, hp=max_hp, wins=0, losses=0, "
        "conquests=0, debt=0, satisfaction=60, morale=70, tax_rate=0.20"
    )
    execute("DELETE FROM army")
    execute("DELETE FROM factories")
    execute("DELETE FROM tech")
    execute("DELETE FROM research_queue")
    execute("UPDATE wars SET status='ended' WHERE status='active'")
    execute("UPDATE relations SET status='neutral'")
    execute("UPDATE territories SET owner_id = original_owner_id WHERE is_strait=0")
    execute("UPDATE territories SET owner_id=NULL WHERE is_strait=1")
    add_news("🔄 فصل جدید بازی آغاز شد! همه‌ی کشورها دوباره آزاد شدند.")


def handle_admin_text(chat_id, user_id, action, pending, text):
    cid = pending.get("country_id")
    try:
        if action == "admin_set_event_image":
            category = pending.get("category")
            if text.strip() in ("حذف", "/حذف", "delete"):
                set_event_image(category, None)
                send_message(chat_id, "✅ عکس حذف شد.")
            else:
                set_event_image(category, text.strip())
                send_message(chat_id, f"✅ عکس برای «{EVENT_IMAGE_CATEGORIES[category]}» ذخیره شد.")
        elif action == "admin_transfer":
            new_owner = int(text)
            execute("UPDATE countries SET owner_id=? WHERE id=?", (new_owner, cid))
            execute("UPDATE users SET country_id=? WHERE user_id=?", (cid, new_owner))
            send_message(chat_id, "✅ مالکیت تغییر کرد.")
        elif action == "admin_settreasury":
            amount = float(text)
            execute("UPDATE countries SET treasury=? WHERE id=?", (amount, cid))
            send_message(chat_id, "✅ خزانه به‌روزرسانی شد.")
        elif action == "admin_setres":
            amount = float(text)
            res = pending["resource"]
            execute(
                "INSERT INTO resources (country_id, resource, amount) VALUES (?,?,?) "
                "ON CONFLICT(country_id, resource) DO UPDATE SET amount=?",
                (cid, res, amount, amount),
            )
            send_message(chat_id, "✅ منبع به‌روزرسانی شد.")
        elif action == "admin_setunit":
            qty = int(text)
            key = pending["unit_key"]
            execute(
                "INSERT INTO army (country_id, unit_key, quantity) VALUES (?,?,?) "
                "ON CONFLICT(country_id, unit_key) DO UPDATE SET quantity=?",
                (cid, key, qty, qty),
            )
            send_message(chat_id, "✅ تعداد واحد نظامی به‌روزرسانی شد.")
        elif action == "admin_sethp":
            hp = float(text)
            execute("UPDATE countries SET hp=? WHERE id=?", (hp, cid))
            send_message(chat_id, "✅ HP به‌روزرسانی شد.")
        elif action == "admin_sendnews":
            add_news(f"📢 {text}")
            send_message(chat_id, "✅ خبر منتشر شد.")
        elif action == "admin_broadcast":
            users = query("SELECT user_id FROM users")
            for u in users:
                try:
                    send_message(u["user_id"], f"📢 <b>پیام همگانی</b>\n\n{text}")
                except Exception:
                    pass
            send_message(chat_id, f"✅ پیام برای {len(users)} کاربر ارسال شد.")
    except ValueError:
        send_message(chat_id, "❗ مقدار وارد شده معتبر نیست.")
        return
    finally:
        AWAITING.pop(user_id, None)

# ======================================================================
# بخش برگرفته از: main.py
# ======================================================================
# -*- coding: utf-8 -*-
"""
نقطه‌ی شروع ربات. این فایل رو در Pydroid3 اجرا کن.
"""
import threading
import time
import traceback



def background_loop():
    """هر چند دقیقه یک‌بار: محاسبه‌ی اقتصاد، تحقیقات تمام‌شده، و شانس رویداد تصادفی."""
    last_tick = 0
    while True:
        try:
            now = int(time.time())
            if now - last_tick >= TICK_INTERVAL_SECONDS:
                economic_tick()
                collect_finished_research()
                import random
                if random.random() < 0.15:  # حدود ۱۵٪ احتمال رویداد در هر تیک
                    maybe_trigger_random_event()
                last_tick = now
        except Exception:
            print("[background_loop] خطا:")
            traceback.print_exc()
        time.sleep(30)


def get_username(frm):
    if not frm:
        return ""
    return frm.get("username") or frm.get("first_name") or str(frm.get("id", ""))


def process_update(update):
    try:
        if "callback_query" in update:
            cq = update["callback_query"]
            chat_id = cq["message"]["chat"]["id"]
            message_id = cq["message"]["message_id"]
            user_id = cq["from"]["id"]
            username = get_username(cq["from"])
            cb_data = cq.get("data", "")
            callback_id = cq.get("id")
            handle_callback(chat_id, message_id, user_id, username, cb_data, callback_id)

        elif "pre_checkout_query" in update:
            pcq = update["pre_checkout_query"]
            answer_pre_checkout_query(pcq["id"], True)

        elif "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            user_id = msg["from"]["id"]
            username = get_username(msg.get("from"))
            if msg.get("successful_payment"):
                handle_successful_payment(chat_id, user_id, msg["successful_payment"])
                return
            if msg.get("photo"):
                file_id = msg["photo"][-1]["file_id"]
                handle_photo(chat_id, user_id, username, file_id)
                return
            text = msg.get("text", "")
            if text:
                handle_text(chat_id, user_id, username, text)
    except Exception:
        print("[process_update] خطا در پردازش آپدیت:")
        traceback.print_exc()


def main():
    print("راه‌اندازی ربات تلگرام ...")
    if not BOT_TOKEN or BOT_TOKEN == "PUT_YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("❌ BOT_TOKEN را در بخش تنظیمات فایل وارد کن.")
        return
    me = get_me()
    if not me.get("ok"):
        print("❌ توکن تلگرام نامعتبر است یا اتصال به Telegram API برقرار نشد.")
        print(me)
        return
    print(f"✅ ربات تلگرام: @{me.get('result', {}).get('username', '')}")
    delete_webhook()

    print("راه‌اندازی دیتابیس ...")
    init_db()
    seed_countries_if_needed()
    ensure_special_and_vip_countries()
    sync_country_flags()
    print("دیتابیس آماده است. شروع polling ...")

    t = threading.Thread(target=background_loop, daemon=True)
    t.start()

    offset = None
    while True:
        try:
            updates = get_updates(offset)
            for u in updates:
                offset = u["update_id"] + 1
                process_update(u)
        except Exception:
            print("[main] خطا در حلقه‌ی اصلی:")
            traceback.print_exc()
            time.sleep(3)




if __name__ == "__main__":
    main()

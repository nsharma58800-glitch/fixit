import asyncio
import sqlite3
import random
import logging
import time
import aiohttp
import hmac
import hashlib
import html as html_lib
import json
import urllib.parse
import os
import re
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, Dice, BufferedInputFile
)

# ==============================================================================
# 1. BOT CONFIGURATION & CONSTANTS
# ==============================================================================
# Railway Volume: mount your Volume at /data in Railway.
DATA_DIR = "/data" if os.path.isdir("/data") else os.path.dirname(os.path.abspath(__file__))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "Thakur_Mods_Ofc.db")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_USERNAME = "THAKUR_MODS_SHOP_BOT"
ADMIN_ID = int(os.getenv("ADMIN_ID", "6513926862"))
ADMIN_CONTACT = "@H4XTHAKUR"

FAMPAY_API_KEY = os.getenv("FAMPAY_API_KEY", "PASTE_YOUR_FAMPAY_API_KEY_HERE").strip()
FAMPAY_QR_URL = "https://famgateway.in/api/qr.php"
FAMPAY_VERIFY_URL = "https://famgateway.in/api/verify-order.php"
FAMPAY_STATUS_URL = "https://famgateway.in/api/checkout-status.php"
BharatPe_API_KEY = os.getenv("BHARATPE_API_KEY", "PASTE_YOUR_BharatPe_API_KEY_HERE").strip()
BharatPe_QR_URL = "https://gateway.anujbots.in/qr.php"
BharatPe_VERIFY_URL = "https://gateway.anujbots.in/bharatpe_verify.php"

# Reseller API (automatic key supplier)
# IMPORTANT: this is intentionally the BantiBhaiya endpoint requested for this build.
RESELLER_API_URL = "https://bantibhaiya.to/api/reseller_v1.php"
RESELLER_API_KEY = os.getenv("RESELLER_API_KEY", "YOUR_RRSELLER_API_ADD").strip()

USDT_TO_INR = 90.0
VIP_DISCOUNT_PERCENTAGE = 1.0
VIP_PRICE_INR = 1000.0

WELCOME_STICKER_ID = "CAACAgIAAxkBAAEU-WZmH_..."  # Replace with your sticker ID
SPIN_DELAY_SECONDS = 2.5

FIXED_CATEGORIES = [
    "ANDROID NON ROOT PANEL",
    "ANDROID ROOT PANEL",
    "IPHONE PANEL",
    "PC PANEL"
]

def get_categories() -> list:
    """Return built-in, admin-created, and database-used product categories."""
    categories = list(FIXED_CATEGORIES)
    try:
        raw = get_setting("custom_product_categories", "[]")
        saved = json.loads(raw) if raw else []
        if isinstance(saved, list):
            categories.extend(str(x).strip().upper() for x in saved if str(x).strip())
    except Exception:
        logger.exception("Could not read custom product categories")
    try:
        rows = db_query(
            "SELECT DISTINCT UPPER(TRIM(category)) FROM products "
            "WHERE TRIM(COALESCE(category,'')) != '' ORDER BY 1",
            fetchall=True
        ) or []
        categories.extend(str(row[0]).strip() for row in rows if row and row[0])
    except Exception:
        logger.exception("Could not load product categories from database")
    result = []
    seen = set()
    for category in categories:
        category = str(category).strip().upper()
        if category and category.casefold() not in seen:
            seen.add(category.casefold())
            result.append(category)
    return result


# ==============================================================================
# YOUR PREMIUM EMOJIS – all required emoji IDs (updated with new premium ones)
# ==============================================================================
DEFAULT_EMOJIS = {
    'product_store': '6163205892834598715',
    'paytm': '6057563333874163460',
    'fampay': '6057891001224144042',
    'BharatPe': '6057563333874163460',
    'cheatz': '6055120360771166479',
    'sagartop': '6278540341851200737',
    'profile': '5870695289714643076',
    'sagarproof': '6001517283426439371',
    'sagar': '6055120360771166479',
    'add_balance': '5429651785352501917',
    'history': '6032594876506312598',
    'referral': '5350452584119279096',
    'support': '5472239203590888751',
    'ludo_spin': '5382194935057372936',
    'back': '5409357944619802453',
    'upi': '5807750375033278838',
    'binance': '6161089551994462716',
    'reseller': '5447410659077661506',
    'tutorial': '6055538870974423127',
    'download': '6161336001512874965',
    'telegram': '5456140674028019486',
    'whatsapp': '5251203410396458957',
    'welcome': '5397782960512444700',
    'vip': '5206607081334906820',
    'category_android_non_root': '6161172706856282588',
    'category_android_root': '6161449831031118974',
    'category_iphone': '6161399700172840408',
    'category_pc': '5350554349074391003',
    'grid_id': '5474625972751837256',
    'name': '5215399540814781035',
    'account_level': '6129584162992034014',
    'regular_user': '5904630315946611415',
    'wallet': '6210859306602995217',
    'current_balance': '5316711376876485361',
    'global_stats': '6161437856662298090',
    'total_orders': '6160968017304888311',
    'total_spent': '5197503331215361533',
    'total_referrals': '5938196735200333756',
    'joined_grid': '5433614043006903194',
    'info_icon': '6037421444789440735',
    'check_icon': '6161241250239356403',
    'checkbox_icon': '6161437856662298090',
    'shield_icon': '6086672466132865380',
    'money_icon': '5890848474563352982',
    'redeem_icon': '5377624166436445368',
    'wallet_left': '6210859306602995217',
    'wallet_right': '5305699699204837855',
    'point_down': '6161302621027049305',
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_activity.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Add BOT_TOKEN in Railway Variables.")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

def fmt_curr(amount: float) -> str:
    return f"₹{amount:,.2f}"

def safe_float(val, default=0.0):
    """Safely convert a value to float, return default if fails."""
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

# ==============================================================================
# 2. DATABASE FUNCTIONS
# ==============================================================================
def db_query(query: str, params: tuple = (), fetchone: bool = False, fetchall: bool = False, commit: bool = True) -> Any:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute(query, params)
        if fetchone:
            res = c.fetchone()
        elif fetchall:
            res = c.fetchall()
        else:
            res = None
        if commit: conn.commit()
        return res
    except Exception as e:
        logger.error(f"DB Error: {e} | Query: {query} | Params: {params}")
        if commit: conn.rollback()
        return None
    finally:
        conn.close()

def get_setting(key: str, default: str = "") -> str:
    val = db_query("SELECT value FROM settings WHERE key=?", (key,), fetchone=True)
    return val[0] if val and val[0] else default

def set_setting(key: str, value: str) -> None:
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))


def new_user_start_message_enabled() -> bool:
    """Return the admin-controlled New User Notification state."""
    return str(get_setting("new_user_start_message", "ON")).strip().upper() == "ON"

def log_activity(user_id: int, action: str, details: str = "") -> None:
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_query(
            "INSERT INTO activity_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, details, timestamp)
        )
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")

def get_emoji(slot: str, default_id: str = None) -> str:
    stored = get_setting(f"emoji_{slot}", "")
    emoji_id = stored if stored and stored.isdigit() else (default_id or DEFAULT_EMOJIS.get(slot, ""))
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">✨</tg-emoji>'
    return "✨"

def get_emoji_icon(slot: str, default_id: str = None) -> str:
    stored = get_setting(f"emoji_{slot}", "")
    emoji_id = stored if stored and stored.isdigit() else (default_id or DEFAULT_EMOJIS.get(slot, ""))
    return emoji_id

# ==============================================================================
# 3. STRING RESOURCES – using placeholders for premium emojis
# ==============================================================================
UI_TEXTS = {
    "start_menu": (
        "{cheatz} 𝐖𝐄𝐋𝐂𝐎𝐌𝐄 𝐓𝐎 𝐓𝐇𝐀𝐊𝐔𝐑 𝐌𝐎𝐃𝐒 𝐒𝐇𝐎𝐏 {sagartop}\n\n"
        "{product_store} 𝐏𝐫𝐞𝐦𝐢𝐮𝐦 𝐆𝐚𝐦𝐞 𝐊𝐞𝐲𝐬 & 𝐏𝐚𝐧𝐞𝐥𝐬\n"
        "{profile}  𝐈𝐧𝐬𝐭𝐚𝐧𝐭 𝐀𝐮𝐭𝐨 𝐃𝐞𝐥𝐢𝐯𝐞𝐫𝐲 𝟐𝟒×𝟕\n"
        "{add_balance} 𝟏𝟎𝟎% 𝐒𝐞𝐜𝐮𝐫𝐞 & 𝐓𝐫𝐮𝐬𝐭𝐞𝐝 𝐒𝐭𝐨𝐫𝐞\n"
        "{history} 𝐁𝐞𝐬𝐭 𝐏𝐫𝐢𝐜𝐞𝐬 𝐆𝐮𝐚𝐫𝐚𝐧𝐭𝐞𝐞𝐝\n"
        "{referral} 𝐃𝐚𝐢𝐥𝐲 𝐑𝐞𝐰𝐚𝐫𝐝𝐬 & 𝐒𝐩𝐞𝐜𝐢𝐚𝐥 𝐎𝐟𝐟𝐞𝐫𝐬\n"
        "{tutorial} 𝟐𝟒/𝟕 𝐋𝐢𝐯𝐞 𝐒𝐮𝐩𝐩𝐨𝐫𝐭 𝐀𝐯𝐚𝐢𝐥𝐚𝐛𝐥𝐞\n"
        "{support}𝐓𝐫𝐮𝐬𝐭𝐞𝐝 𝐛𝐲 𝐇𝐮𝐧𝐝𝐫𝐞𝐝𝐬 𝐨𝐟 𝐔𝐬𝐞𝐫𝐬\n"
        "{sagar} <b>𝐔𝐬𝐞𝐫 𝐈𝐃:</b> <code>{u[0]}</code>\n"
        "{wallet_left} <b>𝐘𝐨𝐮𝐫 𝐁𝐚𝐥𝐚𝐧𝐜𝐞:</b> {fmt_curr(u[3])}\n"
    ),
    "download_files": (
        "🗂 <b><u>DOWNLOAD PREMIUM APK & FILES 📊</u></b>\n\n"
        "🌐 All our highly secured, premium, and updated files\n"
        "are securely hosted on our private channel! ⚠️⛔️\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📱 <b>WHAT YOU GET:</b> 📌\n\n"
        "✔️ Latest APK Updates 🔔\n"
        "✔️ 100% Virus Free & Secure ‼️\n"
        "✔️ All Configs & Scripts 🌸\n"
        "✔️ Complete Installation Guides 🔺\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⌨️ Tap the button below to access the Download Channel! 📝"
    ),
    "lucky_dice_result": (
        "{ludo_spin} <b><u>LUCKY DICE RESULT 🔨 💯</u></b>\n\n"
        "🎲 <b>Dice Value:</b> {dice_value}\n\n"
        "💸 <b>You Won:</b> {won_amount}\n"
        "💰 <b>Total Balance:</b> {new_balance}\n\n"
        "Congratulations! Come back after 24 hours."
    ),
    "vip_menu": (
        "🌟 <b><u>VIP MEMBERSHIP CLUB</u></b> 🌟\n\n"
        "Unlock premium benefits and permanent discounts!\n\n"
        "💎 <b>VIP Benefits:</b>\n"
        "• Flat 15% off on ALL products (Stacks with Reseller!)\n"
        "• Priority Support\n"
        "• Exclusive VIP-only giveaways\n\n"
        "💳 <b>VIP Price:</b> ₹299.00 (Lifetime)\n"
        "👤 <b>Your Status:</b> {vip_status}"
    ),
    "add_balance_menu": (
        "{add_balance} <b>ADD BALANCE</b> {info_icon}\n\n"
        "{info_icon} Select your preferred payment method. {check_icon}\n\n"
        "┣ {fampay} UPI — Fampay payments {checkbox_icon}\n"
        "┣ {BharatPe} UPI — BharatPe payments {checkbox_icon}\n"
        "┣ {upi} UPI — Fast Indian payments {checkbox_icon}\n"
        "┣ {binance} Binance — Crypto payments {checkbox_icon}\n\n"
        "{shield_icon} Payments are verified securely. {check_icon}"
    )
}

def get_ui_text(key: str, **kwargs) -> str:
    val = db_query("SELECT value FROM settings WHERE key=?", (f"ui_{key}",), fetchone=True)
    template = val[0] if val and val[0] else UI_TEXTS.get(key, "")

    emoji_map = {
        '{cheatz}': get_emoji('cheatz'),
        '{paytm}': get_emoji('paytm'),
        '{sagartop}': get_emoji('sagartop'),
        '{sagarproof}': get_emoji('sagarproof'),
        '{fampay}': get_emoji('fampay'),
        '{BharatPe}': get_emoji('BharatPe'),
        '{product_store}': get_emoji('product_store'),
        '{sagar}': get_emoji('sagar'),
        '{profile}': get_emoji('profile'),
        '{add_balance}': get_emoji('add_balance'),
        '{history}': get_emoji('history'),
        '{referral}': get_emoji('referral'),
        '{tutorial}': get_emoji('tutorial'),
        '{support}': get_emoji('support'),
        '{ludo_spin}': get_emoji('ludo_spin'),
        '{download}': get_emoji('download'),
        '{telegram}': get_emoji('telegram'),
        '{whatsapp}': get_emoji('whatsapp'),
        '{upi}': get_emoji('upi'),
        '{binance}': get_emoji('binance'),
        '{info_icon}': get_emoji('info_icon'),
        '{check_icon}': get_emoji('check_icon'),
        '{checkbox_icon}': get_emoji('checkbox_icon'),
        '{shield_icon}': get_emoji('shield_icon'),
        '{money_icon}': get_emoji('money_icon'),
        '{redeem_icon}': get_emoji('redeem_icon'),
        '{wallet_left}': get_emoji('wallet_left'),
        '{wallet_right}': get_emoji('wallet_right'),
        '{point_down}': get_emoji('point_down'),
    }
    for placeholder, emoji_tag in emoji_map.items():
        template = template.replace(placeholder, emoji_tag)

    # The DB may contain an older/custom start_menu template that uses
    # {u[0]} and {fmt_curr(u[3])}. str.format() cannot execute a function
    # call inside a field, so resolve these two live profile values first.
    if key == "start_menu" and kwargs.get("u"):
        user_row = kwargs["u"]
        try:
            template = template.replace("{u[0]}", str(user_row[0]))
            template = template.replace("{fmt_curr(u[3])}", fmt_curr(user_row[3]))
        except (IndexError, TypeError):
            logger.warning("Invalid user data while formatting start_menu")

    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError, IndexError) as e:
            logger.warning(f"Missing/invalid formatting value for template {key}: {e}")
    return template

# ==============================================================================
# 4. DATABASE INITIALISATION & MIGRATION
# ==============================================================================
def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            phone TEXT, 
            first_name TEXT, 
            username TEXT,
            balance REAL DEFAULT 0.0, 
            account_type TEXT DEFAULT 'Regular', 
            orders_count INTEGER DEFAULT 0, 
            spent REAL DEFAULT 0.0, 
            referrals_count INTEGER DEFAULT 0, 
            referral_earned REAL DEFAULT 0.0, 
            referred_by INTEGER, 
            last_spin TEXT, 
            joined_date TEXT,
            is_reseller INTEGER DEFAULT 0,
            reseller_since TEXT,
            total_saved REAL DEFAULT 0.0,
            is_banned INTEGER DEFAULT 0,
            warnings INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            vip_since TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            category TEXT, 
            panel_name TEXT DEFAULT '',
            name TEXT, 
            price_inr REAL, 
            reseller_price REAL DEFAULT 0.0,
            stock INTEGER, 
            apk_link TEXT, 
            validity TEXT DEFAULT 'Lifetime', 
            device_limit TEXT DEFAULT '1 Device',
            is_active INTEGER DEFAULT 1,
            maintenance INTEGER DEFAULT 0,
            api_product_id TEXT DEFAULT '',
            api_duration TEXT DEFAULT ''
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS product_demos (
            product_name_key TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            file_id TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS product_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            product_id INTEGER, 
            key_text TEXT, 
            is_used INTEGER DEFAULT 0
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            product_name TEXT, 
            price_paid REAL, 
            delivered_key TEXT, 
            purchase_date TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            message TEXT, 
            status TEXT DEFAULT 'Open',
            created_at TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, 
            value TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS coupons (
            code TEXT PRIMARY KEY, 
            amount REAL, 
            uses_left INTEGER
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS redeemed (
            user_id INTEGER, 
            code TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            order_id TEXT PRIMARY KEY, 
            user_id INTEGER, 
            amount_inr REAL, 
            status TEXT, 
            timestamp INTEGER,
            qr_url TEXT,
            upi_id TEXT,
            expires_at INTEGER,
            qr_message_id INTEGER
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS crypto_txns (
            txid TEXT PRIMARY KEY, 
            user_id INTEGER, 
            amount_usdt REAL, 
            timestamp INTEGER
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS spin_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            amount REAL
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TEXT
        )
    ''')

    migrations = [
        "ALTER TABLE users ADD COLUMN is_vip INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN vip_since TEXT",
        "ALTER TABLE products ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE products ADD COLUMN maintenance INTEGER DEFAULT 0",
        "ALTER TABLE tickets ADD COLUMN created_at TEXT",
        "ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN warnings INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN panel_name TEXT DEFAULT ''",
        "ALTER TABLE transactions ADD COLUMN qr_url TEXT",
        "ALTER TABLE transactions ADD COLUMN upi_id TEXT",
        "ALTER TABLE transactions ADD COLUMN expires_at INTEGER",
        "ALTER TABLE transactions ADD COLUMN qr_message_id INTEGER",
        "ALTER TABLE products ADD COLUMN api_product_id TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN api_duration TEXT DEFAULT ''"
    ]
    for mig in migrations:
        try: c.execute(mig)
        except sqlite3.OperationalError: pass
    
    c.execute("SELECT COUNT(*) FROM spin_rewards")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO spin_rewards (amount) VALUES (?)", [(0.0,), (1.0,), (2.0,), (5.0,), (10.0,)])

    default_settings = [
        ('spin_status', 'ON'),
        ('daily_spin_limit', '50.0'),
        ('reseller_system_status', 'ON'),
        ('bot_status', 'ON'),
        ('how_to_video', 'None'),
        ('all_files_link', 'None'),
        ('selling_proof_link', 'None'),
        ('fampay_api_key', FAMPAY_API_KEY),
        ('BharatPe_api_key', BharatPe_API_KEY),
        ('gateway_BharatPe_enabled', 'ON'),
        ('reseller_api_key', RESELLER_API_KEY),
        ('reseller_api_url', RESELLER_API_URL),
        ('fampay_upi_id', ''),
        ('binance_api', ''),
        ('binance_secret', ''),
        ('binance_address', ''),
        ('vip_status', 'OFF'),
        ('reseller_setup_fee', '200.0'),
        ('reseller_min_balance', '500.0'),
        ('migration_done', '0'),
        ('new_user_start_message', 'ON'),
        ('support_telegram', 'https://t.me/YourSupport'),
        ('support_whatsapp', 'https://wa.me/YourNumber'),
        ('ui_start_menu', UI_TEXTS['start_menu']),
        ('ui_download_files', UI_TEXTS['download_files']),
        ('ui_lucky_dice_result', UI_TEXTS['lucky_dice_result']),
        ('ui_vip_menu', UI_TEXTS['vip_menu']),
        ('ui_add_balance_menu', UI_TEXTS['add_balance_menu']),
    ]
    for slot, emoji_id in DEFAULT_EMOJIS.items():
        default_settings.append((f"emoji_{slot}", emoji_id))
    
    for key, val in default_settings:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

    conn.commit()
    conn.close()

def migrate_categories() -> None:
    done = get_setting("migration_done", "0")
    
    # ALWAYS force update emojis and UI texts regardless of migration status
    logger.info("Forcing emoji and UI text updates...")
    
    # Update all emoji settings
    for slot, emoji_id in DEFAULT_EMOJIS.items():
        set_setting(f"emoji_{slot}", emoji_id)
    
    # Force update UI texts
    set_setting("ui_start_menu", UI_TEXTS['start_menu'])
    set_setting("ui_add_balance_menu", UI_TEXTS['add_balance_menu'])
    set_setting("ui_download_files", UI_TEXTS['download_files'])
    set_setting("ui_lucky_dice_result", UI_TEXTS['lucky_dice_result'])
    set_setting("ui_vip_menu", UI_TEXTS['vip_menu'])
    logger.info("UI texts and emojis updated with new placeholders and IDs.")
    
    # Fix any corrupted price columns (one-time cleanup)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    products = c.execute("SELECT id, price_inr, reseller_price FROM products").fetchall()
    for prod in products:
        pid = prod[0]
        for col in ['price_inr', 'reseller_price']:
            val = prod[1] if col == 'price_inr' else prod[2]
            if val is None or val == "":
                new_val = 0.0
            else:
                try:
                    new_val = float(val)
                except (ValueError, TypeError):
                    new_val = 0.0
            c.execute(f"UPDATE products SET {col}=? WHERE id=?", (new_val, pid))
    conn.commit()
    conn.close()
    logger.info("Fixed any non-numeric price columns.")
    
    if done == "1":
        return
    
    logger.info("Running category migration...")
    
    mapping = {
        "android non root panel": "ANDROID NON ROOT PANEL",
        "android root panel": "ANDROID ROOT PANEL",
        "iphone panel": "IPHONE PANEL",
        "pc panel": "PC PANEL",
    }
    for old, new in mapping.items():
        db_query("UPDATE products SET category = ? WHERE LOWER(category) = ?", (new, old))
    
    
    set_setting("migration_done", "1")
    logger.info("Category migration complete.")

# ==============================================================================
# 5. MIDDLEWARES & SECURITY
# ==============================================================================
async def hacker_loading(message: Message, text: str = "Decrypting Data") -> Message:
    msg = await message.answer(f"⚡ {text}\n[□□□] 0%")
    await asyncio.sleep(0.3)
    await msg.edit_text(f"⚡ {text}\n[■□□] 33%", parse_mode='HTML')
    await asyncio.sleep(0.3)
    await msg.edit_text(f"⚡ {text}\n[■■□] 66%", parse_mode='HTML')
    await asyncio.sleep(0.3)
    await msg.edit_text(f"⚡ {text}\n[■■■] 100%", parse_mode='HTML')
    return msg

class GlobalSecurityMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self.last_action_times = {}

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        now = time.time()
        # Do not throttle inline-button callbacks: rapid keypad taps (especially
        # Confirm) must not be silently discarded. Keep a short debounce for messages.
        if isinstance(event, Message):
            if user_id in self.last_action_times and now - self.last_action_times[user_id] < 0.08:
                return
            self.last_action_times[user_id] = now

        if user_id != ADMIN_ID:
            user_info = db_query("SELECT is_banned FROM users WHERE user_id=?", (user_id,), fetchone=True)
            if user_info and user_info[0] == 1:
                msg = "🚫 <b>ACCESS DENIED</b>\nYou have been banned from using this bot.\nContact support if you think this is a mistake."
                if isinstance(event, Message): await event.answer(msg)
                elif isinstance(event, CallbackQuery): await event.answer(msg, show_alert=True)
                return
                
            status_check = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
            status = status_check[0] if status_check else 'ON'
            if status == 'OFF':
                msg = "⚠️ <b>Store Maintenance</b>\n\nThe store is currently offline for updates. Please check back later!"
                if isinstance(event, Message): await event.answer(msg)
                elif isinstance(event, CallbackQuery): await event.answer("⚠️ Bot is currently OFF for Maintenance.", show_alert=True)
                return
                
        return await handler(event, data)

dp.message.middleware(GlobalSecurityMiddleware())
dp.callback_query.middleware(GlobalSecurityMiddleware())

# ==============================================================================
# 6. FSM STATES
# ==============================================================================
class UserStates(StatesGroup):
    wait_for_ticket = State()
    wait_for_redeem = State()
    wait_for_crypto_txid = State()
    custom_amount_input = State()
    wait_for_BharatPe_utr = State()

class AdminStates(StatesGroup):
    add_prod_category = State()
    wait_for_new_category_name = State()
    wait_for_category_rename = State()
    add_prod_panel_name = State()
    add_prod_name = State()
    add_prod_validity = State()
    add_prod_device_limit = State()
    add_prod_price = State()
    add_prod_reseller_price = State()
    add_prod_apk = State()
    add_prod_keys = State()
    add_prod_api_pid = State()
    add_prod_api_duration = State()
    wait_for_product_demo_video = State()
    wait_for_demo_delete_time = State()
    wait_for_panel_rename = State()
    
    edit_prod_field = State()
    wait_for_new_value = State()
    wait_for_add_keys = State()
    wait_for_delete_key = State()
    
    broadcast_msg = State()
    add_coupon_code = State()
    add_coupon_amount = State()
    add_coupon_uses = State()
    
    # Payment gateway setup states
    wait_for_fampay_api = State()
    wait_for_fampay_upi = State()
    wait_for_BharatPe_api = State()
    wait_for_zapupi_key = State()
    
    # Binance states
    wait_for_binance_api = State()
    wait_for_binance_secret = State()
    wait_for_binance_address = State()
    
    ticket_reply_msg = State()
    reseller_manage_id = State()
    manage_target_user = State()
    wait_for_add_money = State()
    wait_for_minus_money = State()
    wait_for_balance_user_id = State()
    wait_for_balance_add_amount = State()
    wait_for_balance_remove_user_id = State()
    wait_for_warning = State()
    
    spin_add_reward = State()
    spin_set_limit = State()
    wait_for_howto_video = State()
    wait_for_all_files_link = State()
    wait_for_selling_proof_link = State()
    
    edit_ui_text = State()
    edit_reseller_price = State()
    wait_for_reseller_setup_fee = State()
    wait_for_reseller_min_balance = State()
    wait_for_reseller_api_key = State()
    wait_for_reseller_api_url = State()
    confirm_ban = State()
    
    wait_for_support_telegram = State()
    wait_for_support_whatsapp = State()
    wait_for_category_emoji = State()
    wait_for_panel_emoji_id = State()
    wait_for_emoji_slot = State()

# ==============================================================================
# 7. KEYBOARDS
# ==============================================================================
def get_category_emoji(category: str) -> str:
    """Resolve admin-set emoji IDs for both built-in and custom categories."""
    category = str(category or "").strip().upper()
    custom = get_setting(f"cat_emoji_{category}", "").strip()
    if custom.isdigit():
        return custom
    slot_map = {
        "ANDROID NON ROOT PANEL": "category_android_non_root",
        "ANDROID ROOT PANEL": "category_android_root",
        "IPHONE PANEL": "category_iphone",
        "PC PANEL": "category_pc",
    }
    slot = slot_map.get(category)
    return get_emoji_icon(slot, DEFAULT_EMOJIS.get(slot, "")) if slot else ""

def get_panel_emoji(panel_name: str) -> str:
    stored = get_setting(f"panel_emoji_{panel_name}", "")
    if stored and stored.isdigit():
        return stored
    return get_emoji_icon("product_store")

def contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Verify Contact", request_contact=True)]], 
        resize_keyboard=True, 
        one_time_keyboard=True
    )

def main_menu_kb(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
    status_check = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    sys_status = status_check[0] if status_check else 'ON'
    vip_sys_check = db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True)
    vip_system = vip_sys_check[0] if vip_sys_check else 'OFF'
    
    is_reseller = False
    if user_id:
        user_check = db_query("SELECT is_reseller FROM users WHERE user_id=?", (user_id,), fetchone=True)
        if user_check:
            is_reseller = bool(user_check[0])

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="Buy Key", callback_data="menu_shop",
            icon_custom_emoji_id=get_emoji_icon("product_store"),
            style="success"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="My Profile", callback_data="menu_profile",
            icon_custom_emoji_id=get_emoji_icon("profile"),
            style="success"
        ),
        InlineKeyboardButton(
            text="Add Balance", callback_data="menu_add_balance",
            icon_custom_emoji_id=get_emoji_icon("add_balance"),
            style="success"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="All History", callback_data="menu_orders",
            icon_custom_emoji_id=get_emoji_icon("history"),
            style="success"
        ),
        InlineKeyboardButton(
            text="Referral", callback_data="menu_referral",
            icon_custom_emoji_id=get_emoji_icon("referral"),
            style="success"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="How To Use Bot", callback_data="menu_how_to",
            icon_custom_emoji_id=get_emoji_icon("tutorial"),
            style="success"
        ),
        InlineKeyboardButton(
            text="Support", callback_data="menu_support",
            icon_custom_emoji_id=get_emoji_icon("support"),
            style="success"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="Ludo Spin", callback_data="menu_spin_landing",
            icon_custom_emoji_id=get_emoji_icon("ludo_spin"),
            style="success"
        ),
        InlineKeyboardButton(
            text="Download Files", callback_data="menu_all_files",
            icon_custom_emoji_id=get_emoji_icon("download"),
            style="success"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="Selling Proof", callback_data="menu_selling_proof",
            icon_custom_emoji_id=get_emoji_icon("sagarproof"),
            style="success"
        )
    ])
    
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text=f"Top 5 Best Sellers",
            callback_data="menu_top_sellers",
            icon_custom_emoji_id=get_emoji_icon("sagartop"),
            style="primary"
        )
    ])

    extras_row = []
    if sys_status == 'ON' or is_reseller:
        extras_row.append(InlineKeyboardButton(
            text="Reseller Panel", callback_data="menu_reseller_dash",
            icon_custom_emoji_id=get_emoji_icon("reseller"),
            style="success"
        ))
    if vip_system == 'ON':
        extras_row.append(InlineKeyboardButton(
            text="VIP Club", callback_data="menu_vip_dash",
            style="success"
        ))
    if extras_row:
        kb.inline_keyboard.append(extras_row)
        
    return kb

def back_kb(callback: str = "back_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="BACK", callback_data=callback,
                icon_custom_emoji_id=get_emoji_icon("back"),
                style="danger"
            )
        ]]
    )

def admin_kb() -> InlineKeyboardMarkup:
    status = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
    status_val = status[0] if status else 'ON'
    vip_status = db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True)
    vip_val = vip_status[0] if vip_status else 'OFF'
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Bot Statistics", callback_data="admin_view_stats", style="success")],
        [InlineKeyboardButton(text="🏆 Top 5 Sellers Top", callback_data="admin_top_sellers", style="primary")],
        [
            InlineKeyboardButton(text=f"FamPay: {'🟢 ON' if get_setting('gateway_fampay_enabled', 'ON') == 'ON' else '🔴 OFF'}", callback_data="admin_toggle_fampay", style="success" if get_setting('gateway_fampay_enabled', 'ON') == 'ON' else "danger"),
            InlineKeyboardButton(text=f"ZapUPI: {'🟢 ON' if get_setting('gateway_zapupi_enabled', 'ON') == 'ON' else '🔴 OFF'}", callback_data="admin_toggle_zapupi", style="success" if get_setting('gateway_zapupi_enabled', 'ON') == 'ON' else "danger"),
            InlineKeyboardButton(text=f"BharatPe: {'🟢 ON' if get_setting('gateway_BharatPe_enabled', 'ON') == 'ON' else '🔴 OFF'}", callback_data="admin_toggle_BharatPe", style="success" if get_setting('gateway_BharatPe_enabled', 'ON') == 'ON' else "danger")
        ],
        [InlineKeyboardButton(text="👥 User Control Panel", callback_data="admin_user_control_start", style="success")],
        [InlineKeyboardButton(text="🚫 Block / Unblock User", callback_data="admin_block_user_start", style="danger"), InlineKeyboardButton(text="🗑️ Delete User", callback_data="admin_delete_user_start", style="danger")],
        [InlineKeyboardButton(text="➕ Add User Balance", callback_data="admin_balance_add_start", style="success"), InlineKeyboardButton(text="➖ Remove User Balance", callback_data="admin_balance_remove_list", style="danger")],
        [
            InlineKeyboardButton(text="➕ Add Product", callback_data="admin_add_prod", style="success"),
            InlineKeyboardButton(text="📦 Manage Products", callback_data="admin_manage_prods", style="success")
        ],
        [InlineKeyboardButton(text="➕ Add Product Category", callback_data="admin_add_category", style="success"), InlineKeyboardButton(text="✏️ Edit Product Category", callback_data="admin_edit_category", style="primary")],
        [InlineKeyboardButton(text="🗑️ Delete Category", callback_data="admin_delete_category", style="danger")],
        [InlineKeyboardButton(text="🗑️ Delete Panel", callback_data="admin_delete_panel", style="danger"), InlineKeyboardButton(text="🙈 Hide Panel", callback_data="admin_hide_panel", style="primary")],
        [InlineKeyboardButton(text="👥 Total User", callback_data="admin_total_users", style="success"), InlineKeyboardButton(text="💰 User Check Balance", callback_data="admin_user_balances", style="success")],
        [InlineKeyboardButton(text="🛠 Product Maintenance", callback_data="admin_product_maintenance", style="danger")],
        [InlineKeyboardButton(text="✏️ Panel Name Change", callback_data="admin_panel_name_change", style="success")],
        [InlineKeyboardButton(text="🎬 Set Product Demo", callback_data="admin_set_product_demo", style="success")],
        [
            InlineKeyboardButton(text="👑 Reseller Mgmt", callback_data="admin_reseller_menu", style="success"),
            InlineKeyboardButton(text="🎰 Spin Settings", callback_data="admin_spin_menu", style="success")
        ],
        [
            InlineKeyboardButton(text="➕ Add Reseller", callback_data="reseller_make", style="success"),
            InlineKeyboardButton(text="➖ Remove Reseller", callback_data="reseller_remove", style="danger")
        ],
        [
            InlineKeyboardButton(text="🎟 Create Coupon", callback_data="admin_create_coupon", style="success"),
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast_btn", style="success")
        ],
        [
            InlineKeyboardButton(text="🎫 View Tickets", callback_data="admin_view_tickets", style="success"),
            InlineKeyboardButton(text="📹 Tutorial Video", callback_data="admin_set_video", style="success")
        ],
        [
            InlineKeyboardButton(text="🔗 All Files Link", callback_data="admin_set_all_files", style="success"),
            InlineKeyboardButton(text="🧾 Selling Proof Link", callback_data="admin_set_selling_proof", style="success")
        ],
        [
            InlineKeyboardButton(text="🎨 Edit All Emojis", callback_data="admin_edit_emojis", style="success")
        ],
        [InlineKeyboardButton(text="🔑 BharatPe API Setup", callback_data="admin_setup_BharatPe", style="primary")],
        [
            InlineKeyboardButton(text="⚙️ FamPay Setup", callback_data="admin_setup_fampay", style="success"),
            InlineKeyboardButton(text="🔐 ZapUPI API Setup", callback_data="admin_setup_zapupi", style="success")
        ],
        [InlineKeyboardButton(text="🪙 Binance Setup", callback_data="admin_setup_binance", style="success")],
        [
            InlineKeyboardButton(text="✏️ Edit UI Texts", callback_data="admin_edit_ui_menu", style="success"),
            InlineKeyboardButton(text="📝 Edit Reseller Price", callback_data="admin_edit_reseller_price", style="success")
        ],
        [
            InlineKeyboardButton(text="💰 Reseller Fee", callback_data="admin_set_reseller_fee", style="success"),
            InlineKeyboardButton(text="💳 Min Balance", callback_data="admin_set_reseller_min", style="success")
        ],
        [
            InlineKeyboardButton(text="🔑 Reseller API Key", callback_data="admin_set_reseller_api_key", style="success"),
            InlineKeyboardButton(text="🌐 Reseller API URL", callback_data="admin_set_reseller_api_url", style="success")
        ],
        [
            InlineKeyboardButton(text="📞 Set Support Links", callback_data="admin_set_support_links", style="success"),
            InlineKeyboardButton(text="🎨 Set Category Emojis", callback_data="admin_set_category_emojis", style="success")
        ],
        [
            InlineKeyboardButton(text="🖼 Set Panel Emojis", callback_data="admin_set_panel_emojis", style="success")
        ],
        [
            InlineKeyboardButton(
                text=f"Bot Status: {status_val} {'🟢' if status_val == 'ON' else '🔴'}",
                callback_data="admin_toggle_bot",
                style="success" if status_val == 'ON' else "danger"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"VIP System: {vip_val} {'🟢' if vip_val == 'ON' else '🔴'}",
                callback_data="admin_toggle_vip_sys",
                style="success" if vip_val == 'ON' else "danger"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🆕 New User Notification: {get_setting('new_user_start_message', 'ON')} {'🟢' if str(get_setting('new_user_start_message', 'ON')).upper() == 'ON' else '🔴'}",
                callback_data="admin_toggle_new_user_notification",
                style="success" if str(get_setting('new_user_start_message', 'ON')).upper() == 'ON' else "danger"
            )
        ]
    ])
    return kb

def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="Back to Admin", callback_data="admin_panel_back",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ]])

# ==============================================================================
# 8. NOTIFICATIONS
# ==============================================================================
async def send_advanced_notification(user_id: int, notif_type: str, amount: float, product: str = None, key: str = None, gateway: str = "FamPay") -> None:
    user_info = db_query("SELECT first_name, phone, username, is_reseller, is_vip FROM users WHERE user_id=?", (user_id,), fetchone=True)
    
    name = user_info[0] if user_info else "Unknown"
    phone = user_info[1] if user_info and user_info[1] else "Not Provided"
    username = f"@{user_info[2]}" if user_info and user_info[2] else "None"
    
    tags = []
    if user_info and user_info[3]: tags.append("👑 Reseller")
    if user_info and user_info[4]: tags.append("🌟 VIP")
    tag_str = " | ".join(tags) if tags else "👤 Regular"
        
    time_now = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    
    if notif_type == "ORDER":
        title = "🛒 <b>NEW ORDER PROCESSED!</b> 🛒"
        details = (f"📦 <b>Product:</b> {product}\n🔑 <b>Key:</b> <code>{key}</code>\n💰 <b>Amount Paid:</b> ₹{amount:.2f}\n📅 <b>Time:</b> {time_now}")
    else:
        title = "💰 <b>NEW WALLET DEPOSIT!</b> 💰"
        details = (f"💵 <b>Amount Added:</b> ₹{amount:.2f}\n🧾 <b>Gateway:</b> {gateway}\n🆔 <b>Reference:</b> <code>{product}</code>\n📅 <b>Time:</b> {time_now}")

    msg = f"{title}\n━━━━━━━━━━━━━━━━━━\n👤 <b>Name:</b> {name}\n🆔 <b>User ID:</b> <code>{user_id}</code>\n📱 <b>Phone:</b> {phone}\n🔗 <b>Username:</b> {username}\n🏷 <b>Status:</b> {tag_str}\n━━━━━━━━━━━━━━━━━━\n{details}"
    try: 
        await bot.send_message(ADMIN_ID, msg, parse_mode='HTML')
    except Exception as e: 
        logger.error(f"Failed to send admin notification: {e}")

# ==============================================================================
# BharatPe gateway helpers
async def generate_BharatPe_qr(user_id: int, amount: float, upi_id: str = None) -> Dict[str, Any]:
    """Create a fixed-amount QR through AnujBots Gram UPI Gateway."""
    api_key = get_setting("BharatPe_api_key", BharatPe_API_KEY).strip()
    if not api_key or api_key in ("YOUR_BharatPe_API_KEY", "PASTE_YOUR_BharatPe_API_KEY_HERE"):
        return {"status": "error", "message": "AnujBots BharatPe API key not configured"}

    try:
        timeout = aiohttp.ClientTimeout(total=15, connect=5, sock_read=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                BharatPe_QR_URL,
                params={"api_key": api_key, "amount": f"{float(amount):.2f}"},
                headers={"Accept": "application/json"},
            ) as resp:
                raw = await resp.text()
                try:
                    result = json.loads(raw)
                except Exception:
                    logger.error("AnujBots QR returned non-JSON (HTTP %s): %s", resp.status, raw[:500])
                    return {"status": "error", "message": "Gateway returned an invalid response"}
                if resp.status != 200 or not (result.get("status") is True or str(result.get("status", "")).lower() in ("success", "ok")):
                    detail = result.get("message") or result.get("error") or f"Gateway HTTP {resp.status}"
                    logger.error("AnujBots BharatPe QR rejected request (HTTP %s): %s", resp.status, raw[:800])
                    return {"status": "error", "message": str(detail)[:300]}
                data = result.get("data") if isinstance(result.get("data"), dict) else {}
                qr_url = data.get("qr_url") or data.get("qr_image") or data.get("image_url") or data.get("qr_code_url")
                gateway_order = data.get("order_id") or data.get("txn_id") or data.get("transaction_id")
                if not qr_url or not gateway_order:
                    return {"status": "error", "message": "Gateway response did not include a usable QR URL or order ID. Check gateway API response/settings."}
                return {
                    "status": "success",
                    "data": {
                        **data,
                        "qr_url": qr_url,
                        "order_id": str(gateway_order),
                        "upi_id": data.get("upi_id") or upi_id or get_setting("BharatPe_upi_id", ""),
                    },
                }
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception("AnujBots QR generation error")
        return {"status": "error", "message": "Gateway connection failed. Please retry shortly."}


async def verify_BharatPe_payment(utr: str) -> Dict[str, Any]:
    """Verify BharatPe by the customer's UTR; AnujBots documents UTR-based verification."""
    api_key = get_setting("BharatPe_api_key", BharatPe_API_KEY).strip()
    utr = str(utr or "").strip()
    if not api_key or api_key in ("YOUR_BharatPe_API_KEY", "PASTE_YOUR_BharatPe_API_KEY_HERE"):
        return {"status": "error", "message": "AnujBots BharatPe API key not configured"}
    if not re.fullmatch(r"\d{12}", utr):
        return {"status": "error", "message": "Please enter the 12-digit UTR from your UPI payment."}

    try:
        timeout = aiohttp.ClientTimeout(total=12, connect=4, sock_read=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                BharatPe_VERIFY_URL,
                params={"api_key": api_key, "utr": utr},
                headers={"Accept": "application/json"},
            ) as resp:
                raw = await resp.text()
                try:
                    result = json.loads(raw)
                except Exception:
                    logger.warning("AnujBots verify returned non-JSON (HTTP %s): %s", resp.status, raw[:500])
                    return {"status": "error", "message": "Gateway returned an invalid verification response"}
                data = result.get("data") if isinstance(result.get("data"), dict) else {}
                if resp.status == 200 and (result.get("status") is True or str(result.get("status", "")).lower() == "success"):
                    returned_utr = str(data.get("utr") or "").strip()
                    if returned_utr and returned_utr != utr:
                        return {"status": "error", "message": "Gateway returned a different UTR; payment was not credited."}
                    normalized_data = dict(data)
                    normalized_data.setdefault("sender_name", data.get("payer") or data.get("sender_name") or "Unknown")
                    normalized_data.setdefault("payment_time_ist", data.get("payment_time") or data.get("payment_time_ist") or "")
                    return {"status": "success", "data": normalized_data}
                return {"status": "error", "message": result.get("message") or "Transaction not found or not verified yet."}
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("AnujBots UTR verification request failed")
        return {"status": "error", "message": "Verification service temporarily unavailable. Please retry."}



# 9. FAMPAY PAYMENT FUNCTIONS
# ==============================================================================

async def generate_fampay_qr(user_id: int, amount: float, upi_id: str = None) -> Dict[str, Any]:
    """Generate a FamGateway QR and return its QR URL + gateway order ID."""
    api_key = get_setting("fampay_api_key", FAMPAY_API_KEY)
    if not api_key or api_key == "YOUR_FAMPAY_API_KEY":
        return {"status": "error", "message": "FamGateway API key not configured"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                FAMPAY_QR_URL,
                params={
                    "api_key": api_key,
                    "amount": f"{float(amount):.2f}",
                    "customer_name": f"Telegram User {user_id}",
                },
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                raw = await resp.text()
                try:
                    result = await resp.json(content_type=None)
                except Exception:
                    logger.error("FamGateway QR returned non-JSON: %s", raw[:1000])
                    return {"status": "error", "message": "Invalid FamGateway QR response"}

                if resp.status != 200:
                    return {
                        "status": "error",
                        "message": result.get("message") or f"FamGateway HTTP {resp.status}",
                    }

                if str(result.get("status", "")).lower() != "success":
                    return {
                        "status": "error",
                        "message": result.get("message") or "FamGateway QR generation failed",
                    }

                data = result.get("data") or {}
                qr_url = data.get("qr_url")
                gateway_order = data.get("order_id")

                if not qr_url:
                    return {"status": "error", "message": "FamGateway did not return a QR URL"}
                if not gateway_order:
                    return {"status": "error", "message": "FamGateway did not return an order ID"}

                # Normalize to the structure already used by SAGAR SHOP.py.
                return {
                    "status": "success",
                    "data": {
                        **data,
                        "qr_url": qr_url,
                        "order_id": gateway_order,
                        "upi_id": data.get("upi_id") or upi_id or get_setting("fampay_upi_id", ""),
                    },
                }
    except Exception as e:
        logger.exception("FamGateway QR generation error")
        return {"status": "error", "message": str(e)}


async def verify_fampay_payment(order_id: str) -> Dict[str, Any]:
    """Verify FamGateway using concurrent endpoint checks to reduce payment latency."""
    api_key = get_setting("fampay_api_key", FAMPAY_API_KEY)
    order_id = str(order_id or "").strip()

    if not api_key or api_key == "YOUR_FAMPAY_API_KEY" or api_key == "PASTE_YOUR_FAMPAY_API_KEY_HERE":
        return {"status": "error", "message": "FamGateway API key not configured"}
    if not order_id:
        return {"status": "error", "message": "Order ID is missing"}

    def is_success(data):
        if not isinstance(data, dict):
            return False
        status = str(data.get("status", "")).strip().lower()
        if status in ("success", "paid", "completed", "confirmed"):
            return True
        d = data.get("data")
        if isinstance(d, dict):
            dstatus = str(d.get("status", "")).strip().lower()
            if dstatus in ("success", "paid", "completed", "confirmed"):
                return True
            if d.get("is_paid") is True or d.get("paid") is True:
                return True
        return data.get("is_paid") is True or data.get("paid") is True

    def normalize(data):
        if not isinstance(data, dict):
            return {}
        d = data.get("data")
        return d if isinstance(d, dict) else data

    timeout = aiohttp.ClientTimeout(total=8, connect=3, sock_read=5)
    cache_buster = int(time.time() * 1000)

    async def check_endpoint(session, url, params, headers, label):
        try:
            async with session.get(
                url, params=params, headers=headers, timeout=timeout
            ) as resp:
                if resp.status != 200:
                    logger.debug("FamGateway %s returned HTTP %s", label, resp.status)
                    return None
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    return None
                if not is_success(data):
                    return None
                payload = normalize(data)
                returned_order = str(
                    payload.get("order_id") or data.get("order_id") or ""
                ).strip()
                # Reject a success response explicitly tied to a different order.
                if returned_order and returned_order != order_id:
                    logger.warning("FamGateway %s returned mismatched order ID", label)
                    return None
                return {"status": "success", "data": payload}
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("FamGateway %s verification request failed: %s", label, exc)
            return None

    # Check all supported verification routes at the same time. Sequential fallbacks
    # could take up to 60 seconds; parallel checks return as soon as one confirms paid.
    connector = aiohttp.TCPConnector(limit=6, ttl_dns_cache=300)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            asyncio.create_task(check_endpoint(
                session, FAMPAY_VERIFY_URL,
                {"order_id": order_id, "_": cache_buster},
                {"X-Api-Key": api_key, "Accept": "application/json"},
                "header-auth",
            )),
            asyncio.create_task(check_endpoint(
                session, FAMPAY_VERIFY_URL,
                {"api_key": api_key, "order_id": order_id, "_": cache_buster},
                {"Accept": "application/json"},
                "query-auth",
            )),
            asyncio.create_task(check_endpoint(
                session, FAMPAY_STATUS_URL,
                {"order_id": order_id, "_": cache_buster},
                {"Accept": "application/json"},
                "checkout-status",
            )),
        ]
        try:
            for completed in asyncio.as_completed(tasks):
                result = await completed
                if result and result.get("status") == "success":
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    return result
            return {
                "status": "pending",
                "message": "Payment not verified yet. Complete payment and wait for automatic verification.",
            }
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()

async def run_payment_verification(user_id: int, order_id: str, reply_target: Any) -> None:
    """Run payment verification with FamPay."""
    txn = db_query("SELECT amount_inr, status, timestamp, qr_url, upi_id, expires_at FROM transactions WHERE order_id=?", (order_id,), fetchone=True)
    if not txn:
        err = "❌ Invalid or Fake Order ID detected in system!"
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(err, show_alert=True)
        else: await reply_target.answer(err)
        return
    
    if txn[1] == 'paid':
        msg = "✅ This payment has already been securely credited to your wallet."
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
        else: await reply_target.answer(msg)
        return
    elif txn[1] == 'expired':
        msg = "❌ This order has expired. Please create a new deposit request."
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
        else: await reply_target.answer(msg)
        return
    
    # Do a quick foreground check; the automatic verifier continues polling in the
    # background, so don't make the user's button/start action wait through long retries.
    result = await verify_fampay_payment(order_id)
    if result.get("status") != "success":
        await asyncio.sleep(0.35)
        result = await verify_fampay_payment(order_id)
    
    if result.get("status") == "success":
        # Keep legacy/deep-link verification safe too: the same atomic credit path
        # used by the background verifier prevents double balance crediting.
        txn_data = result.get("data", {})
        credited = await _credit_verified_transaction(order_id, txn[0], user_id, txn_data, "FamPay")
        if not credited:
            msg = "✅ This payment has already been securely credited to your wallet."
            if isinstance(reply_target, CallbackQuery):
                await reply_target.answer(msg, show_alert=True)
            else:
                await reply_target.answer(msg)
        elif isinstance(reply_target, CallbackQuery):
            try:
                await reply_target.answer("✅ Payment verified automatically.")
            except Exception:
                pass
        return
    elif result.get("status") == "error":
        # Check if transaction failed specifically
        error_msg = result.get("message", "Payment not received yet")
        if "Transaction failed" in error_msg or "not received" in error_msg:
            fail_msg = f"❌ {error_msg}\n\n<i>Please make sure you sent the exact amount to the correct UPI ID.</i>"
            if isinstance(reply_target, CallbackQuery): await reply_target.answer(fail_msg, show_alert=True)
            else: await reply_target.answer(fail_msg)
        else:
            # Still pending - show QR again with status
            pending_msg = f"⏳ <b>Payment Status: PENDING</b>\n\n{error_msg}\n\n<i>Please wait a moment and verify again.</i>"
            if isinstance(reply_target, CallbackQuery): await reply_target.answer(pending_msg, show_alert=True)
            else: await reply_target.answer(pending_msg)
    else:
        err = f"⚠️ Gateway Error: {result.get('message', 'Unknown Error')}"
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(err, show_alert=True)
        else: await reply_target.answer(err)

async def _delete_payment_qr_message(user_id: int, order_id: str = None) -> None:
    """Delete the Telegram QR/payment message after success or expiry."""
    try:
        if order_id:
            row = db_query("SELECT qr_message_id FROM transactions WHERE order_id=? AND user_id=?", (order_id, user_id), fetchone=True)
            message_id = row[0] if row and row[0] else None
        else:
            row = db_query("SELECT qr_message_id FROM transactions WHERE user_id=? AND status='pending' ORDER BY timestamp DESC LIMIT 1", (user_id,), fetchone=True)
            message_id = row[0] if row and row[0] else None
        if message_id:
            try:
                await bot.delete_message(chat_id=user_id, message_id=int(message_id))
            except Exception:
                pass
        # Backward compatibility with older records that only stored this setting.
        legacy = get_setting(f"qr_msg_{user_id}", "")
        if legacy and (not message_id or str(legacy) != str(message_id)):
            try:
                await bot.delete_message(chat_id=user_id, message_id=int(legacy))
            except Exception:
                pass
        set_setting(f"qr_msg_{user_id}", "")
    except Exception:
        logger.exception("Failed to delete payment QR message for user %s", user_id)


def _claim_paid_transaction(order_id: str) -> bool:
    """Atomically claim a pending order so balance is credited only once."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE transactions SET status='paid' WHERE order_id=? AND status='pending'", (order_id,))
        changed = cur.rowcount == 1
        if changed:
            conn.commit()
        else:
            conn.rollback()
        return changed
    except Exception:
        conn.rollback()
        logger.exception("Atomic payment claim failed for order %s", order_id)
        return False
    finally:
        conn.close()


async def _credit_verified_transaction(order_id: str, fallback_amount: float, user_id: int, txn_data: dict, source: str = "FamPay") -> bool:
    """Credit a verified transaction exactly once, notify admin/user, and remove QR."""
    if not _claim_paid_transaction(order_id):
        # Another verifier may have completed the same payment concurrently.
        # If it was marked paid, still make a best-effort cleanup of its payment post.
        paid_row = db_query("SELECT status FROM transactions WHERE order_id=? AND user_id=?", (order_id, user_id), fetchone=True)
        if paid_row and paid_row[0] == "paid":
            await _delete_payment_qr_message(user_id, order_id)
        return False

    # Remove the payment QR/link post immediately once the gateway confirms payment.
    # Do this before balance/product notifications so later processing errors cannot
    # leave a stale payment post visible to the user.
    await _delete_payment_qr_message(user_id, order_id)

    amount_received = safe_float(txn_data.get("amount"), safe_float(fallback_amount, 0.0))
    utr = txn_data.get("utr") or txn_data.get("transaction_id") or "N/A"
    # FamGateway responses may use different keys for the payer/sender name,
    # and some versions nest transaction details one level deeper.
    sender_name = "Unknown"
    sender_sources = [txn_data]
    for nested_key in ("data", "payment", "transaction", "payer", "customer"):
        nested = txn_data.get(nested_key)
        if isinstance(nested, dict):
            sender_sources.append(nested)
    sender_keys = (
        "sender_name", "payer_name", "account_holder_name", "account_name",
        "customer_name", "name", "sender", "payer", "paid_by", "from_name",
        "upi_payer_name", "remitter_name", "bank_name"
    )
    for sender_source in sender_sources:
        for sender_key in sender_keys:
            candidate = sender_source.get(sender_key)
            if isinstance(candidate, dict):
                candidate = candidate.get("name") or candidate.get("display_name")
            if isinstance(candidate, str) and candidate.strip():
                sender_name = candidate.strip()
                break
        if sender_name != "Unknown":
            break
    payment_time = txn_data.get("payment_time_ist") or datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")

    # A verified reseller setup payment activates reseller access directly.
    # It must not be credited to the wallet as a normal deposit.
    pending_reseller = get_setting(f"pending_reseller_upgrade_{user_id}", "").strip()
    if pending_reseller:
        user_row = db_query(
            "SELECT is_reseller FROM users WHERE user_id=?",
            (user_id,), fetchone=True
        )
        if user_row and not user_row[0]:
            db_query(
                "UPDATE users SET is_reseller=1, reseller_since=?, account_type='Reseller' WHERE user_id=?",
                (datetime.now().strftime("%Y-%m-%d"), user_id)
            )
            log_activity(user_id, "UPGRADED_RESELLER", f"Payment verified: {order_id}; gateway: {source}")
            set_setting(f"pending_reseller_upgrade_{user_id}", "")
            set_setting(f"pending_gateway_amount_{user_id}", "")
            set_setting(f"pending_gateway_amount_{user_id}", "")
            try:
                await bot.send_message(
                    user_id,
                    f"🎉 <b>RESELLER ACTIVATED SUCCESSFULLY!</b>\n\n"
                    f"✅ Payment of <b>{fmt_curr(amount_received)}</b> verified via {html_lib.escape(str(source))}.\n"
                    f"👑 Your reseller access is now active. Wholesale prices are unlocked.",
                    reply_markup=main_menu_kb(user_id),
                    parse_mode="HTML"
                )
                await bot.send_message(
                    ADMIN_ID,
                    f"👑 <b>NEW PAID RESELLER</b>\n"
                    f"👤 User ID: <code>{user_id}</code>\n"
                    f"💰 Setup payment: {fmt_curr(amount_received)}\n"
                    f"🧾 Order ID: <code>{html_lib.escape(str(order_id))}</code>\n"
                    f"🏦 Gateway: {html_lib.escape(str(source))}",
                    parse_mode="HTML"
                )
            except Exception:
                logger.exception("Could not send reseller activation notification")
        else:
            set_setting(f"pending_reseller_upgrade_{user_id}", "")
        return True

    db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount_received, user_id))

    # A product shortfall payment is different from a normal wallet top-up:
    # restore the exact product intent and continue the existing purchase flow
    # immediately, so the customer receives the key instead of the main menu.
    pending_product = get_setting(f"pending_product_purchase_{user_id}", "").strip()
    if pending_product.isdigit():
        set_setting(f"pending_product_purchase_{user_id}", "")
        try:
            await bot.send_message(
                user_id,
                f"✅ Payment verified ({fmt_curr(amount_received)}).\n🔑 App Ka Key Automatic Banke Aayega Wait",
                parse_mode="HTML",
            )
            from types import SimpleNamespace
            purchase_message = await bot.send_message(user_id, "⏳ Preparing your product key...")
            async def _noop_answer(*args, **kwargs):
                return None
            purchase_call = SimpleNamespace(
                from_user=SimpleNamespace(id=user_id),
                message=purchase_message,
                data=f"buy_{int(pending_product)}",
                answer=_noop_answer,
            )
            # _process_buy edits this same placeholder into the final
            # PURCHASE SUCCESSFUL message. Do not delete it afterwards: that
            # would also delete the delivered key and success details.
            await _process_buy(purchase_call)
        except Exception:
            logger.exception("Payment verified but automatic product delivery failed for user %s", user_id)
            await bot.send_message(
                user_id,
                f"⚠️ Payment verified, but automatic delivery could not finish. Your payment amount {fmt_curr(amount_received)} has been added to your wallet. Please tap Buy Key and retry, or contact {ADMIN_CONTACT}.",
                reply_markup=main_menu_kb(user_id),
                parse_mode="HTML",
            )
        await send_advanced_notification(user_id, "DEPOSIT", amount_received, product=utr, gateway=source)
        log_activity(user_id, "PRODUCT_PAYMENT_AUTO_SUCCESS", f"Product ID: {pending_product}, Amount: {amount_received}, Gateway: {source}, Order: {order_id}, UTR: {utr}")
        return True

    # Ordinary wallet top-ups still return to the main menu and never buy a product.
    set_setting(f"pending_product_purchase_{user_id}", "")
    try:
        await bot.send_message(
            user_id,
            f"🎉 <b>PAYMENT SUCCESSFUL!</b>\n\n"
            f"✅ <b>{fmt_curr(amount_received)}</b>\n"
            + (
                f"👤 <b>Sender Name:</b> {html_lib.escape(sender_name)}\n"
                if str(source).lower().startswith("fampay") else ""
            )
            + f"🧾 <b>UTR:</b> <code>{html_lib.escape(str(utr))}</code>",
            reply_markup=main_menu_kb(user_id),
            parse_mode='HTML'
        )
    except Exception:
        logger.exception("Could not send wallet top-up success message to user %s", user_id)

    await send_advanced_notification(user_id, "DEPOSIT", amount_received, product=utr, gateway=source)
    log_activity(user_id, "DEPOSIT_AUTO_SUCCESS", f"Amount: {amount_received}, Gateway: {source}, Order: {order_id}, UTR: {utr}")
    return True


async def auto_verify_task() -> None:
    """Fast automatic FamGateway verifier. No Verify Payment button is required."""
    await asyncio.sleep(1)
    while True:
        try:
            api_key = get_setting("fampay_api_key", "")
            zap_key = get_setting("zapupi_zap_key", "").strip()
            if (api_key and api_key != "YOUR_FAMPAY_API_KEY") or zap_key:
                pending_txns = db_query(
                    "SELECT order_id, user_id, amount_inr, timestamp, expires_at FROM transactions WHERE status='pending' ORDER BY timestamp ASC",
                    fetchall=True
                ) or []
                for order_id, user_id, amount, ts, expires_at in pending_txns:
                    # Always ask the gateway first; this avoids expiring a payment that settled near the deadline.
                    is_zapupi = str(order_id).startswith("ZAPUPI")
                    is_bharatpe = str(order_id).startswith("BharatPe")
                    if is_zapupi and zap_key:
                        result = await verify_zapupi_payment(order_id)
                    elif is_bharatpe:
                        # BharatPe transactions are verified only against the user's submitted 12-digit UTR.
                        result = {"status": "pending"}
                    elif not is_zapupi and api_key and api_key != "YOUR_FAMPAY_API_KEY":
                        result = await verify_fampay_payment(order_id)
                    else:
                        result = {"status": "pending"}
                    if result.get("status") == "success":
                        await _credit_verified_transaction(order_id, amount, user_id, result.get("data") or {}, "ZapUPI Auto" if is_zapupi else ("BharatPe" if is_bharatpe else "FamPay Auto"))
                        continue

                    if expires_at and time.time() > float(expires_at):
                        # Mark expired only if it is still pending, preventing a race with a successful verifier.
                        conn = sqlite3.connect(DB_PATH, timeout=30)
                        try:
                            cur = conn.cursor()
                            cur.execute("UPDATE transactions SET status='expired' WHERE order_id=? AND status='pending'", (order_id,))
                            expired_now = cur.rowcount == 1
                            conn.commit()
                        finally:
                            conn.close()
                        if expired_now:
                            await _delete_payment_qr_message(user_id, order_id)
                            try:
                                minutes = max(1, int(round((float(expires_at) - float(ts)) / 60))) if expires_at else 5
                            except Exception:
                                minutes = 5
                            try:
                                await bot.send_message(
                                    user_id,
                                    f"⏳ <b>QR Code Expired!</b>\nYour {minutes}-minute payment window for order <code>{order_id}</code> has timed out. Please generate a new QR code.",
                                    parse_mode='HTML'
                                )
                            except Exception:
                                pass
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("FamPay fast auto-verifier sweep failed")

        # ~1 second polling gives fast activation while still yielding to the event loop.
        await asyncio.sleep(1)

# ==============================================================================
# 10. ONBOARDING & START
# ==============================================================================
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    try:
        await message.answer_sticker(WELCOME_STICKER_ID)
    except Exception:
        pass

    args = message.text.split()
    if len(args) > 1 and args[1].startswith("v_"):
        order_id = args[1].split("v_", 1)[1]
        msg = await message.answer(
            "🔄 <b>Verifying your payment securely...</b>\n<i>Connecting to gateway...</i>",
            parse_mode='HTML'
        )
        await run_payment_verification(message.from_user.id, order_id, msg)
        return

    referred_by = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referred_by = int(args[1].split("_", 1)[1])
        except Exception:
            referred_by = None

    user_id = message.from_user.id
    current_username = message.from_user.username or ""
    existing = db_query(
        "SELECT phone, first_name, username FROM users WHERE user_id=?",
        (user_id,),
        fetchone=True
    )

    is_new_user = not existing
    phone_verified = bool(existing and existing[0])

    if is_new_user:
        db_query(
            "INSERT OR IGNORE INTO users "
            "(user_id, first_name, username, referred_by, joined_date) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                user_id,
                message.from_user.first_name or "",
                current_username,
                referred_by,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )
        log_activity(user_id, "ACCOUNT_CREATED")

        # New-user notification is sent directly from /start, independently
        # of contact verification, so a later handler error cannot suppress it.
        if new_user_start_message_enabled():
            username = f"@{current_username}" if current_username else "Not set"
            joined_at = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
            admin_msg = (
                "🆕 <b>NEW USER STARTED THE BOT</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Name:</b> {html_lib.escape(message.from_user.first_name or 'User')}\n"
                f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
                f"🔗 <b>Username:</b> {html_lib.escape(username)}\n"
                "📱 <b>Phone:</b> Not verified yet\n"
                f"📅 <b>Joined:</b> {joined_at}"
            )
            try:
                await bot.send_message(ADMIN_ID, admin_msg, parse_mode='HTML')
                log_activity(user_id, "NEW_USER_ADMIN_NOTIFICATION_SENT")
            except Exception:
                logger.exception("New user notification failed for user %s", user_id)
    else:
        db_query(
            "UPDATE users SET first_name=?, username=? WHERE user_id=?",
            (message.from_user.first_name or "", current_username, user_id)
        )
        log_activity(user_id, "CMD_START")

    if not phone_verified:
        await message.answer(
            "<b>🛡 VERIFICATION REQUIRED</b>\n\n"
            "To safeguard your orders and account, we need to verify your contact.\n"
            "👇 <b>Tap the button below once:</b>",
            parse_mode='HTML',
            reply_markup=contact_kb()
        )
        return

    await send_main_menu(message)


@dp.message(F.contact)
async def handle_contact(message: Message):
    contact = message.contact
    user_id = message.from_user.id

    # Accept only the user's own Telegram contact.
    if contact.user_id is not None and contact.user_id != user_id:
        await message.answer(
            "❌ <b>Security Alert:</b> Please share your OWN contact using the button.",
            parse_mode='HTML',
            reply_markup=contact_kb()
        )
        return

    phone = (contact.phone_number or "").strip()
    if not phone:
        await message.answer(
            "❌ Phone number was not received. Please tap <b>📱 Verify Contact</b> again.",
            parse_mode='HTML',
            reply_markup=contact_kb()
        )
        return

    existing = db_query(
        "SELECT phone, referred_by FROM users WHERE user_id=?",
        (user_id,),
        fetchone=True
    )

    # Ensure the user row exists before saving verification.
    if not existing:
        db_query(
            "INSERT OR IGNORE INTO users "
            "(user_id, first_name, username, joined_date) VALUES (?, ?, ?, ?)",
            (
                user_id,
                message.from_user.first_name or "",
                message.from_user.username or "",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )
        existing = db_query(
            "SELECT phone, referred_by FROM users WHERE user_id=?",
            (user_id,),
            fetchone=True
        )

    was_missing = not existing or not existing[0]
    referrer_id = existing[1] if existing and len(existing) > 1 else None

    # Save the phone BEFORE showing the main menu. This prevents /start from
    # asking for contact verification again.
    db_query(
        "UPDATE users SET phone=?, first_name=?, username=? WHERE user_id=?",
        (
            phone,
            message.from_user.first_name or "",
            message.from_user.username or "",
            user_id
        )
    )

    # IMPORTANT: Notify admin immediately when a NEW user shares their contact.
    # The notification reads the phone directly from the saved DB value, so
    # admin sees the actual number instead of "Not verified yet".
    if was_missing and new_user_start_message_enabled():
        try:
            admin_name = html_lib.escape(message.from_user.first_name or "User")
            admin_username = (
                f"@{html_lib.escape(message.from_user.username)}"
                if message.from_user.username else "Not set"
            )
            contact_time = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
            contact_notification = (
                "📱 <b>NEW USER CONTACT VERIFIED</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Name:</b> {admin_name}\n"
                f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
                f"🔗 <b>Username:</b> {admin_username}\n"
                f"📞 <b>Phone Number:</b> <code>{html_lib.escape(phone)}</code>\n"
                "✅ <b>Status:</b> Contact shared successfully\n"
                f"📅 <b>Time:</b> {contact_time}"
            )
            await bot.send_message(
                ADMIN_ID,
                contact_notification,
                parse_mode='HTML'
            )
            log_activity(
                user_id,
                "NEW_USER_CONTACT_ADMIN_NOTIFICATION_SENT",
                f"Phone: {phone}"
            )
        except Exception:
            logger.exception(
                "New-user contact notification failed for user %s",
                user_id
            )

    if referrer_id and was_missing and referrer_id != user_id:
        db_query(
            "UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id=?",
            (referrer_id,)
        )
        try:
            await bot.send_message(
                referrer_id,
                f"🎉 <b>Referral Success!</b>\n"
                f"User <b>{html_lib.escape(message.from_user.first_name or 'User')}</b> "
                "joined using your link!",
                parse_mode='HTML'
            )
        except Exception:
            pass

    log_activity(user_id, "CONTACT_VERIFIED", f"Phone: {phone}")

    try:
        await message.answer(
            "✅ <b>Contact verification successful!</b>\n\n"
            "Welcome to THAKUR MODS SHOP. Your account is now verified.",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode='HTML'
        )
    except Exception:
        pass

    await send_main_menu(message)


async def send_main_menu(ctx: Any, user_id: Optional[int] = None):
    # Callback message.from_user is the bot, not the person who pressed the button.
    # Accept the real Telegram user ID explicitly for callback-driven menu returns.
    user_id = user_id if user_id is not None else ctx.from_user.id
    u = db_query(
        "SELECT user_id, first_name, account_type, balance, orders_count, spent, "
        "referrals_count, joined_date, is_reseller, reseller_since, total_saved, is_vip "
        "FROM users WHERE user_id=?",
        (user_id,),
        fetchone=True
    )

    if not u:
        u = (
            user_id, ctx.from_user.first_name or "", "Regular", 0.0,
            0, 0.0, 0, "", 0, "", 0.0, 0
        )

    text = get_ui_text("start_menu", u=u)
    kb = main_menu_kb(user_id)

    if isinstance(ctx, Message):
        await ctx.answer(text, reply_markup=kb, parse_mode='HTML')
    else:
        await ctx.message.edit_text(text, reply_markup=kb, parse_mode='HTML')


@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    # Photo captions cannot be converted to the text-based start menu reliably.
    # Remove the old payment/cancel post, then send a fresh main menu message.
    await state.clear()
    log_activity(call.from_user.id, "RETURN_MAIN_MENU")
    try:
        await call.message.delete()
    except Exception:
        pass
    await send_main_menu(call.message, user_id=call.from_user.id)
    try:
        await call.answer()
    except Exception:
        pass

# ==============================================================================
# 11. ADD BALANCE
# ==============================================================================
@dp.callback_query(F.data == "menu_add_balance")
async def select_gateway_menu(call: CallbackQuery):
    log_activity(call.from_user.id, "VIEW_ADD_BALANCE")
    text = get_ui_text("add_balance_menu")
    gateway_rows = []
    fampay_on = get_setting("gateway_fampay_enabled", "ON") == "ON" and bool(get_setting("fampay_api_key", "")) and get_setting("fampay_api_key", "") != "YOUR_FAMPAY_API_KEY"
    zapupi_on = get_setting("gateway_zapupi_enabled", "ON") == "ON" and bool(get_setting("zapupi_zap_key", "").strip())
    if fampay_on:
        gateway_rows.append([InlineKeyboardButton(text="UPI PAY (FamPay)", callback_data="gateway_inr", icon_custom_emoji_id=get_emoji_icon("fampay"), style="primary")])
    if zapupi_on:
        gateway_rows.append([InlineKeyboardButton(text="INDIAN FAST PAY (ZAPUPI)", callback_data="gateway_zapupi", icon_custom_emoji_id=get_emoji_icon("upi"), style="success")])
    bharatpe_on = get_setting("gateway_BharatPe_enabled", "ON") == "ON" and get_setting("BharatPe_api_key", "").strip() not in ("", "YOUR_BharatPe_API_KEY", "PASTE_YOUR_BharatPe_API_KEY_HERE")
    if bharatpe_on:
        gateway_rows.append([InlineKeyboardButton(text="PAY BHARATPE UPI", callback_data="gateway_BharatPe", icon_custom_emoji_id=get_emoji_icon("BharatPe"), style="primary")])
    if not gateway_rows:
        gateway_rows.append([InlineKeyboardButton(text="⚠️ Payment Gateway Not Configured", callback_data="menu_add_balance", style="danger")])
    # Custom amount is gateway-specific and is available inside the ZapUPI menu,
    # not on the main Add Balance screen.
    gateway_rows.extend([
        [InlineKeyboardButton(text="BINANCE PAY", callback_data="gateway_crypto", icon_custom_emoji_id=get_emoji_icon("binance"), style="primary")],
        [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    kb = InlineKeyboardMarkup(inline_keyboard=gateway_rows)
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

# ==============================================================================
# 12. FAMPAY UPI PAYMENT FLOW
# ==============================================================================
@dp.callback_query(F.data == "gateway_inr")
async def add_balance_inr(call: CallbackQuery):
    if get_setting("gateway_fampay_enabled", "ON") != "ON":
        return await call.answer("FamPay gateway is OFF.", show_alert=True)
    text = f"💵 <b>— FAMPAY UPI DEPOSIT —</b> 💵\n\nSelect amount to deposit:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="₹50", callback_data="pay_50", style="primary"), InlineKeyboardButton(text="₹100", callback_data="pay_100", style="primary")],
        [InlineKeyboardButton(text="₹200", callback_data="pay_200", style="primary"), InlineKeyboardButton(text="₹500", callback_data="pay_500", style="primary")],
        [InlineKeyboardButton(text="₹1000", callback_data="pay_1000", style="primary"), InlineKeyboardButton(text="₹2000", callback_data="pay_2000", style="primary")],
        [InlineKeyboardButton(text="✏️ Custom Amount", callback_data="custom_deposit_keypad", style="primary")],
        [InlineKeyboardButton(text="Back", callback_data="menu_add_balance", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "gateway_BharatPe")
async def BharatPe_amount_menu(call: CallbackQuery):
    if get_setting("gateway_BharatPe_enabled", "ON") != "ON":
        return await call.answer("BharatPe gateway is OFF.", show_alert=True)
    if get_setting("BharatPe_api_key", "").strip() in ("", "YOUR_BharatPe_API_KEY", "PASTE_YOUR_BharatPe_API_KEY_HERE"):
        return await call.answer("BharatPe API key is not configured.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="₹50", callback_data="bharat_pay_50", style="primary"), InlineKeyboardButton(text="₹100", callback_data="bharat_pay_100", style="primary")],
        [InlineKeyboardButton(text="₹200", callback_data="bharat_pay_200", style="primary"), InlineKeyboardButton(text="₹500", callback_data="bharat_pay_500", style="primary")],
        [InlineKeyboardButton(text="₹1000", callback_data="bharat_pay_1000", style="primary"), InlineKeyboardButton(text="₹2000", callback_data="bharat_pay_2000", style="primary")],
        [InlineKeyboardButton(text="✏️ Custom Amount", callback_data="custom_BharatPe_keypad", style="primary")],
        [InlineKeyboardButton(text="Back", callback_data="menu_add_balance", style="danger")]
    ])
    await call.message.edit_text("💵 <b>— BHARATPE UPI DEPOSIT —</b> 💵\n\nSelect amount to deposit:", reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("bharat_pay_"))
async def BharatPe_pay_amount(call: CallbackQuery):
    try: amount = float(call.data.rsplit("_", 1)[1])
    except (ValueError, IndexError): return await call.answer("Invalid amount.", show_alert=True)
    await call.message.edit_text(f"⏳ <b>Generating BharatPe QR for {fmt_curr(amount)}...</b>", parse_mode="HTML")
    await generate_BharatPe_order(call.from_user.id, amount, call.message)
    await call.answer()

@dp.callback_query(F.data == "gateway_zapupi")
async def zapupi_amount_menu(call: CallbackQuery):
    if get_setting("gateway_zapupi_enabled", "ON") != "ON":
        return await call.answer("ZapUPI gateway is OFF.", show_alert=True)
    if not get_setting("zapupi_zap_key", "").strip():
        return await call.answer("ZapUPI API Key admin ne abhi set nahi ki hai.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="₹50", callback_data="zap_pay_50", style="primary"), InlineKeyboardButton(text="₹100", callback_data="zap_pay_100", style="primary")],
        [InlineKeyboardButton(text="₹200", callback_data="zap_pay_200", style="primary"), InlineKeyboardButton(text="₹500", callback_data="zap_pay_500", style="primary")],
        [InlineKeyboardButton(text="₹1000", callback_data="zap_pay_1000", style="primary"), InlineKeyboardButton(text="₹2000", callback_data="zap_pay_2000", style="primary")],
        [InlineKeyboardButton(text="✏️ CUSTOM AMOUNT", callback_data="custom_zapupi_keypad", style="success")],
        [InlineKeyboardButton(text="❌ CANCEL / BACK", callback_data="menu_add_balance", style="danger")]
    ])
    await call.message.edit_text("🏦 <b>ZAPUPI DEPOSIT</b>\n\nPayment amount select karein:", reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("zap_pay_"))
async def zapupi_pay_amount(call: CallbackQuery):
    try:
        amount = float(call.data.rsplit("_", 1)[1])
    except (ValueError, IndexError):
        return await call.answer("Invalid amount.", show_alert=True)
    await call.message.edit_text("⏳ <b>ZapUPI payment link generate ho raha hai...</b>", parse_mode="HTML")
    await generate_zapupi_order(call.from_user.id, amount, call.message)
    await call.answer()

async def generate_zapupi_order(user_id: int, amount: float, message_obj: Message) -> None:
    """Create a ZapUPI order and show the payment link; auto-verifier credits only confirmed payments."""
    key = get_setting("zapupi_zap_key", "").strip()
    if not key:
        return await message_obj.edit_text("⚠️ Admin ko Admin Panel → ZapUPI API Setup mein Zap Key set karni hogi.", reply_markup=back_kb("gateway_zapupi"), parse_mode="HTML")
    order_id = f"ZAPUPI{user_id}{int(time.time())}"
    product_intent = get_setting(f"pending_product_purchase_{user_id}", "").strip()
    remark = f"Product {product_intent} UID {user_id}" if product_intent.isdigit() else f"Wallet Deposit | UID {user_id}"
    payload = {"zap_key": key, "amount": str(round(float(amount), 2)), "order_id": order_id, "remark": remark}
    base = get_setting("webhook_base_url", "").strip()
    if base:
        payload.update({"success_url": base.rstrip('/') + "/zapupi/success", "failed_url": base.rstrip('/') + "/zapupi/failed", "timeout_url": base.rstrip('/') + "/zapupi/timeout", "webhook_url": base.rstrip('/') + "/zapupi/webhook"})
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post("https://pay.zapupi.com/api/create-order", json=payload) as resp:
                raw = await resp.text()
                try: data = json.loads(raw)
                except Exception: data = {}
        set_setting("zapupi_debug_last_create", raw[:1500])
        payment_url = data.get("payment_url") if isinstance(data, dict) else None
        if not isinstance(data, dict) or str(data.get("status", "")).lower() != "success" or not payment_url:
            err = data.get("message", "ZapUPI ne valid payment link return nahi kiya.") if isinstance(data, dict) else "Invalid ZapUPI response"
            return await message_obj.edit_text(f"❌ <b>ZapUPI order create nahi hua.</b>\n\n<code>{html_lib.escape(str(err))}</code>", reply_markup=back_kb("gateway_zapupi"), parse_mode="HTML")
        expires_at = int(time.time()) + 300
        db_query("INSERT OR REPLACE INTO transactions (order_id,user_id,amount_inr,status,timestamp,qr_url,upi_id,expires_at) VALUES (?,?,?,'pending',?,?,?,?)", (order_id, user_id, float(amount), int(time.time()), payment_url, "ZapUPI", expires_at))
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Pay Now — ZapUPI", url=payment_url, icon_custom_emoji_id=get_emoji_icon("upi"), style="success")],
            [InlineKeyboardButton(text="Cancel Payment", callback_data=f"cancel_payment_{order_id}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
        ])
        caption = (
            f'<tg-emoji emoji-id="{get_emoji_icon("upi")}">🏦</tg-emoji> <b>ZAPUPI PAYMENT</b>\n\n'
            f'<tg-emoji emoji-id="{get_emoji_icon("money_icon")}">💰</tg-emoji> <b>Amount:</b> {fmt_curr(amount)}\n'
            f'<tg-emoji emoji-id="{get_emoji_icon("history")}">🧾</tg-emoji> <b>Order ID:</b> <code>{html_lib.escape(str(order_id))}</code>\n'
            f'<tg-emoji emoji-id="{get_emoji_icon("info_icon")}">⏳</tg-emoji> <b>Expires:</b> 5 minutes\n\n'
            f'<tg-emoji emoji-id="{get_emoji_icon("point_down")}">👇</tg-emoji> Pay using the button above.\n'
            f'<tg-emoji emoji-id="{get_emoji_icon("check_icon")}">⚡</tg-emoji> Payment is checked automatically.\n'
            f'<tg-emoji emoji-id="{get_emoji_icon("shield_icon")}">🔒</tg-emoji> Balance is added only after ZapUPI confirms success.'
        )
        await message_obj.delete()
        sent = await bot.send_message(user_id, caption, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        db_query("UPDATE transactions SET qr_message_id=? WHERE order_id=? AND user_id=?", (sent.message_id, order_id, user_id))
        set_setting(f"qr_msg_{user_id}", str(sent.message_id))
        log_activity(user_id, "GENERATE_ZAPUPI_ORDER", f"Amount: {amount}, Order ID: {order_id}")
    except Exception as e:
        logger.exception("ZapUPI order creation failed")
        try: await message_obj.edit_text(f"❌ <b>ZapUPI error:</b>\n<code>{html_lib.escape(str(e))}</code>", reply_markup=back_kb("gateway_zapupi"), parse_mode="HTML")
        except Exception: pass

async def verify_zapupi_payment(order_id: str) -> Dict[str, Any]:
    key = get_setting("zapupi_zap_key", "").strip()
    if not key or not order_id:
        return {"status": "pending", "message": "ZapUPI key/order missing"}
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post("https://pay.zapupi.com/api/order-status", json={"zap_key": key, "order_id": order_id}) as resp:
                raw = await resp.text()
                try: data = json.loads(raw)
                except Exception: data = {}
        set_setting("zapupi_debug_last_check", raw[:1500])
        if isinstance(data, dict) and str(data.get("status", "")).lower() == "success":
            d = data.get("data") or {}
            if isinstance(d, dict) and (str(d.get("status", "")).lower() in ("success", "paid", "completed", "successful") or d.get("paid") is True):
                return {"status": "success", "data": d}
        return {"status": "pending", "message": "Payment not verified yet"}
    except Exception as e:
        set_setting("zapupi_debug_last_check", f"[REQUEST FAILED] {e}")
        return {"status": "pending", "message": str(e)}

@dp.callback_query(F.data.in_({"custom_deposit_keypad", "custom_zapupi_keypad", "custom_any_gateway_keypad", "custom_BharatPe_keypad"}))
async def show_custom_keypad(call: CallbackQuery, state: FSMContext):
    gateway = ("choose" if call.data == "custom_any_gateway_keypad" else
               "zapupi" if call.data == "custom_zapupi_keypad" else
               "BharatPe" if call.data == "custom_BharatPe_keypad" else "fampay")
    await state.set_state(UserStates.custom_amount_input)
    await state.update_data(amount_str="0", payment_gateway=gateway)
    cancel_target = ("gateway_zapupi" if gateway == "zapupi" else
                     "gateway_BharatPe" if gateway == "BharatPe" else
                     "menu_add_balance" if gateway == "choose" else "gateway_inr")
    await show_keypad(call.message, cancel_callback=cancel_target)

async def show_keypad(message: Message, amount_str: str = "0", cancel_callback: str = "gateway_inr"):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="      1      ", callback_data="kp_1", style="primary"), InlineKeyboardButton(text="      2      ", callback_data="kp_2", style="primary"), InlineKeyboardButton(text="      3      ", callback_data="kp_3", style="primary")],
        [InlineKeyboardButton(text="      4      ", callback_data="kp_4", style="primary"), InlineKeyboardButton(text="      5      ", callback_data="kp_5", style="primary"), InlineKeyboardButton(text="      6      ", callback_data="kp_6", style="primary")],
        [InlineKeyboardButton(text="      7      ", callback_data="kp_7", style="primary"), InlineKeyboardButton(text="      8      ", callback_data="kp_8", style="primary"), InlineKeyboardButton(text="      9      ", callback_data="kp_9", style="primary")],
        [InlineKeyboardButton(text="    ⌫    ", callback_data="kp_backspace", style="danger"), InlineKeyboardButton(text="      0      ", callback_data="kp_0", style="primary"), InlineKeyboardButton(text="    C    ", callback_data="kp_clear", style="danger")],
        [InlineKeyboardButton(text=f"✅ Confirm (₹{amount_str})", callback_data="kp_confirm", style="success")],
        [InlineKeyboardButton(text="↩️ Cancel", callback_data=cancel_callback, icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    text = f"💵 <b>Enter Amount (₹):</b>\n\nCurrent: ₹{amount_str}"
    await message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("kp_"), UserStates.custom_amount_input)
async def keypad_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount_str = data.get("amount_str", "0")
    action = call.data[len("kp_"):]
    if action == "confirm":
        if amount_str == "0":
            await call.answer("Amount cannot be zero.", show_alert=True)
            return
        try:
            amount = float(amount_str)
            if amount < 1:
                await call.answer("Minimum deposit is ₹1.", show_alert=True)
                return
            gateway = data.get("payment_gateway", "fampay")
            try:
                await call.answer("Processing amount…")
            except Exception:
                pass
            await state.clear()
            if gateway == "choose":
                try: await call.message.delete()
                except Exception: pass
                await start_wallet_payment_gateway_choice(call.from_user.id, amount)
            elif gateway == "zapupi":
                await call.message.edit_text("⏳ <b>Generating ZapUPI payment link...</b>", parse_mode="HTML")
                await generate_zapupi_order(call.from_user.id, amount, call.message)
            elif gateway == "BharatPe":
                await call.message.edit_text(f"⏳ <b>Generating BharatPe QR for {fmt_curr(amount)}...</b>", parse_mode="HTML")
                await generate_BharatPe_order(call.from_user.id, amount, call.message)
            else:
                await call.message.edit_text("⏳ <b>Generating Secure QR Code...</b>", parse_mode="HTML")
                await generate_fampay_order(call.from_user.id, amount, call.message)
        except ValueError:
            await call.answer("Invalid amount.", show_alert=True)
        return
    if action == "backspace":
        if len(amount_str) > 1: amount_str = amount_str[:-1]
        else: amount_str = "0"
    elif action == "clear":
        amount_str = "0"
    else:
        if amount_str == "0": amount_str = action
        else: amount_str += action
        if len(amount_str) > 6: amount_str = amount_str[:6]
    await state.update_data(amount_str=amount_str)
    gateway = data.get("payment_gateway", "fampay")
    cancel_target = ("gateway_zapupi" if gateway == "zapupi" else
                     "gateway_BharatPe" if gateway == "BharatPe" else
                     "menu_add_balance" if gateway == "choose" else "gateway_inr")
    await show_keypad(call.message, amount_str, cancel_callback=cancel_target)
    await call.answer()

@dp.callback_query(F.data.startswith("pay_"))
async def process_fampay_payment_callback(call: CallbackQuery):
    inr_amount = float(call.data.split("_")[1])
    await call.message.edit_text("⏳ <b>Generating Secure QR Code via FamGateway...</b>", parse_mode='HTML')
    await generate_fampay_order(call.from_user.id, inr_amount, call.message)

async def generate_fampay_order(user_id: int, inr_amount: float, message_obj: Message) -> None:
    """Generate FamPay QR and show the QR image directly with Verify/Cancel buttons."""
    api_key = get_setting("fampay_api_key", "")
    if not api_key or api_key == "YOUR_FAMPAY_API_KEY":
        return await message_obj.edit_text(
            "⚠️ FamGateway is currently offline.\nAdmin needs to set the FamGateway API Key.",
            reply_markup=back_kb("gateway_inr"),
            parse_mode="HTML"
        )

    # Admin must configure the receiving UPI ID after saving the API key.
    upi_id = get_setting("fampay_upi_id", "")
    if not upi_id:
        return await message_obj.edit_text(
            "⚠️ UPI ID is not configured.\nAdmin needs to set the UPI ID in FamPay Setup.",
            reply_markup=back_kb("gateway_inr"),
            parse_mode="HTML"
        )

    current_time = int(time.time())
    default_order_id = f"FAMPAY{user_id}{current_time}"

    # FamGateway QR flow from cord.py:
    # https://famgateway.in/api/qr.php?api_key=...&amount=...
    result = await generate_fampay_qr(user_id, inr_amount, upi_id)

    if result.get("status") != "success":
        error_msg = result.get("message", "Unknown error")
        return await message_obj.edit_text(
            f"❌ <b>QR Generation Failed:</b>\n{error_msg}",
            reply_markup=back_kb("gateway_inr"),
            parse_mode="HTML"
        )

    data = result.get("data") or {}
    qr_url = data.get("qr_url")
    order_id = data.get("order_id") or default_order_id
    upi_id = data.get("upi_id") or upi_id
    # Fixed 5-minute payment window for this bot.
    expires_at_str = "5 Minutes"
    created_at = data.get("created_at_ist") or datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    if not qr_url:
        return await message_obj.edit_text(
            "❌ <b>QR Generation Failed:</b>\nFamPay response me QR image URL nahi mila.",
            reply_markup=back_kb("gateway_inr"),
            parse_mode="HTML"
        )

    # Always start a fresh 5-minute local payment window from QR creation.
    expires_timestamp = int(time.time() + 300)

    # Save the transaction as pending.
    db_query(
        "INSERT OR REPLACE INTO transactions "
        "(order_id, user_id, amount_inr, status, timestamp, qr_url, upi_id, expires_at) "
        "VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)",
        (order_id, user_id, inr_amount, current_time, qr_url, upi_id, expires_timestamp)
    )

    # IMPORTANT: show the QR image itself, not a "View QR Code" link.
    # This follows the QR presentation used in SAGAR_MODS_SHOP.
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="❌ Cancel Payment",
                callback_data=f"cancel_payment_{order_id}",
                style="danger"
            )
        ]
    ])

    caption = (
        f'<tg-emoji emoji-id="{get_emoji_icon("fampay")}">💳</tg-emoji> <b>PAYMENT QR CODE</b>\n\n'
        f'<tg-emoji emoji-id="{get_emoji_icon("money_icon")}">💵</tg-emoji> <b>Amount:</b> {fmt_curr(inr_amount)}\n'
        f'<tg-emoji emoji-id="{get_emoji_icon("history")}">🆔</tg-emoji> <b>Order ID:</b> <code>{html_lib.escape(str(order_id))}</code>\n'
        f'<tg-emoji emoji-id="{get_emoji_icon("upi")}">🏦</tg-emoji> <b>UPI ID:</b> <code>{html_lib.escape(str(upi_id))}</code>\n'
        f'<tg-emoji emoji-id="{get_emoji_icon("info_icon")}">⏳</tg-emoji> <b>Expires:</b> {html_lib.escape(str(expires_at_str))}\n\n'
        f'<tg-emoji emoji-id="{get_emoji_icon("wallet")}">📱</tg-emoji> Scan this QR with your UPI app and pay the exact amount.\n'
        f'<tg-emoji emoji-id="{get_emoji_icon("check_icon")}">⚡</tg-emoji> Payment is verified automatically after successful payment.\n\n'
        f'<tg-emoji emoji-id="{get_emoji_icon("shield_icon")}">🔒</tg-emoji> Your balance will be credited automatically after verification.'
    )

    log_activity(
        user_id,
        "GENERATE_INVOICE_FAMPAY",
        f"Amount: {inr_amount}, Order ID: {order_id}"
    )

    # Delete the temporary "Generating..." message and send the QR as a photo.
    try:
        await message_obj.delete()
    except Exception:
        pass

    try:
        sent_qr = await bot.send_photo(
            chat_id=user_id,
            photo=qr_url,
            caption=caption,
            reply_markup=kb,
            parse_mode="HTML"
        )
        # Store QR message id so Cancel/Verify can cleanly remove it.
        try:
            qr_message_id = sent_qr.message_id
            db_query("UPDATE transactions SET qr_message_id=? WHERE order_id=? AND user_id=?", (qr_message_id, order_id, user_id))
            set_setting(f"qr_msg_{user_id}", str(qr_message_id))
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Failed to send FamPay QR photo: {e}")
        # Fallback: keep the QR URL accessible if Telegram cannot fetch the image.
        await bot.send_message(
            chat_id=user_id,
            text=caption + f"\n\n🖼 <a href=\"{qr_url}\">Open QR Code</a>",
            reply_markup=kb,
            parse_mode="HTML"
        )

async def generate_BharatPe_order(user_id: int, inr_amount: float, message_obj: Message) -> None:
    """Generate BharatPe QR and show the QR image directly with Verify/Cancel buttons."""
    api_key = get_setting("BharatPe_api_key", "")
    if not api_key or api_key in ("YOUR_BharatPe_API_KEY", "PASTE_YOUR_BharatPe_API_KEY_HERE"):
        return await message_obj.edit_text(
            "⚠️ AnujBots BharatPe gateway is not configured.\nAdmin needs to set the AnujBots API key.",
            reply_markup=back_kb("gateway_inr"),
            parse_mode="HTML"
        )

    # AnujBots returns the receiving UPI ID in the QR API response.
    upi_id = get_setting("BharatPe_upi_id", "")

    current_time = int(time.time())
    default_order_id = f"BharatPe{user_id}{current_time}"

    # AnujBots QR API: https://gateway.anujbots.in/qr.php?api_key=...&amount=...
    result = await generate_BharatPe_qr(user_id, inr_amount, upi_id)

    if result.get("status") != "success":
        error_msg = result.get("message", "Unknown error")
        return await message_obj.edit_text(
            f"❌ <b>QR Generation Failed:</b>\n{error_msg}",
            reply_markup=back_kb("gateway_inr"),
            parse_mode="HTML"
        )

    data = result.get("data") or {}
    qr_url = data.get("qr_url")
    order_id = data.get("order_id") or default_order_id
    upi_id = data.get("upi_id") or upi_id
    # Fixed 5-minute payment window for this bot.
    expires_at_str = "5 Minutes"
    created_at = data.get("created_at_ist") or datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    if not qr_url:
        return await message_obj.edit_text(
            "❌ <b>QR Generation Failed:</b>\nAnujBots response me QR image URL nahi mila.",
            reply_markup=back_kb("gateway_inr"),
            parse_mode="HTML"
        )

    # Always start a fresh 5-minute local payment window from QR creation.
    expires_timestamp = int(time.time() + 300)

    # Save the transaction as pending.
    db_query(
        "INSERT OR REPLACE INTO transactions "
        "(order_id, user_id, amount_inr, status, timestamp, qr_url, upi_id, expires_at) "
        "VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)",
        (order_id, user_id, inr_amount, current_time, qr_url, upi_id, expires_timestamp)
    )

    # IMPORTANT: show the QR image itself, not a "View QR Code" link.
    # This follows the QR presentation used in SAGAR_MODS_SHOP.
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Submit UTR / Verify",
                callback_data=f"submit_utr_{order_id}",
                style="success"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Cancel Payment",
                callback_data=f"cancel_payment_{order_id}",
                style="danger"
            )
        ]
    ])

    caption = (
        f'<tg-emoji emoji-id="{get_emoji_icon("paytm")}">💳</tg-emoji> <b>PAYMENT QR CODE</b>\n\n'
        f'<tg-emoji emoji-id="{get_emoji_icon("money_icon")}">💵</tg-emoji> <b>Amount:</b> {fmt_curr(inr_amount)}\n'
        f'<tg-emoji emoji-id="{get_emoji_icon("history")}">🆔</tg-emoji> <b>Order ID:</b> <code>{html_lib.escape(str(order_id))}</code>\n'
        f'<tg-emoji emoji-id="{get_emoji_icon("upi")}">🏦</tg-emoji> <b>UPI ID:</b> <code>{html_lib.escape(str(upi_id))}</code>\n'
        f'<tg-emoji emoji-id="{get_emoji_icon("info_icon")}">⏳</tg-emoji> <b>Expires:</b> {html_lib.escape(str(expires_at_str))}\n\n'
        f'<tg-emoji emoji-id="{get_emoji_icon("wallet")}">📱</tg-emoji> Scan this QR with your UPI app and pay the exact amount.\n'
        f'<tg-emoji emoji-id="{get_emoji_icon("check_icon")}">⚡</tg-emoji> After paying, tap <b>Submit UTR / Verify</b> and enter the 12-digit UTR from your UPI app.\n\n'
        f'<tg-emoji emoji-id="{get_emoji_icon("shield_icon")}">🔒</tg-emoji> Balance is credited only after the gateway confirms the UTR.'
    )

    log_activity(
        user_id,
        "GENERATE_INVOICE_BharatPe",
        f"Amount: {inr_amount}, Order ID: {order_id}"
    )

    # Delete the temporary "Generating..." message and send the QR as a photo.
    try:
        await message_obj.delete()
    except Exception:
        pass

    try:
        sent_qr = await bot.send_photo(
            chat_id=user_id,
            photo=qr_url,
            caption=caption,
            reply_markup=kb,
            parse_mode="HTML"
        )
        # Store QR message id so Cancel/Verify can cleanly remove it.
        try:
            qr_message_id = sent_qr.message_id
            db_query("UPDATE transactions SET qr_message_id=? WHERE order_id=? AND user_id=?", (qr_message_id, order_id, user_id))
            set_setting(f"qr_msg_{user_id}", str(qr_message_id))
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Failed to send BharatPe QR photo: {e}")
        # Fallback: keep the QR URL accessible if Telegram cannot fetch the image.
        await bot.send_message(
            chat_id=user_id,
            text=caption + f"\n\n🖼 <a href=\"{qr_url}\">Open QR Code</a>",
            reply_markup=kb,
            parse_mode="HTML"
        )



async def _delete_utr_flow_messages(user_id: int, order_id: str, extra_ids=None) -> None:
    """Delete UTR prompt, verification statuses, and failed UTR attempt messages."""
    key = f"utr_flow_messages_{user_id}_{order_id}"
    try:
        saved = json.loads(get_setting(key, "[]") or "[]")
    except Exception:
        saved = []
    ids = set(int(x) for x in saved if str(x).isdigit())
    ids.update(int(x) for x in (extra_ids or []) if str(x).isdigit())
    for message_id in ids:
        try:
            await bot.delete_message(chat_id=user_id, message_id=message_id)
        except Exception:
            pass
    set_setting(key, "[]")


async def _remember_utr_messages(user_id: int, order_id: str, *message_ids: int) -> None:
    key = f"utr_flow_messages_{user_id}_{order_id}"
    try:
        ids = json.loads(get_setting(key, "[]") or "[]")
    except Exception:
        ids = []
    ids.extend(int(x) for x in message_ids if x)
    set_setting(key, json.dumps(sorted(set(ids))))


@dp.callback_query(F.data.startswith("submit_utr_"))
async def submit_BharatPe_utr_start(call: CallbackQuery, state: FSMContext):
    order_id = call.data[len("submit_utr_"):]
    row = db_query(
        "SELECT amount_inr, status, expires_at FROM transactions WHERE order_id=? AND user_id=?",
        (order_id, call.from_user.id), fetchone=True
    )
    if not row:
        return await call.answer("Payment order not found.", show_alert=True)
    if row[1] == "paid":
        return await call.answer("This payment is already completed.", show_alert=True)
    if row[1] != "pending" or (row[2] and time.time() > float(row[2])):
        return await call.answer("This payment QR expired. Please generate a new one.", show_alert=True)
    await state.set_state(UserStates.wait_for_BharatPe_utr)
    await state.update_data(BharatPe_order_id=order_id, utr_flow_message_ids=[])
    prompt = await call.message.answer(
        "🧾 <b>Enter your 12-digit UTR</b> from the UPI app's payment details.\n\n"
        "Do not send your UPI PIN or OTP. Type /cancel to stop.",
        parse_mode="HTML"
    )
    await state.update_data(utr_prompt_message_id=prompt.message_id)
    await _remember_utr_messages(call.from_user.id, order_id, prompt.message_id)
    await call.answer()


@dp.message(UserStates.wait_for_BharatPe_utr)
async def submit_BharatPe_utr(m: Message, state: FSMContext):
    data = await state.get_data()
    order_id = str(data.get("BharatPe_order_id") or "")
    if (m.text or "").strip().lower() == "/cancel":
        await _delete_utr_flow_messages(m.from_user.id, order_id, [m.message_id])
        await state.clear()
        set_setting(f"pending_product_purchase_{m.from_user.id}", "")
        # Return to the same Add Balance gateway-selection post.
        text = get_ui_text("add_balance_menu")
        rows = []
        if get_setting("gateway_fampay_enabled", "ON") == "ON" and get_setting("fampay_api_key", "") not in ("", "YOUR_FAMPAY_API_KEY"):
            rows.append([InlineKeyboardButton(text="UPI PAY (FamPay)", callback_data="gateway_inr", icon_custom_emoji_id=get_emoji_icon("fampay"), style="primary")])
        if get_setting("gateway_BharatPe_enabled", "ON") == "ON" and get_setting("BharatPe_api_key", "").strip() not in ("", "YOUR_BharatPe_API_KEY", "PASTE_YOUR_BharatPe_API_KEY_HERE"):
            rows.append([InlineKeyboardButton(text="PAY WITH BHARATPE UPI", callback_data="gateway_BharatPe", icon_custom_emoji_id=get_emoji_icon("BharatPe"), style="primary")])
        if get_setting("gateway_zapupi_enabled", "ON") == "ON" and get_setting("zapupi_zap_key", "").strip():
            rows.append([InlineKeyboardButton(text="INDIAN FAST PAY (ZAPUPI)", callback_data="gateway_zapupi", icon_custom_emoji_id=get_emoji_icon("upi"), style="success")])
        rows.extend([[InlineKeyboardButton(text="BINANCE PAY", callback_data="gateway_crypto", icon_custom_emoji_id=get_emoji_icon("binance"), style="primary")], [InlineKeyboardButton(text="BACK TO MAIN MENU", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
        return await m.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")

    utr = (m.text or "").strip()
    if not re.fullmatch(r"\d{12}", utr):
        msg = await m.answer("❌ <b>Invalid UTR format.</b> Payment karne ke baad apna sahi 12-digit UTR bhejein. PIN/OTP share na karein.", parse_mode="HTML")
        if order_id:
            await _remember_utr_messages(m.from_user.id, order_id, m.message_id, msg.message_id)
        return
    row = db_query(
        "SELECT amount_inr, status, expires_at FROM transactions WHERE order_id=? AND user_id=?",
        (order_id, m.from_user.id), fetchone=True
    )
    if not row or row[1] != "pending":
        await state.clear()
        return await m.answer("This payment request is no longer pending. Please create a new QR if needed.")
    if row[2] and time.time() > float(row[2]):
        db_query("UPDATE transactions SET status='expired' WHERE order_id=? AND user_id=? AND status='pending'", (order_id, m.from_user.id))
        await _delete_utr_flow_messages(m.from_user.id, order_id, [m.message_id])
        await state.clear()
        return await m.answer("⏳ QR expired. Please create a new payment QR.")

    await _remember_utr_messages(m.from_user.id, order_id, m.message_id)
    verifying = await m.answer("⏳ Verifying UTR with AnujBots gateway…")
    await _remember_utr_messages(m.from_user.id, order_id, verifying.message_id)
    result = await verify_BharatPe_payment(utr)
    if result.get("status") != "success":
        msg = await m.answer(
            "❌ <b>UTR not verified.</b> Agar payment kar chuke hain, apne UPI app se sahi 12-digit UTR check karke bhejein.\n\n"
            "Payment confirm hone par UTR verification messages automatically delete ho jayenge. PIN/OTP kabhi na bhejein.",
            parse_mode="HTML"
        )
        await _remember_utr_messages(m.from_user.id, order_id, msg.message_id)
        return
    txn_data = result.get("data") or {}
    received = safe_float(txn_data.get("amount"), -1)
    expected = safe_float(row[0], 0)
    if received < 0 or abs(received - expected) > 0.009:
        msg = await m.answer(
            f"❌ <b>Amount mismatch.</b> QR amount: {fmt_curr(expected)}; gateway-confirmed amount: {fmt_curr(received if received >= 0 else 0)}.\n"
            "Balance credit nahi hua. Sahi payment UTR bhejein ya admin se contact karein.",
            parse_mode="HTML"
        )
        await _remember_utr_messages(m.from_user.id, order_id, msg.message_id)
        return
    txn_data["utr"] = txn_data.get("utr") or utr
    utr_setting_key = f"anujbots_used_BharatPe_utr_{utr}"
    previously_used_for = get_setting(utr_setting_key, "").strip()
    if previously_used_for and previously_used_for != order_id:
        msg = await m.answer("❌ This UTR has already been used for another order. Balance was not credited.")
        await _remember_utr_messages(m.from_user.id, order_id, msg.message_id)
        return
    set_setting(utr_setting_key, order_id)
    # Once the gateway confirms the UTR, remove the payment QR post as well as the UTR prompt/status messages.
    await _delete_utr_flow_messages(m.from_user.id, order_id, [m.message_id, verifying.message_id])
    await _delete_payment_qr_message(m.from_user.id, order_id)
    await state.clear()
    await _credit_verified_transaction(order_id, expected, m.from_user.id, txn_data, "AnujBots BharatPe")




@dp.callback_query(F.data.startswith("verify_"))
async def manual_verify_callback(call: CallbackQuery):
    order_id = call.data.split("_", 1)[1]
    await run_payment_verification(call.from_user.id, order_id, call)


@dp.callback_query(F.data.startswith("cancel_payment_"))
async def cancel_payment_callback(call: CallbackQuery):
    """Cancel a pending payment, delete its QR, and show clean cancellation options."""
    order_id = call.data[len("cancel_payment_"):]
    user_id = call.from_user.id
    txn = db_query(
        "SELECT status FROM transactions WHERE order_id=? AND user_id=?",
        (order_id, user_id), fetchone=True
    )
    if not txn:
        return await call.answer("❌ Payment order not found.", show_alert=True)
    if txn[0] == "paid":
        return await call.answer("⚠️ This payment is already completed.", show_alert=True)

    db_query("UPDATE transactions SET status='cancelled' WHERE order_id=? AND user_id=?", (order_id, user_id))
    # Keep the reseller intent only if another pending reseller payment exists.
    pending_reseller_txn = db_query(
        "SELECT 1 FROM transactions WHERE user_id=? AND status='pending' AND order_id!=? LIMIT 1",
        (user_id, order_id), fetchone=True
    )
    if not pending_reseller_txn:
        set_setting(f"pending_reseller_upgrade_{user_id}", "")
    log_activity(user_id, "PAYMENT_CANCELLED", f"Order: {order_id}")
    # Delete the QR/photo itself so it cannot remain above the cancellation message.
    try:
        await call.message.delete()
    except Exception:
        pass
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Add Balance Again", callback_data=f"retry_deposit_{order_id}", style="success")],
        [InlineKeyboardButton(text="↩️ Back to Menu", callback_data="back_main", style="primary")]
    ])
    try:
        await bot.send_message(user_id, "❌ <b>Payment Cancelled</b>", reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await call.answer("❌ Payment cancelled.")

# ==============================================================================
# 13. BINANCE CRYPTO PAYMENT
# ==============================================================================
async def start_wallet_payment_gateway_choice(user_id: int, amount: float):
    fampay_on = get_setting("gateway_fampay_enabled", "ON") == "ON" and bool(get_setting("fampay_api_key", "")) and get_setting("fampay_api_key", "") != "YOUR_FAMPAY_API_KEY"
    zapupi_on = get_setting("gateway_zapupi_enabled", "ON") == "ON" and bool(get_setting("zapupi_zap_key", "").strip())
    bharatpe_on = get_setting("gateway_BharatPe_enabled", "ON") == "ON" and get_setting("BharatPe_api_key", "").strip() not in ("", "YOUR_BharatPe_API_KEY", "PASTE_YOUR_BharatPe_API_KEY_HERE")
    if fampay_on and not zapupi_on and not bharatpe_on:
        msg = await bot.send_message(user_id, f"⏳ Generating FamPay QR for {fmt_curr(amount)}...")
        return await generate_fampay_order(user_id, amount, msg)
    if zapupi_on and not fampay_on and not bharatpe_on:
        msg = await bot.send_message(user_id, f"⏳ Generating ZapUPI payment for {fmt_curr(amount)}...")
        return await generate_zapupi_order(user_id, amount, msg)
    if bharatpe_on and not fampay_on and not zapupi_on:
        msg = await bot.send_message(user_id, f"⏳ Generating BharatPe QR for {fmt_curr(amount)}...")
        return await generate_BharatPe_order(user_id, amount, msg)
    if not fampay_on and not zapupi_on and not bharatpe_on:
        return await bot.send_message(user_id, "❌ Payment gateways are OFF or not configured. Contact admin.")
    set_setting(f"pending_wallet_gateway_amount_{user_id}", str(round(float(amount), 2)))
    gateway_rows = []
    if fampay_on:
        gateway_rows.append([InlineKeyboardButton(text="Pay with FamPay", callback_data="walletpay_fampay", icon_custom_emoji_id=get_emoji_icon("fampay"), style="primary")])
    if zapupi_on:
        gateway_rows.append([InlineKeyboardButton(text="Pay with ZapUPI", callback_data="walletpay_zapupi", icon_custom_emoji_id=get_emoji_icon("upi"), style="success")])
    if bharatpe_on:
        gateway_rows.append([InlineKeyboardButton(text="Pay with BharatPe UPI", callback_data="walletpay_BharatPe", icon_custom_emoji_id=get_emoji_icon("BharatPe"), style="primary")])
    gateway_rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data="menu_add_balance", style="danger")])
    kb = InlineKeyboardMarkup(inline_keyboard=gateway_rows)
    await bot.send_message(user_id, f"💰 <b>Amount:</b> {fmt_curr(amount)}\n\nChoose payment gateway:", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.in_({"walletpay_fampay", "walletpay_zapupi", "walletpay_BharatPe"}))
async def wallet_custom_gateway_choice(call: CallbackQuery):
    user_id = call.from_user.id
    amount = safe_float(get_setting(f"pending_wallet_gateway_amount_{user_id}", "0"))
    if amount <= 0:
        return await call.answer("Amount request expired. Please try again.", show_alert=True)
    gateway = "fampay" if call.data == "walletpay_fampay" else ("BharatPe" if call.data == "walletpay_BharatPe" else "zapupi")
    enabled = get_setting(f"gateway_{gateway}_enabled", "ON") == "ON"
    configured = (bool(get_setting("fampay_api_key", "")) and get_setting("fampay_api_key", "") != "YOUR_FAMPAY_API_KEY") if gateway == "fampay" else ((get_setting("BharatPe_api_key", "").strip() not in ("", "YOUR_BharatPe_API_KEY", "PASTE_YOUR_BharatPe_API_KEY_HERE")) if gateway == "BharatPe" else bool(get_setting("zapupi_zap_key", "").strip()))
    if not enabled or not configured:
        return await call.answer("This gateway is OFF or not configured.", show_alert=True)
    set_setting(f"pending_wallet_gateway_amount_{user_id}", "")
    await call.answer()
    try: await call.message.delete()
    except Exception: pass
    msg = await bot.send_message(user_id, f"⏳ Generating {('FamPay QR' if gateway == 'fampay' else ('BharatPe QR' if gateway == 'BharatPe' else 'ZapUPI payment'))} for {fmt_curr(amount)}...")
    if gateway == "fampay": await generate_fampay_order(user_id, amount, msg)
    elif gateway == "BharatPe": await generate_BharatPe_order(user_id, amount, msg)
    else: await generate_zapupi_order(user_id, amount, msg)

async def start_product_payment_gateway_choice(user_id: int, amount: float):
    """Use only enabled gateways; ask user only when both gateways are available."""
    fampay_on = get_setting("gateway_fampay_enabled", "ON") == "ON" and bool(get_setting("fampay_api_key", "")) and get_setting("fampay_api_key", "") != "YOUR_FAMPAY_API_KEY"
    zapupi_on = get_setting("gateway_zapupi_enabled", "ON") == "ON" and bool(get_setting("zapupi_zap_key", "").strip())
    bharatpe_on = get_setting("gateway_BharatPe_enabled", "ON") == "ON" and get_setting("BharatPe_api_key", "").strip() not in ("", "YOUR_BharatPe_API_KEY", "PASTE_YOUR_BharatPe_API_KEY_HERE")
    if fampay_on and not zapupi_on and not bharatpe_on:
        msg = await bot.send_message(user_id, f"⏳ Generating FamPay QR for {fmt_curr(amount)}...")
        return await generate_fampay_order(user_id, amount, msg)
    if zapupi_on and not fampay_on and not bharatpe_on:
        msg = await bot.send_message(user_id, f"⏳ Generating ZapUPI payment for {fmt_curr(amount)}...")
        return await generate_zapupi_order(user_id, amount, msg)
    if bharatpe_on and not fampay_on and not zapupi_on:
        msg = await bot.send_message(user_id, f"⏳ Generating BharatPe QR for {fmt_curr(amount)}...")
        return await generate_BharatPe_order(user_id, amount, msg)
    if not fampay_on and not zapupi_on and not bharatpe_on:
        return await bot.send_message(user_id, "❌ All payment gateways are OFF or not configured.")
    set_setting(f"pending_gateway_amount_{user_id}", str(round(float(amount), 2)))
    kb_rows = []
    if get_setting("gateway_fampay_enabled", "ON") == "ON" and get_setting("fampay_api_key", "") not in ("", "YOUR_FAMPAY_API_KEY"):
        kb_rows.append([InlineKeyboardButton(text="Pay with FamPay", callback_data="shortpay_fampay", icon_custom_emoji_id=get_emoji_icon("fampay"), style="primary")])
    if get_setting("gateway_zapupi_enabled", "ON") == "ON" and get_setting("zapupi_zap_key", "").strip():
        kb_rows.append([InlineKeyboardButton(text="Pay with ZapUPI", callback_data="shortpay_zapupi", icon_custom_emoji_id=get_emoji_icon("upi"), style="success")])
    if get_setting("gateway_BharatPe_enabled", "ON") == "ON" and get_setting("BharatPe_api_key", "").strip() not in ("", "YOUR_BharatPe_API_KEY", "PASTE_YOUR_BharatPe_API_KEY_HERE"):
        kb_rows.append([InlineKeyboardButton(text="Pay with BharatPe UPI", callback_data="shortpay_BharatPe", icon_custom_emoji_id=get_emoji_icon("BharatPe"), style="primary")])
    kb_rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data="back_main", style="danger")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await bot.send_message(user_id, f"🛒 <b>PRODUCT PAYMENT</b>\n\n💰 Exact amount required: <b>{fmt_curr(amount)}</b>\n\nChoose your payment gateway:", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.in_({"shortpay_fampay", "shortpay_zapupi", "shortpay_BharatPe"}))
async def product_shortfall_gateway_choice(call: CallbackQuery):
    user_id = call.from_user.id
    amount = safe_float(get_setting(f"pending_gateway_amount_{user_id}", "0"))
    if amount <= 0:
        return await call.answer("Payment request expired. Please tap Buy again.", show_alert=True)
    gateway = "fampay" if call.data == "shortpay_fampay" else ("BharatPe" if call.data == "shortpay_BharatPe" else "zapupi")
    enabled = get_setting(f"gateway_{gateway}_enabled", "ON") == "ON"
    configured = (bool(get_setting("fampay_api_key", "")) and get_setting("fampay_api_key", "") != "YOUR_FAMPAY_API_KEY") if gateway == "fampay" else ((get_setting("BharatPe_api_key", "").strip() not in ("", "YOUR_BharatPe_API_KEY", "PASTE_YOUR_BharatPe_API_KEY_HERE")) if gateway == "BharatPe" else bool(get_setting("zapupi_zap_key", "").strip()))
    if not enabled or not configured:
        return await call.answer("This gateway is currently OFF or not configured.", show_alert=True)
    set_setting(f"pending_gateway_amount_{user_id}", "")
    await call.answer()
    try: await call.message.delete()
    except Exception: pass
    msg = await bot.send_message(user_id, f"⏳ Generating {('FamPay QR' if gateway == 'fampay' else ('BharatPe QR' if gateway == 'BharatPe' else 'ZapUPI payment'))} for {fmt_curr(amount)}...")
    if gateway == "fampay":
        await generate_fampay_order(user_id, amount, msg)
    elif gateway == "BharatPe":
        await generate_BharatPe_order(user_id, amount, msg)
    else:
        await generate_zapupi_order(user_id, amount, msg)

@dp.callback_query(F.data.startswith("buytopup_"))
async def buy_product_topup(call: CallbackQuery):
    """Create a UPI QR for the exact wallet shortfall before product purchase."""
    try:
        prod_id = int(call.data.split("_", 1)[1])
    except (ValueError, IndexError):
        return await call.answer("Invalid product.", show_alert=True)
    prod = db_query("SELECT price_inr, reseller_price, name, panel_name FROM products WHERE id=?", (prod_id,), fetchone=True)
    user = db_query("SELECT balance, is_reseller, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if not prod or not user:
        return await call.answer("Product/user not found.", show_alert=True)
    base = safe_float(prod[1]) if user[1] else safe_float(prod[0])
    price = base - (base * VIP_DISCOUNT_PERCENTAGE / 100) if user[2] else base
    amount = round(max(0.0, price - safe_float(user[0])), 2)
    if amount <= 0:
        await call.answer("Your balance is enough now. Tap Buy again.", show_alert=True)
        return
    await call.answer()
    # Remove the old confirm-order post; the QR/payment message replaces it.
    try:
        await call.message.delete()
    except Exception:
        pass
    # Remember the product the user was trying to buy, so verified payment
    # can continue that purchase instead of dropping the user at Start Menu.
    set_setting(f"pending_product_purchase_{call.from_user.id}", str(prod_id))
    await start_product_payment_gateway_choice(call.from_user.id, amount)

@dp.callback_query(F.data.startswith("retry_deposit_"))
async def retry_cancelled_deposit(call: CallbackQuery):
    order_id = call.data[len("retry_deposit_"):]
    txn = db_query("SELECT amount_inr, status FROM transactions WHERE order_id=? AND user_id=?", (order_id, call.from_user.id), fetchone=True)
    if not txn:
        return await call.answer("Payment order not found.", show_alert=True)
    amount = safe_float(txn[0])
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass
    await start_product_payment_gateway_choice(call.from_user.id, amount)

@dp.callback_query(F.data == "gateway_crypto")
async def add_balance_crypto(call: CallbackQuery, state: FSMContext):
    address_check = db_query("SELECT value FROM settings WHERE key='binance_address'", fetchone=True)
    if not address_check or not address_check[0]:
        return await call.message.edit_text("⚠️ Binance Gateway is currently offline. Admin has not set a deposit address.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
    deposit_address = address_check[0]
    msg = (f"🪙 <b>— BINANCE USDT DEPOSIT —</b> 🪙\n\n💵 <b>Exchange Rate:</b> 1 USDT = ₹{USDT_TO_INR}\n⚠️ <b>Network:</b> Please send via <b>TRC20</b> or <b>BEP20</b>.\n\n👇 <b>Send your USDT to this exact address:</b>\n<code>{deposit_address}</code>\n\n━━━━━━━━━━━━━━━━━━\n✅ <b>After sending the USDT, reply to this message with your exact TxID (Transaction Hash) to instantly claim your balance.</b>")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Cancel", callback_data="menu_add_balance", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text(msg, reply_markup=kb, parse_mode='HTML')
    await state.set_state(UserStates.wait_for_crypto_txid)

@dp.message(UserStates.wait_for_crypto_txid)
async def process_crypto_txid(m: Message, state: FSMContext):
    txid = m.text.strip()
    user_id = m.from_user.id
    if len(txid) < 10: return await m.answer("❌ That doesn't look like a valid TxID. Please try again.")
    if db_query("SELECT txid FROM crypto_txns WHERE txid=?", (txid,), fetchone=True):
        return await m.answer("⚠️ This Transaction ID has already been claimed in the system!", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
    api_key_check = db_query("SELECT value FROM settings WHERE key='binance_api'", fetchone=True)
    secret_key_check = db_query("SELECT value FROM settings WHERE key='binance_secret'", fetchone=True)
    if not api_key_check or not secret_key_check:
        return await m.answer("⚠️ Binance API is missing on the server. Contact Support.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
    await m.answer("🔄 <b>Verifying your TxID with Binance Blockchain...</b>\n<i>This may take up to 30 seconds...</i>", parse_mode='HTML')
    api_key = api_key_check[0]; secret_key = secret_key_check[0]
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    headers = {'X-MBX-APIKEY': api_key}
    url = f"https://api.binance.com/sapi/v1/capital/deposit/hisrec?{query_string}&signature={signature}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    try: history = await resp.json(content_type=None)
                    except: history = []
                    found = False
                    for deposit in history:
                        if deposit.get("txId") == txid and deposit.get("status") == 1:
                            found = True
                            usdt_amount = float(deposit.get("amount"))
                            inr_amount = usdt_amount * USDT_TO_INR
                            db_query("INSERT INTO crypto_txns (txid, user_id, amount_usdt, timestamp) VALUES (?, ?, ?, ?)", (txid, user_id, usdt_amount, int(time.time())))
                            db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (inr_amount, user_id))
                            await m.answer(f"🎉 <b>CRYPTO DEPOSIT SUCCESSFUL!</b>\n\n✅ We safely received <b>{usdt_amount} USDT</b>.\n💰 <b>{fmt_curr(inr_amount)}</b> has been added to your balance!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
                            await send_advanced_notification(user_id, "DEPOSIT", inr_amount, product=txid, gateway="Binance Crypto")
                            log_activity(user_id, "CRYPTO_DEPOSIT", f"TxID: {txid}, Amount: {inr_amount}")
                            await state.clear()
                            break
                    if not found: await m.answer("❌ <b>TxID Not Found or Still Pending!</b>\nMake sure the transaction is fully confirmed. Try again in 5 mins.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
                else: await m.answer(f"⚠️ <b>Binance Server Error:</b> HTTP {resp.status}.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
        except Exception as e: await m.answer(f"⚠️ <b>Connection Error:</b> {str(e)}", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')

# ==============================================================================
# 14. SHOP – with uppercase categories and new point_down emoji
# ==============================================================================
@dp.callback_query(F.data == "menu_shop")
async def view_shop_panels(call: CallbackQuery):
    # Always acknowledge the click first; otherwise Telegram keeps the button spinner active.
    try:
        await call.answer()
    except Exception:
        logger.debug("Shop callback was already acknowledged", exc_info=True)
    try:
        log_activity(call.from_user.id, "VIEW_SHOP")
        kb = InlineKeyboardMarkup(inline_keyboard=[])
        text = f"{get_emoji('product_store')} <b><u>SELECT PRODUCT PANEL</u></b>\n━━━━━━━━━━━━━━━━━━\n\n{get_emoji('point_down')} <b>Choose a panel to view its packages:</b>"
        categories = get_categories()
        if not categories:
            text += "\n\n⚠️ No product categories are available yet. Please contact admin."
        for cat in categories:
            emoji_id = get_category_emoji(cat)
            # Keep callback data compact and consistent with the category lookup.
            kb.inline_keyboard.append([InlineKeyboardButton(text=str(cat)[:64], callback_data=f"cat_{str(cat)[:30]}", icon_custom_emoji_id=emoji_id or None, style="primary")])
        kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back") or None, style="danger")])
        try:
            await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
        except Exception as edit_error:
            # Photo/caption messages and unchanged messages may not support edit_text.
            logger.info("Could not edit shop menu message; sending a new one: %s", edit_error)
            await call.message.answer(text, reply_markup=kb, parse_mode='HTML')
    except Exception:
        logger.exception("Failed to open shop menu for user %s", call.from_user.id)
        try:
            await call.message.answer("❌ Shop menu could not be opened. Please try /start again or contact admin.")
        except Exception:
            pass

@dp.callback_query(F.data.startswith("cat_"))
async def view_panel_names(call: CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass
    category = call.data.split("cat_", 1)[1]
    panel_names = db_query("""SELECT MIN(TRIM(panel_name)) AS panel_name, MIN(COALESCE(maintenance,0)) AS maintenance
                              FROM products
                              WHERE category LIKE ? AND is_active=1 AND TRIM(COALESCE(panel_name,'')) != ''
                              GROUP BY LOWER(TRIM(panel_name))
                              ORDER BY MIN(TRIM(panel_name)) COLLATE NOCASE""", (category + '%',), fetchall=True)
    if not panel_names:
        prods = db_query("SELECT id, name, price_inr, stock, reseller_price, validity, device_limit, maintenance FROM products WHERE category LIKE ? AND is_active=1", (category + '%',), fetchall=True)
        if not prods: return await call.answer("❌ No products available in this category yet.", show_alert=True)
        await show_products_for_panel(call, prods, category)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    text = f"{get_emoji('product_store')} <b><u>{category.upper()} PANELS</u></b>\n━━━━━━━━━━━━━━━━━━\n\n{get_emoji('point_down')} <b>Choose a panel name:</b>"
    for pn in panel_names:
        panel = str(pn[0] or '').strip()
        panel_maintenance = bool(pn[1]) if len(pn) > 1 else False
        emoji_id = get_panel_emoji(panel) or get_emoji_icon("product_store")
        # Show maintained panels in red; the maintenance state applies to every duration under this panel.
        label = f"🔴 {panel} — MAINTENANCE" if panel_maintenance else panel
        kb.inline_keyboard.append([InlineKeyboardButton(text=label[:64], callback_data=f"pnl_{category[:30]}_{panel[:30]}", icon_custom_emoji_id=emoji_id, style="danger" if panel_maintenance else "primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK TO PANELS", callback_data="menu_shop", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("pnl_"))
async def view_products_for_panel(call: CallbackQuery):
    try:
        await call.answer()
    except Exception:
        pass
    parts = call.data.split("pnl_", 1)[1].split("_", 1)
    if len(parts) != 2: return await call.answer("Invalid selection.", show_alert=True)
    category, panel_name = parts[0], parts[1]
    # A panel may contain multiple package durations. Maintenance belongs to each
    # product/duration, not to the whole panel: one maintained duration must not
    # block every other package in that panel.
    prods = db_query(
        "SELECT id, name, price_inr, stock, reseller_price, validity, device_limit, maintenance "
        "FROM products WHERE category LIKE ? AND LOWER(TRIM(COALESCE(panel_name,''))) LIKE LOWER(TRIM(?)) AND is_active=1",
        (category + '%', panel_name + '%'), fetchall=True
    )
    if not prods:
        return await call.answer("No visible products found for this panel.", show_alert=True)

    # A red maintenance panel must not open its package list. Check the live
    # database state here (rather than trusting the button colour, which may be stale).
    if any(bool(prod[7]) for prod in prods):
        return await call.answer(
            "🛠 THE PRODUCT IS UNDER MAINTENANCE. PLEASE WAIT FOR SOME TIME.",
            show_alert=True
        )

    await show_products_for_panel(call, prods, f"{category} - {panel_name}")

async def show_products_for_panel(call: CallbackQuery, prods: List[Tuple], header: str):
    user = db_query("SELECT is_reseller, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    is_reseller = bool(user[0]) if user else False
    is_vip = bool(user[1]) if user else False
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    text = f"{get_emoji('product_store')} <b><u>{header.upper()} PACKAGES</u></b>\n━━━━━━━━━━━━━━━━━━\n\n"
    # Same package name is shown only once (case-insensitive), even if duplicated in DB.
    seen_names = set()
    demo_button = None
    for p in prods:
        prod_id, package_name, normal_price, stock, reseller_price, validity, device = p[:7]
        maintenance = bool(p[7]) if len(p) > 7 else False
        normalized_name = str(package_name or '').strip().casefold()
        if normalized_name in seen_names:
            continue
        seen_names.add(normalized_name)
        normal_price = safe_float(normal_price)
        reseller_price = safe_float(reseller_price)
        base_price = reseller_price if is_reseller else normal_price
        display_price = base_price - (base_price * (VIP_DISCOUNT_PERCENTAGE / 100)) if is_vip else base_price
        stock_status = "🛠 UNDER MAINTENANCE" if maintenance else ("✅ In Stock" if stock > 0 else "❌ Out of Stock")
        text += f"{get_emoji('product_store')} ⏱ <b>Validity: {html_lib.escape(str(package_name))}</b>\n"
        if is_reseller or is_vip:
            text += f"💰 Regular Price: <s>{fmt_curr(normal_price)}</s>\n"
            if is_reseller and not is_vip: text += f"👑 <b>Reseller Price: {fmt_curr(display_price)}</b>\n"
            elif is_vip and not is_reseller: text += f"🌟 <b>VIP Price: {fmt_curr(display_price)}</b>\n"
            else: text += f"👑🌟 <b>Super Price: {fmt_curr(display_price)}</b>\n"
        else:
            text += f"💰 Price: {fmt_curr(normal_price)}\n"
        text += f"📱 Limit: {html_lib.escape(str(device))} | 📦 {stock_status}\n\n"
        # Keep a single panel-level Watch Demo button, regardless of how many durations
        # are configured. It is appended after all duration buttons, immediately above Back.
        panel_demo_name = str(header.rsplit(' - ', 1)[-1] if ' - ' in header else header).strip()
        demo_key = panel_demo_name.casefold()
        demo_row = db_query("SELECT file_id FROM product_demos WHERE product_name_key=?", (demo_key,), fetchone=True)
        if demo_row and demo_row[0] and demo_button is None:
            demo_button = InlineKeyboardButton(
                text=f"▶️ Watch Demo — {panel_demo_name}"[:64],
                callback_data=f"watch_demo_{prod_id}",
                style="primary"
            )
        if maintenance:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"🔴 {package_name} — UNDER MAINTENANCE", callback_data=f"product_maintenance_info_{prod_id}", style="danger")])
        elif stock > 0:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"🟢 Buy {package_name} - {fmt_curr(display_price)}", callback_data=f"buy_{prod_id}", icon_custom_emoji_id=get_emoji_icon("product_store"), style="success")])
        else:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ {package_name} (Out of Stock)", callback_data="ignore_stock_click", style="danger")])
    text += f"{get_emoji('point_down')} <b>Select package below to instantly purchase:</b>"
    if demo_button is not None:
        kb.inline_keyboard.append([demo_button])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK TO PANELS", callback_data="menu_shop", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("product_maintenance_info_"))
async def product_maintenance_info(call: CallbackQuery):
    prod_id = int(call.data.rsplit("_", 1)[1])
    row = db_query("SELECT name FROM products WHERE id=?", (prod_id,), fetchone=True)
    name = html_lib.escape(str(row[0])) if row else "Product"
    await call.answer(f"🛠 {name} is under maintenance. Please try again later.", show_alert=True)

@dp.callback_query(F.data == "ignore_stock_click")
async def ignore_stock_click(call: CallbackQuery):
    await call.answer("⚠️ This duration is completely Out of Stock! Admins have been notified to refill.", show_alert=True)

# ==============================================================================
# RESELLER API - AUTOMATIC KEY DELIVERY
# ==============================================================================
USER_BUY_LOCKS: Dict[int, asyncio.Lock] = {}


def get_reseller_api_url() -> str:
    """Return the admin-configured reseller API endpoint."""
    url = get_setting("reseller_api_url", RESELLER_API_URL).strip()
    return url or RESELLER_API_URL


def get_reseller_api_key() -> str:
    return get_setting("reseller_api_key", RESELLER_API_KEY).strip()


async def reseller_api_request(action: str, **fields) -> Tuple[bool, Any]:
    """Call the configured reseller API and reject HTTP errors/non-JSON replies safely."""
    api_key = get_reseller_api_key()
    if not api_key or api_key == "YOUR_RRSELLER_API_ADD":
        return False, "Reseller API key is not configured. Set it in Admin > Reseller API Key."

    endpoint = get_reseller_api_url().strip()
    if not endpoint.startswith(("https://", "http://")):
        return False, "Reseller API URL is invalid. Set the full http(s) endpoint in Admin > Reseller API URL."

    payload = {"api_key": api_key, "action": action}
    payload.update({k: v for k, v in fields.items() if v not in (None, "")})
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                endpoint,
                data=payload,
                headers={"X-API-Key": api_key, "Accept": "application/json"},
            ) as resp:
                raw = await resp.text()
                if resp.status == 404:
                    return False, ("Reseller API endpoint returned HTTP 404 (Not Found). "
                                   "The configured URL/path is not available on the API server. "
                                   "Ask the API provider for the correct active endpoint, then set it in "
                                   "Admin > Reseller API URL. No key was delivered.")
                if resp.status < 200 or resp.status >= 300:
                    excerpt = re.sub(r"\s+", " ", raw).strip()[:180]
                    return False, f"Reseller API HTTP {resp.status}. Check the API URL/key. Response: {excerpt or '(empty response)'}"
                try:
                    data = json.loads(raw)
                except (ValueError, TypeError):
                    content_type = resp.headers.get("Content-Type", "unknown")
                    excerpt = re.sub(r"\s+", " ", raw).strip()[:180]
                    return False, (f"Reseller API returned non-JSON data (Content-Type: {content_type}). "
                                   f"Check the API endpoint. Response: {excerpt or '(empty response)'}")
                if not isinstance(data, (dict, list)):
                    return False, "Reseller API returned an unexpected response format."
                return True, data
    except asyncio.TimeoutError:
        return False, "Reseller API request timed out. Please try again later."
    except aiohttp.ClientError as exc:
        logger.warning("Reseller API connection error: %s", exc)
        return False, "Could not connect to the reseller API. Check the server and endpoint URL."


RESELLER_DELIVERY_META: Dict[str, Dict[str, Any]] = {}

async def reseller_buy(api_product_id: str, duration: str = "", quantity: int = 1) -> Tuple[bool, str]:
    """Purchase a key and retain supplier-provided expiry metadata when available."""
    ok, data = await reseller_api_request(
        "buy", product_id=str(api_product_id), duration=duration, quantity=quantity,
    )
    if not ok:
        return False, str(data)
    if isinstance(data, dict) and str(data.get("status", "")).lower() == "success":
        key = data.get("key")
        if not key:
            keys = data.get("keys")
            if isinstance(keys, list) and keys:
                first = keys[0]
                key = first.get("key") if isinstance(first, dict) else first
        if key:
            meta = data.get("data") if isinstance(data.get("data"), dict) else data
            expiry = (meta.get("expires_at") or meta.get("expiry") or meta.get("expires") or
                      meta.get("expiration") or meta.get("expire_at") or meta.get("valid_until"))
            RESELLER_DELIVERY_META[str(key)] = {"expiry": expiry} if expiry else {}
            return True, str(key)
        logger.error("Reseller API reported success without a key: %s", data)
        return False, "API returned success but no key. Check supplier orders."
    if isinstance(data, dict):
        return False, str(data.get("message") or data.get("error") or "Request failed")
    return False, "Request failed"


@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(call: CallbackQuery):
    """One purchase at a time per user; API purchase happens before wallet debit."""
    lock = USER_BUY_LOCKS.setdefault(call.from_user.id, asyncio.Lock())
    if lock.locked():
        return await call.answer("⏳ Your previous purchase is still processing...", show_alert=True)
    async with lock:
        try:
            # Acknowledge the Telegram callback immediately so the Buy button never keeps spinning.
            await call.answer("⏳ Processing your purchase...")
            await _process_buy(call)
        except Exception:
            logger.exception("Unexpected Buy Key failure for user %s, callback=%s", call.from_user.id, call.data)
            try:
                await call.message.answer("❌ Purchase could not be completed due to an internal error. You have not been charged unless a success message was shown. Please contact admin.")
            except Exception:
                pass


async def _process_buy(call: CallbackQuery):
    try:
        prod_id = int(call.data.split("_", 1)[1])
    except (ValueError, IndexError):
        return await call.message.answer("❌ Invalid product selection. Please reopen the shop.")
    prod = db_query(
        "SELECT name, price_inr, stock, apk_link, validity, device_limit, category, reseller_price, panel_name, api_product_id, api_duration, maintenance FROM products WHERE id=?",
        (prod_id,), fetchone=True
    )
    user = db_query(
        "SELECT balance, referred_by, is_reseller, total_saved, is_vip FROM users WHERE user_id=?",
        (call.from_user.id,), fetchone=True
    )
    if not prod or not user:
        return await call.message.answer("❌ Product/user record was not found. Please reopen the shop or contact admin.")

    if len(prod) > 11 and bool(prod[11]):
        return await call.message.answer("🛠 This product is under maintenance. Please try again later.")

    normal_price = safe_float(prod[1])
    reseller_price = safe_float(prod[7])
    is_reseller = bool(user[2])
    is_vip = bool(user[4])
    base_price = reseller_price if is_reseller else normal_price
    final_price = base_price - (base_price * (VIP_DISCOUNT_PERCENTAGE / 100)) if is_vip else base_price
    savings = normal_price - final_price

    if user[0] < final_price:
        shortfall = round(final_price - safe_float(user[0]), 2)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Pay {fmt_curr(shortfall)} via UPI", callback_data=f"buytopup_{prod_id}", style="success")],
            [InlineKeyboardButton(text="↩️ Back to Shop", callback_data="menu_shop", style="danger")]
        ])
        summary = (
            "💎 <b>CONFIRM YOUR ORDER</b> 💎\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📦 <b>Product:</b> {html_lib.escape(str(prod[8] or prod[0]))}\n"
            f"⏳ <b>Duration:</b> {html_lib.escape(str(prod[4]))}\n"
            f"💰 <b>Price:</b> {fmt_curr(final_price)}\n"
            f"👛 <b>Wallet Balance:</b> {fmt_curr(safe_float(user[0]))}\n"
            f"➕ <b>Amount to Pay:</b> {fmt_curr(shortfall)}\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "⚠️ Your balance is short. Pay only the exact remaining amount using UPI."
        )
        return await call.message.edit_text(summary, reply_markup=kb, parse_mode="HTML")

    # If linked, obtain the key first. A failed supplier request never charges the user.
    api_pid = (prod[9] or "").strip()
    api_duration = (prod[10] or "").strip()
    api_delivered = ""
    if not api_pid:
        local_key = db_query(
            "SELECT id, key_text FROM product_keys WHERE product_id=? AND is_used=0 ORDER BY id LIMIT 1",
            (prod_id,), fetchone=True
        )
        if not local_key:
            return await call.message.answer(
                "❌ No keys are available for this product right now. Your balance was not changed. Please contact admin."
            )
    if api_pid:
        ok, result = await reseller_buy(api_pid, api_duration, 1)
        if not ok:
            log_activity(call.from_user.id, "API_BUY_FAILED", f"prod={prod_id} api_pid={api_pid} err={result}")
            if result == "TIMEOUT":
                msg = "⚠️ Supplier took too long to respond. You were NOT charged. Please try again in a minute."
            else:
                msg = f"❌ Could not generate key right now. You were NOT charged.\nReason: {html_lib.escape(result)}\nContact: {ADMIN_CONTACT}"
            try:
                await bot.send_message(
                    ADMIN_ID,
                    f"⚠️ <b>API BUY FAILED</b>\nProduct #{prod_id} | User <code>{call.from_user.id}</code>\n<code>{html_lib.escape(str(result))}</code>",
                    parse_mode="HTML",
                )
            except Exception:
                pass
            return await call.message.answer(msg, parse_mode="HTML")
        api_delivered = result

    # Charge only after API key delivery succeeds (or for a local-key product).
    db_query(
        "UPDATE users SET balance=?, spent=spent+?, orders_count=orders_count+1, total_saved=total_saved+? WHERE user_id=?",
        (user[0] - final_price, final_price, savings, call.from_user.id),
    )

    delivered_key = api_delivered
    if not delivered_key:
        if local_key:
            delivered_key = local_key[1]
            # Claim the key only if it is still unused.
            claimed = db_query(
                "UPDATE product_keys SET is_used=1 WHERE id=? AND is_used=0",
                (local_key[0],)
            )
            db_query("UPDATE products SET stock=MAX(stock-1, 0) WHERE id=?", (prod_id,))
        else:
            # API-linked products were already delivered above; this is defensive only.
            return await call.message.answer("❌ No key was delivered. Contact admin; no local key was charged.")

    if user[1]:
        commission = final_price * 0.15
        db_query(
            "UPDATE users SET balance=balance+?, referral_earned=referral_earned+? WHERE user_id=?",
            (commission, commission, user[1]),
        )
        try:
            await bot.send_message(
                user[1],
                f"🎁 <b>Referral Bonus Added!</b>\nYour friend made a successful purchase. You earned {fmt_curr(commission)} directly to your wallet!",
                parse_mode="HTML",
            )
        except Exception:
            pass

    product_full_name = f"{prod[6]} - {prod[8]} ({prod[0]})"
    db_query(
        "INSERT INTO orders (user_id, product_name, price_paid, delivered_key, purchase_date) VALUES (?, ?, ?, ?, ?)",
        (call.from_user.id, product_full_name, final_price, delivered_key, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    log_activity(call.from_user.id, "PURCHASE_SUCCESS", f"Product: {product_full_name}, Paid: {final_price}")
    await send_advanced_notification(call.from_user.id, "ORDER", final_price, product=product_full_name, key=delivered_key)

    display_product = str(prod[8] or prod[0])
    product_type = "👑 Reseller" if is_reseller else "🔵 Regular"
    safe_product = html_lib.escape(display_product)
    safe_category = html_lib.escape(str(prod[6] or "Panel"))
    safe_duration = html_lib.escape(str(prod[0] or prod[4] or "N/A"))
    safe_device_limit = html_lib.escape(str(prod[5] or "N/A"))
    # Premium Telegram custom emoji are rendered in the message with tg-emoji tags.
    msg = (
        f"{get_emoji('check_icon')} <b>🎉 PURCHASE SUCCESSFUL! 🎉</b> {get_emoji('sagartop')}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{get_emoji('product_store')} <b>Product:</b> {safe_product}\n"
        f"{get_emoji('profile')} <b>Type:</b> {product_type}\n"
        f"{get_emoji('history')} <b>Duration:</b> {safe_duration}\n"
        f"{get_emoji('money_icon')} <b>Price:</b> {fmt_curr(final_price)}\n"
        f"{get_emoji('grid_id')} <b>Panel Category:</b> {safe_category}\n"
        f"{get_emoji('info_icon')} <b>Device Limit:</b> {safe_device_limit}\n"
        "━━━━━━━━━━━━━━━━━━\n"
    )
    if prod[3] and str(prod[3]).startswith(("http://", "https://")):
        msg += f"{get_emoji('download')} <b>APK Link:</b> <a href='{html_lib.escape(str(prod[3]), quote=True)}'>Click Here to Download</a>\n\n"
    if "OUT_OF_STOCK" in delivered_key:
        msg += f"{get_emoji('shield_icon')} <b>CRITICAL INVENTORY ALERT</b>\n{get_emoji('support')} Your money was deducted, but the key vault was empty. Contact Admin immediately: {html_lib.escape(ADMIN_CONTACT)}\n"
    else:
        expiry_value = RESELLER_DELIVERY_META.pop(str(delivered_key), {}).get("expiry")
        expiry_text = ""
        if expiry_value:
            try:
                if isinstance(expiry_value, (int, float)) or str(expiry_value).strip().isdigit():
                    expiry_text = datetime.fromtimestamp(float(expiry_value)).strftime("%Y-%m-%d %I:%M %p")
                else:
                    expiry_text = str(expiry_value).strip()
            except Exception:
                expiry_text = str(expiry_value).strip()
        else:
            # Use the configured product validity as a fallback for locally stocked keys.
            validity = str(prod[4] or "").strip().lower()
            match = re.fullmatch(r"\s*(\d+)\s*(hour|hours|hr|hrs|day|days|minute|minutes|min|mins|week|weeks|month|months)\s*", validity)
            if match:
                amount, unit = int(match.group(1)), match.group(2)
                delta = (timedelta(hours=amount) if unit in ("hour", "hours", "hr", "hrs") else
                         timedelta(days=amount) if unit in ("day", "days") else
                         timedelta(minutes=amount) if unit in ("minute", "minutes", "min", "mins") else
                         timedelta(weeks=amount) if unit in ("week", "weeks") else
                         timedelta(days=30 * amount))
                expiry_text = (datetime.now() + delta).strftime("%Y-%m-%d %I:%M %p")
        msg += f"{get_emoji('redeem_icon')} <b>Your Key:</b>\n<code>{html_lib.escape(str(delivered_key))}</code>\n"
        if expiry_text:
            msg += f"{get_emoji('history')} <b>Expires:</b> {html_lib.escape(expiry_text)}\n"
        msg += f"\n{get_emoji('cheatz')} <b>ENJOY YOUR {safe_product.upper()}!</b>\n{get_emoji('sagartop')} <b>THAKUR MODS SHOP</b> {get_emoji('cheatz')}\n\n{get_emoji('support')} <i>For help, tap Support or contact: {html_lib.escape(ADMIN_CONTACT)}</i>"
    purchase_kb = InlineKeyboardMarkup(inline_keyboard=[])
    # Copy the delivered key directly to the user's clipboard.
    # Keep the blue button above Join for Panel Update and Back.
    if delivered_key and "OUT_OF_STOCK" not in delivered_key:
        from aiogram.types import CopyTextButton
        purchase_kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="COPY THE KEY",
                copy_text=CopyTextButton(text=str(delivered_key)),
                icon_custom_emoji_id=get_emoji_icon("redeem_icon"),
                style="primary",
            )
        ])
    if prod[3] and str(prod[3]).startswith(("http://", "https://")):
        purchase_kb.inline_keyboard.append([InlineKeyboardButton(text="JOIN FOR PANEL UPDATE", url=str(prod[3])[:2048], icon_custom_emoji_id=get_emoji_icon("telegram"), style="primary")])
    purchase_kb.inline_keyboard.append([InlineKeyboardButton(text="BACK TO SHOP", callback_data="menu_shop", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(msg, reply_markup=purchase_kb, disable_web_page_preview=True, parse_mode="HTML")


@dp.callback_query(F.data == "menu_vip_dash")
async def vip_dashboard(call: CallbackQuery):
    u = db_query("SELECT balance, is_vip, vip_since FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    is_vip = bool(u[1])
    status_str = "🟢 Active (Lifetime)" if is_vip else "🔴 Not Subscribed"
    text = get_ui_text("vip_menu", vip_status=status_str)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if is_vip:
        text += f"\n📅 <b>Member Since:</b> {u[2]}\n\nEnjoy your permanent 15% discount!"
    else:
        text += f"\n\n💳 <b>Your Current Balance:</b> {fmt_curr(u[0])}\n"
        if u[0] >= VIP_PRICE_INR: kb.inline_keyboard.append([InlineKeyboardButton(text=f"✅ Purchase VIP for {fmt_curr(VIP_PRICE_INR)}", callback_data="execute_vip_upgrade", style="success")])
        else:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ Need {fmt_curr(VIP_PRICE_INR)} to Upgrade", callback_data="ignore_stock_click", style="danger")])
            kb.inline_keyboard.append([InlineKeyboardButton(text="💳 Add Balance Now", callback_data="menu_add_balance", style="success")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "execute_vip_upgrade")
async def execute_vip_upgrade(call: CallbackQuery):
    u = db_query("SELECT balance, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if u[1]: return await call.answer("⚠️ You are already a VIP Member!", show_alert=True)
    if u[0] < VIP_PRICE_INR: return await call.answer(f"❌ Your balance dropped below {VIP_PRICE_INR}.", show_alert=True)
    new_balance = u[0] - VIP_PRICE_INR
    now_date = datetime.now().strftime("%Y-%m-%d")
    db_query("UPDATE users SET balance=?, is_vip=1, vip_since=? WHERE user_id=?", (new_balance, now_date, call.from_user.id))
    log_activity(call.from_user.id, "UPGRADED_VIP")
    try: await bot.send_message(ADMIN_ID, f"🌟 <b>NEW VIP UPGRADE</b>\n👤 User ID: <code>{call.from_user.id}</code>", parse_mode='HTML')
    except: pass
    await call.answer("🎉 Upgrade Successful! You are now a VIP Member.", show_alert=True)
    await vip_dashboard(call)

@dp.callback_query(F.data == "menu_reseller_dash")
async def reseller_dashboard(call: CallbackQuery):
    u = db_query("SELECT balance, is_reseller, reseller_since, total_saved FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    status_check = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    system_status = status_check[0] if status_check else "ON"
    setup_fee = safe_float(get_setting("reseller_setup_fee", "200.0"))
    min_balance = safe_float(get_setting("reseller_min_balance", "500.0"))
    if u[1]: 
        text = (f"{get_emoji('shield_icon')} <b><u>— RESELLER DASHBOARD —</u></b> {get_emoji('shield_icon')}\n\n🟢 <b>Status:</b> Active\n📅 <b>Since:</b> {u[2]}\n{get_emoji('money_icon')} <b>Total Saved:</b> {fmt_curr(u[3])}\n\n🎉 You are enjoying exclusive wholesale prices on all products!")
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
        await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
        return
    if system_status == "OFF": return await call.answer("⚠️ Wholesale / Reseller registrations are currently closed by Admin.", show_alert=True)
    text = (
        f"⚡ <b><u>— BECOME A RESELLER —</u></b> ⚡\n\n"
        f"Upgrade your account to unlock wholesale <b>Reseller Prices</b>!\n\n"
        f"💳 <b>One-time setup payment:</b> {fmt_curr(setup_fee)}\n"
        f"💰 <b>Current wallet balance:</b> {fmt_curr(u[0])}\n\n"
        f"👇 Tap below, select FamPay or ZapUPI, and complete the payment. "
        f"Reseller access activates automatically after payment verification."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text=f"💳 Pay {fmt_curr(setup_fee)} & Become Reseller",
            callback_data="execute_reseller_upgrade",
            style="success"
        )
    ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "execute_reseller_upgrade")
async def execute_reseller_upgrade(call: CallbackQuery):
    user_id = call.from_user.id
    setup_fee = round(max(0.0, safe_float(get_setting("reseller_setup_fee", "200.0"))), 2)
    u = db_query("SELECT balance, is_reseller FROM users WHERE user_id=?", (user_id,), fetchone=True)
    if not u:
        return await call.answer("User account not found. Please use /start first.", show_alert=True)
    if u[1]:
        return await call.answer("⚠️ You are already a Reseller!", show_alert=True)
    if setup_fee <= 0:
        return await call.answer("Admin has not configured a valid reseller setup fee.", show_alert=True)

    # Ensure at least one supported payment gateway is enabled and configured.
    fampay_on = (
        get_setting("gateway_fampay_enabled", "ON") == "ON"
        and bool(get_setting("fampay_api_key", ""))
        and get_setting("fampay_api_key", "") != "YOUR_FAMPAY_API_KEY"
        and get_setting("fampay_api_key", "") != "PASTE_YOUR_FAMPAY_API_KEY_HERE"
    )
    zapupi_on = (
        get_setting("gateway_zapupi_enabled", "ON") == "ON"
        and bool(get_setting("zapupi_zap_key", "").strip())
    )
    if not fampay_on and not zapupi_on:
        return await call.answer("FamPay aur ZapUPI dono configured/enabled nahi hain. Admin se contact karein.", show_alert=True)

    # The payment success handler uses this marker to activate reseller access
    # only after the gateway's server-side verification confirms payment.
    set_setting(f"pending_reseller_upgrade_{user_id}", "1")
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass
    await start_product_payment_gateway_choice(user_id, setup_fee)

@dp.callback_query(F.data == "menu_orders")
async def my_orders(call: CallbackQuery):
    orders = db_query("SELECT product_name, delivered_key, purchase_date, price_paid FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (call.from_user.id,), fetchall=True)
    if not orders: return await call.message.edit_text("🧾 You haven't made any purchases yet. Your vault is empty.", reply_markup=back_kb(), parse_mode='HTML')
    text = "🧾 <b><u>— YOUR RECENT ORDERS (LAST 10) —</u></b> 🧾\n\n"
    for o in orders: text += f"📦 <b>{o[0]}</b> ({fmt_curr(o[3])})\n🔑 <code>{o[1]}</code>\n📅 <i>{o[2]}</i>\n━━━━━━━━━━━━━━━━\n"
    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "menu_profile")
async def show_profile(call: CallbackQuery):
    u = db_query("SELECT user_id, first_name, account_type, balance, orders_count, spent, referrals_count, joined_date, is_reseller, reseller_since, total_saved, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    acc_type_display = []
    if u[8]: acc_type_display.append(f"{get_emoji('reseller')} Reseller")
    if u[11]: acc_type_display.append(f"{get_emoji('vip')} VIP")
    type_str = " | ".join(acc_type_display) if acc_type_display else f"{get_emoji('regular_user')} Regular User"
    text = (
        f"{get_emoji('grid_id')} <b><u>— YOUR SECURE PROFILE —</u></b> {get_emoji('grid_id')}\n\n"
        f"{get_emoji('grid_id')} <b>Grid ID:</b> <code>{u[0]}</code>\n"
        f"{get_emoji('name')} <b>Name:</b> {u[1]}\n"
        f"{get_emoji('account_level')} <b>Account Level:</b> {type_str}\n\n"
        f"{get_emoji('wallet_left')} <b>— Wallet —</b> {get_emoji('wallet_right')}\n"
        f"{get_emoji('wallet_left')} <b>Current Balance:</b> {fmt_curr(u[3])} {get_emoji('wallet_right')}\n\n"
        f"{get_emoji('global_stats')} <b>— Global Statistics —</b>\n"
        f"{get_emoji('total_orders')} <b>Total Orders:</b> {u[4]}\n"
        f"{get_emoji('total_spent')} <b>Total Spent:</b> {fmt_curr(u[5])}\n"
        f"{get_emoji('total_referrals')} <b>Total Referrals:</b> {u[6]}\n\n"
    )
    if u[8]:
        text += f"{get_emoji('shield_icon')} <b>— RESELLER METRICS —</b> {get_emoji('shield_icon')}\n{get_emoji('money_icon')} <b>Total Saved via Reseller:</b> {fmt_curr(u[10])}\n\n"
    text += f"{get_emoji('joined_grid')} <b>Joined Grid:</b> {u[7]}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Redeem Promo Code",
            callback_data="redeem_coupon",
            icon_custom_emoji_id=get_emoji_icon('redeem_icon'),
            style="success"
        )],
        [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "redeem_coupon")
async def redeem_coupon_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("🎟 <b>Please enter your VIP / Promo redeem code below:</b>", reply_markup=back_kb("menu_profile"), parse_mode='HTML')
    await state.set_state(UserStates.wait_for_redeem)

@dp.message(UserStates.wait_for_redeem)
async def process_redeem(m: Message, state: FSMContext):
    code = m.text.strip().upper()
    user_id = m.from_user.id
    if db_query("SELECT * FROM redeemed WHERE user_id=? AND code=?", (user_id, code), fetchone=True):
        await m.answer("❌ Anti-Fraud Alert: You already redeemed this unique code!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
        await state.clear()
        return
    coupon = db_query("SELECT amount, uses_left FROM coupons WHERE code=?", (code,), fetchone=True)
    if not coupon: await m.answer("❌ Invalid or Expired Code!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    elif coupon[1] <= 0: await m.answer("❌ This code's usage limit has been fully claimed by other users.", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    else:
        db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (coupon[0], user_id))
        db_query("UPDATE coupons SET uses_left = uses_left - 1 WHERE code=?", (code,))
        db_query("INSERT INTO redeemed (user_id, code) VALUES (?, ?)", (user_id, code))
        log_activity(user_id, "PROMO_REDEEMED", f"Code: {code}, Amount: {coupon[0]}")
        await m.answer(f"🎉 <b>Success!</b>\nSafely added {fmt_curr(coupon[0])} to your balance!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
        try:
            user_info = db_query("SELECT first_name FROM users WHERE user_id=?", (user_id,), fetchone=True)
            uname = user_info[0] if user_info else "Unknown User"
            await bot.send_message(ADMIN_ID, f"🎟 <b>PROMO CODE REDEEMED!</b>\n👤 User: {uname} (<code>{user_id}</code>)\n🔖 Code: <b>{code}</b>\n💵 Amount: {fmt_curr(coupon[0])}", parse_mode='HTML')
        except Exception: pass
    await state.clear()

@dp.callback_query(F.data == "menu_referral")
async def show_referral(call: CallbackQuery):
    u = db_query("SELECT referrals_count, referral_earned FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{call.from_user.id}"
    text = (f"{get_emoji('referral')} <b><u>AFFILIATE PROGRAM</u></b> {get_emoji('referral')}\n\n✅ <b>Status:</b> ACTIVE\n💰 Earn <b>15% flat commission</b> on every successful purchase made by your referred friends!\n\n📊 <b>YOUR STATS:</b>\n👥 Total Invited: {u[0]}\n💵 Life-time Earned: {fmt_curr(u[1])}\n\n🔗 <b>Your Invite Link:</b>\n<code>{ref_link}</code>\n\n<i>Simply copy and share this link to start earning!</i>")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

# ==============================================================================
# 16. LUDO / DICE SPIN
# ==============================================================================
@dp.callback_query(F.data == "menu_spin_landing")
async def lucky_spin_landing(call: CallbackQuery):
    status_check = db_query("SELECT value FROM settings WHERE key='spin_status'", fetchone=True)
    spin_status = status_check[0] if status_check else "ON"
    if spin_status == "OFF": return await call.answer("⚠️ Lucky Ludo Spin is currently disabled by Admin.", show_alert=True)
    await call.message.edit_text(f"{get_emoji('ludo_spin')} <b><u>— LUDO SPIN —</u></b> {get_emoji('ludo_spin')}\n\nTest your luck! You can spin once every 24 hours.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Spin Dice Now!", callback_data="execute_spin", style="success")], 
        [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ]), parse_mode='HTML')

@dp.callback_query(F.data == "execute_spin")
async def execute_spin(call: CallbackQuery):
    status_check = db_query("SELECT value FROM settings WHERE key='spin_status'", fetchone=True)
    if status_check and status_check[0] == "OFF": return await call.answer("⚠️ Lucky Spin is disabled.", show_alert=True)
    u = db_query("SELECT last_spin, balance, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    now = datetime.now()
    if u[0] and now < datetime.strptime(u[0], "%Y-%m-%d %H:%M:%S") + timedelta(hours=24):
        return await call.message.edit_text("❌ <b>Cooldown Active!</b>\nYou already played today. Come back tomorrow.", reply_markup=back_kb(), parse_mode='HTML')
    await call.message.delete()
    dice_msg = await bot.send_dice(chat_id=call.message.chat.id, emoji="🎲")
    await asyncio.sleep(SPIN_DELAY_SECONDS) 
    dice_val = dice_msg.dice.value
    limit_check = db_query("SELECT value FROM settings WHERE key='daily_spin_limit'", fetchone=True)
    limit = safe_float(limit_check[0]) if limit_check else 50.0
    rewards_db = db_query("SELECT amount FROM spin_rewards WHERE amount <= ?", (limit,), fetchall=True)
    rewards_list = [r[0] for r in rewards_db] if rewards_db else [0.0]
    reward = random.choice(rewards_list)
    if bool(u[2]) and reward > 0: reward = reward * 2.0
    new_bal = u[1] + reward
    db_query("UPDATE users SET balance=?, last_spin=? WHERE user_id=?", (new_bal, now.strftime("%Y-%m-%d %H:%M:%S"), call.from_user.id))
    log_activity(call.from_user.id, "PLAYED_SPIN", f"Reward: {reward}, Dice: {dice_val}")
    msg = get_ui_text("lucky_dice_result", dice_value=dice_val, won_amount=fmt_curr(reward), new_balance=fmt_curr(new_bal))
    if bool(u[2]) and reward > 0: msg += "\n\n<i>🌟 VIP Bonus: 2x Multiplier Applied!</i>"
    await dice_msg.reply(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📚 BACK TO MENU", callback_data="back_main", style="success")]]), parse_mode='HTML')

# ==============================================================================
# 17. TUTORIALS & SUPPORT
# ==============================================================================
@dp.callback_query(F.data == "menu_how_to")
async def tutorial_system(call: CallbackQuery):
    video_link_query = db_query("SELECT value FROM settings WHERE key='how_to_video'", fetchone=True)
    video_link = video_link_query[0] if video_link_query and video_link_query[0] != 'None' else None
    text = (f"{get_emoji('tutorial')} <b><u>— TUTORIALS & GUIDE —</u></b> {get_emoji('tutorial')}\n\n1️⃣ Add funds via <b>Add Balance</b>\n2️⃣ Navigate to <b>Buy Key</b>\n3️⃣ Choose your desired Panel and Package validity.\n4️⃣ The Key and Installation APK link will be instantly provided.")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if video_link: kb.inline_keyboard.append([InlineKeyboardButton(text="Watch Full Video Tutorial", url=video_link, icon_custom_emoji_id=get_emoji_icon("tutorial"), style="success")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "menu_support")
async def support_center(call: CallbackQuery):
    telegram_link = get_setting("support_telegram", "https://t.me/YourSupport")
    whatsapp_link = get_setting("support_whatsapp", "https://wa.me/YourNumber")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Contact on Telegram", url=telegram_link, icon_custom_emoji_id=get_emoji_icon("telegram"), style="primary")],
        [InlineKeyboardButton(text="Contact on WhatsApp", url=whatsapp_link, icon_custom_emoji_id=get_emoji_icon("whatsapp"), style="primary")],
        [InlineKeyboardButton(text="🎫 Open New Ticket", callback_data="open_ticket", style="success"), InlineKeyboardButton(text="📋 My Open Tickets", callback_data="my_tickets", style="success")], 
        [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text(f"{get_emoji('telegram')}{get_emoji('whatsapp')} <b><u>— PREMIUM SUPPORT CENTER —</u></b>\n\nContact us via Telegram or WhatsApp for instant help, or open a support ticket for admin assistance.", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "my_tickets")
async def view_my_tickets(call: CallbackQuery):
    tickets = db_query("SELECT id, message, status, created_at FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 5", (call.from_user.id,), fetchall=True)
    if not tickets: return await call.message.edit_text("📋 You do not have any active or previous support tickets.", reply_markup=back_kb("menu_support"), parse_mode='HTML')
    text = "📋 <b><u>— Your Recent Tickets —</u></b> 📋\n\n"
    for t in tickets:
        status_icon = "🟢" if t[2] == 'Open' else "🔴"
        text += f"🎫 <b>Ticket #{t[0]}</b> | Status: {status_icon} <b>{t[2]}</b>\n📅 <i>{t[3]}</i>\n📝 <i>{t[1][:80]}...</i>\n\n"
    await call.message.edit_text(text, reply_markup=back_kb("menu_support"), parse_mode='HTML')

@dp.callback_query(F.data == "open_ticket")
async def open_ticket_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("📝 <b>Please type your issue/message below in detail:</b>", reply_markup=back_kb("menu_support"), parse_mode='HTML')
    await state.set_state(UserStates.wait_for_ticket)

@dp.message(UserStates.wait_for_ticket)
async def process_ticket(m: Message, state: FSMContext):
    db_query("INSERT INTO tickets (user_id, message, created_at) VALUES (?, ?, ?)", (m.from_user.id, m.text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    await m.answer("✅ <b>Ticket Submitted Successfully!</b> Admins will reply soon.", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    try: await bot.send_message(ADMIN_ID, f"🚨 <b>NEW SUPPORT TICKET</b>\nFrom: <code>{m.from_user.id}</code>\nMsg: {m.text}", parse_mode='HTML')
    except: pass
    log_activity(m.from_user.id, "OPENED_TICKET")
    await state.clear()

# ==============================================================================
# 18. ADMIN PANEL
# ==============================================================================
@dp.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    await message.answer("⚙️ <b>Advanced Admin Terminal</b>\n<i>Authorized Access Granted.</i>", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_panel_back")
async def back_to_admin(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("⚙️ <b>Advanced Admin Terminal</b>\n<i>Authorized Access Granted.</i>", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_toggle_vip_sys")
async def toggle_vip_sys(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    res = db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True)
    current = res[0] if res else 'OFF'
    new_status = 'ON' if current == 'OFF' else 'OFF'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('vip_status', ?)", (new_status,))
    await call.message.edit_reply_markup(reply_markup=admin_kb())

@dp.callback_query(F.data.in_({"admin_block_user_start", "admin_delete_user_start"}))
async def admin_quick_user_action_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    await state.clear()
    action_label = "BLOCK / UNBLOCK" if call.data == "admin_block_user_start" else "DELETE USER"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", style="danger")]
    ])
    await call.message.edit_text(
        f"🛡️ <b>{action_label}</b>\n\nSend the user's numeric Telegram ID or @username. The next screen will show the available action buttons.",
        reply_markup=kb, parse_mode="HTML"
    )
    await state.set_state(AdminStates.manage_target_user)
    await call.answer()


@dp.callback_query(F.data == "admin_user_control_start")
async def admin_user_control_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Download Full User List", callback_data="admin_download_userlist", style="success")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text("💻 <b>User Control Terminal</b>\n\n✏️ Enter the <b>User ID</b> or <b>@Username</b> you want to investigate or manage:\n\n👇 <b>OR</b> download the full user CSV format list:", reply_markup=kb, parse_mode='HTML')
    await state.set_state(AdminStates.manage_target_user)

@dp.callback_query(F.data == "admin_download_userlist")
async def admin_download_userlist(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    users = db_query("SELECT username, user_id, phone, balance, orders_count, is_vip, is_reseller FROM users", fetchall=True)
    if not users: return await call.answer("❌ No users found in the database.", show_alert=True)
    file_content = "FULL DATABASE DUMP\n" + "="*100 + "\n"
    for u in users:
        uname = u[0] if u[0] else "No_Username"
        uid = u[1]
        phone = u[2] if u[2] else "No_Phone"
        bal = u[3]
        orders = u[4]
        vip_status = "YES" if u[5] else "NO"
        res_status = "YES" if u[6] else "NO"
        file_content += f"UID: {uid} | UNAME: {uname} | PHONE: {phone} | BAL: ₹{bal:.2f} | BUY: {orders} | VIP: {vip_status} | RES: {res_status}\n"
    doc = BufferedInputFile(file_content.encode('utf-8'), filename=f"DB_{datetime.now().strftime('%Y%m%d')}.txt")
    await call.message.answer_document(document=doc, caption="📋 <b>Database export complete.</b>", parse_mode='HTML')
    await call.answer()

@dp.callback_query(F.data == "admin_balance_add_start")
async def admin_balance_add_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminStates.wait_for_balance_user_id)
    await call.message.edit_text(
        "➕ <b>ADD USER BALANCE</b>\\n\\nSend the user's numeric Telegram ID:",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )
    await call.answer()


@dp.message(AdminStates.wait_for_balance_user_id)
async def admin_balance_get_user_id(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    raw = (m.text or "").strip()
    if not raw.isdigit():
        await m.answer("❌ Please send a valid numeric Telegram User ID.")
        return
    uid = int(raw)
    user = db_query("SELECT user_id, first_name, balance FROM users WHERE user_id=?", (uid,), fetchone=True)
    if not user:
        await m.answer("❌ This user is not registered in the bot database. Please check the ID.", reply_markup=admin_back_kb())
        return
    await state.update_data(balance_target_uid=uid)
    await state.set_state(AdminStates.wait_for_balance_add_amount)
    await m.answer(
        f"👤 User: <b>{html_lib.escape(str(user[1] or 'Unknown'))}</b>\\n🆔 ID: <code>{uid}</code>\\n💰 Current balance: <b>{fmt_curr(user[2] or 0)}</b>\\n\\nEnter amount to add (greater than ₹0):",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )


@dp.message(AdminStates.wait_for_balance_add_amount)
async def admin_balance_add_amount(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    try:
        amount = float((m.text or "").strip())
        if not (amount > 0 and amount < 1e12):
            raise ValueError
    except (ValueError, TypeError):
        await m.answer("❌ Enter a valid amount greater than ₹0.")
        return
    data = await state.get_data()
    uid = int(data["balance_target_uid"])
    user = db_query("SELECT balance FROM users WHERE user_id=?", (uid,), fetchone=True)
    if not user:
        await m.answer("❌ User no longer exists in the database.", reply_markup=admin_kb())
        await state.clear()
        return
    db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
    new_balance = safe_float(user[0]) + amount
    log_activity(uid, "ADMIN_BALANCE_ADD", f"Added ₹{amount:.2f}; new balance ₹{new_balance:.2f}")
    await m.answer(
        f"✅ Added <b>{fmt_curr(amount)}</b> to user <code>{uid}</code>.\\nNew balance: <b>{fmt_curr(new_balance)}</b>",
        reply_markup=admin_kb(), parse_mode="HTML"
    )
    try:
        await bot.send_message(uid, f"💰 <b>Wallet Balance Updated</b>\\n\\nAdmin added <b>{fmt_curr(amount)}</b> to your wallet.\\n💳 Current balance: <b>{fmt_curr(new_balance)}</b>", parse_mode="HTML")
    except Exception as e:
        logger.warning("Could not notify user %s about admin balance addition: %s", uid, e)
        await m.answer("⚠️ Balance was updated, but Telegram could not deliver the user's notification.")
    await state.clear()


@dp.callback_query(F.data == "admin_balance_remove_list")
async def admin_balance_remove_list(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminStates.wait_for_balance_remove_user_id)
    await call.message.edit_text(
        "➖ <b>REMOVE USER BALANCE</b>\n\nSend the user's numeric Telegram ID.\n\nAfter that, you can enter the amount to deduct.",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )
    await call.answer()


@dp.message(AdminStates.wait_for_balance_remove_user_id)
async def admin_balance_remove_get_user_id(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    raw = (m.text or "").strip()
    if not raw.isdigit():
        await m.answer("❌ Please send a valid numeric Telegram User ID.")
        return
    uid = int(raw)
    user = db_query("SELECT user_id, first_name, balance FROM users WHERE user_id=?", (uid,), fetchone=True)
    if not user:
        await m.answer("❌ This user is not registered in the bot database. Please check the ID.", reply_markup=admin_back_kb())
        return
    await state.update_data(target_u_id=uid)
    await state.set_state(AdminStates.wait_for_minus_money)
    await m.answer(
        f"➖ <b>REMOVE USER BALANCE</b>\n\n👤 User: <b>{html_lib.escape(str(user[1] or 'Unknown'))}</b>\n🆔 ID: <code>{uid}</code>\n💰 Current balance: <b>{fmt_curr(safe_float(user[2]))}</b>\n\nEnter the amount to deduct (greater than ₹0):",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )


@dp.message(AdminStates.manage_target_user)
async def process_user_lookup(m: Message, state: FSMContext):
    target = m.text.strip()
    if target.startswith('@'): target = target[1:]
    loader_msg = await hacker_loading(m, "Querying User Database")
    user_q = db_query("SELECT user_id, first_name, username, balance, is_reseller, orders_count, spent, joined_date, is_banned, warnings, is_vip FROM users WHERE user_id=? OR username=? COLLATE NOCASE", (target, target), fetchone=True)
    if not user_q: return await loader_msg.edit_text("❌ Target not found in the grid. Check ID/Username syntax.", reply_markup=admin_back_kb(), parse_mode='HTML')
    u_id, u_name, u_user, bal, is_res, orders, spent, joined, is_banned, warnings, is_vip = user_q
    await state.update_data(target_u_id=u_id)
    status_emoji = "🔴 BANNED" if is_banned else "🟢 ACTIVE"
    tags = []
    if is_res: tags.append("👑 Reseller")
    if is_vip: tags.append("🌟 VIP")
    type_str = " | ".join(tags) if tags else "👤 Regular"
    text = (f"🛡 <b><u>USER CONTROL TERMINAL</u></b> 🛡\n━━━━━━━━━━━━━━━━━━\n📛 <b>Name:</b> {u_name} (@{u_user})\n🆔 <b>ID:</b> <code>{u_id}</code>\n📊 <b>Status:</b> {status_emoji}\n🔰 <b>Type:</b> {type_str}\n⚠️ <b>Warnings Issued:</b> {warnings}\n━━━━━━━━━━━━━━━━━━\n💰 <b>Wallet Balance:</b> {fmt_curr(bal)}\n📦 <b>Orders:</b> {orders} | 💸 <b>Total Spent:</b> {fmt_curr(spent)}\n📅 <b>Joined:</b> {joined}\n\n🌟 <b>Give VIP:</b> VIP status deta/hata hai. VIP perks/discounts store ke VIP settings aur implementation par depend karte hain; ye Reseller status se alag hai.")
    ban_btn_text = "Unban ✅" if is_banned else "Ban 🚫"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Add Funds ➕", callback_data=f"usrctrl_add_{u_id}", style="success"), InlineKeyboardButton(text="Minus Funds ➖", callback_data=f"usrctrl_min_{u_id}", style="danger")],
        [InlineKeyboardButton(text=ban_btn_text, callback_data=f"usrctrl_ban_{u_id}", style="danger"), InlineKeyboardButton(text="Warn User ⚠️", callback_data=f"usrctrl_warn_{u_id}", style="danger")],
        [InlineKeyboardButton(text="Give VIP 🌟" if not is_vip else "Remove VIP 🚫", callback_data=f"usrctrl_vip_{u_id}", style="success")],
        [InlineKeyboardButton(text="🗑 Delete User Record", callback_data=f"usrctrl_delete_{u_id}", style="danger")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await loader_msg.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("usrctrl_"))
async def handle_user_actions(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    action_part = call.data[len("usrctrl_"):]
    action, _, uid_text = action_part.partition("_")
    u_id = int(uid_text)
    await state.update_data(target_u_id=u_id)
    if action == "delete":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Yes, Delete User Record", callback_data=f"confirm_delete_user_{u_id}", style="danger")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="admin_user_control_start", style="primary")]
        ])
        await call.message.edit_text(
            f"⚠️ <b>Delete user record?</b>\n\nUser <code>{u_id}</code> will be removed from the users table. Order/payment history is retained. They can register again with /start. This cannot be undone.",
            reply_markup=kb, parse_mode="HTML"
        )
        await call.answer()
    elif action == "ban":
        current_status_row = db_query("SELECT is_banned FROM users WHERE user_id=?", (u_id,), fetchone=True)
        current_status = current_status_row[0] if current_status_row else 0
        if current_status == 0:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Yes, Ban", callback_data=f"confirm_ban_{u_id}", style="danger"), InlineKeyboardButton(text="❌ Cancel", callback_data="admin_user_control_start", style="danger")]
            ])
            await call.message.edit_text(f"⚠️ Are you sure you want to <b>BAN</b> user <code>{u_id}</code>?", reply_markup=kb, parse_mode='HTML')
            await state.set_state(AdminStates.confirm_ban)
        else:
            db_query("UPDATE users SET is_banned=0 WHERE user_id=?", (u_id,))
            try:
                await bot.send_message(u_id, "✅ <b>Your bot access has been restored.</b> You are now unblocked and can use the bot again.", parse_mode="HTML")
            except Exception as exc:
                logger.warning("Could not notify unblocked user %s: %s", u_id, exc)
            await call.answer("✅ User unbanned successfully!", show_alert=True)
            m = call.message; m.text = str(u_id); await process_user_lookup(m, state)
    elif action == "vip":
        current_status = db_query("SELECT is_vip FROM users WHERE user_id=?", (u_id,), fetchone=True)[0]
        if current_status == 1:
            db_query("UPDATE users SET is_vip=0 WHERE user_id=?", (u_id,))
            notice = "ℹ️ <b>Your VIP status has been removed by the admin.</b>"
            await call.answer("✅ VIP Removed!", show_alert=True)
        else:
            db_query("UPDATE users SET is_vip=1, vip_since=? WHERE user_id=?", (datetime.now().strftime("%Y-%m-%d"), u_id))
            notice = "🌟 <b>Congratulations! Admin has granted you VIP status.</b>\n\nVIP perks/discounts apply according to the store's enabled VIP settings."
            await call.answer("✅ VIP Granted!", show_alert=True)
        try:
            await bot.send_message(u_id, notice, parse_mode="HTML")
        except Exception as exc:
            logger.warning("Could not notify VIP status change for user %s: %s", u_id, exc)
        m = call.message; m.text = str(u_id); await process_user_lookup(m, state)
    elif action == "add":
        await call.message.edit_text("💰 Enter the amount to <b>ADD</b> to this user's wallet:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_add_money)
    elif action == "min":
        await call.message.edit_text("💸 Enter the amount to <b>DEDUCT</b> from this user's wallet:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_minus_money)
    elif action == "warn":
        await call.message.edit_text("⚠️ Type the strict warning message you want to send directly to this user:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_warning)

@dp.callback_query(F.data.startswith("confirm_delete_user_"))
async def confirm_delete_user(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    try:
        u_id = int(call.data.rsplit("_", 1)[1])
    except ValueError:
        return await call.answer("Invalid user ID.", show_alert=True)
    user = db_query("SELECT user_id FROM users WHERE user_id=?", (u_id,), fetchone=True)
    if not user:
        await call.answer("User record was already deleted.", show_alert=True)
        return
    db_query("DELETE FROM users WHERE user_id=?", (u_id,))
    log_activity(u_id, "ADMIN_DELETE_USER", "Removed user record; order/payment history retained")
    try:
        await bot.send_message(
            u_id,
            "ℹ️ <b>Your bot account record has been removed by the admin.</b> You may use /start to register again."
        )
    except Exception as exc:
        logger.info("Could not notify deleted user %s: %s", u_id, exc)
    await state.clear()
    await call.answer("User record deleted.", show_alert=True)
    await call.message.edit_text(
        f"✅ User <code>{u_id}</code> record deleted. Order and payment history were retained.",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("confirm_ban_"))
async def confirm_ban(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    u_id = int(call.data.split("_")[2])
    db_query("UPDATE users SET is_banned=1 WHERE user_id=?", (u_id,))
    try:
        await bot.send_message(u_id, "🚫 <b>Your access to this bot has been blocked by the admin.</b> If you believe this is a mistake, please contact support.")
    except Exception as exc:
        logger.warning("Could not notify blocked user %s: %s", u_id, exc)
    await call.answer("🔴 User has been banned!", show_alert=True)
    await state.clear()
    m = call.message; m.text = str(u_id); await process_user_lookup(m, state)

@dp.message(AdminStates.wait_for_add_money)
async def exec_add_money(m: Message, state: FSMContext):
    try:
        amt = float(m.text)
        data = await state.get_data()
        u_id = data['target_u_id']
        db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (amt, u_id))
        await m.answer(f"✅ Successfully added {fmt_curr(amt)} to target <code>{u_id}</code>.", reply_markup=admin_kb(), parse_mode='HTML')
        try: await bot.send_message(u_id, f"💰 <b>Wallet Top-up!</b>\nAdmin has manually added {fmt_curr(amt)} to your wallet.", parse_mode='HTML')
        except: pass
        await state.clear()
    except ValueError: await m.answer("❌ Critical Error: Input must be a valid number.")

@dp.message(AdminStates.wait_for_minus_money)
async def exec_minus_money(m: Message, state: FSMContext):
    try:
        amt = float((m.text or "").strip())
        if not (amt > 0 and amt < 1e12):
            raise ValueError
        data = await state.get_data()
        u_id = int(data['target_u_id'])
        user = db_query("SELECT balance FROM users WHERE user_id=?", (u_id,), fetchone=True)
        if not user:
            await m.answer("❌ User not found.", reply_markup=admin_kb())
            await state.clear()
            return
        old_balance = safe_float(user[0])
        if amt > old_balance:
            await m.answer(f"❌ Insufficient balance. Current balance is {fmt_curr(old_balance)}. Enter a smaller amount.")
            return
        db_query("UPDATE users SET balance = balance - ? WHERE user_id=?", (amt, u_id))
        new_balance = old_balance - amt
        log_activity(u_id, "ADMIN_BALANCE_REMOVE", f"Removed ₹{amt:.2f}; new balance ₹{new_balance:.2f}")
        await m.answer(f"✅ Deducted {fmt_curr(amt)} from user <code>{u_id}</code>.\\nNew balance: <b>{fmt_curr(new_balance)}</b>", reply_markup=admin_kb(), parse_mode='HTML')
        try:
            await bot.send_message(u_id, f"⚠️ <b>Wallet Balance Updated</b>\\n\\nAdmin deducted <b>{fmt_curr(amt)}</b> from your wallet.\\n💳 Current balance: <b>{fmt_curr(new_balance)}</b>", parse_mode='HTML')
        except Exception as e:
            logger.warning("Could not notify user %s about admin balance deduction: %s", u_id, e)
            await m.answer("⚠️ Balance was updated, but Telegram could not deliver the user's notification.")
        await state.clear()
    except ValueError: await m.answer("❌ Enter a valid amount greater than ₹0.")

@dp.message(AdminStates.wait_for_warning)
async def exec_warn_user(m: Message, state: FSMContext):
    data = await state.get_data()
    u_id = data['target_u_id']
    warn_text = m.text
    db_query("UPDATE users SET warnings = warnings + 1 WHERE user_id=?", (u_id,))
    await m.answer(f"✅ Official warning dispatched to <code>{u_id}</code>.", reply_markup=admin_kb(), parse_mode='HTML')
    try: await bot.send_message(u_id, f"⚠️ <b>OFFICIAL WARNING FROM SYSTEM ADMIN:</b>\n\n{warn_text}\n\n<i>Subsequent infractions may lead to an automated grid ban.</i>", parse_mode='HTML')
    except: pass
    await state.clear()

# ==============================================================================
# 19. ADMIN STATISTICS
# ==============================================================================
@dp.callback_query(F.data == "admin_view_stats")
async def admin_dashboard_stats(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    t_users = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    t_resellers = db_query("SELECT COUNT(*) FROM users WHERE is_reseller=1", fetchone=True)[0]
    t_vip = db_query("SELECT COUNT(*) FROM users WHERE is_vip=1", fetchone=True)[0]
    t_prods = db_query("SELECT COUNT(*) FROM products", fetchone=True)[0]
    t_keys = db_query("SELECT COUNT(*) FROM product_keys WHERE is_used=0", fetchone=True)[0]
    t_rev = db_query("SELECT SUM(spent) FROM users", fetchone=True)[0] or 0.0
    today_str = datetime.now().strftime("%Y-%m-%d")
    t_spins = db_query("SELECT COUNT(*) FROM users WHERE last_spin LIKE ?", (f"{today_str}%",), fetchone=True)[0]
    msg = (f"📊 <b><u>GRID INTELLIGENCE DASHBOARD</u></b> 📊\n━━━━━━━━━━━━━━━━━━\n👥 <b>Total Grid Users:</b> {t_users}\n👑 <b>Wholesale Resellers:</b> {t_resellers}\n🌟 <b>Elite VIP Members:</b> {t_vip}\n━━━━━━━━━━━━━━━━━━\n📦 <b>Active Products:</b> {t_prods}\n🔑 <b>Unused Keys in Vault:</b> {t_keys}\n💰 <b>Total Gross Revenue:</b> {fmt_curr(t_rev)}\n🎰 <b>Ludo Spins Today:</b> {t_spins}\n━━━━━━━━━━━━━━━━━━")
    await call.message.edit_text(msg, reply_markup=admin_back_kb(), parse_mode='HTML')

# ==============================================================================
# =============================================================================
# PRODUCT MAINTENANCE — imported concept from SAGAR_MODS_API.zip
# =============================================================================
@dp.callback_query(F.data == "admin_product_maintenance")
async def admin_product_maintenance_list(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in get_categories():
        row = db_query("SELECT COUNT(*) FROM products WHERE UPPER(TRIM(category))=?", (cat,), fetchone=True)
        if row and row[0]:
            kb.inline_keyboard.append([InlineKeyboardButton(
                text=cat, callback_data="admin_maint_cat_" + cat,
                icon_custom_emoji_id=get_category_emoji(cat), style="success")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="admin_panel_back", style="danger")])
    await call.message.edit_text("🛠 <b>PRODUCT MAINTENANCE</b>\n\nChoose a category:", reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("admin_maint_cat_"))
async def admin_product_maintenance_category(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    category = call.data.split("admin_maint_cat_", 1)[1]
    rows = db_query("""SELECT MIN(id), MIN(TRIM(panel_name)), MAX(COALESCE(maintenance,0))
                       FROM products WHERE UPPER(TRIM(category))=?
                       AND TRIM(COALESCE(panel_name,'')) != ''
                       GROUP BY LOWER(TRIM(panel_name))
                       ORDER BY MIN(TRIM(panel_name)) COLLATE NOCASE""", (category,), fetchall=True) or []
    if not rows:
        rows = db_query("""SELECT MIN(id), MIN(TRIM(name)), MAX(COALESCE(maintenance,0))
                           FROM products WHERE UPPER(TRIM(category))=?
                           GROUP BY LOWER(TRIM(name)) ORDER BY MIN(TRIM(name)) COLLATE NOCASE""",
                        (category,), fetchall=True) or []
    if not rows:
        return await call.answer("No products found in this category.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for prod_id, panel, maintenance in rows:
        panel = str(panel or "").strip()
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{'🔴' if maintenance else '🟢'} {panel[:55]}",
            callback_data=f"admin_maint_product_{prod_id}",
            icon_custom_emoji_id=get_panel_emoji(panel) or get_category_emoji(category),
            style="danger" if maintenance else "success")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Back to Categories", callback_data="admin_product_maintenance", style="danger")])
    await call.message.edit_text(f"🛠 <b>PRODUCT MAINTENANCE</b>\n\n{html_lib.escape(category)}\nTap a panel/product to toggle maintenance.", reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("admin_maint_product_"))
async def admin_maint_product_detail(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    try:
        prod_id = int(call.data.rsplit("_", 1)[1])
    except ValueError:
        return await call.answer("Invalid product.", show_alert=True)
    row = db_query("SELECT category, panel_name, name FROM products WHERE id=?", (prod_id,), fetchone=True)
    if not row:
        return await call.answer("Product not found.", show_alert=True)
    category, panel_name, product_name = row
    identity = str(panel_name or product_name or "").strip()
    use_panel = bool(str(panel_name or "").strip())
    if use_panel:
        state_row = db_query("""SELECT MAX(COALESCE(maintenance,0)) FROM products
                                WHERE UPPER(TRIM(category))=? AND LOWER(TRIM(panel_name))=LOWER(TRIM(?))""",
                             (str(category).upper().strip(), identity), fetchone=True)
        new_state = 0 if (state_row and bool(state_row[0])) else 1
        db_query("""UPDATE products SET maintenance=? WHERE UPPER(TRIM(category))=?
                    AND LOWER(TRIM(panel_name))=LOWER(TRIM(?))""",
                 (new_state, str(category).upper().strip(), identity))
    else:
        state_row = db_query("SELECT COALESCE(maintenance,0) FROM products WHERE id=?", (prod_id,), fetchone=True)
        new_state = 0 if (state_row and bool(state_row[0])) else 1
        db_query("UPDATE products SET maintenance=? WHERE id=?", (new_state, prod_id))
    await call.answer("🔴 Maintenance ON" if new_state else "🟢 Maintenance OFF")
    # Return to the category list for the selected category.
    cat = str(category or "")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    rows = db_query("""SELECT MIN(id), MIN(TRIM(COALESCE(NULLIF(panel_name,''), name))), MAX(COALESCE(maintenance,0))
                       FROM products WHERE UPPER(TRIM(category))=?
                       GROUP BY LOWER(TRIM(COALESCE(NULLIF(panel_name,''), name)))
                       ORDER BY MIN(TRIM(COALESCE(NULLIF(panel_name,''), name))) COLLATE NOCASE""",
                    (cat.upper().strip(),), fetchall=True) or []
    for pid, pname, maint in rows:
        pname = str(pname or "").strip()
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{'🔴' if maint else '🟢'} {pname[:55]}",
            callback_data=f"admin_maint_product_{pid}", icon_custom_emoji_id=get_panel_emoji(pname) or get_category_emoji(cat),
            style="danger" if maint else "success")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Back to Categories", callback_data="admin_product_maintenance", style="danger")])
    await call.message.edit_text(f"🛠 <b>PRODUCT MAINTENANCE</b>\n\n{html_lib.escape(cat)}\nTap a panel/product to toggle maintenance.", reply_markup=kb, parse_mode="HTML")

# Admin-managed custom product categories
@dp.callback_query(F.data == "admin_add_category")
async def admin_add_category_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    await state.clear()
    await state.set_state(AdminStates.wait_for_new_category_name)
    await call.message.edit_text(
        "➕ <b>ADD PRODUCT CATEGORY</b>\\n\\n"
        "Send the new category/button name. Example: <code>VII PRODUCT</code>\\n"
        "This category will appear in Add Product, Set Product Demo, Product Maintenance, "
        "and other category menus.",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )
    await call.answer()

@dp.message(AdminStates.wait_for_new_category_name)
async def admin_add_category_save(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    name = " ".join((message.text or "").strip().upper().split())
    if not name or len(name) > 60:
        return await message.answer("❌ Category name must be between 1 and 60 characters. Try again.")
    if name.startswith("/") or any(ch in name for ch in "\\n\\r"):
        return await message.answer("❌ Please send a valid category name.")
    categories = get_categories()
    if name.casefold() in {c.casefold() for c in categories}:
        await state.clear()
        return await message.answer(
            f"ℹ️ Category <b>{html_lib.escape(name)}</b> already exists.",
            reply_markup=admin_kb(), parse_mode="HTML"
        )
    try:
        raw = get_setting("custom_product_categories", "[]")
        saved = json.loads(raw) if raw else []
        if not isinstance(saved, list):
            saved = []
    except Exception:
        saved = []
    saved.append(name)
    set_setting("custom_product_categories", json.dumps(saved, ensure_ascii=False))
    await state.clear()
    await message.answer(
        f"✅ <b>Category added!</b>\\n\\n"
        f"📂 <b>{html_lib.escape(name)}</b> is now available in Add Product, "
        "Set Product Demo, Product Maintenance, and other category menus.",
        reply_markup=admin_kb(), parse_mode="HTML"
    )


@dp.callback_query(F.data == "admin_edit_category")
async def admin_edit_category_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    await state.clear()
    try:
        raw = get_setting("custom_product_categories", "[]")
        saved = json.loads(raw) if raw else []
        if not isinstance(saved, list):
            saved = []
    except Exception:
        saved = []
    categories = list(dict.fromkeys(str(x).strip().upper() for x in saved if str(x).strip()))
    if not categories:
        return await call.answer("No admin-created categories to edit.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in categories:
        token = hashlib.sha1(cat.encode("utf-8")).hexdigest()[:12]
        set_setting("edit_category_target_" + token, cat)
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"✏️ {cat[:50]}", callback_data=f"admin_edit_cat_{token}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="admin_panel_back", style="danger")])
    await call.message.edit_text("✏️ <b>EDIT PRODUCT CATEGORY</b>\\n\\nChoose the category whose name you want to change.", reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("admin_edit_cat_"))
async def admin_edit_category_pick(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    token = call.data[len("admin_edit_cat_"):]
    category = get_setting("edit_category_target_" + token, "").strip().upper()
    if not category:
        return await call.answer("Category selection expired. Reopen Edit Product Category.", show_alert=True)
    await state.update_data(old_category=category)
    await state.set_state(AdminStates.wait_for_category_rename)
    await call.message.edit_text(
        f"✏️ <b>Rename Product Category</b>\\n\\nCurrent name: <code>{html_lib.escape(category)}</code>\\n\\nSend the new category name. It will update existing products and category menus too.",
        reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()

@dp.message(AdminStates.wait_for_category_rename)
async def admin_edit_category_save(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    new_name = " ".join((message.text or "").strip().upper().split())
    if not new_name or len(new_name) > 60 or new_name.startswith("/"):
        return await message.answer("❌ Category name must be between 1 and 60 characters. Try again.")
    data = await state.get_data()
    old_name = str(data.get("old_category", "")).strip().upper()
    if not old_name:
        await state.clear()
        return await message.answer("Edit session expired. Open Edit Product Category again.", reply_markup=admin_kb())
    categories = get_categories()
    if new_name.casefold() != old_name.casefold() and new_name.casefold() in {x.casefold() for x in categories}:
        return await message.answer("❌ This category name already exists. Send a different name.")
    try:
        raw = get_setting("custom_product_categories", "[]")
        saved = json.loads(raw) if raw else []
        if not isinstance(saved, list):
            saved = []
    except Exception:
        saved = []
    updated = [new_name if str(x).strip().casefold() == old_name.casefold() else str(x).strip().upper()
               for x in saved if str(x).strip()]
    if not any(str(x).strip().casefold() == new_name.casefold() for x in updated):
        await state.clear()
        return await message.answer("❌ Admin-created category was not found.", reply_markup=admin_kb())
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE products SET category=? WHERE UPPER(TRIM(category))=?", (new_name, old_name))
        changed = cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Category rename failed")
        return await message.answer("❌ Category rename failed; database was not changed.", reply_markup=admin_kb())
    finally:
        conn.close()
    set_setting("custom_product_categories", json.dumps(list(dict.fromkeys(updated)), ensure_ascii=False))
    old_emoji = get_setting(f"cat_emoji_{old_name}", "")
    if old_emoji:
        set_setting(f"cat_emoji_{new_name}", old_emoji)
        set_setting(f"cat_emoji_{old_name}", "")
    await state.clear()
    await message.answer(
        f"✅ <b>Category renamed successfully!</b>\\n\\nOld: <code>{html_lib.escape(old_name)}</code>\\nNew: <code>{html_lib.escape(new_name)}</code>\\nUpdated products: <b>{changed}</b>",
        reply_markup=admin_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_delete_category")
async def admin_delete_category_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    try:
        raw = get_setting("custom_product_categories", "[]")
        saved = json.loads(raw) if raw else []
        if not isinstance(saved, list):
            saved = []
    except Exception:
        saved = []
    custom = list(dict.fromkeys(str(x).strip().upper() for x in saved if str(x).strip()))
    if not custom:
        return await call.answer("No custom categories to delete.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in custom:
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"🗑️ {cat[:50]}", callback_data=f"admin_del_cat_{cat}", style="danger")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Back", callback_data="admin_panel_back", style="primary")])
    await call.message.edit_text(
        "🗑️ <b>DELETE PRODUCT CATEGORY</b>\n\nChoose a custom category to remove.\n"
        "Categories that still contain products cannot be deleted.",
        reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("admin_del_cat_"))
async def admin_delete_category_confirm(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    category = call.data[len("admin_del_cat_"):].strip().upper()
    if category in FIXED_CATEGORIES:
        return await call.answer("Built-in categories cannot be deleted.", show_alert=True)
    count = db_query("SELECT COUNT(*) FROM products WHERE UPPER(TRIM(category))=?", (category,), fetchone=True)
    if count and int(count[0] or 0) > 0:
        return await call.answer("This category has products. Remove/move its products first.", show_alert=True)
    try:
        raw = get_setting("custom_product_categories", "[]")
        saved = json.loads(raw) if raw else []
        if not isinstance(saved, list):
            saved = []
    except Exception:
        saved = []
    updated = [str(x).strip().upper() for x in saved if str(x).strip().casefold() != category.casefold()]
    if len(updated) == len([x for x in saved if str(x).strip()]):
        return await call.answer("Custom category not found.", show_alert=True)
    set_setting("custom_product_categories", json.dumps(updated, ensure_ascii=False))
    await call.answer(f"Deleted: {category}", show_alert=True)
    await call.message.edit_text(f"✅ Category <b>{html_lib.escape(category)}</b> deleted.", reply_markup=admin_kb(), parse_mode="HTML")


# Admin utilities: delete/hide all products in a selected category, user totals, and wallet ranking.
def _admin_category_keyboard(prefix: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in get_categories():
        token = hashlib.sha1(cat.encode("utf-8")).hexdigest()[:12]
        set_setting(f"{prefix}_category_target_{token}", cat)
        count = db_query("SELECT COUNT(*) FROM products WHERE UPPER(TRIM(COALESCE(category,'')))=UPPER(TRIM(?))", (cat,), fetchone=True)
        total = int(count[0] or 0) if count else 0
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{cat[:42]} ({total})", callback_data=f"{prefix}_cat_{token}", style="danger" if prefix == "admin_delpanel" else "primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="admin_panel_back", style="danger")])
    return kb

@dp.callback_query(F.data == "admin_delete_panel")
async def admin_delete_panel_start(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    await call.message.edit_text("🗑️ <b>DELETE PANEL CATEGORY</b>\nChoose a category. This permanently deletes every product and its stored keys in that category.", reply_markup=_admin_category_keyboard("admin_delpanel"), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("admin_delpanel_cat_"))
async def admin_delete_panel_category(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    token = call.data.rsplit("_", 1)[-1]
    cat = get_setting(f"admin_delpanel_category_target_{token}", "")
    if not cat:
        return await call.answer("Category selection expired. Reopen Delete Panel.", show_alert=True)
    rows = db_query("SELECT id FROM products WHERE UPPER(TRIM(COALESCE(category,'')))=UPPER(TRIM(?))", (cat,), fetchall=True) or []
    ids = [int(r[0]) for r in rows]
    for pid in ids:
        db_query("DELETE FROM product_keys WHERE product_id=?", (pid,))
    db_query("DELETE FROM products WHERE UPPER(TRIM(COALESCE(category,'')))=UPPER(TRIM(?))", (cat,))
    await call.answer(f"Deleted {len(ids)} product(s).", show_alert=True)
    await call.message.edit_text(f"✅ Deleted category <b>{html_lib.escape(cat)}</b> and {len(ids)} product(s).", reply_markup=admin_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_hide_panel")
async def admin_hide_panel_start(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    await call.message.edit_text(
        "🙈 <b>HIDE PANEL</b>\nFirst choose a category (Android Nonroot, Android Root, iPhone, PC, or a custom category).\nThen choose the specific panel inside it.",
        reply_markup=_admin_category_keyboard("admin_hidepanel"), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("admin_hidepanel_cat_"))
async def admin_hide_panel_category(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    token = call.data.rsplit("_", 1)[-1]
    cat = get_setting(f"admin_hidepanel_category_target_{token}", "")
    if not cat:
        return await call.answer("Category selection expired. Reopen Hide Panel.", show_alert=True)
    rows = db_query(
        "SELECT panel_name, COUNT(*), MAX(COALESCE(is_active,1)) FROM products "
        "WHERE UPPER(TRIM(COALESCE(category,'')))=UPPER(TRIM(?)) "
        "AND TRIM(COALESCE(panel_name,''))<>'' GROUP BY LOWER(TRIM(panel_name)), panel_name "
        "ORDER BY LOWER(TRIM(panel_name))", (cat,), fetchall=True) or []
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for panel, count, active in rows:
        panel = str(panel or '').strip()
        if not panel:
            continue
        panel_token = hashlib.sha1((cat + "\0" + panel).encode("utf-8")).hexdigest()[:12]
        set_setting(f"admin_hidepanel_panel_target_{panel_token}", json.dumps({"category": cat, "panel": panel}, ensure_ascii=False))
        status = "🟢 Visible" if int(active or 0) else "🙈 Hidden"
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{status} · {panel[:32]} ({int(count or 0)})",
            callback_data=f"admin_hidepanel_panel_{panel_token}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Back to Categories", callback_data="admin_hide_panel", style="danger")])
    await call.message.edit_text(
        f"🙈 <b>HIDE PANEL</b>\nCategory: <b>{html_lib.escape(cat)}</b>\n\n"
        "Now select the exact panel to hide. Hidden panels can be selected again to make them visible.",
        reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("admin_hidepanel_panel_"))
async def admin_hide_panel_selected(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    token = call.data.rsplit("_", 1)[-1]
    raw = get_setting(f"admin_hidepanel_panel_target_{token}", "")
    try:
        target = json.loads(raw)
        cat, panel = str(target["category"]), str(target["panel"])
    except Exception:
        return await call.answer("Panel selection expired. Reopen Hide Panel.", show_alert=True)
    row = db_query(
        "SELECT MAX(COALESCE(is_active,1)) FROM products WHERE "
        "UPPER(TRIM(COALESCE(category,'')))=UPPER(TRIM(?)) AND LOWER(TRIM(COALESCE(panel_name,'')))=LOWER(TRIM(?))",
        (cat, panel), fetchone=True)
    if not row:
        return await call.answer("Panel not found.", show_alert=True)
    new_status = 0 if int(row[0] or 0) else 1
    db_query(
        "UPDATE products SET is_active=? WHERE UPPER(TRIM(COALESCE(category,'')))=UPPER(TRIM(?)) "
        "AND LOWER(TRIM(COALESCE(panel_name,'')))=LOWER(TRIM(?))", (new_status, cat, panel))
    await call.answer("Panel hidden." if new_status == 0 else "Panel made visible.", show_alert=True)
    # Refresh the panel list for the same category.
    cat_token = hashlib.sha1(cat.encode("utf-8")).hexdigest()[:12]
    # Reuse the category callback's saved target token, regardless of prior keyboard instance.
    set_setting(f"admin_hidepanel_category_target_{cat_token}", cat)
    rows = db_query(
        "SELECT panel_name, COUNT(*), MAX(COALESCE(is_active,1)) FROM products "
        "WHERE UPPER(TRIM(COALESCE(category,'')))=UPPER(TRIM(?)) AND TRIM(COALESCE(panel_name,''))<>'' "
        "GROUP BY LOWER(TRIM(panel_name)), panel_name ORDER BY LOWER(TRIM(panel_name))", (cat,), fetchall=True) or []
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for pname, count, active in rows:
        pname = str(pname or '').strip()
        ptoken = hashlib.sha1((cat + "\0" + pname).encode("utf-8")).hexdigest()[:12]
        set_setting(f"admin_hidepanel_panel_target_{ptoken}", json.dumps({"category": cat, "panel": pname}, ensure_ascii=False))
        status = "🟢 Visible" if int(active or 0) else "🙈 Hidden"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{status} · {pname[:32]} ({int(count or 0)})", callback_data=f"admin_hidepanel_panel_{ptoken}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Back to Categories", callback_data="admin_hide_panel", style="danger")])
    await call.message.edit_text(
        f"🙈 <b>HIDE PANEL</b>\nCategory: <b>{html_lib.escape(cat)}</b>\n\n"
        "Select a panel to hide or make visible:", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_total_users")
async def admin_total_users(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    total = db_query("SELECT COUNT(*) FROM users", fetchone=True)
    resellers = db_query("SELECT COUNT(*) FROM users WHERE is_reseller=1", fetchone=True)
    regular = db_query("SELECT COUNT(*) FROM users WHERE COALESCE(is_reseller,0)=0", fetchone=True)
    msg = ("👥 <b>TOTAL USER REPORT</b>\n━━━━━━━━━━━━━━━━━━\n"
           f"👤 Total Users: <b>{int(total[0] or 0) if total else 0}</b>\n"
           f"👑 Reseller Users: <b>{int(resellers[0] or 0) if resellers else 0}</b>\n"
           f"🙋 Regular Users: <b>{int(regular[0] or 0) if regular else 0}</b>")
    await call.message.edit_text(msg, reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data == "admin_user_balances")
async def admin_user_balances(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    rows = db_query("SELECT user_id, first_name, username, balance, COALESCE(is_reseller,0) FROM users ORDER BY balance DESC, user_id ASC LIMIT 50", fetchall=True) or []
    if not rows:
        return await call.message.edit_text("No users registered yet.", reply_markup=admin_back_kb())
    lines = ["💰 <b>USER CHECK BALANCE</b>", "<i>Top 50 users, highest balance first.</i>", "━━━━━━━━━━━━━━━━━━"]
    for i, row in enumerate(rows, 1):
        uid, name, username, balance, reseller = row
        kind = "👑 RESELLER USER" if reseller else "🙋 REGULAR USER"
        display = html_lib.escape(str(name or "Unknown"))
        handle = f" @{html_lib.escape(str(username))}" if username else ""
        lines.append(f"{i}. <b>{display}</b>{handle}\n🆔 <code>{uid}</code> · {kind}\n💰 <b>{fmt_curr(safe_float(balance))}</b>")
    lines.append("━━━━━━━━━━━━━━━━━━\nShowing up to 50 users.")
    await call.message.edit_text("\n".join(lines), reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()

# 20. ADMIN PRODUCT MANAGEMENT
# ==============================================================================
@dp.callback_query(F.data == "admin_add_prod")
async def add_prod_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    await state.clear()
    categories = get_categories()
    if not categories:
        return await call.answer("No categories found.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in categories:
        # Keep callback_data short: Telegram limits it to 64 bytes.
        token = hashlib.sha1(cat.encode("utf-8")).hexdigest()[:12]
        set_setting(f"addprod_category_{token}", cat)
        emoji_id = get_category_emoji(cat)
        button = InlineKeyboardButton(
            text=cat[:60], callback_data=f"addprod_cat_{token}", style="primary"
        )
        if emoji_id:
            button.icon_custom_emoji_id = emoji_id
        kb.inline_keyboard.append([button])
    kb.inline_keyboard.append([InlineKeyboardButton(
        text="Cancel", callback_data="admin_panel_back",
        icon_custom_emoji_id=get_emoji_icon("back"), style="danger"
    )])
    await call.answer()
    await call.message.edit_text(
        "<b>Step 1:</b> Choose the <b>Category</b> for this product:",
        reply_markup=kb, parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("addprod_cat_"))
async def add_prod_category_selected(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    token = call.data[len("addprod_cat_"):]
    category = get_setting(f"addprod_category_{token}", "")
    if not category or category not in get_categories():
        return await call.answer("Category not found. Please reopen Add Product.", show_alert=True)
    await state.clear()
    await state.update_data(cat=category)
    await state.set_state(AdminStates.add_prod_panel_name)
    await call.answer()
    await call.message.edit_text(
        f"<b>Step 2:</b> Enter <b>PANEL NAME</b>\\n(e.g., 'MST PANEL', 'DRIP PANEL'):",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )

@dp.message(AdminStates.add_prod_panel_name)
async def add_prod_panel_name(m: Message, state: FSMContext):
    await state.update_data(panel_name=m.text)
    await m.answer("<b>Step 3:</b> Enter <b>PACKAGE DURATION/DATE NAME</b>\n(e.g., '7 Days', '1 Month'):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_name)

@dp.message(AdminStates.add_prod_name)
async def add_prod_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text)
    await m.answer("⏳ Enter Time Validity String (e.g., '24 Hours'):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_validity)

@dp.message(AdminStates.add_prod_validity)
async def add_prod_validity(m: Message, state: FSMContext):
    await state.update_data(validity=m.text)
    await m.answer("📱 Enter strict Device Enforcement Limit (e.g., '1 Device HWID'):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_device_limit)

@dp.message(AdminStates.add_prod_device_limit)
async def add_prod_device_limit(m: Message, state: FSMContext):
    await state.update_data(device_limit=m.text)
    await m.answer("💰 Enter standard **User Price** in Rupees (₹) (e.g., 500):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_price)

@dp.message(AdminStates.add_prod_price)
async def add_prod_price(m: Message, state: FSMContext):
    try:
        await state.update_data(price=float(m.text))
        await m.answer("👑 Enter wholesale **Reseller Price** in Rupees (₹) (e.g., 300):", parse_mode='HTML')
        await state.set_state(AdminStates.add_prod_reseller_price)
    except ValueError: await m.answer("❌ Invalid input datatype! Must be numerical.")

@dp.message(AdminStates.add_prod_reseller_price)
async def add_prod_reseller_price(m: Message, state: FSMContext):
    try:
        await state.update_data(reseller_price=float(m.text))
        await m.answer("🔗 Enter direct APK/Payload Download Link (or type 'none' to omit):", parse_mode='HTML')
        await state.set_state(AdminStates.add_prod_apk)
    except ValueError: await m.answer("❌ Invalid input datatype! Must be numerical.")

@dp.message(AdminStates.add_prod_apk)
async def add_prod_apk(m: Message, state: FSMContext):
    await state.update_data(apk="" if (m.text or "").strip().lower() == 'none' else (m.text or "").strip())
    await m.answer(
        "🔌 <b>API TARGET / PID</b>\n\n"
        "Send the <b>API Target Product ID (PID)</b> from the reseller API for automatic key generation.\n"
        "Example: <code>151</code>\n\n"
        "If this product should use manual keys, type <code>none</code>.",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.add_prod_api_pid)

@dp.message(AdminStates.add_prod_api_pid)
async def add_prod_api_pid(m: Message, state: FSMContext):
    txt = (m.text or "").strip()
    if txt.lower() in ("none", "no", "skip", ""):
        await state.update_data(api_pid="", api_duration="")
        await m.answer(
            "📥 <b>Manual Key Mode</b>\n\nPaste all license <b>Keys</b>, one key per line:",
            parse_mode='HTML'
        )
        await state.set_state(AdminStates.add_prod_keys)
        return
    await state.update_data(api_pid=txt)
    await m.answer(
        "⏱ Send the API <b>duration</b> exactly as supported by the API.\n"
        "Example: <code>1 Day</code>, <code>7 Days</code>, <code>1 Month</code>.\n\n"
        "Type <code>none</code> if the API PID does not need a duration.",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.add_prod_api_duration)

@dp.message(AdminStates.add_prod_api_duration)
async def add_prod_api_duration(m: Message, state: FSMContext):
    txt = (m.text or "").strip()
    duration = "" if txt.lower() in ("none", "no", "skip", "") else txt
    data = await state.get_data()
    db_query(
        "INSERT INTO products (category, panel_name, name, price_inr, reseller_price, stock, apk_link, validity, device_limit, api_product_id, api_duration) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (data['cat'], data['panel_name'], data['name'], data['price'], data['reseller_price'], 999, data['apk'], data['validity'], data['device_limit'], data['api_pid'], duration)
    )
    await m.answer(
        f"✅ <b>Product Added with AUTO API KEY!</b>\n\n"
        f"📦 <b>Category:</b> {html_lib.escape(str(data['cat']))}\n"
        f"🧩 <b>Panel:</b> {html_lib.escape(str(data['panel_name']))}\n"
        f"📌 <b>Product:</b> {html_lib.escape(str(data['name']))}\n"
        f"💰 <b>User Price:</b> {fmt_curr(data['price'])}\n"
        f"👑 <b>Reseller Price:</b> {fmt_curr(data['reseller_price'])}\n"
        f"🔌 <b>API Target/PID:</b> <code>{html_lib.escape(data['api_pid'])}</code>"
        f"{' | ' + html_lib.escape(duration) if duration else ''}\n"
        "⚡ <b>Keys will be generated automatically on purchase.</b>",
        reply_markup=admin_kb(), parse_mode='HTML'
    )
    await state.clear()

@dp.message(AdminStates.add_prod_keys)
async def add_prod_keys(m: Message, state: FSMContext):
    keys = [k.strip() for k in m.text.strip().split('\n') if k.strip()]
    data = await state.get_data()
    stock = len(keys)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO products (category, panel_name, name, price_inr, reseller_price, stock, apk_link, validity, device_limit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (data['cat'], data['panel_name'], data['name'], data['price'], data['reseller_price'], stock, data['apk'], data['validity'], data['device_limit']))
    prod_id = c.lastrowid
    for k in keys: c.execute("INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)", (prod_id, k))
    conn.commit()
    conn.close()
    await m.answer(f"✅ <b>Data Deployment Successful!</b>\n\n📦 Panel '{data['cat']}' -> Panel Name '{data['panel_name']}' -> Package '{data['name']}'\n🔒 Vault Stock: {stock} Keys injected.\n💰 User Price: {fmt_curr(data['price'])} | 👑 Reseller: {fmt_curr(data['reseller_price'])}", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_panel_name_change")
async def admin_panel_name_change(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Not authorized.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    categories = get_categories()
    for label in categories:
        token = hashlib.sha1(label.encode("utf-8")).hexdigest()[:12]
        set_setting("rename_category_target_" + token, label)
        kb.inline_keyboard.append([InlineKeyboardButton(text=label[:60], callback_data=f"rename_cat_{token}", style="success")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="admin_panel_back", style="danger")])
    await state.clear()
    await call.message.edit_text("✏️ <b>PANEL NAME CHANGE</b>\n\nChoose the category, then select the existing panel name. Renaming will update every product row using that panel name, not just one package.", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("rename_cat_"))
async def admin_rename_category(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Not authorized.", show_alert=True)
    token = call.data[len("rename_cat_"):]
    category = get_setting("rename_category_target_" + token, "").strip()
    if not category or category.casefold() not in {x.casefold() for x in get_categories()}:
        return await call.answer("Category selection expired. Reopen Panel Name Change.", show_alert=True)
    rows = db_query("SELECT MIN(TRIM(panel_name)) FROM products WHERE UPPER(TRIM(COALESCE(category,'')))=UPPER(TRIM(?)) AND TRIM(COALESCE(panel_name,'')) != '' GROUP BY LOWER(TRIM(panel_name)) ORDER BY MIN(TRIM(panel_name)) COLLATE NOCASE", (category,), fetchall=True) or []
    if not rows:
        return await call.answer("No panel names found in this category.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for row in rows:
        old_name = str(row[0] or '').strip()
        # Use an index token to avoid Telegram callback length/underscore parsing problems.
        token = hashlib.sha1((category + "|" + old_name).encode()).hexdigest()[:12]
        set_setting("panel_rename_target_" + token, json.dumps({"category": category, "panel_name": old_name}, ensure_ascii=False))
        kb.inline_keyboard.append([InlineKeyboardButton(text=old_name[:60], callback_data=f"rename_pick_{token}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Back", callback_data="admin_panel_name_change", style="danger")])
    await call.message.edit_text(f"✏️ <b>{html_lib.escape(category)} — SELECT PANEL</b>\n\nSame-name package rows are grouped here. Select the panel name you want to rename.", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("rename_pick_"))
async def admin_rename_pick(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Not authorized.", show_alert=True)
    token = call.data.rsplit("_", 1)[-1]
    raw = get_setting("panel_rename_target_" + token, "")
    try:
        target = json.loads(raw)
    except Exception:
        target = None
    if not target:
        return await call.answer("Panel selection expired. Open Panel Name Change again.", show_alert=True)
    await state.update_data(rename_old_panel=target["panel_name"], rename_category=target["category"])
    await state.set_state(AdminStates.wait_for_panel_rename)
    await call.message.edit_text(f"✏️ <b>Rename Panel</b>\n\nCategory: <b>{html_lib.escape(target['category'])}</b>\nCurrent name: <code>{html_lib.escape(target['panel_name'])}</code>\n\nSend the new panel name. All product entries with this exact panel name (case-insensitive) will be updated together.", reply_markup=admin_back_kb(), parse_mode="HTML")

@dp.message(AdminStates.wait_for_panel_rename)
async def admin_save_panel_rename(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    new_name = (message.text or "").strip()
    if not new_name:
        return await message.answer("Please send a valid, non-empty panel name.")
    if len(new_name) > 100:
        return await message.answer("Panel name is too long. Please keep it under 100 characters.")
    data = await state.get_data()
    old_name = str(data.get("rename_old_panel", "")).strip()
    category = str(data.get("rename_category", "")).strip()
    if not old_name or not category:
        await state.clear()
        return await message.answer("Rename session expired. Please open Panel Name Change again.", reply_markup=admin_kb())
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE products SET panel_name=? WHERE UPPER(TRIM(COALESCE(category,'')))=UPPER(TRIM(?)) AND LOWER(TRIM(COALESCE(panel_name,'')))=LOWER(TRIM(?))", (new_name, category, old_name))
        changed = cur.rowcount
        # Keep demo lookup names in sync so Watch Demo continues to work after rename.
        old_key, new_key = old_name.casefold(), new_name.casefold()
        cur.execute("SELECT display_name, file_id FROM product_demos WHERE product_name_key=?", (old_key,))
        demo = cur.fetchone()
        if demo:
            cur.execute("DELETE FROM product_demos WHERE product_name_key=?", (old_key,))
            cur.execute("INSERT OR REPLACE INTO product_demos (product_name_key, display_name, file_id, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)", (new_key, new_name, demo[1]))
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Panel rename failed")
        return await message.answer("❌ Rename failed. Database was not changed.", reply_markup=admin_kb())
    finally:
        conn.close()
    # Move panel emoji setting to the new key if one exists.
    old_emoji = get_setting(f"panel_emoji_{old_name}", "")
    if old_emoji:
        set_setting(f"panel_emoji_{new_name}", old_emoji)
        set_setting(f"panel_emoji_{old_name}", "")
    await state.clear()
    await message.answer(f"✅ <b>Panel name changed successfully!</b>\n\nOld name: <code>{html_lib.escape(old_name)}</code>\nNew name: <code>{html_lib.escape(new_name)}</code>\nUpdated product rows: <b>{changed}</b>\n\nThe same panel name was updated across categories/packages, and the demo name was synced when present.", reply_markup=admin_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_manage_prods")
async def admin_manage_prods(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    # Show every available category, including categories with no products yet.
    categories = get_categories()
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for category in categories:
        token = hashlib.sha1(category.encode("utf-8")).hexdigest()[:12]
        set_setting("manage_category_target_" + token, category)
        count = db_query(
            "SELECT COUNT(*) FROM products WHERE UPPER(TRIM(COALESCE(category,'')))=UPPER(TRIM(?))",
            (category,), fetchone=True
        )
        total = int(count[0] or 0) if count else 0
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"📂 {category[:45]} ({total})",
            callback_data=f"manage_cat_{token}", style="primary"
        )])
    kb.inline_keyboard.append([InlineKeyboardButton(
        text="📋 All Products", callback_data="admin_manage_all_prods", style="success"
    )])
    kb.inline_keyboard.append([InlineKeyboardButton(
        text="Back to Admin", callback_data="admin_panel_back",
        icon_custom_emoji_id=get_emoji_icon("back"), style="danger"
    )])
    await call.message.edit_text(
        "📦 <b>Manage Products — Select Category</b>\n\n"
        "Admin-created categories are listed here too. Select a category to manage its products.",
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("manage_cat_"))
async def admin_manage_products_by_category(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    token = call.data[len("manage_cat_"):]
    category = get_setting("manage_category_target_" + token, "").strip()
    if not category or category.casefold() not in {x.casefold() for x in get_categories()}:
        return await call.answer("Category selection expired. Reopen Manage Products.", show_alert=True)
    prods = db_query(
        "SELECT id, name, category, panel_name, stock, is_active FROM products "
        "WHERE UPPER(TRIM(COALESCE(category,'')))=UPPER(TRIM(?)) ORDER BY panel_name, name",
        (category,), fetchall=True
    ) or []
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for prod in prods:
        status_dot = "🟢" if prod[5] else "🔴"
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{status_dot} {str(prod[3] or '')[:25]} - {str(prod[1] or '')[:25]} (Stock: {prod[4]})",
            callback_data=f"admin_view_p_{prod[0]}", style="primary"
        )])
    kb.inline_keyboard.append([InlineKeyboardButton(
        text="⬅️ Back to Categories", callback_data="admin_manage_prods", style="danger"
    )])
    await call.message.edit_text(
        f"📦 <b>Manage Products</b>\nCategory: <b>{html_lib.escape(category)}</b>\n\n" +
        ("Select a product to edit:" if prods else "No products in this category yet."),
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data == "admin_manage_all_prods")
async def admin_manage_all_products(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    prods = db_query("SELECT id, name, category, panel_name, stock, is_active FROM products ORDER BY category, panel_name, name", fetchall=True) or []
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for prod in prods:
        status_dot = "🟢" if prod[5] else "🔴"
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{status_dot} [{str(prod[2] or '')[:20]}] {str(prod[3] or '')[:20]} - {str(prod[1] or '')[:20]} (Stock: {prod[4]})",
            callback_data=f"admin_view_p_{prod[0]}", style="primary"
        )])
    kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Back to Categories", callback_data="admin_manage_prods", style="danger")])
    await call.message.edit_text(
        "📦 <b>All Products — Select a product to edit</b>" if prods else "📦 No products found.",
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("admin_view_p_"))
async def admin_view_product(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    try:
        p_id = int(call.data.split("_")[3])
        prod = db_query("SELECT * FROM products WHERE id=?", (p_id,), fetchone=True)
        if not prod: return await call.answer("❌ Architecture fault: Node lost!", show_alert=True)
        panel_name = prod[2] if prod[2] is not None else ""
        price_inr = safe_float(prod[4])
        reseller_price = safe_float(prod[5])
        text = (f"📦 <b><u>NODE DEEP DIVE DETAILS</u></b>\n━━━━━━━━━━━━━━━━━━\n<b>ID:</b> <code>{prod[0]}</code>\n<b>Panel Group:</b> {prod[1]}\n<b>Panel Name:</b> {panel_name}\n<b>Package Date/Time:</b> {prod[3]}\n<b>Standard Price:</b> {fmt_curr(price_inr)}\n👑 <b>Wholesale Price:</b> {fmt_curr(reseller_price)}\n<b>Vault Stock:</b> {prod[6]}\n<b>Payload Link:</b> {prod[7] if prod[7] else 'None'}\n<b>Time Config:</b> {prod[8]}\n<b>HWID Limit:</b> {prod[9]}\n<b>Visibility:</b> {'Active' if prod[10] else 'Hidden'}\n<b>API PID:</b> {html_lib.escape(str(prod[12] or 'Not set'))}\n<b>API Days/Duration:</b> {html_lib.escape(str(prod[13] or 'Not set'))}\n━━━━━━━━━━━━━━━━━━")
        toggle_btn_text = "Hide Product 👁‍🗨" if prod[10] else "Unhide Product 👁"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Edit Panel Group 🏷️", callback_data=f"edit_p_{p_id}_cat", style="primary"), InlineKeyboardButton(text="Edit Panel Name 🏷️", callback_data=f"edit_p_{p_id}_panel_name", style="primary")],
            [InlineKeyboardButton(text="Edit Package Name ✏️", callback_data=f"edit_p_{p_id}_name", style="primary")],
            [InlineKeyboardButton(text="Edit Price 💰", callback_data=f"edit_p_{p_id}_price", style="primary"), InlineKeyboardButton(text="Edit R-Price 👑", callback_data=f"edit_p_{p_id}_rprice", style="primary")],
            [InlineKeyboardButton(text="Edit Validity ⏳", callback_data=f"edit_p_{p_id}_validity", style="primary"), InlineKeyboardButton(text="Edit Device 📱", callback_data=f"edit_p_{p_id}_device", style="primary")],
            [InlineKeyboardButton(text="Edit APK Link 🔗", callback_data=f"edit_p_{p_id}_apk", style="primary")],
            [InlineKeyboardButton(text="Edit API PID 🔌", callback_data=f"edit_p_{p_id}_api_pid", style="primary"), InlineKeyboardButton(text="Edit API Days ⏳", callback_data=f"edit_p_{p_id}_api_duration", style="primary")],
            [InlineKeyboardButton(text="Delete Key 🗑", callback_data=f"delkey_p_{p_id}", style="danger"), InlineKeyboardButton(text=toggle_btn_text, callback_data=f"toggle_p_{p_id}", style="primary")],
            [InlineKeyboardButton(text="Nuke Full Node 🗑", callback_data=f"delete_p_{p_id}", style="danger"), InlineKeyboardButton(text="BACK", callback_data="admin_manage_prods", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
        ])
        await call.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error in admin_view_product: {e}")
        await call.message.edit_text(f"❌ Error loading product: {str(e)}", reply_markup=admin_back_kb(), parse_mode='HTML')

@dp.callback_query(F.data.startswith("toggle_p_"))
async def admin_toggle_product(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    p_id = int(call.data.split("_")[2])
    current = db_query("SELECT is_active FROM products WHERE id=?", (p_id,), fetchone=True)[0]
    new_val = 0 if current == 1 else 1
    db_query("UPDATE products SET is_active=? WHERE id=?", (new_val, p_id))
    await call.answer("Visibility updated successfully!", show_alert=True)
    await admin_view_product(call)

# ==============================================================================
# FIX: Edit product field – correctly handle different data types and multi-word fields
# ==============================================================================
@dp.callback_query(F.data.startswith("edit_p_"))
async def start_edit_product(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    # Use split with maxsplit=3 to keep field name intact (may contain underscores)
    parts = call.data.split("_", 3)
    if len(parts) < 4:
        return await call.answer("Invalid callback data.", show_alert=True)
    p_id = int(parts[2])
    field = parts[3]
    await state.update_data(edit_p_id=p_id, edit_field=field)
    if field == 'keys':
        await call.message.edit_text("📥 <b>Vault Injection</b>\nPaste the <b>NEW KEYS</b> to append to the stock (1 key per line):", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_add_keys)
    else:
        field_name_map = {'cat': 'New Panel Group/Category Name', 'panel_name': 'New Panel Name', 'name': 'New Package/Date Name', 'price': 'New Standard Price in ₹', 'rprice': 'New Reseller Price in ₹', 'validity': 'New Time Validity String', 'device': 'New HWID Limit String', 'apk': 'New Payload Link (or type "none")', 'api_pid': 'New API Target / PID (type none to unlink)', 'api_duration': 'New API Days / Duration (type none to clear)'}
        await call.message.edit_text(f"✏️ Input the required data for: <b>{field_name_map.get(field, field)}</b>", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_new_value)

@dp.message(AdminStates.wait_for_new_value)
async def process_edit_value(m: Message, state: FSMContext):
    data = await state.get_data()
    p_id = data['edit_p_id']; field = data['edit_field']; new_val = m.text.strip()
    
    # Convert price fields to float, others remain strings
    if field in ['price', 'rprice']:
        try:
            new_val = float(new_val)
        except ValueError:
            return await m.answer("❌ Invalid number format. Please enter a valid price (e.g., 500).")
    elif field in ['apk', 'api_pid', 'api_duration']:
        new_val = "" if new_val.lower() in ('none', 'no', 'skip') else new_val
    # For panel_name, cat, name, validity, device – keep as string
    
    db_col_map = {'cat': 'category', 'panel_name': 'panel_name', 'name': 'name', 'price': 'price_inr', 'rprice': 'reseller_price', 'validity': 'validity', 'device': 'device_limit', 'apk': 'apk_link', 'api_pid': 'api_product_id', 'api_duration': 'api_duration'}
    db_query(f"UPDATE products SET {db_col_map[field]}=? WHERE id=?", (new_val, p_id))
    await m.answer("✅ <b>Node updated gracefully!</b>", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.message(AdminStates.wait_for_add_keys)
async def process_add_keys(m: Message, state: FSMContext):
    data = await state.get_data()
    p_id = data['edit_p_id']
    keys = [k.strip() for k in m.text.strip().split('\n') if k.strip()]
    if len(keys) == 0: return await m.answer("❌ Protocol breach: Zero valid keys found.", reply_markup=admin_kb(), parse_mode='HTML')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for k in keys: c.execute("INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)", (p_id, k))
    c.execute("UPDATE products SET stock = stock + ? WHERE id=?", (len(keys), p_id))
    conn.commit(); conn.close()
    await m.answer(f"✅ <b>Vault Secure!</b> {len(keys)} new keys appended and encrypted.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data.startswith("delete_p_"))
async def admin_delete_product(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    p_id = int(call.data.split("_")[2])
    db_query("DELETE FROM products WHERE id=?", (p_id,))
    db_query("DELETE FROM product_keys WHERE product_id=?", (p_id,))
    await call.answer("☢️ Nuclear wipe successful! Node and vault deleted.", show_alert=True)
    await admin_manage_prods(call)

@dp.callback_query(F.data.startswith("delkey_p_"))
async def admin_delete_key_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    p_id = int(call.data.split("_")[2])
    await state.update_data(del_p_id=p_id)
    await call.message.edit_text("🗑 Send the <b>exact string match</b> of the key you wish to purge from the vault:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_delete_key)

@dp.message(AdminStates.wait_for_delete_key)
async def process_delete_key(m: Message, state: FSMContext):
    data = await state.get_data()
    p_id = data['del_p_id']
    key_to_delete = m.text.strip()
    key_data = db_query("SELECT id, is_used FROM product_keys WHERE product_id=? AND key_text=?", (p_id, key_to_delete), fetchone=True)
    if not key_data: return await m.answer("❌ Key not found. Check logs and try again.", reply_markup=admin_back_kb(), parse_mode='HTML')
    if key_data[1] == 1: return await m.answer("⚠️ Action Blocked: This key has already been dispatched to a user.", reply_markup=admin_back_kb(), parse_mode='HTML')
    db_query("DELETE FROM product_keys WHERE id=?", (key_data[0],))
    db_query("UPDATE products SET stock = stock - 1 WHERE id=?", (p_id,))
    await m.answer(f"✅ Key <code>{key_to_delete}</code> securely purged from vault.\n📦 Database indices updated.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

# ==============================================================================
# 21. ADMIN TICKETS, BROADCAST, COUPONS
# ==============================================================================
@dp.callback_query(F.data == "admin_view_tickets")
async def admin_view_tickets(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    tickets = db_query("SELECT id, user_id, message, created_at FROM tickets WHERE status='Open' LIMIT 1", fetchall=True)
    if not tickets: return await call.answer("✅ Zero pending issues. Grid is clean!", show_alert=True)
    t = tickets[0]
    text = (f"🎫 <b><u>ACTIVE TICKET #{t[0]}</u></b>\n👤 <b>Origin UID:</b> <code>{t[1]}</code>\n📅 <b>Timestamp:</b> {t[3]}\n\n📝 <b>Payload:</b>\n{t[2]}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Formulate Reply", callback_data=f"reply_ticket_{t[0]}_{t[1]}", style="primary")],
        [InlineKeyboardButton(text="❌ Force Close Ticket", callback_data=f"close_ticket_{t[0]}", style="danger")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("close_ticket_"))
async def close_ticket(call: CallbackQuery):
    ticket_id = call.data.split("_")[2]
    db_query("UPDATE tickets SET status='Closed' WHERE id=?", (ticket_id,))
    await call.answer("✅ Status set to Closed.", show_alert=True)
    await admin_view_tickets(call) 

@dp.callback_query(F.data.startswith("reply_ticket_"))
async def reply_ticket_start(call: CallbackQuery, state: FSMContext):
    data = call.data.split("_")
    ticket_id, user_id = data[2], data[3]
    await state.update_data(ticket_id=ticket_id, user_id=user_id)
    await call.message.edit_text(f"💬 Formulating reply for node <code>{user_id}</code>.\n\nType your message payload:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.ticket_reply_msg)

@dp.message(AdminStates.ticket_reply_msg)
async def send_ticket_reply(m: Message, state: FSMContext):
    data = await state.get_data()
    try:
        await bot.send_message(data['user_id'], f"📞 <b>Admin Reply (Ref #{data['ticket_id']}):</b>\n\n{m.text}", parse_mode='HTML')
        db_query("UPDATE tickets SET status='Closed' WHERE id=?", (data['ticket_id'],))
        await m.answer("✅ Payload delivered and connection closed successfully.", reply_markup=admin_kb(), parse_mode='HTML')
    except Exception as e: await m.answer(f"❌ Transmission Error: {e}", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_broadcast_btn")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("📢 <b>Mass Broadcast Protocol</b>\n\nSend the rich message payload you wish to transmit globally across the grid:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.broadcast_msg)

@dp.message(AdminStates.broadcast_msg)
async def admin_broadcast_send(message: Message, state: FSMContext):
    users = db_query("SELECT user_id FROM users", fetchall=True)
    sent, failed = 0, 0
    m = await message.answer("⏳ Broadcast protocol initiated... Do not interrupt.", parse_mode='HTML')
    for u in users:
        try:
            await message.send_copy(chat_id=u[0])
            sent += 1
        except Exception: failed += 1
        await asyncio.sleep(0.06) 
    await m.edit_text(f"✅ <b>Global Broadcast Complete!</b>\n\n🟢 Nodes reached: {sent}\n🔴 Nodes failed/blocked: {failed}", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_create_coupon")
async def admin_create_coupon_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("🎟 Enter a highly secure alphanumeric sequence for the Promo Code:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_coupon_code)

@dp.message(AdminStates.add_coupon_code)
async def admin_coupon_code(m: Message, state: FSMContext):
    await state.update_data(code=m.text.strip().upper())
    await m.answer("💰 Enter the monetary reward payload in <b>RUPEES (₹)</b>:", parse_mode='HTML')
    await state.set_state(AdminStates.add_coupon_amount)

@dp.message(AdminStates.add_coupon_amount)
async def admin_coupon_amount(m: Message, state: FSMContext):
    try:
        await state.update_data(amount=float(m.text)) 
        await m.answer("👥 Enter the exact maximum threshold uses for this code:", parse_mode='HTML')
        await state.set_state(AdminStates.add_coupon_uses)
    except ValueError: await m.answer("❌ Non-numerical data detected. Aborting.")

@dp.message(AdminStates.add_coupon_uses)
async def admin_coupon_uses(m: Message, state: FSMContext):
    try:
        uses = int(m.text)
        data = await state.get_data()
        db_query("INSERT OR REPLACE INTO coupons (code, amount, uses_left) VALUES (?, ?, ?)", (data['code'], data['amount'], uses))
        await m.answer(f"✅ Protocol <b>{data['code']}</b> encoded!\nReward Vector: {fmt_curr(data['amount'])}\nThreshold Limit: {uses} executions.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Non-numerical data detected. Aborting.")

# ==============================================================================
# 22. ADMIN RESELLER & SPIN SETTINGS
# ==============================================================================
@dp.callback_query(F.data == "admin_reseller_menu")
async def admin_reseller_menu(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    status_check = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    sys_status = status_check[0] if status_check else "ON"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Grant Reseller Rights", callback_data="reseller_make", style="success"), InlineKeyboardButton(text="➖ Revoke Reseller", callback_data="reseller_remove", style="danger")],
        [InlineKeyboardButton(text="📋 Audit Active Resellers", callback_data="reseller_view", style="primary")],
        [InlineKeyboardButton(text=f"{'🟢' if sys_status == 'ON' else '🔴'} Auto-Upgrade System: {sys_status}", callback_data="admin_toggle_reseller_sys", style="success" if sys_status == 'ON' else "danger")], 
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text("👑 <b>Wholesale Reseller Protocols</b>\nSelect administrative action:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "admin_toggle_reseller_sys")
async def toggle_reseller_sys(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    res = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    current = res[0] if res else 'ON'
    new_status = 'OFF' if current == 'ON' else 'ON'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('reseller_system_status', ?)", (new_status,))
    await admin_reseller_menu(call)

@dp.callback_query(F.data.in_(["reseller_make", "reseller_remove"]))
async def reseller_prompt_id(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    action = call.data
    await state.update_data(reseller_action=action)
    await call.message.edit_text("👤 Identify target node. Input <b>User ID</b> or <b>@username</b>:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.reseller_manage_id)

@dp.message(AdminStates.reseller_manage_id)
async def process_reseller_manage(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    target = m.text.strip()
    if target.startswith('@'): target = target[1:]
    user_q = db_query("SELECT user_id, first_name FROM users WHERE user_id=? OR username=? COLLATE NOCASE", (target, target), fetchone=True)
    if not user_q: return await m.answer("❌ Target completely ghosted. Not in database.", reply_markup=admin_back_kb(), parse_mode='HTML')
    u_id, u_name = user_q[0], user_q[1]
    safe_name = html_lib.escape(str(u_name or "Unknown"))
    if data['reseller_action'] == "reseller_make":
        db_query("UPDATE users SET is_reseller=1, reseller_since=?, account_type='Reseller' WHERE user_id=?", (datetime.now().strftime("%Y-%m-%d"), u_id))
        await m.answer(f"✅ <b>Reseller Added</b>\n👤 {safe_name} (<code>{u_id}</code>) now has reseller rights.", reply_markup=admin_kb(), parse_mode='HTML')
        try:
            await bot.send_message(u_id, "🎉 <b>Congratulations! You have been upgraded to Reseller.</b>\n\n👑 Reseller features and reseller pricing are now available in the bot.", parse_mode="HTML")
        except Exception as exc:
            logger.warning("Could not notify newly added reseller %s: %s", u_id, exc)
    else:
        db_query("UPDATE users SET is_reseller=0, reseller_since=NULL, account_type='Regular' WHERE user_id=?", (u_id,))
        await m.answer(f"✅ <b>Reseller Removed</b>\n👤 {safe_name} (<code>{u_id}</code>) is back to regular user.", reply_markup=admin_kb(), parse_mode='HTML')
        try:
            await bot.send_message(u_id, "ℹ️ <b>Your Reseller status has been removed by the admin.</b>\n\nYour account is now a regular user. Regular-user pricing will apply.", parse_mode="HTML")
        except Exception as exc:
            logger.warning("Could not notify removed reseller %s: %s", u_id, exc)
    await state.clear()

@dp.callback_query(F.data == "reseller_view")
async def reseller_view(call: CallbackQuery):
    resellers = db_query("SELECT user_id, first_name, username FROM users WHERE is_reseller=1", fetchall=True)
    if not resellers: return await call.message.edit_text("📋 Zero active resellers found.", reply_markup=admin_back_kb(), parse_mode='HTML')
    text = "👑 <b><u>ACTIVE RESELLER AUDIT LOG</u></b> 👑\n━━━━━━━━━━━━━━━━━━\n"
    for r in resellers:
        uname = f"(@{r[2]})" if r[2] else ""
        text += f"👤 {r[1]} {uname}\n🆔 <code>{r[0]}</code>\n\n"
    await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_spin_menu")
async def admin_spin_menu(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    status = db_query("SELECT value FROM settings WHERE key='spin_status'", fetchone=True)
    limit = db_query("SELECT value FROM settings WHERE key='daily_spin_limit'", fetchone=True)
    status_val = status[0] if status else 'ON'
    limit_val = limit[0] if limit else '50.0'
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Append Reward Logic", callback_data="spin_add", style="success"), InlineKeyboardButton(text="❌ Drop Reward Logic", callback_data="spin_del", style="danger")],
        [InlineKeyboardButton(text="📋 Audit Configs", callback_data="spin_view", style="primary"), InlineKeyboardButton(text="⚙️ Throttle Limits", callback_data="spin_limit", style="primary")],
        [InlineKeyboardButton(text=f"{'🟢' if status_val == 'ON' else '🔴'} Master Toggle: {status_val}", callback_data="spin_toggle", style="success" if status_val == 'ON' else "danger")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text(f"🎰 <b>Advanced Ludo/Spin Algorithms</b>\nCurrent Threshold: ₹{limit_val}", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "spin_toggle")
async def spin_toggle(call: CallbackQuery):
    res = db_query("SELECT value FROM settings WHERE key='spin_status'", fetchone=True)
    current = res[0] if res else 'ON'
    new_status = 'OFF' if current == 'ON' else 'ON'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('spin_status', ?)", (new_status,))
    await admin_spin_menu(call)

@dp.callback_query(F.data == "admin_toggle_new_user_notification")
async def admin_toggle_new_user_notification(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    current = new_user_start_message_enabled()
    set_setting("new_user_start_message", "OFF" if current else "ON")
    await call.answer("New User Notification " + ("OFF" if current else "ON"))
    try:
        await call.message.edit_reply_markup(reply_markup=admin_kb())
    except Exception:
        await call.message.edit_text("⚙️ <b>Admin Control</b>", reply_markup=admin_kb(), parse_mode='HTML')


@dp.callback_query(F.data == "admin_toggle_bot")
async def toggle_bot(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    res = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
    current = res[0] if res else 'ON'
    new_status = 'OFF' if current == 'ON' else 'ON'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('bot_status', ?)", (new_status,))
    await call.message.edit_reply_markup(reply_markup=admin_kb())

@dp.callback_query(F.data == "spin_add")
async def spin_add_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("🎰 Inject new decimal logic limit (e.g. 15.50):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.spin_add_reward)

@dp.message(AdminStates.spin_add_reward)
async def spin_add_exec(m: Message, state: FSMContext):
    try:
        amt = float(m.text)
        db_query("INSERT INTO spin_rewards (amount) VALUES (?)", (amt,))
        await m.answer(f"✅ Algorithm updated. New vector {fmt_curr(amt)} injected.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Math parsing error.")

@dp.callback_query(F.data == "spin_view")
async def spin_view(call: CallbackQuery):
    rewards = db_query("SELECT amount FROM spin_rewards ORDER BY amount ASC", fetchall=True)
    text = "🎰 <b>Live Ludo Constants</b>\n\n"
    for r in rewards: text += f"🎁 {fmt_curr(r[0])}\n"
    await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "menu_all_files")
async def menu_all_files(call: CallbackQuery):
    """Show an intermediate Download Files page; do not open the admin URL directly from the main menu."""
    link = (get_setting("all_files_link", "None") or "None").strip()
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if link.lower() != "none" and (link.startswith("http://") or link.startswith("https://")):
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="📥 Open Download Files",
                icon_custom_emoji_id=get_emoji_icon("download"),
                url=link,
                style="success"
            )
        ])
    else:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="⚠️ Files Not Configured",
                callback_data="download_files_not_configured",
                style="danger"
            )
        ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")
    ])
    text = (
        "📥 <b>DOWNLOAD FILES</b>\n\n"
        "Access the available files from the button below.\n"
        "Your files link is managed by the admin. 📦"
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data == "download_files_not_configured")
async def download_files_not_configured(call: CallbackQuery):
    await call.answer("⚠️ Download Files link is not configured yet.", show_alert=True)


def _top_sellers_rows(limit: int = 5):
    """Return buyers ranked by number of recorded successful key purchases."""
    return db_query(
        "SELECT u.user_id, u.first_name, u.username, u.is_reseller, "
        "COUNT(o.id) AS keys_bought, COALESCE(SUM(o.price_paid), 0) AS total_buy "
        "FROM orders o JOIN users u ON u.user_id=o.user_id "
        "GROUP BY u.user_id, u.first_name, u.username, u.is_reseller "
        "ORDER BY keys_bought DESC, total_buy DESC, u.first_name COLLATE NOCASE ASC "
        "LIMIT ?", (limit,), fetchall=True
    ) or []


@dp.callback_query(F.data == "menu_top_sellers")
async def menu_top_sellers(call: CallbackQuery):
    rows = _top_sellers_rows(5)
    # Use Telegram custom-emoji tags throughout the leaderboard for a premium look.
    trophy = get_emoji("sagartop")
    divider = "━━━━━━━━━━━━━━━━━━"
    lines = [f"{trophy} <b>𝐓𝐎𝐏 𝟓 𝐒𝐄𝐋𝐋𝐄𝐑𝐒 𝐓𝐎𝐏</b> {trophy}", divider]
    if not rows:
        lines.append(f"{get_emoji('info_icon')} <b>No successful purchases have been recorded yet.</b>")
    else:
        for i, row in enumerate(rows, 1):
            user_id, first_name, username, is_reseller, keys_bought, total_buy = row
            name = html_lib.escape(str(first_name or username or "User Name"))
            level = f"{get_emoji('reseller')} <b>𝐑𝐞𝐬𝐞𝐥𝐥𝐞𝐫</b>" if bool(is_reseller) else f"{get_emoji('regular_user')} <b>𝐑𝐞𝐠𝐮𝐥𝐚𝐫 𝐔𝐬𝐞𝐫</b>"
            lines.append(
                f"{get_emoji('name')} <b>{i}. {name}</b>\n"
                f"{get_emoji('account_level')} <b>𝐀𝐜𝐜𝐨𝐮𝐧𝐭 𝐋𝐞𝐯𝐞𝐥:</b> {level}\n"
                f"{get_emoji('total_orders')} <b>𝐊𝐞𝐲𝐬:</b> <b>{keys_bought}</b>\n"
                f"{get_emoji('total_spent')} <b>𝐓𝐨𝐭𝐚𝐥 𝐁𝐮𝐲:</b> <b>{fmt_curr(total_buy)}</b>"
            )
            if i != len(rows):
                lines.append(divider)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="𝐁𝐀𝐂𝐊", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")
    ]])
    await call.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data == "admin_top_sellers")
async def admin_top_sellers(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    rows = _top_sellers_rows(5)
    lines = ["🏆 <b>ADMIN — TOP 5 SELLERS</b> 🏆", "━━━━━━━━━━━━━━━━━━"]
    if not rows:
        lines.append("📊 No successful purchases have been recorded yet.")
    else:
        for i, row in enumerate(rows, 1):
            user_id, first_name, username, is_reseller, keys_bought, total_buy = row
            name = html_lib.escape(str(first_name or username or "User Name"))
            dm = f"@{html_lib.escape(str(username))}" if username else "Not set"
            level = "👑 Reseller" if bool(is_reseller) else "✨ Regular User"
            lines.append(
                f"<b>{i}. {name}</b>\n"
                f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
                f"💬 <b>DM ID / Username:</b> {dm}\n"
                f"👤 <b>Account Level:</b> {level}\n"
                f"🔑 <b>Keys:</b> {keys_bought}\n"
                f"💰 <b>Total Buy:</b> {fmt_curr(total_buy)}"
            )
            if i != len(rows):
                lines.append("━━━━━━━━━━━━━━━━━━")
    await call.message.edit_text("\n".join(lines), reply_markup=admin_back_kb(), parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data == "menu_selling_proof")
async def menu_selling_proof(call: CallbackQuery):
    """Show an intermediate Selling Proof page; the admin-controlled URL opens only from the inner button."""
    link = (get_setting("selling_proof_link", "None") or "None").strip()
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if link.lower() != "none" and (link.startswith("http://") or link.startswith("https://")):
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="🧾 Verify / View Selling Proof",
                icon_custom_emoji_id=get_emoji_icon("sagarproof"),
                url=link,
                style="success"
            )
        ])
    else:
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text="⚠️ Proof Not Configured",
                callback_data="selling_proof_not_configured",
                style="danger"
            )
        ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")
    ])
    text = (
        "🧾 <b>SELLING PROOF</b>\n\n"
        "Check the available selling proof using the button below.\n"
        "The proof link is controlled by the admin. ✅"
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@dp.callback_query(F.data == "selling_proof_not_configured")
async def selling_proof_not_configured(call: CallbackQuery):
    await call.answer("⚠️ Selling Proof link is not configured yet.", show_alert=True)


@dp.callback_query(F.data == "admin_set_product_demo")
async def admin_set_product_demo_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)

    # Reset any old demo-selection state so the menu can always be reopened.
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in get_categories():
        # TRIM + case-insensitive comparison handles legacy category values too.
        count = db_query(
            "SELECT COUNT(*) FROM products WHERE UPPER(TRIM(COALESCE(category,'')))=?",
            (cat.upper(),), fetchone=True
        )
        if count and count[0]:
            kb.inline_keyboard.append([InlineKeyboardButton(
                text=cat, callback_data="admin_demo_cat_" + cat,
                icon_custom_emoji_id=get_category_emoji(cat), style="success"
            )])

    auto_delete = get_setting("demo_auto_delete", "ON").strip().upper() == "ON"
    delay_seconds = max(1, int(safe_float(get_setting("demo_delete_after_seconds", "60"), 60)))
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text=f"Auto-Delete: {'ON 🟢' if auto_delete else 'OFF 🔴'}",
            callback_data="demo_toggle_auto_delete",
            style="success" if auto_delete else "danger"
        ),
        InlineKeyboardButton(
            text=f"Delete After: {format_demo_delay(delay_seconds)}",
            callback_data="demo_set_delete_time", style="success"
        )
    ])
    kb.inline_keyboard.append([InlineKeyboardButton(
        text="⬅️ Back to Admin", callback_data="admin_panel_back", style="danger"
    )])
    text = "🎬 <b>SET PRODUCT DEMO</b>\n\nChoose a product category:"
    if not any(row[0].callback_data.startswith("admin_demo_cat_") for row in kb.inline_keyboard):
        text += "\n\n⚠️ No products found in the four supported categories. Add a product first."
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception as exc:
        # If Telegram says the message is unchanged, still acknowledge the tap.
        logger.debug("Set Product Demo menu edit: %s", exc)
    await call.answer()

@dp.callback_query(F.data.startswith("admin_demo_cat_"))
async def admin_set_product_demo_category(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    category = call.data.split("admin_demo_cat_", 1)[1].strip()
    rows = db_query("""SELECT COALESCE(NULLIF(TRIM(panel_name),''), NULLIF(TRIM(name),'')) AS demo_name
                       FROM products
                       WHERE UPPER(TRIM(COALESCE(category,'')))=?
                         AND COALESCE(NULLIF(TRIM(panel_name),''), NULLIF(TRIM(name),'')) IS NOT NULL
                       GROUP BY LOWER(TRIM(COALESCE(NULLIF(panel_name,''), NULLIF(name,''))))
                       ORDER BY MIN(COALESCE(NULLIF(TRIM(panel_name),''), NULLIF(TRIM(name),''))) COLLATE NOCASE""",
                     (category.upper(),), fetchall=True) or []
    if not rows:
        await call.answer("No products found in this category. Add a product first.", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    demo_name_map = {}
    for row in rows:
        name = str(row[0] or "").strip()
        if not name:
            continue
        key = name.casefold()
        token = str(len(demo_name_map) + 1)
        demo_name_map[token] = name
        existing = db_query("SELECT file_id FROM product_demos WHERE product_name_key=?", (key,), fetchone=True)
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"{'✅' if existing and existing[0] else '🎬'} {name}"[:64],
            callback_data="setdemo_" + token, style="success"
        )])
    await state.clear()
    await state.update_data(demo_name_map=demo_name_map, demo_category=category)
    kb.inline_keyboard.append([InlineKeyboardButton(
        text="⬅️ Back to Categories", callback_data="admin_set_product_demo", style="danger"
    )])
    try:
        await call.message.edit_text(
            f"🎬 <b>SET PRODUCT DEMO</b>\n\n{html_lib.escape(category)}\nChoose a panel/product:",
            reply_markup=kb, parse_mode="HTML"
        )
    except Exception as exc:
        logger.debug("Set Product Demo category edit: %s", exc)
    await call.answer()

@dp.callback_query(F.data.startswith("setdemo_"))
async def admin_choose_demo_product(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    data = await state.get_data()
    name = (data.get("demo_name_map") or {}).get(call.data.split("setdemo_", 1)[1])
    if not name:
        return await call.answer("Selection expired. Open Set Product Demo and choose the category again.", show_alert=True)
    await state.update_data(demo_selected_name=name)
    await state.set_state(AdminStates.wait_for_product_demo_video)
    await call.message.answer(
        f"🎬 Send the demo video for <b>{html_lib.escape(name)}</b>.\n"
        "Send a video, or type <code>none</code> to remove its demo.",
        parse_mode="HTML", reply_markup=admin_back_kb()
    )
    await call.answer()

@dp.message(AdminStates.wait_for_product_demo_video)
async def admin_save_product_demo(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    data = await state.get_data()
    name = str(data.get("demo_selected_name") or "").strip()
    if not name:
        await state.clear()
        return await m.answer("Selection expired. Open Admin → Set Product Demo again.", reply_markup=admin_kb())

    key = name.casefold()
    if (m.text or "").strip().casefold() == "none":
        db_query("DELETE FROM product_demos WHERE product_name_key=?", (key,))
        await state.clear()
        return await m.answer(
            f"✅ Demo removed for <b>{html_lib.escape(name)}</b>.",
            parse_mode="HTML", reply_markup=admin_kb()
        )
    if not m.video:
        return await m.answer(
            "⚠️ Please send the demo as a Telegram video, or type <code>none</code> to remove it.",
            parse_mode="HTML", reply_markup=admin_back_kb()
        )

    # Save directly and verify the row, instead of silently claiming success if SQLite fails.
    conn = sqlite3.connect(DB_PATH, timeout=30)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO product_demos (product_name_key, display_name, file_id, updated_at) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (key, name, m.video.file_id)
        )
        conn.commit()
        saved = conn.execute(
            "SELECT file_id FROM product_demos WHERE product_name_key=?", (key,)
        ).fetchone()
        if not saved or saved[0] != m.video.file_id:
            raise sqlite3.DatabaseError("Demo row verification failed")
    except Exception:
        conn.rollback()
        logger.exception("Could not save product demo for %s", name)
        return await m.answer(
            "❌ Demo could not be saved to the database. Check bot logs/database permissions and try again.",
            reply_markup=admin_back_kb()
        )
    finally:
        conn.close()

    await state.clear()
    delay = max(1, int(safe_float(get_setting("demo_delete_after_seconds", "60"), 60)))
    await m.answer(
        f"✅ Demo saved successfully for <b>{html_lib.escape(name)}</b>.\n"
        f"Auto-delete: <b>{html_lib.escape(get_setting('demo_auto_delete', 'ON'))}</b>; "
        f"delay: <b>{html_lib.escape(format_demo_delay(delay))}</b>.",
        parse_mode="HTML", reply_markup=admin_kb()
    )



# Product demo controls: callback handlers must exist for every button in the menu.
def format_demo_delay(seconds: int) -> str:
    seconds = max(1, int(seconds))
    if seconds % 3600 == 0:
        return f"{seconds // 3600} hour(s)"
    if seconds % 60 == 0:
        return f"{seconds // 60} minute(s)"
    return f"{seconds} second(s)"


@dp.callback_query(F.data == "demo_toggle_auto_delete")
async def demo_toggle_auto_delete(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    current = get_setting("demo_auto_delete", "ON").strip().upper()
    set_setting("demo_auto_delete", "OFF" if current == "ON" else "ON")
    # Rebuild the menu so the displayed status updates immediately.
    try:
        await call.message.edit_text(
            "🎬 <b>SET PRODUCT DEMO</b>\n\nAuto-delete setting updated. Reopen this menu to see the current status.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="admin_panel_back", style="danger")
            ]]),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await call.answer(f"Auto-delete {'enabled' if get_setting('demo_auto_delete', 'ON') == 'ON' else 'disabled'}.")


@dp.callback_query(F.data == "demo_set_delete_time")
async def demo_set_delete_time(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    await state.set_state(AdminStates.wait_for_demo_delete_time)
    await call.message.answer(
        "⏱ Send the demo auto-delete time, e.g. <code>5 minutes</code>, "
        "<code>2 hours</code>, or <code>90 seconds</code>.",
        parse_mode="HTML", reply_markup=admin_back_kb()
    )
    await call.answer()


@dp.message(AdminStates.wait_for_demo_delete_time)
async def save_demo_delete_time(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    raw = (m.text or "").strip().lower()
    match = re.fullmatch(r"(\\d+)\\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)?", raw)
    if not match:
        return await m.answer("❌ Invalid time. Send e.g. <code>5 minutes</code> or <code>2 hours</code>.", parse_mode="HTML", reply_markup=admin_back_kb())
    amount = int(match.group(1))
    unit = match.group(2) or "seconds"
    if amount < 1:
        return await m.answer("❌ Time must be at least 1 second.", reply_markup=admin_back_kb())
    multiplier = 3600 if unit.startswith(("h", "hr", "hour")) else 60 if unit.startswith(("m", "min", "minute")) else 1
    seconds = min(amount * multiplier, 30 * 24 * 3600)
    set_setting("demo_delete_after_seconds", str(seconds))
    await state.clear()
    await m.answer(f"✅ Demo auto-delete delay saved: <b>{html_lib.escape(format_demo_delay(seconds))}</b>.", parse_mode="HTML", reply_markup=admin_kb())


@dp.callback_query(F.data.startswith("watch_demo_"))
async def watch_product_demo(call: CallbackQuery):
    try:
        prod_id = int(call.data.rsplit("_", 1)[1])
    except (ValueError, IndexError):
        return await call.answer("Invalid product.", show_alert=True)
    product = db_query(
        "SELECT COALESCE(NULLIF(TRIM(panel_name),''), NULLIF(TRIM(name),'')) FROM products WHERE id=?",
        (prod_id,), fetchone=True
    )
    if not product or not product[0]:
        return await call.answer("Product not found.", show_alert=True)
    name = str(product[0]).strip()
    demo = db_query("SELECT file_id FROM product_demos WHERE product_name_key=?", (name.casefold(),), fetchone=True)
    if not demo or not demo[0]:
        return await call.answer("Demo video is not configured for this product.", show_alert=True)
    try:
        sent = await bot.send_video(
            chat_id=call.from_user.id,
            video=demo[0],
            caption=f"🎬 <b>{html_lib.escape(name)} — Demo</b>",
            parse_mode="HTML"
        )
        if get_setting("demo_auto_delete", "ON").strip().upper() == "ON":
            delay = max(1, int(safe_float(get_setting("demo_delete_after_seconds", "60"), 60)))
            async def delete_demo_later(chat_id: int, message_id: int, wait_seconds: int):
                await asyncio.sleep(wait_seconds)
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception:
                    logger.warning("Could not auto-delete demo message %s for chat %s", message_id, chat_id)
            asyncio.create_task(delete_demo_later(call.from_user.id, sent.message_id, delay))
        await call.answer("Demo sent to your private chat.")
    except Exception:
        logger.exception("Could not send product demo %s to user %s", name, call.from_user.id)
        await call.answer("Unable to send demo right now. Please start the bot privately and try again.", show_alert=True)


@dp.callback_query(F.data == "admin_set_video")
async def admin_set_video_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("📹 Input direct streaming / YouTube Link for Tutorial system:\n<i>(Or type 'None' to clear registry):</i>", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_howto_video)

@dp.message(AdminStates.wait_for_howto_video)
async def exec_set_video(m: Message, state: FSMContext):
    link = m.text.strip()
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('how_to_video', ?)", (link,))
    await m.answer("✅ Routing complete. Video linked.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_all_files")
async def admin_set_all_files_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("🔗 Input the direct Channel / Cloud URL for 'Download Files' button:\n<i>(Or type 'None' to format data):</i>", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_all_files_link)

@dp.message(AdminStates.wait_for_all_files_link)
async def exec_set_all_files(m: Message, state: FSMContext):
    link = m.text.strip()
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('all_files_link', ?)", (link,))
    await m.answer("✅ Global resource variable updated.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_selling_proof")
async def admin_set_selling_proof_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    current = get_setting("selling_proof_link", "None")
    await call.message.edit_text(
        "🧾 <b>SELLING PROOF LINK</b>\n\n"
        f"Current Link: <code>{current}</code>\n\n"
        "Send the new Selling Proof URL below.\n"
        "Type <code>None</code> to disable/remove it.",
        reply_markup=admin_back_kb(),
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.wait_for_selling_proof_link)


@dp.message(AdminStates.wait_for_selling_proof_link)
async def exec_set_selling_proof(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    link = (m.text or "").strip()

    if link.lower() == "none":
        link = "None"
    elif not (link.startswith("http://") or link.startswith("https://")):
        await m.answer(
            "❌ Invalid URL!\nPlease send a valid link starting with http:// or https://",
            reply_markup=admin_back_kb(),
            parse_mode='HTML'
        )
        return

    set_setting("selling_proof_link", link)
    await state.clear()
    await m.answer(
        "✅ <b>Selling Proof link updated successfully!</b>\n\n"
        f"🔗 Link: <code>{link}</code>",
        reply_markup=admin_kb(),
        parse_mode='HTML'
    )


@dp.callback_query(F.data == "admin_edit_emojis")
async def admin_edit_emojis(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    rows = db_query("SELECT key, value FROM settings WHERE key LIKE 'emoji_%' ORDER BY key", fetchall=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for row in rows:
        key = row[0]
        slot = key.replace("emoji_", "")
        current_id = row[1] if row[1] else "Not set"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{slot} (ID: {current_id})", callback_data=f"edit_emoji_{slot}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("🎨 <b>Edit All Emojis</b>\nChoose an emoji slot to change its ID:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("edit_emoji_"))
async def admin_edit_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    slot = call.data.split("edit_emoji_", 1)[1]
    await state.update_data(emoji_slot=slot)
    current = get_setting(f"emoji_{slot}", "Not set")
    await call.message.edit_text(f"✏️ Enter new emoji ID for <b>{slot}</b>:\nCurrent: {current}\n(Leave empty to reset to default)", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_emoji_slot)

@dp.message(AdminStates.wait_for_emoji_slot)
async def save_emoji_slot(m: Message, state: FSMContext):
    data = await state.get_data()
    slot = data['emoji_slot']
    new_id = m.text.strip()
    if new_id == "":
        db_query("DELETE FROM settings WHERE key=?", (f"emoji_{slot}",))
        await m.answer(f"✅ Reset emoji for '{slot}' to default.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        if not new_id.isdigit():
            await m.answer("❌ Invalid ID! Must be numeric.", reply_markup=admin_kb(), parse_mode='HTML')
            return
        set_setting(f"emoji_{slot}", new_id)
        await m.answer(f"✅ Emoji for '{slot}' updated to ID {new_id}.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_edit_ui_menu")
async def admin_edit_ui_menu(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Edit Start Menu Text", callback_data="edit_ui_start", style="primary")],
        [InlineKeyboardButton(text="Edit Download Files Text", callback_data="edit_ui_download", style="primary")],
        [InlineKeyboardButton(text="Edit VIP Menu Text", callback_data="edit_ui_vip", style="primary")],
        [InlineKeyboardButton(text="Edit Lucky Dice Text", callback_data="edit_ui_dice", style="primary")],
        [InlineKeyboardButton(text="Edit Add Balance Text", callback_data="edit_ui_add_balance", style="primary")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text("✏️ <b>Edit User Interface Texts</b>\nSelect which text you want to modify:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("edit_ui_"))
async def admin_edit_ui_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    ui_key = call.data.split("_")[2]
    await state.update_data(ui_key=ui_key)
    current_text = get_ui_text(ui_key)
    await call.message.edit_text(f"📝 Send the new text for <b>{ui_key.upper()}</b> menu.\n\nCurrent text:\n{current_text}", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.edit_ui_text)

@dp.message(AdminStates.edit_ui_text)
async def admin_save_ui_text(m: Message, state: FSMContext):
    data = await state.get_data()
    ui_key = data['ui_key']
    new_text = m.text
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f"ui_{ui_key}", new_text))
    await m.answer(f"✅ UI text <b>{ui_key}</b> updated successfully!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_edit_reseller_price")
async def admin_edit_reseller_price_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    await state.clear()
    categories = get_categories()
    if not categories:
        return await call.message.edit_text(
            "No product categories found.", reply_markup=admin_back_kb(), parse_mode="HTML"
        )
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for category in categories:
        # Store full category names separately to keep callback_data under Telegram's limit.
        token = hashlib.sha1(category.encode("utf-8")).hexdigest()[:12]
        set_setting(f"reseller_price_category_{token}", category)
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=f"📂 {category[:55]}",
            callback_data=f"reseller_price_cat_{token}",
            style="primary"
        )])
    kb.inline_keyboard.append([InlineKeyboardButton(
        text="⬅️ Back to Admin", callback_data="admin_panel_back",
        icon_custom_emoji_id=get_emoji_icon("back"), style="danger"
    )])
    await call.message.edit_text(
        "👑 <b>EDIT RESELLER PRICE</b>\n\n"
        "Choose a category. Built-in categories and all categories created by admin are listed here.",
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("reseller_price_cat_"))
async def admin_edit_reseller_price_category(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    token = call.data[len("reseller_price_cat_"):]
    category = get_setting(f"reseller_price_category_{token}", "").strip()
    if not category or category.casefold() not in {x.casefold() for x in get_categories()}:
        return await call.answer("Category not found. Reopen Edit Reseller Price.", show_alert=True)

    prods = db_query(
        """SELECT id, name, category, panel_name, reseller_price
           FROM products WHERE UPPER(TRIM(category))=UPPER(TRIM(?))
           ORDER BY panel_name COLLATE NOCASE, name COLLATE NOCASE""",
        (category,), fetchall=True
    ) or []
    if not prods:
        return await call.answer(
            f"No products in {category} yet. Add a product in this category first.",
            show_alert=True
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in prods:
        panel_name = str(p[3] or "").strip()
        product_name = str(p[1] or "").strip()
        r_price = safe_float(p[4])
        label = f"{panel_name + ' - ' if panel_name else ''}{product_name} (₹{r_price:.2f})"
        kb.inline_keyboard.append([InlineKeyboardButton(
            text=label[:60], callback_data=f"edit_reseller_{p[0]}", style="primary"
        )])
    kb.inline_keyboard.append([InlineKeyboardButton(
        text="⬅️ Back to Categories", callback_data="admin_edit_reseller_price", style="danger"
    )])
    await call.message.edit_text(
        f"👑 <b>EDIT RESELLER PRICE</b>\n\n"
        f"Category: <b>{html_lib.escape(category)}</b>\n"
        "Select a product to change its reseller price:",
        reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()


@dp.callback_query(F.data.startswith("edit_reseller_"))
async def admin_edit_reseller_price_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    try:
        prod_id = int(call.data[len("edit_reseller_"):])
    except ValueError:
        return await call.answer("Invalid product.", show_alert=True)
    product = db_query("SELECT id FROM products WHERE id=?", (prod_id,), fetchone=True)
    if not product:
        return await call.answer("Product not found.", show_alert=True)
    await state.update_data(edit_reseller_prod_id=prod_id)
    await call.message.edit_text(
        "💰 Enter the new <b>Reseller Price</b> in Rupees (₹) for this product:",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.edit_reseller_price)
    await call.answer()


@dp.message(AdminStates.edit_reseller_price)
async def admin_save_reseller_price(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    try:
        raw_price = (m.text or "").strip()
        new_price = float(raw_price)
        if new_price < 0:
            raise ValueError
        data = await state.get_data()
        prod_id = int(data["edit_reseller_prod_id"])
        db_query("UPDATE products SET reseller_price=? WHERE id=?", (new_price, prod_id))
        await m.answer(
            f"✅ Reseller price updated to {fmt_curr(new_price)} for product ID {prod_id}.",
            reply_markup=admin_kb(), parse_mode="HTML"
        )
        await state.clear()
    except (ValueError, KeyError, TypeError):
        await m.answer("❌ Invalid price. Please enter a valid amount (0 or greater).")


@dp.callback_query(F.data == "admin_set_reseller_fee")
async def admin_set_reseller_fee(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("💰 Enter the new <b>Reseller Setup Fee</b> in Rupees (₹):\nCurrent: " + get_setting("reseller_setup_fee", "200.0"), reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_reseller_setup_fee)

@dp.message(AdminStates.wait_for_reseller_setup_fee)
async def admin_save_reseller_fee(m: Message, state: FSMContext):
    try:
        fee = float(m.text)
        set_setting("reseller_setup_fee", str(fee))
        await m.answer(f"✅ Reseller setup fee updated to {fmt_curr(fee)}.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Invalid number. Please enter a valid amount.")

@dp.callback_query(F.data == "admin_set_reseller_api_url")
async def admin_set_reseller_api_url(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    current = get_reseller_api_url()
    await call.message.edit_text(
        "🌐 <b>RESELLER API URL CONTROL</b>\n\n"
        f"Current URL: <code>{html_lib.escape(current)}</code>\n\n"
        "Send the new reseller API URL.\n"
        "Example: <code>https://bantibhaiya.to/api/reseller_v1.php</code>\n\n"
        "Type <code>/cancel</code> to cancel.",
        reply_markup=admin_back_kb(), parse_mode='HTML'
    )
    await state.set_state(AdminStates.wait_for_reseller_api_url)

@dp.message(AdminStates.wait_for_reseller_api_url)
async def admin_save_reseller_api_url(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    url = (m.text or "").strip()
    if url.lower() == "/cancel":
        await state.clear()
        return await m.answer("❌ Reseller API URL setup cancelled.", reply_markup=admin_kb(), parse_mode='HTML')
    if not (url.startswith("http://") or url.startswith("https://")):
        return await m.answer("❌ Invalid URL. Please send a URL starting with http:// or https://", reply_markup=admin_back_kb(), parse_mode='HTML')
    set_setting("reseller_api_url", url)
    await state.clear()
    await m.answer(
        "✅ <b>Reseller API URL Saved!</b>\n\n"
        f"🌐 Endpoint: <code>{html_lib.escape(url)}</code>",
        reply_markup=admin_kb(), parse_mode='HTML'
    )


@dp.callback_query(F.data == "admin_set_reseller_api_key")
async def admin_set_reseller_api_key(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    current = get_setting("reseller_api_key", "")
    masked = (current[:4] + "..." + current[-4:]) if len(current) > 10 else ("Not set" if not current else "••••••")
    await call.message.edit_text(
        "🔑 <b>RESELLER API KEY</b>\n\n"
        f"Current Key: <code>{html_lib.escape(masked)}</code>\n\n"
        "Send your new Reseller API Key below.\n"
        "The key will be saved securely in the bot database.\n"
        "Type <code>/cancel</code> to cancel.",
        reply_markup=admin_back_kb(),
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.wait_for_reseller_api_key)


@dp.message(AdminStates.wait_for_reseller_api_key)
async def admin_save_reseller_api_key(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    key = (m.text or "").strip()
    if key.lower() == "/cancel":
        await state.clear()
        return await m.answer("❌ Reseller API key setup cancelled.", reply_markup=admin_kb(), parse_mode='HTML')
    if not key or key == "YOUR_RRSELLER_API_ADD":
        return await m.answer("❌ Invalid API key. Please send the actual Reseller API key.", reply_markup=admin_back_kb(), parse_mode='HTML')
    set_setting("reseller_api_key", key)
    await state.clear()
    try:
        await m.delete()
    except Exception:
        pass
    masked = (key[:4] + "..." + key[-4:]) if len(key) > 10 else "••••••"
    await m.answer(
        "✅ <b>Reseller API Key Saved!</b>\n\n"
        f"🔑 Key: <code>{html_lib.escape(masked)}</code>\n"
        f"🌐 Endpoint: <code>{html_lib.escape(get_reseller_api_url())}</code>\n\n"
        "You no longer need to edit the .py file to change the API key.",
        reply_markup=admin_kb(),
        parse_mode='HTML'
    )


@dp.callback_query(F.data == "admin_set_reseller_min")
async def admin_set_reseller_min(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("💳 Enter the new <b>Minimum Balance</b> required to become reseller (₹):\nCurrent: " + get_setting("reseller_min_balance", "500.0"), reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_reseller_min_balance)

@dp.message(AdminStates.wait_for_reseller_min_balance)
async def admin_save_reseller_min(m: Message, state: FSMContext):
    try:
        min_bal = float(m.text)
        set_setting("reseller_min_balance", str(min_bal))
        await m.answer(f"✅ Minimum reseller balance updated to {fmt_curr(min_bal)}.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Invalid number. Please enter a valid amount.")

@dp.callback_query(F.data == "admin_set_support_links")
async def admin_set_support_links(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Set Telegram Link", callback_data="admin_set_telegram", style="primary")],
        [InlineKeyboardButton(text="📱 Set WhatsApp Link", callback_data="admin_set_whatsapp", style="primary")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text("📌 <b>Support Contact Links</b>\nSet the URLs for Telegram and WhatsApp support:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "admin_set_telegram")
async def admin_set_telegram(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("✈️ Enter the Telegram contact URL (e.g., https://t.me/YourSupport):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_support_telegram)

@dp.message(AdminStates.wait_for_support_telegram)
async def save_telegram_link(m: Message, state: FSMContext):
    link = m.text.strip()
    set_setting("support_telegram", link)
    await m.answer("✅ Telegram support link updated!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_whatsapp")
async def admin_set_whatsapp(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("📱 Enter the WhatsApp contact URL (e.g., https://wa.me/1234567890):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_support_whatsapp)

@dp.message(AdminStates.wait_for_support_whatsapp)
async def save_whatsapp_link(m: Message, state: FSMContext):
    link = m.text.strip()
    set_setting("support_whatsapp", link)
    await m.answer("✅ WhatsApp support link updated!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_category_emojis")
async def admin_set_category_emojis(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in get_categories():
        current = get_setting(f"cat_emoji_{cat.strip().upper()}", "Not set")
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{cat} (ID: {current})", callback_data=f"set_cat_emoji_{cat}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("🎨 <b>Set Category Emojis</b>\nChoose a category to set its custom emoji ID:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("set_cat_emoji_"))
async def admin_set_category_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    category = call.data.split("set_cat_emoji_", 1)[1]
    await state.update_data(cat_emoji_category=category)
    await call.message.edit_text(f"🎨 Enter the emoji ID for <b>{category}</b>:\n(Leave empty to reset to default)", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_category_emoji)

@dp.message(AdminStates.wait_for_category_emoji)
async def save_category_emoji(m: Message, state: FSMContext):
    data = await state.get_data()
    category = data['cat_emoji_category']
    emoji_id = m.text.strip()
    if emoji_id == "":
        db_query("DELETE FROM settings WHERE key=?", (f"cat_emoji_{category.strip().upper()}",))
        await m.answer(f"✅ Reset emoji for {category} to default.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        if not emoji_id.isdigit():
            await m.answer("❌ Invalid ID! Must be numeric.", reply_markup=admin_kb(), parse_mode='HTML')
            return
        set_setting(f"cat_emoji_{category.strip().upper()}", emoji_id)
        await m.answer(f"✅ Emoji set for {category} successfully!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_panel_emojis")
async def admin_set_panel_emojis(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in get_categories():
        row = db_query("SELECT COUNT(*) FROM products WHERE UPPER(TRIM(category))=? AND TRIM(COALESCE(panel_name,''))!=''", (cat,), fetchone=True)
        if row and row[0]:
            kb.inline_keyboard.append([InlineKeyboardButton(text=cat, callback_data="set_panel_cat_" + cat,
                icon_custom_emoji_id=get_category_emoji(cat), style="success")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Back to Admin", callback_data="admin_panel_back", style="danger")])
    await call.message.edit_text("🖼 <b>SET PANEL EMOJIS</b>\n\nChoose a category:", reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("set_panel_cat_"))
async def admin_set_panel_emojis_category(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    category = call.data.split("set_panel_cat_", 1)[1]
    panels = db_query("""SELECT MIN(id), MIN(TRIM(panel_name)) FROM products
                         WHERE UPPER(TRIM(category))=? AND TRIM(COALESCE(panel_name,''))!=''
                         GROUP BY LOWER(TRIM(panel_name)) ORDER BY MIN(TRIM(panel_name)) COLLATE NOCASE""",
                      (category,), fetchall=True) or []
    if not panels:
        return await call.answer("No panels found in this category.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for pid, panel in panels:
        panel = str(panel or "").strip()
        current = get_setting(f"panel_emoji_{panel}", "Not set")
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{panel[:45]} (ID: {current})",
            callback_data=f"set_panel_emoji_id_{pid}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Back to Categories", callback_data="admin_set_panel_emojis", style="danger")])
    await call.message.edit_text(f"🖼 <b>SET PANEL EMOJIS</b>\n\n{html_lib.escape(category)}\nChoose a panel:", reply_markup=kb, parse_mode="HTML")
    await call.answer()

@dp.callback_query(F.data.startswith("set_panel_emoji_id_"))
async def admin_set_panel_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    try:
        product_id = int(call.data.rsplit("_", 1)[1])
    except ValueError:
        return await call.answer("Invalid panel.", show_alert=True)
    row = db_query("SELECT panel_name FROM products WHERE id=?", (product_id,), fetchone=True)
    if not row or not str(row[0] or "").strip():
        return await call.answer("Panel not found.", show_alert=True)
    panel_name = str(row[0]).strip()
    await state.update_data(panel_emoji_name=panel_name)
    await call.message.edit_text(f"🎨 Enter the emoji ID for panel <b>{html_lib.escape(panel_name)}</b>:\n(Leave empty to reset to default)",
        reply_markup=admin_back_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.wait_for_panel_emoji_id)
    await call.answer()

@dp.message(AdminStates.wait_for_panel_emoji_id)
async def save_panel_emoji(m: Message, state: FSMContext):
    data = await state.get_data()
    panel_name = data['panel_emoji_name']
    emoji_id = m.text.strip()
    if emoji_id == "":
        db_query("DELETE FROM settings WHERE key=?", (f"panel_emoji_{panel_name}",))
        await m.answer(f"✅ Reset emoji for panel '{panel_name}'.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        if not emoji_id.isdigit():
            await m.answer("❌ Invalid ID! Must be numeric.", reply_markup=admin_kb(), parse_mode='HTML')
            return
        set_setting(f"panel_emoji_{panel_name}", emoji_id)
        await m.answer(f"✅ Emoji set for panel '{panel_name}'!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

# ==============================================================================
# Payment gateway ON/OFF controls (admin only)
@dp.callback_query(F.data.in_({"admin_toggle_fampay", "admin_toggle_zapupi", "admin_toggle_BharatPe"}))
async def admin_toggle_payment_gateway(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    gateway = "fampay" if call.data == "admin_toggle_fampay" else ("BharatPe" if call.data == "admin_toggle_BharatPe" else "zapupi")
    key = f"gateway_{gateway}_enabled"
    current = get_setting(key, "ON")
    new_value = "OFF" if current == "ON" else "ON"
    set_setting(key, new_value)
    label = "FamPay" if gateway == "fampay" else ("BharatPe" if gateway == "BharatPe" else "ZapUPI")
    await call.answer(f"{label} {new_value}")
    try:
        await call.message.edit_reply_markup(reply_markup=admin_kb())
    except Exception:
        await call.message.answer(f"{label} gateway is now {new_value}.", reply_markup=admin_kb())

# 23. ADMIN FAMPAY SETUP
# ==============================================================================
@dp.callback_query(F.data == "admin_setup_BharatPe")
async def setup_BharatPe_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    current_api = get_setting("BharatPe_api_key", "")
    masked = (current_api[:7] + "••••••••") if current_api and current_api not in ("YOUR_BharatPe_API_KEY", "PASTE_YOUR_BharatPe_API_KEY_HERE") else "NOT SET"
    await call.message.edit_text(
        "⚙️ <b>ANUJBOTS BharatPe GATEWAY SETUP</b>\n\n"
        f"🔑 Current API Key: <code>{html_lib.escape(masked)}</code>\n\n"
        "Send your AnujBots BharatPe API key (BHP_...).\n"
        "<i>Type /cancel to abort. Do not share this key in public chats.</i>",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.wait_for_BharatPe_api)


@dp.message(AdminStates.wait_for_BharatPe_api)
async def setup_BharatPe_api(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    raw = (m.text or "").strip()
    if raw.lower() == "/cancel":
        await state.clear()
        return await m.answer("Setup cancelled.", reply_markup=admin_kb())
    if not raw.startswith("BHP_") or len(raw) < 8:
        return await m.answer("❌ API key format looks invalid. BharatPe keys for this setup should start with BHP_. Try again or /cancel.")
    set_setting("BharatPe_api_key", raw)
    try:
        await m.delete()
    except Exception:
        pass
    await state.clear()
    await m.answer(
        "✅ <b>AnujBots BharatPe gateway API key saved.</b>\n\n"
        "The gateway returns the QR and UPI ID. After paying, users must submit the 12-digit UTR so the gateway can verify it.\n"
        "ZapUPI settings and payment flow were left unchanged.",
        reply_markup=admin_kb(), parse_mode="HTML"
    )



@dp.callback_query(F.data == "admin_setup_fampay")
async def setup_fampay_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    current_api = get_setting("fampay_api_key", "Not set")
    current_upi = get_setting("fampay_upi_id", "Not set")
    await call.message.edit_text(
        f"⚙️ <b>FAMPAY SECURITY DEPLOYMENT</b>\n\n"
        f"🔑 Current API Key: {current_api[:8] if current_api != 'Not set' else 'Not set'}... (hidden)\n"
        f"🏦 Current UPI ID: {current_upi}\n\n"
        f"Send new <b>FamPay API Key</b>:\n<i>(Type /cancel to abort)</i>",
        reply_markup=admin_back_kb(), parse_mode='HTML'
    )
    await state.set_state(AdminStates.wait_for_fampay_api)

@dp.message(AdminStates.wait_for_fampay_api)
async def setup_fampay_api(m: Message, state: FSMContext):
    if m.text == '/cancel':
        await state.clear()
        return await m.answer("Sequence killed.", reply_markup=admin_kb(), parse_mode='HTML')
    api_key = m.text.strip()
    set_setting("fampay_api_key", api_key)
    await m.answer("🔑 FamPay API Key saved!\n\nNow enter the <b>UPI ID</b> to receive payments (e.g., example@okhdfcbank):", parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_fampay_upi)

@dp.message(AdminStates.wait_for_fampay_upi)
async def setup_fampay_upi(m: Message, state: FSMContext):
    upi_id = m.text.strip()
    if '@' not in upi_id:
        return await m.answer("❌ Invalid UPI ID! Must contain '@'. Example: example@okhdfcbank", parse_mode='HTML')
    set_setting("fampay_upi_id", upi_id)
    await m.answer(f"✅ <b>FamPay Gateway configured successfully!</b>\n\n🏦 UPI ID: {upi_id}\n🔑 API Key: Saved\n\nGateway is now ready for payments.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

# ==============================================================================
# ADMIN ZAPUPI API SETUP
# ==============================================================================
@dp.callback_query(F.data == "admin_setup_zapupi")
async def setup_zapupi_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return await call.answer("Admin only.", show_alert=True)
    current = get_setting("zapupi_zap_key", "").strip()
    masked = (current[:6] + "••••••••") if current else "NOT SET"
    await call.message.edit_text(
        "🔐 <b>ZAPUPI API SETTINGS</b>\n\n"
        f"Current Zap Key: <code>{html_lib.escape(masked)}</code>\n\n"
        "pay.zapupi.com gateway ka <b>Zap Key</b> bhejein.\n"
        "Key database mein save hogi; code edit karne ki zaroorat nahi.\n\n"
        "/cancel — cancel setup",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.wait_for_zapupi_key)
    await call.answer()

@dp.message(AdminStates.wait_for_zapupi_key)
async def setup_zapupi_key(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    raw = (m.text or "").strip()
    if raw.lower() == "/cancel":
        await state.clear()
        return await m.answer("❌ ZapUPI setup cancelled.", reply_markup=admin_kb())
    if len(raw) < 6 or raw.startswith("/"):
        return await m.answer("❌ Valid ZapUPI Zap Key bhejein, ya /cancel type karein.")
    set_setting("zapupi_zap_key", raw)
    await state.clear()
    await m.answer("✅ <b>ZapUPI API Key saved!</b>\n\n🏦 ZapUPI payment option ab Add Balance menu mein available hoga.", reply_markup=admin_kb(), parse_mode="HTML")

# ==============================================================================
# 24. ADMIN BINANCE SETUP
# ==============================================================================
@dp.callback_query(F.data == "admin_setup_binance")
async def setup_binance_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("🪙 <b>CRYPTO NODE INIT: Step 1/3</b>\nInput Master <b>Binance API Key</b>:\n<i>(Type /cancel to halt protocol)</i>", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_binance_api)

@dp.message(AdminStates.wait_for_binance_api)
async def setup_binance_api(m: Message, state: FSMContext):
    if m.text == '/cancel':
        await state.clear()
        return await m.answer("Sequence aborted.", reply_markup=admin_kb(), parse_mode='HTML')
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('binance_api', ?)", (m.text.strip(),))
    await m.answer("🪙 <b>CRYPTO NODE INIT: Step 2/3</b>\nNow inject the highly secure <b>Binance Secret Key</b>:", parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_binance_secret)

@dp.message(AdminStates.wait_for_binance_secret)
async def setup_binance_secret(m: Message, state: FSMContext):
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('binance_secret', ?)", (m.text.strip(),))
    await m.answer("🪙 <b>CRYPTO NODE INIT: Step 3/3</b>\nFinal variable: Set the public <b>USDT Deposit Address (TRC20/BEP20)</b>\nUsers will broadcast to this ledger:", parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_binance_address)

@dp.message(AdminStates.wait_for_binance_address)
async def setup_binance_address(m: Message, state: FSMContext):
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('binance_address', ?)", (m.text.strip(),))
    await m.answer("✅ <b>Blockchain node synchronized.</b> Crypto gateway is fully armed.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()


# ==============================================================================
# RESELLER API ADMIN COMMANDS
# ==============================================================================
@dp.message(Command("linkapi"))
async def cmd_linkapi(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    parts = (m.text or "").split(maxsplit=3)
    if len(parts) < 3:
        return await m.answer(
            "Usage:\n<code>/linkapi BOT_PRODUCT_ID API_PID [DURATION]</code>\n"
            "Example: <code>/linkapi 5 151 1 Day</code>\n"
            "Unlink: <code>/linkapi 5 off</code>", parse_mode="HTML")
    try:
        p_id = int(parts[1])
    except ValueError:
        return await m.answer("❌ BOT_PRODUCT_ID must be a number.")
    if not db_query("SELECT id FROM products WHERE id=?", (p_id,), fetchone=True):
        return await m.answer("❌ Product not found in bot.")
    if parts[2].lower() == "off":
        db_query("UPDATE products SET api_product_id='', api_duration='' WHERE id=?", (p_id,))
        return await m.answer(f"✅ Product #{p_id} unlinked from reseller API. Local keys will be used again.")
    api_pid = parts[2].strip()
    duration = parts[3].strip() if len(parts) > 3 else ""
    db_query("UPDATE products SET api_product_id=?, api_duration=?, stock=999 WHERE id=?", (api_pid, duration, p_id))
    duration_line = f"\nDuration: <code>{html_lib.escape(duration)}</code>" if duration else ""
    await m.answer(
        f"✅ <b>API linked!</b>\nProduct: <code>{p_id}</code>\nAPI PID: <code>{html_lib.escape(api_pid)}</code>"
        f"{duration_line}\n\n"
        "Keys will now be generated automatically on purchase.", parse_mode="HTML")


@dp.message(Command("setresellerapi"))
async def cmd_setresellerapi(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    parts = (m.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        return await m.answer("Usage: <code>/setresellerapi YOUR_API_KEY</code>", parse_mode="HTML")
    key = parts[1].strip()
    set_setting("reseller_api_key", key)
    try:
        await m.delete()
    except Exception:
        pass
    await m.answer("✅ Reseller API key saved securely.\n🌐 Endpoint: <code>https://bantibhaiya.to/api/reseller_v1.php</code>", parse_mode="HTML")


@dp.message(Command("apibalance"))
async def cmd_apibalance(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    ok, data = await reseller_api_request("balance")
    if not ok:
        return await m.answer(f"❌ {html_lib.escape(str(data))}", parse_mode="HTML")
    await m.answer(f"💰 <b>Supplier wallet</b>\n<code>{html_lib.escape(json.dumps(data, indent=2, ensure_ascii=False)[:3500])}</code>", parse_mode="HTML")


@dp.message(Command("apiproducts"))
async def cmd_apiproducts(m: Message):
    if m.from_user.id != ADMIN_ID:
        return
    ok, data = await reseller_api_request("products")
    if not ok:
        return await m.answer(f"❌ {html_lib.escape(str(data))}", parse_mode="HTML")
    raw = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    await m.answer_document(BufferedInputFile(raw, filename="api_products.json"), caption="Reseller API products (PIDs & stock)")

# ==============================================================================
# 25. BOOTSTRAPPING & MAIN
# ==============================================================================
async def main() -> None:
    init_db()
    logger.info("Initializing DB structure...")
    migrate_categories()
    asyncio.create_task(auto_verify_task())
    logger.info("FamPay FAST Auto-Verifier Daemon Running in Background (1s polling).")
    logger.info("🚀 CORE SYSTEM IS FULLY OPERATIONAL...")
    try:
        await dp.start_polling(bot)
    except Exception as err:
        logger.error(f"Critical System Failure in Polling: {err}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("System shutting down gracefully. Goodbye.")

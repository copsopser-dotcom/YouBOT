
#creator ChatGPT & DeepSeek & Cr1ticalOps
import logging
import random
import string
import asyncio
import threading
import time
import re
import math
import aiohttp
from typing import Optional
from collections import defaultdict
from functools import wraps
from telegram.ext import CallbackContext
from datetime import datetime, timedelta
from telegram import ChatMemberUpdated
from telegram.ext import ChatMemberHandler
from telegram import Update, LabeledPrice, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ConversationHandler, ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters, CallbackQueryHandler
from transformers import AutoTokenizer, AutoModelForCausalLM, TextGenerationPipeline
from telegram.error import TelegramError
from telegram.ext import Updater
import requests
from io import BytesIO
import tempfile
import json  
import os  




TOKEN = '7865402898:AAHVH2vKi94CQGhAoKlyChZu6OfJW0tIfVc'       
PROVIDER_TOKEN = '1877036958:TEST:94779bd1d5eb52829c9cf64d3c7e7c23b863519a'  # Вставьте ваш токен от платёжной системы
PAYMENT_CURRENCY = "XTR"  # Валюта Telegram Stars

# База данных пользователей (временное решение)
BALANCE_FILE = "balance.json"







# Загружаем модель Mistral

# Ваш ID для получения уведомлений и отправки сообщений от имени бота
OWNER_ID = 5793502641
OWNERS_ID = "5793502641"  # Ваш ID

# Храним состояние пользователей
active_users = set()

# Глобальные переменные для хранения данных
user_activity_data = {}
user_reputation = {}
user_positive_rep = {}
user_message_count = {}
user_games_played = {}

# Игровая валюта и статусы пользователей
referrals = {}  # Хранение реферальных связей
user_currency = {}  # Словарь для хранения валюты пользователей
user_status = {}    # Словарь для хранения статусов пользователей
last_farm_time = {}  # Словарь для отслеживания времени последнего фарма
# Dictionary to store checks
checks = {}  # check_id -> { "amount": int, "password": str, "creator_id": int }
raffle_data = {}
user_data = {}
BLOCKED = {}  # user_id (строка) : причина
pending_requests = {}  # user_id: (question, message_id)

user_diamond = {}  # Словарь для хранения валюты пользователей

chat_histories = {}

# Глобальные переменные для хранения данных
user_behavior_data = {}
user_messages_log = {}

ADMINS_FILE = "admins.json"

# Загрузка списка админов
if os.path.exists(ADMINS_FILE):
    with open(ADMINS_FILE, "r") as f:
        admins = json.load(f)
else:
    admins = {
        "owner": OWNER_ID,
        "admins": []
    }
        
        

def fix_json_file(filename):
    """Исправляет поврежденный JSON файл"""
    print(f"🔧 Исправляем файл: {filename}")
    
    # Читаем файл как текст
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    print(f"📄 Содержимое файла:\n{content}\n")
    
    # Пробуем разные методы исправления
    fixed = False
    
    # Метод 1: Удаляем последнюю запятую если есть
    if content.endswith(','):
        content = content[:-1]
        fixed = True
        print("✅ Удалили лишнюю запятую в конце")
    
    # Метод 2: Добавляем закрывающие скобки если нужно
    if not content.endswith('}'):
        if content.endswith('"}'):
            pass  # Уже нормально
        elif '"' in content:
            content += '}'
            fixed = True
            print("✅ Добавили закрывающую скобку")
    
    # Метод 3: Проверяем валидность
    try:
        data = json.loads(content)
        print("✅ JSON валиден!")
        return data
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка JSON: {e}")
        
        # Создаем новый файл если старый невозможно исправить
        print("🆕 Создаем новый файл с чистыми данными...")
        new_data = {
            "currency": {},
            "last_farm_time": {}
        }
        
        # Пробуем извлечь данные которые есть
        lines = content.split('\n')
        for line in lines:
            if ':' in line and '"' in line:
                try:
                    key, value = line.split(':', 1)
                    key = key.strip().strip('"')
                    value = value.strip().strip(',')
                    
                    if key.isdigit() and value.isdigit():
                        new_data["currency"][key] = int(value)
                        print(f"📊 Восстановлен пользователь {key}: {value}")
                except:
                    pass
        
        return new_data

# Запускаем исправление
if os.path.exists("user_data.json"):
    fixed_data = fix_json_file("user_data.json")
    
    # Сохраняем исправленный файл
    with open("user_data.json", 'w', encoding='utf-8') as f:
        json.dump(fixed_data, f, ensure_ascii=False, indent=2)
    
    print("✅ Файл исправлен и сохранен!")
else:
    print("📁 Файл не найден, создаем новый...")
    with open("user_data.json", 'w', encoding='utf-8') as f:
        json.dump({"currency": {}, "last_farm_time": {}}, f, indent=2)
    print("✅ Новый файл создан!")
    
    
last_farm_time = {}
DATA_FILE = "user_data.json"

def safe_json_load(filename):
    """Безопасная загрузка JSON с восстановлением при ошибках"""
    if not os.path.exists(filename):
        return {"currency": {}, "last_farm_time": {}}
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("⚠️ Файл поврежден, создаем новый")
        return {"currency": {}, "last_farm_time": {}}
    except Exception as e:
        print(f"⚠️ Ошибка чтения файла: {e}")
        return {"currency": {}, "last_farm_time": {}}

def load_user_data():
    """Загрузка данных пользователей из файла"""
    global user_currency, last_farm_time
    
    data = safe_json_load(DATA_FILE)
    
    # Преобразуем ключи из строк в числа
    user_currency = {}
    for user_id_str, amount in data.get('currency', {}).items():
        try:
            user_currency[int(user_id_str)] = int(amount)
        except (ValueError, TypeError):
            continue
    
    # Преобразуем время
    last_farm_time = {}
    for user_id_str, time_str in data.get('last_farm_time', {}).items():
        try:
            if time_str:
                last_farm_time[int(user_id_str)] = datetime.fromisoformat(time_str)
        except (ValueError, TypeError):
            continue
    
    print(f"✅ Загружено {len(user_currency)} пользователей")

def save_user_data():
    """Сохранение данных пользователей в файл"""
    try:
        # Конвертируем datetime в строки
        last_farm_time_str = {}
        for user_id, time_obj in last_farm_time.items():
            last_farm_time_str[str(user_id)] = time_obj.isoformat() if time_obj else None
        
        data = {
            'currency': {str(k): v for k, v in user_currency.items()},
            'last_farm_time': last_farm_time_str
        }
        
        # Сначала сохраняем во временный файл
        temp_file = DATA_FILE + '.tmp'
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Затем перемещаем на место основного
        os.replace(temp_file, DATA_FILE)
        
        print(f"💾 Сохранено {len(user_currency)} пользователей")
        
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        

# ==================== УМНАЯ КОНФИГУРАЦИЯ ЗАЩИТЫ ====================
SECURITY_CONFIG = {
    "MAX_REQUESTS_PER_MINUTE": 30,           # Нормальный лимит
    "MAX_REQUESTS_PER_10_SECONDS": 5,        # Быстрое определение спама
    "BAN_DURATION": 86400,                   # Бан на 24 часа за DDoS
    "AUTO_BAN_THRESHOLD": 15,                # Быстрый бан при атаке
    "WHITELIST_USERS": [123456789],          # ID доверенных пользователей
    "RESPONSE_TIMEOUT": 10,                  # Таймаут ответа бота (сек)
}

# ==================== УМНАЯ СИСТЕМА ЗАЩИТЫ ====================
class SmartProtectionSystem:
    def __init__(self):
        self.request_times = {}              # Время запросов: {user_id: [timestamps]}
        self.banned_users = {}               # Забаненные: {user_id: ban_end_time}
        self.user_behavior = {}              # Поведение: {user_id: {"last_command": "", "waiting_response": False}}
        self.last_cleanup = time.time()
        
    def is_user_whitelisted(self, user_id):
        """Проверяет whitelist"""
        return user_id in SECURITY_CONFIG["WHITELIST_USERS"]
    
    def is_user_banned(self, user_id):
        """Проверяет бан"""
        if user_id in self.banned_users:
            if time.time() < self.banned_users[user_id]:
                return True
            else:
                del self.banned_users[user_id]
        return False
    
    def analyze_behavior(self, user_id, command):
        """Анализирует поведение пользователя"""
        if user_id not in self.user_behavior:
            self.user_behavior[user_id] = {
                "last_command": "",
                "last_command_time": 0,
                "waiting_response": False,
                "response_times": []
            }
        
        behavior = self.user_behavior[user_id]
        current_time = time.time()
        
        # Если пользователь ждет ответа и снова шлет команду - это подозрительно
        if behavior["waiting_response"] and current_time - behavior["last_command_time"] < 3:
            return False, " "
        
        behavior["last_command"] = command
        behavior["last_command_time"] = current_time
        behavior["waiting_response"] = True
        
        # Устанавливаем таймер для сброса флага ожидания
        asyncio.create_task(self.reset_waiting_flag(user_id))
        
        return True, "OK"
    
    async def reset_waiting_flag(self, user_id):
        """Сбрасывает флаг ожидания через таймаут"""
        await asyncio.sleep(SECURITY_CONFIG["RESPONSE_TIMEOUT"])
        if user_id in self.user_behavior:
            self.user_behavior[user_id]["waiting_response"] = False
    
    def check_for_ddos(self, user_id):
        """Обнаружение DDoS атак"""
        if self.is_user_whitelisted(user_id):
            return True, "OK"
            
        if self.is_user_banned(user_id):
            return False, "🚫 Вы заблокированы за нарушение правил"
        
        current_time = time.time()
        
        # Инициализация лога запросов
        if user_id not in self.request_times:
            self.request_times[user_id] = []
        
        # Добавляем текущий запрос
        self.request_times[user_id].append(current_time)
        
        # Очищаем старые логи
        self.cleanup_old_requests()
        
        # Анализируем запросы за последние 10 секунд (быстрое обнаружение DDoS)
        recent_requests = [t for t in self.request_times[user_id] 
                         if current_time - t < 10]
        
        # Анализируем запросы за последнюю минуту
        minute_requests = [t for t in self.request_times[user_id] 
                          if current_time - t < 60]
        
        # ДЕТЕКТОР DDoS: Очень частые запросы за короткое время
        if len(recent_requests) > SECURITY_CONFIG["MAX_REQUESTS_PER_10_SECONDS"]:
            self.ban_user(user_id, SECURITY_CONFIG["BAN_DURATION"])
            return False, "🚫 Обнаружена DDoS атака! Бан на 24 часа"
        
        # ДЕТЕКТОР Спама: Много запросов за минуту
        if len(minute_requests) > SECURITY_CONFIG["MAX_REQUESTS_PER_MINUTE"]:
            if len(minute_requests) > SECURITY_CONFIG["AUTO_BAN_THRESHOLD"]:
                self.ban_user(user_id, SECURITY_CONFIG["BAN_DURATION"])
                return False, "🚫 Слишком много запросов! Бан на 24 часа"
            return False, "⏳ Слишком много запросов! Подождите 1 минуту"
        
        return True, "OK"
    
    def ban_user(self, user_id, duration):
        """Банит пользователя"""
        self.banned_users[user_id] = time.time() + duration
        print(f"🔒 DDoS защита: Забанен пользователь {user_id} на {duration} сек")
    
    def cleanup_old_requests(self):
        """Очищает старые запросы"""
        current_time = time.time()
        if current_time - self.last_cleanup > 60:
            for user_id in list(self.request_times.keys()):
                # Сохраняем только запросы за последние 5 минут
                self.request_times[user_id] = [t for t in self.request_times[user_id] 
                                             if current_time - t < 300]
                if not self.request_times[user_id]:
                    del self.request_times[user_id]
            
            # Очищаем истекшие баны
            for user_id in list(self.banned_users.keys()):
                if current_time > self.banned_users[user_id]:
                    del self.banned_users[user_id]
            
            self.last_cleanup = current_time

# ==================== БАЗА ДАННЫХ ====================
users_info = {}
DATA_FILE = "bot_users.json"
protection = SmartProtectionSystem()

def init_data():
    """Инициализация данных"""
    global users_info
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                users_info = json.load(f)
            print(f"✅ Загружено пользователей: {len(users_info)}")
        except:
            print("❌ Ошибка загрузки, создаем новую БД")
            users_info = {}
    else:
        users_info = {}
        print("📁 Создана новая база данных")

def save_data():
    """Сохранение данных"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(users_info, f, ensure_ascii=False, indent=2)
        print(f"💾 Сохранено пользователей: {len(users_info)}")
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

# ==================== УМНАЯ ПРОВЕРКА ====================
async def smart_security_check(update: Update, command_name: str):
    """Умная проверка безопасности"""
    user_id = update.effective_user.id
    
    # Регистрируем пользователя
    if str(user_id) not in users_info:
        users_info[str(user_id)] = {
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name,
            "join_date": datetime.now().isoformat(),
            "legitimate_requests": 0
        }
        save_data()
    
    # Анализируем поведение
    behavior_ok, behavior_msg = protection.analyze_behavior(user_id, command_name)
    if not behavior_ok:
        return False, behavior_msg
    
    # Проверяем на DDoS
    ddos_ok, ddos_msg = protection.check_for_ddos(user_id)
    if not ddos_ok:
        return False, ddos_msg
    
    # Увеличиваем счетчик легальных запросов
    users_info[str(user_id)]["legitimate_requests"] += 1
    
    return True, "OK"
    
    
# ==================== СИСТЕМА ВОССТАНОВЛЕНИЯ ====================
async def auto_unblock_users():
    """Автоматическое снятие банов"""
    while True:
        await asyncio.sleep(3600)  # Проверка каждый час
        current_time = time.time()
        unbanned_count = 0
        
        for user_id in list(protection.banned_users.keys()):
            if current_time > protection.banned_users[user_id]:
                del protection.banned_users[user_id]
                unbanned_count += 1
        
        if unbanned_count > 0:
            print(f"🔓 Авторазбан: {unbanned_count} пользователей")

async def monitor_system_health():
    """Мониторинг здоровья системы"""
    while True:
        await asyncio.sleep(300)  # Каждые 5 минут
        print(f"📊 Статистика защиты:")
        print(f"   Забанено: {len(protection.banned_users)}")
        print(f"   Активных: {len(protection.request_times)}")
        print(f"   Всего пользователей: {len(users_info)}")

# ==================== КОМАНДА СТАТУСА ====================
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда статуса системы"""
    user_id = update.effective_user.id
    
    # Только для админов/владельца
    if user_id not in SECURITY_CONFIG["WHITELIST_USERS"]:
        await update.message.reply_text("❌ Недостаточно прав")
        return
    
    status_text = (
        "🛡️ Статус системы защиты:\n\n"
        f"• Забанено пользователей: {len(protection.banned_users)}\n"
        f"• Мониторится пользователей: {len(protection.request_times)}\n"
        f"• Всего в базе: {len(users_info)}\n"
        f"• Время работы: {time.time() - start_time:.0f} сек\n\n"
        "✅ Система работает нормально"
    )
    
    await update.message.reply_text(status_text)
    
    


# Состояния для игры
BET_FOOTBALL, CHOICE_FOOTBALL = range(2)
BET_JACKPOT, CHOICE_JACKPOT = range(2, 4)
BET_DARTS, CHOICE_DARTS = range(4, 6)
BOWLING_BET, BOWLING_GUESS = range(6, 8)
BET, CHOICE = range(8, 10)
BASKETBALL_BET, BASKETBALL_SHOT = range(10, 12)

# Устанавливаем начальное количество 🌕 для владельца
user_currency[OWNER_ID] = 10
user_diamond[OWNER_ID] = 10
# Словарь для хранения данных о пользователях
user_activity = defaultdict(lambda: {'messages': 0, 'commands': 0, 'reported': 0})

BLOCKED_FILE = "blocked.json"

# Загрузка списка заблокированных
if os.path.exists(BLOCKED_FILE):
    with open(BLOCKED_FILE, "r") as f:
        BLOCKED = json.load(f)
else:
    BLOCKED = {}

def save_blocked():
    with open(BLOCKED_FILE, "w") as f:
        json.dump(BLOCKED, f)
        
async def block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Блокировка пользователя"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Используй: /block <user_id> <причина>")
        return

    user_id = context.args[0]
    reason = " ".join(context.args[1:])
    
    # Сохраняем блокировку
    BLOCKED[user_id] = reason
    save_blocked()
    
    # Отправляем уведомление
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🚫 ВЫ ЗАБЛОКИРОВАНЫ\nПричина: {reason}\n\nДля разблокировки пишите @YouBot_unblock"
        )
        await update.message.reply_text(
            f"✅ Пользователь {user_id} заблокирован.\n"
            f"Причина: {reason}\n"
            f"Уведомление отправлено."
        )
    except Exception as e:
        await update.message.reply_text(
            f"✅ Пользователь {user_id} заблокирован.\n"
            f"Причина: {reason}\n"
            f"⚠ Не удалось отправить уведомление: {str(e)}"
        )

async def unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Разблокировка пользователя"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    if not context.args:
        await update.message.reply_text("Используй: /unblock <user_id>")
        return

    user_id = context.args[0]
    
    if user_id not in BLOCKED:
        await update.message.reply_text(f"ℹ Пользователь {user_id} не заблокирован.")
        return
    
    # Удаляем блокировку
    del BLOCKED[user_id]
    save_blocked()
    
    # Отправляем уведомление о разблокировке
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="🎉 ВЫ РАЗБЛОКИРОВАНЫ!\nТеперь вы снова можете пользоваться ботом."
        )
        await update.message.reply_text(
            f"✅ Пользователь {user_id} разблокирован.\n"
            f"Уведомление отправлено."
        )
    except Exception as e:
        await update.message.reply_text(
            f"✅ Пользователь {user_id} разблокирован.\n"
            f"⚠ Не удалось отправить уведомление: {str(e)}"
        )
        
# Проверка, заблокирован ли пользователь
async def check_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in BLOCKED:
        reason = BLOCKED[user_id]
        await update.message.reply_text(f"⛔ВЫ ЗАБЛОКИРОВАНЫ\nПричина: {reason}\nДля разблокировки пишите: @YouBot_unblock")
        return True
    return False
    
    # Пример команды, которая не должна работать у заблокированных пользователей
async def some_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_block(update, context):
        return  # Прерываем выполнение, если пользователь заблокирован
    await update.message.reply_text("Эта команда работает!")
    

async def dummy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass  # Пустой обработчик для поглощения команд
     
    


# Пример использования в одной из команд:
async def farm_currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await rate_limiter(update):
        return  # Прерываем выполнение, если пользователь отправляет запросы слишком часто
    
    user_id = update.message.from_user.id
    
# --- КОМАНДЫ БОТА ---
async def farm_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in user_currency:
        user_currency[user_id] = 0

    now = datetime.now()
    last_farm = last_farm_time.get(user_id)
    
    if last_farm and (now - last_farm).total_seconds() < 3600:
        remaining = 3600 - (now - last_farm).total_seconds()
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        await update.message.reply_text(
            f"⏳ Вы можете фармить только раз в час\n"
            f"Осталось: {hours}ч {minutes}м"
        )
        return

    currency = random.randint(25, 125)
    user_currency[user_id] += currency
    last_farm_time[user_id] = now
    save_user_data()

    await update.message.reply_text(
        f"💰 +{currency} 🌕\n"
        f"💵 Баланс: {user_currency[user_id]} 🌕"
    )
    
# Функция для передачи валюты с лимитом 100,000 монет
async def transfer_currency(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await check_block(update, context):         
        return
         
    if len(context.args) < 2:
        await update.message.reply_text("Используйте команду в формате: /transfer_currency <user_id> <amount>")
        return

    sender_id = update.message.from_user.id
    receiver_id = int(context.args[0])
    amount = int(context.args[1])
    
    # Проверка максимального лимита (10,000 монет)
    if amount > 10000:
        await update.message.reply_text("❌ Максимальная сумма перевода - 10,000 🌕")
        return
    
    # Проверка минимальной суммы
    if amount <= 0:
        await update.message.reply_text("❌ Сумма перевода должна быть положительной")
        return
    
    # Проверка наличия средств у отправителя
    if sender_id not in user_currency or user_currency[sender_id] < amount:
        await update.message.reply_text("❌ Недостаточно средств для перевода")
        return

    # Инициализация баланса получателя если нужно
    if receiver_id not in user_currency:
        user_currency[receiver_id] = 0
        
    # Проверка, не пытается ли пользователь перевести сам себе
    if sender_id == receiver_id:
        await update.message.reply_text("❌ Нельзя переводить средства самому себе")
        return
        
    # Перевод валюты
    user_currency[sender_id] -= amount
    user_currency[receiver_id] += amount
    
    # Сохраняем данные
    save_user_data()
    
    # Получаем информацию о получателе для красивого сообщения
    try:
        receiver_user = await context.bot.get_chat(receiver_id)
        receiver_name = receiver_user.first_name
        if receiver_user.username:
            receiver_info = f"@{receiver_user.username} ({receiver_name})"
        else:
            receiver_info = receiver_name
    except:
        receiver_info = f"ID: {receiver_id}"
    
    # Отправляем подтверждение
    await update.message.reply_text(
        f"✅ <b>Перевод выполнен успешно!</b>\n\n"
        f"• <b>Получатель:</b> {receiver_info}\n"
        f"• <b>Сумма:</b> {amount:,} 🌕\n"
        f"• <b>Ваш новый баланс:</b> {user_currency[sender_id]:,} 🌕\n\n"
        f"💸 <b>Комиссия:</b> 0 🌕 (бесплатно)",
        parse_mode='HTML'
    )
    
    # Уведомляем получателя если возможно
    try:
        await context.bot.send_message(
            chat_id=receiver_id,
            text=f"🎉 <b>Вам перевели {amount:,} 🌕!</b>\n\n"
                 f"• <b>Отправитель:</b> {update.message.from_user.first_name}\n"
                 f"• <b>Ваш новый баланс:</b> {user_currency[receiver_id]:,} 🌕",
            parse_mode='HTML'
        )
    except:
        pass  # Если не удалось уведомить получателя


    # Покупка статуса
    user_currency[user_id] -= price
    user_status[user_id] = status
    await update.message.reply_text(f"Вы успешно купили статус {status}! Ваш новый баланс: {user_currency[user_id]} 🌕")

# Словарь для хранения данных о пользователях
user_data = {}

# Файлы для сохранения данных
LIKES_FILE = "user_likes.json"
FOLLOWERS_FILE = "user_followers.json"

# Загрузка данных
def load_social_data():
    """Загружает данные о лайках и подписчиках"""
    global user_likes, user_dislikes, user_followers, user_following
    
    # Лайки и дизлайки
    if os.path.exists(LIKES_FILE):
        try:
            with open(LIKES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                user_likes = data.get('likes', {})
                user_dislikes = data.get('dislikes', {})
        except:
            user_likes = {}
            user_dislikes = {}
    else:
        user_likes = {}
        user_dislikes = {}
    
    # Подписчики и подписки
    if os.path.exists(FOLLOWERS_FILE):
        try:
            with open(FOLLOWERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                user_followers = data.get('followers', {})
                user_following = data.get('following', {})
        except:
            user_followers = {}
            user_following = {}
    else:
        user_followers = {}
        user_following = {}

# Сохранение данных
def save_social_data():
    """Сохраняет данные о лайках и подписчиках"""
    try:
        # Лайки и дизлайки
        with open(LIKES_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'likes': user_likes,
                'dislikes': user_dislikes
            }, f, ensure_ascii=False, indent=2)
        
        # Подписчики и подписки
        with open(FOLLOWERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'followers': user_followers,
                'following': user_following
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения социальных данных: {e}")

# Инициализация глобальных переменных
user_likes = {}
user_dislikes = {}
user_followers = {}
user_following = {}

# Загружаем данные при старте
load_social_data()

# Команда для лайка пользователя
async def like_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await check_block(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("❌ Используйте: /like <user_id>")
        return
    
    try:
        target_id = int(context.args[0])
        user_id = update.effective_user.id
        
        # Нельзя лайкать себя
        if user_id == target_id:
            await update.message.reply_text("❌ Нельзя ставить лайк самому себе")
            return
        
        # Проверяем, не лайкал ли уже
        if str(target_id) in user_likes.get(str(user_id), []):
            await update.message.reply_text("✅ Вы уже лайкнули этого пользователя")
            return
        
        # Проверяем, не дизлайкал ли - удаляем дизлайк если был
        if str(target_id) in user_dislikes.get(str(user_id), []):
            user_dislikes[str(user_id)].remove(str(target_id))
        
        # Добавляем лайк
        if str(user_id) not in user_likes:
            user_likes[str(user_id)] = []
        user_likes[str(user_id)].append(str(target_id))
        
        # Сохраняем
        save_social_data()
        
        await update.message.reply_text("✅ Вы лайкнули пользователя")
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID пользователя")

# Команда для дизлайка пользователя
async def dislike_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await check_block(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("❌ Используйте: /dislike <user_id>")
        return
    
    try:
        target_id = int(context.args[0])
        user_id = update.effective_user.id
        
        # Нельзя дизлайкать себя
        if user_id == target_id:
            await update.message.reply_text("❌ Нельзя ставить дизлайк самому себе")
            return
        
        # Проверяем, не дизлайкал ли уже
        if str(target_id) in user_dislikes.get(str(user_id), []):
            await update.message.reply_text("✅ Вы уже дизлайкнули этого пользователя")
            return
        
        # Проверяем, не лайкал ли - удаляем лайк если был
        if str(target_id) in user_likes.get(str(user_id), []):
            user_likes[str(user_id)].remove(str(target_id))
        
        # Добавляем дизлайк
        if str(user_id) not in user_dislikes:
            user_dislikes[str(user_id)] = []
        user_dislikes[str(user_id)].append(str(target_id))
        
        # Сохраняем
        save_social_data()
        
        await update.message.reply_text("✅ Вы дизлайкнули пользователя")
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID пользователя")

# Команда для подписки на пользователя
async def follow_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await check_block(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("❌ Используйте: /follow <user_id>")
        return
    
    try:
        target_id = int(context.args[0])
        user_id = update.effective_user.id
        
        # Нельзя подписаться на себя
        if user_id == target_id:
            await update.message.reply_text("❌ Нельзя подписаться на самого себя")
            return
        
        # Проверяем, не подписан ли уже
        if str(target_id) in user_following.get(str(user_id), []):
            await update.message.reply_text("✅ Вы уже подписаны на этого пользователя")
            return
        
        # Добавляем в подписки
        if str(user_id) not in user_following:
            user_following[str(user_id)] = []
        user_following[str(user_id)].append(str(target_id))
        
        # Добавляем в подписчики целевого пользователя
        if str(target_id) not in user_followers:
            user_followers[str(target_id)] = []
        user_followers[str(target_id)].append(str(user_id))
        
        # Сохраняем
        save_social_data()
        
        await update.message.reply_text("✅ Вы подписались на пользователя")
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID пользователя")

# Команда для отписки от пользователя
async def unfollow_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await check_block(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("❌ Используйте: /unfollow <user_id>")
        return
    
    try:
        target_id = int(context.args[0])
        user_id = update.effective_user.id
        
        # Проверяем, подписан ли вообще
        if str(target_id) not in user_following.get(str(user_id), []):
            await update.message.reply_text("❌ Вы не подписаны на этого пользователя")
            return
        
        # Удаляем из подписок
        user_following[str(user_id)].remove(str(target_id))
        
        # Удаляем из подписчиков целевого пользователя
        if str(target_id) in user_followers:
            if str(user_id) in user_followers[str(target_id)]:
                user_followers[str(target_id)].remove(str(user_id))
        
        # Сохраняем
        save_social_data()
        
        await update.message.reply_text("✅ Вы отписались от пользователя")
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID пользователя")

# Добавляем в глобальные переменные
VERIFIED_USERS_FILE = "verified_users.json"
verified_users = {}

# Загрузка верифицированных пользователей
def load_verified_users():
    global verified_users
    if os.path.exists(VERIFIED_USERS_FILE):
        try:
            with open(VERIFIED_USERS_FILE, 'r', encoding='utf-8') as f:
                verified_users = json.load(f)
        except:
            verified_users = {}
    else:
        verified_users = {}

# Сохранение верифицированных пользователей
def save_verified_users():
    try:
        with open(VERIFIED_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(verified_users, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения верифицированных пользователей: {e}")

# Загружаем при старте
load_verified_users()

# Команда для верификации пользователя
async def verify_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    # Проверка, что только владелец может верифицировать
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Эта команда доступна только владельцу бота.")
        return

    if not context.args:
        await update.message.reply_text("❌ Используйте: /verify <user_id>")
        return

    try:
        target_id = int(context.args[0])
        target_id_str = str(target_id)
        
        # Проверяем, не верифицирован ли уже
        if target_id_str in verified_users:
            await update.message.reply_text("✅ Этот пользователь уже верифицирован")
            return
        
        # Верифицируем пользователя
        verified_users[target_id_str] = {
            'verified_by': user_id,
            'verified_at': datetime.now().isoformat(),
            'reason': ' '.join(context.args[1:]) if len(context.args) > 1 else "Ручная верификация"
        }
        
        save_verified_users()
        
        # Получаем информацию о пользователе
        try:
            user = await context.bot.get_chat(target_id)
            username = f"@{user.username}" if user.username else user.first_name
        except:
            username = f"ID: {target_id}"
        
        await update.message.reply_text(
            f"✅ <b>Пользователь верифицирован!</b>\n\n"
            f"• <b>Пользователь:</b> {username}\n"
            f"• <b>ID:</b> <code>{target_id}</code>\n"
            f"• <b>Статус:</b> ⚔️ Верифицирован «Cr1ticalOps»\n"
            f"• <b>Причина:</b> {verified_users[target_id_str]['reason']}",
            parse_mode='HTML'
        )
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID пользователя")

# Команда для снятия верификации
async def unverify_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Эта команда доступна только владельцу бота.")
        return

    if not context.args:
        await update.message.reply_text("❌ Используйте: /unverify <user_id>")
        return

    try:
        target_id = int(context.args[0])
        target_id_str = str(target_id)
        
        if target_id_str not in verified_users:
            await update.message.reply_text("❌ Этот пользователь не верифицирован")
            return
        
        # Удаляем верификацию
        del verified_users[target_id_str]
        save_verified_users()
        
        await update.message.reply_text("✅ Верификация пользователя отменена")
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID пользователя")
        
        
# Добавляем словарь для пользователей с голубой галочкой
premium_verified_users = {}

# Файл для хранения пользователей с голубой галочкой
PREMIUM_VERIFIED_FILE = "premium_verified.json"

# Загрузка пользователей с голубой галочкой
def load_premium_verified():
    global premium_verified_users
    try:
        if os.path.exists(PREMIUM_VERIFIED_FILE):
            with open(PREMIUM_VERIFIED_FILE, 'r', encoding='utf-8') as f:
                premium_verified_users = json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки premium пользователей: {e}")
        premium_verified_users = {}

# Сохранение пользователей с голубой галочкой
def save_premium_verified():
    try:
        with open(PREMIUM_VERIFIED_FILE, 'w', encoding='utf-8') as f:
            json.dump(premium_verified_users, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения premium пользователей: {e}")

# Загружаем данные при старте
load_premium_verified()

# Команда для выдачи голубой галочки (только для админа)
async def premium_verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выдача голубой галочки - только для владельца бота"""
    user_id = update.message.from_user.id
    
    # Проверяем, что команду вызывает владелец бота
    if user_id != OWNER_ID:  # Замени YOUR_USER_ID на свой ID
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /premium_verify <user_id> [причина]")
        return
    
    try:
        target_user_id = int(context.args[0])
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Голубая галочка от владельца"
        
        # Добавляем пользователя с голубой галочкой
        premium_verified_users[str(target_user_id)] = {
            'verified_by': user_id,
            'verified_at': datetime.now().isoformat(),
            'reason': reason
        }
        
        save_premium_verified()
        
        # Получаем информацию о пользователе
        try:
            chat_member = await context.bot.get_chat_member(update.message.chat_id, target_user_id)
            username = chat_member.user.first_name or chat_member.user.username or "Пользователь"
        except:
            username = "Пользователь"
        
        await update.message.reply_text(f"✅ Пользователь {username} (ID: {target_user_id}) получил голубую галочку!")
        
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите корректный ID пользователя.")

# Команда для снятия голубой галочки
async def premium_unverify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Снятие голубой галочки - только для владельца бота"""
    user_id = update.message.from_user.id
    
    if user_id != OWNER_ID:  # Замени YOUR_USER_ID на свой ID
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /premium_unverify <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        target_id_str = str(target_user_id)
        
        if target_id_str in premium_verified_users:
            del premium_verified_users[target_id_str]
            save_premium_verified()
            
            try:
                chat_member = await context.bot.get_chat_member(update.message.chat_id, target_user_id)
                username = chat_member.user.first_name or chat_member.user.username or "Пользователь"
            except:
                username = "Пользователь"
            
            await update.message.reply_text(f"❌ Голубая галочка у пользователя {username} (ID: {target_user_id}) снята!")
        else:
            await update.message.reply_text("❌ У этого пользователя нет голубой галочки.")
            
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите корректный ID пользователя.")

# Функция для загрузки иконки голубой галочки
def get_premium_verification_icon():
    try:
        # URL иконки голубой галочки
        icon_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Twitter_Verified_Badge.svg/2048px-Twitter_Verified_Badge.svg.png"
        
        response = requests.get(icon_url)
        if response.status_code == 200:
            return BytesIO(response.content)
    except Exception as e:
        print(f"Ошибка загрузки иконки голубой галочки: {e}")
    
    return None

# Команда для просмотра списка пользователей с голубой галочкой
async def show_premium_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать список пользователей с голубой галочкой"""
    user_id = update.message.from_user.id
    
    if user_id != OWNER_ID:  # Замени YOUR_USER_ID на свой ID
        await update.message.reply_text("❌ Эта команда доступна только владельцу бота.")
        return
    
    if not premium_verified_users:
        await update.message.reply_text("❌ Нет пользователей с голубой галочкой.")
        return
    
    response = "🔵 <b>Пользователи с голубой галочкой:</b>\n\n"
    
    for user_id_str, data in premium_verified_users.items():
        try:
            user_id_int = int(user_id_str)
            chat_member = await context.bot.get_chat_member(update.message.chat_id, user_id_int)
            username = chat_member.user.first_name or chat_member.user.username or "Неизвестно"
        except:
            username = "Неизвестно"
        
        verified_by = data.get('verified_by', 'system')
        reason = data.get('reason', 'Не указана')
        verified_at = data.get('verified_at', 'Неизвестно')
        
        response += f"👤 {username} (ID: {user_id_str})\n"
        response += f"   📅 Дата: {verified_at}\n"
        response += f"   🎯 Причина: {reason}\n"
        response += f"   👨‍💼 Выдал: {verified_by}\n\n"
    
    await update.message.reply_text(response, parse_mode='HTML')
    
    

    
# Обновленная функция показа статуса с двумя типами верификации
async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды показа статуса"""
    allowed, message = await smart_security_check(update, "show_status")
    if not allowed:
        await update.message.reply_text(message)
        return
    
    if await check_block(update, context):         
        return      
    
    user_id = update.message.from_user.id
    username = update.message.from_user.first_name

    # Если user_id указан в параметре команды, используем его
    if context.args:
        try:
            user_id = int(context.args[0])
            chat_member = await context.bot.get_chat_member(update.message.chat_id, user_id)
            username = chat_member.user.first_name
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите корректный ID пользователя.")
            return
        except TelegramError:
            await update.message.reply_text("Пользователь с таким ID не найден.")
            return

    # Получаем социальную статистику
    target_id_str = str(user_id)
    likes_count = sum(1 for user_likes_list in user_likes.values() if target_id_str in user_likes_list)
    dislikes_count = sum(1 for user_dislikes_list in user_dislikes.values() if target_id_str in user_dislikes_list)
    followers_count = len(user_followers.get(target_id_str, []))
    following_count = len(user_following.get(target_id_str, []))
    
    # Проверяем оба типа верификации
    is_verified = target_id_str in verified_users
    is_premium_verified = target_id_str in premium_verified_users
    
    # Форматируем имя пользователя с голубой галочкой
    username_display = f"👤 {username}"
    if is_premium_verified:
        username_display = f"👤 {username} ✅"  # Галочка прямо возле имени
    
    verification_status = ""
    if is_verified:
        verification_status = "⚔️ <b>Верифицирован «Cr1ticalOps»</b>\n"
    
    # Автоматическая верификация при 1000+ подписчиков
    if followers_count >= 1000 and not is_verified:
        verification_status = "⚔️ <b>Верифицирован «Cr1ticalOps»</b>\n"
        verified_users[target_id_str] = {
            'verified_by': 'system',
            'verified_at': datetime.now().isoformat(),
            'reason': 'Автоматическая верификация (1000+ подписчиков)'
        }
        save_verified_users()
        is_verified = True

    # Проверяем, есть ли данные для данного пользователя
    if user_id in user_data:
        status = user_data[user_id].get("status", "Не установлен")
        house = user_data[user_id].get("house", "Не установлен")
        automobile = user_data[user_id].get("automobile", "Не установлен")
        clothes = user_data[user_id].get("clothes", "Не установлен")
        balance = user_currency.get(user_id, 0)
        balancee = user_diamond.get(user_id, 0)
        
        response = (
            f"{username_display}\n"
            f"{verification_status}\n"
            f"👑 <b>Статус:</b> {status}\n"
            f"🌕 <b>Монеты:</b> {balance:,}\n"
            f"💎 <b>Алмазы:</b> {balancee:,}\n\n"
            
            f"❤️ <b>Лайки:</b> {likes_count}\n"
            f"👎 <b>Дизлайки:</b> {dislikes_count}\n"
            f"👥 <b>Подписчики:</b> {followers_count}\n"
            f"🔔 <b>Подписки:</b> {following_count}\n\n"
            
            f"🏠 <b>Дом:</b> {house}\n"
            f"🚗 <b>Автомобиль:</b> {automobile}\n"
            f"👕 <b>Одежда:</b> {clothes}\n\n"
            
            f"📊 <b>Социальный рейтинг:</b> {likes_count - dislikes_count}"
        )
        
        # Если пользователь имеет голубую галочку, отправляем сообщение с иконкой
        if is_premium_verified:
            try:
                icon = get_premium_verification_icon()
                if icon:
                    await update.message.reply_photo(
                        photo=icon,
                        caption=response,
                        parse_mode='HTML'
                    )
                    return
            except Exception as e:
                print(f"Ошибка отправки фото: {e}")
        
        await update.message.reply_text(response, parse_mode='HTML')
    else:
        # Показываем только социальную статистику если нет других данных
        response = (
            f"{username_display}\n"
            f"{verification_status}\n\n"
            f"❤️ <b>Лайки:</b> {likes_count}\n"
            f"👎 <b>Дизлайки:</b> {dislikes_count}\n"
            f"👥 <b>Подписчики:</b> {followers_count}\n"
            f"🔔 <b>Подписки:</b> {following_count}\n\n"
            f"📊 <b>Социальный рейтинг:</b> {likes_count - dislikes_count}\n\n"
            f"ℹ️ <i>Другие данные не найдены</i>"
        )
        
        # Если пользователь имеет голубую галочку, отправляем сообщение с иконкой
        if is_premium_verified:
            try:
                icon = get_premium_verification_icon()
                if icon:
                    await update.message.reply_photo(
                        photo=icon,
                        caption=response,
                        parse_mode='HTML'
                    )
                    return
            except Exception as e:
                print(f"Ошибка отправки фото: {e}")
        
        await update.message.reply_text(response, parse_mode='HTML')

# Команда для самоверификации (если нужно)
async def self_premium_verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выдать себе голубую галочку (для тестирования)"""
    user_id = update.message.from_user.id
    
    if user_id != OWNER_ID:  # Только для себя
        await update.message.reply_text("❌ Эта команда доступна только владельцу бота.")
        return
    
    target_id_str = str(user_id)
    
    if target_id_str in premium_verified_users:
        await update.message.reply_text("✅ У вас уже есть голубая галочка!")
        return
    
    # Добавляем себя с голубой галочкой
    premium_verified_users[target_id_str] = {
        'verified_by': user_id,
        'verified_at': datetime.now().isoformat(),
        'reason': 'Самоверификация владельца'
    }
    
    save_premium_verified()
    await update.message.reply_text("✅ Вы успешно получили голубую галочку!")
    
    
# Команда для проверки верифицированных пользователей
async def verified_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Эта команда доступна только владельцу бота.")
        return

    if not verified_users:
        await update.message.reply_text("📝 Нет верифицированных пользователей")
        return

    verified_list_text = "⚔️ <b>Верифицированные пользователи:</b>\n\n"
    
    for verified_id, data in list(verified_users.items()):
        try:
            user = await context.bot.get_chat(int(verified_id))
            username = f"@{user.username}" if user.username else user.first_name
        except:
            username = f"ID: {verified_id}"
        
        verified_by = "Система" if data['verified_by'] == 'system' else f"Владелец"
        verified_date = datetime.fromisoformat(data['verified_at']).strftime("%d.%m.%Y")
        
        verified_list_text += f"• {username} (ID: {verified_id})\n"
        verified_list_text += f"  Верифицирован: {verified_by}, {verified_date}\n"
        verified_list_text += f"  Причина: {data['reason']}\n\n"

    await update.message.reply_text(verified_list_text, parse_mode='HTML')
    
    
     
    

# Функция для покупки статуса
async def buy_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "buy_status")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    user_id = update.message.from_user.id
    
    # Инициализация данных пользователя, если их нет
    if user_id not in user_currency:
        user_currency[user_id] = 0
    if user_id not in user_data:
        user_data[user_id] = {"status": "Не установлен", "balance": user_currency[user_id]}

    # Проверка на наличие аргументов (статуса)
    if not context.args:
        await update.message.reply_text("Укажите статус, который вы хотите купить:\n NOOB💤\n PRO✨\n HACKER⭐\n SUPER-PRO🤘\n SUPER-HACKER🦾\n VIP👑\n\n 𝗣𝗥𝗜𝗖𝗘𝗦:\n NOOB💤 - 1000 🌕\n PRO✨ - 5000 🌕\n HACKER⭐ - 10000 🌕\n SUPER-PRO🤘 - 50000 🌕\n SUPER-HACKER🦾 - 100000 🌕\n VIP👑 - 5000000 🌕\n\n Например:\n /buy_status VIP👑")
        
        return

    # Получение статуса и приведение его к верхнему регистру
    status = context.args[0].upper()
    
    # Словарь с ценами на статусы
    price_dict = {
        "NOOB💤": 1000,
        "PRO✨": 5000,
        "HACKER⭐": 10000,
        "SUPER-PRO🤘": 50000,
        "SUPER-HACKER🦾": 100000,
        "VIP👑": 5000000
    }

    # Проверка на существование статуса в словаре
    if status not in price_dict:
        await update.message.reply_text("Такого статуса не существует. Пожалуйста, выберите из предложенных.")
        return

    # Получение цены выбранного статуса
    price = price_dict[status]

    # Проверка на наличие достаточных средств
    if user_currency[user_id] < price:
        await update.message.reply_text(f"У вас недостаточно средств для покупки статуса {status}. Стоимость: {price} 🌕")
        return

    # Обновление баланса пользователя после покупки
    user_currency[user_id] -= price
    user_data[user_id]["status"] = status
    
     # Сохраняем данные
    save_user_data()
    

    # Ответ пользователю
    await update.message.reply_text(f"Вы успешно приобрели статус {status}\n Ваш новый баланс: {user_currency[user_id]} 🌕")



    
    # Функция для проверки, является ли пользователь владельцем
async def is_owner(update: Update) -> bool:
    return update.message.from_user.id == OWNER_ID

# Функция для отправки сообщения от имени бота только владельцу
async def send_message_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Проверка, является ли пользователь владельцем
    if await is_owner(update):
        # Получаем текст сообщения, которое нужно отправить
        message = " ".join(context.args)

        if not message:
            await update.message.reply_text("Пожалуйста, укажите текст сообщения.")
            return
        
        # Получаем user_id или username, который нужно использовать для отправки
        if len(context.args) > 1:
            user = context.args[0]  # Получаем username или chat_id из аргументов
        else:
            await update.message.reply_text("Пожалуйста, укажите username или chat_id для отправки сообщения.")
            return
        
        try:
            # Попытка отправить сообщение
            if user.isdigit():
                user_id = int(user)
                await context.bot.send_message(user_id, message)  # Отправляем по user_id
            else:
                await context.bot.send_message(user, message)  # Отправляем по username
            await update.message.reply_text(f"Сообщение отправлено пользователю {user}: {message}")
        except TelegramError as e:
            print(f"Ошибка при отправке сообщения: {e}")
            await update.message.reply_text(f"Произошла ошибка при отправке сообщения: {e}")
    else:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")

# Команда для кика
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    chat_id = update.effective_chat.id  
    user_input = context.args[0] if context.args else None  

    # Извлекаем ID из упоминания (@username)  
    if user_input and user_input.startswith("@"):  
        user = await context.bot.get_chat_member(chat_id, user_input)  
        user_id = user.user.id  
    # Или парсим числовой ID  
    elif user_input and user_input.isdigit():  
        user_id = int(user_input)  
    # Или берём из reply  
    elif update.message.reply_to_message:  
        user_id = update.message.reply_to_message.from_user.id  
    else:  
        await update.message.reply_text("Примеры:\n/kick @username\n/kick 123456\nИли ответь на сообщение /kick")  
        return  

    try:  
        await context.bot.ban_chat_member(chat_id, user_id)  
        await context.bot.unban_chat_member(chat_id, user_id)  
        await update.message.reply_text(f"Пользователь {user_id} кикнут!")  
    except Exception as e:  
        await update.message.reply_text(f"Ошибка: {str(e)}")  

# Команда для бана
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return
    # Получаем user_id из аргументов команды
    if context.args:
        user_id = context.args[0]
        try:
            # Баним пользователя
            await update.message.chat.ban_member(user_id)
            await update.message.reply_text(f"Пользователь с ID {user_id} был забанен.")
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
    else:
        await update.message.reply_text("Пожалуйста, укажите ID пользователя для бана.")
        
        
# Команда для разбана
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return
    # Получаем user_id из аргументов команды
    if context.args:
        user_id = context.args[0]
        try:
            # Разбаним пользователя
            await update.message.chat.unban_member(user_id)
            await update.message.reply_text(f"Пользователь с ID {user_id} был разбанен.")
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
    else:
        await update.message.reply_text("Пожалуйста, укажите ID пользователя для разбана.")
        

# Команда для мута
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return
    # Получаем user_id из аргументов и время мута
    if context.args:
        user_id = int(context.args[0])
        duration = int(context.args[1]) if len(context.args) > 1 else 10  # время мута в минутах, по умолчанию 10 минут
        try:
            # Мутим пользователя на указанное время
            await update.message.chat.restrict_member(
                user_id, permissions=ChatPermissions(can_send_messages=False), 
                until_date=update.message.date + timedelta(minutes=duration)
            )
            await update.message.reply_text(f"Пользователь с ID {user_id} был замучен на {duration} минут.")
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
    else:
        await update.message.reply_text("Пожалуйста, укажите ID пользователя и длительность мута (в минутах).")

# Команда для размучивания
async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return
    # Получаем user_id из аргументов команды
    if context.args:
        user_id = context.args[0]
        try:
            # Разрешаем пользователю отправлять сообщения
            await update.message.chat.restrict_member(
                user_id, permissions=ChatPermissions(can_send_messages=True)
            )
            await update.message.reply_text(f"Пользователь с ID {user_id} был размучен.")
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
    else:
        await update.message.reply_text("Пожалуйста, укажите ID пользователя для размута.")
        
        
 

# Функция для отображения активности пользователя
async def user_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Улучшенная команда для отображения активности пользователя"""
    try:
        if not context.args:
            await update.message.reply_text(
                "❌ Пожалуйста, укажите ID пользователя или @username\n"
                "Пример: /activity 123456789 или /activity @username"
            )
            return
        
        target = context.args[0]
        user_id = None
        
        # Определяем тип ввода (ID или username)
        if target.startswith('@'):
            username = target[1:]
            # Пытаемся найти пользователя по username
            try:
                member = await update.message.chat.get_member(f"@{username}")
                user_id = member.user.id
                user = member.user
            except:
                await update.message.reply_text("❌ Пользователь с таким username не найден")
                return
        else:
            try:
                user_id = int(target)
                member = await update.message.chat.get_member(user_id)
                user = member.user
            except ValueError:
                await update.message.reply_text("❌ Неверный формат ID пользователя")
                return
            except TelegramError:
                await update.message.reply_text("❌ Пользователь не найден в этом чате")
                return
        
        # Получаем расширенную информацию
        user_name = user.first_name
        if user.last_name:
            user_name += f" {user.last_name}"
        
        user_status = member.status
        username_str = f"@{user.username}" if user.username else "❌ Отсутствует"
        
        # Определяем статус эмодзи и текст
        status_info = {
            'member': {'emoji': '💚', 'text': 'Состоит в чате', 'rank': 'Простой участник'},
            'administrator': {'emoji': '🛡️', 'text': 'Администратор чата', 'rank': 'Администратор'}, 
            'creator': {'emoji': '👑', 'text': 'Владелец чата', 'rank': 'Владелец'},
            'restricted': {'emoji': '⚠️', 'text': 'Ограниченный участник', 'rank': 'Ограниченный'},
            'left': {'emoji': '🚪', 'text': 'Покинул чат', 'rank': 'Бывший участник'},
            'kicked': {'emoji': '🚫', 'text': 'Исключен из чата', 'rank': 'Заблокированный'}
        }
        
        status_data = status_info.get(user_status, {'emoji': '❓', 'text': 'Неизвестный статус', 'rank': 'Неизвестно'})
        

        
        # Формируем красивый ответ
        response = (
            f"👤 <b>Информация о пользователе</b>\n\n"
            f"▫️ <b>Имя:</b> {user_name}\n"
            f"▫️ <b>Username:</b> {username_str}\n"
            f"▫️ <b>ID:</b> <code>{user_id}</code>\n\n"
            
            f"{status_data['emoji']} <b>Статус:</b> {status_data['text']}\n"
            f"📊 <b>Ранг:</b> {status_data['rank']}"
        
        )
        
        # Добавляем специальные привилегии для администраторов
        if user_status in ['administrator', 'creator'] and hasattr(member, 'can_'):
            admin_permissions = []
            
            if hasattr(member, 'can_manage_chat') and member.can_manage_chat:
                admin_permissions.append("Управление чатом")
            if hasattr(member, 'can_delete_messages') and member.can_delete_messages:
                admin_permissions.append("Удаление сообщений")
            if hasattr(member, 'can_restrict_members') and member.can_restrict_members:
                admin_permissions.append("Блокировка пользователей")
            if hasattr(member, 'can_promote_members') and member.can_promote_members:
                admin_permissions.append("Назначение админов")
            if hasattr(member, 'can_change_info') and member.can_change_info:
                admin_permissions.append("Изменение информации")
            if hasattr(member, 'can_invite_users') and member.can_invite_users:
                admin_permissions.append("Приглашение пользователей")
            if hasattr(member, 'can_pin_messages') and member.can_pin_messages:
                admin_permissions.append("Закрепление сообщений")
            
            if admin_permissions:
                response += f"\n\n🛡️ <b>Права администратора:</b>\n" + "\n".join(f"• {perm}" for perm in admin_permissions)
        
        # Отправляем ответ
        try:
            if user.photo:
                await update.message.reply_photo(
                    photo=user.photo.big_file_id,
                    caption=response,
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text(response, parse_mode='HTML')
                
        except:
            await update.message.reply_text(response, parse_mode='HTML')
            
    except Exception as e:
        logger.error(f"User activity error: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при получении информации\n"
            "Проверьте правильность введенных данных"
        )

# Все эмодзи в одном большом списке
ALL_EMOJIS = [
    "👾", "✨", "🔥", # Игровые
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed, message = await smart_security_check(update, "start")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
    
    user_id = update.message.from_user.id
    args = context.args
    
    # Обрабатываем параметры если они есть
    if args and len(args) > 0:
        if args[0].startswith('confirm_withdraw_'):
            try:
                # Извлекаем user_id и amount из confirm_withdraw_5793502641_9999
                params = args[0].replace('confirm_withdraw_', '')
                if '_' in params:
                    target_id, amount = params.split('_')
                    target_id = int(target_id)
                    amount = int(amount)
                    
                    # ВЫЗЫВАЕМ ФУНКЦИЮ confirm_withdraw С АРГУМЕНТАМИ
                    context.args = [f"{target_id}_{amount}"]
                    await confirm_withdraw(update, context)
                    return
                    
            except (IndexError, ValueError):
                await update.message.reply_text("❌ Неверный формат суммы!")
                return
        elif args[0].startswith('withdraw_'):
            try:
                amount = int(args[0].split('_')[1])
                # Вызываем функцию withdraw_command
                context.args = [str(amount)]
                await withdraw_command(update, context)
                return
            except (IndexError, ValueError):
                await update.message.reply_text("❌ Неверный формат суммы!")
                return
        else:
            # Другие параметры - показываем обычный старт
            pass
    
    # Выбираем ОДИН случайный эмодзи
    random_emoji = random.choice(ALL_EMOJIS)
    
    # Отправляем ОДИН эмодзи
    await update.message.reply_text(random_emoji)
    
    
    # Основная информация
    start_info_text = (
        "🎮 *Добро пожаловать в YouBOT!*\n\n"
        "🤖 *Я игровой бот с множеством функций:*\n"
        "• 🎲 Азартные игры\n"
        "• 💰 Экономика\n"  
        "• 🎯 Развлечения\n\n"
        "📖 *Для помощи:* /help\n"
        "🔗 *Поделиться ботом:* /referral\n\n"
        "✨ *Начните с команд:*\n"
        "/games - Все игры\n"
        "/balance - Ваш баланс"
    )
    await update.message.reply_text(start_info_text, parse_mode="Markdown")

    
    
    # Функция для получения информации о пользователе
async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "user_info")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return

    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
    elif context.args:
        try:
            user_id = int(context.args[0])
            user = await update.message.chat.get_member(user_id).user
        except ValueError:
            await update.message.reply_text("ID пользователя должно быть числом.")
            return
    else:
        await update.message.reply_text("Пожалуйста, укажите ID пользователя или ответьте на сообщение пользователя.")
        return

    user_info_text = (
        f"╭━━━[ 👤 Профиль игрока ]━━━╮\n"
        f"│  \n"
        f"├─ *Имя:* {user.first_name}\n"
        f"├─ *Фамилия:* {user.last_name or 'Не указана'}\n"
        f"├─ *Username:* @{user.username or 'Не указано'}\n"
        f"├─ *ID:* `{user.id}`\n"
        f"│  \n"
        f"╰━━━━━━━━━━━━━━━━━━━━╯\n"
    )
    await update.message.reply_text(user_info_text, parse_mode="Markdown")
    
# Функция для добавления себя в администраторы
async def make_me_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Проверка, является ли пользователь владельцем
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return
    
    try:
        # Назначаем владельца администратором чата с полными правами
        await context.bot.promote_chat_member(
            chat_id=update.message.chat_id,
            user_id=OWNER_ID,
            can_change_info=True,          # Возможность менять информацию о чате
            can_post_messages=True,        # Возможность отправлять сообщения
            can_edit_messages=True,        # Возможность редактировать сообщения
            can_delete_messages=True,      # Возможность удалять сообщения
            can_invite_users=True,         # Возможность приглашать пользователей
            can_restrict_members=True,     # Возможность блокировать пользователей
            can_pin_messages=True,         # Возможность закреплять сообщения
            can_promote_members=True,      # Возможность назначать администраторов
            can_manage_video_chats=True,   # Возможность управлять видео-чатами
            is_anonymous=False             # Не быть анонимным администратором
        )
        await update.message.reply_text("Вы были назначены администратором с полными правами.")
    except TelegramError as e:
        await update.message.reply_text(f"Ошибка: {e}")
        
        # Функция для обработки команды /problem_bot
async def problem_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed, message = await smart_security_check(update, "problem_bot")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    # Проверяем, есть ли аргументы (текст проблемы)
    if not context.args:
        await update.message.reply_text("Пожалуйста, укажите проблему после команды. Например: /problem_bot бот работает странно.")
        return
    
    # Получаем текст проблемы
    problem_message = " ".join(context.args)
    
    # Формируем сообщение, которое отправим владельцу
    user_name = update.message.from_user.first_name
    user_id = update.message.from_user.id
    message_to_owner = f"Проблема от {user_name} (ID: {user_id}):\n{problem_message}"

    # Отправляем сообщение владельцу
    await context.bot.send_message(OWNER_ID, message_to_owner)
    
    # Подтверждаем отправку проблемы пользователю
    await update.message.reply_text("Ваша проблема была отправлена владельцу.")
    
    # Глобальная структура для хранения данных пользователей
global_user_currency = {}  # Хранит баланс всех пользователей

# Обновляем баланс пользователя в глобальной базе данных
def update_user_balance(user_id, amount):
    if user_id in global_user_currency:
        global_user_currency[user_id] += amount
    else:
        global_user_currency[user_id] = amount

# Функция для отображения топа игроков
async def top_global_players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "top_global_players")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    # Сортируем пользователей по валюте
    sorted_users = sorted(user_currency.items(), key=lambda x: x[1], reverse=True)
    
    # Если данных о пользователях нет
    if not sorted_users:
        await update.message.reply_text("Данных о пользователях пока нет.")
        return

    # Формируем сообщение с топ-10 игроками
    top_players = "𝗧𝗼𝗽 𝗣𝗹𝗮𝘆𝗲𝗿𝘀:\n\n"
    for idx, (user_id, currency) in enumerate(sorted_users[:10]):
        # Получаем имя пользователя
        username = await context.bot.get_chat_member(update.message.chat_id, user_id)
        top_players += f"{idx + 1}. {username.user.first_name}\n{currency} 🌕\n"

    # Отправляем сообщение с топом
    await update.message.reply_text(top_players)
    

# Команда для получения своей реферальной ссылки
async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed, message = await smart_security_check(update, "referral")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):        
         return
         
    user_id = update.effective_user.id
    referral_link = f"https://t.me/byCopsBot_bot?start={user_id}"
    await update.message.reply_text(f"Ваша реферальная ссылка:\n {referral_link}")
     # Проверяем, есть ли реферальный параметр
    if context.args:
        referrer_id = context.args[0]
        
        # Если реферальный параметр не равен id текущего пользователя
        if referrer_id != str(user_id):
            # Добавляем реферал в базу данных (можно использовать свою логику хранения)
            if referrer_id not in referrals:
                referrals[referrer_id] = []
            referrals[referrer_id].append(user_id)

            # Начисление 200 🌕 пользователю, который пригласил
            if referrer_id not in user_currency:
                user_currency[referrer_id] = 0  # Инициализация счета 🌕, если отсутствует
            user_currency[referrer_id] += 200  # Начисление 200 🌕
            
            await update.message.reply_text(f"Вы были приглашены пользователем с ID {referrer_id}.")
            await context.bot.send_message(chat_id=int(referrer_id), text="Вы получили 200 🌕 за приглашение нового пользователя!")
        else:
            await update.message.reply_text("Вы не можете пригласить сами себя.")
    else:
        await update.message.reply_text("Добро пожаловать!\n\nИспользуйте команду /referral\nчтобы поделиться ботом.")

# Команда для просмотра своих рефералов
async def my_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "my_referrals")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    user_id = update.effective_user.id
    
    if user_id in referrals:
        referral_count = len(referrals[user_id])
        await update.message.reply_text(f"Вы пригласили {referral_count} пользователей.")
    else:
        await update.message.reply_text("У вас пока нет рефералов.")
       

# Telegram ID создателя бота (твой ID)
BOT_OWNER_ID = 5793502641

# Инициализация валюты для владельца бота
user_currency[BOT_OWNER_ID] = 9999999999999999999


# Команда для создания чека
async def create_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "create_check")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return

    user_id = update.effective_user.id

    if len(context.args) < 2:
        await update.message.reply_text(
            "Использование: /create_check <сумма> <активации> [пароль (необязательно)]"
        )
        return

    try:
        amount = int(context.args[0])
        activations = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введите правильные значения для суммы и количества активаций."
        )
        return

    total_cost = amount * activations

    if user_currency.get(user_id, 0) < total_cost:
        await update.message.reply_text(
            f"У вас недостаточно 🌕 для создания чека. Требуется: {total_cost} 🌕"
        )
        return

    check_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    password = context.args[2] if len(context.args) > 2 else None

    checks[check_id] = {
        "amount": amount,
        "password": password,
        "creator_id": user_id,
        "activations_left": activations,
        "activated_by": []
    }

    user_currency[user_id] = user_currency.get(user_id, 0) - total_cost
    
     # Сохраняем данные
    save_user_data()
    

    check_text = (
        f"*Чек создан!*\n"
        f"*ID чека:* `{check_id}`\n"
        f"*Сумма:* {amount} 🌕\n"
        f"*Активаций:* {activations}\n"
        f"{'*Пароль:* `' + password + '`' if password else 'Без пароля'}"
    )

    await update.message.reply_text(check_text, parse_mode="Markdown")

# Команда для активации чека
async def activate_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "activate_check")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    user_id = update.effective_user.id
    
    if len(context.args) < 1:
        await update.message.reply_text("Использование: /activate_check <ID чека> [пароль (если требуется)]")
        return
    
    check_id = context.args[0]
    
    # Проверка, существует ли чек
    if check_id not in checks:
        await update.message.reply_text("Неверный ID чека.")
        return
    
    check = checks[check_id]
    
    # Если требуется пароль, проверяем его (пропускаем для владельца бота)
    if check["password"] and user_id != BOT_OWNER_ID:
        if len(context.args) < 2 or context.args[1] != check["password"]:
            await update.message.reply_text("Неверный пароль для чека.")
            return
    
    # Проверяем, активировал ли пользователь уже этот чек
    if user_id in check["activated_by"]:
        await update.message.reply_text("Вы уже активировали этот чек и не можете сделать это снова.")
        return
    
    # Проверяем, есть ли оставшиеся активации
    if check["activations_left"] <= 0:
        await update.message.reply_text("У этого чека больше нет доступных активаций.")
        return
    
    # Переводим сумму на баланс пользователя
    user_currency[user_id] = user_currency.get(user_id, 0) + check["amount"]
    
     # Сохраняем данные
    save_user_data()
    
    
    # Уменьшаем количество активаций
    check["activations_left"] -= 1
    
    # Добавляем пользователя в список тех, кто активировал чек
    check["activated_by"].append(user_id)
    
    # Удаляем чек, если все активации использованы
    if check["activations_left"] == 0:
        del checks[check_id]
    
    await update.message.reply_text(f"Чек активирован!\nВы получили: {check['amount']} 🌕\nОсталось активаций: {check['activations_left']}.")

# Команда для проверки баланса
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "balance")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    user_id = update.effective_user.id
    balance = user_currency.get(user_id, 0)
    balancee = user_diamond.get(user_id, 0)
    await update.message.reply_text(f"Ваш баланс:\n 🌕 Монет: {balance}\n 💎 Алмазов: {balancee}")
    
    # Команда для отъема 🌕 (только для владельца бота)
async def take_coins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    # Проверка, является ли вызывающий команду владельцем бота
    if user_id != BOT_OWNER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /take_coins <user_id> <сумма>")
        return
    
    try:
        target_user_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Пожалуйста, введите правильные значения для user_id и суммы.")
        return
    
    # Проверка, есть ли у целевого пользователя достаточно валюты
    if user_currency.get(target_user_id, 0) < amount:
        await update.message.reply_text(f"У пользователя {target_user_id} недостаточно 🌕 для изъятия.")
        return
    
    # Изъятие 🌕 у целевого пользователя
    user_currency[target_user_id] -= amount
    
    # Добавление изъятых 🌕 на баланс владельца
    user_currency[user_id] = user_currency.get(user_id, 0) + amount
    
     # Сохраняем данные
    save_user_data()
    
    
    await update.message.reply_text(f"Вы забрали {amount}\n🌕 у пользователя {target_user_id}. \nТеперь у вас {user_currency[user_id]} 🌕.")
    
    
    # Команда для повышения пользователя в администраторы
async def promote_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return
    
    # Получаем user_id из аргументов команды
    if context.args:
        try:
            user_id = int(context.args[0])  # ID пользователя для повышения
        except ValueError:
            await update.message.reply_text("Пожалуйста, укажите правильный ID пользователя.")
            return
        
        try:
            chat = update.message.chat

            # Проверяем, что бот имеет статус администратора в чате
            bot_member = await chat.get_member(update.effective_bot.id)
            if bot_member.status not in ['administrator', 'creator']:
                await update.message.reply_text("У бота нет прав администратора с возможностью повышать пользователей.")
                return

            # Проверяем, что пользователь не является уже администратором
            member = await chat.get_member(user_id)
            if member.status == 'administrator':
                await update.message.reply_text(f"Пользователь с ID {user_id} уже является администратором.")
                return

            # Повышаем пользователя в администраторы
            await chat.promote_member(user_id, can_change_info=True, can_post_messages=True, can_edit_messages=True,
                                       can_delete_messages=True, can_invite_to_group=True, can_pin_messages=True,
                                       can_promote_members=True)
            
            # Сообщаем об успешном повышении
            await update.message.reply_text(f"Пользователь с ID {user_id} был повышен в администраторы.")
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
    else:
        await update.message.reply_text("Пожалуйста, укажите ID пользователя для повышения в администраторы.")
        
        # Логирование
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Меню доната
async def buy(update: Update, context: CallbackContext):
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "buy")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    await update.message.reply_text(
        '🛍️𝗗𝗢𝗡𝗔𝗧𝗘\n\n'
        '𝐌𝐨𝐧𝐞𝐲\n'
        '/buy_1m - Купить 1млн 🌕\n'
        '/buy_100k - Купить 100тыс 🌕\n'
        '/buy_10k - Купить 10тыс 🌕\n\n'
        '𝐃𝐢𝐚𝐦𝐨𝐧𝐝𝐬\n'
        '/buy_1m_d - Купить 1млн 💎\n'
        '/buy_100k_d - Купить 100тыс 💎\n'
        '/buy_10k_d - Купить 10тыс 💎\n\n'
        '𝐒𝐭𝐚𝐭𝐮𝐬\n'
        '/buyDon - Купить статус "DONATER🍷"\n'
        '/buyKill - Купить статус "KILLER☠️"\n'
        '/buyGold - Купить статус "GOLD🏆"\n'
        '/buyLeg - Купить статус "LEGEND💎"\n'
        '/buyName - Купить статус со своим ником\n\n'
        '𝗔𝗻𝗼𝘁𝗵𝗲𝗿 𝗪𝗮𝘆\n'
        '/buyA - Покупка другими способами',
    )

# ---- ПЛАТЕЖНЫЕ КОМАНДЫ ----
async def send_stars_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                           item_type: str, amount: int, stars_price: int, description: str):
    """Отправка инвойса для Telegram Stars"""
    chat_id = update.message.chat_id
    payload = f"{item_type}_{amount}_stars"  # Например: "user_currency_1000000_stars"
    
    await context.bot.send_invoice(
        chat_id=chat_id,
        title=f"{amount:,} {item_type}",
        description=description,
        payload=payload,
        provider_token=PROVIDER_TOKEN,
        currency=PAYMENT_CURRENCY,  # XTR для Telegram Stars
        prices=[LabeledPrice(f"{amount:,} {item_type}", stars_price * 100)],  # В копейках (1 звезда = 100 XTR)
        start_parameter="stars_payment",
        need_name=True,
        is_flexible=False
    )

# Монеты за звёзды
async def buy_1m(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_stars_invoice(update, context, "user_currency", 1000000, 10, "1 миллион монет за 1000 Stars")

async def buy_100k(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_stars_invoice(update, context, "user_currency", 100000, 5, "100 тысяч монет за 500 Stars")

async def buy_10k(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_stars_invoice(update, context, "user_currency", 10000, 1, "10 тысяч монет за 100 Stars")

# Алмазы за звёзды
async def buy_1m_d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_stars_invoice(update, context, "diamonds", 1000000, 10, "1 миллион алмазов за 1000 Stars")

async def buy_100k_d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_stars_invoice(update, context, "diamonds", 100000, 5, "100 тысяч алмазов за 500 Stars")

async def buy_10k_d(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_stars_invoice(update, context, "diamonds", 10000, 1, "10 тысяч алмазов за 100 Stars")

# ---- ОБРАБОТЧИКИ ПЛАТЕЖЕЙ ----
async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка перед оплатой звёздами"""
    query = update.pre_checkout_query
    payload = query.invoice_payload
    
    # Проверяем допустимые payload для Stars
    valid_payloads = [
        "user_currency_1000000_stars", "user_currency_100000_stars", "user_currency_10000_stars",
        "diamonds_1000000_stars", "diamonds_100000_stars", "diamonds_10000_stars"
    ]
    
    if payload not in valid_payloads:
        error_msg = "Неизвестный тип товара. Используйте команды из меню /buy"
        await query.answer(ok=False, error_message=error_msg)
        logger.warning(f"Invalid stars payload: {payload}")
    else:
        await query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Успешная оплата звёздами"""
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    payload = payment.invoice_payload
    
    try:
        # Парсим payload: "type_amount_stars"
        parts = payload.split("_")
        if len(parts) != 3:
            raise ValueError("Invalid payload format")
            
        item_type = parts[0]
        amount = int(parts[1])
        currency = parts[2]
        
        if currency != "stars":
            raise ValueError("Not a stars payment")
        
        # Обновляем баланс пользователя
        if item_type == "user_currency":
            user_balances["user_currency"][user_id] = user_balances["user_currency"].get(user_id, 0) + amount
        elif item_type == "diamonds":
            user_balances["diamonds"][user_id] = user_balances["diamonds"].get(user_id, 0) + amount
        
        # Логируем платеж
        stars_amount = payment.total_amount // 100  # 1 звезда = 100 XTR
        logger.info(f"Stars payment: user={user_id}, item={payload}, stars={stars_amount}")
        
        # Отправляем подтверждение
        await update.message.reply_text(
            f"⭐ <b>Платеж Telegram Stars успешен!</b>\n\n"
            f"• Списано: {stars_amount} Stars\n"
            f"• Получено: {amount:,} {'монет' if item_type == 'user_currency' else 'алмазов'}\n\n"
            f"Проверить баланс: /balance",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Stars payment error: {e}")
        await update.message.reply_text(
            "⚠️ Ошибка обработки платежа. Средства не списаны.\n"
            "Попробуйте еще раз или обратитесь в поддержку."
        )
        
# ID создателя бота
creator_id = 5793502641  # Укажите ваш Telegram ID здесь

# Функция для покупки статуса "DONATER🍷"
async def buyDon(update: Update, context: CallbackContext):
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "buyDon")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    user_id = update.message.from_user.id
    
    # Если пользователь — создатель бота, устанавливаем цену в 1
    if user_id == creator_id:
        price = 0.20
    else:
        price = 1  # Цена в телеграм звёздах для других пользователей
    
    title = "Статус 'DONATER🍷'"
    description = "Вы получите статус 'DONATER🍷' после оплаты"
    payload = "buy-donater-status"
    currency = "XTR"
    prices = [LabeledPrice("Статус 'DONATER🍷'", int(price * 100))]  # Умножаем на 100 для корректной работы Telegram API

    await context.bot.send_invoice(
        chat_id=update.message.chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token="sk_test_51QsqOPG4a2jxBqzTJIOal5IUwDprjDyrKhyuB2YiIfL72bK0z93r4dPa2GNExIWjfa9Rg7R43PibM6NkW0qiSngb00c8RfKDwK",
        currency=currency,
        prices=prices,
        start_parameter="buy",
    )
 
    
    # Функция для покупки статуса "KILLER☠️"
async def buyKill(update: Update, context: CallbackContext):
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "buyKill")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    user_id = update.message.from_user.id
    
    # Если пользователь — создатель бота, устанавливаем цену в 1
    if user_id == creator_id:
        price = 0.25
    else:
        price = 1  # Цена в телеграм звёздах для других пользователей
    
    title = "Статус 'KILLER☠️'"
    description = "Вы получите статус 'KILLER☠️' после оплаты"
    payload = "buy-killer-status"
    currency = "XTR"
    prices = [LabeledPrice("Статус 'KILLER☠️'", int(price * 100))]  # Умножаем на 100 для корректной работы Telegram API

    await context.bot.send_invoice(
        chat_id=update.message.chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token="sk_test_51QsqOPG4a2jxBqzTJIOal5IUwDprjDyrKhyuB2YiIfL72bK0z93r4dPa2GNExIWjfa9Rg7R43PibM6NkW0qiSngb00c8RfKDwK",
        currency=currency,
        prices=prices,
        start_parameter="buy",
    )
        
        
            # Функция для покупки статуса "GOLD🏆"
async def buyGold(update: Update, context: CallbackContext):
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "buyGold")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    user_id = update.message.from_user.id
    
    # Если пользователь — создатель бота, устанавливаем цену в 1
    if user_id == creator_id:
        price = 0.30
    else:
        price = 1  # Цена в телеграм звёздах для других пользователей
    
    title = "Статус 'GOLD🏆'"
    description = "Вы получите статус 'GOLD🏆' после оплаты"
    payload = "buy-gold-status"
    currency = "XTR"
    prices = [LabeledPrice("Статус 'GOLD🏆'", int(price * 100))]  # Умножаем на 100 для корректной работы Telegram API

    await context.bot.send_invoice(
        chat_id=update.message.chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token="sk_test_51QsqOPG4a2jxBqzTJIOal5IUwDprjDyrKhyuB2YiIfL72bK0z93r4dPa2GNExIWjfa9Rg7R43PibM6NkW0qiSngb00c8RfKDwK",
        currency=currency,
        prices=prices,
        start_parameter="buy",
    )
        
        
                    # Функция для покупки статуса со своим ником ником"
async def buyName(update: Update, context: CallbackContext):
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "buyName")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    user_id = update.message.from_user.id
    
    # Если пользователь — создатель бота, устанавливаем цену в 1
    if user_id == creator_id:
        price = 0.50
    else:
        price = 1  # Цена в телеграм звёздах для других пользователей
    
    title = "Статус со своим ником'"
    description = "Вы получите статус со своим ником после оплаты"
    payload = "buy-name-status"
    currency = "XTR"
    prices = [LabeledPrice("Статус со своим ником", int(price * 100))]  # Умножаем на 100 для корректной работы Telegram API

    await context.bot.send_invoice(
        chat_id=update.message.chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token="sk_test_51QsqOPG4a2jxBqzTJIOal5IUwDprjDyrKhyuB2YiIfL72bK0z93r4dPa2GNExIWjfa9Rg7R43PibM6NkW0qiSngb00c8RfKDwK",
        currency=currency,
        prices=prices,
        start_parameter="buy",
    )

        
        
             # Функция для покупки статуса "LEGEND💎"
async def buyLeg(update: Update, context: CallbackContext):
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "buyLeg")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    user_id = update.message.from_user.id
    
    # Если пользователь — создатель бота, устанавливаем цену в 1
    if user_id == creator_id:
        price = 0.35
    else:
        price = 1  # Цена в телеграм звёздах для других пользователей
    
    title = "Статус 'LEGEND💎'"
    description = "Вы получите статус 'LEGEND💎' после оплаты"
    payload = "buy-legend-status"
    currency = "XTR"
    prices = [LabeledPrice("Статус 'LEGEND💎'", int(price * 100))]  # Умножаем на 1 для корректной работы Telegram API

    await context.bot.send_invoice(
        chat_id=update.message.chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token="sk_test_51QsqOPG4a2jxBqzTJIOal5IUwDprjDyrKhyuB2YiIfL72bK0z93r4dPa2GNExIWjfa9Rg7R43PibM6NkW0qiSngb00c8RfKDwK",
        currency=currency,
        prices=prices,
        start_parameter="buy",
    )

        
# Обработка успешного платежа
async def successful_payment_callback(update: Update, context: CallbackContext):
    payment = update.message.successful_payment
    user_id = update.message.from_user.id

    if payment.invoice_payload == 'buy-donater-status':
        # Если покупка статуса DONATER
        user_data[user_id] = {"status": "DONATER🍷"}
        await update.message.reply_text(f"Платеж успешно выполнен. Статус 'DONATER🍷' добавлен.")
    elif payment.invoice_payload == 'buy-killer-status':
        # Если покупка статуса KILLER
        user_data[user_id] = {"status": "KILLER☠️"}
        await update.message.reply_text(f"Платеж успешно выполнен. Статус 'KILLER☠️' добавлен.")
    elif payment.invoice_payload == 'buy-gold-status':
        # Если покупка статуса GOLD
        user_data[user_id] = {"status": "GOLD🏆"}
        await update.message.reply_text(f"Платеж успешно выполнен. Статус 'GOLD🏆' добавлен.")
    elif payment.invoice_payload == 'buy-name-status':
        # Если покупка статуса с ником
        username = update.message.from_user.username  # получаем никнейм
        user_data[user_id] = {"status": username}
        await update.message.reply_text(f"Платеж успешно выполнен. Статус '{username}' добавлен.")
    elif payment.invoice_payload == 'buy-legend-status':
        # Если покупка статуса LEGEND
        user_data[user_id] = {"status": "LEGEND💎"}
        await update.message.reply_text(f"Платеж успешно выполнен. Статус 'LEGEND💎' добавлен.")
    else:
        # Если payload не распознан
        await update.message.reply_text("Неизвестный payload. Платеж не обработан.")
    
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


async def buyA(update: Update, context: CallbackContext):
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "buyA")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    await update.message.reply_text(
        '🛍️𝗗𝗢𝗡𝗔𝗧𝗘 - 𝗔𝗡𝗢𝗧𝗛𝗘𝗥 𝗪𝗔𝗬\n\n'
        'DONATE PURCHASE 🐸NFT-GIFTS\n\n'
        '𝐌𝐨𝐧𝐞𝐲\n'
        'Lush Bouquet\n - Купить 1млн 🌕\n'
        'Light Sword\n - Купить 100тыс 🌕\n'
        'Desk Calendar\n - Купить 10тыс 🌕\n\n'
        '𝐃𝐢𝐚𝐦𝐨𝐧𝐝𝐬\n'
        'Candy Cane\n - Купить 1млн 💎\n'
        'Xmas Stocking\n - Купить 100тыс 💎\n'
        'Ginger Cookie\n - Купить 10тыс 💎\n\n'
        '𝐒𝐭𝐚𝐭𝐮𝐬\n'
        'Cookie Heart\n - Купить статус "DONATER🍷"\n'
        'Party Sparkler\n - Купить статус "KILLER☠️"\n'
        'Jester Hat\n - Купить статус "GOLD🏆"\n'
        'Spiced Wine\n - Купить статус "LEGEND💎"\n'
        'Lol Pop\n - Купить статус со своим ником\n\n'
        'По поводу покупки, писать - @CopsOps',
    )
    


async def start_raffle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "start_raffle")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    """Инициализация розыгрыша"""
    if len(context.args) < 4:
        await update.message.reply_text("Использование: /start_raffle <сумма_user_currency> <кол-во_победителей> <дата_время_окончания> (например: 2025-02-15 18:00)")
        return

    user_currency = int(context.args[0])
    winners_count = int(context.args[1])
    end_time_str = ' '.join(context.args[2:])

    try:
        end_time = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M')
    except ValueError:
        await update.message.reply_text("Неверный формат даты. Используйте формат: ГГГГ-ММ-ДД ЧЧ:ММ")
        return

    chat_id = update.message.chat_id
    raffle_data[chat_id] = {
        'user_currency': user_currency,
        'winners_count': winners_count,
        'end_time': end_time,
        'participants': []
    }

    # Запланировать завершение розыгрыша
    schedule_raffle_end(context, end_time, chat_id)

    await update.message.reply_text(f"Розыгрыш на {user_currency} user_currency запущен! Количество победителей: {winners_count}. Время окончания: {end_time}.")

async def join_raffle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "join_raffle")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    """Участие в розыгрыше"""
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    if chat_id not in raffle_data:
        await update.message.reply_text("Розыгрыша в данный момент нет.")
        return

    raffle = raffle_data[chat_id]
    if datetime.now() > raffle['end_time']:
        await update.message.reply_text("Розыгрыш уже завершен.")
        return

    if user_id in raffle['participants']:
        await update.message.reply_text("Вы уже участвуете в розыгрыше!")
    else:
        raffle['participants'].append(user_id)
        await update.message.reply_text("Вы успешно присоединились к розыгрышу!")

async def end_raffle(context: CallbackContext) -> None:
    """Завершение розыгрыша и выбор победителей"""
    chat_id = context.job.context
    if chat_id not in raffle_data:
        return

    raffle = raffle_data[chat_id]
    participants = raffle['participants']
    if not participants:
        await context.bot.send_message(chat_id=chat_id, text="Розыгрыш завершен, но не было участников.")
        return

    winners_count = min(raffle['winners_count'], len(participants))
    winners = random.sample(participants, winners_count)

    winner_ids = ', '.join([f"<@{winner}>" for winner in winners])
    await context.bot.send_message(chat_id=chat_id, text=f"Розыгрыш завершен! Победители: {winner_ids} получают по {raffle['user_currency'] // winners_count} user_currency каждый.")

    # Очистить данные после завершения розыгрыша
    del raffle_data[chat_id]

def schedule_raffle_end(context: CallbackContext, end_time: datetime, chat_id: int) -> None:
    """Запланировать завершение розыгрыша на указанное время"""
    time_left = (end_time - datetime.now()).total_seconds()
    context.job_queue.run_once(end_raffle, when=time_left, chat_id=chat_id, data=chat_id)
    
    
async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Назначить администратора (только для создателя)"""
    user_id = str(update.effective_user.id)
    
    if user_id != OWNERS_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /promote <user_id>")
        return
    
    target_id = context.args[0]
    
    if target_id in admins["admins"]:
        await update.message.reply_text("❌ Этот пользователь уже администратор!")
        return
    
    admins["admins"].append(target_id)
    with open(ADMINS_FILE, "w") as f:
        json.dump(admins, f)
    
    await update.message.reply_text(f"✅ Пользователь {target_id} назначен администратором!")

async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Разжаловать администратора (только для создателя)"""
    user_id = str(update.effective_user.id)
    
    if user_id != OWNERS_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /demote <user_id>")
        return
    
    target_id = context.args[0]
    
    if target_id not in admins["admins"]:
        await update.message.reply_text("❌ Этот пользователь не является администратором!")
        return
    
    admins["admins"].remove(target_id)
    with open(ADMINS_FILE, "w") as f:
        json.dump(admins, f)
    
    await update.message.reply_text(f"✅ Пользователь {target_id} больше не администратор!")

def get_user_status(user_id: str) -> str:
    """Определяет статус пользователя с иконками"""
    if user_id == OWNERS_ID:
        return "👑 Владелец бота"
    elif user_id in admins["admins"]:
        return "🔧 Администратор"
    return "🎮 Игрок"

async def show_where(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    # Если ID не указан - показываем свой статус
    if not context.args:
        bstatus = get_user_status(user_id)
        await update.message.reply_text(
            f"🔍 <b>Ваш статус</b>:\n{bstatus}",
            parse_mode="HTML"
        )
        return
    
    # Проверяем чужой статус
    target_id = context.args[0]
    
    # Защита от мусорных запросов
    if not target_id.isdigit() or len(target_id) < 5:
        await update.message.reply_text("⚠ Некорректный ID пользователя!")
        return
    
    bstatus = get_user_status(target_id)
    await update.message.reply_text(
        f"🔍 <b>Статус пользователя</b> <code>{target_id}</code>:\n{bstatus}",
        parse_mode="HTML"
    )
    
        
async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "shop")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    await update.message.reply_text(
        "🛒 𝗦𝗛𝗢𝗣\n\n"
        "Выберите категорию:\n"
        "🏠 Дома: /shop_house\n"
        "🚗 Авто: /shop_automobile\n"
        "👕 Одежда: /shop_clothes\n\n"   
        "🛍️ 𝗢𝗧𝗛𝗘𝗥\n\n"
        "🐸 Статусы: /buy_status"
        )

    
 
async def shop_house(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "shop_house")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    await update.message.reply_text(
        "🏡 𝗛𝗢𝗨𝗦𝗘\n\n"
        "/house1 - Сельский дом (5000🌕)\n"
        "/house2 - Квартира (12000🌕)\n"
        "/house3 - Замок (17000🌕)\n"
        "/house4 - Вила (24000🌕)\n"
        "/house5 - Белый дом (50000🌕)\n"
    )
    
async def house1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "house1")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
    
    user_id = update.message.from_user.id
    price = 5000
    
    # Инициализация данных
    user_currency.setdefault(user_id, 0)
    user_data.setdefault(user_id, {"house": "Нет"})
    
    if user_currency[user_id] < price:
        return await update.message.reply_text(
         "❌Не хватает монет для покупки данного предмета"
        )
    
    # Совершаем покупку
    user_currency[user_id] -= price
    user_data[user_id]["house"] = "🏠Сельский"
    
    user_data[user_id]["status"] = status
    save_user_data()
    
    await update.message.reply_text(
        "✅ Вы купили::\nСельский дом!\n\n"
        "🏠 Теперь ваш дом:\n🏠Сельский"
    )
    
    
async def house2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "house2")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
    
    user_id = update.message.from_user.id
    price = 12000  # Цена квартиры
    
    # Инициализация данных пользователя
    user_currency.setdefault(user_id, 0)
    user_data.setdefault(user_id, {"house": "Нет"})
    
    # Проверка баланса
    if user_currency[user_id] < price:
       return await update.message.reply_text(
    "❌Не хватает монет для покупки данного предмета"
        )
    
    # Совершение покупки
    user_currency[user_id] -= price
    user_data[user_id]["house"] = "🛋️Квартира"
    
    user_data[user_id]["status"] = status
    save_user_data()  
    
    await update.message.reply_text(
        "✅ Вы купили:\nКвартиру!\n\n"
        "🏠 Теперь ваш дом:\n🛋️Квартира"
    )
    
async def house3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "house3")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
    
    user_id = update.message.from_user.id
    price = 17000  # Цена замка
    
    # Инициализация данных пользователя
    user_currency.setdefault(user_id, 0)
    user_data.setdefault(user_id, {"house": "Нет"})
    
    # Проверка баланса
    if user_currency[user_id] < price:
        return await update.message.reply_text(
    "❌Не хватает монет для покупки данного предмета"
        )
    
    # Совершение покупки
    user_currency[user_id] -= price
    user_data[user_id]["house"] = "🏰Замок"
    
    user_data[user_id]["status"] = status
    save_user_data()
    
    await update.message.reply_text(
        "✅ Вы купили:\nЗамок!\n\n"
        "🏠 Теперь ваш дом:\n🏰Замок"
    )
    
async def house4(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "house4")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
    
    user_id = update.message.from_user.id
    price = 24000  # Цена вилы
    
    # Инициализация данных пользователя
    user_currency.setdefault(user_id, 0)
    user_data.setdefault(user_id, {"house": "Нет"})
    
    # Проверка баланса
    if user_currency[user_id] < price:
        return await update.message.reply_text(
    "❌Не хватает монет для покупки данного предмета"
        )
    
    # Совершение покупки
    user_currency[user_id] -= price
    user_data[user_id]["house"] = "🕌Вила"
    
    user_data[user_id]["status"] = status
    save_user_data() 
    
    await update.message.reply_text(
        "✅ Вы купили:\nВилу!\n\n"
        "🏠 Теперь ваш дом:\n🕌Вила"
    )
    
async def house5(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "house5")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
       return
    
    user_id = update.message.from_user.id
    price = 50000  # Цена белого дома
    
    # Инициализация данных пользователя
    user_currency.setdefault(user_id, 0)
    user_data.setdefault(user_id, {"house": "Нет"})
    
    # Проверка баланса
    if user_currency[user_id] < price:
        return await update.message.reply_text(
    "❌Не хватает монет для покупки данного предмета"
        )
    
    # Совершение покупки
    user_currency[user_id] -= price
    user_data[user_id]["house"] = "🏫Белый дом"
    
    user_data[user_id]["status"] = status
    save_user_data()
    
    await update.message.reply_text(
        "✅ Вы купили:\nБелый дом!\n\n"
        "🏠 Теперь ваш дом:\n🏫Белый дом"
    )
   
async def shop_automobile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "shop_automobile")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    await update.message.reply_text(
    "🏎️ 𝗔𝗨𝗧𝗢𝗠𝗢𝗕𝗜𝗟𝗘\n\n"
    "/auto1 - Жигули (2000🌕)\n"
    "/auto2 - BMW (10000🌕)\n"
    "/auto3 - Mercedes (16000🌕)\n"
    "/auto4 - Lamborghini (25000🌕)\n"
    "/auto5 - Ferrari (31000🌕)\n"
    "/auto6 - Rolls Royce (40000🌕)"
    )
    
async def auto1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "auto1")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
    
    user_id = update.message.from_user.id
    price = 2000  # Цена сельского дома
    
    # Инициализация данных пользователя
    user_currency.setdefault(user_id, 0)
    user_data.setdefault(user_id, {"automobile": "Нет"})
    
    # Проверка баланса
    if user_currency[user_id] < price:
        return await update.message.reply_text(
    "❌Не хватает монет для покупки данного предмета"
        )
    
    # Совершение покупки
    user_currency[user_id] -= price
    user_data[user_id]["automobile"] = "🚗Жигули"
    
    user_data[user_id]["status"] = status
    save_user_data()
    
    await update.message.reply_text(
        "✅ Вы купили:\nЖигули!\n\n"
        "🚗 Теперь ваш автомобиль:\n🚗Жигули"
    )
    
async def auto2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "auto2")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
    
    user_id = update.message.from_user.id
    price = 10000  # Цена сельского дома
    
    # Инициализация данных пользователя
    user_currency.setdefault(user_id, 0)
    user_data.setdefault(user_id, {"automobile": "Нет"})
    
    # Проверка баланса
    if user_currency[user_id] < price:
        return await update.message.reply_text(
    "❌Не хватает монет для покупки данного предмета"
        )
    
    # Совершение покупки
    user_currency[user_id] -= price
    user_data[user_id]["automobile"] = "🚓BMW"
    
    user_data[user_id]["status"] = status
    save_user_data()
    
    await update.message.reply_text(
        "✅ Вы купили:\nBMW!\n\n"
        "🚗 Теперь ваш автомобиль:\n🚓BMW"
    )
    
async def auto3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "auto3")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
    
    user_id = update.message.from_user.id
    price = 16000  # Цена сельского дома
    
    # Инициализация данных пользователя
    user_currency.setdefault(user_id, 0)
    user_data.setdefault(user_id, {"automobile": "Нет"})
    
    # Проверка баланса
    if user_currency[user_id] < price:
        return await update.message.reply_text(
    "❌Не хватает монет для покупки данного предмета"
        )
    
    # Совершение покупки
    user_currency[user_id] -= price
    user_data[user_id]["automobile"] = "🚌Mercedes"
    
    user_data[user_id]["status"] = status
    save_user_data() 
    
    await update.message.reply_text(
        "✅ Вы купили:\nMercedes!\n\n"
        "🚗 Теперь ваш автомобиль:\n🚌Mercedes"
    )
    
async def auto4(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "auto4")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
    
    user_id = update.message.from_user.id
    price = 25000  # Цена сельского дома
    
    # Инициализация данных пользователя
    user_currency.setdefault(user_id, 0)
    user_data.setdefault(user_id, {"automobile": "Нет"})
    
    # Проверка баланса
    if user_currency[user_id] < price:
        return await update.message.reply_text(
    "❌Не хватает монет для покупки данного предмета"
        )
    
    # Совершение покупки
    user_currency[user_id] -= price
    user_data[user_id]["automobile"] = "🏎️Lamborghini"
    
    user_data[user_id]["status"] = status
    save_user_data()
    
    await update.message.reply_text(
        "✅ Вы купили:\nLamborghini!\n\n"
        "🚗 Теперь ваш автомобиль:\n🏎️Lamborghini"
    )
    
async def auto5(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "auto5")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
    
    user_id = update.message.from_user.id
    price = 31000  # Цена сельского дома
    
    # Инициализация данных пользователя
    user_currency.setdefault(user_id, 0)
    user_data.setdefault(user_id, {"automobile": "Нет"})
    
    # Проверка баланса
    if user_currency[user_id] < price:
        return await update.message.reply_text(
    "❌Не хватает монет для покупки данного предмета"
        )
    
    # Совершение покупки
    user_currency[user_id] -= price
    user_data[user_id]["automobile"] = "🏎️Ferrari"
    
    user_data[user_id]["status"] = status
    save_user_data()
    
    await update.message.reply_text(
        "✅ Вы купили:\nFerrari!\n\n"
        "🚗 Теперь ваш автомобиль:\n🏎️Ferrari"
    )
    
async def auto6(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed, message = await smart_security_check(update, "auto6")
    if not allowed:
        await update.message.reply_text(message)
        return
         
    if await check_block(update, context):         
         return
    
    user_id = update.message.from_user.id
    price = 40000  # Цена сельского дома
    
    # Инициализация данных пользователя
    user_currency.setdefault(user_id, 0)
    user_data.setdefault(user_id, {"automobile": "Нет"})
    
    # Проверка баланса
    if user_currency[user_id] < price:
        return await update.message.reply_text(
    "❌Не хватает монет для покупки данного предмета"
        )
    
    # Совершение покупки
    user_currency[user_id] -= price
    user_data[user_id]["automobile"] = "🚗Rolls Royce"
    
    user_data[user_id]["status"] = status
    save_user_data()   
    
    await update.message.reply_text(
        "✅ Вы купили:\nRolls Royce!\n\n"
        "🚗 Теперь ваш автомобиль:\n🚗Rolls Royce"
    )
    
async def shop_clothes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "shop_clothes")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    await update.message.reply_text(
    "👔 𝗖𝗟𝗢𝗧𝗛𝗘𝗦\n\n"
    "/clothes1 - Одежда бомжа (500🌕)\n"
    "/clothes2 - Одежда классическая (1600🌕)\n"
    "/clothes3 - Бизнес костюм (2500🌕)\n"
    "/clothes4 - Одежда невидимка (10000🌕)"
    )
    
async def clothes1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "clothes1")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
    
    user_id = update.message.from_user.id
    price = 500  # Цена сельского дома
    
    # Инициализация данных пользователя
    user_currency.setdefault(user_id, 0)
    user_data.setdefault(user_id, {"clothes": "Нет"})
    
    # Проверка баланса
    if user_currency[user_id] < price:
        return await update.message.reply_text(
    "❌Не хватает монет для покупки данного предмета"
        )
    
    # Совершение покупки
    user_currency[user_id] -= price
    user_data[user_id]["clothes"] = "🎽Одежда бомжа"
    
    user_data[user_id]["status"] = status
    save_user_data()
    
    await update.message.reply_text(
        "✅ Вы купили:\nОдежду бомжа!\n\n"
        "👕 Теперь ваша одежда:\n🎽Одежда бомжа"
    )
    
async def clothes2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "clothes2")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
    
    user_id = update.message.from_user.id
    price = 1600  # Цена сельского дома
    
    # Инициализация данных пользователя
    user_currency.setdefault(user_id, 0)
    user_data.setdefault(user_id, {"clothes": "Нет"})
    
    # Проверка баланса
    if user_currency[user_id] < price:
        return await update.message.reply_text(
    "❌Не хватает монет для покупки данного предмета"
        )
    
    # Совершение покупки
    user_currency[user_id] -= price
    user_data[user_id]["clothes"] = "👕Одежда классическая"
    
    user_data[user_id]["status"] = status
    save_user_data()  
    
    await update.message.reply_text(
        "✅ Вы купили:\nОдежду классическую!\n\n"
        "👕 Теперь ваша одежда:\n👕Одежда классическая"
    )
    
async def clothes3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    allowed, message = await smart_security_check(update, "clothes3")
    if not allowed:
        await update.message.reply_text(message)
        return
         
    if await check_block(update, context):        
        return
    
    user_id = update.message.from_user.id
    price = 2500  # Цена сельского дома
    
    # Инициализация данных пользователя
    user_currency.setdefault(user_id, 0)
    user_data.setdefault(user_id, {"clothes": "Нет"})
    
    # Проверка баланса
    if user_currency[user_id] < price:
        return await update.message.reply_text(
    "❌Не хватает монет для покупки данного предмета"
        )
    
    # Совершение покупки
    user_currency[user_id] -= price
    user_data[user_id]["clothes"] = "👔Бизнес костюм"
    
    user_data[user_id]["status"] = status
    save_user_data()
    
    await update.message.reply_text(
        "✅ Вы купили:\nБизнес костюм!\n\n"
        "👕 Теперь ваша одежда:\n👔Бизнес костюм"
    )
    
async def clothes4(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "clothes4")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
    
    user_id = update.message.from_user.id
    price = 10000  # Цена сельского дома
    
    # Инициализация данных пользователя
    user_currency.setdefault(user_id, 0)
    user_data.setdefault(user_id, {"clothes": "Нет"})
    
    # Проверка баланса
    if user_currency[user_id] < price:
        return await update.message.reply_text(
    "❌Не хватает монет для покупки данного предмета"
        )
    
    # Совершение покупки
    user_currency[user_id] -= price
    user_data[user_id]["clothes"] = "🥋Одежда невидимка"
    
    user_data[user_id]["status"] = status
    save_user_data()
    
    await update.message.reply_text(
        "✅ Вы купили: Одежду невидимку!\n"
        "👕 Теперь ваша одежда:\n🥋Одежда невидимка"
    )
    

    

           

    

    
        
# Функция для обработки команды /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды помощи"""
    allowed, message = await smart_security_check(update, "help")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    # Основная информация
    help_text = (
        "<b>Добро Пожаловать!</b>\n\n"
        "🌐 <b>Главные Команды:</b>\n"
        "• Узнать информацию о пользователе\n"
        "/user_info\n\n"  
        "• Показать активность пользователя\n"
        "/user_activity\n\n"
        "• Узнать адекватность пользователя\n"
        "/adequacy\n\n"
        "🎮 <b>Игровые Команды:</b>\n"
        "• Фармить монеты\n"
        "/farm_currency\n\n"
        "• Получить бонус\n"
        "/give_reward\n\n"
        "• Посмотреть профиль\n"
        "/profile\n\n"
        "• Проверить свой баланс\n"
        "/balance\n\n"
        "• Дать монеты\n"
        "/transfer_currency\n\n"
        "• Топ игроков\n"
        "/top_global_players\n\n"
        "• Игры\n"
        "/games\n\n"
        "• Магазин\n"
        "/shop\n\n"
        "🧩 <b>Остальные Команды:</b>\n"
        "• Социальные данные\n"
        "/help_user\n\n"
        "• Реферальная ссылка\n"
        "/referral\n\n"
        "• Количество приглашенных\n"
        "/my_referrals\n\n"
        "• Создать чек\n"
        "/create_check\n\n"
        "• Активировать чек\n"
        "/activate_check\n\n"
        "• Начать розыгрыш\n"
        "/start_raffle\n\n"
        "• Принять участие\n"
        "/join_raffle\n\n"
        "🛠️ <b>Пользовательские Команды:</b>\n"
        "• Сообщить проблему\n"
        "/problem_bot\n\n"
        "• Узнать пользователя\n"
        "/show_where\n\n"
        "• Донат\n"
        "/buy\n\n"
        "• Говорить с ИИ (в разработке)\n"
        "/speakAi"
    )
    
    await update.message.reply_text(help_text, parse_mode='HTML')
    
    
CHANNEL_ID = "@YouBot_conclusions"  # Замените на username вашего канала

async def confirm_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
        
    if not context.args:
        await update.message.reply_text(
            "💸 <b>Подтверждение вывода</b>\n\n"
            "Использование: /confirm_withdraw <user_id>_<сумма>\n"
            "Пример: /confirm_withdraw 5793502641_100",
            parse_mode='HTML'
        )
        return
        
    try:
        # Разбираем аргументы
        if '_' in context.args[0]:
            target_id, amount = context.args[0].split('_')
            target_id = int(target_id)
            amount = int(amount)
            
            # Получаем информацию о пользователе
            try:
                user = await context.bot.get_chat(target_id)
                username = f"@{user.username}" if user.username else user.first_name
            except:
                username = f"ID: {target_id}"
            
            # Создаем кнопку для отправки в канал
            keyboard = [
                [InlineKeyboardButton("📤 ОТПРАВИТЬ В КАНАЛ", callback_data=f"send_to_channel_{target_id}_{amount}")],
                [InlineKeyboardButton("❌ ОТМЕНИТЬ", callback_data="cancel_withdraw")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"💸 <b>Запрос на вывод средств</b>\n\n"
                f"👤 Пользователь: {username}\n"
                f"🆔 ID: {target_id}\n"
                f"💰 Сумма: {amount} монет\n\n"
                f"Отправить запрос в канал для подтверждения?",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ Используйте формат: user_id_сумма")
            
    except ValueError:
        await update.message.reply_text("❌ Неверный формат! Пример: 5793502641_100")
        
async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда вывода средств"""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name
    
    if not context.args:
        await update.message.reply_text(
            "💸 <b>Вывод средств</b>\n\n"
            "Использование: /withdraw <сумма>\n"
            "Пример: /withdraw 100\n\n"
            "После запроса свяжитесь с админом для подтверждения",
            parse_mode='HTML'
        )
        return
    
    try:
        amount = int(context.args[0])
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть положительной!")
            return
            
        if amount > user_currency.get(user_id, 0):
            await update.message.reply_text("❌ Недостаточно средств!")
            return
        
        # Формируем команду для админа
        admin_command = f"/confirm_withdraw {user_id}_{amount}"
        
        await update.message.reply_text(
            f"💸 <b>Запрос на вывод создан!</b>\n\n"
            f"• Сумма: {amount} монет\n"
            f"• Ваш ID: {user_id}\n"
            f"• Канал выводов: @YouBot_conclusions\n\n"
            f"<b>Команда для админа:</b>\n"
            f"<code>{admin_command}</code>\n\n"
            "Отправьте эту команду админу для подтверждения",
            parse_mode='HTML'
        )
        
    except ValueError:
        await update.message.reply_text("❌ Введите корректную сумму!")
        



async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий кнопок"""
    query = update.callback_query
    await query.answer()  # Подтверждаем нажатие
    
    data = query.data
    user_id = query.from_user.id
    print(f"🟢 Нажата кнопка: {data} пользователем: {user_id}")  # Отладка
    
    # Проверяем права доступа для кнопок канала
    if data.startswith("confirm_channel_") or data.startswith("reject_channel_"):
        if user_id != OWNER_ID:
            await query.answer("❌ Только администратор может подтверждать операции!", show_alert=True)
            return
    
    if data.startswith("send_to_channel_"):
        # Извлекаем данные
        parts = data.split('_')
        target_id = int(parts[3])
        amount = int(parts[4])
        
        # Получаем информацию о пользователе
        try:
            user = await context.bot.get_chat(target_id)
            username = f"@{user.username}" if user.username else user.first_name
        except:
            username = f"ID: {target_id}"
        
        # Клавиатура для подтверждения в канале
        channel_keyboard = [
            [InlineKeyboardButton("✅ ПОДТВЕРДИТЬ НАЧИСЛЕНИЕ", callback_data=f"confirm_channel_{target_id}_{amount}")],
            [InlineKeyboardButton("❌ ОТКЛОНИТЬ", callback_data=f"reject_channel_{target_id}_{amount}")]
        ]
        channel_markup = InlineKeyboardMarkup(channel_keyboard)
        
        try:
            # Отправляем сообщение в канал
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=f"💸 <b>ЗАПРОС НА НАЧИСЛЕНИЕ СРЕДСТВ</b>\n\n"
                     f"👤 Пользователь: {username}\n"
                     f"🆔 ID: <code>{target_id}</code>\n"
                     f"💰 Сумма: {amount} монет\n"
                     f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                     f"<i>Для подтверждения нажмите кнопку ниже</i>",
                reply_markup=channel_markup,
                parse_mode='HTML'
            )
            
            await query.edit_message_text(
                f"✅ <b>Запрос отправлен в канал!</b>\n\n"
                f"👤 Пользователь: {username}\n"
                f"💰 Сумма: {amount} монет\n\n"
                f"Ожидайте подтверждения...",
                parse_mode='HTML'
            )
            
        except Exception as e:
            print(f"❌ Ошибка отправки в канал: {e}")
            await query.edit_message_text(
                f"❌ <b>Ошибка отправки в канал!</b>\n\n"
                f"Проверьте настройки бота и канала.\n"
                f"Ошибка: {e}",
                parse_mode='HTML'
            )
    
    elif data.startswith("confirm_channel_"):
        # Подтверждение из канала
        parts = data.split('_')
        target_id = int(parts[2])
        amount = int(parts[3])
        
        # НАЧИСЛЕНИЕ вместо списания!
        user_currency[target_id] = user_currency.get(target_id, 0) + amount
        save_user_data()
        
        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"✅ <b>Начисление средств подтверждено!</b>\n\n"
                     f"💰 Сумма: +{amount} монет\n"
                     f"📋 Статус: Обработано администратором\n\n"
                     f"Новый баланс: {user_currency.get(target_id, 0)} монет",
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"❌ Не удалось уведомить пользователя: {e}")
        
        # Отправляем фото с подтверждением в канал
        try:
            # Создаем текст для фото
            caption = (f"✅ <b>НАЧИСЛЕНИЕ ПОДТВЕРЖДЕНО</b>\n\n"
                      f"👤 Пользователь: ID {target_id}\n"
                      f"💰 Сумма: +{amount} монет\n"
                      f"🕒 Подтверждено: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                      f"<i>Средства успешно начислены</i>")
            
            # Отправляем фото с подтверждением
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=open('payment_image.png', 'rb'),  # Фото для подтверждения
                caption=caption,
                parse_mode='HTML'
            )
            
        except Exception as e:
            print(f"❌ Ошибка отправки фото подтверждения: {e}")
            # Если не удалось отправить фото, отправляем текстовое сообщение
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=caption,
                parse_mode='HTML'
            )
        
        # Удаляем оригинальное сообщение с кнопками или редактируем его
        try:
            await query.delete_message()
        except:
            try:
                await query.edit_message_text(
                    f"✅ <b>ОПЕРАЦИЯ ЗАВЕРШЕНА</b>\n\n"
                    f"Начисление подтверждено и отправлено в канал",
                    parse_mode='HTML'
                )
            except:
                pass
    
    elif data.startswith("reject_channel_"):
        # Отклонение из канала
        parts = data.split('_')
        target_id = int(parts[2])
        amount = int(parts[3])
        
        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"❌ <b>Начисление средств отклонено</b>\n\n"
                     f"💰 Сумма: {amount} монет\n"
                     f"📋 Статус: Отклонено администратором\n\n"
                     f"Обратитесь к администратору для уточнения причин.",
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"❌ Не удалось уведомить пользователя: {e}")
        
        # Отправляем фото с отклонением в канал
        try:
            # Создаем текст для фото отклонения
            caption = (f"❌ <b>НАЧИСЛЕНИЕ ОТКЛОНЕНО</b>\n\n"
                      f"👤 Пользователь: ID {target_id}\n"
                      f"💰 Сумма: {amount} монет\n"
                      f"🕒 Отклонено: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
            
            # Отправляем фото с отклонением
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=open('payments_image.png', 'rb'),  # Фото для отклонения
                caption=caption,
                parse_mode='HTML'
            )
            
        except Exception as e:
            print(f"❌ Ошибка отправки фото отклонения: {e}")
            # Если не удалось отправить фото, отправляем текстовое сообщение
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=caption,
                parse_mode='HTML'
            )
        
        # Удаляем оригинальное сообщение с кнопками или редактируем его
        try:
            await query.delete_message()
        except:
            try:
                await query.edit_message_text(
                    f"❌ <b>ОПЕРАЦИЯ ОТКЛОНЕНА</b>\n\n"
                    f"Начисление отклонено и отправлено в канал",
                    parse_mode='HTML'
                )
            except:
                pass
    
    elif data == "cancel_withdraw":
        await query.edit_message_text("❌ Вывод отменен!")
        
    
    balance = user_currency.get(user_id, 0)
    diamonds = user_diamonds.get(user_id, 0)
    
    if data == "get_reward":
        await give_reward_callback(query, context)
    
    elif data == "check_balance":
        await query.edit_message_text(
            f"💰 <b>Ваш баланс:</b>\n"
            f"• Монеты: {balance:,}\n"
            f"• Алмазы: {diamonds}\n\n"
            f"Используйте /give_reward для получения награды",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎁 ПОЛУЧИТЬ НАГРАДУ", callback_data="get_reward")],
                [InlineKeyboardButton("📋 ИНФО О НАГРАДЕ", callback_data="reward_info")]
            ])
        )
    
    elif data == "reward_info":
        # Проверяем доступность награды
        reward_available = True
        if user_id in last_reward:
            last_time = datetime.fromisoformat(last_reward[user_id])
            if datetime.now() - last_time < timedelta(hours=REWARD_COOLDOWN_HOURS):
                reward_available = False
        
        status = "✅ Доступна" if reward_available else "⏳ Завтра"
        
        await query.edit_message_text(
            f"🎁 <b>Ежедневная награда</b>\n\n"
            f"💰 <b>Размер награды:</b> {REWARD_AMOUNT} монет\n"
            f"🕒 <b>Периодичность:</b> каждые 24 часа\n"
            f"📊 <b>Статус:</b> {status}\n\n"
            f"📝 <b>Условие:</b> Добавить в описание профиля:\n"
            f"<code>{REQUIRED_BOT_USERNAME}</code>\n\n"
            f"💰 <b>Ваш баланс:</b>\n"
            f"• Монеты: {balance:,}\n"
            f"• Алмазы: {diamonds}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎁 ПОЛУЧИТЬ НАГРАДУ", callback_data="get_reward")],
                [InlineKeyboardButton("💰 БАЛАНС", callback_data="check_balance")]
            ])
        )

async def give_reward_callback(query, context):
    """Обработчик награды через кнопку"""
    user_id = str(query.from_user.id)
    diamonds = user_diamonds.get(user_id, 0)
    
    # Проверяем кулдаун
    if user_id in last_reward:
        last_time = datetime.fromisoformat(last_reward[user_id])
        if datetime.now() - last_time < timedelta(hours=REWARD_COOLDOWN_HOURS):
            next_time = last_time + timedelta(hours=REWARD_COOLDOWN_HOURS)
            wait_time = next_time - datetime.now()
            hours_left = int(wait_time.total_seconds() // 3600)
            minutes_left = int((wait_time.total_seconds() % 3600) // 60)
            
            await query.edit_message_text(
                f"⏳ Вы уже получали награду сегодня!\n\n"
                f"🕒 Следующая награда через: {hours_left}ч {minutes_left}м\n"
                f"💰 Награда: {REWARD_AMOUNT} монет",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 БАЛАНС", callback_data="check_balance")],
                    [InlineKeyboardButton("📋 ИНФО", callback_data="reward_info")]
                ])
            )
            return
    
    try:
        # Получаем информацию о пользователе
        user = await context.bot.get_chat(user_id)
        
        # Проверяем описание профиля (bio)
        if user.bio and REQUIRED_BOT_USERNAME.lower() in user.bio.lower():
            # Начисляем награду
            if user_id not in user_currency:
                user_currency[user_id] = 0
            user_currency[user_id] += REWARD_AMOUNT
            
            # Обновляем время последней награды
            last_reward[user_id] = datetime.now().isoformat()
            save_user_datas()
            
            await query.edit_message_text(
                f"✅ <b>Награда получена!</b>\n\n"
                f"💰 +{REWARD_AMOUNT} монет\n"
                f"💳 Новый баланс: {user_currency[user_id]:,} монет\n"
                f"💎 Алмазов: {diamonds}\n\n"
                f"🎯 Следующая награда через 24 часа",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 БАЛАНС", callback_data="check_balance")],
                    [InlineKeyboardButton("📋 ИНФО", callback_data="reward_info")]
                ])
            )
        else:
            await query.edit_message_text(
                f"❌ <b>Условие не выполнено!</b>\n\n"
                f"📝 Добавьте в описание профиля:\n"
                f"<code>{REQUIRED_BOT_USERNAME}</code>\n\n"
                f"💰 Награда: {REWARD_AMOUNT} монет каждые 24 часа\n\n"
                f"💰 <b>Текущий баланс:</b>\n"
                f"• Монеты: {user_currency.get(user_id, 0):,}\n"
                f"• Алмазы: {diamonds}",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 ПРОВЕРИТЬ СНОВА", callback_data="get_reward")],
                    [InlineKeyboardButton("📋 ИНФО", callback_data="reward_info")]
                ])
            )
            
    except Exception as e:
        print(f"Ошибка при проверке профиля: {e}")
        await query.edit_message_text(
            "❌ <b>Ошибка при проверке профиля!</b>\n\n"
            "Попробуйте позже.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 ПОВТОРИТЬ", callback_data="get_reward")],
                [InlineKeyboardButton("💰 БАЛАНС", callback_data="check_balance")]
            ])
        )
        
        

        
# Добавляем в существующий код
REWARD_DATA_FILE = "user_datas.json"
REQUIRED_BOT_USERNAME = "@byCopsBot_bot"
REWARD_AMOUNT = 1000
REWARD_COOLDOWN_HOURS = 24

# Загрузка данных о наградах
def load_reward_data():
    if os.path.exists(REWARD_DATA_FILE):
        with open(REWARD_DATA_FILE, 'r') as f:
            data = json.load(f)
            if 'last_reward' in data:
                return data['last_reward']
    return {}

# Сохранение данных о наградах
def save_reward_data():
    data = {'last_reward': last_reward}
    with open(REWARD_DATA_FILE, 'w') as f:
        json.dump(data, f)

# Глобальная переменная для времени наград
last_reward = load_reward_data()

async def give_reward_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /give_reward для получения награды"""
    user_id = str(update.message.from_user.id)
    
    # Проверяем кулдаун
    if user_id in last_reward:
        last_time = datetime.fromisoformat(last_reward[user_id])
        if datetime.now() - last_time < timedelta(hours=REWARD_COOLDOWN_HOURS):
            next_time = last_time + timedelta(hours=REWARD_COOLDOWN_HOURS)
            wait_time = next_time - datetime.now()
            hours_left = int(wait_time.total_seconds() // 3600)
            minutes_left = int((wait_time.total_seconds() % 3600) // 60)
            
            await update.message.reply_text(
                f"⏳ Вы уже получали награду сегодня!\n\n"
                f"🕒 Следующая награда через: {hours_left}ч {minutes_left}м\n"
                f"💰 Награда: {REWARD_AMOUNT} монет\n\n"
                f"📝 Условие: добавить {REQUIRED_BOT_USERNAME} в описание профиля"
            )
            return
    
    try:
        # Получаем информацию о пользователе
        user = await context.bot.get_chat(user_id)
        
        # Проверяем описание профиля (bio)
        if user.bio and REQUIRED_BOT_USERNAME.lower() in user.bio.lower():
            # Начисляем награду (используем вашу существующую структуру users_info)
            if user_id not in users_info:
                users_info[user_id] = {'currency': 0}
            elif 'currency' not in users_info[user_id]:
                users_info[user_id]['currency'] = 0
                
            users_info[user_id]['currency'] += REWARD_AMOUNT
            save_data()  # Ваша существующая функция сохранения
            
            # Обновляем время последней награды
            last_reward[user_id] = datetime.now().isoformat()
            save_reward_data()
            
            await update.message.reply_text(
                f"✅ <b>Награда получена!</b>\n\n"
                f"💰 +{REWARD_AMOUNT} монет\n"
                f"💳 Новый баланс: {users_info[user_id]['currency']:,} монет\n\n"
                f"🎯 Следующая награда через 24 часа\n"
                f"📝 Условие: {REQUIRED_BOT_USERNAME} должен оставаться в описании профиля",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                f"❌ <b>Условие не выполнено!</b>\n\n"
                f"📝 Для получения награды добавьте в описание вашего профиля:\n"
                f"<code>{REQUIRED_BOT_USERNAME}</code>\n\n"
                f"💰 Награда: {REWARD_AMOUNT} монет каждые 24 часа",
                parse_mode='HTML'
            )
            
    except Exception as e:
        print(f"Ошибка при проверке профиля: {e}")
        await update.message.reply_text(
            "❌ <b>Ошибка при проверке профиля!</b>\n\n"
            "Попробуйте позже или обратитесь к администратору.",
            parse_mode='HTML'
        )
        

    
async def help_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды помощи по социальным функциям"""
    allowed, message = await smart_security_check(update, "help_user")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    social_text = (
       "<b>Добро Пожаловать</b>\n"
       "🌐 <b>Социальные Данные</b>\n"
       "• Подписаться на пользователя\n"
       "/follow <user_id>\n\n"
       "• Отписаться от пользователя\n"
       "/unfollow <user_id>\n\n"
       "• Поставить лайк пользователю\n"
       "/like <user_id>\n\n"
       "• Поставить дизлайк пользователю\n"
       "/dislike <user_id>\n\n"
       "• Проверить социальный статус\n"
       "/social_status"
    )
    
    await update.message.reply_text(social_text, parse_mode='HTML')
    
async def give_follow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Проверка, что только ты можешь передавать подписчиков
    if user_id != OWNER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    # Разбор команды
    if len(context.args) != 2:
        await update.message.reply_text("❗ Используйте команду в формате: /give_follow <ID пользователя> <Количество подписчиков>")
        return

    targetf_user_id = int(context.args[0])
    amount = int(context.args[1])

    # Проверка, что количество подписчиков больше 0
    if amount <= 0:
        await update.message.reply_text("❗ Количество подписчиков должно быть больше 0.")
        return

    # Добавляем подписчиков пользователю
    target_id_str = str(targetf_user_id)
    
    # Инициализируем если нужно
    if target_id_str not in user_followers:
        user_followers[target_id_str] = []
    
    # Добавляем "виртуальных" подписчиков
    for i in range(amount):
        fake_follower_id = f"fake_follower_{target_id_str}_{i}_{datetime.now().timestamp()}"
        user_followers[target_id_str].append(fake_follower_id)
    
    # Сохраняем данные
    save_social_data()  # ← ОТСТУП ИСПРАВЛЕН

    await update.message.reply_text(
        f"🎉 Вы добавили {amount} подписчиков пользователю {targetf_user_id}.\n"
        f"Текущее количество подписчиков: {len(user_followers[target_id_str])} 👥"
    )
    
# Команда для добавления лайков пользователю
async def add_likes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    # Проверка, что только владелец может добавлять лайки
    if user_id != OWNER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    # Разбор команды: /add_likes <user_id> <количество>
    if len(context.args) != 2:
        await update.message.reply_text("❌ Используйте: /add_likes <user_id> <количество>")
        return

    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        target_id_str = str(target_id)
        
        # Проверка количества
        if amount <= 0:
            await update.message.reply_text("❌ Количество лайков должно быть больше 0")
            return
            
        if amount > 1000000:  # Максимум 1 млн лайков за раз
            await update.message.reply_text("❌ Максимальное количество - 1,000,000 лайков за раз")
            return

        # Добавляем лайки через "фейковых" пользователей
        current_likes = sum(1 for user_likes_list in user_likes.values() if target_id_str in user_likes_list)
        
        for i in range(amount):
            fake_user_id = f"fake_like_{target_id_str}_{i}_{datetime.now().timestamp()}"
            if fake_user_id not in user_likes:
                user_likes[fake_user_id] = []
            user_likes[fake_user_id].append(target_id_str)
        
        # Сохраняем данные
        save_social_data()
        
        # Получаем информацию о пользователе
        try:
            user = await context.bot.get_chat(target_id)
            username = f"@{user.username}" if user.username else user.first_name
        except:
            username = f"ID: {target_id}"
        
        new_likes_count = current_likes + amount
        
        await update.message.reply_text(
            f"✅ <b>Лайки добавлены!</b>\n\n"
            f"• <b>Пользователь:</b> {username}\n"
            f"• <b>ID:</b> <code>{target_id}</code>\n"
            f"• <b>Добавлено лайков:</b> {amount:,} ❤️\n"
            f"• <b>Было лайков:</b> {current_likes:,}\n"
            f"• <b>Стало лайков:</b> {new_likes_count:,}\n\n"
            f"⚡ <i>Лайки успешно начислены пользователю</i>",
            parse_mode='HTML'
        )
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Используйте: /add_likes <user_id> <количество>")

# Команда для удаления лайков пользователю
async def remove_likes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Эта команда доступна только владельцу бота.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("❌ Используйте: /remove_likes <user_id> <количество>")
        return

    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        target_id_str = str(target_id)
        
        if amount <= 0:
            await update.message.reply_text("❌ Количество лайков должно быть больше 0")
            return
            
        # Получаем текущее количество лайков
        current_likes = sum(1 for user_likes_list in user_likes.values() if target_id_str in user_likes_list)
        
        if amount > current_likes:
            await update.message.reply_text(f"❌ Нельзя удалить больше лайков чем есть. У пользователя всего {current_likes} лайков")
            return
        
        # Удаляем лайки (удаляем фейковые сначала)
        removed_count = 0
        for fake_user_id in list(user_likes.keys()):
            if fake_user_id.startswith(f"fake_like_{target_id_str}_") and target_id_str in user_likes[fake_user_id]:
                user_likes[fake_user_id].remove(target_id_str)
                removed_count += 1
                if removed_count >= amount:
                    break
        
        # Если нужно удалить еще, удаляем из обычных
        if removed_count < amount:
            remaining = amount - removed_count
            for user_id_str in list(user_likes.keys()):
                if target_id_str in user_likes[user_id_str]:
                    user_likes[user_id_str].remove(target_id_str)
                    remaining -= 1
                    if remaining <= 0:
                        break
        
        # Сохраняем данные
        save_social_data()
        
        # Получаем информацию о пользователе
        try:
            user = await context.bot.get_chat(target_id)
            username = f"@{user.username}" if user.username else user.first_name
        except:
            username = f"ID: {target_id}"
        
        new_likes_count = current_likes - amount
        
        await update.message.reply_text(
            f"✅ <b>Лайки удалены!</b>\n\n"
            f"• <b>Пользователь:</b> {username}\n"
            f"• <b>ID:</b> <code>{target_id}</code>\n"
            f"• <b>Удалено лайков:</b> {amount:,} ❤️\n"
            f"• <b>Было лайков:</b> {current_likes:,}\n"
            f"• <b>Стало лайков:</b> {new_likes_count:,}\n\n"
            f"⚡ <i>Лайки успешно удалены у пользователя</i>",
            parse_mode='HTML'
        )
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Используйте: /remove_likes <user_id> <количество>")

# Команда для установки точного количества лайков
async def set_likes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if user_id != OWNER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("❌ Используйте: /set_likes <user_id> <количество>")
        return

    try:
        target_id = int(context.args[0])
        target_amount = int(context.args[1])
        target_id_str = str(target_id)
        
        if target_amount < 0:
            await update.message.reply_text("❌ Количество лайков не может быть отрицательным")
            return
            
        if target_amount > 100000000:  # Максимум 100 млн лайков
            await update.message.reply_text("❌ Максимальное количество - 100,000,000 лайков")
            return

        # Получаем текущее количество лайков
        current_likes = sum(1 for user_likes_list in user_likes.values() if target_id_str in user_likes_list)
        
        if target_amount == current_likes:
            await update.message.reply_text("✅ У пользователя уже такое количество лайков")
            return
        
        # Очищаем все текущие лайки
        for user_id_str in list(user_likes.keys()):
            if target_id_str in user_likes[user_id_str]:
                user_likes[user_id_str].remove(target_id_str)
        
        # Добавляем нужное количество фейковых лайков
        if target_amount > 0:
            for i in range(target_amount):
                fake_user_id = f"fake_like_{target_id_str}_{i}_{datetime.now().timestamp()}"
                if fake_user_id not in user_likes:
                    user_likes[fake_user_id] = []
                user_likes[fake_user_id].append(target_id_str)
        
        # Сохраняем данные
        save_social_data()
        
        # Получаем информацию о пользователе
        try:
            user = await context.bot.get_chat(target_id)
            username = f"@{user.username}" if user.username else user.first_name
        except:
            username = f"ID: {target_id}"
        
        await update.message.reply_text(
            f"✅ <b>Количество лайков установлено!</b>\n\n"
            f"• <b>Пользователь:</b> {username}\n"
            f"• <b>ID:</b> <code>{target_id}</code>\n"
            f"• <b>Было лайков:</b> {current_likes:,}\n"
            f"• <b>Установлено:</b> {target_amount:,} ❤️\n\n"
            f"⚡ <i>Количество лайков успешно изменено</i>",
            parse_mode='HTML'
        )
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Используйте: /set_likes <user_id> <количество>")
    
    # Функция для проверки, является ли пользователь владельцем
async def is_owner(update: Update) -> bool:
    return update.message.from_user.id == OWNER_ID

# Команда для вывода инструкций только для создателя бота
async def help_creator(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    await update.message.reply_text(
        f'<b>Добро Пожаловать</b>\n\n'
        f'💬 <b>Чатовые Команды:</b>\n'
        f'• Забанить пользователя\n'
        f'/ban <user_id>\n\n'
        f'• Разбанить пользователя\n'
        f'/unban\n\n'
        f'• Замутить пользователя\n'
        f'/mute\n\n'
        f'• Размутить пользователя\n'
        f'/unmute\n\n'
        f'• Кикнуть пользователя\n'
        f'/kick\n\n'
        f'• Стать админом чата\n'
        f'/make_me_admin\n\n'
        f'• Сделать пользователя админом чата\n'
        f'/promote_to_admin\n\n'
        f'📌 <b>Пользовательские Команды:</b>\n'
        f'• Верифицировать пользователя\n'
        f'/verify\n\n'
        f'• Заблокировать пользователя бота\n'
        f'/block\n\n'
        f'• Разблокировать пользователя бота\n'
        f'/unblock\n\n'
        f'• Сделать пользователя админом бота\n'
        f'/promote\n\n'
        f'• Разжаловать пользователя\n'
        f'/demote\n\n'
        f'• Список заблокированных пользователей\n'
        f'/blocked_users\n\n'
        f'• Писать сообщения от имени бота\n'
        f'/send_message\n\n'
        f'• Полный экспорт участников\n'
        f'/export_members\n\n'
        f'• Упрощённый экспорт участников\n'
        f'/export_simple\n\n'
        f'• Проврека прав бота\n'
        f'/check_rights\n\n'
        f'🎮 <b>Игровые Команды:</b>\n'
        f'• Забрать монеты у пользователя\n'
        f'/take_coins\n\n'
        f'• Дать монеты пользователю\n'
        f'/give_coins\n\n'
        f'• Дать алмазы пользователю\n'
        f'/give_diamond\n\n'
        f'• Изменить статус пользователю\n'
        f'/change_status\n\n'
        f'• Изменить статус\n'
        f'/change_my_status',
    reply_markup=reply_markup,
    parse_mode='HTML'
    ) 
    
    
    
    
        # Функция для проверки, является ли пользователь владельцем
async def is_owner(update: Update) -> bool:
    return update.message.from_user.id == OWNER_ID

# Команда для вывода просмотра/измениния статуса только для создателя бота
async def change_my_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return
    
    # Текст для отображения
    help_text = (
        '𝗧𝗢 𝗧𝗛𝗘 𝗕𝗢𝗧 𝗖𝗥𝗘𝗔𝗧𝗢𝗥\n'
        '𝐂𝐇𝐀𝐍𝐆𝐄 𝐒𝐓𝐀𝐓𝐔𝐒\n'
        'Статус DONATER🍷\n'
        '/change_status_donater\n\n'
        'Статус KILLER☠️\n'
        '/change_status_killer\n\n'
        'Статус GOLD🏆\n'
        '/change_status_gold\n\n'
        'Статус LEGEND💎\n'
        '/change_status_legend\n\n'
        'Статус ADMIN💰\n'
        '/change_status_admin\n\n'
        'Статус CREATOR🍭\n'
        '/change_status_creator\n\n'
        'Статус "НовыйСтатус"\n'
        '/change_status_name'
    
    )
    await update.message.reply_text(help_text)

async def change_status_donater(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    user_data[OWNER_ID] = {"status": "DONATER🍷"}
    await update.message.reply_text("Статус на 'DONATER🍷' изменён.")    


async def change_status_killer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    user_data[OWNER_ID] = {"status": "KILLER☠️"}
    await update.message.reply_text("Статус на 'KILLER☠️' изменён.")  


async def change_status_gold(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    user_data[OWNER_ID] = {"status": "GOLD🏆"}
    await update.message.reply_text("Статус на 'GOLD🏆' изменён.")  


async def change_status_legend(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    user_data[OWNER_ID] = {"status": "LEGEND💎"}
    await update.message.reply_text("Статус на 'LEGEND💎' изменён.")  


async def change_status_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    user_data[OWNER_ID] = {"status": "ADMIN💰"}
    await update.message.reply_text("Статус на 'ADMIN💰' изменён.")  


async def change_status_creator(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    user_data[OWNER_ID] = {"status": "CREATOR🍭"}
    await update.message.reply_text("Статус на 'CREATOR🍭' изменён.")
    
    
async def change_status_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    if not context.args:
        await update.message.reply_text("Пожалуйста, укажи свой статус после команды.\n\nПример:\n`/change_status_name НовыйСтатус`", parse_mode="Markdown")
        return

    custom_status = " ".join(context.args)
    user_data[OWNER_ID] = {"status": custom_status}
    await update.message.reply_text(f"Статус изменён на: *{custom_status}*", parse_mode="Markdown")
    
    # Команда передачи монет
async def give_coins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Проверка, что только ты можешь передавать монеты
    if user_id != OWNER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    # Разбор команды (например, "/givecoins <id> <количество>")
    if len(context.args) != 2:
        await update.message.reply_text("❗ Используйте команду в формате: /give_coins <ID пользователя> <Количество монет>")
        return

    target_user_id = int(context.args[0])
    amount = int(context.args[1])

    # Проверка, что количество монет больше 0
    if amount <= 0:
        await update.message.reply_text("❗ Количество монет должно быть больше 0.")
        return

    # Добавляем монеты другому пользователю
    user_currency.setdefault(target_user_id, 0)
    user_currency[target_user_id] += amount
    
     # Сохраняем данные
    save_user_data()
    

    await update.message.reply_text(
        f"🎉 Вы передали {amount} 🌕 пользователю {target_user_id}.\nТекущий баланс пользователя: {user_currency[target_user_id]} 🌕"
    )
    
    # Команда передачи монет
async def give_diamond(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Проверка, что только ты можешь передавать монеты
    if user_id != OWNER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    # Разбор команды (например, "/givecoins <id> <количество>")
    if len(context.args) != 2:
        await update.message.reply_text("❗ Используйте команду в формате: /give_diamond <ID пользователя> <Количество монет>")
        return

    target_user_id = int(context.args[0])
    amount = int(context.args[1])

    # Проверка, что количество монет больше 0
    if amount <= 0:
        await update.message.reply_text("❗ Количество монет должно быть больше 0.")
        return

    # Добавляем монеты другому пользователю
    user_diamond.setdefault(target_user_id, 0)
    user_diamond[target_user_id] += amount

    await update.message.reply_text(
        f"🎉 Вы передали {amount} 💎 пользователю {target_user_id}.\nТекущий баланс пользователя: {user_diamond[target_user_id]} 💎"
    )
    
# Команда для изменения статуса
async def change_status(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    if not await is_owner(update):
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("Использование: /changestatus <user_id> <status>")
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID пользователя должен быть числом.")
        return

    new_status = context.args[1]

    # Меняем статус
    user_status[target_user_id] = new_status
    await update.message.reply_text(f"Статус пользователя {target_user_id} изменён на {new_status}.")
    
   

    # Получаем ID пользователя
    user_id = context.args[0]

    # Проверяем, есть ли этот пользователь в словаре с паролями
    if user_id in user_passwords:
        del user_passwords[user_id]  # Удаляем пароль пользователя
        await update.message.reply_text(f"Пароль пользователя {user_id} был сброшен.")
    else:
        await update.message.reply_text(f"Пользователь с ID {user_id} не найден.")
        
        
  

        
           # Функция для обработки команды /speakAI
async def speakAI(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "speakAi")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
        
    await update.message.reply_text(
        '𝗔𝗜\n'
        '🟢 Начать разговор\n'
        '/ai_chat\n\n'
        '🔴 Закончить разговор\n'
        '/ai_stop'
    
    ) 
    

        
        
# Файл для хранения базы знаний ИИ
AI_KNOWLEDGE_FILE = "ai_knowledge.json"
# Файл для хранения истории обучения
AI_TRAINING_HISTORY = "ai_training_history.json"
# Файл для хранения активных диалогов
AI_ACTIVE_CHATS = "ai_active_chats.json"

class SimpleAI:
    def __init__(self):
        self.knowledge = defaultdict(list)
        self.training_history = []
        self.active_chats = {}  # {user_id: True/False}
        self.load_knowledge()
        self.load_training_history()
        self.load_active_chats()
        self.load_school_knowledge()  # Загружаем школьные знания
    
    def load_school_knowledge(self):
        """Загрузка школьных знаний по всем предметам"""
        # Математика
        math_knowledge = {
            'теорема пифагора': 'В прямоугольном треугольнике квадрат гипотенузы равен сумме квадратов катетов: a² + b² = c²',
            'площадь круга': 'Площадь круга: S = πr², где π ≈ 3.14, r - радиус',
            'периметр круга': 'Длина окружности: C = 2πr',
            'площадь треугольника': 'Площадь треугольника: S = (a × h) / 2, где a - основание, h - высота',
            'объем шара': 'Объем шара: V = (4/3)πr³',
            'квадратное уравнение': 'ax² + bx + c = 0, дискриминант D = b² - 4ac, корни: x = (-b ± √D)/2a',
            'синус': 'sin(α) = противолежащий катет / гипотенуза',
            'косинус': 'cos(α) = прилежащий катет / гипотенуза',
            'тангенс': 'tg(α) = sin(α) / cos(α)',
            'логарифм': 'logₐb = c, где aᶜ = b',
            'производная': 'Производная функции f(x) показывает скорость изменения функции',
            'интеграл': 'Интеграл - это площадь под кривой функции'
        }
        
        # Физика
        physics_knowledge = {
            'закон ньютона': 'F = ma (сила равна массе на ускорение)',
            'закон ома': 'I = U/R (сила тока равна напряжению деленному на сопротивление)',
            'закон сохранения энергии': 'Энергия не создается и не уничтожается, а только преобразуется',
            'скорость света': 'c ≈ 300 000 км/с',
            'ускорение свободного падения': 'g ≈ 9.8 м/с²',
            'плотность': 'ρ = m/V (плотность равна массе деленной на объем)',
            'работа': 'A = F × s (работа равна силе на путь)',
            'мощность': 'P = A/t (мощность равна работе деленной на время)',
            'закон архимеда': 'На тело, погруженное в жидкость, действует выталкивающая сила',
            'кинетическая энергия': 'Eк = mv²/2',
            'потенциальная энергия': 'Eп = mgh'
        }
        
        # Химия
        chemistry_knowledge = {
            'вода формула': 'H₂O',
            'поваренная соль': 'NaCl',
            'углекислый газ': 'CO₂',
            'серная кислота': 'H₂SO₄',
            'соляная кислота': 'HCl',
            'аммиак': 'NH₃',
            'метан': 'CH₄',
            'этанол': 'C₂H₅OH',
            'периодическая система': 'Таблица Менделеева содержит 118 элементов',
            'валентность': 'Валентность - это способность атомов соединяться с другими атомами',
            'моль': '1 моль = 6.022 × 10²³ частиц (число Авогадро)'
        }
        
        # География
        geography_knowledge = {
            'столица россии': 'Москва',
            'столица франции': 'Париж',
            'столица германии': 'Берлин',
            'столица китая': 'Пекин',
            'столица сша': 'Вашингтон',
            'самая длинная река': 'Нил (6650 км) или Амазонка (6400 км)',
            'самое глубокое озеро': 'Байкал (1642 м)',
            'самая высокая гора': 'Эверест (8848 м)',
            'крупнейший океан': 'Тихий океан',
            'пустыня сахара': 'Самая большая пустыня в мире',
            'антарктида': 'Самый холодный континент'
        }
        
        # История
        history_knowledge = {
            'год крещения руси': '988 год',
            'год великой отечественной': '1941-1945',
            'первый космонавт': 'Юрий Гагарин (1961 год)',
            'вторая мировая война': '1939-1945',
            'революция 1917': 'Октябрьская революция в России',
            'петр первый': 'Петр Великий, основатель Санкт-Петербурга',
            'иван грозный': 'Первый царь всея Руси',
            'наполеон': 'Французский император, напал на Россию в 1812 году',
            'древний рим': 'Основан в 753 году до н.э.',
            'древняя греция': 'Колыбель западной цивилизации'
        }
        
        # Литература
        literature_knowledge = {
            'автор война и мир': 'Лев Толстой',
            'пушкин годы жизни': '1799-1837',
            'гоголь годы жизни': '1809-1852',
            'достоевский': 'Федор Достоевский, автор "Преступления и наказания"',
            'чехов': 'Антон Чехов, мастер короткого рассказа',
            'шекспир': 'Уильям Шекспир, английский драматург',
            'евгений онегин': 'Роман в стихах Пушкина',
            'мертвые души': 'Поэма Гоголя',
            'преступление и наказание': 'Роман Достоевского',
            'анна каренина': 'Роман Толстого'
        }
        
        # Биология
        biology_knowledge = {
            'фотосинтез': 'Процесс преобразования света в энергию растениями',
            'днк': 'Дезоксирибонуклеиновая кислота, носитель генетической информации',
            'клетка': 'Основная единица жизни',
            'митоз': 'Процесс деления клеток',
            'дарвин': 'Чарльз Дарвин, теория эволюции',
            'генетика': 'Наука о наследственности',
            'виды тканей': 'Эпителиальная, соединительная, мышечная, нервная',
            'системы органов': 'Пищеварительная, дыхательная, кровеносная и др.',
            'вирусы': 'Неcellular infectious agents',
            'бактерии': 'Одноклеточные prokaryotic organisms'
        }
        
        # Добавляем все знания в базу
        all_knowledge = {
            **math_knowledge,
            **physics_knowledge,
            **chemistry_knowledge,
            **geography_knowledge,
            **history_knowledge,
            **literature_knowledge,
            **biology_knowledge
        }
        
        for pattern, response in all_knowledge.items():
            if pattern not in self.knowledge:
                self.knowledge[pattern] = [response]
    
    def load_knowledge(self):
        """Загрузка базы знаний ИИ"""
        try:
            if os.path.exists(AI_KNOWLEDGE_FILE):
                with open(AI_KNOWLEDGE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.knowledge = defaultdict(list, data)
        except Exception as e:
            print(f"Ошибка загрузки знаний ИИ: {e}")
            self.knowledge = defaultdict(list)
    
    def save_knowledge(self):
        """Сохранение базы знаний ИИ"""
        try:
            with open(AI_KNOWLEDGE_FILE, 'w', encoding='utf-8') as f:
                json.dump(dict(self.knowledge), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения знаний ИИ: {e}")
    
    def load_training_history(self):
        """Загрузка истории обучения"""
        try:
            if os.path.exists(AI_TRAINING_HISTORY):
                with open(AI_TRAINING_HISTORY, 'r', encoding='utf-8') as f:
                    self.training_history = json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки истории обучения: {e}")
            self.training_history = []
    
    def save_training_history(self):
        """Сохранение истории обучения"""
        try:
            with open(AI_TRAINING_HISTORY, 'w', encoding='utf-8') as f:
                json.dump(self.training_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения истории обучения: {e}")
    
    def load_active_chats(self):
        """Загрузка активных диалогов"""
        try:
            if os.path.exists(AI_ACTIVE_CHATS):
                with open(AI_ACTIVE_CHATS, 'r', encoding='utf-8') as f:
                    self.active_chats = json.load(f)
        except Exception as e:
            print(f"Ошибка загрузки активных диалогов: {e}")
            self.active_chats = {}
    
    def save_active_chats(self):
        """Сохранение активных диалогов"""
        try:
            with open(AI_ACTIVE_CHATS, 'w', encoding='utf-8') as f:
                json.dump(self.active_chats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения активных диалогов: {e}")
    
    def is_chat_active(self, user_id):
        """Проверка активен ли диалог с пользователем"""
        return self.active_chats.get(str(user_id), False)
    
    def start_chat(self, user_id):
        """Начать диалог с пользователем"""
        self.active_chats[str(user_id)] = True
        self.save_active_chats()
    
    def stop_chat(self, user_id):
        """Остановить диалог с пользователем"""
        self.active_chats[str(user_id)] = False
        self.save_active_chats()
    
    def preprocess_text(self, text):
        """Предварительная обработка текста"""
        text = text.lower().strip()
        text = re.sub(r'[^\w\sа-яё]', '', text)  # Удаляем спецсимволы
        words = text.split()
        return words
    
    def find_best_match(self, question):
        """Поиск лучшего совпадения в базе знаний"""
        question_words = self.preprocess_text(question)
        best_match = None
        best_score = 0
        
        for pattern, responses in self.knowledge.items():
            pattern_words = self.preprocess_text(pattern)
            
            # Простой алгоритм сравнения
            common_words = set(question_words) & set(pattern_words)
            score = len(common_words) / max(len(question_words), len(pattern_words))
            
            if score > best_score and score > 0.3:  # Пороговое значение
                best_score = score
                best_match = (pattern, responses)
        
        return best_match
    
    def solve_math_expression(self, expression):
        """Решение математических выражений"""
        try:
            # Безопасное вычисление
            expr = expression.replace('×', '*').replace('÷', '/').replace('^', '**')
            expr = re.sub(r'[^0-9+\-*/().]', '', expr)
            
            if not re.match(r'^[0-9+\-*/().]+$', expr):
                return None
                
            result = eval(expr)
            return f"{expression} = {result}"
        except:
            return None
    
    def get_response(self, question, user_id=None):
        """Получение ответа от ИИ"""
        if not question.strip():
            return "Я вас слушаю..."
        
        # Проверяем команды остановки диалога
        stop_commands = ['стопИИ']
        if question.lower() in stop_commands:
            if user_id:
                self.stop_chat(user_id)
            return "Диалог завершен! Если захотите пообщаться снова, просто напишите мне что-нибудь 😊"
        
        # Пытаемся решить математическое выражение
        math_result = self.solve_math_expression(question)
        if math_result:
            return f"🎯 {math_result}"
        
        # Ищем в базе знаний
        match = self.find_best_match(question)
        
        if match:
            pattern, responses = match
            import random
            return f" {random.choice(responses)}"
        else:
            unknown_responses = [
                "Интересный вопрос! Но я пока не знаю ответа.",
                "Мне нужно еще поучиться, чтобы ответить на это.",
                "Извините, я еще не знаю ответ на этот вопрос.",
                "Пока не могу ответить на этот вопрос.",
                "Хм, хороший вопрос! Спросите о чем-то из школьной программы."
            ]
            import random
            return random.choice(unknown_responses)
    
    def learn(self, pattern, response, trained_by):
        """Обучение ИИ новому шаблону - ТОЛЬКО для владельца"""
        pattern = pattern.lower().strip()
        
        # Добавляем в базу знаний
        if pattern not in self.knowledge:
            self.knowledge[pattern] = []
        
        if response not in self.knowledge[pattern]:
            self.knowledge[pattern].append(response)
        
        # Сохраняем в историю обучения
        training_entry = {
            'timestamp': datetime.now().isoformat(),
            'pattern': pattern,
            'response': response,
            'trained_by': trained_by
        }
        self.training_history.append(training_entry)
        
        # Сохраняем данные
        self.save_knowledge()
        self.save_training_history()
        
        return f"✅ ИИ обучен! Шаблон: '{pattern}' → Ответ: '{response}'"
    
    def forget(self, pattern):
        """Удаление шаблона из базы знаний - ТОЛЬКО для владельца"""
        pattern = pattern.lower().strip()
        
        if pattern in self.knowledge:
            del self.knowledge[pattern]
            self.save_knowledge()
            
            # Удаляем из истории обучения
            self.training_history = [entry for entry in self.training_history 
                                   if entry['pattern'].lower() != pattern]
            self.save_training_history()
            
            return f"✅ Шаблон '{pattern}' удален из памяти ИИ"
        else:
            return f"❌ Шаблон '{pattern}' не найден в базе знаний"
    
    def get_stats(self):
        """Получение статистики ИИ"""
        total_patterns = len(self.knowledge)
        total_responses = sum(len(responses) for responses in self.knowledge.values())
        total_trainings = len(self.training_history)
        active_chats_count = sum(1 for active in self.active_chats.values() if active)
        
        return (
            f"📊 <b>Статистика ИИ:</b>\n"
            f"• Шаблонов: {total_patterns}\n"
            f"• Ответов: {total_responses}\n"
            f"• Обучений: {total_trainings}\n"
            f"• Активных диалогов: {active_chats_count}\n"
            f"• Последнее обучение: {self.training_history[-1]['timestamp'][:10] if self.training_history else 'Никогда'}"
        )
        
class DeepSeekAI:
    def __init__(self):
        self.api_key = os.environ.get('DEEPSEEK_API_KEY')
        self.base_url = "https://api.deepseek.com/v1/chat/completions"
    
    async def chat(self, message: str, user_id: Optional[str] = None) -> str:
        """Общение с DeepSeek AI"""
        if not self.api_key:
            return "❌ API ключ не настроен. Используйте /ai_learn для обучения"
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {
                        "role": "system",
                        "content": "Ты полезный и дружелюбный AI ассистент в Telegram боте. Отвечай кратко и понятно."
                    },
                    {
                        "role": "user", 
                        "content": message
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 1000,
                "stream": False
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['choices'][0]['message']['content']
                    else:
                        error = await response.text()
                        return f"❌ Ошибка DeepSeek: {error}"
                        
        except Exception as e:
            print(f"DeepSeek error: {e}")
            # Fallback на локальный ИИ
            return ai_system.get_response(message, user_id)
            
# Создаем экземпляр ИИ
ai_system = SimpleAI()
deepseek_ai = DeepSeekAI()

async def get_ai_response(message, user_id):
    """Умная система ответов с fallback"""
    try:
        # Пытаемся DeepSeek
        response = await deepseek_ai.chat(message, user_id)
        return response
    except Exception as e:
        print(f"DeepSeek ошибка: {e}")
        # Fallback на локальный ИИ
        return ai_system.get_response(message, user_id)

# Пример начального обучения ИИ
def initialize_ai():
    """Начальное обучение ИИ базовым командам"""
    if not ai_system.knowledge:
        print("🤖 Инициализация ИИ школьными знаниями...")
        
        basic_knowledge = [
            ("привет", "Привет! 😊 Готов помочь с учебой! По какому предмету вопрос?"),
            ("как дела", "Отлично! Готов объяснять школьные темы. Спрашивай!"),
            ("что ты умеешь", "Я помогаю с школьными предметами: математика, физика, химия, география, история, литература, биология!"),
            ("спасибо", "Всегда пожалуйста! 😊 Рад был помочь с учебой!"),
            ("пока", "До свидания! Возвращайся, если будут вопросы по учебе! 👋"),
        ]
        
        for pattern, response in basic_knowledge:
            ai_system.learn(pattern, response, "system")
        
        print("✅ ИИ успешно загрузил школьные знания")
        
initialize_ai()
        
async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):        
    print(f"🔵 Получено сообщение: {update.message.text}")
    
    # Выполняем security проверки
    allowed, message = await smart_security_check(update, "message")
    if not allowed:
        await update.message.reply_text(message)
        return        
        
    if await check_block(update, context):         
        return

    user_id = update.message.from_user.id
    user_message = update.message.text  # ← Сохраняем сообщение в переменную
    print(f"🔵 user_id: {user_id}, активен чат: {ai_system.is_chat_active(user_id)}")
    
    if ai_system.is_chat_active(user_id):
        print("🔵 Передаем сообщение DeepSeek")
        
        # ПОПЫТКА 1: DeepSeek
        try:
            response = await deepseek_ai.chat(user_message, user_id)
            print(f"🔵 Ответ DeepSeek: {response}")
        except Exception as e:
            print(f"❌ DeepSeek ошибка: {e}")
            # ПОПЫТКА 2: Локальный ИИ
            response = ai_system.get_response(user_message, user_id)
            print(f"🔵 Ответ локального ИИ: {response}")
        
        # Отправляем ответ пользователю
        await update.message.reply_text(response)
        
        # ✅ АВТО-ОБУЧЕНИЕ после успешного ответа
        await auto_learn_from_chat(user_message, response)
        return
    
    await update.message.reply_text("")  # Ваша основная логика
    

  
    
    
# ================== AI COMMAND FUNCTIONS ==================

async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начать диалог с ИИ"""
    user_id = update.message.from_user.id
    
    if context.args:
        question = " ".join(context.args)
        ai_system.start_chat(user_id)
        response = await deepseek_ai.chat(question, user_id)
        await update.message.reply_text(response + "\n\n💡 <i>Диалог начат! Пишите вопросы. 'стопИИ' чтобы закончить</i>", parse_mode='HTML')
    else:
        ai_system.start_chat(user_id)
        await update.message.reply_text(
            "🤖 <b>Диалог с ИИ начат!</b>\n\n"
            "Задавайте вопросы! Я постараюсь помочь!\n\n"
            "💡 <i>Чтобы закончить, напишите:</i> стопИИ", 
            parse_mode='HTML'
        )

async def ai_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Остановить диалог с ИИ"""
    user_id = update.message.from_user.id
    if ai_system.is_chat_active(user_id):
        ai_system.stop_chat(user_id)
        await update.message.reply_text("✅ Диалог с ИИ завершен! /ai_chat чтобы начать снова")
    else:
        await update.message.reply_text("ℹ️ У вас нет активного диалога с ИИ")

async def ai_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Помощь по командам ИИ"""
    help_text = (
        "🤖 <b>AI Помощник</b>\n\n"
        "💬 <b>Команды:</b>\n"
        "/ai_chat - Начать диалог\n"
        "/ai_stop - Завершить диалог\n"
        "/ai_help - Эта справка\n"
        "/school - Школьные предметы\n\n"
        "💡 <b>Просто напишите вопрос</b> после /ai_chat\n"
        "❓ <b>Как закончить:</b> напишите 'стопИИ'"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

async def school_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Список школьных предметов"""
    subjects_text = (
        "📚 <b>Школьные предметы:</b>\n\n"
        "🧮 <b>Математика</b> - алгебра, геометрия\n"
        "⚛️ <b>Физика</b> - законы, формулы\n"
        "🧪 <b>Химия</b> - элементы, реакции\n"
        "🌍 <b>География</b> - страны, природа\n"
        "📜 <b>История</b> - даты, события\n"
        "📖 <b>Литература</b> - авторы, произведения\n"
        "🔬 <b>Биология</b> - организмы, процессы\n\n"
        "💡 Спросите о любой теме!"
    )
    await update.message.reply_text(subjects_text, parse_mode='HTML')

# ================== ADMIN AI FUNCTIONS ==================

async def ai_learn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обучение ИИ - только для владельца"""
    user_id = update.message.from_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Только для владельца")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("📚 Использование: /ai_learn <шаблон> | <ответ>")
        return
    
    message_text = " ".join(context.args)
    if "|" not in message_text:
        await update.message.reply_text("❌ Используйте | для разделения")
        return
    
    pattern, response = message_text.split("|", 1)
    pattern, response = pattern.strip(), response.strip()
    
    if not pattern or not response:
        await update.message.reply_text("❌ Шаблон и ответ не могут быть пустыми")
        return
    
    result = ai_system.learn(pattern, response, user_id)
    await update.message.reply_text(result)

async def ai_forget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удаление шаблона - только для владельца"""
    user_id = update.message.from_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Только для владельца")
        return
    
    if not context.args:
        await update.message.reply_text("🗑️ Использование: /ai_forget <шаблон>")
        return
    
    pattern = " ".join(context.args)
    result = ai_system.forget(pattern)
    await update.message.reply_text(result)

async def ai_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Статистика ИИ - только для владельца"""
    user_id = update.message.from_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ Только для владельца")
        return
    
    stats = ai_system.get_stats()
    await update.message.reply_text(stats, parse_mode='HTML')
    
async def auto_learn_from_chat(user_message, bot_response):
    """Умное авто-обучение"""
    # Не обучаемся на коротких сообщениях
    if len(user_message) < 5 or len(bot_response) < 3:
        return
        
    # Не обучаемся на командах
    if user_message.startswith('/'):
        return
        
    # Обучаем только если ответ понравился
    positive_keywords = ['спасибо', 'круто', 'класс', 'супер', 'отлично', ' здорово', '👍', '😊', '😄', 'спс']
    negative_keywords = ['плохо', 'неправ', 'ошибка', 'глупость', '👎', '😠', 'динаху', 'иди нахуй']
    
    has_positive = any(keyword in user_message.lower() for keyword in positive_keywords)
    has_negative = any(keyword in user_message.lower() for keyword in negative_keywords)
    
    if has_positive and not has_negative:
        # Добавляем в базу знаний
        ai_system.learn(user_message, bot_response, "auto_learn")
        print(f"✅ Авто-обучение: '{user_message}' → '{bot_response}'")
    
    # Функция для обработки команды /game
async def games(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик игровых команд"""
    allowed, message = await smart_security_check(update, "games")
    if not allowed:
        await update.message.reply_text(message)
        return
        
    if await check_block(update, context):         
        return
         
    await update.message.reply_text(
        '𝗚𝗔𝗠𝗘𝗦\n'   
        '⚽ Футбол\n'
        '/football_start_game\n\n'
        '🎰 Джекпот\n'
        '/jackpot_start_game\n\n'
        '🎯 Дартс\n'
        '/darts_start_game\n\n'
        '🎳 Боулинг\n'
        '/bowling_start_game\n\n'
        '🏀 Баскетбол\n'
        '/basketball_start_game\n\n'
        '🎲 Кубик\n'
        '/cube_start_game\n\n'
        '🔴 Отменить игру\n'
        '/cancel'
    )
    

    
async def football_start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
         
    if await check_block(update, context):         
        return
         
    user_id = update.effective_user.id
    user_currency.setdefault(user_id, 100)  # Инициализация баланса
    await update.message.reply_text(
        "⚽ Игра в Футбол\n"
        f"Баланс: {user_currency[user_id]} 🌕\n"
        "Напиши /fgame чтобы начать!"
    )
    
async def football_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик игровых команд"""
    
    if await check_block(update, context):         
        return
         
        
    user_id = update.effective_user.id
    user_currency.setdefault(user_id, 100)
    await update.message.reply_text(
        "⚽ Добро пожаловать в игру Футбол!\n"
        f"Ваш баланс: {user_currency[user_id]} 🌕\n"
        "Введите ставку:"
    )
    return BET_FOOTBALL
    
async def handle_football_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        bet = int(update.message.text)
        if bet <= 0 or bet > user_currency.get(user_id, 0):
            await update.message.reply_text("❌ Неверная ставка!")
            return ConversationHandler.END
        context.user_data['bet'] = bet
        await update.message.reply_text("Теперь напишите: Гол или Промах")
        return CHOICE_FOOTBALL
    except ValueError:
        await update.message.reply_text("Введите число!")
        return ConversationHandler.END

async def handle_football_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bet = context.user_data.get('bet', 0)
    choice = update.message.text.strip().lower()

    if choice not in ['гол', 'промах']:
        await update.message.reply_text("Пожалуйста, напишите 'Гол' или 'Промах'")
        return CHOICE_FOOTBALL

    # Бросаем кубик футбола
    dice_message = await update.message.reply_dice(emoji="⚽")
    dice_value = dice_message.dice.value
    result = 'гол' if dice_value in [4, 5] else 'промах'

    if choice == result:
        winnings = bet * 2
        user_currency[user_id] += winnings
        save_user_data()
        await update.message.reply_text("🎉")
        outcome = f"⚽ {result.capitalize()}!\n🎉Победа! +{winnings} 🌕"
    else:
        user_currency[user_id] -= bet
        save_user_data()
        await update.message.reply_text("🥵")
        outcome = f"💥 {result.capitalize()}!\n💥Проигрыш... -{bet} 🌕"

    await update.message.reply_text(f"{outcome}\nТекущий баланс: {user_currency[user_id]} 🌕\n/Напиши /fgame — сыграть снова")
    return ConversationHandler.END
    
async def jackpot_start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
                
    if await check_block(update, context):         
        return
         
    user_id = update.effective_user.id
    user_currency.setdefault(user_id, 100)  # Инициализация баланса
    await update.message.reply_text(
        "🎰 Игра в Джекпот\n"
        f"Баланс: {user_currency[user_id]} 🌕\n"
        "Напиши /jgame чтобы начать!"
    )
    
async def jackpot_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    if await check_block(update, context):         
        return
         
    user_id = update.effective_user.id
    user_currency.setdefault(user_id, 100)
    await update.message.reply_text(
        f"🎰 Добро пожаловать в игру Джекпот!\n"
        f"Ваш баланс: {user_currency[user_id]} 🌕\n"
        "Введите ставку:"
    )
    return BET_JACKPOT

async def handle_jackpot_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        bet = int(update.message.text)
        if bet <= 0 or bet > user_currency.get(user_id, 0):
            await update.message.reply_text("❌ Неверная ставка!")
            return ConversationHandler.END
        context.user_data['bet'] = bet
        await update.message.reply_text("Теперь напишите: Победа или Промах")
        return CHOICE_JACKPOT
    except ValueError:
        await update.message.reply_text("Введите число!")
        return ConversationHandler.END

async def handle_jackpot_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bet = context.user_data.get('bet', 0)
    choice = update.message.text.strip().lower()

    if choice not in ['победа', 'промах']:
        await update.message.reply_text("Пожалуйста, напишите 'Победа' или 'Промах'")
        return CHOICE_JACKPOT

    dice_message = await update.message.reply_dice(emoji="🎰")
    dice_value = dice_message.dice.value

    # УЛУЧШЕННАЯ И СПРАВЕДЛИВАЯ СИСТЕМА
    if dice_value == 64:  # Джекпот (три семерки)
        multiplier = 10
        message = "🎰 ДЖЕКПОТ! 777! x10"
        result_type = "победа"
    elif dice_value in [32, 48]:  # Два одинаковых символа
        multiplier = 3
        message = "🎰 Два одинаковых! x3"
        result_type = "победа"
    elif dice_value in [1, 2, 4, 8, 16]:  # Выигрышные комбинации
        multiplier = 2
        message = "🎰 Выигрыш! x2"
        result_type = "победа"
    else:
        multiplier = 0
        message = "💥 Проигрыш..."
        result_type = "промах"

    # НОРМАЛЬНАЯ ЛОГИКА: если угадал - получаешь, не угадал - теряешь
    if choice == result_type:
        if result_type == "победа":
            winnings = bet * multiplier
            user_currency[user_id] += winnings
            save_user_data()
            text = f"🎉 {message}\nТы угадал! +{winnings} 🌕"
        else:  # угадал промах
            # Возвращаем ставку или небольшой бонус
            user_currency[user_id] += bet  # Возврат ставки
            save_user_data()
            text = f"🎯 {message}\nТы угадал промах! Ставка возвращена 🌕"
    else:
        user_currency[user_id] -= bet
        save_user_data()
        text = f"💥 {message}\nТы не угадал! -{bet} 🌕"

    await update.message.reply_text(
        f"{text}\nТекущий баланс: {user_currency[user_id]} 🌕\n/jgame — сыграть снова"
    )
    return ConversationHandler.END


    
async def darts_start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик игровых команд"""
         
    if await check_block(update, context):         
        return
         
         
    user_id = update.effective_user.id
    user_currency.setdefault(user_id, 100)  # Инициализация баланса
    await update.message.reply_text(
        "🎯 Игра в Дартс\n"
        f"Баланс: {user_currency[user_id]} 🌕\n"
        "Напиши /dgame чтобы начать!"
    )
    
    # Функция для начала игры в дартс
async def darts_game(update: Update, context):
    allowed, message = await smart_security_check(update, "dgame")
         
    if await check_block(update, context):         
        return
         
    user_id = update.effective_user.id
    user_currency.setdefault(user_id, 100)
    await update.message.reply_text(
        f"🎯 Добро пожаловать в игру Дартс!\n"
        f"Ваш баланс: {user_currency[user_id]} 🌕\n"
        "Введите вашу ставку:"
    )
    return BET_DARTS
    
    # Обработка ставки в дартс
async def handle_darts_bet(update: Update, context):
    user_id = update.effective_user.id
    try:
        bet = int(update.message.text)
        if bet <= 0 or bet > user_currency.get(user_id, 0):
            await update.message.reply_text("❌ Неверная ставка!")
            return ConversationHandler.END
        context.user_data['bet'] = bet
        await update.message.reply_text("Теперь напишите: 'Промах' или 'Попал'")
        return CHOICE_DARTS
    except ValueError:
        await update.message.reply_text("❗ Пожалуйста, введите число.")
        return BET_DARTS

# Обработка выбора "Попал" или "Промах"
async def handle_darts_choice(update: Update, context):
    user_id = update.effective_user.id
    bet = context.user_data.get('bet', 0)
    choice = update.message.text.strip().lower()

    if choice not in ['попал', 'промах']:
        await update.message.reply_text("❗ Напишите 'Попал' или 'Промах'")
        return CHOICE_DARTS

    # Отправляем анимацию дартса
    dice_message = await update.message.reply_dice(emoji="🎯")
    await asyncio.sleep(3)  # Ждём, пока завершится анимация

    value = dice_message.dice.value
    actual_result = 'попал' if value == 6 else 'промах'

    if choice == actual_result:
        multiplier = 2
        winnings = bet * multiplier
        user_currency[user_id] += winnings
        save_user_data()
        await update.message.reply_text("🎉")
        text = (
            f"🎯 Дартс показывает: {value} ({actual_result.upper()})\n"
            f"🎉 Ты угадал! +{winnings} 🌕"
        )
    else:
        user_currency[user_id] -= bet
        save_user_data()
        await update.message.reply_text("🥵")
        text = (
            f"🎯 Дартс показывает: {value} ({actual_result.upper()})\n"
            f"💥 Ты не угадал. -{bet} 🌕"
        )

    await update.message.reply_text(
        f"{text}\nТекущий баланс: {user_currency[user_id]} 🌕\nНапиши /dgame — сыграть снова"
    )
    return ConversationHandler.END
    
async def bowling_start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик игровых команд"""
         
    if await check_block(update, context):         
        return
         
         
    user_id = update.effective_user.id
    user_currency.setdefault(user_id, 100)  # Инициализация баланса
    await update.message.reply_text(
        "🎳 Игра в Боулинг\n"
        f"Баланс: {user_currency[user_id]} 🌕\n"
        "Напиши /bgame чтобы начать!"
    )
    
async def bowling_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик игровых команд"""
    
    if await check_block(update, context):         
        return
         
    user_id = update.effective_user.id
    user_currency.setdefault(user_id, 100)
    await update.message.reply_text(
        f"🎳 Добро пожаловать в Боулинг!\n"
        f"Ваш баланс: {user_currency[user_id]} 🌕\n"
        "Введите вашу ставку:"
    )
    return BOWLING_BET
    
async def handle_bowling_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        bet = int(update.message.text)
        if bet <= 0 or bet > user_currency.get(user_id, 0):
            await update.message.reply_text("❌ Неверная ставка.")
            return ConversationHandler.END
        context.user_data['bowling_bet'] = bet
        await update.message.reply_text("Теперь напиши: 'Выбил все' или 'Выбил не все'")
        return BOWLING_GUESS
    except ValueError:
        await update.message.reply_text("❗ Введите число.")
        return BOWLING_BET
    
async def handle_bowling_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    choice = update.message.text.strip().lower()
    bet = context.user_data.get('bowling_bet', 0)

    if choice not in ['выбил все', 'выбил не все']:
        await update.message.reply_text("❗ Введи 'Выбил все' или 'Выбил не все'")
        return BOWLING_GUESS

    dice_msg = await update.message.reply_dice(emoji="🎳")
    await asyncio.sleep(3)

    value = dice_msg.dice.value
    actual = 'выбил все' if value == 6 else 'выбил не все'

    if choice == actual:
        winnings = bet * 2
        user_currency[user_id] += winnings
        save_user_data()
        await update.message.reply_text("🎉")
        result = f"🎳 Выпало: {value} ({actual.upper()})\n🎉 Ты угадал! +{winnings} 🌕"
    else:
        user_currency[user_id] -= bet
        save_user_data()
        await update.message.reply_text("🥵")
        result = f"🎳 Выпало: {value} ({actual.upper()})\n💥 Ты не угадал. -{bet} 🌕"

    await update.message.reply_text(
        f"{result}\nТекущий баланс: {user_currency[user_id]} 🌕\nНапиши /bgame — сыграть снова"
    )
    return ConversationHandler.END

async def cube_start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик игровых команд"""
         
    if await check_block(update, context):         
        return
               
         
    user_id = update.effective_user.id
    user_currency.setdefault(user_id, 100)  # Инициализация баланса
    await update.message.reply_text(
        "🎲 Игра в Кубик\n"
        f"Баланс: {user_currency[user_id]} 🌕\n"
        "Напиши /cgame чтобы начать!"
    )
    
# Команда для начала игры
async def cube_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    
    if await check_block(update, context):         
        return
         
    user_id = update.effective_user.id
    user_currency.setdefault(user_id, 100)  # Инициализация баланса
    await update.message.reply_text(
        "🎲 Добро пожаловать в игру Кубик!\n"
        f"Ваш баланс: {user_currency[user_id]} 🌕\n"
        "Введите ставку:"
    )
    return BET

# Обработка ставки
async def handle_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        bet = int(update.message.text)
        if bet <= 0 or bet > user_currency.get(user_id, 0):
            await update.message.reply_text("❌ Неверная ставка!")
            return ConversationHandler.END
        context.user_data['bet'] = bet
        await update.message.reply_text("Выберите: Чёт или Нечёт?")
        return CHOICE
    except ValueError:
        await update.message.reply_text("Введите число!")
        return ConversationHandler.END

# Обработка выбора чёт/нечёт
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bet = context.user_data.get('bet', 0)
    choice = update.message.text.strip().lower()

    if choice not in ['чёт', 'чет', 'нечёт', 'нечет']:
        await update.message.reply_text("Пожалуйста, выберите 'Чёт' или 'Нечёт'")
        return CHOICE

    # Бот кидает кубик
    dice_message = await update.message.reply_dice(emoji="🎲")
    dice_value = dice_message.dice.value
    result = 'чёт' if dice_value % 2 == 0 else 'нечёт'

    if choice.startswith(result):
        winnings = bet * 2
        user_currency[user_id] += winnings
        save_user_data()
        await update.message.reply_text("🎉")
        outcome = f"🎉 Победа x2!\nКубик: {dice_value} ({result}).\n +{winnings} 🌕"
    else:
        user_currency[user_id] -= bet
        save_user_data()
        await update.message.reply_text("🥵")
        outcome = f"💥 Проигрыш!\nКубик: {dice_value} ({result}).\n -{bet} 🌕"

    await update.message.reply_text(f"{outcome}\nТекущий баланс:\n {user_currency[user_id]} 🌕\n/cgame — сыграть снова")
    return ConversationHandler.END
    
    
# Запуск баскетбола
async def basketball_start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_block(update, context):         
        return
         
    user_id = update.effective_user.id
    user_currency.setdefault(user_id, 100)
    await update.message.reply_text(
        "🏀 Игра в Баскетбол\n"
        f"Баланс: {user_currency[user_id]} 🌕\n"
        "Напиши /baskgame чтобы начать!"
    )

# Игра в баскетбол
async def basketball_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_block(update, context):         
        return
         
    user_id = update.effective_user.id
    user_currency.setdefault(user_id, 100)
    await update.message.reply_text(
        "🏀 Добро пожаловать в Баскетбол!\n"
        f"Ваш баланс: {user_currency[user_id]} 🌕\n"
        "Введите ставку:"
    )
    return BASKETBALL_BET

# Обработка ставки баскетбол
async def handle_basketball_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        bet = int(update.message.text)
        if bet <= 0 or bet > user_currency.get(user_id, 0):
            await update.message.reply_text("❌ Неверная ставка!")
            return ConversationHandler.END
        context.user_data['bet'] = bet
        await update.message.reply_text("Бросьте мяч! Напишите: 'Забросил' или 'Промах'")
        return BASKETBALL_SHOT
    except ValueError:
        await update.message.reply_text("Введите число!")
        return ConversationHandler.END

# Обработка броска баскетбол
async def handle_basketball_shot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bet = context.user_data.get('bet', 0)
    choice = update.message.text.strip().lower()

    if choice not in ['забросил', 'промах']:
        await update.message.reply_text("Пожалуйста, напишите 'Забросил' или 'Промах'")
        return BASKETBALL_SHOT

    # Бросаем баскетбольный мяч
    dice_message = await update.message.reply_dice(emoji="🏀")
    dice_value = dice_message.dice.value
    
    # В баскетболе значения 4-5 - попадание, 1-3 - промах
    result = 'забросил' if dice_value >= 4 else 'промах'

    if choice == result:
        winnings = bet * 2
        user_currency[user_id] += winnings
        save_user_data()
        await update.message.reply_text("🎉")
        outcome = f"🏀 {result.upper()}! (Выпало: {dice_value})\n🎉 Победа! +{winnings} 🌕"
    else:
        user_currency[user_id] -= bet
        save_user_data()
        await update.message.reply_text("🥵")
        outcome = f"🏀 {result.upper()}! (Выпало: {dice_value})\n💥 Проигрыш... -{bet} 🌕"

    await update.message.reply_text(f"{outcome}\nТекущий баланс: {user_currency[user_id]} 🌕\n/baskgame — сыграть снова")
    return ConversationHandler.END

# Отмена игры
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Игра отменена.")
    return ConversationHandler.END
    
async def check_user_adequacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для проверки адекватности пользователя"""
    try:
        if not context.args:
            await update.message.reply_text(
                "❌ Использование: /adequacy @username или /adequacy user_id\n"
                "Пример: /adequacy @username или /adequacy 123456789"
            )
            return

        target = context.args[0]
        
        # Определяем target_type (username или user_id)
        if target.startswith('@'):
            username = target[1:]
            user_id = await get_user_id_by_username(context.bot, username, update.message.chat_id)
            if not user_id:
                await update.message.reply_text("❌ Пользователь с таким username не найден")
                return
        else:
            try:
                user_id = int(target)
            except ValueError:
                await update.message.reply_text("❌ Введите корректный user_id (число)")
                return

        # Получаем информацию о пользователе
        try:
            user = await context.bot.get_chat(user_id)
            user_profile = await analyze_user_behavior(user_id, user)
            adequacy_score = calculate_adequacy_score(user_profile)
            
            # Формируем отчет
            report = generate_adequacy_report(user, user_profile, adequacy_score)
            
            await update.message.reply_text(report, parse_mode='HTML')
            
        except TelegramError as e:
            await update.message.reply_text(f"❌ Ошибка: Не удалось получить информацию о пользователе\n{str(e)}")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")

async def get_user_id_by_username(bot, username, chat_id):
    """Получает user_id по username"""
    try:
        # Пытаемся найти пользователя в чате
        chat_member = await bot.get_chat_member(chat_id, f"@{username}")
        return chat_member.user.id
    except:
        try:
            # Альтернативный метод (если пользователь не в чате)
            user = await bot.get_chat(f"@{username}")
            return user.id
        except:
            return None

async def analyze_user_behavior(user_id, user):
    """Анализирует поведение пользователя"""
    current_time = datetime.now()
    
    # Базовая информация
    profile = {
        'user_id': user_id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_bot': user.is_bot if hasattr(user, 'is_bot') else False,
        'analysis_date': current_time.isoformat(),
        'metrics': {}
    }
    
    # Анализ активности (если есть данные)
    if user_id in user_behavior_data:
        behavior = user_behavior_data[user_id]
        profile['metrics']['message_count'] = behavior.get('message_count', 0)
        profile['metrics']['last_activity'] = behavior.get('last_activity')
        profile['metrics']['avg_message_length'] = behavior.get('avg_message_length', 0)
        profile['metrics']['command_usage'] = behavior.get('command_usage', {})
    else:
        profile['metrics']['message_count'] = 0
        profile['metrics']['data_available'] = False
    
    # Анализ профиля
    profile['metrics']['has_username'] = bool(user.username)
    profile['metrics']['has_photo'] = user.photo and user.photo.small_file_id if hasattr(user, 'photo') else False
    profile['metrics']['account_age'] = await estimate_account_age(user_id)
    
    return profile

async def estimate_account_age(user_id):
    """Оценивает возраст аккаунта (примерно)"""
    # Это упрощенная реализация - в реальности нужно хранить дату первого сообщения
    if user_id in user_behavior_data:
        first_seen = user_behavior_data[user_id].get('first_seen')
        if first_seen:
            first_seen_date = datetime.fromisoformat(first_seen)
            return (datetime.now() - first_seen_date).days
    return "неизвестно"

def calculate_adequacy_score(profile):
    """Вычисляет оценку адекватности (0-100)"""
    metrics = profile['metrics']
    score = 50  # Базовая оценка
    
    # Корректировки на основе данных
    if metrics.get('message_count', 0) > 10:
        score += min(metrics['message_count'] / 2, 20)  # Активность + до 20 баллов
    
    if metrics.get('has_username'):
        score += 10  # Наличие username
    
    if metrics.get('has_photo'):
        score += 5  # Наличие фото
    
    if metrics.get('avg_message_length', 0) > 5:
        score += 5  # Не односложные сообщения
    
    # Штрафы за подозрительное поведение
    if profile['is_bot']:
        score -= 30  # Боты менее "адекватны" с точки зрения человека
    
    if metrics.get('spam_flags', 0) > 0:
        score -= metrics['spam_flags'] * 10  # Штраф за спам
    
    # Ограничиваем от 0 до 100
    return max(0, min(100, int(score)))

def generate_adequacy_report(user, profile, score):
    """Генерирует отчет об адекватности"""
    metrics = profile['metrics']
    
    # Цвет оценки в зависимости от баллов
    if score >= 80:
        emoji = "✅"
        color = "🟢"
        status = "Высокая адекватность"
    elif score >= 60:
        emoji = "⚠️"
        color = "🟡" 
        status = "Средняя адекватность"
    elif score >= 40:
        emoji = "⚡"
        color = "🟠"
        status = "Низкая адекватность"
    else:
        emoji = "❌"
        color = "🔴"
        status = "Очень низкая адекватность"
    
    report = f"""
{emoji} <b>АНАЛИЗ АДЕКВАТНОСТИ ПОЛЬЗОВАТЕЛЯ</b> {color}

👤 <b>Пользователь:</b> {user.first_name or 'Без имени'}
📧 <b>Username:</b> @{user.username if user.username else 'отсутствует'}
🆔 <b>ID:</b> <code>{user.id}</code>

📊 <b>Оценка адекватности:</b> {score}/100
📈 <b>Статус:</b> {status}

<b>МЕТРИКИ:</b>
• Сообщений: {metrics.get('message_count', 'нет данных')}
• Username: {'есть' if metrics.get('has_username') else 'нет'}
• Фото профиля: {'есть' if metrics.get('has_photo') else 'нет'}
• Возраст аккаунта: {metrics.get('account_age', 'неизвестно')} дней

<b>ПРИМЕЧАНИЕ:</b>
Это автоматическая оценка на основе доступных данных.
Реальная адекватность может отличаться.
    """
    
    return report

# Функция для логирования сообщений (должна вызываться при каждом сообщении)
async def log_user_message(user_id, message_text):
    """Логирует сообщения пользователя для анализа"""
    if user_id not in user_behavior_data:
        user_behavior_data[user_id] = {
            'message_count': 0,
            'total_message_length': 0,
            'first_seen': datetime.now().isoformat(),
            'last_activity': datetime.now().isoformat(),
            'command_usage': {}
        }
    
    user_data = user_behavior_data[user_id]
    user_data['message_count'] += 1
    user_data['total_message_length'] += len(message_text)
    user_data['last_activity'] = datetime.now().isoformat()
    user_data['avg_message_length'] = user_data['total_message_length'] / user_data['message_count']
    
    # Логируем использование команд
    if message_text.startswith('/'):
        command = message_text.split()[0]
        user_data['command_usage'][command] = user_data['command_usage'].get(command, 0) + 1

# Функция для сохранения данных в файл
def save_behavior_data():
    """Сохраняет данные о поведении пользователей"""
    import json
    try:
        with open('user_behavior.json', 'w', encoding='utf-8') as f:
            json.dump(user_behavior_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения данных: {e}")

def load_behavior_data():
    """Загружает данные о поведении пользователей"""
    import json
    import os
    global user_behavior_data
    try:
        if os.path.exists('user_behavior.json'):
            with open('user_behavior.json', 'r', encoding='utf-8') as f:
                user_behavior_data = json.load(f)
    except:
        user_behavior_data = {}
    
# Команда /blocked_users — список заблокированных с никами, ID и причиной
async def blocked_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BLOCKED  # Ставим в начало до любого использования BLOCKED

    if update.effective_user.id != OWNER_ID:
        return

    if not BLOCKED:
        await update.message.reply_text("Список заблокированных пуст.")
        return

    updated_blocked = {}  # Новый словарь для актуальных заблокированных
    text = "Заблокированные пользователи:\n\n"

    for user_id_str, reason in BLOCKED.items():
        user_id = int(user_id_str)
        try:
            user = await context.bot.get_chat(user_id)
            name = f"@{user.username}" if user.username else f"{user.full_name}"
            text += f"👤Ник: {name}\nID🖋️: {user_id_str}\n⛔Причина: {reason}\n\n"
            updated_blocked[user_id_str] = reason
        except:
            text += f"🖋️ID: {user_id_str}\n👤Имя: Не удалось получить\n⛔Причина: {reason}\n\n"
            updated_blocked[user_id_str] = reason

    BLOCKED = updated_blocked
    save_blocked(BLOCKED)

    await update.message.reply_text(text)
    
    
async def export_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Экспорт всех участников чата в JSON файл"""
    user_id = update.effective_user.id
    
    # Проверяем права доступа (только для админов/владельца)
    if user_id != OWNER_ID:  # OWNER_ID - ваш ID
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return
    
    try:
        chat_id = update.effective_chat.id
        chat = await context.bot.get_chat(chat_id)
        
        # Отправляем сообщение о начале процесса
        progress_msg = await update.message.reply_text("⏳ Начинаю сбор данных участников...")
        
        members_data = []
        admin_count = 0
        member_count = 0
        bot_count = 0
        
        # Получаем всех участников чата
        async for member in context.bot.get_chat_members(chat_id):
            user = member.user
            member_info = {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'is_bot': user.is_bot,
                'status': member.status,
                'joined_date': member.joined_date.isoformat() if member.joined_date else None,
                'custom_title': member.custom_title,
                'until_date': member.until_date.isoformat() if member.until_date else None,
                'can_be_edited': member.can_be_edited if hasattr(member, 'can_be_edited') else None,
                'can_manage_chat': member.can_manage_chat if hasattr(member, 'can_manage_chat') else None,
                'can_delete_messages': member.can_delete_messages if hasattr(member, 'can_delete_messages') else None,
                'can_manage_video_chats': member.can_manage_video_chats if hasattr(member, 'can_manage_video_chats') else None,
                'can_restrict_members': member.can_restrict_members if hasattr(member, 'can_restrict_members') else None,
                'can_promote_members': member.can_promote_members if hasattr(member, 'can_promote_members') else None,
                'can_change_info': member.can_change_info if hasattr(member, 'can_change_info') else None,
                'can_invite_users': member.can_invite_users if hasattr(member, 'can_invite_users') else None,
                'can_post_messages': member.can_post_messages if hasattr(member, 'can_post_messages') else None,
                'can_edit_messages': member.can_edit_messages if hasattr(member, 'can_edit_messages') else None,
                'can_pin_messages': member.can_pin_messages if hasattr(member, 'can_pin_messages') else None,
                'can_manage_topics': member.can_manage_topics if hasattr(member, 'can_manage_topics') else None
            }
            
            # Убираем None значения для чистоты JSON
            member_info = {k: v for k, v in member_info.items() if v is not None}
            
            members_data.append(member_info)
            
            # Считаем статистику
            if user.is_bot:
                bot_count += 1
            elif member.status in ['administrator', 'creator']:
                admin_count += 1
            else:
                member_count += 1
            
            # Обновляем прогресс каждые 50 участников
            if len(members_data) % 50 == 0:
                await progress_msg.edit_text(
                    f"⏳ Собрано {len(members_data)} участников...\n"
                    f"👥 Обычные: {member_count} | 🛡️ Админы: {admin_count} | 🤖 Боты: {bot_count}"
                )
        
        # Создаем имя файла с timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chat_members_{chat_id}_{timestamp}.json"
        
        # Сохраняем в JSON файл
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'export_date': datetime.now().isoformat(),
                'chat_id': chat_id,
                'chat_title': chat.title,
                'chat_type': chat.type,
                'total_members': len(members_data),
                'members': members_data
            }, f, ensure_ascii=False, indent=2)
        
        # Статистика
        stats_text = (
            f"✅ <b>Экспорт завершен!</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• Всего участников: {len(members_data)}\n"
            f"• 👥 Обычные пользователи: {member_count}\n"
            f"• 🛡️ Администраторы: {admin_count}\n"
            f"• 🤖 Боты: {bot_count}\n\n"
            f"💾 <b>Файл:</b> {filename}\n"
            f"📁 <b>Размер:</b> {os.path.getsize(filename) / 1024:.1f} KB\n\n"
            f"⚡ <i>Файл сохранен на сервере бота</i>"
        )
        
        await progress_msg.edit_text(stats_text, parse_mode='HTML')
        
        # Пытаемся отправить файл пользователю
        try:
            with open(filename, 'rb') as file:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=file,
                    caption=f"📋 Экспорт участников чата '{chat.title}'\n"
                           f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                           f"👥 Участников: {len(members_data)}",
                    filename=filename
                )
            # Удаляем временный файл после отправки
            os.remove(filename)
            
        except Exception as e:
            await update.message.reply_text(
                f"✅ Данные сохранены в файл: {filename}\n"
                f"❌ Не удалось отправить файл: {str(e)}"
            )
            
    except Exception as e:
        error_msg = (
            f"❌ <b>Ошибка экспорта:</b>\n\n"
            f"<code>{str(e)}</code>\n\n"
            f"⚠️ <i>Убедитесь что бот имеет права администратора</i>"
        )
        await update.message.reply_text(error_msg, parse_mode='HTML')

# Упрощенная версия (только базовая информация)
async def export_members_simple(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Упрощенный экспорт участников"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return
    
    try:
        chat_id = update.effective_chat.id
        chat = await context.bot.get_chat(chat_id)
        
        await update.message.reply_text("⏳ Собираю базовую информацию участников...")
        
        members_data = []
        
        async for member in context.bot.get_chat_members(chat_id):
            user = member.user
            member_info = {
                'id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'is_bot': user.is_bot,
                'status': member.status
            }
            members_data.append(member_info)
        
        # Сохраняем в файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"members_simple_{chat_id}_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'chat_title': chat.title,
                'export_date': datetime.now().isoformat(),
                'total_members': len(members_data),
                'members': members_data
            }, f, ensure_ascii=False, indent=2)
        
        # Отправляем файл
        with open(filename, 'rb') as file:
            await context.bot.send_document(
                chat_id=user_id,
                document=file,
                caption=f"👥 Участники {chat.title} ({len(members_data)} человек)",
                filename=filename
            )
        
        os.remove(filename)
        await update.message.reply_text(f"✅ Экспорт завершен! Отправлено {len(members_data)} участников.")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# Команда для проверки прав бота
async def check_bot_rights(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Проверка прав бота в чате"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("Эта команда доступна только владельцу бота.")
        return
    
    try:
        chat_id = update.effective_chat.id
        chat = await context.bot.get_chat(chat_id)
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        
        rights_info = (
            f"🛡️ <b>Права бота в чате '{chat.title}':</b>\n\n"
            f"• <b>Статус:</b> {bot_member.status}\n"
            f"• <b>Может управлять чатом:</b> {bot_member.can_manage_chat if hasattr(bot_member, 'can_manage_chat') else 'N/A'}\n"
            f"• <b>Может удалять сообщения:</b> {bot_member.can_delete_messages if hasattr(bot_member, 'can_delete_messages') else 'N/A'}\n"
            f"• <b>Может банить пользователей:</b> {bot_member.can_restrict_members if hasattr(bot_member, 'can_restrict_members') else 'N/A'}\n"
            f"• <b>Может приглашать:</b> {bot_member.can_invite_users if hasattr(bot_member, 'can_invite_users') else 'N/A'}\n\n"
            f"⚠️ <i>Для экспорта участников бот должен быть администратором</i>"
        )
        
        await update.message.reply_text(rights_info, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка проверки прав: {str(e)}")

            
def main():
# Ваш API ключ
    print("🟢 Начинаем запуск бота...")
    application = ApplicationBuilder().token(TOKEN).build()
    print("🟢 Application создан")



    football_conv = ConversationHandler(
    entry_points=[CommandHandler("fgame", football_game)],
    states={
        BET_FOOTBALL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_football_bet)],
        CHOICE_FOOTBALL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_football_choice)],
         },
    fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    handler_conv = ConversationHandler(
         entry_points=[CommandHandler("jgame", jackpot_game)],
         states={
             BET_JACKPOT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_jackpot_bet)],
             CHOICE_JACKPOT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_jackpot_choice)],
         },
         fallbacks=[CommandHandler("cancel", cancel)],
    )

    darts_conv = ConversationHandler(
        entry_points=[CommandHandler("dgame", darts_game)],
        states={
            BET_DARTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_darts_bet)],
            CHOICE_DARTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_darts_choice)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    bowling_conv = ConversationHandler(
        entry_points=[CommandHandler("bgame", bowling_game)],
        states={
            BOWLING_BET: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bowling_bet)],
            BOWLING_GUESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bowling_choice)],
        },
        fallbacks=[],
    )
    
    cube_conv = ConversationHandler(
        entry_points=[CommandHandler("cgame", cube_game)],
        states={
            BET: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_bet)],
            CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice)],
         },
    fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    bask_conv = ConversationHandler(
        entry_points=[CommandHandler("baskgame", basketball_game)],
        states={
            BASKETBALL_BET: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_basketball_bet)],
            BASKETBALL_SHOT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_basketball_shot)],
         },
    fallbacks=[CommandHandler("cancel", cancel)],
    )
    


    # ==================== ЗАПУСК БОТА ====================
    start_time = time.time()
    load_user_data()
    init_data()
    # Все add_handler ВНУТРИ функции с одинаковым отступом
    application.add_handler(CommandHandler("kick", kick)) #доступно владельцу бота
    application.add_handler(CommandHandler("ban", ban)) #доступно владельцу бота
    application.add_handler(CommandHandler("mute", mute)) #доступно владельцу бота
    application.add_handler(CommandHandler("unmute", unmute)) #доступно владельцу бота
    application.add_handler(CommandHandler("send_message", send_message_to_user)) #доступно владельцу бота
    application.add_handler(CommandHandler("user_activity", user_activity))
    application.add_handler(CommandHandler("user_info", user_info))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("help_creator", help_creator)) #доступно владельцу бота
    application.add_handler(CommandHandler("help_user", help_user))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("games", games))
    application.add_handler(CommandHandler("farm_currency", farm_currency))
    application.add_handler(CommandHandler("transfer_currency", transfer_currency))
    application.add_handler(CommandHandler("transfer", transfer_currency))
    application.add_handler(CommandHandler("send", transfer_currency))
    application.add_handler(CommandHandler("buy_status", buy_status))
    application.add_handler(CommandHandler("like", like_user))
    application.add_handler(CommandHandler("dislike", dislike_user))
    application.add_handler(CommandHandler("follow", follow_user))
    application.add_handler(CommandHandler("unfollow", unfollow_user))
    application.add_handler(CommandHandler("verify", verify_user)) #доступно владельцу бота
    application.add_handler(CommandHandler("unverify", unverify_user)) #доступно владельцу бота
    application.add_handler(CommandHandler("profile", show_status))
    application.add_handler(CommandHandler("top_global_players", top_global_players))
    application.add_handler(CommandHandler("referral", referral))
    application.add_handler(CommandHandler("my_referrals", my_referrals))
    application.add_handler(CommandHandler("create_check", create_check))
    application.add_handler(CommandHandler("activate_check", activate_check))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("start_raffle", start_raffle))
    application.add_handler(CommandHandler("join_raffle", join_raffle))
    application.add_handler(CommandHandler("take_coins", take_coins)) # доступно владельцу бота
    application.add_handler(CommandHandler("make_me_admin", make_me_admin)) #доступно владельцу бота
    application.add_handler(CommandHandler("promote_to_admin", promote_to_admin)) #доступно владельцу бота
    application.add_handler(CommandHandler("problem_bot", problem_bot))
    application.add_handler(CommandHandler("block", block)) #доступно владельцу бота
    application.add_handler(CommandHandler("unblock", unblock)) #доступно владельцу бота
    application.add_handler(CommandHandler("some_command", some_command))
    application.add_handler(CommandHandler("buy", buy))
    application.add_handler(CommandHandler("shop", shop))
    application.add_handler(CommandHandler("shop_house", shop_house))
    application.add_handler(CommandHandler("shop_automobile", shop_automobile))
    application.add_handler(CommandHandler("shop_clothes", shop_clothes))
    application.add_handler(CommandHandler("buy_1m", buy_1m))
    application.add_handler(CommandHandler("buy_100k", buy_100k))
    application.add_handler(CommandHandler("buy_10k", buy_10k))
    application.add_handler(CommandHandler("buy_1m_d", buy_1m_d))
    application.add_handler(CommandHandler("buy_100k_d", buy_100k_d))
    application.add_handler(CommandHandler("buy_10k_d", buy_10k_d))
    application.add_handler(CommandHandler("buyDon", buyDon))
    application.add_handler(CommandHandler("buyKill", buyKill))
    application.add_handler(CommandHandler("buyGold", buyGold))
    application.add_handler(CommandHandler("buyLeg", buyLeg))
    application.add_handler(CommandHandler("buyName", buyName))
    application.add_handler(CommandHandler("change_status", change_status))
    application.add_handler(CommandHandler("adequacy", check_user_adequacy))
    application.add_handler(CommandHandler("adequacy_check", check_user_adequacy))
    application.add_handler(CommandHandler("check_user", check_user_adequacy))
    application.add_handler(CommandHandler("cube_start_game", cube_start_game))
    application.add_handler(cube_conv)
    application.add_handler(CommandHandler("football_start_game", football_start_game))
    application.add_handler(football_conv)
    application.add_handler(CommandHandler("jackpot_start_game", jackpot_start_game))
    application.add_handler(handler_conv)
    application.add_handler(CommandHandler("darts_start_game", darts_start_game))
    application.add_handler(darts_conv)
    application.add_handler(CommandHandler("bowling_start_game", bowling_start_game))
    application.add_handler(bowling_conv)
    application.add_handler(CommandHandler("basketball_start_game", basketball_start_game))
    application.add_handler(bask_conv)
    application.add_handler(CommandHandler("give_coins", give_coins))
    application.add_handler(CommandHandler("give_diamond", give_diamond))
    application.add_handler(CommandHandler("change_my_status", change_my_status)) #доступно владельцу бота
    application.add_handler(CommandHandler("blocked_users", blocked_users)) #доступно владельцу бота
    application.add_handler(CommandHandler("change_status_donater", change_status_donater)) #доступно владельцу бота
    application.add_handler(CommandHandler("change_status_killer", change_status_killer)) #доступно владельцу бота
    application.add_handler(CommandHandler("change_status_gold", change_status_gold)) #доступно владельцу бота
    application.add_handler(CommandHandler("change_status_legend", change_status_legend)) #доступно владельцу бота
    application.add_handler(CommandHandler("change_status_admin", change_status_admin)) #доступно владельцу бота
    application.add_handler(CommandHandler("change_status_creator", change_status_creator)) #доступно владельцу бота
    application.add_handler(CommandHandler("change_status_name", change_status_name)) #доступно владельцу бота
    application.add_handler(CommandHandler("speakAI", speakAI))
    application.add_handler(CommandHandler("house1", house1))
    application.add_handler(CommandHandler("house2", house2))
    application.add_handler(CommandHandler("house3", house3))
    application.add_handler(CommandHandler("house4", house4))
    application.add_handler(CommandHandler("house5", house5))
    application.add_handler(CommandHandler("auto1", auto1))
    application.add_handler(CommandHandler("auto2", auto2))
    application.add_handler(CommandHandler("auto3", auto3))
    application.add_handler(CommandHandler("auto4", auto4))
    application.add_handler(CommandHandler("auto5", auto5))
    application.add_handler(CommandHandler("auto6", auto6))
    application.add_handler(CommandHandler("clothes1", clothes1))
    application.add_handler(CommandHandler("clothes2", clothes2))
    application.add_handler(CommandHandler("clothes3", clothes3))
    application.add_handler(CommandHandler("clothes4", clothes4))
    application.add_handler(CommandHandler("buyA", buyA))
    application.add_handler(CommandHandler("send_stars_invoice", send_stars_invoice))
    application.add_handler(CommandHandler("promote", promote)) #доступно владельцу бота
    application.add_handler(CommandHandler("demote", demote)) #доступно владельцу бота
    application.add_handler(CommandHandler("show_where", show_where))  
    application.add_handler(CommandHandler("give_follow", give_follow))  
    application.add_handler(CommandHandler("add_likes", add_likes))
    application.add_handler(CommandHandler("remove_likes", remove_likes)) 
    application.add_handler(CommandHandler("set_likes", set_likes))
    application.add_handler(CommandHandler("export_members", export_members))
    application.add_handler(CommandHandler("export_simple", export_members_simple))
    application.add_handler(CommandHandler("check_rights", check_bot_rights))
    application.add_handler(CommandHandler("premium_verify", premium_verify))
    application.add_handler(CommandHandler("premium_unverify", premium_unverify))
    application.add_handler(CommandHandler("premium_list", show_premium_users))
    application.add_handler(CommandHandler("give_me_premium", self_premium_verify))  # Для теста
    # Основные команды ИИ
    application.add_handler(CommandHandler("ai_chat", ai_chat))
    application.add_handler(CommandHandler("ai_stop", ai_stop))
    application.add_handler(CommandHandler("ai_help", ai_help))
    application.add_handler(CommandHandler("school", school_subjects))
    # Команды обучения (только для владельца)
    application.add_handler(CommandHandler("ai_learn", ai_learn))
    application.add_handler(CommandHandler("ai_forget", ai_forget)) 
    application.add_handler(CommandHandler("ai_stats", ai_stats))
    application.add_handler(CommandHandler("withdraw", withdraw_command))
    application.add_handler(CommandHandler("confirm_withdraw", confirm_withdraw))
    application.add_handler(CommandHandler("give_reward", give_reward_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))
    print("🟢 Обработчики добавлены")


       
    # Загрузка данных при старте
    load_behavior_data()
    
    import atexit
    atexit.register(save_user_data)
    atexit.register(save_data)
    atexit.register(save_behavior_data)
    
    # Запуск фоновых задач
    async def start_background_tasks():
        asyncio.create_task(auto_unblock_users())
        asyncio.create_task(monitor_system_health())
        
        
    
    
    print("🛡️ Умная защита активирована!")
    print("⚙️ Конфигурация:")
    for key, value in SECURITY_CONFIG.items():
        print(f"   {key}: {value}")
    
    
    
    application.run_polling()
    print("🟢 Бот запущен")  # Эта строка может не выполниться из-за блокировки run_polling

if __name__ == '__main__':
    main()
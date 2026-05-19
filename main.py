import asyncio
import logging
import sys
from datetime import datetime
import pytz
import random
from os import getenv
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiohttp
load_dotenv()
# ============================================================
# SOZLAMALAR
# ============================================================
TOKEN = getenv("BOT_TOKEN")
WEATHER_API_KEY = getenv("WEATHER_API_KEY")   # https://openweathermap.org dan oling

storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ============================================================
# FSM HOLATLARI
# ============================================================
class WeatherState(StatesGroup):
    waiting_for_city = State()

class CurrencyConvertState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_direction = State()

# ============================================================
# KLAVIATURALAR
# ============================================================
def get_main_menu():
    kb = [
        [KeyboardButton(text="💱 Valyuta Kurslari"), KeyboardButton(text="🌤 Ob-havo")],
        [KeyboardButton(text="🧮 Konvertor"),        KeyboardButton(text="🕐 Vaqt")],
        [KeyboardButton(text="😄 Hazil"),            KeyboardButton(text="📖 Yordam")],
        [KeyboardButton(text="ℹ️ Bot haqida"),       KeyboardButton(text="📞 Aloqa")],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_currency_inline():
    buttons = [
        [InlineKeyboardButton(text="🔄 Yangilash",        callback_data="refresh_currency")],
        [InlineKeyboardButton(text="🧮 Konvertor",        callback_data="open_converter")],
        [InlineKeyboardButton(text="🌐 Markaziy Bank",    url="https://cbu.uz/uz/")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_convert_direction():
    buttons = [
        [InlineKeyboardButton(text="💵 USD → SO'M", callback_data="conv_usd_to_uzs")],
        [InlineKeyboardButton(text="💴 SO'M → USD", callback_data="conv_uzs_to_usd")],
        [InlineKeyboardButton(text="💶 EUR → SO'M", callback_data="conv_eur_to_uzs")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_convert")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_menu():
    buttons = [
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_currency")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ============================================================
# API FUNKSIYALARI
# ============================================================
async def get_all_rates() -> dict:
    """CBU dan barcha kurslarni olish"""
    url = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json(content_type=None)
                    rates = {}
                    target = {"USD", "EUR", "RUB", "GBP", "CNY", "KZT"}
                    for item in data:
                        if item.get("Ccy") in target:
                            rates[item["Ccy"]] = {
                                "rate": item["Rate"],
                                "diff": item.get("Diff", "0"),
                            }
                    return rates
    except Exception as e:
        logging.error(f"Valyuta xatosi: {e}")
    return {}

async def get_usd_rate() -> str | None:
    rates = await get_all_rates()
    return rates.get("USD", {}).get("rate")

async def get_weather(city_name: str) -> str:
    url = (
        f"http://api.openweathermap.org/data/2.5/weather"
        f"?q={city_name}&appid={WEATHER_API_KEY}&units=metric&lang=uz"
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    temp      = data["main"]["temp"]
                    feels     = data["main"]["feels_like"]
                    humidity  = data["main"]["humidity"]
                    wind      = data["wind"]["speed"]
                    desc      = data["weather"][0]["description"]
                    icon_code = data["weather"][0]["icon"]

                    # Emoji tanlash
                    icon_map = {
                        "01": "☀️", "02": "🌤", "03": "⛅️", "04": "☁️",
                        "09": "🌧", "10": "🌦", "11": "⛈", "13": "❄️", "50": "🌫",
                    }
                    emoji = icon_map.get(icon_code[:2], "🌡")

                    arrow = "📈" if temp > 20 else ("📉" if temp < 5 else "➡️")

                    return (
                        f"{emoji} <b>{city_name.title()}</b> shahri ob-havosi:\n\n"
                        f"🌡 Harorat: <b>{temp}°C</b> {arrow}\n"
                        f"🤔 His qilinadi: <b>{feels}°C</b>\n"
                        f"☁️ Holat: {desc.capitalize()}\n"
                        f"💧 Namlik: {humidity}%\n"
                        f"💨 Shamol: {wind} m/s"
                    )
                elif response.status == 404:
                    return "❌ Shahar topilmadi. Ingliz tilida to'g'ri yozganingizni tekshiring."
    except Exception as e:
        logging.error(f"Ob-havo xatosi: {e}")
    return "❌ Ob-havo ma'lumotini olishda xatolik yuz berdi."

# ============================================================
# HAZILLAR
# ============================================================
JOKES = [
    "Dasturchi nima yeydi? — Spam! 🥫",
    "— Nima uchun dasturchilar ko'zoynak taqadi?\n— Chunki ular C# ko'rolmaydi! 👓",
    "Bug topildi: kompyuter o'chiq edi. 🖥",
    "99 ta bug topib tugatdim. Patch qildim. Endi 127 ta bug bor. 😅",
    "Hayot — bu loop. Lekin exit() hech qachon ishlamaydi 🔄",
    "— Choy ichmoqchimisan?\n— Yo'q, men faqat Python ichamiz 🐍☕",
    "Server ishlamayapti.\n— Qayta yoqib ko'rdingizmi?\n— ... 🔌",
    "Ertaga qilamiz deb boshlagan loyiha: git init ✅\n10 yil o'tdi: git init ✅",
]

# ============================================================
# HANDLERLAR — BOSHLASH
# ============================================================
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    name = html.bold(message.from_user.full_name)
    text = (
        f"🤖 Assalomu alaykum, {name}!\n\n"
        "Men ko'p funksiyali botman. Quyidagilarni qila olaman:\n\n"
        "💱 Valyuta kurslari (CBU)\n"
        "🌤 Ob-havo ma'lumoti\n"
        "🧮 Valyuta konvertori\n"
        "🕐 Joriy vaqt\n"
        "😄 Kulgili hazillar\n\n"
        "Pastdagi menyudan tanlang 👇"
    )
    await message.answer(text, reply_markup=get_main_menu())

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await show_help(message)

# ============================================================
# VALYUTA
# ============================================================
@dp.message(F.text == "💱 Valyuta Kurslari")
async def show_currency(message: Message):
    msg = await message.answer("⏳ Kurslar yuklanmoqda...")
    rates = await get_all_rates()
    if rates:
        now = datetime.now(pytz.timezone("Asia/Tashkent")).strftime("%d.%m.%Y %H:%M")

        def diff_arrow(d):
            try:
                v = float(d)
                return "🔺" if v > 0 else ("🔻" if v < 0 else "➡️")
            except:
                return "➡️"

        lines = [f"💹 <b>Valyuta kurslari</b> ({now})\n<i>Manba: CBU</i>\n"]
        flags = {"USD": "🇺🇸", "EUR": "🇪🇺", "RUB": "🇷🇺", "GBP": "🇬🇧", "CNY": "🇨🇳", "KZT": "🇰🇿"}
        for ccy, info in rates.items():
            arrow = diff_arrow(info["diff"])
            lines.append(f"{flags.get(ccy,'🏳️')} <b>{ccy}</b>: {float(info['rate']):,.2f} so'm {arrow}")

        await msg.edit_text("\n".join(lines), reply_markup=get_currency_inline())
    else:
        await msg.edit_text("❌ Kurslarni olishda xatolik. Keyinroq urinib ko'ring.")

@dp.callback_query(F.data == "refresh_currency")
async def refresh_currency(callback: CallbackQuery):
    rates = await get_all_rates()
    if rates:
        now = datetime.now(pytz.timezone("Asia/Tashkent")).strftime("%d.%m.%Y %H:%M")

        def diff_arrow(d):
            try:
                v = float(d)
                return "🔺" if v > 0 else ("🔻" if v < 0 else "➡️")
            except:
                return "➡️"

        flags = {"USD": "🇺🇸", "EUR": "🇪🇺", "RUB": "🇷🇺", "GBP": "🇬🇧", "CNY": "🇨🇳", "KZT": "🇰🇿"}
        lines = [f"💹 <b>Valyuta kurslari</b> ({now})\n<i>Manba: CBU</i>\n"]
        for ccy, info in rates.items():
            arrow = diff_arrow(info["diff"])
            lines.append(f"{flags.get(ccy,'🏳️')} <b>{ccy}</b>: {float(info['rate']):,.2f} so'm {arrow}")

        await callback.message.edit_text("\n".join(lines), reply_markup=get_currency_inline())
        await callback.answer("✅ Yangilandi!")
    else:
        await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)

# ============================================================
# OB-HAVO
# ============================================================
@dp.message(F.text == "🌤 Ob-havo")
async def ask_city(message: Message, state: FSMContext):
    await state.set_state(WeatherState.waiting_for_city)
    await message.answer(
        "🏙 Ob-havoni bilmoqchi bo'lgan shaharni inglizcha yozing:\n"
        "<i>Masalan: Tashkent, London, Moscow, Dubai</i>",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
            resize_keyboard=True
        )
    )

@dp.message(WeatherState.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=get_main_menu())
        return

    msg = await message.answer("⏳ Ma'lumot olinmoqda...")
    result = await get_weather(message.text.strip())
    await state.clear()
    await msg.edit_text(result)
    await message.answer("Bosh menyu:", reply_markup=get_main_menu())

# ============================================================
# KONVERTOR
# ============================================================
@dp.message(F.text == "🧮 Konvertor")
async def open_converter_menu(message: Message):
    await message.answer("🧮 Qaysi yo'nalishda konvertatsiya qilmoqchisiz?", reply_markup=get_convert_direction())

@dp.callback_query(F.data == "open_converter")
async def open_converter_callback(callback: CallbackQuery):
    await callback.message.answer("🧮 Qaysi yo'nalishda konvertatsiya qilmoqchisiz?", reply_markup=get_convert_direction())
    await callback.answer()

@dp.callback_query(F.data.in_({"conv_usd_to_uzs", "conv_uzs_to_usd", "conv_eur_to_uzs"}))
async def choose_direction(callback: CallbackQuery, state: FSMContext):
    direction_map = {
        "conv_usd_to_uzs": ("USD", "so'm",  "USD → SO'M"),
        "conv_uzs_to_usd": ("UZS", "USD",   "SO'M → USD"),
        "conv_eur_to_uzs": ("EUR", "so'm",  "EUR → SO'M"),
    }
    frm, to, label = direction_map[callback.data]
    await state.update_data(direction=callback.data)
    await state.set_state(CurrencyConvertState.waiting_for_amount)
    await callback.message.answer(
        f"💱 <b>{label}</b> konvertori\n\nMiqdorni kiriting (faqat raqam):",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
            resize_keyboard=True
        )
    )
    await callback.answer()

@dp.callback_query(F.data == "cancel_convert")
async def cancel_convert(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Konvertatsiya bekor qilindi.")
    await callback.answer()

@dp.message(CurrencyConvertState.waiting_for_amount)
async def process_convert_amount(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=get_main_menu())
        return

    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer("⚠️ Iltimos, faqat raqam kiriting. Masalan: 100")
        return

    data = await state.get_data()
    direction = data.get("direction", "conv_usd_to_uzs")

    rates = await get_all_rates()
    usd_rate = float(rates.get("USD", {}).get("rate", 0))
    eur_rate = float(rates.get("EUR", {}).get("rate", 0))

    if direction == "conv_usd_to_uzs":
        if not usd_rate:
            await message.answer("❌ Kurs ma'lumoti topilmadi.")
            await state.clear()
            await message.answer("Bosh menyu:", reply_markup=get_main_menu())
            return
        result = amount * usd_rate
        text = f"💵 {amount:,.2f} USD = <b>{result:,.0f} so'm</b>\n<i>Kurs: {usd_rate:,.2f} so'm/USD</i>"

    elif direction == "conv_uzs_to_usd":
        if not usd_rate:
            await message.answer("❌ Kurs ma'lumoti topilmadi.")
            await state.clear()
            await message.answer("Bosh menyu:", reply_markup=get_main_menu())
            return
        result = amount / usd_rate
        text = f"💴 {amount:,.0f} so'm = <b>{result:,.4f} USD</b>\n<i>Kurs: {usd_rate:,.2f} so'm/USD</i>"

    elif direction == "conv_eur_to_uzs":
        if not eur_rate:
            await message.answer("❌ Kurs ma'lumoti topilmadi.")
            await state.clear()
            await message.answer("Bosh menyu:", reply_markup=get_main_menu())
            return
        result = amount * eur_rate
        text = f"💶 {amount:,.2f} EUR = <b>{result:,.0f} so'm</b>\n<i>Kurs: {eur_rate:,.2f} so'm/EUR</i>"
    else:
        text = "❌ Noma'lum yo'nalish."

    await state.clear()
    await message.answer(text, reply_markup=get_main_menu())

# ============================================================
# VAQT
# ============================================================
@dp.message(F.text == "🕐 Vaqt")
async def show_time(message: Message):
    tz_list = [
        ("🇺🇿 Toshkent",   "Asia/Tashkent"),
        ("🇷🇺 Moskva",     "Europe/Moscow"),
        ("🇬🇧 London",     "Europe/London"),
        ("🇦🇪 Dubai",      "Asia/Dubai"),
        ("🇺🇸 Nyu-York",  "America/New_York"),
        ("🇯🇵 Tokio",      "Asia/Tokyo"),
    ]
    lines = ["🕐 <b>Joriy vaqt (dunyo bo'ylab)</b>\n"]
    for label, tz in tz_list:
        now = datetime.now(pytz.timezone(tz)).strftime("%H:%M  |  %d.%m.%Y")
        lines.append(f"{label}: <code>{now}</code>")
    await message.answer("\n".join(lines))

# ============================================================
# HAZIL
# ============================================================
@dp.message(F.text == "😄 Hazil")
async def send_joke(message: Message):
    joke = random.choice(JOKES)
    await message.answer(f"😄 {joke}\n\n<i>Yana bir hazil uchun tugmani bosing 😊</i>")

# ============================================================
# YORDAM
# ============================================================
async def show_help(message: Message):
    text = (
        "📖 <b>Buyruqlar va funksiyalar:</b>\n\n"
        "/start — Botni qayta ishga tushirish\n"
        "/help  — Ushbu yordam xabari\n\n"
        "💱 <b>Valyuta Kurslari</b> — USD, EUR, RUB, GBP, CNY, KZT kurslarini CBU dan olish\n"
        "🌤 <b>Ob-havo</b> — Istalgan shahar ob-havosi (OpenWeatherMap)\n"
        "🧮 <b>Konvertor</b> — Valyutani so'mga yoki aksincha konvertatsiya\n"
        "🕐 <b>Vaqt</b> — Dunyo shaharlari bo'yicha joriy vaqt\n"
        "😄 <b>Hazil</b> — Tasodifiy dasturchi hazili\n\n"
        "👨‍💻 Muammo bo'lsa: @joraboyevv_s"
    )
    await message.answer(text)

@dp.message(F.text == "📖 Yordam")
async def yordam(message: Message):
    await show_help(message)

# ============================================================
# BOT HAQIDA VA ALOQA
# ============================================================
@dp.message(F.text == "ℹ️ Bot haqida")
async def about(message: Message):
    text = (
        "🤖 <b>Bot haqida ma'lumot</b>\n\n"
        "📌 Versiya: 2.0\n"
        "🛠 Texnologiyalar:\n"
        "  • Python 3.11+\n"
        "  • Aiogram 3.x (FSM bilan)\n"
        "  • aiohttp (asinxron HTTP)\n"
        "  • CBU API (Markaziy Bank)\n"
        "  • OpenWeatherMap API\n\n"
        "✨ Funksiyalar: valyuta, ob-havo, konvertor, vaqt, hazillar\n"
        "👨‍💻 Muallif: @joraboyevv_s"
    )
    await message.answer(text)

@dp.message(F.text == "📞 Aloqa")
async def contact(message: Message):
    await message.answer(
        "📞 <b>Bog'lanish</b>\n\n"
        "👨‍💻 Admin: @joraboyevv_s\n"
        "💬 Savol, taklif yoki xato topilsa — yozing!"
    )

# ============================================================
# NOMA'LUM XABARLAR — FSM da bo'lmagan holatda
# ============================================================
@dp.message(F.text)
async def unknown_message(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return  # FSM holati boshqaradi

    await message.answer(
        "🤔 Bu buyruqni tushunmadim.\n"
        "📖 Yordam uchun /help yozing yoki pastdagi menyudan tanlang.",
        reply_markup=get_main_menu()
    )

# ============================================================
# ASOSIY FUNKSIYA
# ============================================================
async def main():
    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    logging.info("Bot ishga tushdi ✅")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s | %(levelname)s | %(message)s"
    )
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot to'xtatildi")
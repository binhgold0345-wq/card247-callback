import os
import json
import asyncio
import re
import random
import gc
import time
import sys
from datetime import datetime, timedelta
import pytz

from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl import functions, types
from telethon.tl.functions.messages import GetBotCallbackAnswerRequest
from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from PIL import Image
import pytesseract

from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich.box import DOUBLE

# === CẤU HÌNH MÔI TRƯỜNG CHO RENDER ===
# Render không có Termux, nên tắt thông báo để tránh crash
def send_termux_notification(title, content):
    # Render không hỗ trợ termux, bỏ qua hoàn toàn
    pass

# == Kết thúc cấu hình Render ===

console = Console()
telethon_clients = {}
ACCOUNT_COOLDOWN_MANAGER = {}
EVENT_CODE_MANAGER = {}

TELEGRAM_BOT_TOKEN = "8890510446:AAG_jifBiDUXW_wv92BRrsiiqbSH6QZ0mpk"
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
CONFIG_FILE = "config_v53_dealer.json"
STATE_FILE = "daily_state.json"
MASTER_ADMIN_ID = 8201945667

SUPERSCRIPT_MAP = {
    '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5',
    '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9', '⁰': '0'
}

BOT_EXCLUDE_LIST = ["@dealerclmm_bot", "@dealer_poomroom_bot", "@bonuongroom_bot", "@laucua_tx_room_bot"]

DEFAULT_CONFIG = {
    "global_admins": [MASTER_ADMIN_ID],
    "sub_ids": {},
    "rooms_data": {
        "clmm": {
            "name": "CLMM",
            "channel": "@lichsuphienclmmgg",
            "code_room": "@txclmmgg",
            "bot": "@naprutclmmnew_bot",
            "dealer": "@DealerClmm_BOT",
            "icon": "🟢",
            "patterns": [
                r'CLMM-[A-Z0-9]{5,20}',
                r'CLMM-CODETT-POINT-[A-Z0-9]{5,20}',
                r'CLMM-DIEMDANH-[A-Z0-9]{5,20}',
                r'EVNAP-M[1-9]-[A-Z0-9]{5,20}'
            ]
        },
        "poom": {
            "name": "POOM ROOM",
            "channel": "@soicaupommroom",
            "code_room": "@PomeranianRoom",
            "bot": "@Pomgame_Pomeranian_bot",
            "dealer": "@Dealer_Poomroom_bot",
            "icon": "🟣",
            "patterns": [
                r'LUCKY-POINT-[A-Z0-9]{5,20}',
                r'POMM-CODETT-POINT-[A-Z0-9]{5,20}',
                r'EVNAP-M[1-9]-[A-Z0-9]{5,20}'
            ]
        },
        "bonuong": {
            "name": "BÒ NƯỚNG",
            "channel": "@bonuongroom",
            "code_room": "@bonuongroom",
            "bot": "@bonuongbot_bot",
            "dealer": "@bonuongdealer_bot",
            "icon": "🐂",
            "patterns": [
                r'KMAINAP\d+',
                r'EVENTXX[A-Z0-9]+',
                r'BONUONG\d+',
                r'THUONGBONUONG-[A-Z0-9]+'
            ]
        },
        "lau_cua": {
            "name": "LẨU CUA TÀI XỈU",
            "channel": "@laucuataixiuroom",
            "code_room": "@laucuataixiuroom",
            "bot": "@laucua_chiang_mai_bot",
            "dealer": "@laucua_tx_room_bot",
            "icon": "🦀",
            "patterns": [
                r'LAUCUA-[A-Z0-9]{5,25}',
                r'GIFTCODE-[A-Z0-9]{5,25}',
                r'CUA-[A-Z0-9]{5,25}'
            ]
        }
    },
    "users_data": {},
    "auto_code_config": {
        "clmm_active": False,
        "poom_active": False,
        "bonuong_active": False,
        "lau_cua_active": False,
        "auto_click_button": True,
        "clmm_params": {"max_code": 4, "delay_detect": 2, "delay_retry": 301},
        "poom_params": {"max_code": 4, "delay_detect": 1, "delay_retry": 301},
        "bonuong_params": {"max_code": 4, "delay_detect": 1, "delay_retry": 301},
        "lau_cua_params": {"max_code": 4, "delay_detect": 1, "delay_retry": 301},
        "history_logs": []
    }
}

STATS = {
    "start_time": datetime.now(),
    "codes_entered": 0,
    "total_lua": 0,
    "images_scanned": 0,
    "latest_code": "Chưa có",
    "acc_online": 0,
    "current_date": datetime.now().strftime("%Y-%m-%d")
}

PROCESSED_PHIEN_LOCK = set()
XX_NHANH_START_TIMES = {}
XX_NHANH_LAST_MSG_IDS = {}
DAILY_SUCCESS = {}

def load_daily_state():
    today_str = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                if data.get("date") == today_str:
                    return data.get("success_dict", {})
        except Exception:
            pass
    return {}

def save_daily_state(state_dict):
    today_str = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(STATE_FILE, "w") as f:
            json.dump({"date": today_str, "success_dict": state_dict}, f)
    except Exception:
        pass

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "global_admins" not in data:
                data["global_admins"] = [MASTER_ADMIN_ID]
            if MASTER_ADMIN_ID not in data["global_admins"]:
                data["global_admins"].append(MASTER_ADMIN_ID)
            if "sub_ids" not in data:
                data["sub_ids"] = {}
            if "rooms_data" not in data:
                data["rooms_data"] = DEFAULT_CONFIG["rooms_data"]

            for rk, rmeta in DEFAULT_CONFIG["rooms_data"].items():
                if rk not in data["rooms_data"]:
                    data["rooms_data"][rk] = rmeta
                else:
                    data["rooms_data"][rk]["name"] = rmeta["name"]
                    data["rooms_data"][rk]["icon"] = rmeta["icon"]
                    if "patterns" not in data["rooms_data"][rk]:
                        data["rooms_data"][rk]["patterns"] = rmeta["patterns"]
            if "auto_code_config" not in data:
                data["auto_code_config"] = DEFAULT_CONFIG["auto_code_config"]
            else:
                if "auto_click_button" not in data["auto_code_config"]:
                    data["auto_code_config"]["auto_click_button"] = True
                for pk in ["clmm_params", "poom_params", "bonuong_params", "lau_cua_params"]:
                    if pk not in data["auto_code_config"]:
                        data["auto_code_config"][pk] = DEFAULT_CONFIG["auto_code_config"].get(pk, {"max_code": 4, "delay_detect": 1, "delay_retry": 301})
                    else:
                        if "max_code" not in data["auto_code_config"][pk]:
                            data["auto_code_config"][pk]["max_code"] = 4
                        if "delay_retry" not in data["auto_code_config"][pk]:
                            data["auto_code_config"][pk]["delay_retry"] = 301
            return data
    except Exception:
        return DEFAULT_CONFIG

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

config = load_config()
used_codes_cache = set()
DAILY_SUCCESS = load_daily_state()

def fix_ocr_code(text):
    return text.upper().replace(" ", "").strip()

def init_user_if_not_exists(user_id_str):
    if user_id_str not in config["users_data"]:
        config["users_data"][user_id_str] = {
            "is_admin": False,
            "active_rooms": {k: False for k in config["rooms_data"].keys()},
            "rooms_config": {},
            "connected_phones": []
        }
    udata = config["users_data"][user_id_str]
    if "connected_phones" not in udata:
        udata["connected_phones"] = []

    if int(user_id_str) == MASTER_ADMIN_ID or config["sub_ids"].get(user_id_str) == "admin":
        udata["is_admin"] = True
    else:
        udata["is_admin"] = False

    for k in config["rooms_data"].keys():
        if k not in udata["active_rooms"]:
            udata["active_rooms"][k] = False
        if k not in udata["rooms_config"]:
            udata["rooms_config"][k] = {
                "mode": "du_doan", "he_phan_tich": "tx", "von_ban_dau": 1000, "he_so_nhan": 2.0, "chot_loi": 0, "cat_lo": 0,
                "nguong_rut_tien": 0, "so_tien_rut_auto": 0, "current_balance": 0, "current_bet_step": 0, "total_profit_loss": 0,
                "streak_win_ai": 0, "max_streak_win_ai": 0, "streak_loss_ai": 0, "max_streak_loss_ai": 0,
                "streak_loss_bet": 0, "total_predictions": 0, "total_wins": 0, "last_confidence": 75.0,
                "history_tx": [], "history_cl": [], "last_prediction": "", "last_processed_phien": "",
                "current_logic_index": 0, "is_using_20_logic": True,
                "chot_loi_le_vong": 0, "nghi_so_phien": 0, "cat_chuoi_thua": 0,
                "accumulated_vong_profit": 0, "remaining_rest_phiens": 0,
                "is_withdrawn_at_threshold": False, "last_match_result": "",
                "delay_bet_xx_nhanh": 2,
                "is_betting_locked": False,
                "is_cầu_1_1_active": False,
                "xx_nhanh_logic_type": "logic_1",
                "cau_history_tx": [],
                "cau_history_cl": [],
                "bat_cau_3so": False,
                "auto_cuoc_enabled": False,
                "logic3_state": {"mode": "kep", "loss_count": 0, "win_count": 0, "streak": 0},
                "logic4_state": {"mode": "kep", "loss_count": 0, "pattern": [], "choice": "", "waiting": False}
            }

def get_progress_bar(confidence):
    filled_len = int(confidence // 10)
    return '█' * filled_len + '░' * (10 - filled_len)

def get_target_profit_bar(current, target):
    if target <= 0:
        return "░░░░░░░░░░ 0%"
    percent = min(int((current / target) * 100), 100)
    if percent < 0:
        percent = 0
    filled_len = int(percent // 10)
    return f"{'█' * filled_len}{'░' * (10 - filled_len)} {percent}%"

def get_fibonacci_step(index):
    if index <= 0:
        return 1
    if index == 1:
        return 1
    a, b = 1, 1
    for _ in range(2, index + 1):
        a, b = b, a + b
    return b

def get_vietnam_time_str():
    return datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime("%Y-%m-%d %H:%M:%S")

async def send_system_notification(bot_app, target_user_id, room_name, icon, event_type, status, current_balance, details=""):
    time_now = get_vietnam_time_str()
    msg = (
        f"🚨 <b>THÔNG BÁO HỆ THỐNG - {room_name.upper()}</b> {icon}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"➔ <b>Loại Sự Kiện:</b> <code>{event_type.upper()}</code>\n"
        f"➔ <b>Trạng Thái:</b> {status}\n"
        f"➔ <b>Thời Gian:</b> <code>{time_now}</code>\n"
        f"➔ <b>Số Dư Hiện Tại:</b> <code>{current_balance:,} đ</code>\n"
    )
    if details:
        msg += f"────────────────────────────\n📝 <b>Chi Tiết:</b> <i>{details}</i>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    try:
        await bot_app.bot.send_message(chat_id=int(target_user_id), text=msg, parse_mode="HTML")
    except Exception:
        pass

async def send_denied_banner(update: Update):
    username_display = update.effective_user.first_name if update.effective_user.first_name else "Không xác định"
    msg_denied = (
        f"🚫 <b>HỆ THỐNG TBTOOL - CẢNH BÁO BẢN QUYỀN</b> 🚫\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ <b>THÔNG BÁO:</b> Tài khoản của bạn CHƯA ĐƯỢC CẤP QUYỀN!\n\n"
        f"➔ 👤 <b>Tên người dùng:</b> <code>{username_display}</code>\n"
        f"➔ 🆔 <b>ID Telegram:</b> <code>{update.effective_user.id}</code>\n"
        f"➔ 🛡️ <b>Trạng thái:</b> Bị Khóa / Chưa Kích Hoạt\n\n"
        f"💬 Để sử dụng toàn bộ tính năng cao cao cấp của TBTOOL:\n"
        f"👉 Vui lòng liên hệ trực tiếp người quản trị để được duyệt ID của bạn.\n\n"
        f"📩 <b>NHẮN TIN NGAY TẠI:</b> 🌟 @hack838688 🌟\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(msg_denied, parse_mode="HTML")

def generate_live_ui():
    uptime = str(datetime.now() - STATS["start_time"]).split('.')[0]

    ui_text = Text()
    ui_text.append("\n ⏱️  Thời gian tool chạy : ", style="bold white")
    ui_text.append(f"{uptime}\n", style="bold green")

    ui_text.append(" 📅  Ngày hệ thống hôm nay: ", style="bold white")
    ui_text.append(f"{STATS['current_date']}\n", style="bold bright_blue")

    ui_text.append(" 👤  Số tài khoản Online : ", style="bold white")
    ui_text.append(f"{STATS['acc_online']} ACC OPERATING\n", style="bold cyan")

    ui_text.append(" 🔢  Tổng số code đã gửi : ", style="bold white")
    ui_text.append(f"{STATS['codes_entered']} LẦN\n", style="bold yellow")

    ui_text.append(" 🌾  Tổng số lúa đã húp   : ", style="bold white")
    ui_text.append(f"{STATS['total_lua']:,} VNĐ\n", style="bold green blink")

    ui_text.append(" 🖼️  Ảnh đã xử lý quét OCR: ", style="bold white")
    ui_text.append(f"{STATS['images_scanned']} ĐỒNG BỘ\n", style="bold magenta")

    ui_text.append(" 🔥  Mã Giftcode mới nhất : ", style="bold white")
    ui_text.append(f"{STATS['latest_code']}\n", style="bold bright_red")

    return Panel(
        ui_text,
        title=" ⚡ [bold gold1]HỆ THỐNG TBTOOL MULTI-ROOM AUTO CODE v99.9[/bold gold1] ⚡ ",
        title_align="center",
        border_style="bold green",
        box=DOUBLE,
        expand=True,
        subtitle=" ⛔ [bold red]HỆ THỐNG ĐANG CHẠY ĐỒNG BỘ NGẦM TRÊN TERMINAL[/bold red] ⛔ "
    )

def render_success_alert(code, value, balance, phone, code_type="TEXT"):
    alert_text = Text()
    alert_text.append(f"❇️ NHẬP GIFTCODE ({code_type}) THÀNH CÔNG KHỚP LÚA ❇️\n\n", style="bold green")
    alert_text.append(f" 📱 Tài khoản: {phone}\n", style="white")
    alert_text.append(f" 🎁 Mã Code : ", style="white")
    alert_text.append(f"{code}\n", style="bold cyan")
    alert_text.append(f" 💰 Giá trị : ", style="white")
    alert_text.append(f"{value:,} đ\n", style="bold yellow")
    alert_text.append(f" 💳 Số dư   : ", style="white")
    alert_text.append(f"{balance} đ\n\n", style="bold green")
    alert_text.append(f" 🔥 TỔNG DOANH THU HOẠCH LÚA: {STATS['total_lua']:,} đ", style="bold gold1 blink")

    alert_panel = Panel(alert_text, border_style="bold gold1", box=DOUBLE, expand=True)
    console.print("\n")
    console.print(alert_panel)
    console.print("\n")

async def midnight_checker_loop():
    global DAILY_SUCCESS
    while True:
        today_str = datetime.now().strftime("%Y-%m-%d")
        if STATS["current_date"] != today_str:
            STATS["current_date"] = today_str
            DAILY_SUCCESS = {}
            save_daily_state(DAILY_SUCCESS)
            console.print("[bold green]🌅 [RESET 00:00] Qua ngày mới, mở khóa toàn bộ lượt ăn Code Nút bấm cho các tài khoản![/bold green]")
        await asyncio.sleep(10)

def update_cau_history(rc, actual_tx, actual_cl):
    if actual_tx in ["TÀI", "XỈU"]:
        tx_short = "T" if actual_tx == "TÀI" else "X"
        rc["cau_history_tx"].append(tx_short)
        if len(rc["cau_history_tx"]) > 10:
            rc["cau_history_tx"].pop(0)
    if actual_cl in ["CHẴN", "LẺ"]:
        cl_short = "C" if actual_cl == "CHẴN" else "L"
        rc["cau_history_cl"].append(cl_short)
        if len(rc["cau_history_cl"]) > 10:
            rc["cau_history_cl"].pop(0)

def find_pattern_results(history, pattern_str):
    pattern = list(pattern_str.upper().replace("-", "").replace(" ", ""))
    if not pattern or len(pattern) == 0 or len(history) <= len(pattern):
        return {}
    results = {}
    for i in range(len(history) - len(pattern)):
        if history[i:i+len(pattern)] == pattern:
            next_val = history[i+len(pattern)] if i+len(pattern) < len(history) else None
            if next_val:
                results[next_val] = results.get(next_val, 0) + 1
    return results

def render_cau_history_display(rc, room_name):
    tx_str = " ".join(rc.get("cau_history_tx", [])) if rc.get("cau_history_tx") else "Chưa có dữ liệu"
    cl_str = " ".join(rc.get("cau_history_cl", [])) if rc.get("cau_history_cl") else "Chưa có dữ liệu"
    result = (
        f"📊 <b>10 CẦU GẦN NHẤT - {room_name.upper()}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔵 TÀI/XỈU (T/X): <code>{tx_str}</code>\n"
        f"⚪ CHẴN/LẺ (C/L): <code>{cl_str}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    if rc.get("xx_nhanh_logic_type") == "logic_3":
        logic_state = rc.get("logic3_state", {"mode": "kep", "loss_count": 0, "win_count": 0})
        mode_str = "🔁 BẮT KÉP" if logic_state["mode"] == "kep" else "📈 BẮT 11"
        result += f"\n⚡ <b>LOGIC 3:</b> {mode_str} | Thua liên: {logic_state['loss_count']}/3 | Thắng liên: {logic_state['win_count']}/3"
    return result

def get_main_keyboard(user_id):
    kb = [
        [KeyboardButton("🚀 BẬT / TẮT ROOM"), KeyboardButton("🔄 CHUYỂN PHƯƠNG THỨC CƯỢC")],
        [KeyboardButton("🎛️ ĐỔI HỆ ANALYZE (T/X - C/L)"), KeyboardButton("📊 TRẠNG THÁI ACC CỦA TÔI")],
        [KeyboardButton("⚙️ CẤU HÌNH VỐN & THÔNG SỐ"), KeyboardButton("➕ THÊM TÀI KHOẢN CHÍNH")],
        [KeyboardButton("🔍 TÌM CẦU TOÀN BỘ"), KeyboardButton("🎯 BẮT CẦU 3 SỐ (AUTO)")]
    ]
    if user_id == MASTER_ADMIN_ID:
        kb.append([KeyboardButton("🔑 QUẢN LÝ HỆ THỐNG ID"), KeyboardButton("🧱 THÊM / XÓA ROOM GAME")])
    kb.append([KeyboardButton("🎁 AUTO CODE"), KeyboardButton("🗑️ HỦY LIÊN KẾT / ĐÓNG SESSION")])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_auto_code_keyboard():
    acc = config["auto_code_config"]
    clmm_st = "🟢 ON" if acc.get("clmm_active", False) else "🔴 OFF"
    poom_st = "🟢 ON" if acc.get("poom_active", False) else "🔴 OFF"
    bonuong_st = "🟢 ON" if acc.get("bonuong_active", False) else "🔴 OFF"
    laucua_st = "🟢 ON" if acc.get("lau_cua_active", False) else "🔴 OFF"
    return ReplyKeyboardMarkup([
        [KeyboardButton(f"TOGGLE_CODE_CLMM ({clmm_st})"), KeyboardButton(f"TOGGLE_CODE_POOM ({poom_st})")],
        [KeyboardButton(f"TOGGLE_CODE_BONUONG ({bonuong_st})"), KeyboardButton(f"TOGGLE_CODE_LAUCUA ({laucua_st})")],
        [KeyboardButton("⚙️ CẤU HÌNH THAM SỐ CODE"), KeyboardButton("📋 DANH SÁCH CODE NHẬP ĐƯỢC")],
        [KeyboardButton("⬅️ QUAY LẠI MENU CHÍNH")]
    ], resize_keyboard=True)

def get_room_manage_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("💰 QUẢN LÝ PHƯƠNG THỨC VỐN"), KeyboardButton("💸 NHẬP VỐN BAN ĐẦU")],
        [KeyboardButton("🛑 NHẬP CẮT LỖ"), KeyboardButton("🏆 NHẬP CHỐT LỜI")],
        [KeyboardButton("🤖 CẤU HÌNH AUTO RÚT (2 BƯỚC)"), KeyboardButton("⏳ DELAY ĐẶT CƯỢC ALL ROOM ⏱️")],
        [KeyboardButton("🎯 CHỐT LỜI LẺ VÒNG 💎"), KeyboardButton("⏳ NGHỈ SỐ PHIÊN ⏱️")],
        [KeyboardButton("🚨 CẮT CHUỒI THUA 📉"), KeyboardButton("🔄 RESET CHUỒI THẮNG/THUA ⚡")],
        [KeyboardButton("⬅️ QUAY LẠI MENU CHIẾN THUẬT")]
    ], resize_keyboard=True)

def get_von_manage_keyboard(current_type):
    gt_status = "🟢 [ĐANG BẬT]" if current_type == "gap_thep" else "🔴 [ĐANG TẮT]"
    fibo_status = "🟢 [ĐANG BẬT]" if current_type == "fibonacci" else "🔴 [ĐANG TẮT]"
    return ReplyKeyboardMarkup([
        [KeyboardButton(f"📈 GẤP THẾP CŨ {gt_status}"), KeyboardButton(f"🛡️ FIBONACCI AN TOÀN {fibo_status}")],
        [KeyboardButton("✖️ NHẬP HỆ SỐ NHÂN (GẤP THẾP)")],
        [KeyboardButton("⬅️ QUAY LẠI MENU CHIẾN THUẬT")]
    ], resize_keyboard=True)

def get_xx_nhanh_logic_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🧠 CHỌN LOGIC 1"), KeyboardButton("🔮 CHỌN LOGIC 2")],
        [KeyboardButton("⚡ CHỌN LOGIC 3 (KÉP/11)"), KeyboardButton("🎯 CHỌN LOGIC 4 (THỦ CÔNG)")],
        [KeyboardButton("🤖 AUTO CƯỢC ROOM (BẬT/TẮT)")],
        [KeyboardButton("⬅️ QUAY LẠI MENU CHÍNH")]
    ], resize_keyboard=True)

async def handle_text_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uid_str = str(uid)
    if uid != MASTER_ADMIN_ID and uid_str not in config["sub_ids"]:
        await send_denied_banner(update)
        return

    init_user_if_not_exists(uid_str)
    udata = config["users_data"].get(uid_str)
    if not udata:
        return
    text = update.message.text.strip()
    step = context.user_data.get("step")

    if text == "⬅️ QUAY LẠI MENU CHÍNH":
        context.user_data["step"] = None
        await update.message.reply_text("🔙 Đã quay lại bảng điều khiển trung tâm.", reply_markup=get_main_keyboard(uid))
        return

    if text == "⬅️ QUAY LẠI MENU CHIẾN THUẬT":
        context.user_data["step"] = None
        await update.message.reply_text("🛠️ Quay lại Menu chiến thuật.", reply_markup=get_room_manage_keyboard())
        return

    if text == "🎁 AUTO CODE":
        acc = config["auto_code_config"]
        cp = acc.get("clmm_params", {"max_code": 4, "delay_detect": 2, "delay_retry": 301})
        pp = acc.get("poom_params", {"max_code": 4, "delay_detect": 1, "delay_retry": 301})
        bp = acc.get("bonuong_params", {"max_code": 4, "delay_detect": 1, "delay_retry": 301})
        lp = acc.get("lau_cua_params", {"max_code": 4, "delay_detect": 1, "delay_retry": 301})
        msg = (
            "🎁 <b>HỆ THỐNG TỰ ĐỘNG SĂN VÉT CODE ĐỢT GIỜ VÀNG (ĐẾM NGƯỢC 5 PHÚT)</b>\n"
            "⚠️ <i>Hỗ trợ: Code nút bấm chỉ ăn 1 lần/ngày (Qua 00h reset). Toàn bộ sảnh đồng bộ nạp qua lệnh /code. Bắn Termux API!</i>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"➔ Auto Code CLMM: <b>{'BẬT 🟢' if acc.get('clmm_active') else 'TẮT 🔴'}</b>\n"
            f"   [Max Code: {cp.get('max_code', 4)} | Chờ: {cp['delay_detect']}s | Giãn cách: {cp['delay_retry']}s]\n\n"
            f"➔ Auto Code POOM: <b>{'BẬT 🟢' if acc.get('poom_active') else 'TẮT 🔴'}</b>\n"
            f"   [Max Code: {pp.get('max_code', 4)} | Chờ: {pp['delay_detect']}s | Giãn cách: {pp['delay_retry']}s]\n\n"
            f"➔ Auto Code BÒ NƯỚNG: <b>{'BẬT 🟢' if acc.get('bonuong_active') else 'TẮT 🔴'}</b>\n"
            f"   [Max Code: {bp.get('max_code', 4)} | Chờ: {bp['delay_detect']}s | Giãn cách: {bp['delay_retry']}s]\n\n"
            f"➔ Auto Code LẨU CUA: <b>{'BẬT 🟢' if acc.get('lau_cua_active') else 'TẮT 🔴'}</b>\n"
            f"   [Max Code: {lp.get('max_code', 4)} | Chờ: {lp['delay_detect']}s | Giãn cách: {lp['delay_retry']}s]\n\n"
            f"➔ Auto Click Nút Bấm Lấy Code: <b>{'BẬT 🟢' if acc.get('auto_click_button', True) else 'TẮT 🔴'}</b>\n"
            "────────────────────────────\n"
            "Vui lòng nhấn các nút điều hướng bên dưới để vận hành:"
        )
        await update.message.reply_text(msg, reply_markup=get_auto_code_keyboard(), parse_mode="HTML")
        return

    if text.startswith("TOGGLE_CODE_"):
        acc = config["auto_code_config"]
        if "CLMM" in text:
            acc["clmm_active"] = not acc.get("clmm_active", False)
        elif "POOM" in text:
            acc["poom_active"] = not acc.get("poom_active", False)
        elif "BONUONG" in text:
            acc["bonuong_active"] = not acc.get("bonuong_active", False)
        elif "LAUCUA" in text:
            acc["lau_cua_active"] = not acc.get("lau_cua_active", False)
        save_config(config)
        await update.message.reply_text("✅ Đã cập nhật trạng thái BẬT/TẮT săn code thành công!", reply_markup=get_auto_code_keyboard())
        return

    if text == "⚙️ CẤU HÌNH THAM SỐ CODE":
        acc = config["auto_code_config"]
        click_status = "TẮT AUTO CLICK NÚT 🔴" if acc.get("auto_click_button", True) else "BẬT AUTO CLICK NÚT 🟢"
        kb = [
            [KeyboardButton("PARAMS_CODE_CLMM"), KeyboardButton("PARAMS_CODE_POOM")],
            [KeyboardButton("PARAMS_CODE_BONUONG"), KeyboardButton("PARAMS_CODE_LAUCUA")],
            [KeyboardButton(click_status), KeyboardButton("🎁 AUTO CODE")]
        ]
        await update.message.reply_text("Chọn loại Room Game muốn điều chỉnh thông số hoặc Tắt/Bật chế độ Tự động nhấn nút lấy code:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return

    if "AUTO CLICK NÚT" in text:
        acc = config["auto_code_config"]
        acc["auto_click_button"] = not acc.get("auto_click_button", True)
        save_config(config)
        st_txt = "BẬT KHỚP LỆNH CLICK NÚT 🟢" if acc["auto_click_button"] else "TẮT KHỚP LỆNH CLICK NÚT 🔴"
        await update.message.reply_text(f"✅ Đã cấu hình hệ thống: <b>{st_txt}</b> thành công!", reply_markup=get_auto_code_keyboard(), parse_mode="HTML")
        return

    if text.startswith("PARAMS_CODE_"):
        target_room_type = text.replace("PARAMS_CODE_", "").lower()
        context.user_data["editing_code_room"] = target_room_type
        kb = [
            [KeyboardButton("🔢 THAY ĐỔI SỐ CODE TỐI ĐA")],
            [KeyboardButton("⏳ THAY ĐỔI DELAY PHÁT HIỆN"), KeyboardButton("🔄 THAY ĐỔI DELAY HỒI CHIÊU")],
            [KeyboardButton("⚙️ CẤU HÌNH THAM SỐ CODE")]
        ]
        await update.message.reply_text(f"⚙️ Đang sửa tham số cho Room: <b>{target_room_type.upper()}</b>. Chọn thông số:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode="HTML")
        return

    if text in ["🔢 THAY ĐỔI SỐ CODE TỐI ĐA", "⏳ THAY ĐỔI DELAY PHÁT HIỆN", "🔄 THAY ĐỔI DELAY HỒI CHIÊU"]:
        room_type = context.user_data.get("editing_code_room", "clmm")
        step_map = {
            "🔢 THAY ĐỔI SỐ CODE TỐI ĐA": ("max_code", f"Nhập số lượng code tối đa muốn nhập mỗi lần quét của {room_type.upper()} (Ví dụ: 4):"),
            "⏳ THAY ĐỔI DELAY PHÁT HIỆN": ("delay_detect", f"Nhập số giây delay chờ khi thấy tin nhắn code gốc của {room_type.upper()} (Ví dụ: 2):"),
            "🔄 THAY ĐỔI DELAY HỒI CHIÊU": ("delay_retry", f"Nhập số giây delay hồi chiêu sau khi ăn xong (Ví dụ: 301):")
        }
        field, prompt = step_map[text]
        context.user_data["code_field_v2"] = field
        context.user_data["step"] = "typing_code_param_v2"
        await update.message.reply_text(prompt)
        return

    if step == "typing_code_param_v2":
        room_type = context.user_data.get("editing_code_room", "clmm")
        field = context.user_data.get("code_field_v2")
        param_key = f"{room_type}_params"
        try:
            val = int(text)
            if param_key not in config["auto_code_config"]:
                config["auto_code_config"][param_key] = {"max_code": 4, "delay_detect": 2, "delay_retry": 301}
            config["auto_code_config"][param_key][field] = val
            save_config(config)
            await update.message.reply_text(f"✅ Lưu thông số <code>{field}</code> của Room <b>{room_type.upper()}</b> thành giá trị: <b>{val}</b> thành công!", reply_markup=get_auto_code_keyboard(), parse_mode="HTML")
        except ValueError:
            await update.message.reply_text("❌ Vui lòng chỉ nhập ký tự số nguyên!")
        context.user_data["step"] = None
        return

    if text == "📋 DANH SÁCH CODE NHẬP ĐƯỢC":
        logs = config["auto_code_config"].get("history_logs", [])
        if not logs:
            await update.message.reply_text("📋 <b>DANH SÁCH LỊCH SỬ NHẬP CODE THÀNH CÔNG</b>\n──────────────────\n<i>(Chưa có mã code thành công nào được ghi nhận)</i>", parse_mode="HTML")
            return
        msg = "📋 <b>DANH SÁCH CODE TRÚNG THƯỞNG GẦN NHẤT:</b>\n────────────────━━━━━━━━━━━━\n"
        for item in logs[-25:]:
            msg += f"➔ <code>[{item.get('time')}]</code> <b>{item.get('code')}</b> | ID: {item.get('uid')} | Số Dư: {item.get('balance')}\n"
        await update.message.reply_text(msg, reply_markup=get_auto_code_keyboard(), parse_mode="HTML")
        return

    if text == "🗑️ HỦY LIÊN KẾT / ĐÓNG SESSION":
        phones = udata.get("connected_phones", [])
        if not phones:
            await update.message.reply_text("❌ Bạn hiện chưa liên kết tài khoản Telegram chạy ngầm nào cả.", reply_markup=get_main_keyboard(uid))
            return
        kb = [[KeyboardButton(f"UNBIND_PHONE_{ph}")] for ph in phones]
        kb.append([KeyboardButton("⬅️ QUAY LẠI MENU CHÍNH")])
        await update.message.reply_text("⚠️ Chọn SĐT muốn ĐÓNG SẠCH SESSION và xóa dữ liệu chạy ngầm:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return

    if text.startswith("UNBIND_PHONE_"):
        phone_clean = text.replace("UNBIND_PHONE_", "").strip()
        if phone_clean in udata.get("connected_phones", []):
            client_key = f"{uid_str}_{phone_clean}"
            cl_client = telethon_clients.get(client_key)
            if cl_client:
                try:
                    if not cl_client.is_connected():
                        await cl_client.connect()
                    await cl_client.log_out()
                    await cl_client.disconnect()
                except Exception:
                    pass
                if client_key in telethon_clients:
                    del telethon_clients[client_key]
                STATS["acc_online"] = max(0, STATS["acc_online"] - 1)
                gc.collect()
            session_base = f"sessions/{client_key}.session"
            journal_file = f"sessions/{client_key}.session-journal"
            if os.path.exists(session_base):
                os.remove(session_base)
            if os.path.exists(journal_file):
                os.remove(journal_file)

            udata["connected_phones"].remove(phone_clean)
            save_config(config)
            await update.message.reply_text(f"🗑️ Đã giải phóng hoàn toàn và xóa sạch file session của SĐT {phone_clean}!", reply_markup=get_main_keyboard(uid))
        else:
            await update.message.reply_text("❌ Số điện thoại không tồn tại hệ thống.", reply_markup=get_main_keyboard(uid))
        return

    if text == "🔑 QUẢN LÝ HỆ THỐNG ID":
        if uid != MASTER_ADMIN_ID:
            return
        msg_id = "🔑 <b>DANH SÁCH ID PHÂN QUYỀN TRÊN HỆ THỐNG:</b>\n──────────────────\n"
        if not config["sub_ids"]:
            msg_id += "<i>(Chưa có ID con nào được cấp quyền)</i>\n"
        else:
            for sid, role in config["sub_ids"].items():
                msg_id += f"➔ ID: <code>{sid}</code> | Quyền: <b>{role.upper()}</b>\n"
        kb = [[KeyboardButton("➕ THÊM ID: MEMBER"), KeyboardButton("➕ THÊM ID: ADMIN")], [KeyboardButton("⬅️ QUAY LẠI MENU CHÍNH")]]
        await update.message.reply_text(msg_id, reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), parse_mode="HTML")
        return

    if text in ["➕ THÊM ID: MEMBER", "➕ THÊM ID: ADMIN"]:
        if uid != MASTER_ADMIN_ID:
            return
        role_assign = "member" if "MEMBER" in text else "admin"
        context.user_data["temp_role"] = role_assign
        context.user_data["step"] = "typing_new_id"
        await update.message.reply_text(f"📥 Vui lòng nhập số ID Telegram muốn phân quyền làm [<b>{role_assign.upper()}</b>]:", parse_mode="HTML")
        return

    if step == "typing_new_id":
        if uid != MASTER_ADMIN_ID:
            return
        if not text.isdigit():
            await update.message.reply_text("❌ ID Telegram phải là chuỗi ký tự số!")
            context.user_data["step"] = None
            return
        config["sub_ids"][text] = context.user_data.get("temp_role", "member")
        save_config(config)
        context.user_data["step"] = None
        await update.message.reply_text(f"✅ Đã thêm ID: <code>{text}</code> quyền <b>{config['sub_ids'][text].upper()}</b>!", reply_markup=get_main_keyboard(uid), parse_mode="HTML")
        return

    if text == "🧱 THÊM / XÓA ROOM GAME":
        if uid != MASTER_ADMIN_ID:
            return
        kb = [[KeyboardButton("➕ TẠO THÊM ROOM MỚI"), KeyboardButton("❌ XÓA ROOM HIỆN CÓ")], [KeyboardButton("⬅️ QUAY LẠI MENU CHÍNH")]]
        await update.message.reply_text("🧱 Cấu hình quản lý phòng game đấu động:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return

    if text == "➕ TẠO THÊM ROOM MỚI":
        if uid != MASTER_ADMIN_ID:
            return
        context.user_data["step"] = "add_room_step_1"
        await update.message.reply_text("📥 <b>[BƯỚC 1/3]</b> Nhập mã viết liền chữ thường (Vd: <code>clmm2</code>):", parse_mode="HTML")
        return

    if step == "add_room_step_1":
        if uid != MASTER_ADMIN_ID:
            return
        context.user_data["new_room_key"] = text.lower().strip()
        context.user_data["step"] = "add_room_step_2"
        await update.message.reply_text("📥 <b>[BƯỚC 2/3]</b> Nhập tên hiển thị Sàn (Vd: <code>Chẵn Lẻ Momo VIP</code>):", parse_mode="HTML")
        return

    if step == "add_room_step_2":
        if uid != MASTER_ADMIN_ID:
            return
        context.user_data["new_room_name"] = text
        context.user_data["step"] = "add_room_step_3"
        await update.message.reply_text("📥 <b>[BƯỚC 3/3]</b> Nhập Kênh lịch sử, Tên Bot, Dealer cách bởi dấu `|` (Vd: <code>@lichsuphienclmmgg|@NapRutClmm_BOT|@DealerClmm_BOT</code>):")
        return

    if step == "add_room_step_3":
        if uid != MASTER_ADMIN_ID:
            return
        try:
            parts = text.split("|")
            config["rooms_data"][context.user_data.get("new_room_key")] = {
                "name": context.user_data.get("new_room_name"),
                "channel": parts[0].strip(),
                "code_room": parts[0].strip(),
                "bot": parts[1].strip(),
                "dealer": parts[2].strip() if len(parts) > 2 else parts[1].strip(),
                "icon": "🎲",
                "patterns": [r'[A-Z0-9]{5,30}']
            }
            save_config(config)
            for k_uid in config["users_data"].keys():
                init_user_if_not_exists(k_uid)
            await update.message.reply_text("🎉 Khởi tạo thành công sàn đấu mới!", reply_markup=get_main_keyboard(uid))
        except Exception:
            await update.message.reply_text("❌ Lỗi cấu trúc chuỗi.")
        context.user_data["step"] = None
        return

    if text == "❌ XÓA ROOM HIỆN CÓ":
        if uid != MASTER_ADMIN_ID:
            return
        kb = [[KeyboardButton(f"DELETE_ROOM_{k.upper()}")] for k in config["rooms_data"].keys()]
        kb.append([KeyboardButton("⬅️ QUAY LẠI MENU CHÍNH")])
        await update.message.reply_text("⚠️ Chọn sảnh đấu muốn xóa khỏi mã nguồn:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return

    if text.startswith("DELETE_ROOM_"):
        if uid != MASTER_ADMIN_ID:
            return
        target_rk = text.replace("DELETE_ROOM_", "").lower().strip()
        if target_rk in config["rooms_data"]:
            del config["rooms_data"][target_rk]
            for k_uid in config["users_data"].keys():
                if target_rk in config["users_data"][k_uid]["active_rooms"]:
                    del config["users_data"][k_uid]["active_rooms"][target_rk]
                if target_rk in config["users_data"][k_uid]["rooms_config"]:
                    del config["users_data"][k_uid]["rooms_config"][target_rk]
            save_config(config)
            await update.message.reply_text(f"🗑️ Đã xóa hoàn tất sàn dữ liệu {target_rk.upper()}.", reply_markup=get_main_keyboard(uid))
        return

    if text == "💰 QUẢN LÝ PHƯƠNG THỨC VỐN":
        rk = context.user_data.get("target_room")
        rc = udata["rooms_config"][rk]
        await update.message.reply_text(
            f"💰 <b>QUẢN LÝ VỐN SÀN: {config['rooms_data'][rk]['name'].upper()}</b>\n"
            f"────────────────────────────\n"
            f"Bấm trực tiếp vào các nút trạng thái bên dưới để thay đổi:",
            reply_markup=get_von_manage_keyboard(rc.get("quan_ly_von_type", "gap_thep")), parse_mode="HTML"
        )
        return

    if "📈 GẤP THẾP CŨ" in text:
        rk = context.user_data.get("target_room")
        udata["rooms_config"][rk]["quan_ly_von_type"] = "gap_thep"
        save_config(config)
        await update.message.reply_text("✅ Đã chuyển đổi trạng thái cược thành công sang: <b>GẤP THẾP HỆ SỐ</b>!", reply_markup=get_von_manage_keyboard("gap_thep"), parse_mode="HTML")
        return

    if "🛡️ FIBONACCI AN TOÀN" in text:
        rk = context.user_data.get("target_room")
        udata["rooms_config"][rk]["quan_ly_von_type"] = "fibonacci"
        save_config(config)
        await update.message.reply_text("🛡️ Đã chuyển đổi trạng thái cược thành công sang: <b>VỐN AN TOÀN FIBONACCI</b>!", reply_markup=get_von_manage_keyboard("fibonacci"), parse_mode="HTML")
        return

    if text == "🔄 RESET CHUỒI THẮNG/THUA ⚡":
        rk = context.user_data.get("target_room")
        if rk and rk in udata["rooms_config"]:
            rc = udata["rooms_config"][rk]
            rc["streak_win_ai"] = 0
            rc["streak_loss_ai"] = 0
            rc["streak_loss_bet"] = 0
            rc["max_streak_win_ai"] = 0
            rc["max_streak_loss_ai"] = 0
            rc["total_predictions"] = 0
            rc["total_wins"] = 0
            rc["accumulated_vong_profit"] = 0
            rc["remaining_rest_phiens"] = 0
            rc["current_logic_index"] = 0
            rc["last_prediction"] = ""
            rc["is_betting_locked"] = False
            rc["is_cầu_1_1_active"] = False
            rc["cau_history_tx"] = []
            rc["cau_history_cl"] = []
            rc["logic3_state"] = {"mode": "kep", "loss_count": 0, "win_count": 0}
            rc["logic4_state"] = {"mode": "kep", "loss_count": 0, "pattern": [], "choice": "", "waiting": False}
            save_config(config)

            msg_cache_key = f"{uid_str}_{rk}"
            if msg_cache_key in XX_NHANH_LAST_MSG_IDS:
                del XX_NHANH_LAST_MSG_IDS[msg_cache_key]

            await update.message.reply_text(f"🔄 Đã đặt lại toàn bộ kỉ lục chuỗi cũ và tổng số ván của sàn <b>{config['rooms_data'][rk]['name'].upper()}</b> về 0.", reply_markup=get_room_manage_keyboard(), parse_mode="HTML")
        return

    if text == "🚀 BẬT / TẮT ROOM":
        kb = [[KeyboardButton(f"TOGGLE_{k.upper()} ({'ON' if v else 'OFF'})")] for k, v in udata["active_rooms"].items()]
        kb.append([KeyboardButton("⬅️ QUAY LẠI MENU CHÍNH")])
        await update.message.reply_text("Chọn sảnh muốn BẬT/TẮT kiểm soát cược:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return

    if text.startswith("TOGGLE_"):
        match = re.match(r"^TOGGLE_([A-Z0-9_]+)\s*\(", text)
        if match:
            room_key = match.group(1).lower().strip()
            if room_key in udata["active_rooms"]:
                udata["active_rooms"][room_key] = not udata["active_rooms"][room_key]
                if udata["active_rooms"][room_key]:
                    udata["rooms_config"][room_key]["is_withdrawn_at_threshold"] = False
                    udata["rooms_config"][room_key]["is_betting_locked"] = False
                    if udata["rooms_config"][room_key].get("mode") == "xx_nhanh":
                        XX_NHANH_START_TIMES[f"{uid_str}_{room_key}"] = time.time()
                        msg_cache_key = f"{uid_str}_{room_key}"
                        if msg_cache_key in XX_NHANH_LAST_MSG_IDS:
                            del XX_NHANH_LAST_MSG_IDS[msg_cache_key]
                save_config(config)
                await update.message.reply_text(f"⚡ {config['rooms_data'][room_key]['name'].upper()}: {'BẬT GIÁM SÁT 🟢' if udata['active_rooms'][room_key] else 'TẮT GIÁM SÁT 🔴'}", reply_markup=get_main_keyboard(uid))
            else:
                await update.message.reply_text(f"❌ Không tìm thấy mã phòng: {room_key.upper()}")
        return

    if text == "🔄 CHUYỂN PHƯƠNG THỨC CƯỢC":
        kb = [
            [KeyboardButton("SETMODE_DU_DOAN"), KeyboardButton("SETMODE_CUOC_V1"), KeyboardButton("SETMODE_CUOC_V2")],
            [KeyboardButton("SETMODE_XX_NHANH"), KeyboardButton("SETMODE_AUTO_CUOC_V3")],
            [KeyboardButton("⬅️ QUAY LẠI MENU CHÍNH")]
        ]
        await update.message.reply_text("⚙️ Chọn chế độ vận hành Siêu AI:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return

    if text.startswith("SETMODE_"):
        chosen_mode = text.replace("SETMODE_", "").lower().strip()
        context.user_data["temp_mode"] = chosen_mode
        kb = [[KeyboardButton(f"APPLYMODE_{k.upper()}")] for k in config["rooms_data"].keys()]
        await update.message.reply_text(f"Chọn sàn muốn áp dụng chế độ {chosen_mode.upper()}:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return

    if text.startswith("APPLYMODE_"):
        rk = text.replace("APPLYMODE_", "").lower().strip()
        new_mode = context.user_data.get("temp_mode", "du_doan")
        if rk in udata["rooms_config"]:
            udata["rooms_config"][rk]["mode"] = new_mode
            udata["rooms_config"][rk]["is_betting_locked"] = False

            if new_mode in ["xx_nhanh", "auto_cuoc_v3"]:
                XX_NHANH_START_TIMES[f"{uid_str}_{rk}"] = time.time()
                msg_cache_key = f"{uid_str}_{rk}"
                if msg_cache_key in XX_NHANH_LAST_MSG_IDS:
                    del XX_NHANH_LAST_MSG_IDS[msg_cache_key]
                rc = udata["rooms_config"][rk]
                rc["is_betting_locked"] = False
                rc["last_prediction"] = ""
                rc["logic3_state"] = {"mode": "kep", "loss_count": 0, "win_count": 0}
                rc["logic4_state"] = {"mode": "kep", "loss_count": 0, "pattern": [], "choice": "", "waiting": False}
                save_config(config)
                context.user_data["target_room"] = rk
                mode_display = "XX NHANH" if new_mode == "xx_nhanh" else "AUTO CƯỢC V3"
                await update.message.reply_text(
                    f"⚡ Đã cài đặt chế độ <b>{mode_display}</b> cho sàn {config['rooms_data'][rk]['name'].upper()}.\n\n"
                    f"👉 Vui lòng chọn nhánh Logic thuật toán vận hành:",
                    reply_markup=get_xx_nhanh_logic_keyboard(), parse_mode="HTML"
                )
                return

            save_config(config)
            await update.message.reply_text(f"✅ Sàn {config['rooms_data'][rk]['name'].upper()} chuyển cấu hình sang: {udata['rooms_config'][rk]['mode'].upper()}", reply_markup=get_main_keyboard(uid))
        else:
            await update.message.reply_text(f"❌ Không thấy mã phòng: {rk.upper()}", reply_markup=get_main_keyboard(uid))
        return

    if text in ["🧠 CHỌN LOGIC 1", "🔮 CHỌN LOGIC 2", "⚡ CHỌN LOGIC 3 (KÉP/11)", "🎯 CHỌN LOGIC 4 (THỦ CÔNG)"]:
        rk = context.user_data.get("target_room")
        if not rk:
            await update.message.reply_text("❌ Không tìm thấy thông tin sàn hiện tại, vui lòng chọn lại qua cấu hình.", reply_markup=get_main_keyboard(uid))
            return

        if "LOGIC 1" in text:
            logic_choice = "logic_1"
            name_logic = "LOGIC 1 (Xúc xắc ma trận + Cầu bẻ 1-1)"
        elif "LOGIC 2" in text:
            logic_choice = "logic_2"
            name_logic = "LOGIC 2 (Ma trận phân tích 256 biến)"
        elif "LOGIC 3" in text:
            logic_choice = "logic_3"
            name_logic = "LOGIC 3 (Kép ↔ 11 + Nhánh 2)"
            if "logic3_state" not in udata["rooms_config"][rk]:
                udata["rooms_config"][rk]["logic3_state"] = {"mode": "kep", "loss_count": 0, "win_count": 0, "streak": 0}
        else:  # LOGIC 4
            logic_choice = "logic_4"
            name_logic = "LOGIC 4 (Thủ công 5 tay)"
            if "logic4_state" not in udata["rooms_config"][rk]:
                udata["rooms_config"][rk]["logic4_state"] = {"mode": "kep", "loss_count": 0, "pattern": [], "choice": "", "waiting": False}

        udata["rooms_config"][rk]["xx_nhanh_logic_type"] = logic_choice
        save_config(config)

        await update.message.reply_text(f"✅ Sàn {config['rooms_data'][rk]['name'].upper()} kích hoạt vận hành: <b>{name_logic}</b> thành công!", reply_markup=get_main_keyboard(uid), parse_mode="HTML")
        return

    if text == "🤖 AUTO CƯỢC ROOM (BẬT/TẮT)":
        rk = context.user_data.get("target_room")
        if not rk:
            await update.message.reply_text("❌ Vui lòng chọn sàn trước qua menu CẤU HÌNH VỐN & THÔNG SỐ.", reply_markup=get_main_keyboard(uid))
            return
        rc = udata["rooms_config"][rk]
        current = rc.get("auto_cuoc_enabled", False)
        rc["auto_cuoc_enabled"] = not current
        save_config(config)
        state = "🟢 BẬT" if rc["auto_cuoc_enabled"] else "🔴 TẮT"
        await update.message.reply_text(f"✅ Auto cược room {config['rooms_data'][rk]['name'].upper()} đã chuyển sang <b>{state}</b>!", reply_markup=get_xx_nhanh_logic_keyboard(), parse_mode="HTML")
        return

    if text == "🎛️ ĐỔI HỆ ANALYZE (T/X - C/L)":
        kb = [[KeyboardButton(f"HE_{k.upper()}")] for k in config["rooms_data"].keys()]
        kb.append([KeyboardButton("⬅️ QUAY LẠI MENU CHÍNH")])
        await update.message.reply_text("🎛️ Chọn sảnh đấu bạn muốn xoay vòng Hệ Phân Tích cược:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return

    if text.startswith("HE_"):
        rk = text.replace("HE_", "").lower().strip()
        if rk in udata["rooms_config"]:
            rc = udata["rooms_config"][rk]
            current_he = rc.get("he_phan_tich", "tx")
            he_map = {"tx": "cl", "cl": "tx"}
            he_names = {"tx": "¹ TÀI / XỈU 📈", "cl": "² CHẴN / LẺ 📉"}
            next_he = he_map.get(current_he, "tx")
            rc["he_phan_tich"] = next_he
            rc["last_prediction"] = ""
            save_config(config)
            await update.message.reply_text(f"🔄 Đổi hệ sàn {config['rooms_data'][rk]['name'].upper()} thành công ➔ <b>{he_names[next_he]}</b>", reply_markup=get_main_keyboard(uid), parse_mode="HTML")
        else:
            await update.message.reply_text(f"❌ Không tìm thấy mã phòng: {rk.upper()}")
        return

    if text == "⚙️ CẤU HÌNH VỐN & THÔNG SỐ":
        kb = [[KeyboardButton(f"MANAGE_{k.upper()}")] for k in config["rooms_data"].keys()]
        kb.append([KeyboardButton("⬅️ QUAY LẠI MENU CHÍNH")])
        await update.message.reply_text("Chọn sàn muốn thiết lập cấu hình tham số:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        return

    if text.startswith("MANAGE_"):
        rk = text.replace("MANAGE_", "").lower().strip()
        if rk in udata["rooms_config"]:
            context.user_data["target_room"] = rk
            await update.message.reply_text(f"🛠️ Đang mở bảng chiến thuật sàn: {config['rooms_data'][rk]['name'].upper()}.", reply_markup=get_room_manage_keyboard())
        else:
            await update.message.reply_text(f"❌ Không tìm thấy mã phòng: {rk.upper()}")
        return

    if text == "⏳ DELAY ĐẶT CƯỢC ALL ROOM ⏱️":
        context.user_data["step"] = "typing_delay_xx_nhanh"
        await update.message.reply_text("📥 Nhập số giây muốn delay giãn cách trước khi tự động đặt cược (Ví dụ: 10):")
        return

    if step == "typing_delay_xx_nhanh":
        rk = context.user_data.get("target_room")
        try:
            val = int(text)
            udata["rooms_config"][rk]["delay_bet_xx_nhanh"] = val
            save_config(config)
            await update.message.reply_text(f"✅ Đã lưu cấu hình delay đặt cược hệ thống: <b>{val} giây</b>!", reply_markup=get_room_manage_keyboard(), parse_mode="HTML")
        except ValueError:
            await update.message.reply_text("❌ Vui lòng nhập số nguyên hợp lệ!")
        context.user_data["step"] = None
        return

    if text == "🤖 CẤU HÌNH AUTO RÚT (2 BƯỚC)":
        context.user_data["step"] = "setup_withdraw_step_1"
        await update.message.reply_text("💰 <b>[BƯỚC 1]</b> Nhập mốc số dư sàn game đạt mốc sẽ kích hoạt rút (Ví dụ: 160000):", parse_mode="HTML")
        return

    if step == "setup_withdraw_step_1":
        try:
            context.user_data["temp_nguong_rut"] = int(text)
            context.user_data["step"] = "setup_withdraw_step_2"
            await update.message.reply_text(f"💵 <b>[BƯỚC 2]</b> Khi ví đạt mốc, bạn muốn tự động gửi lệnh rút bao nhiêu? (Ví dụ: 50000):", parse_mode="HTML")
        except ValueError:
            await update.message.reply_text("❌ Nhập số lỗi.")
            context.user_data["step"] = None
        return

    if step == "setup_withdraw_step_2":
        try:
            rk = context.user_data.get("target_room")
            udata["rooms_config"][rk]["nguong_rut_tien"] = context.user_data.get("temp_nguong_rut")
            udata["rooms_config"][rk]["so_tien_rut_auto"] = int(text)
            udata["rooms_config"][rk]["is_withdrawn_at_threshold"] = False
            save_config(config)
            await update.message.reply_text(f"✅ Đã lưu cấu hình tự động rút tiền cho sàn {config['rooms_data'][rk]['name'].upper()}!", reply_markup=get_room_manage_keyboard())
        except ValueError:
            await update.message.reply_text("❌ Lỗi.")
        context.user_data["step"] = None
        return

    if text in ["💸 NHẬP VỐN BAN ĐẦU", "✖️ NHẬP HỆ SỐ NHÂN (GẤP THẾP)", "🛑 NHẬP CẮT LỖ", "🏆 NHẬP CHỐT LỜI", "🎯 CHỐT LỜI LẺ VÒNG 💎", "⏳ NGHỈ SỐ PHIÊN ⏱️", "🚨 CẮT CHUỒI THUA 📉"]:
        param_map = {
            "💸 NHẬP VỐN BAN ĐẦU": ("von_ban_dau", "Nhập mức tiền cược gốc ban đầu (VND):"),
            "✖️ NHẬP HỆ SỐ NHÂN (GẤP THẾP)": ("he_so_nhan", "Nhập hệ số nhân khi gấp thếp thua (Vd: 2.1):"),
            "🛑 NHẬP CẮT LỖ": ("cat_lo", "Nhập tổng hạn mức cắt lỗ bảo toàn ví (VND):"),
            "🏆 NHẬP CHỐT LỜI": ("chot_loi", "Nhập tổng hạn mức chốt lời mục tiêu (VND):"),
            "🎯 CHỐT LỜI LẺ VÒNG 💎": ("chot_loi_le_vong", "Nhập số tiền lãi tích lũy mỗi chuỗi ngắn để dừng nghỉ:"),
            "⏳ NGHỈ SỐ PHIÊN ⏱️": ("nghi_so_phien", "Nhập số lượng phiên cần nghỉ xả cầu sau khi chốt vòng:"),
            "🚨 CẮT CHUỒI THUA 📉": ("cat_chuoi_thua", "Nhập số ván thua liên tiếp tối đa để bóp phanh dừng cược:")
        }
        field, prompt = param_map[text]
        context.user_data["target_field"] = field
        context.user_data["step"] = "typing_normal_value"
        await update.message.reply_text(prompt)
        return

    if step == "typing_normal_value":
        rk = context.user_data.get("target_room")
        field = context.user_data.get("target_field")
        try:
            val = float(text) if field == "he_so_nhan" else int(text)
            udata["rooms_config"][rk][field] = val
            save_config(config)
            brk = get_von_manage_keyboard(udata["rooms_config"][rk].get("quan_ly_von_type", "gap_thep")) if field == "he_so_nhan" else get_room_manage_keyboard()
            await update.message.reply_text(f"✅ Đã lưu cấu hình thông số thành công!", reply_markup=brk)
        except ValueError:
            await update.message.reply_text("❌ Lỗi định dạng số!")
        context.user_data["step"] = None
        return

    if text == "🔍 TÌM CẦU TOÀN BỘ":
        if not udata["active_rooms"] or not any(udata["active_rooms"].values()):
            await update.message.reply_text("❌ Bạn chưa bật sàn nào. Hãy bật ít nhất 1 sàn để tìm cầu.")
            return
        combined = {}
        for rk, active in udata["active_rooms"].items():
            if not active:
                continue
            rc = udata["rooms_config"][rk]
            hist_tx = rc.get("cau_history_tx", [])
            hist_cl = rc.get("cau_history_cl", [])
            tx_str = " ".join(hist_tx[-10:]) if hist_tx else ""
            cl_str = " ".join(hist_cl[-10:]) if hist_cl else ""
            combined[rk] = {"tx": tx_str, "cl": cl_str}

        if not combined:
            await update.message.reply_text("Chưa có dữ liệu cầu trên các sàn đang bật.")
            return

        msg = "🔍 <b>CẦU TOÀN BỘ CÁC SÀN ĐANG BẬT</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        for rk, data in combined.items():
            room_name = config["rooms_data"][rk]["name"]
            msg += f"<b>{room_name.upper()}</b>:\n"
            msg += f"  TX: <code>{data['tx']}</code>\n"
            msg += f"  CL: <code>{data['cl']}</code>\n"
            msg += "────────────────────\n"
        await update.message.reply_text(msg, parse_mode="HTML")
        return

    if text == "🎯 BẮT CẦU 3 SỐ (AUTO)":
        target_rk = None
        for rk, active in udata["active_rooms"].items():
            if active and udata["rooms_config"][rk]["mode"] in ["cuoc_v1", "cuoc_v2", "xx_nhanh", "auto_cuoc_v3"]:
                target_rk = rk
                break
        if not target_rk:
            await update.message.reply_text("❌ Không tìm thấy sàn nào đang chạy chế độ cược. Vui lòng chuyển mode cược trước.")
            return

        rc = udata["rooms_config"][target_rk]
        if not rc.get("bat_cau_3so", False):
            rc["bat_cau_3so"] = True
            save_config(config)
            await update.message.reply_text(f"✅ Đã bật chế độ đánh bắt cầu 3 số tự động cho sàn {config['rooms_data'][target_rk]['name'].upper()}.")
        else:
            rc["bat_cau_3so"] = False
            save_config(config)
            await update.message.reply_text(f"🔴 Đã tắt chế độ đánh bắt cầu 3 số tự động cho sàn {config['rooms_data'][target_rk]['name'].upper()}.")
        return

    if text == "➕ THÊM TÀI KHOẢN CHÍNH":
        context.user_data["step"] = "typing_phone"
        await update.message.reply_text("📥 Nhập số điện thoại tài khoản Telegram cần treo lệnh chạy đa sàn (Vd: +849xxx):")
        return

    if step == "typing_phone":
        context.user_data["user_phone"] = text
        phone_clean = text.replace("+", "").strip()
        cl = TelegramClient(f"sessions/{uid_str}_{phone_clean}", API_ID, API_HASH)
        await cl.connect()
        req = await cl.send_code_request(text)
        context.user_data["phone_code_hash"] = req.phone_code_hash
        context.user_data["step"] = "enter_otp_main"
        await update.message.reply_text("🔑 Nhập mã OTP dạng ký tự nhỏ (Ví dụ: ¹²³⁴⁵):")
        return

    if step == "enter_otp_main":
        raw_text = text.strip()
        decoded_otp = "".join(SUPERSCRIPT_MAP.get(char, "") for char in raw_text)
        if len(decoded_otp) != 5:
            await update.message.reply_text("⚠️ Sai định dạng OTP chuỗi nhỏ!")
            return
        phone = context.user_data.get("user_phone")
        phone_clean = phone.replace("+", "").strip()
        cl = TelegramClient(f"sessions/{uid_str}_{phone_clean}", API_ID, API_HASH)
        await cl.connect()
        try:
            await cl.sign_in(phone=phone, code=decoded_otp, phone_code_hash=context.user_data.get("phone_code_hash"))
            if phone_clean not in udata["connected_phones"]:
                udata["connected_phones"].append(phone_clean)
            save_config(config)
            telethon_clients[f"{uid_str}_{phone_clean}"] = cl
            STATS["acc_online"] += 1

            await bind_single_client_to_all_rooms(context.application, uid_str, phone_clean, cl)

            context.user_data["step"] = None
            await update.message.reply_text(f"🎉 Kết nối THÀNH CÔNG SĐT: {phone_clean}. Đã phân luồng chạy tự động đa sàn!", reply_markup=get_main_keyboard(uid))
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi kích hoạt session: {e}", reply_markup=get_main_keyboard(uid))
            context.user_data["step"] = None
        return

    if text in ["📊 TRẠNG THÁI ACC CỦA TÔI", "⬅️ QUAY LẠI"]:
        report = f"📊 <b>BÁO CÁO HỆ THỐNG TBTOOL VIP PLATINUM V99.9</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        he_names = {"tx": "TÀI/XỈU 📊", "cl": "CHẴN/LẺ 📈"}
        phones_str = ", ".join(udata.get("connected_phones", [])) if udata.get("connected_phones") else "Chưa có"
        report += f"📱 <b>Tài khoản chạy ngầm:</b> <code>{phones_str}</code>\n"
        report += "────────────────────\n"
        for rk, rm in config["rooms_data"].items():
            if rk not in udata["rooms_config"]:
                continue
            rc = udata["rooms_config"][rk]
            status_icon = "🟢 ACTIVE" if udata["active_rooms"].get(rk, False) else "🔴 DISABLED"
            v_type = "GẤP THẾP" if rc.get("quan_ly_von_type") == "gap_thep" else "FIBONACCI🛡️"
            p_total = rc.get("total_predictions", 0)
            w_rate = (rc.get("total_wins", 0) / p_total * 100) if p_total > 0 else 0.0

            curr_logic = rc.get("xx_nhanh_logic_type", "logic_1").upper()

            report += (
                f"{rm.get('icon', '🎲')} <b>SÀN: {rm['name'].upper()}</b> [{status_icon}]\n"
                f"  ↳ Chế độ chạy: <b>{rc.get('mode','').upper()}</b> ({curr_logic})\n"
                f"  ↳ Quản lý vốn: <b>{v_type}</b> | Hệ: <b>{he_names.get(rc.get('he_phan_tich','tx'), 'TÀI/XỈU')}</b>\n"
                f"  ↳ Ví hiện tại: <code>{rc.get('current_balance', 0):,} đ</code>\n"
                f"  ↳ Thắng/Tổng: <b>{rc.get('total_wins',0)}/{p_total} ván</b> ({w_rate:.1f}%)\n"
                f"  ↳ Kỷ lục chuỗi AI: Thắng max: {rc.get('max_streak_win_ai', 0)} | Thua max: {rc.get('max_streak_loss_ai', 0)}\n"
                f"  ↳ Lãi Vòng Hiện Tại: <code>{rc.get('accumulated_vong_profit', 0):,} đ</code> / {rc.get('chot_loi_le_vong', 0):,} đ\n"
                f"  ↳ Delay All Room: <code>{rc.get('delay_bet_xx_nhanh', 10)} giây</code>\n"
                f"────────────────────\n"
            )
        await update.message.reply_text(report, reply_markup=get_main_keyboard(uid), parse_mode="HTML")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uid_str = str(uid)
    if uid != MASTER_ADMIN_ID and uid_str not in config["sub_ids"]:
        await send_denied_banner(update)
        return
    init_user_if_not_exists(uid_str)
    welcome_msg = (
        f"⚡ <b>WELCOME TO TBTOOL SYSTEM MULTI-ROOM CHỜ VÉT CODE v99.9</b> ⚡\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛠 <b>BẢN CẬP NHẬT PHÂN CHIA HỆ THỐNG MÃ CODE CHUẨN XÁC:</b>\n"
        f"➔ 🔘 <b>Ưu Tiên Phân Quyền:</b> Đẩy luồng Acc ADMIN nạp code trước, MEMBER sau.\n"
        f"➔ ⏳ <b>Cơ Chế Delay Hồi Chiêu:</b> Chạy chính xác delay mốc giây `{config['auto_code_config']['clmm_params']['delay_retry']}s` cách quãng.\n"
        f"➔ 🔢 <b>Max Mảng Lệnh Code:</b> Hạn mức `{config['auto_code_config']['clmm_params']['max_code']}` mã chuẩn xác theo lệnh quét.\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(welcome_msg, reply_markup=get_main_keyboard(uid), parse_mode="HTML")

def add_code_log(code_str, uid_str, balance_str):
    now_tz = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
    time_format = now_tz.strftime("%Y/%m/%d %H:%M:%S")
    log_item = {"time": time_format, "code": code_str, "uid": uid_str, "balance": balance_str}
    config["auto_code_config"]["history_logs"].append(log_item)
    save_config(config)

async def process_single_account_codes(bot_app, target_bot, uid_str, phone_clean, codes_to_send, delay_retry, room_key, code_type):
    global DAILY_SUCCESS
    cl_client = telethon_clients.get(f"{uid_str}_{phone_clean}")
    if not cl_client:
        return

    key_cooldown = f"{phone_clean}_{room_key}"

    for code in codes_to_send:
        key_success_btn = f"{phone_clean}_{room_key}_button_code"
        if code_type == "BUTTON" and DAILY_SUCCESS.get(key_success_btn) is True:
            continue

        try:
            if not cl_client.is_connected():
                await cl_client.connect()

            sent_msg = await cl_client.send_message(target_bot, f"/code {code}")
            await asyncio.sleep(1.8)

            is_success = False
            async for message in cl_client.iter_messages(target_bot, limit=3):
                if message.text and ("Nhập giftcode" in message.text or "thành công" in message.text or "⚠️" not in message.text and "❇️" in message.text):
                    if code_type == "TEXT":
                        used_codes_cache.add(code)

                    STATS["codes_entered"] += 1
                    STATS["latest_code"] = code

                    gia_tri = re.search(r'Giá trị:\s*([0-9.,]+)', message.text)
                    so_du = re.search(r'Số dư hiện tại:\s*([0-9.,]+)', message.text)

                    val_str = gia_tri.group(1).replace(".", "").replace(",", "") if gia_tri else "3333"
                    sd_str = so_du.group(1) if so_du else "Không rõ"

                    val_int = int(val_str) if val_str.isdigit() else 0
                    STATS["total_lua"] += val_int

                    if code_type == "BUTTON":
                        DAILY_SUCCESS[key_success_btn] = True
                        save_daily_state(DAILY_SUCCESS)

                    is_success = True
                    add_code_log(code, uid_str, sd_str)
                    render_success_alert(code, val_int, sd_str, phone_clean, code_type)

                    send_termux_notification(
                        f"🌾 TBTOOL HÚP LÚA CODE {code_type} !",
                        f"Mã: {code} | Giá trị: {val_int:,} đ | Ví: {sd_str} đ | Acc: {phone_clean}"
                    )

                    if room_key in EVENT_CODE_MANAGER and code in EVENT_CODE_MANAGER[room_key]["codes"]:
                        EVENT_CODE_MANAGER[room_key]["codes"][code] = "USED"
                    break

            if not is_success:
                try:
                    async for bad_msg in cl_client.iter_messages(target_bot, limit=2):
                        await cl_client.delete_messages(target_bot, [sent_msg.id, bad_msg.id])
                except Exception:
                    pass

        except Exception:
            pass

    if delay_retry > 0:
        ACCOUNT_COOLDOWN_MANAGER[key_cooldown] = time.time() + delay_retry

async def trigger_send_code(bot_app, target_bot, code_list, delay_retry, room_key="clmm", code_type="TEXT"):
    if not code_list:
        return

    if code_type == "TEXT":
        code_list = [c for c in code_list if c not in used_codes_cache]
    if not code_list:
        return

    admin_queue = []
    member_queue = []

    for uid_str, udata in config["users_data"].items():
        phones = udata.get("connected_phones", [])
        is_admin_role = udata.get("is_admin", False)

        for phone_clean in phones:
            key_cooldown = f"{phone_clean}_{room_key}"
            if key_cooldown in ACCOUNT_COOLDOWN_MANAGER:
                if time.time() < ACCOUNT_COOLDOWN_MANAGER[key_cooldown]:
                    continue

            account_package = {"uid": uid_str, "phone": phone_clean}
            if is_admin_role:
                admin_queue.append(account_package)
            else:
                member_queue.append(account_package)

    if admin_queue:
        admin_tasks = []
        for acc in admin_queue:
            admin_tasks.append(asyncio.create_task(
                process_single_account_codes(bot_app, target_bot, acc["uid"], acc["phone"], code_list, delay_retry, room_key, code_type)
            ))
        await asyncio.gather(*admin_tasks)

    if member_queue:
        await asyncio.sleep(1.5)
        member_tasks = []
        for acc in member_queue:
            member_tasks.append(asyncio.create_task(
                process_single_account_codes(bot_app, target_bot, acc["uid"], acc["phone"], code_list, delay_retry, room_key, code_type)
            ))
        await asyncio.gather(*member_tasks)

async def start_event_countdown_veting(bot_app, room_key, list_codes):
    acc = config["auto_code_config"]
    rm_meta = config["rooms_data"].get(room_key)
    if not rm_meta:
        return

    wait_seconds = 300
    param_k = f"{room_key}_params"
    room_p = acc.get(param_k, {"max_code": 4, "delay_detect": 1, "delay_retry": 301})
    max_c = room_p.get("max_code", 4)

    await asyncio.sleep(wait_seconds)

    evt_data = EVENT_CODE_MANAGER.get(room_key)
    if not evt_data:
        return

    alive_codes = [c for c, status in evt_data["codes"].items() if status == "ALIVE"]

    if alive_codes:
        alive_codes = alive_codes[:max_c]
        console.print(f"[bold green]🔥 [KÍCH HOẠT NHẬP VÉT 5 PHÚT] Tiến hành quét hốt {len(alive_codes)} mã còn tồn dư![/bold green]")
        asyncio.create_task(trigger_send_code(bot_app, rm_meta["bot"], alive_codes, room_p.get("delay_retry", 301), room_key, "TEXT"))

    if room_key in EVENT_CODE_MANAGER:
        del EVENT_CODE_MANAGER[room_key]

async def check_and_kill_used_codes(room_key, raw_text):
    evt_data = EVENT_CODE_MANAGER.get(room_key)
    if not evt_data:
        return

    upper_msg = raw_text.upper()
    if any(kw in upper_msg for kw in ["ĐÃ ĐƯỢC SỬ DỤNG", "ĐÃ HÚP", "THÀNH CÔNG", "NHẬP CODE", "HẾT LƯỢT", "HẾT LƯỢT NHẬP"]):
        for code in list(evt_data["codes"].keys()):
            if code in upper_msg and evt_data["codes"][code] == "ALIVE":
                evt_data["codes"][code] = "USED"
                console.print(f"[bold red]❌ [GẠCH TÊN CACHING] Mã {code} của {room_key.upper()} đã bị húp công khai hoặc hết hạn! Huỷ luồng vét.[/bold red]")

# Hàm mới để tự động bấm nút bằng Telethon
async def click_telegram_button(cl_client, bot_entity, msg_id):
    try:
        # Lấy lại tin nhắn chứa nút bấm
        msg = await cl_client.get_messages(bot_entity, ids=msg_id)
        if not msg or not msg.buttons:
            return False
        
        # Duyệt qua từng nút trong tin nhắn
        for row in msg.buttons:
            for button in row:
                btn_text = button.text.lower()
                # Chỉ bấm nếu có từ khóa liên quan đến giftcode/start
                if any(k in btn_text for k in ["mở", "nhập", "code", "lấy", "start", "click", "🎁", "giftcode"]):
                    if button.url: # Nếu là nút dạng URL start=
                        if "start=" in button.url.lower():
                            # Gửi lệnh Start tương đương với việc bấm nút
                            start_param_match = re.search(r'start=([A-Za-z0-9_\-]+)', button.url, re.IGNORECASE)
                            if start_param_match:
                                await cl_client(functions.messages.StartBotRequest(
                                    bot=bot_entity, peer=bot_entity, start_param=start_param_match.group(1)
                                ))
                                return True
                    elif button.data: # Nếu là nút callback bình thường
                        await cl_client(GetBotCallbackAnswerRequest(
                            peer=bot_entity, msg_id=msg_id, data=button.data
                        ))
                        return True
    except Exception as e:
        console.print(f"[red]Lỗi Click Button: {e}[/red]")
    return False

async def parse_and_hunt_codes(bot_app, chat_title, raw_text, sender_username=None, event=None):
    if sender_username:
        chk_user = f"@{sender_username}".lower()
        if chk_user in BOT_EXCLUDE_LIST:
            return

    acc = config["auto_code_config"]
    final_text = raw_text if raw_text else ""

    room_key = "clmm"
    if "pomm" in chat_title.lower() or "soicaupomm" in chat_title.lower() or "pomeranian" in chat_title.lower():
        room_key = "poom"
    elif "bonuong" in chat_title.lower():
        room_key = "bonuong"
    elif "laucua" in chat_title.lower() or "lẩu cua" in chat_title.lower():
        room_key = "lau_cua"

    rm_meta = config["rooms_data"].get(room_key, config["rooms_data"]["clmm"])
    is_room_code_active = acc.get(f"{room_key}_active", False)
    if not is_room_code_active:
        return

    if room_key in EVENT_CODE_MANAGER:
        await check_and_kill_used_codes(room_key, final_text)

    param_k = f"{room_key}_params"
    room_p = acc.get(param_k, {"max_code": 4, "delay_detect": 2, "delay_retry": 301})
    max_c = room_p.get("max_code", 4)

    # 1. Xử lý ảnh (OCR) nếu có
    if event and event.message and event.message.photo:
        try:
            if not os.path.exists("sessions"):
                os.makedirs("sessions", exist_ok=True)
            temp_img_path = f"sessions/temp_ocr_{int(time.time())}_{random.randint(1000,9999)}.jpg"
            await event.message.download_media(file=temp_img_path)
            STATS["images_scanned"] += 1

            if os.path.exists(temp_img_path):
                img = Image.open(temp_img_path)
                ocr_text = pytesseract.image_to_string(img).upper()
                final_text += "\n" + ocr_text
                img.close()
                os.remove(temp_img_path)
        except Exception:
            pass

    # 2. Xử lý tự động bấm nút (Bỏ qua cơ chế click từ event gốc, dùng Telethon click)
    if acc.get("auto_click_button", True):
        # Kiểm tra xem tin nhắn này có nút bấm không
        if event and event.message and event.message.buttons:
            for uid_str, udata in config["users_data"].items():
                for phone_clean in udata.get("connected_phones", []):
                    key_success_btn = f"{phone_clean}_{room_key}_button_code"
                    if DAILY_SUCCESS.get(key_success_btn) is True:
                        continue # Đã ăn code nút hôm nay rồi

                    cl_client = telethon_clients.get(f"{uid_str}_{phone_clean}")
                    if cl_client:
                        try:
                            # Gọi hàm click nút trên Telethon
                            clicked = await click_telegram_button(cl_client, rm_meta["bot"], event.message.id)
                            if clicked:
                                await asyncio.sleep(2.0) # Chờ bot reply
                                
                                # Đọc tin nhắn phản hồi gần nhất từ bot click
                                async for msg_reply in cl_client.iter_messages(rm_meta["bot"], limit=2):
                                    if msg_reply.text:
                                        extracted_text = msg_reply.text.upper()
                                        detected_list = []
                                        # Quét lấy mã code dựa vào regex
                                        for pattern in rm_meta.get("patterns", []):
                                            finds_cb = re.findall(pattern, extracted_text, re.IGNORECASE)
                                            for r_code in finds_cb:
                                                detected_list.append(fix_ocr_code(r_code))

                                        if detected_list:
                                            detected_list = list(set(detected_list))[:max_c]
                                            # Gửi lệnh /code kèm mã đã lấy được
                                            asyncio.create_task(trigger_send_code(bot_app, rm_meta["bot"], detected_list, room_p.get("delay_retry", 301), room_key, "BUTTON"))
                                            break
                                break # Chỉ bấm 1 lần cho sự kiện này
                        except Exception:
                            pass

    # 3. Quét Text để tìm code bằng Regex
    found_codes = []
    day_month_str = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime("%d%m")
    dynamic_regex = r'\b(CLMM-' + day_month_str + r'-[A-Z0-9]+)\b'
    matches_dyn = re.findall(dynamic_regex, final_text, re.IGNORECASE)
    if matches_dyn:
        found_codes.extend([m.upper() for m in matches_dyn])

    for pattern in rm_meta.get("patterns", []):
        finds = re.findall(pattern, final_text, re.IGNORECASE)
        for raw_code in finds:
            found_codes.append(fix_ocr_code(raw_code))

    if not found_codes:
        return

    unique_detected = list(set(found_codes))[:max_c]
    delay_detect = room_p.get("delay_detect", 2)

    if unique_detected:
        if delay_detect > 0:
            await asyncio.sleep(delay_detect)
        asyncio.create_task(trigger_send_code(bot_app, rm_meta["bot"], unique_detected, room_p.get("delay_retry", 301), room_key, "TEXT"))

    if room_key not in EVENT_CODE_MANAGER:
        EVENT_CODE_MANAGER[room_key] = {
            "codes": {code: "ALIVE" for code in unique_detected},
            "start_time": time.time()
        }
        asyncio.create_task(start_event_countdown_veting(bot_app, room_key, unique_detected))
    else:
        for c in unique_detected:
            if c not in EVENT_CODE_MANAGER[room_key]["codes"]:
                EVENT_CODE_MANAGER[room_key]["codes"][c] = "ALIVE"

def find_matching_logic_index(history_list, system_he):
    return random.randint(0, 255)

async def process_independent_flow(bot_app, target_user_id, room_key, raw_text, event=None):
    uid_str = str(target_user_id)
    udata = config["users_data"].get(uid_str)
    if not udata or not udata["active_rooms"].get(room_key, False):
        return
    rc = udata["rooms_config"][room_key]
    rm = config["rooms_data"][room_key]
    s_icon = rm.get("icon", "🎲")

    upper_text = raw_text.upper() if raw_text else ""
    is_xx_nhanh_mode = (rc.get("mode", "du_doan") in ["xx_nhanh", "auto_cuoc_v3"])
    chosen_logic_type = rc.get("xx_nhanh_logic_type", "logic_1")

    actual_tx, actual_cl = None, None
    is_dice_event = False
    next_door_predicted = None
    dice_val = None

    # 1. Nếu là dice từ bot (media)
    if event and event.message and event.message.media and hasattr(event.message.media, 'value'):
        dice_val = event.message.media.value
        phien_id = f"DICE_{event.message.id}"
        lock_key = f"lock_{target_user_id}_{room_key}_{phien_id}"
        if lock_key in PROCESSED_PHIEN_LOCK:
            return
        if rc.get("last_processed_phien_id") == phien_id:
            return
        PROCESSED_PHIEN_LOCK.add(lock_key)
        rc["last_processed_phien_id"] = phien_id

        is_dice_event = True
        actual_tx = "TÀI" if dice_val >= 4 else "XỈU"
        actual_cl = "CHẴN" if dice_val % 2 == 0 else "LẺ"

        if dice_val in [1, 2, 3]:
            next_door_predicted = "XỈU"
        elif dice_val in [4, 5, 6]:
            next_door_predicted = "TÀI"
        else:
            return

    # 2. Nếu là text từ kênh lịch sử phiên
    else:
        dice_find = re.search(r'(?:^|\s)([1-6])\s+([1-6])\s+([1-6])', raw_text if raw_text else "")
        if not dice_find:
            dice_find = re.search(r'([1-6])\s*[\+\s,]\s*([1-6])\s*[\+\s,]\s*([1-6])', raw_text if raw_text else "")

        if room_key == "lau_cua":
            if not dice_find:
                return

        if room_key != "lau_cua" and not dice_find:
            valid_keywords = ["PHIÊN", "MÃ PHIÊN", "MÃ TRÒ CHƠI", "KỲ", "KẾT QUẢ", "KQ:", "XỈU", "TÀI", "CHẴN", "LẺ", "XÚC XẮC", "KẾT QUẢ PHIÊN"]
            if not any(kw in upper_text for kw in valid_keywords):
                return

        phien_match = re.search(r'\b(\d{4,7})\b', raw_text if raw_text else "")
        phien_id = phien_match.group(1) if phien_match else f"TXT_{int(time.time())}"

        lock_key = f"lock_{target_user_id}_{room_key}_{phien_id}"
        if lock_key in PROCESSED_PHIEN_LOCK:
            return
        if rc.get("last_processed_phien_id") == phien_id:
            return
        PROCESSED_PHIEN_LOCK.add(lock_key)
        rc["last_processed_phien_id"] = phien_id

        if dice_find:
            h1, h2, h3 = int(dice_find.group(1)), int(dice_find.group(2)), int(dice_find.group(3))
            total_sum = h1 + h2 + h3
            dice_val = total_sum
            actual_tx = "TÀI" if total_sum >= 11 else "XỈU"
            actual_cl = "CHẴN" if total_sum % 2 == 0 else "LẺ"

            if room_key == "lau_cua" or is_xx_nhanh_mode:
                is_dice_event = True
                if total_sum in [3, 4, 5, 6, 7, 8, 9, 10]:
                    next_door_predicted = "XỈU"
                else:
                    next_door_predicted = "TÀI"
        else:
            if "TÀI" in upper_text or "🔵" in raw_text:
                actual_tx = "TÀI"
            elif "XỈU" in upper_text or "🔴" in raw_text:
                actual_tx = "XỈU"
            if "CHẴN" in upper_text or "⚪" in raw_text:
                actual_cl = "CHẴN"
            elif "LẺ" in upper_text or "⚫" in raw_text:
                actual_cl = "LẺ"

    if not actual_tx or not actual_cl:
        return

    rc["is_betting_locked"] = False

    if rc.get("remaining_rest_phiens", 0) > 0:
        rc["remaining_rest_phiens"] -= 1
        if rc["remaining_rest_phiens"] == 0:
            await send_system_notification(bot_app, target_user_id, rm["name"], s_icon, "Nghỉ Số Phiên", "HOÀN THÀNH NGHỈ XẢ ⏱️", rc.get("current_balance", 0), "Quay lại luồng chiến.")
        rc["history_tx"].append(actual_tx)
        rc["history_cl"].append(actual_cl)
        save_config(config)
        if rc["mode"] in ["cuoc_v1", "cuoc_v2", "xx_nhanh", "auto_cuoc_v3"]:
            asyncio.create_task(trigger_next_xx_nhanh_bet(bot_app, target_user_id, room_key))
        return

    he_hien_tai = rc.get("he_phan_tich", "tx")
    target_actual_result = actual_tx if he_hien_tai == "tx" else actual_cl
    is_du_doan_mode = (rc.get("mode", "du_doan") == "du_doan")

    last_pred = str(rc.get("last_prediction", "")).upper()
    is_valid_system_pred = False
    if he_hien_tai == "tx" and last_pred in ["TÀI", "XỈU"]:
        is_valid_system_pred = True
    elif he_hien_tai == "cl" and last_pred in ["CHẴN", "LẺ"]:
        is_valid_system_pred = True

    if last_pred and is_valid_system_pred:
        bet_money = rc["current_bet_step"] if rc["current_bet_step"] > 0 else rc["von_ban_dau"]
        if last_pred == target_actual_result:
            rc["total_predictions"] += 1
            rc["total_wins"] += 1
            rc["streak_win_ai"] += 1
            rc["max_streak_win_ai"] = max(rc.get("max_streak_win_ai", 0), rc["streak_win_ai"])
            rc["streak_loss_ai"] = 0
            rc["streak_loss_bet"] = 0

            if is_du_doan_mode:
                rc["accumulated_vong_profit"] = 0
            else:
                rc["accumulated_vong_profit"] += int(bet_money * 1.9) - bet_money
            result_status_string = "ĐÚNG ✅"
        else:
            rc["total_predictions"] += 1
            rc["streak_loss_ai"] += 1
            rc["max_streak_loss_ai"] = max(rc.get("max_streak_loss_ai", 0), rc["streak_loss_ai"])
            rc["streak_win_ai"] = 0
            rc["streak_loss_bet"] += 1
            if is_du_doan_mode:
                rc["accumulated_vong_profit"] = 0
            else:
                rc["accumulated_vong_profit"] -= bet_money
            result_status_string = "SAI ❌"

            if is_xx_nhanh_mode and chosen_logic_type == "logic_1" and rc.get("is_cầu_1_1_active", False):
                rc["is_cầu_1_1_active"] = False
                rc["streak_loss_ai"] = 0
    else:
        result_status_string = "KHỞI TẠO 🔄"
        rc["streak_win_ai"], rc["streak_loss_ai"], rc["streak_loss_bet"] = 0, 0, 0

    rc["last_match_result"] = result_status_string
    rc["history_tx"].append(actual_tx)
    rc["history_cl"].append(actual_cl)
    if len(rc["history_tx"]) > 20:
        rc["history_tx"].pop(0)
    if len(rc["history_cl"]) > 20:
        rc["history_cl"].pop(0)

    if not is_du_doan_mode and result_status_string in ["ĐÚNG ✅", "SAI ❌"]:
        cl_le_vong = rc.get("chot_loi_le_vong", 0)
        if cl_le_vong > 0 and rc["accumulated_vong_profit"] >= cl_le_vong:
            rc["remaining_rest_phiens"] = rc.get("nghi_so_phien", 0)
            rc["accumulated_vong_profit"] = 0
            rc["current_bet_step"] = rc["von_ban_dau"]
            rc["last_prediction"] = ""
            rc["is_cầu_1_1_active"] = False
            save_config(config)
            await send_system_notification(bot_app, target_user_id, rm["name"], s_icon, "Chốt Lẻ Vòng", "THÀNH CÔNG ĐẠT MỐC 💎", rc.get("current_balance", 0), f"Lại vòng chuỗi đạt mốc.")
            if rc["mode"] in ["cuoc_v1", "cuoc_v2", "xx_nhanh", "auto_cuoc_v3"]:
                asyncio.create_task(trigger_next_xx_nhanh_bet(bot_app, target_user_id, room_key))
            return

        max_c_thua = rc.get("cat_chuoi_thua", 0)
        if max_c_thua > 0 and rc["streak_loss_ai"] >= max_c_thua and not rc.get("is_cầu_1_1_active"):
            rc["mode"] = "du_doan"
            rc["current_bet_step"] = rc["von_ban_dau"]
            rc["is_cầu_1_1_active"] = False
            save_config(config)
            send_termux_notification("🚨 BOT BÓP PHANH CẮT THUA!", f"Sàn: {rm['name'].upper()} chạm mốc dừng.")
            await send_system_notification(bot_app, target_user_id, rm["name"], s_icon, "Cắt Chuỗi Thua", "PHANH ĐỘNG 🛑", rc.get("current_balance", 0), "Về dự đoán.")
            return

    # === LOGIC 3+ (KÉP ↔ 11 + NHÁNH 2) ===
    if chosen_logic_type == "logic_3":
        if is_dice_event and dice_val is not None:
            current_result = "TÀI" if dice_val >= 4 else "XỈU"
            logic_state = rc.get("logic3_state", {"mode": "kep", "loss_count": 0, "win_count": 0})
            last_pred = rc.get("last_prediction", "")
            hist = rc.get("history_tx", [])

            # --- Nhánh 2: cầu nghiêng nhịp 2-2 ---
            if len(hist) >= 4 and hist[-4] == hist[-3] != hist[-2] == hist[-1]:
                logic_state["mode"] = "cau_nghieng"
                logic_state["loss_count"] = 0

            # --- Nếu không rơi vào nhánh 2, giữ kép ↔ 11 ---
            else:
                if logic_state["mode"] == "cau_nghieng" and last_pred and last_pred != current_result:
                    logic_state["mode"] = "kep"
                    logic_state["loss_count"] = 0
                else:
                    if last_pred:
                        if last_pred == current_result:
                            logic_state["loss_count"] = 0
                        else:
                            logic_state["loss_count"] += 1
                            if logic_state["loss_count"] >= 3:
                                logic_state["mode"] = "bat11"
                                logic_state["loss_count"] = 0

            # --- Xác định dự đoán tiếp theo ---
            if logic_state["mode"] == "kep":
                # Bắt kép: đánh theo kết quả vừa ra
                final_next_door = current_result
            elif logic_state["mode"] == "bat11":
                # Bắt 11: đánh ngược kết quả vừa ra
                final_next_door = "XỈU" if current_result == "TÀI" else "TÀI"
                if last_pred and last_pred != current_result:
                    logic_state["mode"] = "kep"
            elif logic_state["mode"] == "cau_nghieng":
                # Cầu nghiêng: nếu 2 ván trước giống nhau → đánh ngược, nếu khác → đánh theo
                if len(hist) >= 2 and hist[-1] == hist[-2]:
                    final_next_door = "XỈU" if current_result == "TÀI" else "TÀI"
                else:
                    final_next_door = current_result
            else:
                final_next_door = current_result

            rc["logic3_state"] = logic_state
        else:
            if is_dice_event and next_door_predicted:
                final_next_door = next_door_predicted
            else:
                final_next_door = "TÀI" if random.choice([True, False]) else "XỈU"

    # === LOGIC 4 (THỦ CÔNG GHI NHỚ MẪU 5 TAY) ===
    elif chosen_logic_type == "logic_4":
        if is_dice_event and dice_val is not None:
            current_result = "TÀI" if dice_val >= 4 else "XỈU"
            logic_state = rc.get("logic4_state", {"mode": "kep", "loss_count": 0, "pattern": [], "choice": "", "waiting": False})
            last_pred = rc.get("last_prediction", "")
            hist = rc.get("history_tx", [])

            # --- Giai đoạn bắt kép bình thường ---
            if logic_state["mode"] == "kep":
                if last_pred:
                    if last_pred == current_result:
                        logic_state["loss_count"] = 0
                    else:
                        logic_state["loss_count"] += 1
                        if logic_state["loss_count"] >= 3:
                            # Đã thua 3 tay liên tiếp → dừng đặt, chờ mẫu 5 tay
                            logic_state["mode"] = "cho_mau"
                            logic_state["loss_count"] = 0
                            logic_state["waiting"] = True
                            send_termux_notification("🧠 LOGIC 4", "Thua 3 tay liên tiếp. Đang chờ mẫu 5 tay để đặt lại.")
                else:
                    # Ván đầu tiên, chưa có dự đoán
                    pass

            # --- Giai đoạn chờ mẫu 5 tay ---
            if logic_state["mode"] == "cho_mau":
                # Vẫn cập nhật lịch sử
                if len(hist) >= 5 and not logic_state.get("pattern"):
                    # Đã có đủ 5 tay, nhưng chưa có mẫu. Người dùng cần chọn mẫu và T/X.
                    # Tạm thời tiếp tục theo dõi, không đặt cược.
                    pass
                elif len(hist) >= 5 and logic_state.get("pattern") and logic_state.get("choice"):
                    # Đã có mẫu và lựa chọn. Kiểm tra xem 5 tay gần nhất có khớp mẫu không.
                    last_5 = hist[-5:]
                    if last_5 == logic_state["pattern"]:
                        # Khớp mẫu → đặt theo lựa chọn đã lưu
                        final_next_door = logic_state["choice"]
                        logic_state["mode"] = "dang_dat_mau"
                        logic_state["waiting"] = False
                        send_termux_notification("🧠 LOGIC 4", "Đã khớp mẫu 5 tay. Đang đặt cược.")
                    else:
                        # Chưa khớp mẫu → tiếp tục chờ
                        final_next_door = None
                else:
                    # Chưa có mẫu hoặc lựa chọn → tiếp tục chờ
                    final_next_door = None

            # --- Giai đoạn đang đặt theo mẫu ---
            elif logic_state["mode"] == "dang_dat_mau":
                # Đang đặt theo mẫu, nếu thua 1 tay thì quay lại kép
                if last_pred and last_pred != current_result:
                    logic_state["mode"] = "kep"
                    logic_state["loss_count"] = 0
                    logic_state["pattern"] = []
                    logic_state["choice"] = ""
                    logic_state["waiting"] = False
                    send_termux_notification("🧠 LOGIC 4", "Thua 1 tay ở mẫu. Quay lại bắt kép.")
                else:
                    # Tiếp tục đặt theo mẫu
                    final_next_door = logic_state.get("choice", current_result)

            # --- Nếu không có dự đoán, giữ nguyên last_pred ---
            if final_next_door is None:
                final_next_door = rc.get("last_prediction", "TÀI")

            rc["logic4_state"] = logic_state
        else:
            if is_dice_event and next_door_predicted:
                final_next_door = next_door_predicted
            else:
                final_next_door = "TÀI" if random.choice([True, False]) else "XỈU"

    # === CÁC LOGIC KHÁC (1, 2) ===
    else:
        if is_xx_nhanh_mode and chosen_logic_type == "logic_1":
            if rc["streak_loss_ai"] >= 3 and not rc.get("is_cầu_1_1_active", False):
                rc["is_cầu_1_1_active"] = True

        if is_xx_nhanh_mode and chosen_logic_type == "logic_1":
            if rc.get("is_cầu_1_1_active", False):
                if he_hien_tai == "tx":
                    final_next_door = "XỈU" if actual_tx == "TÀI" else "TÀI"
                else:
                    final_next_door = "LẺ" if actual_cl == "CHẴN" else "CHẴN"
            else:
                if is_dice_event and next_door_predicted:
                    final_next_door = next_door_predicted
                else:
                    final_next_door = "TÀI" if random.choice([True, False]) else "XỈU"
        else:
            if is_dice_event and next_door_predicted and room_key == "lau_cua":
                final_next_door = next_door_predicted
            else:
                final_next_door = "TÀI" if random.choice([True, False]) else "XỈU"

    active_history = rc["history_tx"] if he_hien_tai == "tx" else rc["history_cl"]
    matched_logic_idx = find_matching_logic_index(active_history, he_hien_tai)
    rc["current_logic_index"] = matched_logic_idx

    if not is_du_doan_mode and rc["last_prediction"] and result_status_string == "SAI ❌":
        if rc.get("quan_ly_von_type") == "fibonacci":
            fibo_factor = get_fibonacci_step(rc["streak_loss_ai"])
            rc["current_bet_step"] = int(rc["von_ban_dau"] * fibo_factor)
        else:
            bet_money = rc["current_bet_step"] if rc["current_bet_step"] > 0 else rc["von_ban_dau"]
            rc["current_bet_step"] = int(bet_money * rc["he_so_nhan"])
    else:
        rc["current_bet_step"] = rc["von_ban_dau"]

    confidence = round(random.uniform(78.5, 97.4), 1)
    rc["last_confidence"] = confidence
    rc["last_prediction"] = final_next_door
    save_config(config)

    # === CẬP NHẬT BẢNG THÔNG TIN SAU MỖI PHIÊN ===
    if is_xx_nhanh_mode:
        start_t = XX_NHANH_START_TIMES.get(f"{uid_str}_{room_key}", time.time())
        diff_sec = int(time.time() - start_t)
        hours = diff_sec // 3600
        minutes = (diff_sec % 3600) // 60
        seconds = diff_sec % 60
        runtime_str = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"

        door_next = rc["last_prediction"]
        syntax_display = "T" if door_next == "TÀI" else "X" if door_next == "XỈU" else door_next
        syntax_send = "XXX" if door_next == "XỈU" else "XXT" if door_next == "TÀI" else door_next

        profit_val = rc['accumulated_vong_profit']
        profit_sign = "🟢 +" if profit_val >= 0 else "🔴 "

        status_text_indicator = f"⚡ ĐANG CHẠY {chosen_logic_type.upper()}..."
        if chosen_logic_type == "logic_1" and rc.get("is_cầu_1_1_active", False):
            status_text_indicator = "🔄 LOGIC 1: ĐANG THEO CẦU 1-1 (THUA 3 TAY)"
        elif rc.get("remaining_rest_phiens", 0) > 0:
            status_text_indicator = f"⏳ ĐANG NGHỈ XẢ PHIÊN ({rc['remaining_rest_phiens']}v)"
        elif chosen_logic_type == "logic_3":
            logic_state = rc.get("logic3_state", {"mode": "kep", "loss_count": 0, "win_count": 0})
            mode_desc = "🔁 Bắt Kép" if logic_state["mode"] == "kep" else "📈 Bắt 11" if logic_state["mode"] == "bat11" else "📊 Cầu Nghiêng"
            status_text_indicator = f"⚡ LOGIC 3: {mode_desc} | Thua liên: {logic_state['loss_count']}/3"
        elif chosen_logic_type == "logic_4":
            logic_state = rc.get("logic4_state", {"mode": "kep", "loss_count": 0, "pattern": [], "choice": "", "waiting": False})
            mode_desc = "🔄 Bắt Kép" if logic_state["mode"] == "kep" else "⏸ Chờ Mẫu" if logic_state["mode"] == "cho_mau" else "🎯 Đặt Theo Mẫu"
            status_text_indicator = f"⚡ LOGIC 4: {mode_desc}"

        visual_dots_list = []
        for tx_res in rc["history_tx"][-12:]:
            if tx_res == "TÀI":
                visual_dots_list.append("🔵")
            elif tx_res == "XỈU":
                visual_dots_list.append("🔴")
        string_visual_bridge = "".join(visual_dots_list) if visual_dots_list else "Chưa ghi nhận cầu"

        current_balance = rc.get("current_balance", 0)

        msg_gop_xx_nhanh = (
            f"🎰 <b>BẢNG GIÁM SÁT SIÊU TỐC [ {rm['name'].upper()} ]</b> {s_icon}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱️ <b>Thời Gian Chạy:</b> <code>{runtime_str}</code>\n"
            f"🔢 <b>Số Phiên Chạy Được:</b> <code>{rc['total_predictions']} phiên</code>\n"
            f"🧠 <b>Nhánh Thuật Toán:</b> <code>{chosen_logic_type.upper()}</code>\n"
            f"📊 <b>Chuỗi Lịch Sử Cầu:</b> {string_visual_bridge}\n"
            f"💵 <b>Lãi / Lỗ Chuỗi:</b> <code>{profit_sign}{profit_val:,} đ</code>\n"
            f"💰 <b>Số dư hiện tại:</b> <code>{current_balance:,} đ</code>\n"
            f"────────────────────────────\n"
            f"🏆 <b>LỆNH CƯỢC TIẾP THEO:</b>\n"
            f"   ➔ Cú Pháp Hiển Thị: <code>{syntax_display} {rc['current_bet_step']:,}</code>\n"
            f"   ➔ Cú Pháp Gửi Bot: <code>{syntax_send} {rc['current_bet_step']:,}</code>\n"
            f"   ➔ Nhánh Ma Trận: <code>Pool-L #{matched_logic_idx}</code>\n"
            f"   ➔ Chỉ Tiêu Vòng: <code>[{get_target_profit_bar(profit_val, rc.get('chot_loi_le_vong', 0))}]</code>\n"
            f"────────────────────────────\n"
            f"📊 <b>Kỷ Lục Chuỗi:</b> Thắng Max: <code>{rc.get('max_streak_win_ai', 0)}</code> | Thua Max: <code>{rc.get('max_streak_loss_ai', 0)}</code>\n"
            f"⏳ <b>Delay đặt lệnh:</b> <code>{rc.get('delay_bet_xx_nhanh', 10)} giây</code>\n"
            f"🟢 <b>Trạng Thế Hệ Thống:</b> <b>{status_text_indicator}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

        msg_cache_key = f"{uid_str}_{room_key}"
        last_msg_id = XX_NHANH_LAST_MSG_IDS.get(msg_cache_key)
        edited_success = False
        if last_msg_id:
            try:
                await bot_app.bot.edit_message_text(chat_id=int(target_user_id), message_id=last_msg_id, text=msg_gop_xx_nhanh, parse_mode="HTML")
                edited_success = True
            except Exception:
                edited_success = False

        if not edited_success:
            try:
                new_msg = await bot_app.bot.send_message(chat_id=int(target_user_id), text=msg_gop_xx_nhanh, parse_mode="HTML")
                XX_NHANH_LAST_MSG_IDS[msg_cache_key] = new_msg.message_id
            except Exception:
                pass
    else:
        time_now = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh')).strftime("%H:%M:%S")
        he_names = {"tx": "¹ TÀI/XỈU 📊", "cl": "² CHẴN/LẺ 📈"}
        msg_analysis = (
            f"{s_icon} <b>BÁO CÁO PHÂN TÍCH CHẾ ĐỘ: {rc['mode'].upper()}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ Thời gian: {time_now}\n"
            f"🏁 Bot báo ván trước: <b>{rc['last_match_result']}</b>\n"
            f"🎛️ <b>Hệ phân tích:</b> <u>{he_names.get(he_hien_tai)}</u>\n"
            f"🧠 <b>Logic Định:</b> <code>Nhánh L-Matrix #{matched_logic_idx} / 256</code>\n"
            f"💎 <b>Lãi tích lũy vòng:</b> <code>{rc['accumulated_vong_profit']:,} đ</code>\n"
            f"💰 <b>Số dư hiện tại:</b> <code>{rc.get('current_balance', 0):,} đ</code>\n"
            f"────────────────────────────\n"
            f"🔥 <b>CHUỒI HIỆN TẠI:</b> Thắng: <b>{rc['streak_win_ai']}</b> tay | Thua: <b>{rc['streak_loss_ai']}</b> tay\n"
            f"────────────────────────────\n"
            f"🎯 <b>HƯỚNG LỆNH TIẾP THEO:</b> 🔥 <b>{final_next_door}</b> 🔥\n"
        )
        if chosen_logic_type == "logic_1" and rc.get("is_cầu_1_1_active", False):
            msg_analysis += "⚠️ <b>HỆ THỐNG:</b> <i>Đang bám cầu bẻ 1-1</i>\n"
        if rc["mode"] in ["cuoc_v1", "cuoc_v2"]:
            msg_analysis += f"💵 <b>Số tiền lệnh cược:</b> <code>{rc['current_bet_step']:,} đ</code>\n"
        msg_analysis += (
            f"⚡ <b>Độ tự tin cầu:</b> <code>[{get_progress_bar(confidence)}] {confidence}%</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        await bot_app.bot.send_message(chat_id=int(target_user_id), text=msg_analysis, parse_mode="HTML")

    if rc.get("mode") == "auto_cuoc_v3" and rc.get("last_prediction") and rc.get("remaining_rest_phiens", 0) == 0:
        if not rc.get("auto_cuoc_enabled", False):
            rc["auto_cuoc_enabled"] = True
            save_config(config)
        asyncio.create_task(trigger_next_xx_nhanh_bet(bot_app, target_user_id, room_key))

    if rc["mode"] in ["cuoc_v1", "cuoc_v2", "xx_nhanh"] and rc["last_prediction"] and rc.get("remaining_rest_phiens", 0) == 0:
        asyncio.create_task(trigger_next_xx_nhanh_bet(bot_app, target_user_id, room_key))

async def trigger_next_xx_nhanh_bet(bot_app, target_user_id, room_key, force_delay=None):
    udata = config["users_data"].get(str(target_user_id))
    if not udata:
        return
    rc = udata["rooms_config"][room_key]
    rm = config["rooms_data"][room_key]
    if rc["mode"] not in ["cuoc_v1", "cuoc_v2", "xx_nhanh", "auto_cuoc_v3"] or not rc["last_prediction"] or rc.get("remaining_rest_phiens", 0) > 0:
        return
    if rc.get("is_betting_locked", False):
        return

    if rc["mode"] == "xx_nhanh" or room_key == "lau_cua":
        delay_time = force_delay if force_delay is not None else rc.get("delay_bet_xx_nhanh", 2)
    else:
        delay_time = force_delay if force_delay is not None else 2

    if delay_time > 0:
        await asyncio.sleep(delay_time)

    rc["is_betting_locked"] = True

    for phone_clean in udata.get("connected_phones", []):
        cl_client = telethon_clients.get(f"{target_user_id}_{phone_clean}")
        if cl_client:
            try:
                if not cl_client.is_connected():
                    await cl_client.connect()
                door = rc["last_prediction"]
                current_bet = rc.get("current_bet_step", 1000)

                if rc["mode"] == "xx_nhanh":
                    if door == "TÀI":
                        syntax = "XXT"
                    elif door == "XỈU":
                        syntax = "XXX"
                    else:
                        syntax = None
                elif rc["mode"] == "auto_cuoc_v3":
                    if door == "TÀI":
                        syntax = "T"
                    elif door == "XỈU":
                        syntax = "X"
                    else:
                        syntax = None
                else:
                    if door == "TÀI":
                        syntax = "T"
                    elif door == "XỈU":
                        syntax = "X"
                    elif door == "CHẴN":
                        syntax = "C"
                    elif door == "LẺ":
                        syntax = "L"
                    else:
                        syntax = None

                if syntax:
                    await cl_client.send_message(rm["bot"], f"{syntax} {current_bet}")
            except Exception:
                rc["is_betting_locked"] = False

async def process_bot_response_log(bot_app, target_user_id, room_key, event, phone_clean):
    if not event.is_private:
        return
    bot_text = event.message.message if event.message.message else ""
    client_key = f"{target_user_id}_{phone_clean}"
    cl_client = telethon_clients.get(client_key)

    udata = config["users_data"].get(str(target_user_id))
    if udata and room_key in udata["rooms_config"]:
        rc = udata["rooms_config"][room_key]
        # Nếu có dice (media) hoặc tin nhắn từ bot -> xử lý XX nhanh
        if event.message.media or rc.get("mode") in ["xx_nhanh", "auto_cuoc_v3"]:
            await process_independent_flow(bot_app, target_user_id, room_key, bot_text, event=event)

    if not udata or room_key not in udata["rooms_config"]:
        return
    rc = udata["rooms_config"][room_key]
    rm = config["rooms_data"][room_key]

    balance_match = re.search(r'(?:Số dư mới|Số dư|Ví|Còn lại|Khả dụng)[:\s]*([\d.,]+)', bot_text, re.IGNORECASE)
    if balance_match:
        try:
            rc["current_balance"] = int(balance_match.group(1).replace(",", "").replace(".", ""))
            nguong_rut = rc.get("nguong_rut_tien", 0)
            so_tien_can_rut = rc.get("so_tien_rut_auto", 0)
            if rc["current_balance"] < nguong_rut and rc.get("is_withdrawn_at_threshold", False):
                rc["is_withdrawn_at_threshold"] = False
            elif nguong_rut > 0 and so_tien_can_rut > 0 and rc["current_balance"] >= nguong_rut:
                if not rc.get("is_withdrawn_at_threshold", False):
                    if cl_client:
                        if not cl_client.is_connected():
                            await cl_client.connect()
                        rc["is_withdrawn_at_threshold"] = True
                        save_config(config)
                        send_termux_notification("💸 KÍCH HOẠT AUTO RÚT TIỀN!", f"Sàn: {rm['name'].upper()} tự động rút.")
                        await cl_client.send_message(rm["bot"], f"/rut {so_tien_can_rut}")
            save_config(config)
        except Exception:
            pass

def create_global_message_handler(bot_app, uid_str, rk):
    async def handler(event):
        try:
            if rk not in config["rooms_data"]:
                return
            if event.message.out and event.chat_id == (await event.client.get_input_entity(config["rooms_data"][rk]["bot"])).user_id:
                user_text = event.message.message.strip().upper()
                bet_match = re.match(r'^(T|X|C|L|TÀI|XỈU|CHẴN|LẺ|TC|XL|TL|XC|XXX|XXT|XXC|XXL)\s*([\d.,]+)', user_text)
                if bet_match:
                    udata = config["users_data"].get(str(uid_str))
                    if udata and rk in udata["rooms_config"]:
                        rc = udata["rooms_config"][rk]
                        raw_door = bet_match.group(1)
                        if "X" in raw_door:
                            rc["last_prediction"] = "XỈU"
                        elif "T" in raw_door:
                            rc["last_prediction"] = "TÀI"
                        elif "C" in raw_door:
                            rc["last_prediction"] = "CHẴN"
                        elif "L" in raw_door:
                            rc["last_prediction"] = "LẺ"
                        rc["current_bet_step"] = int(bet_match.group(2).replace(",", "").replace(".", ""))
                        save_config(config)
        except Exception:
            pass
    return handler

async def bind_single_client_to_all_rooms(bot_app, uid_str, phone_clean, cl):
    for rk, room_info in config["rooms_data"].items():
        try:
            # Kênh lịch sử phiên (dùng cho T/X)
            try:
                channel_entity = await cl.get_entity(room_info["channel"])
                await cl(JoinChannelRequest(channel_entity))
            except Exception:
                channel_entity = room_info["channel"]

            # Bot cược (dùng cho XXT/XXX dice)
            bot_entity = await cl.get_entity(room_info["bot"])

            # Handler cho kênh lịch sử phiên – đọc T/X
            async def channel_handler(event, b_app=bot_app, u_id=uid_str, r_key=rk):
                # Chỉ xử lý nếu mode không phải xx_nhanh (hoặc cho auto_cuoc_v3)
                rc = config["users_data"].get(str(u_id), {}).get("rooms_config", {}).get(r_key, {})
                if rc.get("mode") != "xx_nhanh":
                    await process_independent_flow(b_app, u_id, r_key, event.message.message, event=event)
            cl.add_event_handler(channel_handler, events.NewMessage(chats=channel_entity))

            # Handler cho bot – đọc dice (XXT/XXX) và cả balance
            async def bot_handler(event, b_app=bot_app, u_id=uid_str, r_key=rk, p=phone_clean):
                # Nếu có media (dice) hoặc tin nhắn từ bot -> xử lý XX nhanh
                if event.message.media:
                    await process_independent_flow(b_app, u_id, r_key, event.message.message, event=event)
                # Xử lý balance và các phản hồi khác
                await process_bot_response_log(b_app, u_id, r_key, event, p)
            cl.add_event_handler(bot_handler, events.NewMessage(chats=bot_entity))

            # Handler cho tin nhắn outgoing (tự gửi lệnh cược) – cập nhật state
            cl.add_event_handler(create_global_message_handler(bot_app, uid_str, rk), events.NewMessage(outgoing=True, chats=bot_entity))

        except Exception:
            pass

async def on_bot_start_hook(bot_app: Application):
    try:
        if not os.path.exists("sessions"):
            os.makedirs("sessions", exist_ok=True)
        for uid_str, udata in config["users_data"].items():
            phones = udata.get("connected_phones", [])
            for ph in phones:
                client_key = f"{uid_str}_{ph}"
                cl = TelegramClient(f"sessions/{client_key}", API_ID, API_HASH)
                await cl.connect()
                if await cl.is_user_authorized():
                    telethon_clients[client_key] = cl
                    STATS["acc_online"] += 1
                    await bind_single_client_to_all_rooms(bot_app, uid_str, ph, cl)
    except Exception:
        pass

async def run_rich_ui_loop():
    with Live(generate_live_ui(), refresh_per_second=1) as live:
        while True:
            await asyncio.sleep(1)
            live.update(generate_live_ui())

def main():
    os.system('clear' if os.name == 'posix' else 'cls')
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(on_bot_start_hook).build()
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("code", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_inputs))

    loop = asyncio.get_event_loop()
    loop.create_task(midnight_checker_loop())
    loop.create_task(run_rich_ui_loop())

    print("\033[1;32m⚙️ Hệ thống v99.9 Đang Kết Nối Đồng Bộ Sang Khung Hộp Rich Panel...\033[0m")
    application.run_polling()

if __name__ == "__main__":
    main()

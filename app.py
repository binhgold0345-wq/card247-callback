# -*- coding: utf-8 -*-
# ==========================================
# FULL CODE app.py - CARD247 CALLBACK SERVER
# COPY TOÀN BỘ PASTE VÀO GITHUB
# ==========================================

from flask import Flask, request, jsonify
import requests
import datetime
import json
import os
import sqlite3
import threading
import time

app = Flask(__name__)

# ==========================================
# CONFIG - LẤY TỪ BIẾN MÔI TRƯỜNG RENDER
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "")
DB_PATH = os.environ.get("DB_PATH", "/tmp/card247.db")

# ==========================================
# DATABASE ĐƠN GIẢN
# ==========================================
class DB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.lock = threading.Lock()
        self._init()
    
    def _init(self):
        with self.lock:
            c = self.conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS callback_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            self.conn.commit()
    
    def log(self, type, data):
        with self.lock:
            c = self.conn.cursor()
            c.execute('INSERT INTO callback_logs (type, data) VALUES (?, ?)',
                     (type, json.dumps(data) if isinstance(data, dict) else str(data)))
            self.conn.commit()
    
    def get_logs(self, limit=100):
        c = self.conn.cursor()
        c.execute('SELECT * FROM callback_logs ORDER BY created_at DESC LIMIT ?', (limit,))
        return c.fetchall()
    
    def get_user(self, user_id):
        c = self.conn.cursor()
        c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        u = c.fetchone()
        if not u:
            c.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
            self.conn.commit()
            return {"user_id": user_id, "balance": 0}
        return {"user_id": u[0], "balance": u[1]}
    
    def add_balance(self, user_id, amount):
        with self.lock:
            c = self.conn.cursor()
            c.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
            self.conn.commit()
            return self.get_user(user_id)

db = DB()

# ==========================================
# GỬI TELEGRAM
# ==========================================
def send_telegram(text, chat_id=None):
    """Gửi tin nhắn Telegram"""
    if not BOT_TOKEN:
        print("[TELEGRAM] Chưa cấu hình BOT_TOKEN")
        return False
    
    target = chat_id or ADMIN_ID
    if not target:
        print("[TELEGRAM] Chưa cấu hình ADMIN_ID")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": target,
            "text": text,
            "parse_mode": "HTML"
        }
        resp = requests.post(url, json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        print(f"[TELEGRAM ERROR] {e}")
        return False

# ==========================================
# CARD RATES (TỈ GIÁ ĐỔI THẺ)
# ==========================================
CARD_RATES = {
    "VIETTEL": {"10000": 8500, "20000": 17000, "50000": 42500, "100000": 85000, "200000": 170000, "500000": 425000, "1000000": 850000},
    "VINA": {"10000": 8500, "20000": 17000, "50000": 42500, "100000": 85000, "200000": 170000, "500000": 425000, "1000000": 850000},
    "MOBIFONE": {"10000": 8500, "20000": 17000, "50000": 42500, "100000": 85000, "200000": 170000, "500000": 425000, "1000000": 850000},
    "GARENA": {"10000": 8000, "20000": 16000, "50000": 40000, "100000": 80000, "200000": 160000, "500000": 400000},
    "ZING": {"10000": 8000, "20000": 16000, "50000": 40000, "100000": 80000, "200000": 160000, "500000": 400000},
    "VCOIN": {"10000": 8000, "20000": 16000, "50000": 40000, "100000": 80000, "200000": 160000, "500000": 400000}
}

FEE_PERCENT = int(os.environ.get("FEE_PERCENT", "15"))

# ==========================================
# API ĐỔI THẺ (GỌI RA NGOÀI)
# ==========================================
EXCHANGE_API_URL = os.environ.get("EXCHANGE_API_URL", "")
EXCHANGE_PARTNER_ID = os.environ.get("EXCHANGE_PARTNER_ID", "")
EXCHANGE_PARTNER_KEY = os.environ.get("EXCHANGE_PARTNER_KEY", "")

def call_exchange_api(telco, code, serial, amount):
    """Gọi API đối tác để đổi thẻ"""
    if not EXCHANGE_API_URL:
        return {"status": "error", "message": "Chưa cấu hình EXCHANGE_API_URL"}
    
    try:
        payload = {
            "partner_id": EXCHANGE_PARTNER_ID,
            "partner_key": EXCHANGE_PARTNER_KEY,
            "telco": telco,
            "code": code,
            "serial": serial,
            "amount": amount
        }
        resp = requests.post(EXCHANGE_API_URL, json=payload, timeout=30)
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# API MUA THẺ (GỌI RA NGOÀI)
# ==========================================
BUY_CARD_API_URL = os.environ.get("BUY_CARD_API_URL", "")
BUY_CARD_API_KEY = os.environ.get("BUY_CARD_API_KEY", "")

def call_buy_api(telco, amount, quantity):
    """Gọi API mua thẻ"""
    if not BUY_CARD_API_URL:
        return {"status": "error", "message": "Chưa cấu hình BUY_CARD_API_URL"}
    
    try:
        payload = {
            "api_key": BUY_CARD_API_KEY,
            "telco": telco,
            "amount": amount,
            "quantity": quantity
        }
        resp = requests.post(BUY_CARD_API_URL, json=payload, timeout=30)
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# THÔNG TIN NGÂN HÀNG ADMIN
# ==========================================
BANK_INFO = {
    "bank_name": os.environ.get("BANK_NAME", "VCB"),
    "account_number": os.environ.get("BANK_ACCOUNT", "0123456789"),
    "account_name": os.environ.get("BANK_OWNER", "NGUYEN VAN A"),
    "momo": os.environ.get("MOMO_NUMBER", "0123456789")
}

# ==========================================
# ROUTES CHÍNH
# ==========================================

@app.route('/')
def home():
    """Trang chủ - Kiểm tra server online"""
    return jsonify({
        "status": "online",
        "server": "CARD247 API",
        "version": "2.0.0",
        "time": datetime.datetime.now().isoformat(),
        "endpoints": {
            "doi_the": "/api/exchange",
            "mua_the": "/api/buy-card",
            "nap_tien": "/api/deposit",
            "rut_tien": "/api/withdraw",
            "kiem_tra_balance": "/api/balance/<user_id>",
            "callback_doi_the": "/callback/doi-the",
            "callback_mua_the": "/callback/mua-the",
            "logs": "/api/logs"
        }
    })

# ==========================================
# CALLBACK ENDPOINTS (NHẬN TỪ API ĐỐI TÁC)
# ==========================================

@app.route('/callback/doi-the', methods=['POST', 'GET'])
def callback_doi_the():
    """
    CALLBACK TỪ API ĐỔI THẺ
    URL: https://your-app.onrender.com/callback/doi-the
    
    Dữ liệu nhận:
    {
        "request_id": "123",
        "status": "success/failed/pending",
        "telco": "VIETTEL",
        "amount": 100000,
        "code": "12345678901234",
        "serial": "123456789012345",
        "received_amount": 85000,
        "message": "Thành công"
    }
    """
    data = request.json if request.is_json else request.args.to_dict()
    
    # Log vào database
    db.log("doi-the-callback", data)
    
    # Log ra console
    print(f"\n{'='*50}")
    print(f"[CALLBACK ĐỔI THẺ] {datetime.datetime.now()}")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"{'='*50}\n")
    
    # Xử lý callback
    if data:
        status = data.get('status', '')
        request_id = data.get('request_id', '')
        telco = data.get('telco', '')
        amount = data.get('amount', 0)
        code = data.get('code', '***')
        serial = data.get('serial', '***')
        received = data.get('received_amount', 0)
        message = data.get('message', '')
        
        if status == 'success':
            emoji = "✅"
            status_text = "THÀNH CÔNG"
        elif status == 'failed':
            emoji = "❌"
            status_text = "THẤT BẠI"
        else:
            emoji = "⏳"
            status_text = "ĐANG XỬ LÝ"
        
        # Gửi Telegram cho admin
        tg_msg = f"""
{emoji} <b>CALLBACK ĐỔI THẺ - {status_text}</b>

🆔 Request ID: <code>{request_id}</code>
📱 Nhà mạng: <b>{telco}</b>
💵 Mệnh giá: <b>{int(amount):,}đ</b>
🎫 Mã thẻ: <code>{code}</code>
🔢 Serial: <code>{serial}</code>
💰 Thực nhận: <b>{int(received):,}đ</b>
📝 Ghi chú: {message}
⏰ Thời gian: {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}

🏷 <i>Callback tự động từ API đối tác</i>
        """
        send_telegram(tg_msg, ADMIN_ID)
    
    return jsonify({
        "status": "ok",
        "message": "Callback received successfully",
        "time": datetime.datetime.now().isoformat()
    })

@app.route('/callback/mua-the', methods=['POST', 'GET'])
def callback_mua_the():
    """
    CALLBACK TỪ API MUA THẺ
    URL: https://your-app.onrender.com/callback/mua-the
    
    Dữ liệu nhận:
    {
        "order_id": "ORDER123",
        "status": "success/failed",
        "telco": "VIETTEL",
        "amount": 100000,
        "quantity": 5,
        "total": 500000,
        "cards": [
            {"code": "1234...", "serial": "5678..."},
            ...
        ],
        "message": "Thành công"
    }
    """
    data = request.json if request.is_json else request.args.to_dict()
    
    # Log
    db.log("mua-the-callback", data)
    
    print(f"\n{'='*50}")
    print(f"[CALLBACK MUA THẺ] {datetime.datetime.now()}")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"{'='*50}\n")
    
    if data:
        order_id = data.get('order_id', '')
        status = data.get('status', '')
        telco = data.get('telco', '')
        amount = data.get('amount', 0)
        quantity = data.get('quantity', 0)
        cards = data.get('cards', [])
        message = data.get('message', '')
        
        emoji = "✅" if status == 'success' else "❌"
        
        cards_text = ""
        if cards:
            cards_list = []
            for i, card in enumerate(cards, 1):
                cards_list.append(f"  {i}. <code>{card.get('code', '***')}</code> | <code>{card.get('serial', '***')}</code>")
            cards_text = "\n".join(cards_list)
        
        tg_msg = f"""
{emoji} <b>CALLBACK MUA THẺ</b>

🆔 Order ID: <code>{order_id}</code>
📱 Nhà mạng: <b>{telco}</b>
💵 Mệnh giá: <b>{int(amount):,}đ</b>
🔢 Số lượng: <b>{quantity}</b>
📝 Trạng thái: <b>{status}</b>
💬 Ghi chú: {message}

🎫 <b>DANH SÁCH THẺ:</b>
{cards_text if cards_text else 'Không có dữ liệu'}

⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
        """
        send_telegram(tg_msg, ADMIN_ID)
    
    return jsonify({
        "status": "ok",
        "message": "Callback received successfully",
        "time": datetime.datetime.now().isoformat()
    })

# ==========================================
# API CHO NGƯỜI DÙNG GỌI
# ==========================================

@app.route('/api/exchange', methods=['POST'])
def api_exchange():
    """
    API ĐỔI THẺ CÀO
    GỌI TỪ BOT TELEGRAM HOẶC WEB
    
    Body JSON:
    {
        "user_id": 123456,
        "telco": "VIETTEL",
        "amount": 100000,
        "card_code": "12345678901234",
        "card_serial": "123456789012345"
    }
    """
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Thiếu dữ liệu"})
    
    user_id = data.get('user_id')
    telco = data.get('telco', '').upper()
    amount = str(data.get('amount', ''))
    card_code = data.get('card_code', '')
    card_serial = data.get('card_serial', '')
    
    # Validate
    if telco not in CARD_RATES:
        return jsonify({"status": "error", "message": "Nhà mạng không hỗ trợ"})
    
    if amount not in CARD_RATES.get(telco, {}):
        return jsonify({"status": "error", "message": "Mệnh giá không hỗ trợ"})
    
    if not card_code or not card_serial:
        return jsonify({"status": "error", "message": "Thiếu mã thẻ hoặc serial"})
    
    # Tính toán
    rate = CARD_RATES[telco][amount]
    fee = int(int(amount) * FEE_PERCENT / 100)
    received = rate - fee
    
    # Gọi API đối tác
    result = call_exchange_api(telco, card_code, card_serial, amount)
    
    if result.get('status') == 'success':
        # Cộng tiền cho user (nếu có user_id)
        if user_id:
            db.add_balance(user_id, received)
        
        # Log
        db.log("doi-the-success", {
            "user_id": user_id,
            "telco": telco,
            "amount": amount,
            "code": card_code,
            "serial": card_serial,
            "received": received
        })
        
        # Gửi Telegram admin
        tg_msg = f"""
✅ <b>ĐỔI THẺ THÀNH CÔNG</b>

👤 User ID: <code>{user_id}</code>
📱 Nhà mạng: <b>{telco}</b>
💵 Mệnh giá: <b>{int(amount):,}đ</b>
🎫 Mã thẻ: <code>{card_code}</code>
🔢 Serial: <code>{card_serial}</code>
💰 Nhận được: <b>{received:,} xu</b>
📊 Phí: <b>{fee:,} xu</b>
⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
        """
        send_telegram(tg_msg, ADMIN_ID)
        
        return jsonify({
            "status": "success",
            "message": "Đổi thẻ thành công",
            "received_amount": received,
            "fee": fee,
            "telco": telco,
            "amount": int(amount)
        })
    else:
        db.log("doi-the-failed", {
            "user_id": user_id,
            "telco": telco,
            "amount": amount,
            "error": result.get('message', '')
        })
        
        return jsonify({
            "status": "error",
            "message": result.get('message', 'Đổi thẻ thất bại')
        })

@app.route('/api/buy-card', methods=['POST'])
def api_buy_card():
    """
    API MUA THẺ CÀO
    
    Body JSON:
    {
        "user_id": 123456,
        "telco": "VIETTEL",
        "amount": 100000,
        "quantity": 1
    }
    """
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Thiếu dữ liệu"})
    
    user_id = data.get('user_id')
    telco = data.get('telco', '').upper()
    amount = data.get('amount')
    quantity = data.get('quantity', 1)
    
    # Gọi API mua thẻ
    result = call_buy_api(telco, amount, quantity)
    
    if result.get('status') == 'success':
        cards = result.get('cards', [])
        
        # Log
        db.log("mua-the-success", {
            "user_id": user_id,
            "telco": telco,
            "amount": amount,
            "quantity": quantity,
            "cards_count": len(cards)
        })
        
        cards_list = "\n".join([
            f"  {i+1}. <code>{c.get('code','***')}</code> | <code>{c.get('serial','***')}</code>"
            for i, c in enumerate(cards)
        ])
        
        tg_msg = f"""
✅ <b>MUA THẺ THÀNH CÔNG</b>

👤 User ID: <code>{user_id}</code>
📱 Nhà mạng: <b>{telco}</b>
💵 Mệnh giá: <b>{int(amount):,}đ</b>
🔢 Số lượng: <b>{quantity}</b>

🎫 <b>THẺ NHẬN ĐƯỢC:</b>
{cards_list}

⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
        """
        send_telegram(tg_msg, ADMIN_ID)
        
        return jsonify({
            "status": "success",
            "message": "Mua thẻ thành công",
            "cards": cards,
            "quantity": quantity
        })
    else:
        return jsonify({
            "status": "error",
            "message": result.get('message', 'Mua thẻ thất bại')
        })

@app.route('/api/deposit', methods=['POST'])
def api_deposit():
    """
    API NẠP TIỀN - TẠO YÊU CẦU
    
    Body JSON:
    {
        "user_id": 123456,
        "amount": 100000,
        "content": "NAP TIEN USER 123456",
        "method": "bank"
    }
    """
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Thiếu dữ liệu"})
    
    user_id = data.get('user_id')
    amount = data.get('amount')
    content = data.get('content', '')
    method = data.get('method', 'bank')
    
    transaction_id = f"NAP{int(time.time())}{os.urandom(3).hex().upper()}"
    
    # Log
    db.log("deposit-request", {
        "user_id": user_id,
        "amount": amount,
        "content": content,
        "method": method,
        "transaction_id": transaction_id
    })
    
    # Gửi Telegram admin
    tg_msg = f"""
💰 <b>YÊU CẦU NẠP TIỀN</b>

👤 User ID: <code>{user_id}</code>
💵 Số tiền: <b>{int(amount):,}đ</b>
📝 Nội dung CK: <b>{content}</b>
🏦 Phương thức: <b>{method}</b>
🔢 Mã GD: <code>{transaction_id}</code>
⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}

✅ <b>Kiểm tra tài khoản và xác nhận!</b>
        """
    send_telegram(tg_msg, ADMIN_ID)
    
    return jsonify({
        "status": "pending",
        "message": "Yêu cầu nạp tiền đã được gửi, admin sẽ xác nhận sau khi kiểm tra",
        "transaction_id": transaction_id,
        "bank_info": BANK_INFO,
        "note": f"Vui lòng chuyển khoản với nội dung: {content or 'NAP ' + str(user_id)}"
    })

@app.route('/api/withdraw', methods=['POST'])
def api_withdraw():
    """
    API RÚT TIỀN
    
    Body JSON:
    {
        "user_id": 123456,
        "amount": 100000,
        "bank_name": "VCB",
        "account_number": "0123456789",
        "account_name": "NGUYEN VAN A"
    }
    """
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Thiếu dữ liệu"})
    
    user_id = data.get('user_id')
    amount = int(data.get('amount', 0))
    bank_name = data.get('bank_name', '')
    account_number = data.get('account_number', '')
    account_name = data.get('account_name', '')
    
    fee = int(amount * 5 / 100)  # 5% phí
    receive = amount - fee
    
    # Log
    db.log("withdraw-request", {
        "user_id": user_id,
        "amount": amount,
        "fee": fee,
        "receive": receive,
        "bank_name": bank_name,
        "account_number": account_number,
        "account_name": account_name
    })
    
    # Gửi Telegram admin
    tg_msg = f"""
💸 <b>YÊU CẦU RÚT TIỀN</b>

👤 User ID: <code>{user_id}</code>
💵 Số tiền rút: <b>{amount:,} xu</b>
📊 Phí (5%): <b>{fee:,} xu</b>
💳 Thực nhận: <b>{receive:,} xu</b>
🏦 Ngân hàng: <b>{bank_name}</b>
🔢 Số TK: <code>{account_number}</code>
👤 Chủ TK: <b>{account_name}</b>
⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}

⚠️ <b>Chuyển khoản ngay cho user!</b>
        """
    send_telegram(tg_msg, ADMIN_ID)
    
    return jsonify({
        "status": "pending",
        "message": "Yêu cầu rút tiền đã được gửi, admin sẽ xử lý trong 5-15 phút",
        "amount": amount,
        "fee": fee,
        "receive": receive
    })

# ==========================================
# API KIỂM TRA
# ==========================================

@app.route('/api/balance/<int:user_id>', methods=['GET'])
def api_balance(user_id):
    """Kiểm tra số dư"""
    user = db.get_user(user_id)
    return jsonify({
        "user_id": user_id,
        "balance": user['balance']
    })

@app.route('/api/logs', methods=['GET'])
def api_logs():
    """Xem log callback"""
    logs = db.get_logs(50)
    result = []
    for log in logs:
        try:
            data = json.loads(log[2]) if isinstance(log[2], str) else log[2]
        except:
            data = str(log[2])
        result.append({
            "id": log[0],
            "type": log[1],
            "data": data,
            "time": log[3]
        })
    return jsonify({
        "total": len(result),
        "logs": result
    })

@app.route('/api/stats', methods=['GET'])
def api_stats():
    """Thống kê hệ thống"""
    logs = db.get_logs(1000)
    
    stats = {
        "total_callbacks": len(logs),
        "doi_the": 0,
        "mua_the": 0,
        "nap_tien": 0,
        "rut_tien": 0
    }
    
    for log in logs:
        log_type = log[1]
        if 'doi-the' in log_type:
            stats['doi_the'] += 1
        elif 'mua-the' in log_type:
            stats['mua_the'] += 1
        elif 'deposit' in log_type:
            stats['nap_tien'] += 1
        elif 'withdraw' in log_type:
            stats['rut_tien'] += 1
    
    return jsonify(stats)

# ==========================================
# HEALTH CHECK CHO UPTIMEROBOT
# ==========================================
@app.route('/health', methods=['GET'])
def health():
    return "OK", 200

@app.route('/ping', methods=['GET'])
def ping():
    return "pong", 200

# ==========================================
# MAIN
# ==========================================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    
    print(f"""
╔══════════════════════════════════════════════╗
║     CARD247 CALLBACK SERVER                  ║
║     Port: {port}                              ║
║     Admin ID: {ADMIN_ID}                     ║
║     Exchange API: {EXCHANGE_API_URL or 'Chưa cấu hình'}  ║
║     Buy Card API: {BUY_CARD_API_URL or 'Chưa cấu hình'}  ║
╚══════════════════════════════════════════════╝
    """)
    
    app.run(host='0.0.0.0', port=port, debug=False)

# -*- coding: utf-8 -*-
# ==========================================
# FULL CODE app.py - CARD247 CALLBACK SERVER
# PHÍ ĐỔI THẺ: 20%
# COPY TOÀN BỘ DÁN VÀO GITHUB
# ==========================================
from flask import Flask, request, jsonify
import requests, datetime, json, os, time

app = Flask(__name__)

# ==========================================
# CONFIG TỪ BIẾN MÔI TRƯỜNG RENDER
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "")

EXCHANGE_API_URL = os.environ.get("EXCHANGE_API_URL", "")
EXCHANGE_PARTNER_ID = os.environ.get("EXCHANGE_PARTNER_ID", "83952560492")
EXCHANGE_PARTNER_KEY = os.environ.get("EXCHANGE_PARTNER_KEY", "a14e7d3b856674848c4e9f8677cab4ad")

BUY_CARD_API_URL = os.environ.get("BUY_CARD_API_URL", "")
BUY_CARD_API_KEY = os.environ.get("BUY_CARD_API_KEY", "")

# ==========================================
# TỈ GIÁ ĐỔI THẺ (MỖI THẺ -20%)
# Ví dụ: Thẻ 100k -> 100.000 - 20% = 80.000 xu
# ==========================================
CARD_RATES = {
    "VIETTEL": {
        "10000": 8000, "20000": 16000, "50000": 40000,
        "100000": 80000, "200000": 160000, "500000": 400000, "1000000": 800000
    },
    "VINA": {
        "10000": 8000, "20000": 16000, "50000": 40000,
        "100000": 80000, "200000": 160000, "500000": 400000, "1000000": 800000
    },
    "MOBIFONE": {
        "10000": 8000, "20000": 16000, "50000": 40000,
        "100000": 80000, "200000": 160000, "500000": 400000, "1000000": 800000
    },
    "GARENA": {
        "10000": 8000, "20000": 16000, "50000": 40000,
        "100000": 80000, "200000": 160000, "500000": 400000
    },
    "ZING": {
        "10000": 8000, "20000": 16000, "50000": 40000,
        "100000": 80000, "200000": 160000, "500000": 400000
    },
    "VCOIN": {
        "10000": 8000, "20000": 16000, "50000": 40000,
        "100000": 80000, "200000": 160000, "500000": 400000
    }
}

# ==========================================
# GỬI TELEGRAM
# ==========================================
def send_telegram(text):
    if not BOT_TOKEN or not ADMIN_ID:
        print("Thiếu BOT_TOKEN hoặc ADMIN_ID")
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": ADMIN_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"Lỗi Telegram: {e}")

# ==========================================
# GỌI API ĐỐI TÁC ĐỔI THẺ
# ==========================================
def call_exchange_api(telco, code, serial, amount):
    if not EXCHANGE_API_URL:
        return {"status": "error", "message": "Chưa cấu hình EXCHANGE_API_URL"}
    try:
        resp = requests.post(EXCHANGE_API_URL, json={
            "partner_id": EXCHANGE_PARTNER_ID,
            "partner_key": EXCHANGE_PARTNER_KEY,
            "telco": telco,
            "code": code,
            "serial": serial,
            "amount": amount
        }, timeout=30)
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# GỌI API ĐỐI TÁC MUA THẺ
# ==========================================
def call_buy_api(telco, amount, quantity):
    if not BUY_CARD_API_URL:
        return {"status": "error", "message": "Chưa cấu hình BUY_CARD_API_URL"}
    try:
        resp = requests.post(BUY_CARD_API_URL, json={
            "api_key": BUY_CARD_API_KEY,
            "telco": telco,
            "amount": amount,
            "quantity": quantity
        }, timeout=30)
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# TRANG CHỦ
# ==========================================
@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "server": "CARD247",
        "time": datetime.datetime.now().isoformat()
    })

# ==========================================
# CALLBACK TỪ API ĐỐI TÁC ĐỔI THẺ
# ==========================================
@app.route('/callback/doi-the', methods=['POST', 'GET'])
def callback_doi_the():
    data = request.json or request.args.to_dict()
    print(f"[CALLBACK DOI THE] {data}")
    
    if data:
        status = data.get('status', '')
        emoji = "✅" if status == 'success' else "❌" if status == 'failed' else "⏳"
        
        msg = f"""
{emoji} <b>CALLBACK ĐỔI THẺ</b>
🆔 {data.get('request_id','')}
📱 {data.get('telco','')} | {data.get('amount',0):,}đ
🎫 {data.get('code','***')} | {data.get('serial','***')}
💰 Nhận: {data.get('received_amount',0):,}đ
📝 {data.get('message','')}
⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
        """
        send_telegram(msg)
    
    return jsonify({"status": "ok"})

# ==========================================
# CALLBACK TỪ API ĐỐI TÁC MUA THẺ
# ==========================================
@app.route('/callback/mua-the', methods=['POST', 'GET'])
def callback_mua_the():
    data = request.json or request.args.to_dict()
    print(f"[CALLBACK MUA THE] {data}")
    
    if data:
        cards = data.get('cards', [])
        cards_text = "\n".join([f"{i+1}. {c.get('code','')} | {c.get('serial','')}" for i,c in enumerate(cards)])
        
        msg = f"""
✅ <b>CALLBACK MUA THẺ</b>
🆔 {data.get('order_id','')}
📱 {data.get('telco','')} | {data.get('amount',0):,}đ x {len(cards)}
🎫 {cards_text if cards_text else 'Đang xử lý'}
⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
        """
        send_telegram(msg)
    
    return jsonify({"status": "ok"})

# ==========================================
# API ĐỔI THẺ (BOT GỌI) - PHÍ 20%
# ==========================================
@app.route('/api/exchange', methods=['POST'])
def api_exchange():
    data = request.json
    
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
    
    # Tính tiền (đã trừ 20% trong bảng giá)
    received = CARD_RATES[telco][amount]
    original = int(amount)
    fee = original - received
    
    # Gọi API đối tác
    result = call_exchange_api(telco, card_code, card_serial, amount)
    
    if result.get('status') == 'success':
        msg = f"""
✅ <b>ĐỔI THẺ THÀNH CÔNG</b>
👤 User: <code>{user_id}</code>
📱 {telco} | {original:,}đ
🎫 {card_code} | {card_serial}
💰 Nhận: {received:,} xu
📊 Phí (20%): {fee:,} xu
⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
        """
        send_telegram(msg)
        
        return jsonify({
            "status": "success",
            "received_amount": received,
            "fee": fee,
            "message": f"Đổi thẻ thành công! Nhận {received:,} xu (phí 20%)"
        })
    else:
        return jsonify({
            "status": "error",
            "message": result.get('message', 'Đổi thẻ thất bại')
        })

# ==========================================
# API MUA THẺ (BOT GỌI)
# ==========================================
@app.route('/api/buy-card', methods=['POST'])
def api_buy_card():
    data = request.json
    
    user_id = data.get('user_id')
    telco = data.get('telco', '').upper()
    amount = data.get('amount')
    quantity = data.get('quantity', 1)
    
    result = call_buy_api(telco, amount, quantity)
    
    if result.get('status') == 'success':
        cards = result.get('cards', [])
        cards_text = "\n".join([f"{i+1}. {c.get('code','')} | {c.get('serial','')}" for i,c in enumerate(cards)])
        
        msg = f"""
✅ <b>MUA THẺ THÀNH CÔNG</b>
👤 User: <code>{user_id}</code>
📱 {telco} | {int(amount):,}đ x {quantity}
🎫 {cards_text}
⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
        """
        send_telegram(msg)
        
        return jsonify({"status": "success", "cards": cards})
    else:
        return jsonify({"status": "error", "message": result.get('message', 'Mua thẻ thất bại')})

# ==========================================
# API NẠP TIỀN -> GỬI TELEGRAM CHO BẠN DUYỆT
# ==========================================
@app.route('/api/deposit', methods=['POST'])
def api_deposit():
    data = request.json
    
    user_id = data.get('user_id')
    amount = data.get('amount')
    content = data.get('content', '')
    method = data.get('method', 'bank')
    
    msg = f"""
💰 <b>CÓ NGƯỜI NẠP TIỀN - KIỂM TRA NGAY!</b>

👤 User ID: <code>{user_id}</code>
💵 Số tiền: <b>{int(amount):,}đ</b>
📝 Nội dung CK: <b>{content}</b>
🏦 Phương thức: <b>{method}</b>
⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}

✅ Vào app bank kiểm tra rồi cộng xu cho user
❌ Nếu chưa có tiền thì báo user chưa chuyển
    """
    send_telegram(msg)
    
    return jsonify({
        "status": "pending",
        "message": "Đã gửi yêu cầu. Admin sẽ kiểm tra và duyệt."
    })

# ==========================================
# API RÚT TIỀN -> GỬI TELEGRAM CHO BẠN CHUYỂN
# ==========================================
@app.route('/api/withdraw', methods=['POST'])
def api_withdraw():
    data = request.json
    
    user_id = data.get('user_id')
    amount = int(data.get('amount', 0))
    bank_name = data.get('bank_name', '')
    account_number = data.get('account_number', '')
    account_name = data.get('account_name', '')
    
    fee = int(amount * 5 / 100)
    receive = amount - fee
    
    msg = f"""
💸 <b>CÓ NGƯỜI RÚT TIỀN - CHUYỂN NGAY!</b>

👤 User ID: <code>{user_id}</code>
💵 Rút: <b>{amount:,} xu</b>
📊 Phí 5%: <b>{fee:,} xu</b>
💳 Nhận: <b>{receive:,} xu</b>
🏦 Bank: <b>{bank_name}</b>
🔢 STK: <code>{account_number}</code>
👤 Chủ TK: <b>{account_name}</b>
⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}

⚠️ Mở app bank chuyển {receive:,}đ cho user ngay!
    """
    send_telegram(msg)
    
    return jsonify({
        "status": "pending",
        "message": "Đã gửi yêu cầu. Admin sẽ chuyển khoản."
    })

# ==========================================
# KIỂM TRA SỐ DƯ
# ==========================================
@app.route('/api/balance/<int:user_id>', methods=['GET'])
def api_balance(user_id):
    return jsonify({"user_id": user_id, "balance": 0, "note": "Admin tự quản lý số dư"})

# ==========================================
# MAIN
# ==========================================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"CARD247 SERVER - Port {port}")
    print(f"Phí đổi thẻ: 20%")
    app.run(host='0.0.0.0', port=port)

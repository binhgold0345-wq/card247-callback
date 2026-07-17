# -*- coding: utf-8 -*-
# ==========================================
# CARD247 - FULL CODE app.py
# 2 API ĐỔI THẺ + MUA THẺ
# 2 ADMIN ID
# ==========================================
from flask import Flask, request, jsonify
import requests
import datetime
import os
import threading

app = Flask(__name__)

# ==========================================
# CONFIG
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8795312989:AAGxNXoc7lRTOjRiqGkxjahXLJB1I7fYfHw")

# 2 Admin ID
ADMIN_IDS = os.environ.get("ADMIN_IDS", "8816389907,8201945667")
ADMIN_LIST = [int(x.strip()) for x in ADMIN_IDS.split(",") if x.strip()]

# ==========================================
# API ĐỔI THẺ (API 1)
# ==========================================
EXCHANGE_API_URL = os.environ.get("EXCHANGE_API_URL", "")
EXCHANGE_PARTNER_ID = os.environ.get("EXCHANGE_PARTNER_ID", "83952560492")
EXCHANGE_PARTNER_KEY = os.environ.get("EXCHANGE_PARTNER_KEY", "a14e7d3b856674848c4e9f8677cab4ad")

# ==========================================
# API MUA THẺ (API 2)
# ==========================================
BUY_CARD_API_URL = os.environ.get("BUY_CARD_API_URL", "")
BUY_CARD_PARTNER_ID = os.environ.get("BUY_CARD_PARTNER_ID", "96368346934")
BUY_CARD_PARTNER_KEY = os.environ.get("BUY_CARD_PARTNER_KEY", "06a9e7a0d1e4e6afceb0c40d4e4b4eb9")

# ==========================================
# TỈ GIÁ ĐỔI THẺ (TRỪ 20% PHÍ)
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
# GỬI TIN NHẮN CHO TẤT CẢ ADMIN
# ==========================================
def send_telegram_all(text):
    """Gửi tin nhắn cho tất cả admin"""
    if not BOT_TOKEN:
        print("[LỖI] Thiếu BOT_TOKEN")
        return
    
    for admin_id in ADMIN_LIST:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(url, json={
                "chat_id": admin_id,
                "text": text,
                "parse_mode": "HTML"
            }, timeout=10)
            print(f"[TG] Đã gửi admin {admin_id}")
        except Exception as e:
            print(f"[TG] Lỗi gửi admin {admin_id}: {e}")

# ==========================================
# GỌI API ĐỔI THẺ (API 1)
# ==========================================
def call_exchange_api(telco, code, serial, amount):
    """Gọi API đối tác đổi thẻ"""
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
        print(f"[DOI THE] Gửi: {payload}")
        resp = requests.post(EXCHANGE_API_URL, json=payload, timeout=30)
        result = resp.json()
        print(f"[DOI THE] Nhận: {result}")
        return result
    except Exception as e:
        print(f"[DOI THE] Lỗi: {e}")
        return {"status": "error", "message": str(e)}

# ==========================================
# GỌI API MUA THẺ (API 2)
# ==========================================
def call_buy_api(telco, amount, quantity):
    """Gọi API đối tác mua thẻ"""
    if not BUY_CARD_API_URL:
        return {"status": "error", "message": "Chưa cấu hình BUY_CARD_API_URL"}
    
    try:
        payload = {
            "partner_id": BUY_CARD_PARTNER_ID,
            "partner_key": BUY_CARD_PARTNER_KEY,
            "telco": telco,
            "amount": amount,
            "quantity": quantity
        }
        print(f"[MUA THE] Gửi: {payload}")
        resp = requests.post(BUY_CARD_API_URL, json=payload, timeout=30)
        result = resp.json()
        print(f"[MUA THE] Nhận: {result}")
        return result
    except Exception as e:
        print(f"[MUA THE] Lỗi: {e}")
        return {"status": "error", "message": str(e)}

# ==========================================
# TRANG CHỦ - KIỂM TRA SERVER SỐNG
# ==========================================
@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "server": "CARD247",
        "version": "3.0.0",
        "time": datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
        "admins": len(ADMIN_LIST),
        "exchange_api": bool(EXCHANGE_API_URL),
        "buy_api": bool(BUY_CARD_API_URL)
    })

# ==========================================
# API ĐỔI THẺ (BOT TELEGRAM GỌI)
# ==========================================
@app.route('/api/exchange', methods=['POST', 'GET'])
def api_exchange():
    # Nhận dữ liệu
    if request.is_json:
        data = request.json
    else:
        data = request.args.to_dict()
    
    print(f"[API EXCHANGE] Nhận: {data}")
    
    user_id = data.get('user_id', 'unknown')
    telco = data.get('telco', '').upper()
    amount = str(data.get('amount', ''))
    card_code = data.get('card_code', '')
    card_serial = data.get('card_serial', '')
    
    # Validate
    if telco not in CARD_RATES:
        return jsonify({"status": "error", "message": f"Nhà mạng {telco} không hỗ trợ"})
    
    if amount not in CARD_RATES.get(telco, {}):
        return jsonify({"status": "error", "message": f"Mệnh giá {amount} không hỗ trợ"})
    
    if not card_code or not card_serial:
        return jsonify({"status": "error", "message": "Thiếu mã thẻ hoặc serial"})
    
    # Tính tiền (đã trừ 20%)
    received = CARD_RATES[telco][amount]
    original = int(amount)
    fee = original - received
    
    # Gọi API đối tác đổi thẻ
    result = call_exchange_api(telco, card_code, card_serial, amount)
    
    if result.get('status') == 'success':
        # Gửi thông báo cho 2 admin
        msg = f"""
✅ <b>ĐỔI THẺ THÀNH CÔNG</b>

👤 User: <code>{user_id}</code>
📱 Nhà mạng: <b>{telco}</b>
💵 Mệnh giá: <b>{original:,}đ</b>
🎫 Mã thẻ: <code>{card_code}</code>
🔢 Serial: <code>{card_serial}</code>
💰 User nhận: <b>{received:,} xu</b>
📊 Phí (20%): <b>{fee:,} xu</b>
⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
        """
        send_telegram_all(msg)
        
        return jsonify({
            "status": "success",
            "message": f"Đổi thẻ thành công! Nhận {received:,} xu",
            "received_amount": received,
            "fee": fee,
            "telco": telco,
            "amount": original
        })
    else:
        return jsonify({
            "status": "error",
            "message": result.get('message', 'Thẻ không hợp lệ hoặc đã được sử dụng')
        })

# ==========================================
# API MUA THẺ (BOT TELEGRAM GỌI)
# ==========================================
@app.route('/api/buy-card', methods=['POST', 'GET'])
def api_buy_card():
    if request.is_json:
        data = request.json
    else:
        data = request.args.to_dict()
    
    print(f"[API BUY CARD] Nhận: {data}")
    
    user_id = data.get('user_id', 'unknown')
    telco = data.get('telco', '').upper()
    amount = str(data.get('amount', ''))
    quantity = int(data.get('quantity', 1))
    
    # Gọi API đối tác mua thẻ
    result = call_buy_api(telco, amount, quantity)
    
    if result.get('status') == 'success':
        cards = result.get('cards', [])
        cards_text = "\n".join([
            f"  {i+1}. <code>{c.get('code','***')}</code> | <code>{c.get('serial','***')}</code>"
            for i, c in enumerate(cards)
        ])
        
        msg = f"""
🛒 <b>MUA THẺ THÀNH CÔNG</b>

👤 User: <code>{user_id}</code>
📱 Nhà mạng: <b>{telco}</b>
💵 Mệnh giá: <b>{int(amount):,}đ</b>
🔢 Số lượng: <b>{quantity}</b>

🎫 <b>THẺ NHẬN ĐƯỢC:</b>
{cards_text}

⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
        """
        send_telegram_all(msg)
        
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

# ==========================================
# CALLBACK TỪ ĐỐI TÁC ĐỔI THẺ
# ==========================================
@app.route('/callback/doi-the', methods=['POST', 'GET'])
def callback_doi_the():
    if request.is_json:
        data = request.json
    else:
        data = request.args.to_dict()
    
    print(f"[CALLBACK DOI THE] {data}")
    
    if data:
        status = data.get('status', '')
        emoji = "✅" if status == 'success' else "❌" if status == 'failed' else "⏳"
        
        msg = f"""
{emoji} <b>CALLBACK ĐỔI THẺ</b>

🆔 Request: <code>{data.get('request_id','')}</code>
📱 Nhà mạng: <b>{data.get('telco','')}</b>
💵 Mệnh giá: <b>{data.get('amount',0):,}đ</b>
🎫 Mã thẻ: <code>{data.get('code','***')}</code>
🔢 Serial: <code>{data.get('serial','***')}</code>
💰 Nhận được: <b>{data.get('received_amount',0):,}đ</b>
📝 Trạng thái: <b>{status}</b>
💬 {data.get('message','')}
⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
        """
        send_telegram_all(msg)
    
    return jsonify({"status": "ok"})

# ==========================================
# CALLBACK TỪ ĐỐI TÁC MUA THẺ
# ==========================================
@app.route('/callback/mua-the', methods=['POST', 'GET'])
def callback_mua_the():
    if request.is_json:
        data = request.json
    else:
        data = request.args.to_dict()
    
    print(f"[CALLBACK MUA THE] {data}")
    
    if data:
        status = data.get('status', '')
        emoji = "✅" if status == 'success' else "❌"
        cards = data.get('cards', [])
        
        cards_text = ""
        if cards:
            cards_list = []
            for i, c in enumerate(cards, 1):
                cards_list.append(f"  {i}. <code>{c.get('code','***')}</code> | <code>{c.get('serial','***')}</code>")
            cards_text = "\n".join(cards_list)
        
        msg = f"""
{emoji} <b>CALLBACK MUA THẺ</b>

🆔 Order: <code>{data.get('order_id','')}</code>
📱 Nhà mạng: <b>{data.get('telco','')}</b>
💵 Mệnh giá: <b>{data.get('amount',0):,}đ</b>
🔢 Số lượng: <b>{len(cards) if cards else 0}</b>
📝 Trạng thái: <b>{status}</b>

🎫 <b>THẺ:</b>
{cards_text if cards_text else 'Không có dữ liệu'}

💬 {data.get('message','')}
⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}
        """
        send_telegram_all(msg)
    
    return jsonify({"status": "ok"})

# ==========================================
# API NẠP TIỀN -> GỬI TELEGRAM CHO ADMIN
# ==========================================
@app.route('/api/deposit', methods=['POST', 'GET'])
def api_deposit():
    if request.is_json:
        data = request.json
    else:
        data = request.args.to_dict()
    
    user_id = data.get('user_id', 'unknown')
    amount = data.get('amount', 0)
    content = data.get('content', '')
    method = data.get('method', 'bank')
    
    msg = f"""
💰 <b>CÓ NGƯỜI NẠP TIỀN - KIỂM TRA BANK NGAY!</b>

👤 User ID: <code>{user_id}</code>
💵 Số tiền: <b>{int(amount):,}đ</b>
📝 Nội dung CK: <b>{content}</b>
🏦 Phương thức: <b>{method}</b>
⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}

✅ <b>Vào app bank kiểm tra</b>
✅ <b>Có tiền -> cộng xu cho user</b>
❌ <b>Chưa có -> báo user chưa chuyển</b>
    """
    send_telegram_all(msg)
    
    return jsonify({
        "status": "pending",
        "message": "Yêu cầu đã gửi cho admin. Vui lòng đợi xác nhận."
    })

# ==========================================
# API RÚT TIỀN -> GỬI TELEGRAM CHO ADMIN
# ==========================================
@app.route('/api/withdraw', methods=['POST', 'GET'])
def api_withdraw():
    if request.is_json:
        data = request.json
    else:
        data = request.args.to_dict()
    
    user_id = data.get('user_id', 'unknown')
    amount = int(data.get('amount', 0))
    bank_name = data.get('bank_name', '')
    account_number = data.get('account_number', '')
    account_name = data.get('account_name', '')
    
    fee = int(amount * 5 / 100)
    receive = amount - fee
    
    msg = f"""
💸 <b>CÓ NGƯỜI RÚT TIỀN - CHUYỂN KHOẢN NGAY!</b>

👤 User ID: <code>{user_id}</code>
💵 Rút: <b>{amount:,} xu</b>
📊 Phí (5%): <b>{fee:,} xu</b>
💳 Nhận: <b>{receive:,} xu</b>
🏦 Bank: <b>{bank_name}</b>
🔢 STK: <code>{account_number}</code>
👤 Chủ TK: <b>{account_name}</b>
⏰ {datetime.datetime.now().strftime('%H:%M:%S %d/%m/%Y')}

⚠️ <b>Mở app bank chuyển {receive:,}đ ngay!</b>
    """
    send_telegram_all(msg)
    
    return jsonify({
        "status": "pending",
        "message": "Yêu cầu đã gửi cho admin. Admin sẽ chuyển khoản sớm."
    })

# ==========================================
# KIỂM TRA SỐ DƯ
# ==========================================
@app.route('/api/balance/<int:user_id>', methods=['GET'])
def api_balance(user_id):
    return jsonify({
        "user_id": user_id,
        "balance": 0,
        "note": "Admin quản lý số dư thủ công"
    })

# ==========================================
# MAIN
# ==========================================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    
    print(f"""
╔══════════════════════════════════════════╗
║       CARD247 SERVER v3.0.0              ║
╠══════════════════════════════════════════╣
║  Port: {port}                              ║
║  Admins: {len(ADMIN_LIST)}                           ║
║  Exchange API: {bool(EXCHANGE_API_URL)}     ║
║  Buy Card API: {bool(BUY_CARD_API_URL)}      ║
╚══════════════════════════════════════════╝
    """)
    
    app.run(host='0.0.0.0', port=port)

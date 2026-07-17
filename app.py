# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
import requests, datetime, os

app = Flask(__name__)

# CONFIG
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8795312989:AAGxNXoc7lRTOjRiqGkxjahXLJB1I7fYfHw")
ADMIN_IDS_STR = os.environ.get("ADMIN_IDS", "8816389907,8201945667")
ADMIN_LIST = [int(x.strip()) for x in ADMIN_IDS_STR.split(",") if x.strip()]

EXCHANGE_API_URL = os.environ.get("EXCHANGE_API_URL", "https://doithecao.com/doi-the")
EXCHANGE_PARTNER_ID = os.environ.get("EXCHANGE_PARTNER_ID", "83952560492")
EXCHANGE_PARTNER_KEY = os.environ.get("EXCHANGE_PARTNER_KEY", "a14e7d3b856674848c4e9f8677cab4ad")

BUY_CARD_API_URL = os.environ.get("BUY_CARD_API_URL", "https://doithecao.com/mua-ma-the")
BUY_CARD_PARTNER_ID = os.environ.get("BUY_CARD_PARTNER_ID", "96368346934")
BUY_CARD_PARTNER_KEY = os.environ.get("BUY_CARD_PARTNER_KEY", "06a9e7a0d1e4e6afceb0c40d4e4b4eb9")

# Tỉ giá
CARD_RATES = {
    "VIETTEL": {"10000": 8000, "20000": 16000, "50000": 40000, "100000": 80000, "200000": 160000, "500000": 400000, "1000000": 800000},
    "VINA": {"10000": 8000, "20000": 16000, "50000": 40000, "100000": 80000, "200000": 160000, "500000": 400000, "1000000": 800000},
    "MOBIFONE": {"10000": 8000, "20000": 16000, "50000": 40000, "100000": 80000, "200000": 160000, "500000": 400000, "1000000": 800000},
    "GARENA": {"10000": 8000, "20000": 16000, "50000": 40000, "100000": 80000, "200000": 160000, "500000": 400000},
    "ZING": {"10000": 8000, "20000": 16000, "50000": 40000, "100000": 80000, "200000": 160000, "500000": 400000},
    "VCOIN": {"10000": 8000, "20000": 16000, "50000": 40000, "100000": 80000, "200000": 160000, "500000": 400000}
}

def send_telegram_all(text):
    if not BOT_TOKEN: return
    for uid in ADMIN_LIST:
        try:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                         json={"chat_id": uid, "text": text, "parse_mode": "HTML"}, timeout=10)
        except: pass

def call_exchange_api(telco, code, serial, amount):
    if not EXCHANGE_API_URL: return {"status": "error", "message": "Chưa cấu hình API"}
    try:
        resp = requests.post(EXCHANGE_API_URL, json={
            "partner_id": EXCHANGE_PARTNER_ID, "partner_key": EXCHANGE_PARTNER_KEY,
            "telco": telco, "code": code, "serial": serial, "amount": amount
        }, timeout=30)
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def call_buy_api(telco, amount, quantity):
    if not BUY_CARD_API_URL: return {"status": "error", "message": "Chưa cấu hình API"}
    try:
        resp = requests.post(BUY_CARD_API_URL, json={
            "partner_id": BUY_CARD_PARTNER_ID, "partner_key": BUY_CARD_PARTNER_KEY,
            "telco": telco, "amount": amount, "quantity": quantity
        }, timeout=30)
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.route('/')
def home():
    return jsonify({"status": "online", "exchange_api": bool(EXCHANGE_API_URL), "buy_api": bool(BUY_CARD_API_URL)})

@app.route('/api/exchange', methods=['POST', 'GET'])
def api_exchange():
    data = request.json if request.is_json else request.args.to_dict()
    user_id = data.get('user_id', '')
    telco = data.get('telco', '').upper()
    amount = str(data.get('amount', ''))
    card_code = data.get('card_code', '')
    card_serial = data.get('card_serial', '')
    
    if telco not in CARD_RATES: return jsonify({"status": "error", "message": "Nhà mạng không hỗ trợ"})
    if amount not in CARD_RATES.get(telco, {}): return jsonify({"status": "error", "message": "Mệnh giá không hỗ trợ"})
    
    received = CARD_RATES[telco][amount]
    result = call_exchange_api(telco, card_code, card_serial, amount)
    
    if result.get('status') == 'success':
        send_telegram_all(f"✅ ĐỔI THẺ\n👤 {user_id}\n📱 {telco} {int(amount):,}đ\n💰 Nhận: {received:,} xu")
        return jsonify({"status": "success", "received_amount": received})
    return jsonify({"status": "error", "message": result.get('message', 'Thẻ lỗi')})

@app.route('/api/buy-card', methods=['POST', 'GET'])
def api_buy_card():
    data = request.json if request.is_json else request.args.to_dict()
    user_id = data.get('user_id', '')
    telco = data.get('telco', '').upper()
    amount = str(data.get('amount', ''))
    quantity = int(data.get('quantity', 1))
    
    result = call_buy_api(telco, amount, quantity)
    
    if result.get('status') == 'success':
        cards = result.get('cards', [])
        cards_text = "\n".join([f"{c.get('code','')} | {c.get('serial','')}" for c in cards])
        send_telegram_all(f"🛒 MUA THẺ\n👤 {user_id}\n📱 {telco} {int(amount):,}đ x{quantity}\n{cards_text}")
        return jsonify({"status": "success", "cards": cards})
    return jsonify({"status": "error", "message": result.get('message', 'Lỗi')})

@app.route('/callback/doi-the', methods=['POST', 'GET'])
def callback_doi_the():
    data = request.json if request.is_json else request.args.to_dict()
    send_telegram_all(f"📥 CALLBACK ĐỔI THẺ\n{data}")
    return jsonify({"status": "ok"})

@app.route('/callback/mua-the', methods=['POST', 'GET'])
def callback_mua_the():
    data = request.json if request.is_json else request.args.to_dict()
    send_telegram_all(f"📥 CALLBACK MUA THẺ\n{data}")
    return jsonify({"status": "ok"})

@app.route('/api/deposit', methods=['POST', 'GET'])
def api_deposit():
    data = request.json if request.is_json else request.args.to_dict()
    send_telegram_all(f"💰 NẠP TIỀN\n👤 {data.get('user_id')}\n💵 {data.get('amount',0):,}đ\n📝 {data.get('content','')}")
    return jsonify({"status": "pending", "message": "Đã gửi admin"})

@app.route('/api/withdraw', methods=['POST', 'GET'])
def api_withdraw():
    data = request.json if request.is_json else request.args.to_dict()
    send_telegram_all(f"💸 RÚT TIỀN\n👤 {data.get('user_id')}\n💵 {data.get('amount',0):,} xu\n🏦 {data.get('bank_name')} {data.get('account_number')}\n👤 {data.get('account_name')}")
    return jsonify({"status": "pending", "message": "Đã gửi admin"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
import requests
import time

# Render Port Error ကို ကျော်ရန် Dummy HTTP Server
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active!")

def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Background Thread ဖြင့် Web Server စတင်ခြင်း
threading.Thread(target=run_http_server, daemon=True).start()

BOT_TOKEN = "8941998282:AAEPK8ENpBDiBybvLAUuTQTtBiig_K4yIho"
bot = telebot.TeleBot(BOT_TOKEN)

BASE_URL = "https://api.mail.tm"
user_sessions = {}

def create_account():
    try:
        res = requests.get(f"{BASE_URL}/domains", timeout=10)
        if res.status_code != 200:
            return None, None
        
        domains = res.json().get("hydra:member", [])
        if not domains:
            return None, None
            
        domain = domains[0]["domain"]
        username = f"user_{int(time.time())}"
        address = f"{username}@{domain}"
        password = "Password123!"
        
        payload = {"address": address, "password": password}
        reg_res = requests.post(f"{BASE_URL}/accounts", json=payload, timeout=10)
        
        if reg_res.status_code == 201:
            token_res = requests.post(f"{BASE_URL}/token", json=payload, timeout=10).json()
            token = token_res.get("token")
            return address, token
    except Exception as e:
        print(f"Error creating account: {e}")
    return None, None

@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = telebot.types.InlineKeyboardMarkup()
    btn_gen = telebot.types.InlineKeyboardButton("📧 Generate Mail", callback_data="gen_mail")
    markup.add(btn_gen)
    bot.reply_to(message, "👋 Welcome to Temp Mail Bot (@spiderrio)!\n\nClick below to generate a temporary email.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_listener(call):
    chat_id = call.message.chat.id
    
    if call.data == "gen_mail":
        bot.answer_callback_query(call.id, "Generating mail...")
        address, token = create_account()
        
        if address and token:
            user_sessions[chat_id] = {
                "address": address,
                "token": token
            }
            
            markup = telebot.types.InlineKeyboardMarkup()
            btn_check = telebot.types.InlineKeyboardButton("📥 Check Inbox", callback_data="check_inbox")
            markup.add(btn_check)
            
            bot.send_message(
                chat_id, 
                f"✨ **Your Temp Mail:**\n`{address}`\n\n@spiderrio", 
                parse_mode="Markdown", 
                reply_markup=markup
            )
        else:
            bot.send_message(chat_id, "❌ Error creating email. Please try again.")
    
    elif call.data == "check_inbox":
        session = user_sessions.get(chat_id)
        if not session or not session.get("token"):
            bot.answer_callback_query(call.id, "❌ No active email found. Please generate a new mail.", show_alert=True)
            return
            
        token = session["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            res = requests.get(f"{BASE_URL}/messages", headers=headers, timeout=10)
            if res.status_code == 200:
                messages = res.json().get("hydra:member", [])
                
                if not messages:
                    bot.answer_callback_query(call.id, "📭 No messages yet. Try again in a few seconds.", show_alert=True)
                else:
                    bot.answer_callback_query(call.id, "New messages found!")
                    for msg in messages[:3]:
                        msg_id = msg["id"]
                        detail = requests.get(f"{BASE_URL}/messages/{msg_id}", headers=headers, timeout=10).json()
                        
                        from_addr = detail.get("from", {}).get("address", "Unknown")
                        subject = detail.get("subject", "No Subject")
                        intro = detail.get("intro", detail.get("text", "No Content"))
                        
                        text = f"📩 **New Email Received!**\n\n**From:** `{from_addr}`\n**Subject:** {subject}\n\n**Message:**\n{intro}\n\n@spiderrio"
                        bot.send_message(chat_id, text, parse_mode="Markdown")
            else:
                bot.answer_callback_query(call.id, "❌ Error fetching messages.", show_alert=True)
        except Exception as e:
            print(f"Error fetching inbox: {e}")
            bot.answer_callback_query(call.id, "❌ Network error. Try again.", show_alert=True)

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
      

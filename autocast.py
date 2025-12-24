import os
import json
import asyncio
import random
import re
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import ForwardMessagesRequest

# --- KONFIGURASI DARI GITHUB SECRETS ---
API_ID = os.environ.get('TG_API_ID')
API_HASH = os.environ.get('TG_API_HASH')
SESSION_STRING = os.environ.get('TG_SESSION_STRING')
TARGETS_JSON_ENV = os.environ.get('TG_TARGETS_JSON')

# Konfigurasi Baru
SOURCE_LINK = os.environ.get('TG_SOURCE_MESSAGE_LINK') # Link pesan sumber
DELAY_MIN = int(os.environ.get('TG_DELAY_SECONDS_MIN', 10)) # Default min 10 detik

# Nama Template
TARGET_TEMPLATE_NAME = os.environ.get('TG_TEMPLATE_NAME', 'Promo Harian') 

# Fallback Text
PROMO_TEXT = "Halo! Cek channel kami."

async def get_targets_from_source():
    targets = []
    data = None
    try:
        if TARGETS_JSON_ENV:
            print("🔒 Membaca target dari GitHub Secrets...")
            try: data = json.loads(TARGETS_JSON_ENV)
            except: return []
        elif os.path.exists("target_templates.json"):
            print("📂 Membaca target dari file lokal...")
            with open("target_templates.json", "r") as f:
                data = json.load(f)
        
        if data:
            for phone, templates in data.items():
                if TARGET_TEMPLATE_NAME in templates:
                    targets.extend(templates[TARGET_TEMPLATE_NAME])
    except: pass
    return targets

async def fetch_message_from_link(client, link):
    """Mengambil objek pesan dari link Telegram"""
    try:
        if "t.me/" not in link: return None
        
        link = link.split("?")[0].strip()
        parts = link.split("/")
        msg_id = int(parts[-1])
        
        chat_identifier = None
        if "/c/" in link:
            # Private group link: t.me/c/1234567890/123
            try:
                c_index = parts.index("c")
                raw_id = parts[c_index + 1]
                chat_identifier = int(f"-100{raw_id}")
            except: pass
        else:
            # Public link: t.me/username/123
            t_index = parts.index("t.me")
            chat_identifier = parts[t_index + 1]
            
        if chat_identifier:
            print(f"🔄 Fetching message {msg_id} from {chat_identifier}...")
            message = await client.get_messages(chat_identifier, ids=msg_id)
            return message
    except Exception as e:
        print(f"❌ Error fetching message: {e}")
    return None

async def main():
    if not API_ID or not API_HASH or not SESSION_STRING:
        print("❌ Error: Secrets belum lengkap.")
        return

    print("🚀 Memulai MoonTele Serverless Broadcast (True Forward Mode)...")
    
    client = TelegramClient(StringSession(SESSION_STRING), int(API_ID), API_HASH)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("❌ Sesi login kadaluarsa.")
            return

        # 1. Ambil Target
        targets = await get_targets_from_source()
        if not targets:
            print("⚠️ Tidak ada target.")
            return

        # 2. Siapkan Pesan (Source)
        message_object = None
        final_text = PROMO_TEXT

        if SOURCE_LINK:
            print(f"🔗 Link Sumber terdeteksi: {SOURCE_LINK}")
            message_object = await fetch_message_from_link(client, SOURCE_LINK)
            if message_object:
                print("✅ Pesan sumber berhasil diambil (Siap True Forward).")
            else:
                print("⚠️ Gagal mengambil pesan dari link. Fallback ke teks.")
        else:
            # Cek file lokal promo.txt
            if os.path.exists("promo.txt"):
                with open("promo.txt", "r") as f:
                    final_text = f.read()

        print(f"🎯 Total Target: {len(targets)} chat")
        print(f"⏱️  Delay antar pesan: {DELAY_MIN} - {DELAY_MIN + 5} detik")

        # 3. Eksekusi Broadcast
        success = 0
        
        # Pre-calculate InputPeer for Source (Only needed for True Forward)
        src_peer = None
        if message_object:
             src_peer = await client.get_input_entity(message_object.chat_id)

        for i, t in enumerate(targets, 1):
            chat_id = t['chat_id']
            chat_title = t.get('chat_title', str(chat_id))
            topic_id = t.get('topic_id')
            
            print(f"[{i}/{len(targets)}] Sending to {chat_title}...", end=" ")
            
            try:
                dest_peer = await client.get_input_entity(chat_id)
                
                if message_object and src_peer:
                    # TRUE FORWARD MODE (Raw API)
                    await client(ForwardMessagesRequest(
                        from_peer=src_peer,
                        id=[message_object.id],
                        to_peer=dest_peer,
                        top_msg_id=topic_id if topic_id else None
                    ))
                    print("✅ (Forwarded)")
                else:
                    # TEXT MODE
                    await client.send_message(
                        chat_id, 
                        final_text, 
                        reply_to=topic_id 
                    )
                    print("✅ (Sent Text)")
                
                success += 1
            except Exception as e:
                print(f"❌ {e}")
            
            # Delay sesuai request user
            wait = random.uniform(DELAY_MIN, DELAY_MIN + 5)
            await asyncio.sleep(wait)

        print(f"\n✨ Selesai! Sukses: {success}")

    except Exception as e:
        print(f"❌ Fatal Error: {e}")
    finally:
        if client.is_connected(): await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

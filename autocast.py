import os
import json
import asyncio
import random
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.messages import ForwardMessagesRequest

# --- KONFIGURASI DARI GITHUB SECRETS ---
API_ID = os.environ.get('TG_API_ID')
API_HASH = os.environ.get('TG_API_HASH')
SESSION_STRING = os.environ.get('TG_SESSION_STRING')
TARGETS_JSON_ENV = os.environ.get('TG_TARGETS_JSON') # <--- Sumber Data Baru (Rahasia)

# Nama Template yang akan dipakai
TARGET_TEMPLATE_NAME = os.environ.get('TG_TEMPLATE_NAME', 'Promo Harian') 

# Pesan Promosi
PROMO_TEXT = """
Halo! 👋
Ini adalah pesan otomatis dari MoonTele Serverless.
Jangan lupa cek channel kami ya!
"""

async def get_targets_from_source():
    """
    Membaca target. Prioritas:
    1. Environment Variable 'TG_TARGETS_JSON' (Dari GitHub Secrets)
    2. File lokal 'target_templates.json' (Untuk testing lokal)
    """
    targets = []
    data = None
    
    try:
        # Cek Sumber 1: Environment Variable (Secrets)
        if TARGETS_JSON_ENV:
            print("🔒 Membaca target dari GitHub Secrets (Aman)...")
            try:
                data = json.loads(TARGETS_JSON_ENV)
            except json.JSONDecodeError:
                print("❌ Error: Format JSON di Secret 'TG_TARGETS_JSON' tidak valid.")
                return []
        
        # Cek Sumber 2: File Lokal (Fallback)
        elif os.path.exists("target_templates.json"):
            print("📂 Membaca target dari file lokal 'target_templates.json'...")
            with open("target_templates.json", "r") as f:
                data = json.load(f)
        
        else:
            print("❌ Tidak ada sumber data target (Secret kosong & File tidak ada).")
            return []

        # --- Parsing Data (Format Sama) ---
        if data:
            # Cari template di semua akun
            # Struktur: { "628xxx": { "NamaTemplate": [list] } }
            found = False
            for phone, templates in data.items():
                if TARGET_TEMPLATE_NAME in templates:
                    print(f"✅ Ditemukan template '{TARGET_TEMPLATE_NAME}' pada data akun {phone}")
                    targets.extend(templates[TARGET_TEMPLATE_NAME])
                    found = True
            
            if not found:
                 print(f"⚠️ Template '{TARGET_TEMPLATE_NAME}' tidak ditemukan dalam data JSON.")

    except Exception as e:
        print(f"❌ Gagal memproses data target: {e}")
    
    return targets

async def main():
    if not API_ID or not API_HASH or not SESSION_STRING:
        print("❌ Error: Secrets TG_API_ID, TG_API_HASH, atau TG_SESSION_STRING belum diset di GitHub!")
        return

    print("🚀 Memulai MoonTele Serverless Broadcast...")
    
    try:
        client = TelegramClient(StringSession(SESSION_STRING), int(API_ID), API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ Sesi kadaluarsa atau tidak valid. Harap generate ulang SESSION_STRING.")
            return

        me = await client.get_me()
        print(f"🔑 Login sebagai: {me.first_name} (@{me.username})")

        # 1. Ambil Target (Logic Baru)
        targets = await get_targets_from_source()
        
        if not targets:
            print("⚠️ Tidak ada target untuk diproses. Stop.")
            return

        print(f"🎯 Total Target: {len(targets)} chat")

        # 2. Cek pesan (Prioritas: File promo.txt > Default Text)
        final_message = PROMO_TEXT
        if os.path.exists("promo.txt"):
            with open("promo.txt", "r") as f:
                final_message = f.read()
            print("📄 Menggunakan pesan dari promo.txt")

        # 3. Mulai Broadcast
        success = 0
        failed = 0
        
        for i, t in enumerate(targets, 1):
            chat_id = t['chat_id']
            chat_title = t.get('chat_title', str(chat_id))
            topic_id = t.get('topic_id')
            
            print(f"[{i}/{len(targets)}] Mengirim ke: {chat_title}...", end=" ")
            
            try:
                # Kirim Pesan
                await client.send_message(
                    chat_id, 
                    final_message, 
                    reply_to=topic_id 
                )
                print("✅ OK")
                success += 1
            except Exception as e:
                print(f"❌ Fail: {e}")
                failed += 1
            
            # Delay acak 5-10 detik
            wait = random.uniform(5, 10)
            await asyncio.sleep(wait)

        print(f"\n✨ Selesai! Sukses: {success}, Gagal: {failed}")

    except Exception as e:
        print(f"❌ Fatal Error: {e}")
    finally:
        if 'client' in locals() and client.is_connected():
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
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

# Nama Template yang akan dipakai (Sesuaikan jika perlu)
# Di GitHub Actions, kita bisa set ini juga lewat Environment Variable atau hardcode
TARGET_TEMPLATE_NAME = os.environ.get('TG_TEMPLATE_NAME', 'Promo Harian') 

# Pesan Promosi (Bisa diganti atau diambil dari file)
# Untuk demo, kita pakai teks hardcoded atau baca dari file 'promo.txt' jika ada
PROMO_TEXT = """
Halo! 👋
Ini adalah pesan otomatis dari MoonTele Serverless.
Jangan lupa cek channel kami ya!
"""

async def get_targets_from_template():
    """Membaca target dari target_templates.json"""
    targets = []
    try:
        if os.path.exists("target_templates.json"):
            with open("target_templates.json", "r") as f:
                data = json.load(f)
            
            # Cari template di semua akun
            # Struktur baru: { "628xxx": { "NamaTemplate": [list] } }
            for phone, templates in data.items():
                if TARGET_TEMPLATE_NAME in templates:
                    print(f"✅ Ditemukan template '{TARGET_TEMPLATE_NAME}' di akun {phone}")
                    targets.extend(templates[TARGET_TEMPLATE_NAME])
    except Exception as e:
        print(f"❌ Gagal membaca template: {e}")
    
    return targets

async def main():
    if not API_ID or not API_HASH or not SESSION_STRING:
        print("❌ Error: Secrets TG_API_ID, TG_API_HASH, atau TG_SESSION_STRING belum diset di GitHub!")
        return

    print("🚀 Memulai MoonTele Serverless Broadcast...")
    
    client = TelegramClient(StringSession(SESSION_STRING), int(API_ID), API_HASH)
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            print("❌ Sesi kadaluarsa atau tidak valid. Harap generate ulang SESSION_STRING.")
            return

        me = await client.get_me()
        print(f"🔑 Login sebagai: {me.first_name} (@{me.username})")

        # 1. Ambil Target
        targets = await get_targets_from_template()
        if not targets:
            print(f"⚠️ Tidak ada target ditemukan di template '{TARGET_TEMPLATE_NAME}'.")
            print("Pastikan Anda sudah membuat template tersebut di MoonTele dan mem-push file .json ke repo.")
            return

        print(f"🎯 Total Target: {len(targets)} chat")

        # 2. Cek apakah ada file promo.txt, jika ada pakai itu
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
                # Mode Broadcast: Send Custom Message (Text)
                # Jika ingin mode Forward, logikanya perlu disesuaikan untuk mengambil source msg dulu
                
                await client.send_message(
                    chat_id, 
                    final_message, 
                    reply_to=topic_id # Kirim ke topik jika ada
                )
                print("✅ OK")
                success += 1
            except Exception as e:
                print(f"❌ Fail: {e}")
                failed += 1
            
            # Delay acak 5-10 detik agar aman
            wait = random.uniform(5, 10)
            await asyncio.sleep(wait)

        print(f"\n✨ Selesai! Sukses: {success}, Gagal: {failed}")

    except Exception as e:
        print(f"❌ Fatal Error: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

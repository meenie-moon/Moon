import os
import asyncio
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# KREDENSIAL SEMENTARA (Akan meminta input user)
# Tujuannya hanya untuk mencetak String Session
async def main():
    print("=== TELEGRAM SESSION STRING GENERATOR ===")
    print("Alat ini akan mengubah login Anda menjadi kode String panjang")
    print("agar bisa digunakan di GitHub Actions secara aman.\n")

    api_id = input("Masukkan API ID: ").strip()
    api_hash = input("Masukkan API HASH: ").strip()
    phone = input("Masukkan Nomor HP (ex: 628xxx): ").strip()

    print("\nMenghubungkan ke Telegram...")
    
    # Menggunakan StringSession (bukan file .session)
    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        # Proses login standar
        # Jika belum login, Telethon akan meminta OTP di terminal
        await client.start(phone)
        
        # Ambil string sesi
        session_string = client.session.save()
        
        print("\n" + "="*50)
        print("✅ BERHASIL! SALIN KODE DI BAWAH INI (JANGAN SAMPAI HILANG):")
        print("="*50)
        print(session_string)
        print("="*50 + "\n")
        print("Instruksi selanjutnya:")
        print("1. Buka Repo GitHub Anda > Settings > Secrets and variables > Actions")
        print("2. Buat Repository Secret baru dengan nama: TG_SESSION_STRING")
        print("3. Paste kode panjang di atas ke dalamnya.")

if __name__ == "__main__":
    asyncio.run(main())

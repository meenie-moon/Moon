# MoonTele - Modern Telegram Automation Tool 🌙

**MoonTele** adalah alat otomasi Telegram berbasis CLI (Command Line Interface) yang kini hadir dengan **Tampilan Modern (Rich UI)**. Ditulis dalam Python, alat ini dirancang untuk membantu Anda mengelola grup, saluran, dan forum Telegram, serta berfungsi sebagai **Bot Promosi (Iklan Massal)** yang efektif dengan pengalaman pengguna yang interaktif, rapi, dan profesional.

## ✨ Fitur Baru (v2.0)

*   **🎨 Modern & Rich UI:** Antarmuka berbasis panel, tabel, dan warna yang memanjakan mata. Tidak ada lagi teks terminal yang membosankan.
*   **👥 Multi-Account System:** Kelola banyak akun Telegram dalam satu aplikasi. Ganti akun dengan mudah tanpa perlu login ulang.
*   **📊 Smart Progress Bar:** Visualisasi proses Scraping dan Broadcast dengan animasi loading bar yang akurat.
*   **🔗 True Forwarding:** Teruskan pesan dengan tag 'Forwarded from' dan jumlah view asli. Kini mendukung topik forum dan Album media.
*   **👀 Enhanced Chat List UI:** Tampilan daftar chat (Menu 1) kini lebih rapi dengan tabel interaktif.

---

## 🚀 Fitur Utama

1.  **List Chats**: Menampilkan daftar obrolan Anda dalam bentuk tabel interaktif yang rapi (ID, Nama, Tipe Chat), dengan opsi untuk menyimpan ke file.
2.  **Forward Messages (Real-time)**: Memantau dan meneruskan pesan baru secara otomatis dari sumber ke tujuan (Auto-Forward).
3.  **Scrape Past Messages**: Mengambil riwayat pesan lama (History) dari grup/forum dan menyimpannya ke file teks.
4.  **Extract Data**: Memindai dan mengekstrak ribuan Tautan (Links), IP Address, dan Domain dari riwayat chat.
5.  **Manage Templates**: Simpan daftar target grup/forum Anda sebagai "Template". Template kini tersimpan secara terisolasi untuk setiap akun.
6.  **Smart Broadcast**: Kirim pesan massal dengan aman.
    *   Mendukung input Manual, File `.txt`, atau **Forward via Link**. Pilihan mode pengiriman: 'Send as Copy' (tanpa tag) atau 'True Forward' (dengan tag 'Forwarded from' dan dukungan topik forum).
    *   **Anti-Spam Delay:** Pengaturan jeda waktu antar pesan untuk menjaga keamanan akun.
    *   **Album Support:** Otomatis mendeteksi dan mengirim album foto/video secara utuh.

---

## 🛠️ Instalasi

Pastikan Anda telah menginstal `python` dan `git` di perangkat Anda (PC/VPS/Termux).

1.  **Clone Repository:**
    ```bash
    git clone https://github.com/meenie-moon/Moon.git
    cd Moon
    ```

2.  **Install Dependensi:**
    ```bash
    pip install -r requirements.txt
    ```

---

## ⚙️ Cara Penggunaan

Jalankan skrip utama:

```bash
python3 MoonTele.py
```

### 🔐 Login & Manajemen Akun
*   Saat pertama kali dibuka, Anda akan diminta memasukkan **API ID** dan **API Hash** (Dapatkan di [my.telegram.org](https://my.telegram.org)).
*   Aplikasi akan otomatis menyimpan sesi dan Nama Asli akun Anda.
*   Gunakan menu **[7] Manage Accounts** untuk menambah atau berpindah akun kapan saja.

### 📡 Broadcast & Forwarding
1.  Pilih menu **[6] Send Message / Broadcast**.
2.  Pilih Target (Single Chat atau Template).
3.  Pilih Sumber Pesan:
    *   **[3] Forward Message (Recommended):** Cukup paste link pesan Telegram (contoh: `https://t.me/channel/123`).
        *   Setelah link, Anda akan diminta memilih mode pengiriman:
            *   **Send as Copy:** Pesan dikirim sebagai pesan baru (tanpa tag 'Forwarded from', views dimulai dari 0).
            *   **True Forward:** Pesan diteruskan secara asli (dengan tag 'Forwarded from', views asli dipertahankan, dan kini mendukung topik forum spesifik).

---

---

**Bug report and criticism, please contact me:** [t.me/MoonCiella](https://t.me/MoonCiella)

---

## ⚠️ Disclaimer

Gunakan alat ini dengan bijak. Pengiriman pesan massal (spam) yang berlebihan dapat menyebabkan akun Telegram Anda dibatasi (limit) atau diblokir.
*   Gunakan fitur **Delay** yang disediakan.
*   Jangan gunakan untuk spam yang mengganggu.
*   Pengembang tidak bertanggung jawab atas penyalahgunaan alat ini.
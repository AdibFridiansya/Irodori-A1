import google.generativeai as genai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import os
import glob
from pypdf import PdfReader
import json
from dotenv import load_dotenv

# 1. OPTIMALISASI: Keamanan Kredensial (Gunakan file .env)
load_dotenv()
GEMINI_API_KEY = os.getenv("AQ.Ab8RN6KMn5ijnRmcPEp1_W_PtPbMgBuwwXS_OGOcrMj8CR5eDQ")
TELEGRAM_TOKEN = os.getenv("8759504835:AAEsa5HrEx8qh57mpdb2eylpYlsVxejzPlk")

genai.configure(api_key=GEMINI_API_KEY)
# 2. OPTIMALISASI: Gunakan nama model yang valid dan stabil
model = genai.GenerativeModel('gemini-3.5-flash-lite')

user_states = {}
# 3. OPTIMALISASI: Cache PDF agar bot tidak membaca file berulang kali (Anti-Lag)
pdf_cache = {}

# --- FUNGSI PENYIMPANAN STATE ---
# 4. OPTIMALISASI: Menyimpan state ke JSON agar tidak hilang saat bot restart
STATE_FILE = "user_states_backup.json"

def save_states():
    # Buang object 'session' saat disave karena tidak bisa di-JSON-kan
    safe_states = {}
    for uid, data in user_states.items():
        safe_states[str(uid)] = {k: v for k, v in data.items() if k != "session"}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(safe_states, f, indent=4)

def load_states():
    global user_states
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for uid, state_data in data.items():
                state_data["session"] = None # Session harus diinisiasi ulang jika restart
                user_states[int(uid)] = state_data

# Muat data lama saat bot pertama kali dinyalakan
load_states()

# --- FUNGSI MEMBACA PDF DENGAN CACHE ---
def get_pdf_materi(bab_name):
    if bab_name in pdf_cache:
        return pdf_cache[bab_name]
    
    teks_pdf = "Materi N5 lingkungan kerja."
    if os.path.exists(bab_name):
        pdf_files = glob.glob(os.path.join(bab_name, "*.pdf"))
        if pdf_files:
            try:
                reader = PdfReader(pdf_files[0])
                teks_pdf = "".join(page.extract_text() + "\n" for page in reader.pages)
            except Exception as e:
                print(f"Gagal ekstrak PDF {bab_name}: {e}")
    
    pdf_cache[bab_name] = teks_pdf
    return teks_pdf

# --- HANDLER UTAMA ---
async def start(update: Update, context):
    user_id = update.effective_user.id
    user_states[user_id] = {
        "mode": None, 
        "session": None, 
        "terjemahan_count": 0, 
        "menunggu_next": False,
        "bab_turn": 0,
        "bab_cando": 1,
        "bab_sub_state": "persetujuan"
    }
    save_states()

    keyboard = [[InlineKeyboardButton("📝 Latihan Terjemahan", callback_data="Terjemahan")]]
    
    row = []
    for i in range(1, 19):
        row.append(InlineKeyboardButton(f"BAB {i}", callback_data=f"BAB {i}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)
    pesan = 'Pilih mode latihan bahasa Jepang untuk karier profesional Anda:'

    if update.message:
        await update.message.reply_text(pesan, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(pesan, reply_markup=reply_markup)

async def button(update: Update, context):
    query = update.callback_query
    await query.answer()

    pilihan = query.data 
    user_id = query.from_user.id

    if pilihan == "Menu":
        await start(update, context)
        return

    if user_id not in user_states:
        await start(update, context) # Re-init jika data hilang
        return

    if pilihan == "Next_Soal":
        user_states[user_id]["terjemahan_count"] += 1
        c = user_states[user_id]["terjemahan_count"]
        user_states[user_id]["menunggu_next"] = False
        save_states()

        if c <= 3: level_instruksi = "Sangat Mudah (Subjek + Predikat)"
        elif c <= 6: level_instruksi = "Mudah (Subjek + Waktu/Tempat + Objek + Predikat)"
        elif c <= 11: level_instruksi = "Sedang (Partikel gabungan/kalimat setara)"
        else: level_instruksi = "Sulit (Anak kalimat/pengandaian)"

        await context.bot.send_chat_action(chat_id=query.message.chat_id, action='typing')
        prompt_soal = f"Berikan soal terjemahan ke-{c}. Tingkat kesulitan: {level_instruksi}. Konteks: Pekerjaan. ATURAN: HANYA tulis 1 kalimat bahasa Indonesia secara langsung."
        
        try:
            response = user_states[user_id]["session"].send_message(prompt_soal)
            await query.message.reply_text(f"Soal Ke-{c}:\n\n{response.text.strip()}")
        except Exception as e:
            print(f"Error AI Next Soal: {e}")
            await query.message.reply_text("Jaringan terputus, klik tombol kembali.")
        return

    await query.message.reply_text(f"Memuat {pilihan}...")

    if pilihan == "Terjemahan":
        user_states[user_id]["mode"] = "terjemahan"
        user_states[user_id]["terjemahan_count"] = 1
        user_states[user_id]["menunggu_next"] = False
        save_states()

        instruksi_sistem = """
        Anda adalah penguji terjemahan bahasa Jepang lingkungan kerja N5.
        1. SAAT MEMBERIKAN SOAL: Berikan HANYA 1 kalimat bahasa Indonesia.
        2. SAAT SALAH: HANYA balas 'Correction: [Teks Jepang murni]'. DILARANG KERAS menambahkan cara baca hiragana dalam kurung, romaji, atau penjelasan apapun. Contoh balasan yang benar: "Correction: 会議は10時に始まります。"
        3. SAAT BENAR: Cukup balas "Benar!" tanpa kata correction.
        """
        user_states[user_id]["session"] = model.start_chat(history=[{"role": "user", "parts": [instruksi_sistem]}])
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action='typing')
        response = user_states[user_id]["session"].send_message("Berikan soal ke-1. HANYA tulis 1 kalimat bahasa Indonesia.")
        await query.message.reply_text(f"Soal Ke-1:\n\n{response.text.strip()}")
        return

    if "BAB" in pilihan:
        user_states[user_id]["mode"] = "bab"
        user_states[user_id]["bab_turn"] = 0
        user_states[user_id]["bab_cando"] = 1
        user_states[user_id]["bab_sub_state"] = "persetujuan"
        save_states()

        teks_pdf = get_pdf_materi(pilihan)

        instruksi_bab = f"""
        Anda adalah instruktur latihan bahasa Jepang N5. Materi rujukan Can-Do: {teks_pdf}
        ATURAN MUTLAK LATIHAN:
        1. TAHAP PERSETUJUAN: Berikan 1 kalimat Bahasa Indonesia tentang situasi roleplay. Jika pengguna setuju, mulai latihan. Jika menolak, cari kondisi lain.
        2. TAHAP LATIHAN: Berikan 1 kalimat Bahasa Indonesia yang HARUS diterjemahkan pengguna.
        3. EVALUASI JAWABAN (KETAT):
           - JIKA SALAH (Grammar/Kosakata/Kanji): Balas HANYA dengan 'Correction: [Kana & Kanji N5 yang benar]'. Dilarang memberi Romaji, arti, atau lanjut cerita. Tunggu pengguna mengulang.
           - JIKA BENAR: Lanjutkan roleplay dengan format mutlak:
             [Kana & Kanji Balasan Lawan Bicara]
             [Romaji Balasan Lawan Bicara]
             
             [1 Kalimat Bahasa Indonesia BARU untuk diterjemahkan pengguna selanjutnya]
        """
        user_states[user_id]["session"] = model.start_chat(history=[{"role": "user", "parts": [instruksi_bab]}])
        await context.bot.send_chat_action(chat_id=query.message.chat_id, action='typing')
        response = user_states[user_id]["session"].send_message("Mulai Can Do 1. Berikan HANYA 1 kalimat Bahasa Indonesia berisi situasi roleplay.")
        await query.message.reply_text(response.text.strip())

async def handle_message(update: Update, context):
    user_id = update.message.from_user.id
    if user_id not in user_states or user_states[user_id]["mode"] is None:
        await update.message.reply_text("Ketik /start untuk memilih mode.")
        return

    mode = user_states[user_id]["mode"]
    session = user_states[user_id]["session"]
    
    # Keamanan tambahan jika server baru restart dan session kosong
    if session is None:
        await update.message.reply_text("Sistem baru saja di-restart. Sesi AI terputus. Silakan ketik /start untuk memulai kembali.")
        return

    teks_user = update.message.text
    teks_lower = teks_user.lower()

    if mode == "terjemahan":
        if user_states[user_id]["menunggu_next"]:
            keyboard = [[InlineKeyboardButton("⏭ Lanjut Soal Berikutnya", callback_data="Next_Soal")]]
            await update.message.reply_text("Klik tombol 'Lanjut' untuk soal berikutnya.", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        await context.bot.send_chat_action(chat_id=update.message.chat_id, action='typing')
        prompt_koreksi = f"Jawaban: '{teks_user}'. Jika SALAH balas HANYA 'Correction: [Teks Jepang murni]'. DILARANG KERAS menambahkan tanda kurung atau cara baca hiragana. Jika BENAR balas singkat TANPA kata Correction."
        
        try:
            response = session.send_message(prompt_koreksi)
            user_states[user_id]["menunggu_next"] = True
            save_states()
            
            keyboard = [[InlineKeyboardButton("⏭ Lanjut Soal Berikutnya", callback_data="Next_Soal")], [InlineKeyboardButton("🏠 Menu Utama", callback_data="Menu")]]
            await update.message.reply_text(response.text.strip(), reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            # 5. OPTIMALISASI: Error logging untuk mempermudah debugging
            print(f"[Error Mode Terjemahan ID:{user_id}] -> {e}")
            await update.message.reply_text("Kesalahan jaringan, silakan kirim ulang jawaban Anda.")

    elif mode == "bab":
        await context.bot.send_chat_action(chat_id=update.message.chat_id, action='typing')
        
        sub_state = user_states[user_id]["bab_sub_state"]
        c_cando = user_states[user_id]["bab_cando"]

        try:
            if sub_state == "persetujuan":
                if any(kata in teks_lower for kata in ["tidak", "ganti", "lain", "ubah"]):
                    msg = f"Pengguna menolak situasi. Berikan HANYA 1 kalimat Bahasa Indonesia berisi situasi BARU untuk Can-Do {c_cando}."
                    response = session.send_message(msg)
                    await update.message.reply_text(response.text.strip())
                else:
                    user_states[user_id]["bab_sub_state"] = "latihan"
                    save_states()
                    msg = "Pengguna setuju. Berikan 1 kalimat Bahasa Indonesia PERTAMA yang harus diterjemahkan pengguna ke bahasa Jepang."
                    response = session.send_message(msg)
                    await update.message.reply_text(response.text.strip())

            elif sub_state == "latihan":
                msg = f"Terjemahan pengguna: '{teks_user}'\n\n[Sistem: Evaluasi jawaban. JIKA SALAH, ketik 'Correction: [Teks Benar]'. JIKA BENAR, berikan balasan dialog (Kana & Romaji) DAN 1 kalimat Indonesia baru sesuai aturan mutlak.]"
                response = session.send_message(msg)
                teks_balasan = response.text.strip()

                if not teks_balasan.startswith("Correction"):
                    user_states[user_id]["bab_turn"] += 1
                    save_states()

                if user_states[user_id]["bab_turn"] >= 10 and not teks_balasan.startswith("Correction"):
                    user_states[user_id]["bab_sub_state"] = "selesai"
                    save_states()
                    pesan_akhir = f"{teks_balasan}\n\n終わりました\nApakah ingin lanjut ke Can Do {c_cando + 1}?"
                    await update.message.reply_text(pesan_akhir)
                else:
                    await update.message.reply_text(teks_balasan)

            elif sub_state == "selesai":
                if any(kata in teks_lower for kata in ["lanjut", "ya", "yes", "mau", "ok"]):
                    user_states[user_id]["bab_cando"] += 1
                    user_states[user_id]["bab_turn"] = 0
                    user_states[user_id]["bab_sub_state"] = "persetujuan"
                    save_states()
                    msg = f"Mulai Can Do {user_states[user_id]['bab_cando']}. Berikan HANYA 1 kalimat Bahasa Indonesia menjelaskan situasi roleplay baru."
                    response = session.send_message(msg)
                    await update.message.reply_text(response.text.strip())
                else:
                    user_states[user_id]["mode"] = None
                    save_states()
                    await update.message.reply_text("Sesi diakhiri. Ketik /start untuk menu utama.")

        except Exception as e:
            print(f"[Error Mode BAB ID:{user_id}] -> {e}")
            await update.message.reply_text("Terjadi kesalahan sistem, silakan kirim ulang pesan Anda.")

async def end_chat(update: Update, context):
    user_id = update.message.from_user.id
    if user_id in user_states:
        user_states[user_id] = {"mode": None, "session": None, "terjemahan_count": 0, "menunggu_next": False, "bab_turn": 0, "bab_cando": 1, "bab_sub_state": "persetujuan"}
        save_states()
        await update.message.reply_text("お疲れ様でした！ (Otsukaresama deshita!) Sesi diakhiri.")
    else:
        await update.message.reply_text("Tidak ada sesi aktif.")

if __name__ == '__main__':
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("end", end_chat))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot Jepang Mode Karier v2 (Optimized) berjalan...")
    app.run_polling()
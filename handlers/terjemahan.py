from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from google.genai import types
import config
import prompts
import state_manager

async def init_terjemahan(update: Update, context, user_id):
    state_manager.user_states[user_id]["mode"] = "terjemahan"
    state_manager.user_states[user_id]["terjemahan_count"] = 1
    state_manager.user_states[user_id]["menunggu_next"] = False
    state_manager.save_states()

    state_manager.user_states[user_id]["chats"] = config.client.chats.create(
        model=config.MODEL_NAME,
        config=types.GenerateContentConfig(
            system_instruction=prompts.INSTRUKSI_SISTEM_TERJEMAHAN
        )
    )
    
    chat_id = update.callback_query.message.chat_id
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    
    response = state_manager.user_states[user_id]["chats"].send_message("Berikan soal ke-1. HANYA tulis 1 kalimat bahasa Indonesia.")
    await update.callback_query.message.reply_text(f"Soal Ke-1:\n\n{response.text.strip()}")

async def handle_next_soal(update: Update, context, user_id):
    query = update.callback_query
    state_manager.user_states[user_id]["terjemahan_count"] += 1
    c = state_manager.user_states[user_id]["terjemahan_count"]
    state_manager.user_states[user_id]["menunggu_next"] = False
    state_manager.save_states()

    if c <= 3: level = "Sangat Mudah (Subjek + Predikat)"
    elif c <= 6: level = "Mudah (Subjek + Waktu/Tempat + Objek + Predikat)"
    elif c <= 11: level = "Sedang (Partikel gabungan/kalimat setara)"
    else: level = "Sulit (Anak kalimat/pengandaian)"

    await context.bot.send_chat_action(chat_id=query.message.chat_id, action='typing')
    prompt_soal = f"Berikan soal terjemahan ke-{c}. Tingkat kesulitan: {level}. Konteks: Pekerjaan. ATURAN: HANYA tulis 1 kalimat bahasa Indonesia secara langsung."
    
    try:
        chat_session = state_manager.user_states[user_id]["chats"]
        response = chat_session.send_message(prompt_soal)
        await query.message.reply_text(f"Soal Ke-{c}:\n\n{response.text.strip()}")
    except Exception as e:
        print(f"Error AI Next Soal: {e}")
        await query.message.reply_text("Jaringan terputus, silakan coba lagi.")

async def process_message(update: Update, context, user_id, teks_user):
    if state_manager.user_states[user_id]["menunggu_next"]:
        keyboard = [[InlineKeyboardButton("⏭ Lanjut Soal Berikutnya", callback_data="Next_Soal")]]
        await update.message.reply_text("Klik tombol 'Lanjut' untuk soal berikutnya.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    await context.bot.send_chat_action(chat_id=update.message.chat_id, action='typing')
    prompt_koreksi = f"Jawaban: '{teks_user}'. Jika SALAH balas HANYA 'Correction: [Teks Jepang murni]'. DILARANG KERAS menambahkan tanda kurung atau cara baca hiragana. Jika BENAR balas singkat TANPA kata Correction."
    
    try:
        chat_session = state_manager.user_states[user_id]["chats"]
        response = chat_session.send_message(prompt_koreksi)
        
        state_manager.user_states[user_id]["menunggu_next"] = True
        state_manager.save_states()
        
        keyboard = [
            [InlineKeyboardButton("⏭ Lanjut Soal Berikutnya", callback_data="Next_Soal")], 
            [InlineKeyboardButton("🏠 Menu Utama", callback_data="Menu")]
        ]
        await update.message.reply_text(response.text.strip(), reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        print(f"[Error Terjemahan ID:{user_id}] -> {e}")
        await update.message.reply_text("Kesalahan jaringan, silakan kirim ulang jawaban Anda.")
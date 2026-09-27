from telegram import Update
from google.genai import types
import config
import prompts
import state_manager

async def init_bab(update: Update, context, user_id, pilihan):
    state_manager.user_states[user_id]["mode"] = "bab"
    state_manager.user_states[user_id]["bab_turn"] = 0
    state_manager.user_states[user_id]["bab_cando"] = 1
    state_manager.user_states[user_id]["bab_sub_state"] = "persetujuan"
    state_manager.save_states()

    teks_pdf = state_manager.get_pdf_materi(pilihan)
    instruksi_bab = prompts.get_instruksi_bab(teks_pdf)

    state_manager.user_states[user_id]["chats"] = config.client.chats.create(
        model=config.MODEL_NAME,
        config=types.GenerateContentConfig(
            system_instruction=instruksi_bab
        )
    )
    
    chat_id = update.callback_query.message.chat_id
    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    
    response = state_manager.user_states[user_id]["chats"].send_message("Mulai Can Do 1. Berikan HANYA 1 kalimat Bahasa Indonesia berisi situasi roleplay.")
    await update.callback_query.message.reply_text(response.text.strip())

async def process_message(update: Update, context, user_id, teks_user):
    chat_session = state_manager.user_states[user_id]["chats"]
    sub_state = state_manager.user_states[user_id]["bab_sub_state"]
    c_cando = state_manager.user_states[user_id]["bab_cando"]
    teks_lower = teks_user.lower()

    await context.bot.send_chat_action(chat_id=update.message.chat_id, action='typing')

    try:
        if sub_state == "persetujuan":
            if any(kata in teks_lower for kata in ["tidak", "ganti", "lain", "ubah", "iie", "いいえ"]):
                msg = f"Pengguna menolak situasi. Berikan HANYA 1 kalimat Bahasa Indonesia berisi situasi BARU untuk Can-Do {c_cando}."
                response = chat_session.send_message(msg)
                await update.message.reply_text(response.text.strip())
            else:
                state_manager.user_states[user_id]["bab_sub_state"] = "latihan"
                state_manager.save_states()
                msg = "Pengguna setuju. Berikan 1 kalimat Bahasa Indonesia PERTAMA yang harus diterjemahkan pengguna ke bahasa Jepang."
                response = chat_session.send_message(msg)
                await update.message.reply_text(response.text.strip())

        elif sub_state == "latihan":
            msg = f"Jawaban pengguna: '{teks_user}'\n\n[Sistem: Evaluasi jawaban. JIKA SALAH balas HANYA 'Correction: [Teks Jepang Benar]'. JIKA BENAR, berikan 1 kalimat Bahasa Indonesia BARU untuk diterjemahkan tanpa basa-basi.]"
            
            response = chat_session.send_message(msg)
            teks_balasan = response.text.strip()

            if not teks_balasan.startswith("Correction"):
                state_manager.user_states[user_id]["bab_turn"] += 1
                state_manager.save_states()
                
                # FIX BUG 1: Mencegah penumpukan pertanyaan. Jika sudah turn ke-10, buang pertanyaan ke-11 dari AI.
                if state_manager.user_states[user_id]["bab_turn"] >= 10:
                    state_manager.user_states[user_id]["bab_sub_state"] = "selesai"
                    state_manager.save_states()
                    
                    pesan_akhir = f"Jawaban Benar! ✨\n\n終わりました\nApakah ingin lanjut ke Can Do {c_cando + 1}?"
                    await update.message.reply_text(pesan_akhir)
                    return  # Berhenti di sini agar soal ke-11 tidak dikirim

            await update.message.reply_text(teks_balasan)

        elif sub_state == "selesai":
            # FIX BUG 2: Menambahkan "hai" dan huruf jepang "はい" ke dalam daftar kata kunci agar tidak dianggap membatalkan sesi.
            accepted_words = ["lanjut", "ya", "yes", "mau", "ok", "hai", "はい", "y"]
            
            if any(kata in teks_lower for kata in accepted_words):
                state_manager.user_states[user_id]["bab_cando"] += 1
                state_manager.user_states[user_id]["bab_turn"] = 0
                state_manager.user_states[user_id]["bab_sub_state"] = "persetujuan"
                state_manager.save_states()
                msg = f"Mulai Can Do {state_manager.user_states[user_id]['bab_cando']}. Berikan HANYA 1 kalimat Bahasa Indonesia menjelaskan situasi roleplay baru."
                response = chat_session.send_message(msg)
                await update.message.reply_text(response.text.strip())
            else:
                state_manager.user_states[user_id]["mode"] = None
                state_manager.save_states()
                await update.message.reply_text("Sesi diakhiri. Ketik /start untuk menu utama.")

    except Exception as e:
        print(f"[Error BAB ID:{user_id}] -> {e}")
        await update.message.reply_text("Terjadi kesalahan sistem, silakan kirim ulang pesan Anda.")
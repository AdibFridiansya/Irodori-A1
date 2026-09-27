from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import config
import state_manager
from handlers import terjemahan, bab_roleplay

# Inisialisasi awal saat bot nyala
state_manager.load_states()

async def start(update: Update, context):
    user_id = update.effective_user.id
    state_manager.user_states[user_id] = {
        "mode": None, 
        "chats": None, 
        "terjemahan_count": 0, 
        "menunggu_next": False,
        "bab_turn": 0,
        "bab_cando": 1,
        "bab_sub_state": "persetujuan"
    }
    state_manager.save_states()

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

async def button_router(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    pilihan = query.data 
    user_id = query.from_user.id

    if pilihan == "Menu":
        await start(update, context)
        return

    if user_id not in state_manager.user_states:
        await start(update, context)
        return

    if pilihan == "Next_Soal":
        await terjemahan.handle_next_soal(update, context, user_id)
        return

    await query.message.reply_text(f"Memuat {pilihan}...")

    if pilihan == "Terjemahan":
        await terjemahan.init_terjemahan(update, context, user_id)
    elif "BAB" in pilihan:
        await bab_roleplay.init_bab(update, context, user_id, pilihan)

async def message_router(update: Update, context):
    user_id = update.message.from_user.id
    
    if user_id not in state_manager.user_states or state_manager.user_states[user_id].get("mode") is None:
        await update.message.reply_text("Ketik /start untuk memilih mode.")
        return

    mode = state_manager.user_states[user_id]["mode"]
    
    if state_manager.user_states[user_id].get("chats") is None:
        await update.message.reply_text("Sesi terputus karena server di-restart. Ketik /start untuk memuat ulang.")
        return

    teks_user = update.message.text

    if mode == "terjemahan":
        await terjemahan.process_message(update, context, user_id, teks_user)
    elif mode == "bab":
        await bab_roleplay.process_message(update, context, user_id, teks_user)

async def end_chat(update: Update, context):
    user_id = update.message.from_user.id
    if user_id in state_manager.user_states:
        state_manager.user_states[user_id] = {
            "mode": None, "chats": None, "terjemahan_count": 0, "menunggu_next": False, 
            "bab_turn": 0, "bab_cando": 1, "bab_sub_state": "persetujuan"
        }
        state_manager.save_states()
        await update.message.reply_text("お疲れ様でした！ (Otsukaresama deshita!) Sesi diakhiri.")
    else:
        await update.message.reply_text("Tidak ada sesi aktif.")

if __name__ == '__main__':
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("end", end_chat))
    app.add_handler(CallbackQueryHandler(button_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))
    
    print("Bot berjalan...")
    app.run_polling()
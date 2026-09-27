import os
import json
import glob
from pypdf import PdfReader

STATE_FILE = "user_states_backup.json"
user_states = {}
pdf_cache = {}

def save_states():
    safe_states = {}
    for uid, data in user_states.items():
        # Session 'chats' dari SDK tidak bisa di-JSON-kan, jadi dibuang saat save
        safe_states[str(uid)] = {k: v for k, v in data.items() if k != "chats"}
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(safe_states, f, indent=4)

def load_states():
    global user_states
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for uid, state_data in data.items():
                    state_data["chats"] = None
                    user_states[int(uid)] = state_data
        except Exception as e:
            print(f"Gagal memuat state backup: {e}")

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
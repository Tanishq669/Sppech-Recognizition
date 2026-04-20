import speech_recognition as sr
import tkinter as tk
from tkinter import messagebox
import threading
import sqlite3
from googletrans import Translator

# ---------------- DATABASE SETUP ----------------
def init_db():
    conn = sqlite3.connect("speech_logs.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_text TEXT,
            translated_text TEXT,
            source_language TEXT,
            target_language TEXT
        )
    """)
    conn.commit()

    # Old database support
    cursor.execute("PRAGMA table_info(logs)")
    columns = [col[1] for col in cursor.fetchall()]

    if "source_language" not in columns:
        cursor.execute("ALTER TABLE logs ADD COLUMN source_language TEXT DEFAULT 'Unknown'")
    if "target_language" not in columns:
        cursor.execute("ALTER TABLE logs ADD COLUMN target_language TEXT DEFAULT 'Hindi'")

    conn.commit()
    conn.close()


def save_to_db(original_text, translated_text, source_language, target_language):
    conn = sqlite3.connect("speech_logs.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO logs (original_text, translated_text, source_language, target_language)
        VALUES (?, ?, ?, ?)
        """,
        (original_text, translated_text, source_language, target_language)
    )
    conn.commit()
    conn.close()


def load_history():
    conn = sqlite3.connect("speech_logs.db")
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(logs)")
    columns = [col[1] for col in cursor.fetchall()]

    if "source_language" in columns and "target_language" in columns:
        cursor.execute("""
            SELECT original_text, translated_text, source_language, target_language
            FROM logs
            ORDER BY id ASC
        """)
        rows = cursor.fetchall()
    else:
        cursor.execute("""
            SELECT original_text, translated_text, language
            FROM logs
            ORDER BY id ASC
        """)
        old_rows = cursor.fetchall()
        rows = [(row[0], row[1], "Unknown", row[2]) for row in old_rows]

    conn.close()
    return rows


def clear_history_db():
    conn = sqlite3.connect("speech_logs.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM logs")
    conn.commit()
    conn.close()


# ---------------- TRANSLATOR ----------------
translator = Translator()

language_map = {
    "Hindi": "hi",
    "Punjabi": "pa",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Japanese": "ja",
    "English": "en",
    "Urdu": "ur",
    "Arabic": "ar",
    "Russian": "ru"
}

source_language_names = {
    "en": "English",
    "hi": "Hindi",
    "pa": "Punjabi",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ja": "Japanese",
    "ur": "Urdu",
    "ar": "Arabic",
    "ru": "Russian"
}


# ---------------- SAFE GUI UPDATE FUNCTIONS ----------------
def set_status(text):
    window.after(0, lambda: status_label.config(text=text))


def append_text(original, translated, source_language, target_language):
    def update_box():
        output_box.insert(tk.END, f"Original ({source_language}): {original}\n")
        output_box.insert(tk.END, f"Translated ({target_language}): {translated}\n")
        output_box.insert(tk.END, "-" * 60 + "\n")
        output_box.see(tk.END)
    window.after(0, update_box)


def show_history():
    output_box.delete("1.0", tk.END)
    rows = load_history()
    for row in rows:
        original, translated, source_language, target_language = row
        output_box.insert(tk.END, f"Original ({source_language}): {original}\n")
        output_box.insert(tk.END, f"Translated ({target_language}): {translated}\n")
        output_box.insert(tk.END, "-" * 60 + "\n")


def show_error(title, msg):
    window.after(0, lambda: messagebox.showerror(title, msg))


def enable_button():
    window.after(0, lambda: btn.config(state="normal"))


def disable_button():
    window.after(0, lambda: btn.config(state="disabled"))


# ---------------- REMOVE HISTORY ----------------
def remove_history():
    answer = messagebox.askyesno("Confirm", "Do you want to delete all history?")
    if answer:
        clear_history_db()
        output_box.delete("1.0", tk.END)
        status_label.config(text="History removed ✅")


# ---------------- SPEECH FUNCTION ----------------
def recognize_speech():
    disable_button()
    try:
        selected_language = language_var.get()
        target_lang = language_map[selected_language]

        r = sr.Recognizer()

        with sr.Microphone() as source:
            set_status("Listening... Speak now 🎤")
            r.adjust_for_ambient_noise(source, duration=1)
            audio = r.listen(source, timeout=10, phrase_time_limit=8)

        set_status("Recognizing...")

        # Try multiple languages one by one
        recognized_text = None
        tried_languages = ["en-IN", "hi-IN", "pa-IN", "es-ES", "fr-FR", "de-DE", "it-IT", "ja-JP", "ur-PK", "ar-SA", "ru-RU"]

        for lang_code in tried_languages:
            try:
                recognized_text = r.recognize_google(audio, language=lang_code)
                if recognized_text:
                    break
            except:
                continue

        if not recognized_text:
            raise sr.UnknownValueError()

        original_text = recognized_text

        set_status("Detecting language...")
        detected_lang_code = translator.detect(original_text).lang
        detected_lang_name = source_language_names.get(detected_lang_code, detected_lang_code.upper())

        set_status("Translating...")
        translated_text = translator.translate(original_text, dest=target_lang).text

        save_to_db(original_text, translated_text, detected_lang_name, selected_language)
        append_text(original_text, translated_text, detected_lang_name, selected_language)

        set_status(f"Detected: {detected_lang_name} | Translated to {selected_language} ✅")

    except sr.WaitTimeoutError:
        show_error("Error", "You didn't speak in time")
        set_status("Try again")

    except sr.UnknownValueError:
        show_error("Error", "Could not understand audio")
        set_status("Speak clearly")

    except sr.RequestError:
        show_error("Error", "Internet error")
        set_status("Check connection")

    except Exception as e:
        show_error("Error", str(e))
        set_status("Error occurred")

    finally:
        enable_button()


# ---------------- THREAD ----------------
def start_listening():
    threading.Thread(target=recognize_speech, daemon=True).start()


# ---------------- GUI ----------------
window = tk.Tk()
window.title("Speech Recognition + Language Converter")
window.geometry("800x650")
window.configure(bg="#0f172a")

init_db()

title = tk.Label(
    window,
    text="SPEECH RECOGNITION SYSTEM",
    font=("Arial", 18, "bold"),
    fg="#38bdf8",
    bg="#0f172a"
)
title.pack(pady=20)

status_label = tk.Label(
    window,
    text="Click button, speak in any added language, and get translation",
    font=("Arial", 12),
    fg="#facc15",
    bg="#0f172a"
)
status_label.pack()

# Language selection
language_frame = tk.Frame(window, bg="#0f172a")
language_frame.pack(pady=10)

language_label = tk.Label(
    language_frame,
    text="Convert to:",
    font=("Arial", 12, "bold"),
    fg="white",
    bg="#0f172a"
)
language_label.pack(side="left", padx=5)

language_var = tk.StringVar()
language_var.set("Hindi")

language_menu = tk.OptionMenu(
    language_frame,
    language_var,
    "Hindi",
    "Punjabi",
    "Spanish",
    "French",
    "German",
    "Italian",
    "Japanese",
    "English",
    "Urdu",
    "Arabic",
    "Russian"
)
language_menu.config(font=("Arial", 11), bg="#38bdf8", fg="#020617", width=12)
language_menu["menu"].config(font=("Arial", 11))
language_menu.pack(side="left", padx=5)

btn = tk.Button(
    window,
    text="START VOICE CAPTURE",
    font=("Arial", 12, "bold"),
    bg="#38bdf8",
    fg="#020617",
    width=25,
    command=start_listening
)
btn.pack(pady=20)

output_box = tk.Text(
    window,
    height=18,
    width=90,
    font=("Arial", 11),
    bg="#1e293b",
    fg="white"
)
output_box.pack(pady=10)

remove_btn = tk.Button(
    window,
    text="REMOVE HISTORY",
    font=("Arial", 11, "bold"),
    bg="#ef4444",
    fg="white",
    width=20,
    command=remove_history
)
remove_btn.pack(pady=10)

show_history()

window.mainloop()
"""Gemini desktop studio for chat, images, speech, and local dictation."""
import base64
import array
import difflib
import html
import json
import math
import os
import random
import re
import shutil
import threading
import time
import tkinter as tk
import unicodedata
import wave
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from urllib.parse import quote

import requests

ROOT_DIR = Path(__file__).parent
KEY_FILE = ROOT_DIR / "gemini_api_key.txt"
HORDE_KEY_FILE = ROOT_DIR / "aihorde_api_key.txt"
CHAT_MODEL = "gemini-3.6-flash"
AUDIO_MODEL = "gemini-3.8-flash-tts"
IMAGE_DIR = ROOT_DIR / "generated_images"
HORDE_API = "https://aihorde.net/api/v2"
HORDE_ANON_KEY = "0000000000"
POLLINATIONS_KEY_FILE = ROOT_DIR / "pollinations_api_key.txt"
POLLINATIONS_IMAGE_MODEL = "google/gemini-3.1-flash-image"
POLLINATIONS_IMAGE_URL = "https://gen.pollinations.ai/image/{}"
AUDIO_DIR = ROOT_DIR / "generated_audio"
VOSK_MODEL_NAME = "vosk-model-small-es-0.42"
VOSK_MODEL_DIR = ROOT_DIR / "models" / VOSK_MODEL_NAME
if not VOSK_MODEL_DIR.is_dir():
    VOSK_MODEL_DIR = ROOT_DIR / VOSK_MODEL_NAME

BG, PANEL, FIELD = "#050608", "#101522", "#0a0e17"
FG, MUTED, ACCENT = "#edf2ff", "#a7b0c4", "#ed2638"
DESIGN_DIR = ROOT_DIR / "ima_diseño"
BRAND_IMAGE = DESIGN_DIR / "fondo_IA_GEN.png"
BRAND_LOGO = DESIGN_DIR / "logo_IA_GEN.png"
SPRITE_FILES = tuple(DESIGN_DIR / f"Sprite {index:02d} — JonGoX IA Gen.png" for index in range(1, 5))
DRONE_IMAGE = DESIGN_DIR / "dron_leer_transparente.png"
DRONE_FALLBACK_IMAGE = DESIGN_DIR / "dron_leer.png"
DRONE_TRANSPARENT_KEY = "#010203"


def get_api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    try:
        return KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def get_horde_api_key():
    key = os.environ.get("AI_HORDE_API_KEY", "").strip()
    if key:
        return key
    try:
        key = HORDE_KEY_FILE.read_text(encoding="utf-8").strip()
        return key or HORDE_ANON_KEY
    except OSError:
        return HORDE_ANON_KEY


def get_pollinations_api_key():
    key = os.environ.get("POLLINATIONS_API_KEY", "").strip()
    if key:
        return key
    try:
        return POLLINATIONS_KEY_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def gemini_request(model, payload, timeout=180, version="v1beta"):
    key = get_api_key()
    if not key:
        raise RuntimeError("Falta la clave. Guardala en C:\\IA_GEN\\gemini_api_key.txt, junto a app.py.")
    url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent"
    response = requests.post(url, headers={"x-goog-api-key": key}, json=payload, timeout=timeout)
    if not response.ok:
        try:
            detail = response.json().get("error", {}).get("message", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(f"Gemini ({response.status_code}): {detail}")
    return response.json()

class LocalAIApp:
    def __init__(self, root):
        self.root = root
        root.title("JONGOX IA GEN")
        screen_width, screen_height = root.winfo_screenwidth(), root.winfo_screenheight()
        window_width = min(screen_width - 40, max(820, int(screen_width * 0.72)))
        window_height = min(screen_height - 80, max(540, int(screen_height * 0.68)))
        root.state("normal")
        root.geometry(
            f"{window_width}x{window_height}+"
            f"{(screen_width - window_width) // 2}+{(screen_height - window_height) // 2}"
        )
        root.minsize(min(820, window_width), min(540, window_height))
        root.configure(bg=BG)
        self.messages, self.last_answer = [], ""
        self.busy, self.preview_image, self.preview_source = False, None, None
        self.audio_path = None
        self.last_question = ""
        self._image_jobs = []
        self._image_job_running = False
        self._ignore_current_image = False
        self._image_source_url = ""
        self._web_search_id = 0
        self._preview_path = None
        self._sprite_index = 0
        self._banner_size = None
        self._rune_offsets = [0.0, 0.0]
        self._visualizer_started = False
        self._audio_play_started = 0.0
        self._audio_envelope, self._audio_duration = [], 0.0
        self._image_popup_after = None
        self._image_popup = None
        self._speech_active = False
        self._speech_session = 0
        self._speech_stop_event = None
        self._speech_engine = None
        self._drone_popup = None
        self._drone_slide_after = None
        self._drone_light_after = None
        self._drone_last_word_at = 0.0
        try:
            from PIL import Image
            self.brand_source = Image.open(BRAND_IMAGE).convert("RGB")
            self.logo_source = Image.open(BRAND_LOGO).convert("RGBA")
            self.sprite_sources = [Image.open(path).convert("RGBA") for path in SPRITE_FILES if path.is_file()]
        except (ImportError, OSError):
            self.brand_source = None
            self.logo_source = None
            self.sprite_sources = []
        try:
            from PIL import Image
            drone_path = DRONE_IMAGE if DRONE_IMAGE.is_file() else DRONE_FALLBACK_IMAGE
            self.drone_source = Image.open(drone_path).convert("RGBA")
        except (ImportError, OSError):
            self.drone_source = None
        self._style()
        self.brand_canvas = tk.Canvas(root, height=200, bg="#030405",
                                      highlightthickness=0, bd=0)
        self.brand_canvas.pack(fill=tk.X)
        self.brand_canvas.bind("<Configure>", self._render_brand_banner)
        workspace = tk.Frame(root, bg="#000000")
        workspace.pack(fill=tk.BOTH, expand=True)
        self.left_runes = tk.Canvas(workspace, bg="#000000", highlightthickness=0)
        self.left_runes.place(relx=0, rely=0, relwidth=0.1, relheight=1)
        self.right_runes = tk.Canvas(workspace, bg="#000000", highlightthickness=0)
        self.right_runes.place(relx=0.9, rely=0, relwidth=0.1, relheight=1)
        center = ttk.Frame(workspace, padding=8)
        center.place(relx=0.5, rely=0.5, relwidth=0.8, relheight=1, anchor="center")
        self.tabs = ttk.Notebook(center)
        self.tabs.pack(fill=tk.BOTH, expand=True)
        self._build_chat()
        self.status = tk.StringVar(value="Listo")
        footer = tk.Frame(root, bg="#080a0e")
        footer.pack(fill=tk.X)
        tk.Label(footer, textvariable=self.status, anchor="w", padx=14, pady=7,
                 fg=MUTED, bg="#080a0e", font=("Segoe UI", 9)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.clear_button = ttk.Button(footer, text="Borrar chat", command=self._clear_all)
        self.clear_button.pack(side=tk.RIGHT, padx=12, pady=4)
        self._apply_theme(ACCENT)
        root.after(100, self._animate_brand_banner)
        root.after(100, self._animate_runes)

    def _style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=PANEL)
        style.configure("TLabel", background=PANEL, foreground=FG, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Heading.TLabel", background=PANEL, foreground=FG, font=("Segoe UI", 16, "bold"))
        style.configure("TButton", background="#263653", foreground=FG, padding=(14, 9), font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("TButton", background=[("active", "#38517a"), ("disabled", "#202a3e")])
        style.configure("ChatAction.TButton", background="#263653", foreground=FG,
                        padding=(11, 6), font=("Segoe UI", 9, "bold"), anchor="center", borderwidth=0)
        style.map("ChatAction.TButton", background=[("active", "#38517a"), ("disabled", "#202a3e")])
        style.configure("ChatSend.TButton", background=ACCENT, foreground="#ffffff",
                        padding=(12, 6), font=("Segoe UI", 9, "bold"), anchor="center", borderwidth=0)
        style.map("ChatSend.TButton", background=[("active", "#ff4353"), ("disabled", "#38365e")])
        style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", "#ff4353"), ("disabled", "#38365e")])
        style.configure("Image.Horizontal.TProgressbar", troughcolor="#202d46", background=ACCENT, bordercolor="#202d46", lightcolor=ACCENT, darkcolor=ACCENT, thickness=10)
        style.configure("TEntry", fieldbackground=FIELD, foreground=FG, insertcolor=FG, padding=9)
        style.configure("TCombobox", fieldbackground=FIELD, background="#263653", foreground=FG, arrowcolor=FG, padding=7)
        style.map("TCombobox", fieldbackground=[("readonly", FIELD)], foreground=[("readonly", FG)])
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background="#17233a", foreground=MUTED, padding=(22, 12), font=("Segoe UI", 10, "bold"), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", ACCENT), ("active", "#263653")], foreground=[("selected", "#ffffff")])

    def _render_brand_banner(self, _event=None):
        from PIL import Image, ImageOps, ImageTk

        width = max(640, self.brand_canvas.winfo_width())
        height = max(120, self.brand_canvas.winfo_height())
        if self._banner_size == (width, height):
            self._update_banner_sprite()
            return
        self._banner_size = (width, height)
        self.brand_canvas.delete("all")
        if self.brand_source is not None:
            background = ImageOps.fit(self.brand_source, (width, height), centering=(0.5, 0.5))
            background = Image.blend(background, Image.new("RGB", background.size, "#050609"), 0.20)
            self.brand_background_photo = ImageTk.PhotoImage(background)
            self.brand_canvas.create_image(0, 0, image=self.brand_background_photo, anchor="nw")

        self.brand_sprite_item = None
        if self.logo_source is not None:
            logo = self.logo_source.copy()
            logo.thumbnail((min(360, width // 3), height - 26), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(logo)
            self.brand_canvas.create_image(width - 24, height // 2, image=self.logo_photo, anchor="e")
        self._update_banner_sprite()
        self.brand_canvas.create_rectangle(0, height - 4, width, height, fill=ACCENT, outline="")

    def _update_banner_sprite(self):
        if not self.sprite_sources:
            return
        from PIL import Image, ImageTk

        height = max(120, self.brand_canvas.winfo_height())
        sprite = self.sprite_sources[self._sprite_index % len(self.sprite_sources)].copy()
        sprite.thumbnail((height - 18, height - 18), Image.Resampling.LANCZOS)
        self.sprite_photo = ImageTk.PhotoImage(sprite)
        if self.brand_sprite_item is None:
            self.brand_sprite_item = self.brand_canvas.create_image(
                26, height // 2, image=self.sprite_photo, anchor="w")
        else:
            self.brand_canvas.itemconfigure(self.brand_sprite_item, image=self.sprite_photo)
            self.brand_canvas.coords(self.brand_sprite_item, 26, height // 2)

    def _animate_brand_banner(self):
        if self.sprite_sources:
            self._sprite_index = (self._sprite_index + 1) % len(self.sprite_sources)
            self._update_banner_sprite()
        self.root.after(950, self._animate_brand_banner)

    def _apply_theme(self, _color=ACCENT):
        style = ttk.Style(self.root)
        style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", "#ff4353"), ("disabled", "#38365e")])
        style.map("TNotebook.Tab", background=[("selected", ACCENT), ("active", "#263653")],
                  foreground=[("selected", "#ffffff")])
        style.configure("Image.Horizontal.TProgressbar", troughcolor="#202d46", background=ACCENT,
                        bordercolor="#202d46", lightcolor=ACCENT, darkcolor=ACCENT, thickness=10)

    def _animate_runes(self):
        glyphs = "R+¤YMXHΔΨΩΦ†"
        for column, canvas in enumerate((self.left_runes, self.right_runes)):
            canvas.delete("all")
            height = max(100, canvas.winfo_height())
            spacing = 27
            offset = self._rune_offsets[column] % spacing
            direction = -1 if column == 0 else 1
            for stream in range(5):
                x = (stream + 0.5) * canvas.winfo_width() / 5
                shift = offset if stream % 2 == 0 else -offset
                for row in range(-1, height // spacing + 2):
                    y = row * spacing + shift
                    char = glyphs[(row * 3 + stream + column * 5) % len(glyphs)]
                    canvas.create_text(x, y, text=char, fill="#ed2638",
                                       font=("Bahnschrift", 13, "bold"))
            self._rune_offsets[column] += direction * 2.0
        self.root.after(70, self._animate_runes)

    @staticmethod
    def _text_area(parent, height):
        return tk.Text(parent, height=height, wrap=tk.WORD, undo=True, bg=FIELD, fg=FG,
                       insertbackground=FG, selectbackground=ACCENT, relief=tk.FLAT,
                       font=("Segoe UI", 11), padx=13, pady=12,
                       highlightthickness=1, highlightbackground="#263653", highlightcolor=ACCENT)

    def _build_chat(self):
        tab = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(tab, text="  Estudio IA  ")
        ttk.Label(tab, text="Conversación multimodal", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(tab, text="Pregunta a Gemini: recibirás la respuesta y una imagen relacionada de Openverse o Wikimedia Commons.",
                  style="Muted.TLabel").pack(anchor="w", pady=(3, 12))

        row = ttk.Frame(tab)
        row.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 4))
        self.entry = ttk.Entry(row, font=("Segoe UI", 11))
        self.entry.grid(row=0, column=0, columnspan=4, sticky="ew", ipady=3, pady=(0, 7))
        row.columnconfigure(0, weight=1, uniform="chat_actions")
        row.columnconfigure(1, weight=1, uniform="chat_actions")
        row.columnconfigure(2, weight=1, uniform="chat_actions")
        row.columnconfigure(3, weight=1, uniform="chat_actions")
        self.entry.bind("<Return>", self._send_message)
        self.send_button = ttk.Button(row, text="Enviar", style="ChatSend.TButton", command=self._send_message)
        self.send_button.grid(row=1, column=0, padx=(0, 4), sticky="ew")
        self.mic_button = ttk.Button(row, text="Dictar 8 s", style="ChatAction.TButton", command=self._dictate)
        self.mic_button.grid(row=1, column=1, padx=4, sticky="ew")
        self.speak_button = ttk.Button(row, text="Leer respuesta", style="ChatAction.TButton", command=self._speak_answer)
        self.speak_button.grid(row=1, column=2, padx=4, sticky="ew")
        self.stop_speak_button = ttk.Button(row, text="Detener voz", style="ChatAction.TButton",
                                            command=self._stop_speech, state=tk.DISABLED)
        self.stop_speak_button.grid(row=1, column=3, padx=(4, 0), sticky="ew")

        content = ttk.Frame(tab)
        content.pack(fill=tk.BOTH, expand=True)
        content.columnconfigure(0, weight=3, uniform="multimodal")
        content.columnconfigure(1, weight=2, uniform="multimodal")
        content.rowconfigure(0, weight=1)
        conversation = ttk.Frame(content)
        conversation.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ttk.Label(conversation, text="Conversación", style="Muted.TLabel").pack(anchor="w", pady=(0, 5))
        self.chat = scrolledtext.ScrolledText(conversation, wrap=tk.WORD, state=tk.DISABLED,
            font=("Segoe UI", 11), padx=16, pady=14, bg=FIELD, fg=FG,
            insertbackground=FG, relief=tk.FLAT, borderwidth=0,
            highlightthickness=1, highlightbackground="#263653")
        self.chat.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        self.chat.tag_configure("user", foreground="#83c5ff", spacing1=10, font=("Segoe UI", 10, "bold"))
        self.chat.tag_configure("assistant", foreground="#e7eaff", spacing1=10)
        self.chat.tag_configure("system", foreground="#ffc66d", spacing1=10)
        self._add_message("Asistente", "Hola. Escribe una pregunta para empezar.", "assistant")

        image_panel = tk.Frame(content, bg=FIELD, padx=12, pady=10,
                               highlightthickness=1, highlightbackground="#263653")
        image_panel.grid(row=0, column=1, sticky="nsew")
        image_panel.rowconfigure(1, weight=1)
        image_panel.columnconfigure(0, weight=1)
        ttk.Label(image_panel, text="Imagen encontrada en la web", style="Heading.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8))
        self.image_preview = tk.Label(
            image_panel, text="La imagen de la respuesta aparecerá aquí",
            wraplength=260, bg=FIELD, fg=MUTED, font=("Segoe UI", 11))
        self.image_preview.grid(row=1, column=0, sticky="nsew")
        self.image_preview.bind("<Configure>", self._resize_image_preview)
        self.image_preview.bind("<Enter>", self._schedule_image_popup)
        self.image_preview.bind("<Button-1>", self._open_image_popup)
        self.image_label = ttk.Label(image_panel, text="Se buscará automáticamente en Openverse y Wikimedia Commons.",
                                     style="Muted.TLabel", wraplength=260)
        self.image_label.grid(row=2, column=0, sticky="ew", pady=(6, 4))
        self.image_progress_text = tk.StringVar(value="Listo para tu consulta")
        ttk.Label(image_panel, textvariable=self.image_progress_text,
                  style="Muted.TLabel", wraplength=260).grid(row=3, column=0, sticky="w", pady=(2, 5))
        self.image_progress = ttk.Progressbar(
            image_panel, mode="indeterminate", style="Image.Horizontal.TProgressbar", maximum=100)
        self.image_progress.grid(row=4, column=0, sticky="ew")
        self.image_progress_active = False
        image_actions = ttk.Frame(image_panel)
        image_actions.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        image_actions.columnconfigure(0, weight=1)
        self.image_source_button = ttk.Button(image_actions, text="Abrir fuente", state=tk.DISABLED,
                                              command=self._open_image_source)
        self.image_source_button.grid(row=0, column=0, sticky="ew")
        ttk.Button(image_panel, text="Abrir carpeta de imágenes",
                   command=lambda: self._open_folder(IMAGE_DIR)).grid(
                       row=6, column=0, sticky="ew", pady=(6, 0))

    def _build_images(self):
        tab = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(tab, text="  Imagenes  ")
        ttk.Label(tab, text="Generador de imágenes", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(tab, text="Generación remota con modelos comunitarios. La disponibilidad y la espera dependen del proveedor.", style="Muted.TLabel").pack(anchor="w", pady=(3, 12))
        self.image_prompt = self._text_area(tab, 5)
        self.image_prompt.pack(fill=tk.X, pady=(0, 10))
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(0, 10))
        self.image_button = ttk.Button(row, text="Generar imagen", style="Accent.TButton", command=self._generate_image)
        self.image_button.pack(side=tk.LEFT)
        ttk.Button(row, text="Abrir carpeta", command=lambda: self._open_folder(IMAGE_DIR)).pack(side=tk.LEFT, padx=8)
        progress_card = tk.Frame(tab, bg="#111a2e", padx=14, pady=10,
                                 highlightthickness=1, highlightbackground="#263653")
        progress_card.pack(fill=tk.X, pady=(0, 10))
        self.image_progress_text = tk.StringVar(value="Listo para generar")
        ttk.Label(progress_card, textvariable=self.image_progress_text,
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 7))
        self.image_progress = ttk.Progressbar(progress_card, mode="indeterminate",
                                              style="Image.Horizontal.TProgressbar", maximum=100)
        self.image_progress.pack(fill=tk.X)
        self.image_progress_active = False
        self.image_preview = tk.Label(tab, text="La imagen aparecerá aquí", bg=FIELD, fg=MUTED, font=("Segoe UI", 11), height=12)
        self.image_preview.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.image_preview.bind("<Enter>", self._schedule_image_popup)
        self.image_preview.bind("<Button-1>", self._open_image_popup)
        self.image_label = ttk.Label(tab, text="", style="Muted.TLabel")
        self.image_label.pack(anchor="w")

    def _build_audio(self):
        tab = ttk.Frame(self.tabs, padding=18)
        self.tabs.add(tab, text="  Audio  ")
        ttk.Label(tab, text="Generador de voz", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(tab, text="Convierte texto en WAV. Si Gemini falla, usa una voz instalada en Windows.", style="Muted.TLabel").pack(anchor="w", pady=(3, 12))
        self.audio_text = self._text_area(tab, 4)
        self.audio_text.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.visualizer = tk.Canvas(tab, height=96, bg="#050608", highlightthickness=1,
                                    highlightbackground="#7d1420")
        self.visualizer.pack(fill=tk.X, pady=(0, 8))
        self.visualizer.bind("<Configure>", lambda _event: self._draw_audio_visualizer())
        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(row, text="Voz:").pack(side=tk.LEFT, padx=(0, 7))
        self.voice = ttk.Combobox(row, state="readonly", width=12, values=("Kore", "Aoede", "Puck", "Charon", "Fenrir"))
        self.voice.set("Kore")
        self.voice.pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(row, text="Estilo:").pack(side=tk.LEFT, padx=(0, 7))
        self.voice_style = ttk.Entry(row)
        self.voice_style.insert(0, "Calido, claro y natural")
        self.voice_style.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))
        self.audio_button = ttk.Button(row, text="Generar audio", style="Accent.TButton", command=self._generate_audio)
        self.audio_button.pack(side=tk.LEFT)
        actions = ttk.Frame(tab)
        actions.pack(fill=tk.X)
        self.play_button = ttk.Button(actions, text="Reproducir WAV", command=self._play_audio, state=tk.DISABLED)
        self.play_button.pack(side=tk.LEFT)
        self.copy_button = ttk.Button(actions, text="Guardar copia", command=self._save_audio, state=tk.DISABLED)
        self.copy_button.pack(side=tk.LEFT, padx=8)
        ttk.Button(actions, text="Abrir carpeta", command=lambda: self._open_folder(AUDIO_DIR)).pack(side=tk.LEFT)
        self.audio_label = ttk.Label(tab, text="", style="Muted.TLabel")
        self.audio_label.pack(anchor="w", pady=(12, 0))

    def _clear_all(self):
        if self.busy:
            return
        if self._speech_active:
            self._stop_speech()
        try:
            import winsound
            winsound.PlaySound(None, 0)
        except Exception:
            pass
        if self._image_popup and self._image_popup.winfo_exists():
            self._image_popup.destroy()
        self._image_popup = None
        if self._image_popup_after:
            self.root.after_cancel(self._image_popup_after)
            self._image_popup_after = None
        self.messages.clear()
        self.last_answer = ""
        self.last_question = ""
        self.entry.delete(0, tk.END)
        self.chat.configure(state=tk.NORMAL)
        self.chat.delete("1.0", tk.END)
        self.chat.configure(state=tk.DISABLED)
        self._add_message("Asistente", "Hola. Escribe una pregunta para empezar.", "assistant")
        self._image_jobs.clear()
        self._ignore_current_image = self._image_job_running
        self._web_search_id += 1
        self._image_source_url = ""
        self._preview_path = None
        self.image_source_button.configure(state=tk.DISABLED)
        self.image_preview.configure(image="", text="La imagen de la respuesta aparecerá aquí")
        self.preview_image = None
        self.preview_source = None
        self.image_label.configure(text="")
        self._set_image_progress("Listo para generar", False)
        self.status.set("Conversación limpia; los archivos guardados se conservan.")

    def _resize_image_preview(self, _event=None):
        if self.preview_source is None:
            return
        from PIL import Image, ImageTk

        width = max(120, self.image_preview.winfo_width() - 20)
        height = max(120, self.image_preview.winfo_height() - 20)
        image = self.preview_source.copy()
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        self.preview_image = ImageTk.PhotoImage(image)
        self.image_preview.configure(image=self.preview_image, text="")

    def _schedule_image_popup(self, _event=None):
        if self.preview_image:
            self._image_popup_after = self.root.after(350, self._open_image_popup)

    def _open_image_popup(self, _event=None):
        if self._image_popup_after:
            self.root.after_cancel(self._image_popup_after)
            self._image_popup_after = None
        if not self.preview_image:
            return
        if self._image_popup and self._image_popup.winfo_exists():
            self._image_popup.deiconify()
            self._image_popup.lift()
            return
        path = Path(self._preview_path) if self._preview_path else Path()
        if not path.is_file():
            return
        from PIL import Image, ImageTk
        popup = tk.Toplevel(self.root)
        popup.title("Imagen completa")
        popup.configure(bg="#050608")
        image = Image.open(path)
        image.thumbnail((1200, 820), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image)
        preview = tk.Label(popup, image=photo, bg="#050608")
        preview.image = photo
        preview.pack(padx=12, pady=12)
        popup.bind("<Escape>", lambda _event: popup.destroy())
        self._image_popup = popup

    @staticmethod
    def _read_audio_envelope(path, bins=96):
        try:
            with wave.open(str(path), "rb") as wav:
                count, rate, width = wav.getnframes(), wav.getframerate(), wav.getsampwidth()
                frames = wav.readframes(count)
            if not count or rate <= 0 or width != 2:
                return [], 0.0
            samples = array.array("h")
            samples.frombytes(frames[:len(frames) - len(frames) % 2])
            if os.sys.byteorder != "little":
                samples.byteswap()
            step = max(1, len(samples) // bins)
            envelope = [max((abs(sample) for sample in samples[i:i + step]), default=0)
                        for i in range(0, len(samples), step)][:bins]
            peak = max(envelope, default=0) or 1
            return [value / peak for value in envelope], count / rate
        except (OSError, EOFError, wave.Error, ValueError):
            return [], 0.0

    @staticmethod
    def _write_tts_wav(encoded_audio, mime_type, path):
        audio_bytes = base64.b64decode(encoded_audio)
        if audio_bytes.startswith(b"RIFF"):
            Path(path).write_bytes(audio_bytes)
            return
        rate_match = re.search(r"(?:rate\s*=\s*)(\d+)", mime_type or "", re.IGNORECASE)
        sample_rate = int(rate_match.group(1)) if rate_match else 24000
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(audio_bytes)

    def _draw_audio_visualizer(self):
        if not hasattr(self, "visualizer"):
            return
        canvas = self.visualizer
        canvas.delete("all")
        width, height = max(120, canvas.winfo_width()), max(75, canvas.winfo_height())
        mid = height // 2
        canvas.create_text(14, 13, anchor="w", text="JX-07  /  TRANSMISION DE VOZ",
                           fill="#ff6370", font=("Segoe UI", 9, "bold"))
        canvas.create_text(width - 14, 13, anchor="e", text="RX - VOX",
                           fill="#ad1f2d", font=("Segoe UI", 8, "bold"))
        canvas.create_line(16, mid, width - 16, mid, fill="#64111c")
        count = max(24, min(120, width // 12))
        for index in range(count):
            x = 18 + index * (width - 36) / max(1, count - 1)
            value = self._audio_envelope[min(len(self._audio_envelope) - 1,
                         index * len(self._audio_envelope) // count)] if self._audio_envelope else 0.07
            if self._visualizer_started:
                value = max(value, abs(math.sin(time.monotonic() * 6 - index * .42)) * .24)
            amp = 2 + value * height * .34
            canvas.create_polygon(x, mid - amp, x + 3, mid, x, mid + amp, x - 3, mid,
                                  fill="#c5162b", outline="#ff6974")
        if self._visualizer_started:
            elapsed = time.monotonic() - self._audio_play_started
            progress = min(1.0, elapsed / max(self._audio_duration, 0.1))
            playhead_x = 16 + progress * max(1, width - 32)
            canvas.create_line(playhead_x, 25, playhead_x, height - 7,
                               fill="#ff7b83", width=2)
            if progress >= 1.0:
                self._audio_playback_done()
                return
            self.root.after(60, self._draw_audio_visualizer)

    def _add_message(self, speaker, text, tag):
        self.chat.configure(state=tk.NORMAL)
        self.chat.insert(tk.END, f"{speaker}: ", tag)
        self.chat.insert(tk.END, f"{text}\n\n")
        self.chat.configure(state=tk.DISABLED)
        self.chat.see(tk.END)

    def _send_message(self, _event=None):
        if self.busy:
            return "break"
        question = self.entry.get().strip()
        if not question:
            return "break"
        self.entry.delete(0, tk.END)
        self.last_question = question
        self._add_message("Tu", question, "user")
        self.messages.append({"role": "user", "content": question})
        # Buscar la imagen en paralelo: también funciona si Gemini devuelve un error temporal.
        self._queue_response_image(question, "")
        self._set_busy(True, "Investigando la pregunta en la web...")
        threading.Thread(target=self._chat_worker, daemon=True).start()
        return "break"

    def _chat_worker(self):
        contents = [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]} for m in self.messages]
        system_instruction = (
            "Responde siempre en el mismo idioma que usa el usuario en su mensaje más reciente. "
            "Si escribe en español, responde en español. Si cambia de idioma, acompáñalo. "
            "Mantén nombres propios y términos técnicos cuando sea necesario, pero explica en ese idioma. "
            "Para preguntas informativas, investiga con la búsqueda web disponible, sintetiza los hallazgos "
            "con claridad y distingue los datos verificados de cualquier incertidumbre."
        )
        try:
            for attempt in range(3):
                try:
                    data = gemini_request(CHAT_MODEL, {
                        "systemInstruction": {"parts": [{"text": system_instruction}]},
                        "tools": [{"google_search": {}}],
                        "contents": contents,
                    }, timeout=120)
                    break
                except RuntimeError as error:
                    if attempt == 2 or not any(f"Gemini ({code})" in str(error)
                                               for code in ("503", "502", "504")):
                        raise
                    time.sleep(2 * (attempt + 1))
            parts = data["candidates"][0]["content"]["parts"]
            answer = "\n".join(part["text"] for part in parts if "text" in part).strip()
            if not answer:
                raise ValueError("Gemini devolvio una respuesta vacia.")
            sources = self._grounding_sources(data)
            if sources:
                answer += "\n\nFuentes consultadas:\n" + "\n".join(
                    f"- {title}: {url}" for title, url in sources)
            self.messages.append({"role": "assistant", "content": answer})
            self.root.after(0, self._chat_finished, answer, None)
        except requests.exceptions.ConnectionError:
            self.root.after(0, self._chat_finished, "", "No hay conexion con Gemini. Revisa internet.")
        except requests.exceptions.Timeout:
            self.root.after(0, self._chat_finished, "", "Gemini tardo demasiado en responder.")
        except RuntimeError as error:
            if "Gemini (429)" in str(error):
                try:
                    self.root.after(0, self.status.set,
                                    "Se agotó la cuota de Gemini; solicitando respuesta escrita a AI Horde...")
                    answer = self._horde_text_answer(self.messages)
                    answer += "\n\nRespuesta alternativa de AI Horde. No incluye búsqueda web en tiempo real."
                    self.messages.append({"role": "assistant", "content": answer})
                    self.root.after(0, self._chat_finished, answer, None)
                except Exception as fallback_error:
                    self.root.after(
                        0, self._chat_finished, "",
                        f"Gemini agotó la cuota y AI Horde no pudo responder: {fallback_error}",
                    )
            else:
                self.root.after(0, self._chat_finished, "", str(error))
        except (requests.exceptions.RequestException, KeyError, IndexError, ValueError) as error:
            self.root.after(0, self._chat_finished, "", str(error))

    def _horde_text_answer(self, messages):
        headers = {
            "apikey": get_horde_api_key(),
            "Client-Agent": "EstudioIA:1.0:desktop",
            "Content-Type": "application/json",
        }
        transcript = []
        for message in messages[-12:]:
            speaker = "Usuario" if message["role"] == "user" else "Asistente"
            transcript.append(f"{speaker}: {message['content']}")
        prompt = (
            "Eres un asistente útil. Contesta en el mismo idioma del último mensaje del usuario; "
            "si está en español, responde en español. Da una respuesta clara y directa. "
            "No inventes fuentes ni afirmes haber buscado en internet.\n\n"
            + "\n".join(transcript)
            + "\nAsistente:"
        )[-9000:]
        payload = {
            "prompt": prompt,
            "params": {
                "max_length": 500,
                "max_context_length": 4096,
                "n": 1,
                "temperature": 0.7,
                "rep_pen": 1.1,
            },
            "nsfw": False,
        }
        response = requests.post(
            f"{HORDE_API}/generate/text/async", headers=headers, json=payload, timeout=30)
        if not response.ok:
            raise RuntimeError(self._horde_error(response))
        request_id = response.json().get("id")
        if not request_id:
            raise RuntimeError("AI Horde no devolvió el identificador de la respuesta de texto.")

        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            time.sleep(5)
            check_response = requests.get(
                f"{HORDE_API}/generate/text/status/{request_id}", headers=headers, timeout=30)
            if not check_response.ok:
                raise RuntimeError(self._horde_error(check_response))
            status = check_response.json()
            if status.get("faulted"):
                raise RuntimeError("La cola comunitaria de texto no pudo completar la respuesta.")
            if status.get("done"):
                generations = status.get("generations", [])
                answer = generations[0].get("text", "").strip() if generations else ""
                if not answer:
                    raise RuntimeError("AI Horde terminó el trabajo sin devolver texto.")
                return answer
            waiting = status.get("queue_position", status.get("waiting", "?"))
            self.root.after(
                0, self.status.set,
                f"Respuesta escrita en cola comunitaria de AI Horde (posición {waiting})...",
            )
        raise RuntimeError("AI Horde lleva más de 15 minutos en cola; inténtalo más tarde.")

    @staticmethod
    def _grounding_sources(data):
        candidate = (data.get("candidates") or [{}])[0]
        metadata = candidate.get("groundingMetadata", {})
        sources = []
        seen = set()
        for chunk in metadata.get("groundingChunks", []):
            web = chunk.get("web", {})
            url = web.get("uri", "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append((web.get("title") or "Fuente web", url))
        return sources[:6]

    def _chat_finished(self, answer, error):
        if error:
            if self.messages and self.messages[-1]["role"] == "user":
                self.messages.pop()
            friendly_error = self._friendly_chat_error(error)
            self._add_message("Aviso", friendly_error, "system")
            self.status.set(friendly_error)
        else:
            self.last_answer = answer
            self._add_message("JonGox", answer, "assistant")
            if "Respuesta alternativa de AI Horde." in answer:
                self.status.set("Respuesta recibida desde AI Horde")
            else:
                self.status.set("Respuesta recibida desde Gemini")
        self._set_busy(False)

    @staticmethod
    def _friendly_chat_error(error):
        if "Gemini (429)" in error:
            retry = re.search(
                r"retry in (?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?", error, re.IGNORECASE
            )
            wait_text = ""
            if retry:
                hours = int(retry.group(1) or 0)
                minutes = int(retry.group(2) or 0)
                seconds = float(retry.group(3) or 0)
                total_minutes = math.ceil((hours * 3600 + minutes * 60 + seconds) / 60)
                wait_hours, wait_minutes = divmod(total_minutes, 60)
                if wait_hours:
                    wait_text = f" Intenta de nuevo en aproximadamente {wait_hours} h {wait_minutes} min."
                elif wait_minutes:
                    wait_text = f" Intenta de nuevo en aproximadamente {wait_minutes} min."
            return (
                "Gemini alcanzó el límite de solicitudes de tu cuota actual. No se reintentará "
                "automáticamente para evitar repetir llamadas." + wait_text +
                " La búsqueda de imágenes web funciona por separado."
            )
        if any(f"Gemini ({code})" in error for code in ("502", "503", "504")):
            return "Gemini sigue ocupado después de varios reintentos. Inténtalo más tarde. La búsqueda web continúa por separado."
        return error

    def _dictate(self):
        if self.busy:
            return
        if not VOSK_MODEL_DIR.is_dir():
            messagebox.showerror("Falta el modelo de voz", f"No se encontro Vosk en:\n{VOSK_MODEL_DIR}")
            return
        if not hasattr(self, "_dictation_running"):
            self._dictation_running = False
        if self._dictation_running:
            return
        self._dictation_running = True
        self.mic_button.configure(state=tk.DISABLED)
        self.status.set("Escuchando durante 8 segundos...")
        threading.Thread(target=self._record_speech, daemon=True).start()

    def _record_speech(self):
        try:
            import sounddevice as sd
            from vosk import KaldiRecognizer, Model
            recognizer = KaldiRecognizer(Model(str(VOSK_MODEL_DIR)), 16000)
            audio = sd.rec(8 * 16000, samplerate=16000, channels=1, dtype="int16")
            sd.wait()
            recognizer.AcceptWaveform(audio.tobytes())
            text = json.loads(recognizer.FinalResult()).get("text", "")
            self.root.after(0, self._dictation_finished, text, None)
        except Exception as error:
            self.root.after(0, self._dictation_finished, "", str(error))

    def _dictation_finished(self, text, error):
        self._dictation_running = False
        self.mic_button.configure(state=tk.NORMAL)
        if error:
            messagebox.showerror("Error de voz", str(error))
            self.status.set("No se pudo usar el microfono")
        elif text:
            self.entry.delete(0, tk.END)
            self.entry.insert(0, text)
            self.status.set("Dictado listo. Presiona Enviar.")
        else:
            self.status.set("No se reconocio voz. Intenta de nuevo.")

    def _speak_answer(self):
        if not self.last_answer:
            self.status.set("Primero pide una respuesta a Gemini.")
            return
        if self._speech_active:
            return
        self._speech_active = True
        self._speech_session += 1
        session = self._speech_session
        stop_event = threading.Event()
        self._speech_stop_event = stop_event
        self.speak_button.configure(state=tk.DISABLED)
        self.stop_speak_button.configure(state=tk.NORMAL)
        self._show_speaking_drone(self.last_answer, session)
        self.status.set("JonGox está leyendo la respuesta...")
        threading.Thread(target=self._speak_worker,
                         args=(self.last_answer, session, stop_event), daemon=True).start()

    def _speak_worker(self, text, session, stop_event):
        engine = None
        error = None
        try:
            import pyttsx3
            engine = pyttsx3.init()
            self._speech_engine = (session, engine)

            def on_word(_name, location, length):
                start = max(0, location)
                word = text[start:start + max(0, length)].strip()
                if word and not stop_event.is_set():
                    try:
                        self.root.after(0, self._drone_spoke_word, session, word)
                    except tk.TclError:
                        pass

            engine.connect("started-word", on_word)
            if stop_event.is_set():
                engine.stop()
            else:
                engine.say(text)
                engine.runAndWait()
        except Exception as caught:
            if not stop_event.is_set():
                error = str(caught)
        finally:
            if engine is not None:
                try:
                    engine.stop()
                except Exception:
                    pass
            if self._speech_engine and self._speech_engine[0] == session:
                self._speech_engine = None
            try:
                self.root.after(0, self._finish_speech, session, error, stop_event.is_set())
            except tk.TclError:
                pass

    def _show_speaking_drone(self, _text, session):
        self._destroy_drone_popup()
        if self.drone_source is None:
            self.status.set("No se encontró la imagen del dron; leyendo sin animación.")
            return
        from PIL import Image, ImageTk

        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg=DRONE_TRANSPARENT_KEY)
        try:
            popup.attributes("-transparentcolor", DRONE_TRANSPARENT_KEY)
        except tk.TclError:
            popup.destroy()
            self.status.set("Esta versión de Tk no admite transparencia; continúa la voz sin mostrar el dron.")
            return
        self._drone_popup = popup
        image = self.drone_source.copy()
        image.thumbnail((400, 267), Image.Resampling.LANCZOS)
        self._drone_photo = ImageTk.PhotoImage(image)
        image_width, image_height = image.size
        canvas = tk.Canvas(popup, width=image_width, height=image_height, bg=DRONE_TRANSPARENT_KEY,
                           highlightthickness=0, bd=0)
        canvas.pack()
        canvas.create_image(image_width // 2, image_height // 2, image=self._drone_photo)
        light_x, light_y = image_width * 0.5, image_height * 0.58
        self._drone_outer_light = canvas.create_oval(
            light_x - 24, light_y - 24, light_x + 24, light_y + 24,
            outline="#9d1724", width=3, tags="pulse")
        self._drone_halo_light = canvas.create_oval(
            light_x - 39, light_y - 39, light_x + 39, light_y + 39,
            outline="#7d101c", width=2, dash=(3, 5), tags="pulse")
        self._drone_inner_light = canvas.create_oval(
            light_x - 11, light_y - 11, light_x + 11, light_y + 11,
            fill="#9d1724", outline="#ff7b83", width=2, tags="pulse")
        self._drone_canvas = canvas
        popup.update_idletasks()
        width, height = image_width, image_height
        screen_width, screen_height = popup.winfo_screenwidth(), popup.winfo_screenheight()
        target_x = min(screen_width - width - 12,
                       max(12, self.root.winfo_rootx() + self.root.winfo_width() - width - 18))
        target_y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 2
        target_y = max(12, min(target_y, screen_height - height - 48))
        self._drone_target_x = target_x
        self._drone_current_x = screen_width
        self._drone_target_y = target_y
        popup.geometry(f"{width}x{height}+{screen_width}+{target_y}")
        self._slide_drone_in(session)
        self._animate_drone_light(session)

    def _slide_drone_in(self, session):
        if session != self._speech_session or not self._speech_active or not self._drone_popup:
            return
        self._drone_current_x = max(self._drone_target_x, self._drone_current_x - 28)
        self._drone_popup.geometry(f"+{self._drone_current_x}+{self._drone_target_y}")
        if self._drone_current_x > self._drone_target_x:
            self._drone_slide_after = self.root.after(12, self._slide_drone_in, session)

    def _animate_drone_light(self, session):
        if session != self._speech_session or not self._speech_active or not self._drone_popup:
            return
        now = time.monotonic()
        word_pulse = max(0.0, 1.0 - (now - self._drone_last_word_at) / 0.28)
        beat = (math.sin(now * 5.2) + 1.0) / 2.0
        intensity = max(word_pulse, 0.18 + beat * 0.32)
        radius = 22 + intensity * 11
        x = self._drone_canvas.winfo_width() * 0.5
        y = self._drone_canvas.winfo_height() * 0.58
        self._drone_canvas.coords(self._drone_outer_light, x - radius, y - radius,
                                  x + radius, y + radius)
        halo_radius = radius + 14
        self._drone_canvas.coords(self._drone_halo_light, x - halo_radius, y - halo_radius,
                                  x + halo_radius, y + halo_radius)
        self._drone_canvas.itemconfigure(
            self._drone_outer_light,
            outline="#ff364a" if intensity > 0.45 else "#74101c",
            width=2 + int(intensity * 3))
        self._drone_canvas.itemconfigure(
            self._drone_halo_light,
            outline="#ff263d" if intensity > 0.68 else "#5f1019",
            width=1 + int(intensity * 2))
        self._drone_canvas.itemconfigure(
            self._drone_inner_light,
            fill="#fff0f1" if intensity > 0.65 else "#bd1726",
            outline="#ffffff" if intensity > 0.65 else "#ff5663")
        self._drone_light_after = self.root.after(75, self._animate_drone_light, session)

    def _drone_spoke_word(self, session, word):
        if session != self._speech_session or not self._speech_active:
            return
        self._drone_last_word_at = time.monotonic()

    def _stop_speech(self):
        if not self._speech_active:
            return
        if self._speech_stop_event is not None:
            self._speech_stop_event.set()
        if self._speech_engine is not None:
            try:
                self._speech_engine[1].stop()
            except Exception:
                pass
        self._finish_speech(self._speech_session, None, True)

    def _finish_speech(self, session, error=None, stopped=False):
        if session != self._speech_session or not self._speech_active:
            return
        self._speech_active = False
        self._speech_engine = None
        self._speech_stop_event = None
        self.stop_speak_button.configure(state=tk.DISABLED)
        self.speak_button.configure(state=tk.DISABLED if self.busy else tk.NORMAL)
        if error:
            self.status.set(f"No se pudo reproducir la respuesta: {error}")
        elif stopped:
            self.status.set("Lectura de respuesta detenida")
        else:
            self.status.set("Lectura de respuesta terminada")
        if self._drone_popup and self._drone_popup.winfo_exists():
            self._drone_slide_after = self.root.after(120, self._slide_drone_out, session)

    def _slide_drone_out(self, session):
        if session != self._speech_session or not self._drone_popup:
            return
        screen_width = self.root.winfo_screenwidth()
        self._drone_current_x = min(screen_width, self._drone_current_x + 30)
        self._drone_popup.geometry(f"+{self._drone_current_x}+{self._drone_target_y}")
        if self._drone_current_x < screen_width:
            self._drone_slide_after = self.root.after(12, self._slide_drone_out, session)
        else:
            self._destroy_drone_popup()

    def _destroy_drone_popup(self):
        for attribute in ("_drone_slide_after", "_drone_light_after"):
            after_id = getattr(self, attribute, None)
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
                setattr(self, attribute, None)
        if self._drone_popup and self._drone_popup.winfo_exists():
            self._drone_popup.destroy()
        self._drone_popup = None

    @staticmethod
    def _response_image_prompt(question, answer):
        question = re.sub(r"\s+", " ", question).strip()[:900]
        answer = re.sub(r"\s+", " ", answer).strip()[:1200]
        return (
            "Create one clear, detailed image that directly illustrates the user's original request. "
            "Treat the request as the source of truth; use the answer only as supporting context. "
            "Do not substitute a different subject, place, country, or object. If a specific map or diagram is requested, "
            "depict that exact subject accurately. Do not add captions, labels, or watermarks.\n"
            f"User request: {question}\nRelevant answer context: {answer}"
        )

    def _queue_response_image(self, question, answer):
        self._image_jobs.clear()
        self._ignore_current_image = self._image_job_running
        self._web_search_id += 1
        search_id = self._web_search_id
        self._image_source_url = ""
        self.image_source_button.configure(state=tk.DISABLED)
        self.preview_image = None
        self.preview_source = None
        self._preview_path = None
        self.image_preview.configure(image="", text="Buscando una imagen relacionada...")
        self.image_label.configure(text="Buscando en Openverse y Wikimedia Commons; se mostrará licencia y fuente.")
        self._set_image_progress("Buscando imágenes relacionadas en la web...", True)
        threading.Thread(target=self._web_image_worker, args=(question, search_id), daemon=True).start()

    @staticmethod
    def _commons_text(metadata, key, fallback=""):
        value = metadata.get(key, {}).get("value", fallback)
        value = re.sub(r"<[^>]*>", " ", str(value))
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    @classmethod
    def _commons_query_variants(cls, query):
        normalized = unicodedata.normalize("NFKD", query.casefold())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        corrected_words = []
        for word in normalized.split():
            close_match = difflib.get_close_matches(word, ("formula",), n=1, cutoff=0.72)
            corrected_words.append(close_match[0] if close_match else word)
        normalized = " ".join(corrected_words)
        stop_words = {
            "a", "al", "algun", "algunos", "algunas", "como", "cual", "cuales", "de",
            "del", "desde", "donde", "el", "ella", "en", "es", "esta", "este", "la",
            "las", "lo", "los", "mas", "me", "mi", "para", "por", "que", "se", "sobre",
            "su", "todo", "todos", "una", "uno", "un", "y", "the", "about", "all", "what",
        }
        words = [word for word in normalized.split() if word not in stop_words]
        concise = " ".join(words)
        variants = []
        if re.search(r"\b(formula\s*(uno|one|1)|f\s*1|f1|gran\s*premio)\b", normalized):
            variants.extend(("Formula One", "Formula 1", "F1", "Grand Prix"))
        if concise:
            variants.append(concise)
        if query.strip():
            variants.append(query.strip()[:350])
        return list(dict.fromkeys(variants))

    @classmethod
    def _search_commons_image(cls, query):
        from io import BytesIO
        from PIL import Image

        for search_query in cls._commons_query_variants(query)[:2]:
            response = requests.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action": "query", "generator": "search", "gsrsearch": search_query,
                    "gsrnamespace": 6, "gsrlimit": 12, "prop": "imageinfo",
                    "iiprop": "url|extmetadata", "iiurlwidth": 1200,
                    "format": "json", "formatversion": 2,
                },
                headers={"User-Agent": "JONGOX-IA-GEN/1.0 (desktop image search)"},
                timeout=(7, 16),
            )
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", [])
            for page in pages[:8]:
                info_list = page.get("imageinfo", [])
                if not info_list:
                    continue
                info = info_list[0]
                image_url = info.get("thumburl") or info.get("url")
                source_url = info.get("descriptionurl", "")
                if not info.get("mime", "").startswith("image/") or not image_url or not source_url:
                    continue
                metadata = info.get("extmetadata", {})
                license_name = cls._commons_text(metadata, "LicenseShortName", "Licencia no indicada")
                artist = cls._commons_text(metadata, "Artist", "Autor no indicado")
                try:
                    image_response = requests.get(
                        image_url, headers={"User-Agent": "JONGOX-IA-GEN/1.0 (desktop image search)"},
                        timeout=(7, 16),
                    )
                    image_response.raise_for_status()
                    with Image.open(BytesIO(image_response.content)) as image:
                        image.load()
                        if image.width < 200 or image.height < 150:
                            continue
                        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
                        path = IMAGE_DIR / f"web_{datetime.now():%Y%m%d_%H%M%S_%f}.png"
                        image.convert("RGB").save(path, format="PNG")
                except (requests.exceptions.RequestException, OSError, ValueError):
                    continue
                title = page.get("title", "Archivo de Wikimedia Commons").removeprefix("File:")
                return str(path), title, license_name, artist, source_url
        raise RuntimeError("No se encontró una imagen adecuada en Wikimedia Commons para esta consulta.")

    @classmethod
    def _search_openverse_image(cls, query):
        """Find openly licensed images across multiple catalogs via Openverse."""
        from io import BytesIO
        from PIL import Image

        for search_query in cls._commons_query_variants(query)[:2]:
            response = requests.get(
                "https://api.openverse.org/v1/images/",
                params={"q": search_query, "page_size": 12, "mature": "false"},
                headers={"User-Agent": "JONGOX-IA-GEN/1.0 (desktop image search)"},
                timeout=(7, 16),
            )
            response.raise_for_status()
            for item in response.json().get("results", [])[:8]:
                image_url = item.get("thumbnail") or item.get("url")
                source_url = item.get("foreign_landing_url") or item.get("detail_url")
                if not image_url or not source_url:
                    continue
                try:
                    image_response = requests.get(
                        image_url,
                        headers={"User-Agent": "JONGOX-IA-GEN/1.0 (desktop image search)"},
                        timeout=(7, 16),
                    )
                    image_response.raise_for_status()
                    with Image.open(BytesIO(image_response.content)) as image:
                        image.load()
                        if image.width < 200 or image.height < 150:
                            continue
                        IMAGE_DIR.mkdir(parents=True, exist_ok=True)
                        path = IMAGE_DIR / f"web_{datetime.now():%Y%m%d_%H%M%S_%f}.png"
                        image.convert("RGB").save(path, format="PNG")
                    license_name = item.get("license", "Licencia no indicada")
                    if item.get("license_version"):
                        license_name += f" {item['license_version']}"
                    artist = item.get("creator") or "Autor no indicado"
                    title = item.get("title") or "Imagen de Openverse"
                    return str(path), title, license_name, artist, source_url
                except (requests.exceptions.RequestException, OSError, ValueError):
                    continue
        raise RuntimeError("Openverse no encontró una imagen adecuada para esta consulta.")

    @classmethod
    def _search_web_image(cls, query):
        errors = []
        for provider, search in (("Openverse", cls._search_openverse_image),
                                 ("Wikimedia Commons", cls._search_commons_image)):
            try:
                return search(query)
            except Exception as error:
                errors.append(f"{provider}: {error}")
        raise RuntimeError("No se encontró imagen en Openverse ni en Wikimedia Commons. " + " ".join(errors))

    def _web_image_worker(self, question, search_id):
        errors = []
        for provider, search in (("Openverse", self._search_openverse_image),
                                 ("Wikimedia Commons", self._search_commons_image)):
            try:
                self.root.after(0, self._set_image_progress, f"Buscando opciones en {provider}...", True)
                result = search(question)
                self.root.after(0, self._web_image_finished, search_id, *result, None)
                return
            except Exception as error:
                errors.append(f"{provider}: {error}")
        message = "No se encontró una imagen adecuada. Se probaron Openverse y Wikimedia Commons."
        self.root.after(0, self._web_image_finished, search_id, "", "", "", "", "",
                        f"{message} {' '.join(errors)}")

    def _web_image_finished(self, search_id, path, title, license_name, artist, source_url, error):
        if search_id != self._web_search_id:
            return
        if error:
            self.image_preview.configure(image="", text="No se encontró una imagen web.")
            self.image_label.configure(text=f"{error} La búsqueda automática terminó sin resultados.")
            self._set_image_progress("Búsqueda finalizada sin imagen", False)
            if not self.busy:
                self.status.set("No se encontró imagen web")
            return
        try:
            from PIL import Image
            with Image.open(path) as image:
                self.preview_source = image.convert("RGB")
            self._preview_path = path
            self._resize_image_preview()
            self._image_source_url = source_url
            self.image_source_button.configure(state=tk.NORMAL)
            self.image_label.configure(
                text=f"{title}\nLicencia: {license_name}\nAutor: {artist}\nGuardada en: {path}")
            self._set_image_progress("Imagen encontrada y guardada", False)
            if not self.busy:
                self.status.set("Imagen web lista")
        except Exception as display_error:
            self._set_image_progress("Imagen encontrada; no se pudo mostrar", False)
            self.image_label.configure(text=f"Imagen guardada en {path}: {display_error}")

    def _open_image_source(self):
        if self._image_source_url:
            webbrowser.open(self._image_source_url)

    def _start_next_image_job(self):
        if self._image_job_running or not self._image_jobs:
            return
        prompt = self._image_jobs.pop(0)
        self._image_job_running = True
        self._ignore_current_image = False
        self.preview_image = None
        self.preview_source = None
        self._preview_path = None
        self.image_preview.configure(image="", text="Generando imagen relacionada...")
        self.image_label.configure(text="Pollinations primero; AI Horde como alternativa.")
        self._set_image_progress("Generando una imagen a partir de la consulta...", True)
        threading.Thread(target=self._image_worker, args=(prompt,), daemon=True).start()

    def _generate_image(self):
        if self.busy:
            return
        prompt = self.image_prompt.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showinfo("Describe la imagen", "Escribe que imagen quieres crear.")
            return
        self._set_busy(True, "Buscando proveedor de imagen disponible...")
        self._set_image_progress("Pollinations primero; AI Horde si no está disponible.", True)
        threading.Thread(target=self._image_worker, args=(prompt,), daemon=True).start()

    def _set_image_progress(self, text, active):
        self.image_progress_text.set(text)
        if active and not self.image_progress_active:
            self.image_progress.start(14)
            self.image_progress_active = True
        elif not active and self.image_progress_active:
            self.image_progress.stop()
            self.image_progress_active = False

    @staticmethod
    def _horde_error(response):
        try:
            data = response.json()
            detail = data.get("message") or data.get("error") or data
        except ValueError:
            detail = response.text[:500]
        return f"AI Horde ({response.status_code}): {detail}"

    @staticmethod
    def _request_pollinations_image(prompt, api_key):
        from io import BytesIO
        from PIL import Image

        response = requests.get(
            POLLINATIONS_IMAGE_URL.format(quote(prompt, safe="")),
            headers={"Authorization": f"Bearer {api_key}"},
            params={"model": POLLINATIONS_IMAGE_MODEL, "width": 768,
                    "height": 768, "nologo": "true"},
            timeout=(20, 240),
        )
        if not response.ok:
            raise RuntimeError(f"Pollinations ({response.status_code}): {response.text[:300]}")
        with Image.open(BytesIO(response.content)) as image:
            image.load()
            IMAGE_DIR.mkdir(parents=True, exist_ok=True)
            path = IMAGE_DIR / f"pollinations_{datetime.now():%Y%m%d_%H%M%S}.png"
            image.convert("RGB").save(path, format="PNG")
        return path

    def _image_worker(self, prompt):
        pollinations_key = get_pollinations_api_key()
        if pollinations_key:
            self.root.after(0, self._set_image_progress, "Probando Pollinations...", True)
            try:
                path = self._request_pollinations_image(prompt, pollinations_key)
                self.root.after(0, self._image_finished, str(path), None)
                return
            except requests.exceptions.Timeout:
                self.root.after(0, self._image_finished, "", "Pollinations tardo demasiado. No se repite para evitar generar dos veces.")
                return
            except Exception as error:
                self.root.after(0, self._set_image_progress,
                                f"Pollinations no disponible; intentando AI Horde: {error}", True)
        headers = {"apikey": get_horde_api_key(), "Client-Agent": "EstudioIA:1.0:desktop", "Content-Type": "application/json"}
        payload = {
            "prompt": prompt,
            "params": {"width": 512, "height": 512, "steps": 20, "n": 1},
            "nsfw": False,
            "censor_nsfw": True,
        }
        try:
            response = requests.post(f"{HORDE_API}/generate/async", headers=headers, json=payload, timeout=45)
            if not response.ok:
                raise RuntimeError(self._horde_error(response))
            request_id = response.json().get("id")
            if not request_id:
                raise RuntimeError("AI Horde no devolvio el identificador del trabajo.")
            self.root.after(0, self._set_image_progress, "Solicitud aceptada; esperando un equipo voluntario...", True)

            deadline = time.monotonic() + 900
            while time.monotonic() < deadline:
                time.sleep(5)
                check_response = requests.get(f"{HORDE_API}/generate/check/{request_id}", headers=headers, timeout=30)
                if not check_response.ok:
                    raise RuntimeError(self._horde_error(check_response))
                check = check_response.json()
                if check.get("faulted"):
                    raise RuntimeError("La cola comunitaria no pudo completar esta imagen. Prueba de nuevo mas tarde.")
                if check.get("done"):
                    break
                waiting = check.get("waiting", "?")
                processing = check.get("processing", "?")
                if check.get("is_possible") is False:
                    progress = "No hay equipos disponibles para esta solicitud por ahora. Sigue esperando..."
                elif isinstance(processing, int) and processing > 0:
                    progress = f"Generando imagen... ({waiting} trabajos esperando)"
                else:
                    progress = f"En cola de AI Horde... ({waiting} trabajos esperando)"
                self.root.after(0, self._set_image_progress, progress, True)
                self.root.after(0, self.status.set, progress)
            else:
                raise RuntimeError("La cola supero 15 minutos. Puedes volver a intentarlo mas tarde.")

            result_response = requests.get(f"{HORDE_API}/generate/status/{request_id}", headers=headers, timeout=45)
            if not result_response.ok:
                raise RuntimeError(self._horde_error(result_response))
            generations = result_response.json().get("generations", [])
            if not generations or not generations[0].get("img"):
                raise RuntimeError("AI Horde termino el trabajo sin devolver una imagen.")
            self.root.after(0, self._set_image_progress, "Generacion lista; descargando imagen...", True)
            image_response = requests.get(generations[0]["img"], timeout=90)
            if not image_response.ok:
                raise RuntimeError(f"No se pudo descargar la imagen ({image_response.status_code}).")
            IMAGE_DIR.mkdir(parents=True, exist_ok=True)
            path = IMAGE_DIR / f"horde_{datetime.now():%Y%m%d_%H%M%S}.png"
            path.write_bytes(image_response.content)
            self.root.after(0, self._image_finished, str(path), None)
        except requests.exceptions.Timeout:
            self.root.after(0, self._image_finished, "", "La conexion tardo demasiado. Revisa internet e intenta de nuevo.")
        except requests.exceptions.RequestException as error:
            self.root.after(0, self._image_finished, "", f"No se pudo conectar con AI Horde: {error}")
        except Exception as error:
            self.root.after(0, self._image_finished, "", str(error))

    def _image_finished(self, path, error):
        self._image_job_running = False
        ignore_result = self._ignore_current_image
        self._ignore_current_image = False
        if not ignore_result:
            if error:
                self._set_image_progress("No se pudo completar la imagen", False)
                self.image_label.configure(text=f"No se pudo crear la imagen: {error}")
                self.status.set(f"Respuesta lista; imagen no disponible: {error}")
            else:
                try:
                    from PIL import Image
                    with Image.open(path) as image:
                        self.preview_source = image.convert("RGB")
                    self._preview_path = path
                    self._resize_image_preview()
                    self.image_label.configure(text=f"Guardada en: {path}")
                    self._set_image_progress("Imagen lista y guardada correctamente", False)
                    self.status.set("Respuesta e imagen listas")
                except Exception as display_error:
                    self._set_image_progress("Imagen guardada; no se pudo mostrar", False)
                    self.image_label.configure(text=f"Imagen guardada en {path}, pero no se pudo mostrar: {display_error}")
                    self.status.set("Imagen guardada; no se pudo mostrar")
        if self._image_jobs:
            self._start_next_image_job()
        elif ignore_result:
            self._set_image_progress("Listo para tu consulta", False)

    def _generate_audio(self):
        if self.busy:
            return
        text = self.audio_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("Escribe el texto", "Escribe el texto que quieres convertir en voz.")
            return
        if len(text) > 12000:
            messagebox.showinfo("Texto muy largo", "Divide el texto en fragmentos de hasta 12000 caracteres.")
            return
        self._set_busy(True, "Generando audio con Gemini...")
        threading.Thread(target=self._audio_worker, args=(text, self.voice.get(), self.voice_style.get().strip()), daemon=True).start()

    def _audio_worker(self, text, voice, style):
        part = {"text": text}
        if style:
            part["speech_metadata"] = {"style": style}
        payload = {"contents": [{"role": "user", "parts": [part]}], "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"voice": voice}}}}
        try:
            try:
                data = gemini_request(AUDIO_MODEL, payload, timeout=300)
                parts = data["candidates"][0]["content"]["parts"]
                audio_part = next((item.get("inlineData") for item in parts
                                   if item.get("inlineData", {}).get("data")), None)
                if not audio_part:
                    raise RuntimeError("Gemini no devolvio audio.")
                AUDIO_DIR.mkdir(parents=True, exist_ok=True)
                path = AUDIO_DIR / f"voz_{datetime.now():%Y%m%d_%H%M%S}.wav"
                self._write_tts_wav(audio_part["data"], audio_part.get("mimeType", ""), path)
                self.root.after(0, self._audio_finished, str(path), None, "Audio generado con Gemini.")
            except Exception as gemini_error:
                self.root.after(0, self.status.set, "Gemini no esta disponible; creando WAV con voz local de Windows...")
                path = self._create_local_audio(text)
                notice = f"Gemini no estuvo disponible. Audio creado con voz local de Windows. Detalle: {gemini_error}"
                self.root.after(0, self._audio_finished, str(path), None, notice)
        except Exception as error:
            self.root.after(0, self._audio_finished, "", str(error), None)

    @staticmethod
    def _create_local_audio(text):
        import pyttsx3

        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        path = AUDIO_DIR / f"voz_local_{datetime.now():%Y%m%d_%H%M%S}.wav"
        engine = pyttsx3.init()
        try:
            voices = engine.getProperty("voices") or []
            for candidate in voices:
                info = f"{getattr(candidate, 'name', '')} {getattr(candidate, 'id', '')} {getattr(candidate, 'languages', '')}".lower()
                if any(language in info for language in ("spanish", "español", "es_es", "es-es", "es_mx", "es-mx")):
                    engine.setProperty("voice", candidate.id)
                    break
            engine.setProperty("rate", 165)
            engine.save_to_file(text, str(path))
            engine.runAndWait()
        finally:
            engine.stop()
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("Windows no pudo crear el archivo de voz. Revisa las voces instaladas.")
        return path

    def _audio_finished(self, path, error, notice=None):
        self._set_busy(False)
        if error:
            self.status.set(f"No se pudo generar audio: {error}")
            messagebox.showerror("Generacion de audio", str(error))
            return
        self.audio_path = Path(path)
        self._audio_envelope, self._audio_duration = self._read_audio_envelope(self.audio_path)
        self._draw_audio_visualizer()
        self.audio_label.configure(text=f"Audio guardado en: {path}")
        self.play_button.configure(state=tk.NORMAL)
        self.copy_button.configure(state=tk.NORMAL)
        self.status.set(notice or "Audio generado y guardado en WAV")

    def _play_audio(self):
        if self.audio_path and self.audio_path.exists():
            try:
                import winsound
                winsound.PlaySound(str(self.audio_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
                self._visualizer_started = True
                self._audio_play_started = time.monotonic()
                self._draw_audio_visualizer()
                self.status.set("Reproduciendo audio...")
            except Exception as error:
                messagebox.showerror("Reproduccion", str(error))

    def _audio_playback_done(self):
        self._visualizer_started = False
        self._draw_audio_visualizer()
        self.status.set("Reproduccion terminada")

    def _save_audio(self):
        if not self.audio_path or not self.audio_path.exists():
            return
        target = filedialog.asksaveasfilename(title="Guardar audio", defaultextension=".wav", initialfile=self.audio_path.name, filetypes=(("Audio WAV", "*.wav"), ("Todos los archivos", "*.*")))
        if target:
            shutil.copy2(self.audio_path, target)
            self.status.set(f"Copia guardada: {target}")

    def _open_folder(self, folder):
        folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(folder))
        except AttributeError:
            messagebox.showinfo("Carpeta", str(folder))
        except OSError as error:
            messagebox.showerror("No se pudo abrir la carpeta", str(error))

    def _set_busy(self, busy, status_text=None):
        self.busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.send_button.configure(state=state)
        self.mic_button.configure(state=state)
        self.speak_button.configure(state=tk.DISABLED if busy or self._speech_active else tk.NORMAL)
        self.stop_speak_button.configure(state=tk.NORMAL if self._speech_active else tk.DISABLED)
        self.clear_button.configure(state=state)
        if status_text:
            self.status.set(status_text)


def main():
    root = tk.Tk()
    LocalAIApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

"""Arayüz: link ekleme, indirme kuyruğu, küçük resimler, format seçimi, ilerleme ve bileşen güncellemesi.

Ağ işleri (güncelleme, video bilgisi, küçük resim, indirme) arka plan iş parçacıklarında çalışır. Onlar sonuçlarını
self.events kuyruğuna koyar; pencereye sadece ana iş parçacığı dokunur (poll_events).
"""
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
import traceback
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import ImageTk

import updater
from app_info import REPOSITORY_URL, VERSION, find_tool, resource_path
from downloader import Download, DownloadFailed, fetch_info
from formats import AUDIO_FORMATS, download_options
from i18n import format_duration, format_speed, translate
from links import LinkError, canonical_url, parse_link
from settings import FORMAT_CHOICES, load_settings, save_settings
from thumbnails import fetch_thumbnail

FONT = "Segoe UI"
POLL_MS = 100
MAX_QUEUE = 1000
THUMBNAIL_SIZE = (96, 54)
RETRY_STATES = ("ready", "cancelled", "failed")  # "İndir"e basınca sıraya girenler
START_STATES = RETRY_STATES + ("reading",)  # okunan video varken de "İndir"e basılabilir; okununca iner
DONE_STATES = ("done", "exists")

THEMES = {
    "dark": {
        "background": "#202020", "panel": "#2b2b2b", "field": "#1c1c1c", "text": "#ffffff",
        "muted": "#9d9d9d", "accent": "#4cc2ff", "accent_text": "#000000", "hover": "#383838",
        "error": "#ff99a4", "success": "#6ccb5f", "line": "#3d3d3d",
    },
    "light": {
        "background": "#f3f3f3", "panel": "#ffffff", "field": "#fbfbfb", "text": "#1a1a1a",
        "muted": "#5f5f5f", "accent": "#005fb8", "accent_text": "#ffffff", "hover": "#e5e5e5",
        "error": "#c42b1c", "success": "#0f7b0f", "line": "#d4d4d4",
    },
}


class DownloaderApp:
    def __init__(self, root):
        self.root = root
        root.report_callback_exception = self.on_unexpected_error
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.set_icon()

        self.settings = load_settings()
        self.colors = THEMES[self.settings["theme"]]
        ffmpeg = find_tool("ffmpeg")
        self.ffmpeg_folder = Path(ffmpeg).parent if ffmpeg else None
        self.scale = root.winfo_fpixels("1i") / 96
        self.thumbnail_size = tuple(int(side * self.scale) for side in THUMBNAIL_SIZE)

        self.items = {}  # kimlik → {"video", "state", "code", "percent", "speed", "eta", "stage", "target", "image"}
        self.next_id = 0
        self.events = queue.Queue()
        self.info_jobs = queue.Queue()
        self.thumbnail_jobs = queue.Queue()
        self.components_ready = threading.Event()  # yt-dlp güncellenip yüklenmeden bilgi alınmaz
        self.js_runtime = None
        self.running = False
        self.current = None  # (kimlik, Download)
        self.run_done = self.run_failed = 0
        self.last_target = None
        self.closing = False
        self.component_text = ("components_preparing", {})

        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.build_header()
        self.build_link_row()
        self.build_queue()
        self.build_options()
        self.build_footer()
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(2, weight=1)
        self.bind_keys()

        self.apply_theme()
        self.render_texts()
        self.fit_window()
        for worker in (self.prepare_components, self.info_worker, self.thumbnail_worker):
            threading.Thread(target=worker, daemon=True).start()
        self.root.after(POLL_MS, self.poll_events)
        self.root.bind("<FocusIn>", self.paste_from_clipboard)
        self.link_entry.focus_set()
        if not self.ffmpeg_folder:
            self.root.after(300, lambda: messagebox.showerror(self.t("app_name"), self.t("ffmpeg_missing_text")))

    # ---------- Kurulum ----------

    def build_header(self):
        self.header = tk.Frame(self.root, padx=20, pady=12)
        self.header.grid(row=0, column=0, sticky="ew")
        self.title_label = tk.Label(self.header, font=(FONT, 16, "bold"), anchor="w")
        self.title_label.pack(side="left")
        self.about_button = self.small_button(self.header, self.show_about)
        self.language_button = self.small_button(self.header, self.toggle_language)
        self.theme_button = self.small_button(self.header, self.toggle_theme)

    def small_button(self, parent, command, side="right"):
        button = tk.Button(parent, font=(FONT, 10), relief="flat", bd=0, padx=12, pady=5, cursor="hand2",
                           command=command)
        button.pack(side=side, padx=(6, 0))
        return button

    def build_link_row(self):
        self.link_frame = tk.Frame(self.root, padx=20)
        self.link_frame.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.link_frame.grid_columnconfigure(0, weight=1)
        self.link_var = tk.StringVar()
        self.link_entry = tk.Entry(self.link_frame, textvariable=self.link_var, font=(FONT, 12), relief="flat", bd=8)
        self.link_entry.grid(row=0, column=0, sticky="ew")
        self.add_button = tk.Button(self.link_frame, font=(FONT, 10, "bold"), relief="flat", bd=0, padx=22, pady=8,
                                    cursor="hand2", command=self.add_link)
        self.add_button.grid(row=0, column=1, padx=(8, 0), sticky="ns")
        self.link_status = tk.Label(self.link_frame, font=(FONT, 9), anchor="w")
        self.link_status.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        # Boş kutuda soluk ipucu yazısı (Tkinter'da hazır "placeholder" yok)
        self.placeholder = tk.Label(self.link_entry, font=(FONT, 12), anchor="w", cursor="xterm")
        self.placeholder.place(x=4, rely=0.5, anchor="w")
        self.placeholder.bind("<Button-1>", lambda event: self.link_entry.focus_set())
        self.link_var.trace_add("write", lambda *args: self.render_placeholder())

    def build_queue(self):
        self.queue_frame = tk.Frame(self.root, padx=20)
        self.queue_frame.grid(row=2, column=0, sticky="nsew")
        self.queue_frame.grid_columnconfigure(0, weight=1)
        self.queue_frame.grid_rowconfigure(1, weight=1)

        self.toolbar = tk.Frame(self.queue_frame)
        self.toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.remove_button = self.small_button(self.toolbar, self.remove_selected, side="left")
        self.clear_button = self.small_button(self.toolbar, self.clear_queue, side="left")

        self.table = ttk.Treeview(self.queue_frame, columns=("title", "info", "status"), show="tree headings",
                                  selectmode="extended")
        self.table.column("#0", width=self.thumbnail_size[0] + 16, stretch=False)
        self.table.column("title", width=360, anchor="w")
        self.table.column("info", width=200, anchor="w")
        self.table.column("status", width=220, anchor="w")
        self.table.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self.queue_frame, orient="vertical", command=self.table.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.bind("<Double-1>", self.on_double_click)

        # Liste boşken ortada görünen ipucu
        self.hint = tk.Frame(self.queue_frame)
        self.hint_icon = tk.Label(self.hint, text="▶", font=(FONT, 28))
        self.hint_icon.pack()
        self.hint_label = tk.Label(self.hint, font=(FONT, 12, "bold"))
        self.hint_label.pack()
        self.hint_sub = tk.Label(self.hint, font=(FONT, 9), wraplength=int(520 * self.scale))
        self.hint_sub.pack(pady=(4, 0))

    def build_options(self):
        self.options = tk.Frame(self.root, padx=20, pady=12)
        self.options.grid(row=3, column=0, sticky="ew")
        self.options.grid_columnconfigure(3, weight=1)
        self.format_label = tk.Label(self.options, font=(FONT, 10), anchor="w")
        self.format_label.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.format_combo = ttk.Combobox(self.options, state="readonly", font=(FONT, 10), width=24)
        self.format_combo.grid(row=0, column=1, sticky="w", padx=(0, 24))
        self.format_combo.bind("<<ComboboxSelected>>", lambda event: self.on_format_changed())
        self.folder_label = tk.Label(self.options, font=(FONT, 10), anchor="w")
        self.folder_label.grid(row=0, column=2, sticky="w", padx=(0, 8))
        self.folder_value = tk.Label(self.options, font=(FONT, 10), anchor="w")
        self.folder_value.grid(row=0, column=3, sticky="ew")
        self.change_button = tk.Button(self.options, font=(FONT, 10), relief="flat", bd=0, padx=12, pady=5,
                                       cursor="hand2", command=self.choose_folder)
        self.change_button.grid(row=0, column=4, padx=(8, 0))

    def build_footer(self):
        self.footer = tk.Frame(self.root, padx=20, pady=12)
        self.footer.grid(row=4, column=0, sticky="ew")
        self.footer.grid_columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(self.footer, maximum=100)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 14))
        self.summary_label = tk.Label(self.footer, font=(FONT, 10), anchor="e")
        self.summary_label.grid(row=0, column=1, sticky="e", padx=(0, 10))
        self.open_button = tk.Button(self.footer, font=(FONT, 10), relief="flat", bd=0, padx=12, pady=8,
                                     cursor="hand2", command=self.open_last_folder)
        self.open_button.grid(row=0, column=2, padx=(0, 8))
        self.download_button = tk.Button(self.footer, font=(FONT, 11, "bold"), relief="flat", bd=0, padx=26, pady=8,
                                         cursor="hand2", command=self.toggle_downloads)
        self.download_button.grid(row=0, column=3)
        self.component_label = tk.Label(self.footer, font=(FONT, 8), anchor="w")
        self.component_label.grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))

    def bind_keys(self):
        self.link_entry.bind("<Return>", lambda event: self.add_link())
        self.table.bind("<Delete>", lambda event: self.remove_selected())
        self.root.bind("<Control-Return>", lambda event: self.toggle_downloads())

    def set_icon(self):
        try:
            self.root.iconbitmap(default=resource_path("assets/icon.ico"))
        except tk.TclError:
            pass

    def fit_window(self):
        """Pencere boyutu ekran ölçeğine göre ayarlanır: %150 ölçekte yazılar büyür, pencere de büyümeli."""
        self.root.update_idletasks()
        needed_width, needed_height = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        width = min(max(int(1040 * self.scale), needed_width), self.root.winfo_screenwidth() - 40)
        height = min(max(int(660 * self.scale), needed_height), self.root.winfo_screenheight() - 80)
        left = (self.root.winfo_screenwidth() - width) // 2
        top = max(0, (self.root.winfo_screenheight() - height) // 2 - 20)
        self.root.geometry(f"{width}x{height}+{left}+{top}")
        self.root.minsize(min(needed_width, width), min(needed_height, height))

    # ---------- Metinler ve tema ----------

    def t(self, key, **params):
        return translate(self.settings["lang"], key, **params)

    def render_texts(self):
        self.root.title(self.t("app_name"))
        self.title_label.config(text=self.t("app_name"))
        self.theme_button.config(text=("☀  " if self.settings["theme"] == "dark" else "☾  ") + self.t("theme"))
        self.language_button.config(text="🌐  " + self.t("language"))
        self.about_button.config(text="ⓘ  " + self.t("about"))
        self.add_button.config(text=self.t("add"))
        self.placeholder.config(text=self.t("link_placeholder"))
        self.remove_button.config(text=self.t("remove"))
        self.clear_button.config(text=self.t("clear"))
        self.hint_label.config(text=self.t("empty_hint"))
        self.hint_sub.config(text=self.t("empty_hint_sub"))
        for column in ("video", "info", "status"):
            self.table.heading("title" if column == "video" else column, text=self.t(f"col_{column}"))
        self.format_label.config(text=self.t("format"))
        self.folder_label.config(text=self.t("output_folder") + ":")
        self.change_button.config(text=self.t("change"))
        self.open_button.config(text=self.t("open_folder"))
        self.link_status.config(text="")
        self.render_formats()
        self.render_folder()
        self.render_components()
        for item_id in self.items:
            self.render_row(item_id)
        self.render_state()

    def apply_theme(self):
        c = self.colors
        for frame in (self.root, self.header, self.link_frame, self.queue_frame, self.toolbar, self.options,
                      self.footer):
            frame.config(bg=c["background"])
        self.hint.config(bg=c["field"])
        self.hint_label.config(bg=c["field"], fg=c["text"])
        for label in (self.hint_icon, self.hint_sub):
            label.config(bg=c["field"], fg=c["muted"])
        for label in (self.title_label, self.format_label, self.folder_label, self.folder_value):
            label.config(bg=c["background"], fg=c["text"])
        for label in (self.summary_label, self.component_label, self.link_status):
            label.config(bg=c["background"], fg=c["muted"])
        self.link_entry.config(bg=c["field"], fg=c["text"], insertbackground=c["text"], highlightthickness=1,
                               highlightbackground=c["line"], highlightcolor=c["accent"])
        self.placeholder.config(bg=c["field"], fg=c["muted"])
        for button in (self.theme_button, self.language_button, self.about_button):
            button.config(bg=c["background"], fg=c["text"], activebackground=c["hover"], activeforeground=c["text"])
        for button in (self.remove_button, self.clear_button, self.change_button, self.open_button):
            button.config(bg=c["panel"], fg=c["text"], activebackground=c["hover"], activeforeground=c["text"],
                          disabledforeground=c["muted"])
        for button in (self.add_button, self.download_button):
            button.config(bg=c["accent"], fg=c["accent_text"], activebackground=c["accent"],
                          activeforeground=c["accent_text"], disabledforeground=c["accent_text"])

        self.style.configure("TCombobox", fieldbackground=c["field"], background=c["panel"], foreground=c["text"],
                             arrowcolor=c["text"], bordercolor=c["line"], lightcolor=c["field"], darkcolor=c["field"])
        self.style.map("TCombobox",
                       fieldbackground=[("readonly", c["field"]), ("disabled", c["background"])],
                       foreground=[("disabled", c["muted"]), ("readonly", c["text"])],
                       selectbackground=[("readonly", c["field"])], selectforeground=[("readonly", c["text"])])
        self.style.configure("Treeview", background=c["field"], fieldbackground=c["field"], foreground=c["text"],
                             bordercolor=c["line"], lightcolor=c["line"], darkcolor=c["line"],
                             rowheight=self.thumbnail_size[1] + 8, font=(FONT, 10))
        self.style.map("Treeview", background=[("selected", c["hover"])], foreground=[("selected", c["text"])])
        self.style.configure("Treeview.Heading", background=c["panel"], foreground=c["muted"], relief="flat",
                             font=(FONT, 9, "bold"))
        self.style.map("Treeview.Heading", background=[("active", c["hover"])])
        self.style.configure("Vertical.TScrollbar", background=c["hover"], troughcolor=c["field"],
                             bordercolor=c["field"], arrowcolor=c["muted"], lightcolor=c["hover"],
                             darkcolor=c["hover"], gripcount=0)
        self.style.map("Vertical.TScrollbar", background=[("active", c["line"])])
        self.style.configure("Horizontal.TProgressbar", background=c["accent"], troughcolor=c["panel"],
                             bordercolor=c["panel"], lightcolor=c["accent"], darkcolor=c["accent"])
        self.table.tag_configure("error", foreground=c["error"])
        self.table.tag_configure("done", foreground=c["success"])
        self.table.tag_configure("muted", foreground=c["muted"])
        self.root.option_add("*TCombobox*Listbox.background", c["panel"])
        self.root.option_add("*TCombobox*Listbox.foreground", c["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", c["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", c["accent_text"])
        try:
            popdown = self.format_combo.tk.eval(f"ttk::combobox::PopdownWindow {self.format_combo}")
            self.format_combo.tk.call(f"{popdown}.f.l", "configure", "-background", c["panel"], "-foreground",
                                      c["text"], "-selectbackground", c["accent"], "-selectforeground", c["accent_text"])
        except tk.TclError:
            pass

    def toggle_theme(self):
        self.settings["theme"] = "light" if self.settings["theme"] == "dark" else "dark"
        self.colors = THEMES[self.settings["theme"]]
        save_settings(self.settings)
        self.apply_theme()
        self.render_texts()

    def toggle_language(self):
        self.settings["lang"] = "en" if self.settings["lang"] == "tr" else "tr"
        save_settings(self.settings)
        self.render_texts()

    # ---------- Seçenekler ----------

    def format_label_text(self, choice):
        mode, key = choice.split(":")
        if mode == "audio":
            return f"🎵  {self.t('audio')} · {AUDIO_FORMATS[key]}"
        return f"🎬  {self.t('video')} · " + (self.t("best") if key == "best" else key)

    def render_formats(self):
        self.format_combo.config(values=[self.format_label_text(choice) for choice in FORMAT_CHOICES])
        self.format_combo.current(FORMAT_CHOICES.index(self.settings["format"]))

    def on_format_changed(self):
        self.settings["format"] = FORMAT_CHOICES[self.format_combo.current()]
        save_settings(self.settings)

    def output_folder(self):
        return Path(self.settings["output_dir"]) if self.settings["output_dir"] else Path.home() / "Downloads"

    def render_folder(self):
        folder = str(self.output_folder())
        self.folder_value.config(text=folder if len(folder) <= 60 else "…" + folder[-59:])

    def choose_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title=self.t("select_folder"),
                                         initialdir=self.output_folder())
        if folder:
            self.settings["output_dir"] = str(Path(folder))
            save_settings(self.settings)
            self.render_folder()

    # ---------- Link ve kuyruk ----------

    def render_placeholder(self):
        if self.link_var.get():
            self.placeholder.place_forget()
        else:
            self.placeholder.place(x=4, rely=0.5, anchor="w")

    def show_link_status(self, text, error=False):
        self.link_status.config(text=text, fg=self.colors["error"] if error else self.colors["muted"])

    def paste_from_clipboard(self, event):
        """Pencereye dönülünce panoda YouTube linki varsa ve kutu boşsa link kendiliğinden yapıştırılır."""
        if event.widget is not self.root or self.link_var.get():
            return
        try:
            text = self.root.clipboard_get()
            kind, item_id = parse_link(text)
        except (tk.TclError, LinkError):
            return
        if kind == "video" and any(item["video"]["id"] == item_id for item in self.items.values()):
            return
        self.link_var.set(text.strip())
        self.link_entry.select_range(0, "end")

    def add_link(self):
        try:
            kind, item_id = parse_link(self.link_var.get())
        except LinkError as error:
            self.show_link_status(self.t(f"error_{error.code}"), error=True)
            return
        if kind == "video" and any(item["video"]["id"] == item_id for item in self.items.values()):
            self.show_link_status(self.t("already_added"), error=True)
            return
        self.link_var.set("")
        url = canonical_url(kind, item_id)
        if kind == "playlist":
            self.show_link_status(self.t("playlist_reading"))
            self.info_jobs.put((None, url, kind))
        else:
            self.show_link_status("")
            placeholder = self.add_item({"id": item_id, "url": url, "title": url, "channel": None, "duration": None,
                                         "is_live": False}, state="reading")
            self.info_jobs.put((placeholder, url, kind))
        self.render_state()

    def add_item(self, video, state="ready"):
        item_id = str(self.next_id)
        self.next_id += 1
        self.items[item_id] = {"video": video, "state": state, "code": None, "percent": 0, "speed": None,
                               "eta": None, "stage": None, "target": None, "image": None}
        self.table.insert("", "end", iid=item_id, values=("", "", ""))
        self.render_row(item_id)
        self.thumbnail_jobs.put((item_id, video["id"]))
        return item_id

    def render_row(self, item_id):
        item = self.items[item_id]
        video, state = item["video"], item["state"]
        info = " · ".join(part for part in (video["channel"], video["duration"] and format_duration(video["duration"])) if part)
        if state == "downloading":
            status = self.progress_text(item)
        elif state in ("error", "failed"):
            status = self.t(f"error_{item['code']}")
        else:
            status = self.t(f"status_{state}")
        tag = {"error": "error", "failed": "error", "done": "done", "exists": "done", "reading": "muted",
               "cancelled": "muted"}.get(state, "")
        self.table.item(item_id, values=(video["title"], info, status), tags=(tag,))

    def progress_text(self, item):
        if item["stage"] == "processing":
            return self.t("status_processing")
        percent = int(item["percent"])
        if not item["speed"]:
            return self.t("status_downloading", percent=percent)
        speed = format_speed(item["speed"], self.settings["lang"])
        if item["eta"] and item["eta"] >= 1:
            return self.t("status_details_eta", percent=percent, speed=speed, time=format_duration(item["eta"]))
        return self.t("status_details", percent=percent, speed=speed)

    def set_state(self, item_id, state, code=None):
        item = self.items.get(item_id)
        if item is None:
            return
        item["state"], item["code"] = state, code
        self.render_row(item_id)

    def remove_selected(self):
        for item_id in self.table.selection():
            if self.current and self.current[0] == item_id:
                continue  # inen video kaldırılamaz; önce durdurulmalı
            self.table.delete(item_id)
            del self.items[item_id]
        self.render_state()

    def clear_queue(self):
        self.table.selection_set(list(self.items))
        self.remove_selected()

    def on_double_click(self, event):
        item = self.items.get(self.table.identify_row(event.y))
        if item and item["state"] in DONE_STATES:
            self.reveal(item["target"])

    # ---------- Arka plan işleri ----------

    def prepare_components(self):
        """yt-dlp ve Deno güncellenir, sonra yüklenir. İnternet yoksa kurulumdaki sürümle devam edilir."""
        status, last = "ready", [-1]

        def report(received, total):
            percent = int(received / total * 100)
            if percent != last[0]:  # her yüzde değişiminde bir kez; kuyruğu olaya boğmamak için
                last[0] = percent
                self.events.put(("components", "components_downloading", {"percent": percent}))

        try:
            if updater.check_for_updates(on_progress=report):
                status = "updated"
        except Exception:  # bağlantı yok, PyPI'de sorun, bozuk dosya: kurulumla gelen sürümle devam edilir
            status = "offline"
        try:
            self.js_runtime = updater.activate()
            import yt_dlp

            key = {"ready": "components_ready", "updated": "components_updated", "offline": "components_offline"}[status]
            self.events.put(("components", key, {"version": yt_dlp.version.__version__}))
        finally:
            self.components_ready.set()  # ne olursa olsun bekleyen işler serbest kalsın

    def info_worker(self):
        self.components_ready.wait()
        while True:
            placeholder, url, kind = self.info_jobs.get()
            try:
                self.events.put(("info", placeholder, kind, fetch_info(url, kind, self.js_runtime), None))
            except DownloadFailed as error:
                self.events.put(("info", placeholder, kind, None, error.code))
            except Exception:  # beklenmeyen hata işçiyi öldürmesin
                self.events.put(("info", placeholder, kind, None, "failed"))

    def thumbnail_worker(self):
        while True:
            item_id, video_id = self.thumbnail_jobs.get()
            image = fetch_thumbnail(video_id, self.thumbnail_size)
            if image is not None:
                self.events.put(("thumbnail", item_id, image))

    def poll_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                getattr(self, f"on_{event[0]}")(*event[1:])
        except queue.Empty:
            pass
        self.root.after(POLL_MS, self.poll_events)

    def on_components(self, key, params):
        self.component_text = (key, params)
        self.render_components()
        if key != "components_downloading" and self.running and not self.current:
            self.start_next()

    def render_components(self):
        key, params = self.component_text
        self.component_label.config(text=self.t(key, **params))

    def on_info(self, placeholder, kind, videos, code):
        if kind == "video":
            if placeholder not in self.items:
                return  # okunurken listeden kaldırıldı
            if videos is None:
                self.set_state(placeholder, "error", code)
            else:
                self.items[placeholder]["video"] = videos[0]
                self.mark_ready(placeholder)
        elif videos is None:
            self.show_link_status(self.t(f"error_{code}"), error=True)
        else:
            known = {item["video"]["id"] for item in self.items.values()}
            added = 0
            for video in videos:
                if video["id"] not in known and len(self.items) < MAX_QUEUE:
                    known.add(video["id"])
                    self.mark_ready(self.add_item(video))
                    added += 1
            self.show_link_status(self.t("playlist_added", count=added))
        self.render_state()
        if self.running and not self.current:
            self.start_next()

    def mark_ready(self, item_id):
        """Bilgisi gelen video sıraya girer; canlı yayınlar indirilemeyeceği için baştan hatalı gösterilir."""
        if self.items[item_id]["video"]["is_live"]:
            self.set_state(item_id, "error", "live")
        else:
            self.set_state(item_id, "ready")

    def on_thumbnail(self, item_id, image):
        item = self.items.get(item_id)
        if item is None:
            return
        # Resim nesnesi bir yerde tutulmazsa Python onu siler ve tabloda boş görünür
        item["image"] = ImageTk.PhotoImage(image)
        self.table.item(item_id, image=item["image"])

    def on_progress(self, item_id, stage, percent, speed, eta):
        item = self.items.get(item_id)
        if item is None or item["state"] != "downloading":
            return
        # yt-dlp'nin kalan süresi sadece o anki parçanın (görüntü ya da ses); toplam ilerlemeden yeniden hesaplanır
        elapsed = time.monotonic() - item["started"]
        eta = elapsed * (100 - percent) / percent if percent >= 1 and elapsed >= 1 else None
        item.update(stage=stage, percent=percent, speed=speed, eta=eta)
        self.render_row(item_id)
        self.progress.config(value=percent)

    def on_finished(self, item_id, result, path):
        self.current = None
        item = self.items.get(item_id)
        if result in DONE_STATES:
            self.run_done += 1
            self.last_target = path
            if item:
                item["target"] = path
            self.set_state(item_id, result)
        elif result == "cancelled":
            self.set_state(item_id, "cancelled")
        else:
            self.run_failed += 1
            self.set_state(item_id, "failed", result)
        if self.closing:
            self.close_window()
            return
        if self.running:
            self.start_next()
        self.render_state()

    # ---------- İndirme ----------

    def toggle_downloads(self):
        if self.running:
            self.stop()
            return
        if not any(item["state"] in START_STATES for item in self.items.values()):
            return
        retry = [item_id for item_id, item in self.items.items() if item["state"] in RETRY_STATES]
        for item_id in retry:
            self.set_state(item_id, "ready")
        self.running = True
        self.run_done = self.run_failed = 0
        self.start_next()
        self.render_state()

    def start_next(self):
        if self.current or not self.components_ready.is_set():
            return  # önceki indirme kapanıyor ya da bileşenler hazırlanıyor; hazır olunca devam edilir
        ready = [item_id for item_id, item in self.items.items() if item["state"] == "ready"]
        if not ready:
            if not any(item["state"] == "reading" for item in self.items.values()):
                self.running = False
                self.progress.config(value=100 if self.run_done else 0)
                if self.run_done:
                    self.root.bell()
            self.render_state()
            return
        item_id = ready[0]
        folder = self.output_folder()
        if not folder.is_dir():
            self.run_failed += 1
            self.set_state(item_id, "failed", "output_missing")
            self.start_next()
            return
        mode, choice = self.settings["format"].split(":")
        options = download_options(mode, choice, folder, self.ffmpeg_folder)
        if self.js_runtime:
            options["js_runtimes"] = {"deno": {"path": str(self.js_runtime)}}
        item = self.items[item_id]
        item.update(percent=0, speed=None, eta=None, stage=None, started=time.monotonic())
        self.set_state(item_id, "downloading")
        self.progress.config(value=0)
        download = Download(item["video"]["url"], options,
                            lambda *values: self.events.put(("progress", item_id, *values)))
        self.current = (item_id, download)
        threading.Thread(target=self.download_worker, args=(item_id, download), daemon=True).start()
        self.render_state()

    def download_worker(self, item_id, download):
        try:
            result, path = download.run()
        except Exception:  # "bitti" olayı her durumda gelsin; yoksa kuyruk "iniyor"da takılı kalır
            result, path = "failed", None
        self.events.put(("finished", item_id, result, path))

    def stop(self):
        self.running = False
        if self.current:
            self.current[1].cancel()
        self.render_state()

    def render_state(self):
        """Düğmeler, özet yazısı ve boş liste ipucu."""
        has_items = bool(self.items)
        if has_items:
            self.hint.place_forget()
        else:
            self.hint.place(in_=self.table, relx=0.5, rely=0.5, anchor="center")
        can_start = any(item["state"] in START_STATES for item in self.items.values())
        self.download_button.config(text=self.t("cancel") if self.running else self.t("download"),
                                    state="normal" if self.running or can_start else "disabled")
        self.remove_button.config(state="normal" if has_items else "disabled")
        self.clear_button.config(state="normal" if has_items else "disabled")
        self.open_button.config(state="normal" if self.last_target else "disabled")
        self.format_combo.config(state="disabled" if self.running else "readonly")
        self.change_button.config(state="disabled" if self.running else "normal")

        if self.running:
            waiting = sum(item["state"] in ("ready", "reading") for item in self.items.values())
            finished = self.run_done + self.run_failed
            total = finished + waiting + (1 if self.current else 0)
            text = self.t("summary_running", current=min(finished + 1, total), total=total)
        elif self.run_done or self.run_failed:
            parts = [self.t("summary_done", count=self.run_done)] if self.run_done else []
            if self.run_failed:
                parts.append(self.t("summary_failed", count=self.run_failed))
            text = " · ".join(parts)
        elif any(item["state"] == "cancelled" for item in self.items.values()):
            text = self.t("summary_stopped")
        else:
            text = ""
        self.summary_label.config(text=text)

    # ---------- Diğer ----------

    def reveal(self, path):
        """Dosyayı Gezgin'de seçili olarak gösterir; dosya artık yoksa klasörünü açar."""
        if path and Path(path).exists():
            subprocess.Popen(["explorer", "/select,", str(path)])
        elif path and Path(path).parent.is_dir():
            os.startfile(Path(path).parent)

    def open_last_folder(self):
        if self.last_target:
            self.reveal(self.last_target)

    def show_about(self):
        c = self.colors
        window = tk.Toplevel(self.root, bg=c["background"], padx=28, pady=22)
        window.title(self.t("about"))
        window.resizable(False, False)
        window.transient(self.root)
        window.geometry(f"+{self.root.winfo_rootx() + 80}+{self.root.winfo_rooty() + 80}")
        for text, font, color in (
            (self.t("app_name"), (FONT, 16, "bold"), c["text"]),
            (self.t("version", version=VERSION), (FONT, 11), c["text"]),
            (self.t("about_text"), (FONT, 10), c["text"]),
            (self.t("personal_use"), (FONT, 9, "bold"), c["error"]),
            (self.t("credits"), (FONT, 9), c["muted"]),
            ("© 2026 Miraç Deprem", (FONT, 9), c["text"]),
        ):
            tk.Label(window, text=text, font=font, wraplength=int(360 * self.scale), justify="center",
                     bg=c["background"], fg=color).pack(pady=3)
        link = tk.Label(window, text=self.t("view_on_github"), font=(FONT, 10, "underline"), cursor="hand2",
                        bg=c["background"], fg=c["accent"])
        link.pack(pady=(10, 0))
        link.bind("<Button-1>", lambda event: webbrowser.open(REPOSITORY_URL))
        window.bind("<Escape>", lambda event: window.destroy())
        window.grab_set()
        window.focus_set()

    def on_close(self):
        if not self.current:
            self.root.destroy()
            return
        if messagebox.askyesno(self.t("app_name"), self.t("quit_text"), parent=self.root):
            # Önce indirme durdurulur ve yarım dosya silinir; pencere "finished" olayında kapanır
            self.closing = True
            self.stop()
            self.root.after(8000, self.close_window)  # her ihtimale karşı

    def close_window(self):
        try:
            self.root.destroy()
        except tk.TclError:  # zaten kapandı
            pass

    def on_unexpected_error(self, exc_type, exc_value, exc_traceback):
        # Ayrıntı kullanıcıya değil konsola yazılır; kullanıcı sade bir mesaj görür ve uygulama çalışmaya devam eder
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)
        messagebox.showerror(self.t("app_name"), self.t("unexpected_error"), parent=self.root)

import os
import multiprocess
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from overlay import run
from stockfish_bot import StockfishBot
from selenium.common import WebDriverException
import keyboard
from PIL import Image, ImageTk

# Optional OpenCV import for intro video
try:
    import cv2
    CV2_AVAILABLE = True
except ModuleNotFoundError:
    CV2_AVAILABLE = False


class IntroVideo:
    """Plays the intro MP4 video in a separate window before the main app loads."""

    def __init__(self, video_path):
        self.video_path = video_path

    def play(self, on_finished):
        """Play the intro video and call on_finished when done or closed."""
        if not CV2_AVAILABLE:
            on_finished()
            return

        def _play():
            try:
                cap = cv2.VideoCapture(self.video_path)
                if not cap.isOpened():
                    on_finished()
                    return

                fps = cap.get(cv2.CAP_PROP_FPS)
                delay = int(1000 / fps) if fps > 0 else 33
                cv2.namedWindow("Chess_king Intro", cv2.WINDOW_NORMAL)
                cv2.resizeWindow("Chess_king Intro", 640, 360)

                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    cv2.imshow("Chess_king Intro", frame)
                    key = cv2.waitKey(delay) & 0xFF
                    if key == 27 or key == ord('q') or key == ord(' '):  # ESC, q, space to skip
                        break

                cap.release()
                cv2.destroyWindow("Chess_king Intro")
                cv2.waitKey(1)  # Flush the event queue
            except Exception:
                pass
            on_finished()

        thread = threading.Thread(target=_play, daemon=True)
        thread.start()
        return thread


class GUI:
    def __init__(self, master):
        self.master = master

        # Used for closing the threads
        self.exit = False

        # The Selenium Chrome driver
        self.chrome = None

        self.chrome_url = None
        self.chrome_session_id = None

        # Used for the communication between the GUI and the Stockfish Bot process
        self.stockfish_bot_pipe = None
        self.overlay_screen_pipe = None

        # The Stockfish Bot process
        self.stockfish_bot_process = None
        self.overlay_screen_process = None
        self.restart_after_stopping = False

        # Used for storing the match moves
        self.match_moves = []

        # ── Color Palette ──
        self.COLOR_BG = "#1a1a2e"
        self.COLOR_FG = "#e0e0e0"
        self.COLOR_ACCENT = "#e94560"
        self.COLOR_SECONDARY = "#0f3460"
        self.COLOR_TERTIARY = "#16213e"
        self.COLOR_GREEN = "#00ff88"
        self.COLOR_RED = "#ff4466"
        self.COLOR_GOLD = "#ffd700"
        self.COLOR_WHITE = "#ffffff"
        self.COLOR_BLACK = "#000000"
        self.COLOR_BUTTON_BG = "#e94560"
        self.COLOR_BUTTON_FG = "#ffffff"
        self.COLOR_DISABLED = "#555555"
        self.COLOR_TREE_HEADING = "#0f3460"

        # ── Fonts ── (smaller for compactness)
        self.FONT_TITLE = ("Segoe UI", 10, "bold")
        self.FONT_NORMAL = ("Segoe UI", 9)
        self.FONT_BOLD = ("Segoe UI", 9, "bold")
        self.FONT_SMALL = ("Segoe UI", 8)
        self.FONT_MONO = ("Consolas", 9)

        # ── Configure the root window ──
        master.title("Chess_king")
        master.resizable(False, False)
        master.attributes("-topmost", True)
        master.protocol("WM_DELETE_WINDOW", self.on_close_listener)
        master.configure(bg=self.COLOR_BG)

        # ── Load the custom logo ──
        logo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..",
            "Modern Creative Logo Instagram Post.png"
        )
        if os.path.exists(logo_path):
            try:
                logo_img = Image.open(logo_path)
                logo_img = logo_img.resize((32, 32), Image.LANCZOS)
                self.logo_tk = ImageTk.PhotoImage(logo_img)
                master.iconphoto(True, self.logo_tk)
            except Exception:
                fallback_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "assets", "pawn_32x32.png"
                )
                if os.path.exists(fallback_path):
                    master.iconphoto(True, tk.PhotoImage(file=fallback_path))
        else:
            fallback_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "assets", "pawn_32x32.png"
            )
            if os.path.exists(fallback_path):
                master.iconphoto(True, tk.PhotoImage(file=fallback_path))

        # ── Configure ttk style ──
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Treeview",
            background=self.COLOR_TERTIARY,
            foreground=self.COLOR_FG,
            fieldbackground=self.COLOR_TERTIARY,
            font=self.FONT_NORMAL,
            rowheight=24,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=self.COLOR_TREE_HEADING,
            foreground=self.COLOR_GOLD,
            font=self.FONT_BOLD,
            borderwidth=0,
        )
        style.map(
            "Treeview",
            background=[("selected", self.COLOR_ACCENT)],
            foreground=[("selected", self.COLOR_WHITE)],
        )
        style.map(
            "Treeview.Heading",
            background=[("active", self.COLOR_SECONDARY)],
        )
        style.configure(
            "TSeparator", background=self.COLOR_ACCENT,
        )
        style.configure(
            "Vertical.TScrollbar",
            background=self.COLOR_SECONDARY,
            troughcolor=self.COLOR_BG,
            bordercolor=self.COLOR_BG,
            arrowcolor=self.COLOR_GOLD,
        )

        # ── Header Bar ──
        header_frame = tk.Frame(master, bg=self.COLOR_SECONDARY, height=32)
        header_frame.pack(fill=tk.X, side=tk.TOP)
        header_frame.pack_propagate(False)

        header_label = tk.Label(
            header_frame,
            text="♚ Chess_king Bot ♚",
            font=("Segoe UI", 12, "bold"),
            bg=self.COLOR_SECONDARY,
            fg=self.COLOR_GOLD,
        )
        header_label.pack(expand=True)

        sub_header = tk.Label(
            master,
            text="Chess.com  •  Lichess.org",
            font=self.FONT_SMALL,
            bg=self.COLOR_BG,
            fg=self.COLOR_ACCENT,
        )
        sub_header.pack(fill=tk.X, pady=(1, 3))

        # ── Main Content Container ──
        main_container = tk.Frame(master, bg=self.COLOR_BG)
        main_container.pack(fill=tk.BOTH, expand=True)

        # ─── LEFT FRAME (scrollable) ───
        left_canvas_bg = self.COLOR_TERTIARY
        left_container = tk.Frame(
            main_container,
            bg=self.COLOR_TERTIARY,
            highlightbackground=self.COLOR_SECONDARY,
            highlightthickness=1,
        )
        left_container.grid(row=0, column=0, padx=4, pady=4, sticky=tk.NW)
        left_container.grid_rowconfigure(0, weight=1)
        left_container.grid_columnconfigure(0, weight=1)

        left_canvas = tk.Canvas(
            left_container,
            bg=self.COLOR_TERTIARY,
            highlightthickness=0,
            width=235,
            height=490,
        )
        left_canvas.grid(row=0, column=0, sticky=tk.NSEW)

        left_scrollbar = ttk.Scrollbar(
            left_container,
            orient="vertical",
            command=left_canvas.yview,
        )
        left_scrollbar.grid(row=0, column=1, sticky=tk.NS)

        left_frame = tk.Frame(left_canvas, bg=self.COLOR_TERTIARY)

        left_frame.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all")),
        )

        left_canvas.create_window((0, 0), window=left_frame, anchor=tk.NW, width=230)
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        # Bind mouse wheel to the canvas
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # --- Status ---
        status_label = tk.Frame(left_frame, bg=self.COLOR_TERTIARY)
        tk.Label(
            status_label,
            text="● Status:",
            font=self.FONT_BOLD,
            bg=self.COLOR_TERTIARY,
            fg=self.COLOR_FG,
        ).pack(side=tk.LEFT)
        self.status_text = tk.Label(
            status_label,
            text="Inactive",
            font=self.FONT_BOLD,
            bg=self.COLOR_TERTIARY,
            fg=self.COLOR_RED,
        )
        self.status_text.pack(side=tk.LEFT, padx=(4, 0))
        status_label.pack(anchor=tk.NW, padx=6, pady=(6, 1))

        tk.Frame(left_frame, bg=self.COLOR_ACCENT, height=1).pack(fill=tk.X, padx=6, pady=1)

        # --- Evaluation info ---
        self.eval_frame = tk.Frame(left_frame, bg=self.COLOR_TERTIARY)
        eval_data = [
            ("Eval:", "eval_text", self.COLOR_GOLD),
            ("WDL:", "wdl_text", self.COLOR_FG),
            ("Material:", "material_text", self.COLOR_GOLD),
            ("Bot Acc:", "white_acc_text", self.COLOR_GREEN),
            ("Opponent Acc:", "black_acc_text", self.COLOR_RED),
        ]
        for label_text, attr, color in eval_data:
            row = tk.Frame(self.eval_frame, bg=self.COLOR_TERTIARY)
            tk.Label(
                row,
                text=label_text,
                font=self.FONT_SMALL,
                bg=self.COLOR_TERTIARY,
                fg=color,
                width=11,
                anchor=tk.W,
            ).pack(side=tk.LEFT)
            lbl = tk.Label(
                row,
                text="-",
                font=self.FONT_MONO,
                bg=self.COLOR_TERTIARY,
                fg=self.COLOR_FG,
                width=9,
                anchor=tk.W,
            )
            lbl.pack(side=tk.LEFT)
            setattr(self, attr, lbl)
            row.pack(anchor=tk.NW, padx=6, pady=0)
        self.eval_frame.pack(anchor=tk.NW, fill=tk.X, pady=(1, 3))

        tk.Frame(left_frame, bg=self.COLOR_ACCENT, height=1).pack(fill=tk.X, padx=6, pady=1)

        # --- Platform ---
        tk.Label(
            left_frame,
            text="Platform:",
            font=self.FONT_BOLD,
            bg=self.COLOR_TERTIARY,
            fg=self.COLOR_GOLD,
        ).pack(anchor=tk.NW, padx=6, pady=(3, 0))

        self.website = tk.StringVar(value="chesscom")
        radio_frame = tk.Frame(left_frame, bg=self.COLOR_TERTIARY)
        self.chesscom_radio_button = tk.Radiobutton(
            radio_frame,
            text="Chess.com",
            variable=self.website,
            value="chesscom",
            font=self.FONT_SMALL,
            bg=self.COLOR_TERTIARY,
            fg=self.COLOR_FG,
            selectcolor=self.COLOR_SECONDARY,
            activebackground=self.COLOR_TERTIARY,
            activeforeground=self.COLOR_GOLD,
        )
        self.chesscom_radio_button.pack(side=tk.LEFT, padx=(0, 6))
        self.lichess_radio_button = tk.Radiobutton(
            radio_frame,
            text="Lichess.org",
            variable=self.website,
            value="lichess",
            font=self.FONT_SMALL,
            bg=self.COLOR_TERTIARY,
            fg=self.COLOR_FG,
            selectcolor=self.COLOR_SECONDARY,
            activebackground=self.COLOR_TERTIARY,
            activeforeground=self.COLOR_GOLD,
        )
        self.lichess_radio_button.pack(side=tk.LEFT)
        radio_frame.pack(anchor=tk.NW, padx=6, pady=1)

        tk.Frame(left_frame, bg=self.COLOR_ACCENT, height=1).pack(fill=tk.X, padx=6, pady=1)

        # --- Buttons ---
        button_frame = tk.Frame(left_frame, bg=self.COLOR_TERTIARY)
        self.opening_browser = False
        self.opened_browser = False
        self.open_browser_button = self._create_styled_button(
            button_frame, text="🌐 Open Browser",
            command=self.on_open_browser_button_listener,
            font_size=8,
        )
        self.open_browser_button.pack(side=tk.LEFT, padx=2)

        self.running = False
        self.start_button = self._create_styled_button(
            button_frame, text="▶ Start",
            command=self.on_start_button_listener,
            state="disabled",
            font_size=8,
        )
        self.start_button.pack(side=tk.LEFT, padx=2)
        button_frame.pack(anchor=tk.NW, padx=6, pady=3)

        tk.Frame(left_frame, bg=self.COLOR_ACCENT, height=1).pack(fill=tk.X, padx=6, pady=1)

        # --- Mode checkboxes ---
        mode_frame = tk.Frame(left_frame, bg=self.COLOR_TERTIARY)
        self.enable_manual_mode = tk.BooleanVar(value=False)
        self.manual_mode_checkbox = tk.Checkbutton(
            mode_frame, text="Manual Mode",
            variable=self.enable_manual_mode,
            command=self.on_manual_mode_checkbox_listener,
            font=self.FONT_SMALL, bg=self.COLOR_TERTIARY, fg=self.COLOR_FG,
            selectcolor=self.COLOR_SECONDARY,
            activebackground=self.COLOR_TERTIARY, activeforeground=self.COLOR_GOLD,
        )
        self.manual_mode_checkbox.pack(anchor=tk.NW)

        self.manual_mode_frame = tk.Frame(mode_frame, bg=self.COLOR_TERTIARY)
        self.manual_mode_label = tk.Label(
            self.manual_mode_frame,
            text="\u2022 Press 3 to make a move",
            font=self.FONT_SMALL, bg=self.COLOR_TERTIARY, fg=self.COLOR_GREEN,
        )
        self.manual_mode_label.pack(anchor=tk.NW)

        self.enable_mouseless_mode = tk.BooleanVar(value=False)
        self.mouseless_mode_checkbox = tk.Checkbutton(
            mode_frame, text="Mouseless Mode",
            variable=self.enable_mouseless_mode,
            font=self.FONT_SMALL, bg=self.COLOR_TERTIARY, fg=self.COLOR_FG,
            selectcolor=self.COLOR_SECONDARY,
            activebackground=self.COLOR_TERTIARY, activeforeground=self.COLOR_GOLD,
        )
        self.mouseless_mode_checkbox.pack(anchor=tk.NW)

        self.enable_non_stop_puzzles = tk.IntVar(value=0)
        self.non_stop_puzzles_check_button = tk.Checkbutton(
            mode_frame, text="Non-stop puzzles",
            variable=self.enable_non_stop_puzzles,
            font=self.FONT_SMALL, bg=self.COLOR_TERTIARY, fg=self.COLOR_FG,
            selectcolor=self.COLOR_SECONDARY,
            activebackground=self.COLOR_TERTIARY, activeforeground=self.COLOR_GOLD,
        )
        self.non_stop_puzzles_check_button.pack(anchor=tk.NW)

        self.enable_non_stop_matches = tk.IntVar(value=0)
        self.non_stop_matches_check_button = tk.Checkbutton(
            mode_frame, text="Non-stop online matches",
            variable=self.enable_non_stop_matches,
            font=self.FONT_SMALL, bg=self.COLOR_TERTIARY, fg=self.COLOR_FG,
            selectcolor=self.COLOR_SECONDARY,
            activebackground=self.COLOR_TERTIARY, activeforeground=self.COLOR_GOLD,
        )
        self.non_stop_matches_check_button.pack(anchor=tk.NW)

        self.enable_bongcloud = tk.IntVar()
        self.bongcloud_check_button = tk.Checkbutton(
            mode_frame, text="Bongcloud ☁️",
            variable=self.enable_bongcloud,
            font=self.FONT_SMALL, bg=self.COLOR_TERTIARY, fg=self.COLOR_GOLD,
            selectcolor=self.COLOR_SECONDARY,
            activebackground=self.COLOR_TERTIARY, activeforeground=self.COLOR_GOLD,
        )
        self.bongcloud_check_button.pack(anchor=tk.NW)
        mode_frame.pack(anchor=tk.NW, padx=6, pady=3)

        tk.Frame(left_frame, bg=self.COLOR_ACCENT, height=1).pack(fill=tk.X, padx=6)

        # --- Mouse Latency ---
        mouse_latency_frame = tk.Frame(left_frame, bg=self.COLOR_TERTIARY)
        tk.Label(
            mouse_latency_frame, text="🐭 Mouse Latency (sec)",
            font=self.FONT_SMALL, bg=self.COLOR_TERTIARY, fg=self.COLOR_FG,
        ).pack(pady=(5, 0))
        self.mouse_latency = tk.DoubleVar(value=0.0)
        self.mouse_latency_scale = tk.Scale(
            mouse_latency_frame, from_=0.0, to=15, resolution=0.2,
            orient=tk.HORIZONTAL, variable=self.mouse_latency,
            bg=self.COLOR_TERTIARY, fg=self.COLOR_GOLD,
            troughcolor=self.COLOR_SECONDARY, activebackground=self.COLOR_ACCENT,
            font=self.FONT_SMALL, length=180,
        )
        self.mouse_latency_scale.pack(fill=tk.X, padx=4)
        mouse_latency_frame.pack(anchor=tk.NW, fill=tk.X, padx=6, pady=3)

        tk.Frame(left_frame, bg=self.COLOR_ACCENT, height=1).pack(fill=tk.X, padx=6)

        # --- Stockfish Parameters ---
        tk.Label(
            left_frame, text="⚙ Stockfish Parameters",
            font=self.FONT_BOLD, bg=self.COLOR_TERTIARY, fg=self.COLOR_GOLD,
        ).pack(anchor=tk.NW, padx=6, pady=(3, 1))

        # Slow Mover
        slow_mover_frame = tk.Frame(left_frame, bg=self.COLOR_TERTIARY)
        tk.Label(
            slow_mover_frame, text="Slow Mover", font=self.FONT_SMALL,
            bg=self.COLOR_TERTIARY, fg=self.COLOR_FG,
        ).pack(side=tk.LEFT)
        self.slow_mover = tk.IntVar(value=100)
        self.slow_mover_entry = tk.Entry(
            slow_mover_frame, textvariable=self.slow_mover,
            justify="center", width=6, font=self.FONT_MONO,
            bg=self.COLOR_SECONDARY, fg=self.COLOR_GOLD,
            insertbackground=self.COLOR_GOLD, relief=tk.FLAT, bd=2,
        )
        self.slow_mover_entry.pack(side=tk.LEFT, padx=(4, 0))
        slow_mover_frame.pack(anchor=tk.NW, padx=6, pady=1)

        # Skill Level
        skill_level_frame = tk.Frame(left_frame, bg=self.COLOR_TERTIARY)
        tk.Label(
            skill_level_frame, text="Skill Level", font=self.FONT_SMALL,
            bg=self.COLOR_TERTIARY, fg=self.COLOR_FG,
        ).pack(pady=(5, 0))
        self.skill_level = tk.IntVar(value=20)
        self.skill_level_scale = tk.Scale(
            skill_level_frame, from_=0, to=20, orient=tk.HORIZONTAL,
            variable=self.skill_level, bg=self.COLOR_TERTIARY, fg=self.COLOR_GOLD,
            troughcolor=self.COLOR_SECONDARY, activebackground=self.COLOR_ACCENT,
            font=self.FONT_SMALL, length=180,
        )
        self.skill_level_scale.pack(fill=tk.X, padx=4)
        skill_level_frame.pack(anchor=tk.NW, fill=tk.X, padx=6)

        # Depth
        depth_frame = tk.Frame(left_frame, bg=self.COLOR_TERTIARY)
        tk.Label(
            depth_frame, text="Depth", font=self.FONT_SMALL,
            bg=self.COLOR_TERTIARY, fg=self.COLOR_FG,
        ).pack(pady=(5, 0))
        self.stockfish_depth = tk.IntVar(value=15)
        self.stockfish_depth_scale = tk.Scale(
            depth_frame, from_=1, to=20, orient=tk.HORIZONTAL,
            variable=self.stockfish_depth,
            bg=self.COLOR_TERTIARY, fg=self.COLOR_GOLD,
            troughcolor=self.COLOR_SECONDARY, activebackground=self.COLOR_ACCENT,
            font=self.FONT_SMALL, length=180,
        )
        self.stockfish_depth_scale.pack(fill=tk.X, padx=4)
        depth_frame.pack(anchor=tk.NW, fill=tk.X, padx=6)

        # Memory
        memory_frame = tk.Frame(left_frame, bg=self.COLOR_TERTIARY)
        tk.Label(
            memory_frame, text="Memory", font=self.FONT_SMALL,
            bg=self.COLOR_TERTIARY, fg=self.COLOR_FG,
        ).pack(side=tk.LEFT)
        self.memory = tk.IntVar(value=512)
        self.memory_entry = tk.Entry(
            memory_frame, textvariable=self.memory,
            justify="center", width=7, font=self.FONT_MONO,
            bg=self.COLOR_SECONDARY, fg=self.COLOR_GOLD,
            insertbackground=self.COLOR_GOLD, relief=tk.FLAT, bd=2,
        )
        self.memory_entry.pack(side=tk.LEFT, padx=(4, 0))
        tk.Label(
            memory_frame, text="MB", font=self.FONT_SMALL,
            bg=self.COLOR_TERTIARY, fg=self.COLOR_FG,
        ).pack(side=tk.LEFT)
        memory_frame.pack(anchor=tk.NW, padx=6, pady=1)

        # CPU Threads
        cpu_threads_frame = tk.Frame(left_frame, bg=self.COLOR_TERTIARY)
        tk.Label(
            cpu_threads_frame, text="CPU Threads", font=self.FONT_SMALL,
            bg=self.COLOR_TERTIARY, fg=self.COLOR_FG,
        ).pack(side=tk.LEFT)
        self.cpu_threads = tk.IntVar(value=1)
        self.cpu_threads_entry = tk.Entry(
            cpu_threads_frame, textvariable=self.cpu_threads,
            justify="center", width=5, font=self.FONT_MONO,
            bg=self.COLOR_SECONDARY, fg=self.COLOR_GOLD,
            insertbackground=self.COLOR_GOLD, relief=tk.FLAT, bd=2,
        )
        self.cpu_threads_entry.pack(side=tk.LEFT, padx=(4, 0))
        cpu_threads_frame.pack(anchor=tk.NW, padx=6, pady=1)

        tk.Frame(left_frame, bg=self.COLOR_ACCENT, height=1).pack(fill=tk.X, padx=6, pady=3)

        # --- Misc ---
        tk.Label(
            left_frame, text="🔧 Misc",
            font=self.FONT_BOLD, bg=self.COLOR_TERTIARY, fg=self.COLOR_GOLD,
        ).pack(anchor=tk.NW, padx=6)

        self.enable_topmost = tk.IntVar(value=1)
        self.topmost_check_button = tk.Checkbutton(
            left_frame, text="Window stays on top",
            variable=self.enable_topmost, onvalue=1, offvalue=0,
            command=self.on_topmost_check_button_listener,
            font=self.FONT_SMALL, bg=self.COLOR_TERTIARY, fg=self.COLOR_FG,
            selectcolor=self.COLOR_SECONDARY,
            activebackground=self.COLOR_TERTIARY, activeforeground=self.COLOR_GOLD,
        )
        self.topmost_check_button.pack(anchor=tk.NW, padx=6)

        # Stockfish path
        self.stockfish_path = self.auto_detect_stockfish()
        detected_text = self.stockfish_path if self.stockfish_path else ""

        sf_btn_frame = tk.Frame(left_frame, bg=self.COLOR_TERTIARY)
        self.select_stockfish_button = self._create_styled_button(
            sf_btn_frame, text="📁 Select Stockfish",
            command=self.on_select_stockfish_button_listener,
            font_size=8,
        )
        self.select_stockfish_button.pack(side=tk.LEFT, padx=2)
        sf_btn_frame.pack(anchor=tk.NW, padx=6, pady=(3, 1))

        self.stockfish_path_text = tk.Label(
            left_frame, text=detected_text, wraplength=210,
            font=self.FONT_SMALL, bg=self.COLOR_TERTIARY,
            fg=self.COLOR_GREEN if detected_text else self.COLOR_RED,
        )
        self.stockfish_path_text.pack(anchor=tk.NW, padx=6, pady=(0, 4))

        left_container.grid(row=0, column=0, padx=4, pady=4, sticky=tk.NW)

        # ─── RIGHT FRAME ───
        right_frame = tk.Frame(
            main_container,
            bg=self.COLOR_TERTIARY,
            highlightbackground=self.COLOR_SECONDARY,
            highlightthickness=1,
        )

        tk.Label(
            right_frame, text="📋 Move Log",
            font=self.FONT_BOLD, bg=self.COLOR_TERTIARY, fg=self.COLOR_GOLD,
        ).pack(anchor=tk.NW, padx=6, pady=(4, 1))

        treeview_frame = tk.Frame(right_frame, bg=self.COLOR_TERTIARY)
        self.tree = ttk.Treeview(
            treeview_frame, column=("#", "White", "Black"),
            show="headings", height=23, selectmode="browse",
        )
        self.tree.pack(anchor=tk.NW, side=tk.LEFT)

        self.vsb = ttk.Scrollbar(
            treeview_frame, orient="vertical", command=self.tree.yview,
        )
        self.vsb.pack(fill=tk.Y, expand=True)
        self.tree.configure(yscrollcommand=self.vsb.set)

        self.tree.column("# 1", anchor=tk.CENTER, width=35)
        self.tree.heading("# 1", text="#")
        self.tree.column("# 2", anchor=tk.CENTER, width=60)
        self.tree.heading("# 2", text="White")
        self.tree.column("# 3", anchor=tk.CENTER, width=60)
        self.tree.heading("# 3", text="Black")

        treeview_frame.pack(anchor=tk.NW, padx=6, pady=(0, 3))

        self.export_pgn_button = self._create_styled_button(
            right_frame, text="💾 Export PGN",
            command=self.on_export_pgn_button_listener,
            font_size=8,
        )
        self.export_pgn_button.pack(anchor=tk.NW, fill=tk.X, padx=6, pady=(0, 6))

        right_frame.grid(row=0, column=1, padx=(0, 4), pady=4, sticky=tk.NW)

        # Footer
        footer_label = tk.Label(
            master,
            text="Created by Bijoy  •  Press 1=Start  2=Stop",
            font=("Segoe UI", 7),
            bg=self.COLOR_BG,
            fg=self.COLOR_DISABLED,
        )
        footer_label.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 1))

        # ── Start threads ──
        process_checker_thread = threading.Thread(target=self.process_checker_thread)
        process_checker_thread.start()

        browser_checker_thread = threading.Thread(target=self.browser_checker_thread)
        browser_checker_thread.start()

        process_communicator_thread = threading.Thread(
            target=self.process_communicator_thread
        )
        process_communicator_thread.start()

        keyboard_listener_thread = threading.Thread(
            target=self.keypress_listener_thread
        )
        keyboard_listener_thread.start()

    def _create_styled_button(self, parent, text, command, state="normal", font_size=9):
        btn = tk.Button(
            parent, text=text, command=command, state=state,
            font=("Segoe UI", font_size, "bold"),
            bg=self.COLOR_BUTTON_BG, fg=self.COLOR_BUTTON_FG,
            activebackground=self.COLOR_ACCENT, activeforeground=self.COLOR_WHITE,
            disabledforeground=self.COLOR_DISABLED,
            relief=tk.FLAT, bd=0, padx=8, pady=3,
            cursor="hand2",
        )
        btn.bind("<Enter>", lambda e, b=btn: self._on_button_hover(b, True))
        btn.bind("<Leave>", lambda e, b=btn: self._on_button_hover(b, False))
        return btn

    def _on_button_hover(self, button, is_hover):
        if button["state"] != "disabled":
            if is_hover:
                button["bg"] = self.COLOR_GOLD
                button["fg"] = self.COLOR_BLACK
            else:
                button["bg"] = self.COLOR_BUTTON_BG
                button["fg"] = self.COLOR_BUTTON_FG

    def on_close_listener(self):
        self.exit = True
        self.master.destroy()

    def process_checker_thread(self):
        while not self.exit:
            if (
                self.running
                and self.stockfish_bot_process is not None
                and not self.stockfish_bot_process.is_alive()
            ):
                self.on_stop_button_listener()
                if self.restart_after_stopping:
                    self.restart_after_stopping = False
                    self.on_start_button_listener()
            time.sleep(0.1)

    def browser_checker_thread(self):
        while not self.exit:
            try:
                if (
                    self.opened_browser
                    and self.chrome is not None
                    and "target window already closed"
                    in self.chrome.get_log("driver")[-1]["message"]
                ):
                    self.opened_browser = False
                    self.open_browser_button["text"] = "🌐 Open Browser"
                    self.open_browser_button["state"] = "normal"
                    self.open_browser_button.update()
                    self.on_stop_button_listener()
                    self.chrome = None
            except IndexError:
                pass
            time.sleep(0.1)

    def process_communicator_thread(self):
        while not self.exit:
            try:
                if (
                    self.stockfish_bot_pipe is not None
                    and self.stockfish_bot_pipe.poll()
                ):
                    data = self.stockfish_bot_pipe.recv()
                    if data == "START":
                        self.clear_tree()
                        self.match_moves = []
                        self.status_text["text"] = "● Running"
                        self.status_text["fg"] = self.COLOR_GREEN
                        self.status_text.update()
                        self.start_button["text"] = "⏹ Stop"
                        self.start_button["state"] = "normal"
                        self.start_button["command"] = self.on_stop_button_listener
                        self.start_button.update()
                    elif data[:7] == "RESTART":
                        self.restart_after_stopping = True
                        self.stockfish_bot_pipe.send("DELETE")
                    elif data[:6] == "S_MOVE":
                        move = data[6:]
                        self.match_moves.append(move)
                        self.insert_move(move)
                        self.tree.yview_moveto(1)
                    elif data[:6] == "M_MOVE":
                        moves = data[6:].split(",")
                        self.match_moves += moves
                        self.set_moves(moves)
                        self.tree.yview_moveto(1)
                    elif data[:5] == "EVAL|":
                        parts = data.split("|")
                        if len(parts) >= 5:
                            eval_str, wdl_str, material_str, bot_accuracy_str, opponent_accuracy_str = parts[1:]
                            self.update_evaluation_display(eval_str, wdl_str, material_str, bot_accuracy_str, opponent_accuracy_str)
                    elif data[:7] == "ERR_EXE":
                        tk.messagebox.showerror("Error", "Stockfish path provided is not valid!")
                    elif data[:8] == "ERR_PERM":
                        tk.messagebox.showerror("Error", "Stockfish path provided is not executable!")
                    elif data[:9] == "ERR_BOARD":
                        tk.messagebox.showerror("Error", "Cant find board!")
                    elif data[:9] == "ERR_COLOR":
                        tk.messagebox.showerror("Error", "Cant find player color!")
                    elif data[:9] == "ERR_MOVES":
                        tk.messagebox.showerror("Error", "Cant find moves list!")
                    elif data[:12] == "ERR_GAMEOVER":
                        tk.messagebox.showerror("Error", "Game has already finished!")
            except (BrokenPipeError, OSError):
                self.stockfish_bot_pipe = None
            time.sleep(0.1)

    def keypress_listener_thread(self):
        while not self.exit:
            time.sleep(0.1)
            if not self.opened_browser:
                continue
            if keyboard.is_pressed("1") and not self.running:
                self.on_start_button_listener()
            elif keyboard.is_pressed("2"):
                self.on_stop_button_listener()

    def on_open_browser_button_listener(self):
        self.opening_browser = True
        self.open_browser_button["text"] = "⏳ Opening Browser..."
        self.open_browser_button["state"] = "disabled"
        self.open_browser_button.update()

        options = webdriver.ChromeOptions()
        options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('useAutomationExtension', False)
        try:
            chrome_install = ChromeDriverManager().install()
            folder = os.path.dirname(chrome_install)
            chromedriver_path = os.path.join(folder, "chromedriver.exe")
            service = ChromeService(chromedriver_path)
            self.chrome = webdriver.Chrome(service=service, options=options)
        except WebDriverException:
            self.opening_browser = False
            self.open_browser_button["text"] = "🌐 Open Browser"
            self.open_browser_button["state"] = "normal"
            self.open_browser_button.update()
            tk.messagebox.showerror("Error", "Cant find Chrome. You need to have Chrome installed for this to work.")
            return
        except Exception as e:
            self.opening_browser = False
            self.open_browser_button["text"] = "🌐 Open Browser"
            self.open_browser_button["state"] = "normal"
            self.open_browser_button.update()
            tk.messagebox.showerror("Error", f"An error occurred while opening the browser: {e}")
            return

        if self.website.get() == "chesscom":
            self.chrome.get("https://www.chess.com")
        else:
            self.chrome.get("https://www.lichess.org")

        self.chrome_url = self.chrome.service.service_url
        self.chrome_session_id = self.chrome.session_id

        self.opening_browser = False
        self.opened_browser = True
        self.open_browser_button["text"] = "✅ Browser is open"
        self.open_browser_button["state"] = "disabled"
        self.open_browser_button.update()
        self.start_button["state"] = "normal"
        self.start_button.update()

    def on_start_button_listener(self):
        if self.running:
            return

        slow_mover = self.slow_mover.get()
        if slow_mover < 10 or slow_mover > 1000:
            tk.messagebox.showerror("Error", "Slow Mover must be between 10 and 1000")
            return
        if self.stockfish_path == "":
            tk.messagebox.showerror("Error", "Stockfish path is empty")
            return
        if self.enable_mouseless_mode.get() == 1 and self.website.get() == "chesscom":
            tk.messagebox.showerror("Error", "Mouseless mode is only supported on lichess.org")
            return

        parent_conn, child_conn = multiprocess.Pipe()
        self.stockfish_bot_pipe = parent_conn
        st_ov_queue = multiprocess.Queue()

        self.stockfish_bot_process = StockfishBot(
            self.chrome_url, self.chrome_session_id, self.website.get(),
            child_conn, st_ov_queue, self.stockfish_path,
            self.enable_manual_mode.get() == 1, self.enable_mouseless_mode.get() == 1,
            self.enable_non_stop_puzzles.get() == 1, self.enable_non_stop_matches.get() == 1,
            self.mouse_latency.get(), self.enable_bongcloud.get() == 1,
            self.slow_mover.get(), self.skill_level.get(), self.stockfish_depth.get(),
            self.memory.get(), self.cpu_threads.get(),
        )
        self.stockfish_bot_process.start()

        self.overlay_screen_process = multiprocess.Process(target=run, args=(st_ov_queue,))
        self.overlay_screen_process.start()

        self.running = True
        self.start_button["text"] = "⏳ Starting..."
        self.start_button["state"] = "disabled"
        self.start_button.update()

    def on_stop_button_listener(self):
        if self.stockfish_bot_process is not None:
            if self.overlay_screen_process is not None:
                self.overlay_screen_process.kill()
                self.overlay_screen_process = None
            if self.stockfish_bot_process.is_alive():
                self.stockfish_bot_process.kill()
            self.stockfish_bot_process = None
        if self.stockfish_bot_pipe is not None:
            self.stockfish_bot_pipe.close()
            self.stockfish_bot_pipe = None

        self.running = False
        self.status_text["text"] = "● Inactive"
        self.status_text["fg"] = self.COLOR_RED
        self.status_text.update()

        self.eval_text["text"] = "-"
        self.eval_text["fg"] = self.COLOR_FG
        self.wdl_text["text"] = "-"
        self.material_text["text"] = "-"
        self.material_text["fg"] = self.COLOR_FG
        self.white_acc_text["text"] = "-"
        self.black_acc_text["text"] = "-"
        self.eval_text.update()
        self.wdl_text.update()
        self.material_text.update()
        self.white_acc_text.update()
        self.black_acc_text.update()

        if not self.restart_after_stopping:
            self.start_button["text"] = "▶ Start"
            self.start_button["state"] = "normal"
            self.start_button["command"] = self.on_start_button_listener
        else:
            self.restart_after_stopping = False
            self.on_start_button_listener()
        self.start_button.update()

    def on_topmost_check_button_listener(self):
        if self.enable_topmost.get() == 1:
            self.master.attributes("-topmost", True)
        else:
            self.master.attributes("-topmost", False)

    def on_export_pgn_button_listener(self):
        f = filedialog.asksaveasfile(
            initialfile="match.pgn", defaultextension=".pgn",
            filetypes=[("Portable Game Notation", "*.pgn"), ("All Files", "*.*")],
        )
        if f is None:
            return
        data = ""
        for i in range(len(self.match_moves) // 2 + 1):
            if len(self.match_moves) % 2 == 0 and i == len(self.match_moves) // 2:
                continue
            data += str(i + 1) + ". "
            data += self.match_moves[i * 2] + " "
            if (i * 2) + 1 < len(self.match_moves):
                data += self.match_moves[i * 2 + 1] + " "
        f.write(data)
        f.close()

    @staticmethod
    def auto_detect_stockfish():
        import pathlib
        desktop = pathlib.Path.home() / "Desktop"
        stockfish_dir = desktop / "stockfish"
        if stockfish_dir.is_dir():
            for exe in stockfish_dir.glob("stockfish*.exe"):
                return str(exe.resolve())
        for exe in desktop.glob("stockfish*.exe"):
            return str(exe.resolve())
        return ""

    def on_select_stockfish_button_listener(self):
        f = filedialog.askopenfilename()
        if f is None:
            return
        self.stockfish_path = f
        self.stockfish_path_text["text"] = self.stockfish_path
        self.stockfish_path_text["fg"] = self.COLOR_GREEN
        self.stockfish_path_text.update()

    def clear_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.tree.update()

    def insert_move(self, move):
        cells_num = sum(
            [len(self.tree.item(i)["values"]) - 1 for i in self.tree.get_children()]
        )
        if (cells_num % 2) == 0:
            rows_num = len(self.tree.get_children())
            self.tree.insert("", "end", text="1", values=(rows_num + 1, move))
        else:
            self.tree.set(self.tree.get_children()[-1], column=2, value=move)
        self.tree.update()

    def set_moves(self, moves):
        self.clear_tree()
        pairs = list(zip(*[iter(moves)] * 2))
        for i, pair in enumerate(pairs):
            self.tree.insert("", "end", text="1", values=(str(i + 1), pair[0], pair[1]))
        if len(moves) % 2 == 1:
            self.tree.insert("", "end", text="1", values=(len(pairs) + 1, moves[-1]))
        self.tree.update()

    def on_manual_mode_checkbox_listener(self):
        if self.enable_manual_mode.get() == 1:
            self.manual_mode_frame.pack(after=self.manual_mode_checkbox)
            self.manual_mode_frame.update()
        else:
            self.manual_mode_frame.pack_forget()
            self.manual_mode_checkbox.update()

    def update_evaluation_display(self, eval_str, wdl_str, material_str, bot_acc, opponent_acc):
        self.eval_text["text"] = eval_str
        try:
            if eval_str.startswith("M"):
                mate_value = int(eval_str[1:])
                self.eval_text["fg"] = self.COLOR_GREEN if mate_value > 0 else self.COLOR_RED
            else:
                eval_value = float(eval_str)
                self.eval_text["fg"] = self.COLOR_GREEN if eval_value > 0 else (self.COLOR_FG if eval_value == 0 else self.COLOR_RED)
        except ValueError:
            self.eval_text["fg"] = self.COLOR_FG
        self.wdl_text["text"] = wdl_str
        self.material_text["text"] = material_str
        try:
            if material_str.startswith("+"):
                self.material_text["fg"] = self.COLOR_GREEN
            elif material_str.startswith("-"):
                self.material_text["fg"] = self.COLOR_RED
            else:
                self.material_text["fg"] = self.COLOR_FG
        except:
            self.material_text["fg"] = self.COLOR_FG
        self.white_acc_text["text"] = bot_acc
        self.black_acc_text["text"] = opponent_acc
        self.eval_text.update()
        self.wdl_text.update()
        self.material_text.update()
        self.white_acc_text.update()
        self.black_acc_text.update()


def play_intro_then_start():
    """Play intro video, then start the main GUI."""
    video_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..",
        "Modern Creative Logo Instagram Post.mp4"
    )
    if os.path.exists(video_path):
        intro = IntroVideo(video_path)
        intro_played = threading.Event()

        def on_intro_finished():
            intro_played.set()

        intro.play(on_intro_finished)
        # Wait for the video to finish (with timeout in case it loops)
        intro_played.wait(timeout=30)

    # Start the main GUI
    window = tk.Tk()
    my_gui = GUI(window)
    window.mainloop()


if __name__ == "__main__":
    play_intro_then_start()

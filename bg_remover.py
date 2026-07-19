"""
MagicRemover — an offline background remover built on flood-fill colour keying.

Pick a colour, flood fill selects the contiguous region within a tolerance, and
the region is written to the alpha channel. Every pick is kept as its own mask,
so the result is recomposited from the untouched original on every change and
any single pick can be taken back at any time.
"""

import math
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

APP_VERSION = "6.0"

# ============================================================================
# Interface strings
# ============================================================================

TEXTS = {
    "en": {
        "title": f"MagicRemover v{APP_VERSION}",
        "btn_open": "Open Image",
        "btn_save": "Save Result",
        "btn_reset": "Reset All",
        "btn_fit": "Fit",
        "label_tol": "Tolerance",
        "tol_hint": "applies to the latest pick",
        "mode_pick": "Pick",
        "mode_move": "Move",
        "mode_hint": "Scroll to zoom · drag to pan",
        "area_source": "Source",
        "area_preview": "Result",
        "area_hist": "History",
        "hist_item_text": "Colour removed",
        "hist_empty": "No picks yet.\nClick a colour in the source\nimage to remove it.",
        "hint_open": "Open an image to begin",
        "status_ready": "Ready",
        "msg_error": "Error",
        "msg_success": "Saved",
        "msg_saved": "Image saved successfully.",
        "msg_nothing": "Open an image first.",
        "resize_title": "Export Settings",
        "resize_opt_orig": "Original size",
        "resize_opt_custom": "Custom size",
        "resize_lbl_w": "Width (px)",
        "resize_lbl_h": "Height (px)",
        "resize_chk_ratio": "Lock aspect ratio",
        "btn_confirm": "Export",
        "btn_cancel": "Cancel",
        "lang_switch": "中文",
    },
    "zh": {
        "title": f"MagicRemover 去背器 v{APP_VERSION}",
        "btn_open": "打开图片",
        "btn_save": "保存结果",
        "btn_reset": "全部重置",
        "btn_fit": "适应窗口",
        "label_tol": "容差值",
        "tol_hint": "作用于最近一次取色",
        "mode_pick": "取色",
        "mode_move": "移动",
        "mode_hint": "滚轮缩放 · 拖拽平移",
        "area_source": "原图",
        "area_preview": "结果预览",
        "area_hist": "操作历史",
        "hist_item_text": "已去除颜色",
        "hist_empty": "还没有任何操作。\n在左侧原图上点击\n想去掉的颜色。",
        "hint_open": "打开一张图片开始",
        "status_ready": "就绪",
        "msg_error": "错误",
        "msg_success": "成功",
        "msg_saved": "图片已保存。",
        "msg_nothing": "请先打开一张图片。",
        "resize_title": "导出设置",
        "resize_opt_orig": "原始尺寸",
        "resize_opt_custom": "自定义尺寸",
        "resize_lbl_w": "宽度 (px)",
        "resize_lbl_h": "高度 (px)",
        "resize_chk_ratio": "锁定长宽比",
        "btn_confirm": "导出",
        "btn_cancel": "取消",
        "lang_switch": "EN",
    },
}

# ============================================================================
# Theme
# ============================================================================

BG_APP = "#1b1c1f"      # window background
BG_PANEL = "#232529"    # toolbars, side panel
BG_ELEV = "#2b2e33"     # raised controls
BG_HOVER = "#343841"
BG_CANVAS = "#141517"   # image viewport
BORDER = "#35383e"
TEXT = "#e6e8eb"
TEXT_DIM = "#9aa0a8"
ACCENT = "#4c8dff"
ACCENT_HOVER = "#6ba0ff"
DANGER = "#e5534b"
SUCCESS = "#3fb950"

FONT = "Segoe UI"
F_BODY = (FONT, 10)
F_SMALL = (FONT, 9)
F_LABEL = (FONT, 9, "bold")

CHECKER_LIGHT = 255
CHECKER_DARK = 205
CHECKER_STEP = 12


class Slider(tk.Canvas):
    """A flat slider drawn by hand.

    ttk's built-in scale cannot be styled into this look under any theme — clam
    stipples the trough and draws grip lines on the handle — so it is a canvas.
    """

    PAD = 11
    TRACK_H = 4
    KNOB_R = 7

    def __init__(self, parent, from_, to, value, command, width=220, height=26):
        super().__init__(parent, width=width, height=height, bg=BG_PANEL,
                         highlightthickness=0, cursor="hand2")
        self.from_, self.to = from_, to
        self.value = value
        self.command = command
        self._hover = False

        self.bind("<Button-1>", self._on_pointer)
        self.bind("<B1-Motion>", self._on_pointer)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Configure>", lambda e: self._redraw())
        self._redraw()

    # -- public API mirrors ttk.Scale --
    def set(self, value):
        self.value = max(self.from_, min(self.to, int(value)))
        self._redraw()

    def get(self):
        return self.value

    # -- internals --
    def _track_span(self):
        return self.PAD, max(self.PAD + 1, self.winfo_width() - self.PAD)

    def _on_enter(self, _):
        self._hover = True
        self._redraw()

    def _on_leave(self, _):
        self._hover = False
        self._redraw()

    def _on_pointer(self, event):
        x0, x1 = self._track_span()
        ratio = (event.x - x0) / max(1, x1 - x0)
        value = round(self.from_ + ratio * (self.to - self.from_))
        value = max(self.from_, min(self.to, value))
        if value != self.value:
            self.value = value
            self._redraw()
            self.command(value)

    def _redraw(self):
        self.delete("all")
        x0, x1 = self._track_span()
        cy = self.winfo_height() / 2
        ratio = (self.value - self.from_) / (self.to - self.from_)
        kx = x0 + ratio * (x1 - x0)
        half = self.TRACK_H / 2

        self.create_rectangle(x0, cy - half, x1, cy + half, fill=BG_APP, outline="")
        if kx > x0:
            self.create_rectangle(x0, cy - half, kx, cy + half, fill=ACCENT, outline="")

        r = self.KNOB_R + (1 if self._hover else 0)
        self.create_oval(kx - r, cy - r, kx + r, cy + r,
                         fill="#ffffff", outline=ACCENT_HOVER if self._hover else "", width=2)


class MagicRemover:
    def __init__(self, root):
        self.root = root
        self.lang = "zh"
        self.t = TEXTS[self.lang]

        # --- Core state (survives a language switch / UI rebuild) ---
        self.original_cv = None
        self.actions = []
        self.action_counter = 0
        self.final_cv_result = None
        self.filename = ""

        # --- View state ---
        self.mode = "pick"
        self.scale_factor = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.tolerance = 40

        self.root.configure(bg=BG_APP)
        self.root.geometry("1400x880")
        self.root.minsize(1000, 640)
        self._init_style()
        self._build_ui()
        self._bind_shortcuts()

    # ------------------------------------------------------------------
    # Styling
    # ------------------------------------------------------------------
    def _init_style(self):
        style = ttk.Style()
        style.theme_use("clam")  # the most restyleable built-in theme

        style.configure("TFrame", background=BG_PANEL)
        style.configure("App.TFrame", background=BG_APP)
        style.configure("Canvas.TFrame", background=BG_CANVAS)

        style.configure("TLabel", background=BG_PANEL, foreground=TEXT, font=F_BODY)
        style.configure("Dim.TLabel", background=BG_PANEL, foreground=TEXT_DIM, font=F_SMALL)
        style.configure("Header.TLabel", background=BG_PANEL, foreground=TEXT_DIM, font=F_LABEL)

        # Buttons: flat, no focus ring, colour-shifted on hover.
        def button(name, bg, fg, hover):
            style.configure(
                name,
                background=bg, foreground=fg, font=F_BODY,
                borderwidth=0, focuscolor=bg, relief="flat", padding=(14, 7),
            )
            style.map(
                name,
                background=[("pressed", hover), ("active", hover), ("disabled", BG_ELEV)],
                foreground=[("disabled", TEXT_DIM)],
            )

        button("Tool.TButton", BG_ELEV, TEXT, BG_HOVER)
        button("Accent.TButton", ACCENT, "#ffffff", ACCENT_HOVER)
        button("Danger.TButton", BG_ELEV, DANGER, BG_HOVER)
        button("Seg.TButton", BG_ELEV, TEXT_DIM, BG_HOVER)          # segmented, inactive
        button("SegOn.TButton", ACCENT, "#ffffff", ACCENT_HOVER)    # segmented, active
        button("Lang.TButton", BG_PANEL, TEXT_DIM, BG_ELEV)

        style.configure(
            "Vertical.TScrollbar",
            background=BG_ELEV, troughcolor=BG_PANEL, bordercolor=BG_PANEL,
            arrowcolor=TEXT_DIM, borderwidth=0,
        )
        style.map("Vertical.TScrollbar", background=[("active", BG_HOVER)])
        style.configure("TSeparator", background=BORDER)

        style.configure(
            "TRadiobutton",
            background=BG_PANEL, foreground=TEXT, font=F_BODY,
            indicatorcolor=BG_ELEV, focuscolor=BG_PANEL,
        )
        style.map("TRadiobutton", background=[("active", BG_PANEL)],
                  indicatorcolor=[("selected", ACCENT)])
        style.configure(
            "TCheckbutton",
            background=BG_PANEL, foreground=TEXT, font=F_BODY,
            indicatorcolor=BG_ELEV, focuscolor=BG_PANEL,
        )
        style.map("TCheckbutton", background=[("active", BG_PANEL)],
                  indicatorcolor=[("selected", ACCENT)])
        style.configure(
            "TEntry",
            fieldbackground=BG_ELEV, foreground=TEXT, bordercolor=BORDER,
            insertcolor=TEXT, borderwidth=1, padding=4,
        )

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_ui(self):
        """Build every widget. Called again from scratch on a language switch."""
        for child in self.root.winfo_children():
            child.destroy()

        self.root.title(self.t["title"])

        self._build_toolbar()

        body = ttk.Frame(self.root, style="App.TFrame")
        body.pack(fill=tk.BOTH, expand=True)

        self.canvas_orig = self._build_viewport(body, self.t["area_source"], weight=1)
        self.canvas_result = self._build_viewport(body, self.t["area_preview"], weight=1)
        self._build_history(body)

        self._build_statusbar()

        # Pointer interaction lives on the source canvas only.
        self.canvas_orig.bind("<Button-1>", self.on_mouse_down)
        self.canvas_orig.bind("<B1-Motion>", self.on_mouse_drag)
        for c in (self.canvas_orig, self.canvas_result):
            c.bind("<MouseWheel>", self.on_zoom)
            c.bind("<Button-4>", self.on_zoom)
            c.bind("<Button-5>", self.on_zoom)
            c.bind("<Configure>", lambda e: self.redraw_canvases())

        self.set_mode(self.mode)
        for action in self.actions:
            self.add_history_ui_row(action)
        self._sync_history_placeholder()
        self.root.after(50, self.redraw_canvases)

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(14, 10))
        bar.pack(fill=tk.X)
        tk.Frame(self.root, height=1, bg=BORDER).pack(fill=tk.X)

        ttk.Button(bar, text=self.t["btn_open"], style="Accent.TButton",
                   command=self.upload_image).pack(side=tk.LEFT)

        ttk.Separator(bar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=14)

        # Segmented pick/move control
        seg = ttk.Frame(bar)
        seg.pack(side=tk.LEFT)
        self.btn_pick = ttk.Button(seg, text=self.t["mode_pick"], width=8,
                                   command=lambda: self.set_mode("pick"))
        self.btn_pick.pack(side=tk.LEFT, padx=(0, 2))
        self.btn_move = ttk.Button(seg, text=self.t["mode_move"], width=8,
                                   command=lambda: self.set_mode("move"))
        self.btn_move.pack(side=tk.LEFT)

        ttk.Separator(bar, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=14)

        # Tolerance
        tol_box = ttk.Frame(bar)
        tol_box.pack(side=tk.LEFT)
        head = ttk.Frame(tol_box)
        head.pack(fill=tk.X)
        ttk.Label(head, text=self.t["label_tol"], style="Header.TLabel").pack(side=tk.LEFT)
        self.lbl_tol_value = ttk.Label(head, text=str(self.tolerance), style="TLabel")
        self.lbl_tol_value.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(head, text=self.t["tol_hint"], style="Dim.TLabel").pack(side=tk.LEFT, padx=(10, 0))

        self.scale_tol = Slider(tol_box, from_=0, to=150, value=self.tolerance,
                                command=self.update_last_action_tolerance, width=220)
        self.scale_tol.pack(fill=tk.X, pady=(1, 0))

        # Right-hand side
        ttk.Button(bar, text=self.t["lang_switch"], style="Lang.TButton", width=6,
                   command=self.toggle_language).pack(side=tk.RIGHT)
        ttk.Separator(bar, orient="vertical").pack(side=tk.RIGHT, fill=tk.Y, padx=14)
        ttk.Button(bar, text=self.t["btn_save"], style="Accent.TButton",
                   command=self.save_image).pack(side=tk.RIGHT)
        ttk.Button(bar, text=self.t["btn_reset"], style="Danger.TButton",
                   command=self.reset_all).pack(side=tk.RIGHT, padx=8)
        ttk.Button(bar, text=self.t["btn_fit"], style="Tool.TButton",
                   command=self.fit_to_window).pack(side=tk.RIGHT)

    def _build_viewport(self, parent, title, weight):
        """A titled canvas pane. Returns the canvas."""
        wrap = tk.Frame(parent, bg=BG_APP)
        wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)

        header = tk.Frame(wrap, bg=BG_PANEL, height=30)
        header.pack(fill=tk.X)
        tk.Label(header, text=title, bg=BG_PANEL, fg=TEXT_DIM, font=F_LABEL,
                 anchor="w", padx=12, pady=6).pack(fill=tk.X)

        canvas = tk.Canvas(wrap, bg=BG_CANVAS, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        return canvas

    def _build_history(self, parent):
        panel = tk.Frame(parent, bg=BG_PANEL, width=290)
        panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        panel.pack_propagate(False)

        tk.Label(panel, text=self.t["area_hist"], bg=BG_PANEL, fg=TEXT_DIM, font=F_LABEL,
                 anchor="w", padx=12, pady=8).pack(fill=tk.X)
        tk.Frame(panel, height=1, bg=BORDER).pack(fill=tk.X)

        holder = tk.Frame(panel, bg=BG_PANEL)
        holder.pack(fill=tk.BOTH, expand=True)

        self.history_canvas = tk.Canvas(holder, bg=BG_PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.history_canvas.yview)
        self.scrollable_frame = tk.Frame(self.history_canvas, bg=BG_PANEL)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all")),
        )
        self.history_window = self.history_canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )
        self.history_canvas.bind(
            "<Configure>",
            lambda e: self.history_canvas.itemconfig(self.history_window, width=e.width),
        )
        self.history_canvas.configure(yscrollcommand=scrollbar.set)

        self.history_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.lbl_hist_empty = tk.Label(
            self.scrollable_frame, text=self.t["hist_empty"], bg=BG_PANEL, fg=TEXT_DIM,
            font=F_SMALL, justify="left", anchor="w", padx=14, pady=16,
        )

    def _build_statusbar(self):
        tk.Frame(self.root, height=1, bg=BORDER).pack(fill=tk.X)
        bar = tk.Frame(self.root, bg=BG_PANEL)
        bar.pack(fill=tk.X)
        self.lbl_status = tk.Label(bar, text=self.t["hint_open"], bg=BG_PANEL, fg=TEXT_DIM,
                                   font=F_SMALL, anchor="w", padx=14, pady=6)
        self.lbl_status.pack(side=tk.LEFT)
        self.lbl_hint = tk.Label(bar, text=self.t["mode_hint"], bg=BG_PANEL, fg=TEXT_DIM,
                                 font=F_SMALL, anchor="e", padx=14, pady=6)
        self.lbl_hint.pack(side=tk.RIGHT)

    def _bind_shortcuts(self):
        self.root.bind("<Control-o>", lambda e: self.upload_image())
        self.root.bind("<Control-s>", lambda e: self.save_image())
        self.root.bind("<Control-z>", lambda e: self.undo_last())

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------
    def toggle_language(self):
        self.lang = "en" if self.lang == "zh" else "zh"
        self.t = TEXTS[self.lang]
        self._build_ui()          # state is preserved; only widgets are rebuilt
        self.update_status()

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def set_mode(self, mode):
        self.mode = mode
        picking = mode == "pick"
        self.btn_pick.configure(style="SegOn.TButton" if picking else "Seg.TButton")
        self.btn_move.configure(style="Seg.TButton" if picking else "SegOn.TButton")
        self.canvas_orig.config(cursor="crosshair" if picking else "fleur")

    def on_zoom(self, event):
        if self.original_cv is None:
            return
        scale_mult = 0.9 if (event.num == 5 or event.delta < 0) else 1.1
        new_scale = self.scale_factor * scale_mult
        if new_scale < 0.02 or new_scale > 40:
            return

        # Keep the point under the cursor fixed while zooming.
        img_x = (event.x - self.offset_x) / self.scale_factor
        img_y = (event.y - self.offset_y) / self.scale_factor
        self.scale_factor = new_scale
        self.offset_x = event.x - img_x * self.scale_factor
        self.offset_y = event.y - img_y * self.scale_factor

        self.redraw_canvases()
        self.update_status()

    def on_mouse_down(self, event):
        if self.mode == "move":
            self.last_mouse_x, self.last_mouse_y = event.x, event.y
        else:
            self.handle_color_pick(event.x, event.y)

    def on_mouse_drag(self, event):
        if self.mode != "move":
            return
        self.offset_x += event.x - self.last_mouse_x
        self.offset_y += event.y - self.last_mouse_y
        self.last_mouse_x, self.last_mouse_y = event.x, event.y
        self.redraw_canvases()

    def handle_color_pick(self, screen_x, screen_y):
        if self.original_cv is None:
            return
        img_x = int((screen_x - self.offset_x) / self.scale_factor)
        img_y = int((screen_y - self.offset_y) / self.scale_factor)
        h, w = self.original_cv.shape[:2]
        if 0 <= img_x < w and 0 <= img_y < h:
            self.add_action(img_x, img_y, self.tolerance)

    # ------------------------------------------------------------------
    # Image IO
    # ------------------------------------------------------------------
    def upload_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            # imdecode via fromfile so non-ASCII paths work on Windows.
            img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if img is None:
                raise ValueError("Unsupported or corrupt image file.")

            if img.ndim == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
            elif img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)

            self.original_cv = img
            self.filename = path.replace("\\", "/").split("/")[-1]
            self.reset_all()
            self.fit_to_window()
        except Exception as exc:
            messagebox.showerror(self.t["msg_error"], str(exc))

    def save_image(self):
        if self.final_cv_result is None:
            messagebox.showinfo(self.t["msg_error"], self.t["msg_nothing"])
            return

        h, w = self.final_cv_result.shape[:2]
        target_size = self.ask_resize_dialog(h, w)
        if target_size is None:
            return

        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            filetypes=[("PNG", "*.png")])
        if not path:
            return
        try:
            img = self.final_cv_result
            if target_size != (w, h):
                interp = cv2.INTER_AREA if target_size[0] < w else cv2.INTER_LINEAR
                img = cv2.resize(img, target_size, interpolation=interp)
            ok, buf = cv2.imencode(".png", img)
            if not ok:
                raise IOError("PNG encoding failed.")
            buf.tofile(path)
            messagebox.showinfo(self.t["msg_success"], self.t["msg_saved"])
        except Exception as exc:
            messagebox.showerror(self.t["msg_error"], str(exc))

    # ------------------------------------------------------------------
    # View rendering
    # ------------------------------------------------------------------
    def fit_to_window(self):
        if self.original_cv is None:
            return
        h, w = self.original_cv.shape[:2]
        cw = self.canvas_orig.winfo_width() or 600
        ch = self.canvas_orig.winfo_height() or 500
        self.scale_factor = min(cw / w, ch / h) * 0.92
        self.offset_x = (cw - w * self.scale_factor) / 2
        self.offset_y = (ch - h * self.scale_factor) / 2
        self.redraw_canvases()
        self.update_status()

    def redraw_canvases(self):
        if self.original_cv is None:
            return
        self.tk_orig = self._render(self.canvas_orig, self.original_cv, checker=False)
        self.tk_res = self._render(self.canvas_result, self.final_cv_result, checker=True)

    def _render(self, canvas, cv_img, checker):
        """Draw the visible slice of cv_img into canvas at the shared zoom/pan.

        Only the region actually on screen is cropped and scaled, so memory and
        time stay bound to the canvas size no matter how far in the user zooms.
        """
        if cv_img is None:
            return None
        cw, ch = canvas.winfo_width(), canvas.winfo_height()
        if cw < 10 or ch < 10:
            return None

        canvas.delete("all")
        h, w = cv_img.shape[:2]
        s = self.scale_factor

        x0 = max(0, int(math.floor(-self.offset_x / s)))
        y0 = max(0, int(math.floor(-self.offset_y / s)))
        x1 = min(w, int(math.ceil((cw - self.offset_x) / s)))
        y1 = min(h, int(math.ceil((ch - self.offset_y) / s)))
        if x1 <= x0 or y1 <= y0:
            return None  # image scrolled fully off screen

        crop = cv_img[y0:y1, x0:x1]
        dw = max(1, int(round((x1 - x0) * s)))
        dh = max(1, int(round((y1 - y0) * s)))
        interp = cv2.INTER_NEAREST if s >= 1 else cv2.INTER_AREA
        small = cv2.resize(crop, (dw, dh), interpolation=interp)

        if checker:
            small = self._composite_checkerboard(small)

        photo = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGRA2RGBA)))
        canvas.create_image(
            int(round(self.offset_x + x0 * s)),
            int(round(self.offset_y + y0 * s)),
            anchor=tk.NW, image=photo,
        )
        return photo  # caller keeps the reference alive

    @staticmethod
    def _composite_checkerboard(img_bgra):
        """Flatten BGRA onto a checkerboard so transparency is visible."""
        h, w = img_bgra.shape[:2]
        rows = (np.arange(h) // CHECKER_STEP)[:, None]
        cols = (np.arange(w) // CHECKER_STEP)[None, :]
        board = np.where((rows + cols) % 2 == 0, CHECKER_LIGHT, CHECKER_DARK)
        board = np.repeat(board[:, :, None], 3, axis=2).astype(np.float32)

        alpha = img_bgra[:, :, 3:4].astype(np.float32) / 255.0
        rgb = img_bgra[:, :, :3].astype(np.float32)
        out = (rgb * alpha + board * (1 - alpha)).astype(np.uint8)
        return cv2.cvtColor(out, cv2.COLOR_BGR2BGRA)

    def update_status(self):
        if self.original_cv is None:
            self.lbl_status.config(text=self.t["hint_open"])
            return
        h, w = self.original_cv.shape[:2]
        self.lbl_status.config(
            text=f"{self.filename}   ·   {w} × {h} px   ·   {self.scale_factor * 100:.0f}%"
        )

    # ------------------------------------------------------------------
    # Actions (the non-destructive pick stack)
    # ------------------------------------------------------------------
    def add_action(self, x, y, tol):
        b, g, r, _ = self.original_cv[y, x]
        self.action_counter += 1
        action = {
            "id": self.action_counter,
            "seed": (x, y),
            "tolerance": tol,
            "mask": self.compute_flood_mask(x, y, tol),
            "color_hex": f"#{r:02x}{g:02x}{b:02x}",
        }
        self.actions.append(action)

        self.add_history_ui_row(action)
        self._sync_history_placeholder()
        self.refresh_result_data()
        self.redraw_canvases()

    def compute_flood_mask(self, x, y, tol):
        """Mask of pixels within ±tol of the seed colour, connected to the seed."""
        img = self.original_cv[:, :, :3].copy()
        h, w = img.shape[:2]
        mask = np.zeros((h + 2, w + 2), np.uint8)
        flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE
        try:
            cv2.floodFill(img, mask, (x, y), (0, 0, 0), (tol,) * 3, (tol,) * 3, flags)
            return mask[1:-1, 1:-1]
        except cv2.error as exc:
            print(f"floodFill failed: {exc}")
            return np.zeros((h, w), np.uint8)

    def update_last_action_tolerance(self, val):
        tol = int(float(val))
        if tol == self.tolerance:
            return
        # Always track the slider, even with no picks yet, so the *next* pick
        # uses the value actually shown on screen.
        self.tolerance = tol
        self.lbl_tol_value.config(text=str(tol))
        if not self.actions:
            return

        last = self.actions[-1]
        last["tolerance"] = tol
        last["mask"] = self.compute_flood_mask(*last["seed"], tol)
        self.refresh_result_data()
        self.redraw_canvases()

    def delete_action(self, action_id, ui_row):
        self.actions = [a for a in self.actions if a["id"] != action_id]
        ui_row.destroy()
        self._sync_history_placeholder()
        self.refresh_result_data()
        self.redraw_canvases()

    def undo_last(self):
        if self.actions:
            last = self.actions[-1]
            self.delete_action(last["id"], last["row"])

    def add_history_ui_row(self, action):
        row = tk.Frame(self.scrollable_frame, bg=BG_PANEL)
        row.pack(fill=tk.X, padx=10, pady=3)
        action["row"] = row

        swatch = tk.Frame(row, bg=action["color_hex"], width=34, height=26,
                          highlightbackground=BORDER, highlightthickness=1)
        swatch.pack(side=tk.LEFT, padx=(8, 10), pady=6)
        swatch.pack_propagate(False)

        text = tk.Frame(row, bg=BG_PANEL)
        text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        lbl_name = tk.Label(text, text=self.t["hist_item_text"], bg=BG_PANEL, fg=TEXT,
                            font=F_BODY, anchor="w")
        lbl_name.pack(fill=tk.X)
        lbl_meta = tk.Label(text, text=f"{action['color_hex'].upper()} · ±{action['tolerance']}",
                            bg=BG_PANEL, fg=TEXT_DIM, font=F_SMALL, anchor="w")
        lbl_meta.pack(fill=tk.X)

        btn = tk.Label(row, text="✕", bg=BG_PANEL, fg=TEXT_DIM, font=(FONT, 10),
                       cursor="hand2", padx=10)
        btn.pack(side=tk.RIGHT)
        btn.bind("<Button-1>", lambda e, i=action["id"], f=row: self.delete_action(i, f))

        # Hover highlights the whole row, not just the widget under the cursor.
        members = (row, text, lbl_name, lbl_meta, btn)

        def enter(_):
            for m in members:
                m.configure(bg=BG_ELEV)
            btn.configure(fg=DANGER)

        def leave(_):
            for m in members:
                m.configure(bg=BG_PANEL)
            btn.configure(fg=TEXT_DIM)

        for m in members:
            m.bind("<Enter>", enter)
            m.bind("<Leave>", leave)

    def _sync_history_placeholder(self):
        if self.actions:
            self.lbl_hist_empty.pack_forget()
        else:
            self.lbl_hist_empty.pack(fill=tk.X)

    def refresh_result_data(self):
        """Recompose the result from the untouched original + every live mask."""
        if self.original_cv is None:
            return
        h, w = self.original_cv.shape[:2]
        alpha = np.full((h, w), 255, dtype=np.uint8)
        for action in self.actions:
            alpha[action["mask"] == 255] = 0

        result = self.original_cv.copy()
        result[:, :, 3] = alpha
        self.final_cv_result = result

    def reset_all(self):
        self.actions = []
        self.action_counter = 0
        for widget in self.scrollable_frame.winfo_children():
            if widget is not self.lbl_hist_empty:
                widget.destroy()
        self._sync_history_placeholder()
        self.refresh_result_data()
        self.redraw_canvases()
        self.update_status()

    # ------------------------------------------------------------------
    # Export dialog
    # ------------------------------------------------------------------
    def ask_resize_dialog(self, original_h, original_w):
        """Modal export-size dialog. Returns (w, h) or None if cancelled."""
        dialog = tk.Toplevel(self.root)
        dialog.title(self.t["resize_title"])
        dialog.configure(bg=BG_PANEL)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        var_choice = tk.IntVar(value=1)  # 1 = original, 2 = custom
        var_w = tk.StringVar(value=str(original_w))
        var_h = tk.StringVar(value=str(original_h))
        var_lock = tk.BooleanVar(value=True)
        result = {"size": None}
        syncing = {"busy": False}

        body = ttk.Frame(dialog, padding=(22, 18))
        body.pack(fill=tk.BOTH, expand=True)

        def toggle_inputs():
            state = "normal" if var_choice.get() == 2 else "disabled"
            entry_w.config(state=state)
            entry_h.config(state=state)
            chk_lock.config(state=state)

        def on_dim_change(source):
            """Mirror the edited dimension into the other one when locked."""
            if syncing["busy"] or not var_lock.get() or var_choice.get() != 2:
                return
            syncing["busy"] = True
            try:
                if source == "w":
                    w = int(var_w.get())
                    if w > 0:
                        var_h.set(str(max(1, round(w * original_h / original_w))))
                else:
                    h = int(var_h.get())
                    if h > 0:
                        var_w.set(str(max(1, round(h * original_w / original_h))))
            except ValueError:
                pass  # mid-typing; ignore
            finally:
                syncing["busy"] = False

        def on_confirm():
            if var_choice.get() == 1:
                result["size"] = (original_w, original_h)
            else:
                try:
                    w, h = int(var_w.get()), int(var_h.get())
                except ValueError:
                    return
                if w <= 0 or h <= 0:
                    return
                result["size"] = (w, h)
            dialog.destroy()

        ttk.Radiobutton(
            body, text=f"{self.t['resize_opt_orig']}  ({original_w} × {original_h})",
            variable=var_choice, value=1, command=toggle_inputs,
        ).pack(anchor="w", pady=(0, 8))
        ttk.Radiobutton(
            body, text=self.t["resize_opt_custom"],
            variable=var_choice, value=2, command=toggle_inputs,
        ).pack(anchor="w")

        fields = ttk.Frame(body, padding=(26, 10, 0, 0))
        fields.pack(fill=tk.X)

        ttk.Label(fields, text=self.t["resize_lbl_w"]).grid(row=0, column=0, sticky="w", pady=3)
        entry_w = ttk.Entry(fields, textvariable=var_w, width=10, state="disabled")
        entry_w.grid(row=0, column=1, padx=10, pady=3)

        ttk.Label(fields, text=self.t["resize_lbl_h"]).grid(row=1, column=0, sticky="w", pady=3)
        entry_h = ttk.Entry(fields, textvariable=var_h, width=10, state="disabled")
        entry_h.grid(row=1, column=1, padx=10, pady=3)

        chk_lock = ttk.Checkbutton(fields, text=self.t["resize_chk_ratio"],
                                   variable=var_lock, state="disabled")
        chk_lock.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        var_w.trace_add("write", lambda *_: on_dim_change("w"))
        var_h.trace_add("write", lambda *_: on_dim_change("h"))

        buttons = ttk.Frame(body, padding=(0, 18, 0, 0))
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text=self.t["btn_confirm"], style="Accent.TButton",
                   command=on_confirm).pack(side=tk.RIGHT)
        ttk.Button(buttons, text=self.t["btn_cancel"], style="Tool.TButton",
                   command=dialog.destroy).pack(side=tk.RIGHT, padx=8)

        dialog.bind("<Return>", lambda e: on_confirm())
        dialog.bind("<Escape>", lambda e: dialog.destroy())

        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_height()) // 3
        dialog.geometry(f"+{x}+{y}")

        self.root.wait_window(dialog)
        return result["size"]


if __name__ == "__main__":
    root = tk.Tk()
    app = MagicRemover(root)
    root.mainloop()

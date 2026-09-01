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

APP_VERSION = "7.0"

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
        "btn_guide": "Guide",
        "guide_title": "User Guide",
        "guide_close": "Close",
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
        "btn_guide": "使用指南",
        "guide_title": "使用指南",
        "guide_close": "关闭",
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
# User guide content
#
# Blocks are (kind, payload) pairs rendered by MagicRemover._render_guide:
#   h    heading                p    paragraph            ol   numbered steps
#   ul   (term, detail) pairs   kbd  (keys, action) pairs
# Kept as data in both languages so the guide follows the language switch.
# ============================================================================

GUIDE = {
    "en": [
        ("p", "MagicRemover removes backgrounds with classic computer vision "
              "\u2014 flood-fill colour keying \u2014 instead of an AI model. Every "
              "removal is something you aim, tune, stack and undo yourself, and "
              "nothing ever leaves your machine."),
        ("p", "It is best suited to images with flat, solid-colour backgrounds: "
              "logos, product shots, screenshots, scanned artwork."),

        ("h", "Getting started"),
        ("ol", [
            "Open Image loads a PNG / JPG / BMP / WEBP file.",
            "Stay in Pick mode and click the background colour you want gone. "
            "You can click in either view \u2014 the source or the result.",
            "Drag the Tolerance slider to tighten or loosen that pick until the "
            "edge looks right.",
            "Click more colours to remove them too. Each becomes its own entry "
            "in History; click \u2715 on an entry to take just that one back.",
            "Switch to Move mode to drag the view. The scroll wheel zooms in "
            "either mode, and Fit returns to the whole image.",
            "Save Result \u2014 choose the original or a custom export size, then "
            "save as PNG.",
            "Reset All clears every pick and returns to the untouched image.",
        ]),

        ("h", "Aiming with the crosshair"),
        ("p", "While the pointer is over the source image, a crosshair on the "
              "result view marks the exact pixel under it. Use it to aim: find "
              "the leftover area in the result that you still want gone, move "
              "the pointer until the ring sits on it, then click."),

        ("h", "Shortcuts"),
        ("kbd", [
            ("Ctrl + O", "Open image"),
            ("Ctrl + S", "Save result"),
            ("Ctrl + Z", "Undo the latest pick"),
            ("F1", "Open this guide"),
        ]),

        ("h", "Features"),
        ("ul", [
            ("Click-to-remove colour keying",
             "Click any colour in the image; flood fill selects the contiguous "
             "region within an adjustable tolerance and writes it to the alpha "
             "channel."),
            ("Non-destructive, editable history",
             "Every pick is a separate layer in the history panel. Delete any "
             "one of them at any time; the result recomposites instantly."),
            ("Adjustable tolerance",
             "The slider retunes the most recent pick live, so you can dial in "
             "the edge without starting over."),
            ("Synced dual view",
             "The original and the transparency preview (rendered over a "
             "checkerboard) share one zoom/pan viewport, so you always compare "
             "the same region."),
            ("Pick / Move modes",
             "Scroll to zoom toward the cursor, drag to pan. Only the on-screen "
             "region is ever scaled, so zooming stays fast on large images."),
            ("Export with resizing",
             "Save as PNG at the original size, or a custom size with optional "
             "aspect-ratio lock."),
            ("Bilingual UI",
             "Switch between English and Chinese at runtime \u2014 no restart, and "
             "your picks and zoom are preserved."),
            ("Runs offline",
             "No network calls, no uploads, no account."),
        ]),

        ("h", "How it works"),
        ("p", "The image is loaded as BGRA. Each click runs cv2.floodFill in "
              "FLOODFILL_MASK_ONLY mode with FLOODFILL_FIXED_RANGE, meaning "
              "every pixel is compared against the seed colour you clicked (not "
              "against its neighbour), within \u00b1tolerance on each channel. That "
              "produces a binary mask, stored alongside its seed point and "
              "tolerance rather than being applied immediately."),
        ("p", "Because the masks are kept as a list, the final image is "
              "recomputed from scratch on every change: start from a fully "
              "opaque alpha channel, zero it wherever any mask is set, write it "
              "into a copy of the original. This is what makes the history "
              "genuinely non-destructive \u2014 deleting a pick simply drops it from "
              "the list, and the original pixel data is never modified."),

        ("h", "Known limitations"),
        ("ul", [
            ("Flat backgrounds only.",
             "Flood fill keys on colour similarity, so gradients, textures and "
             "busy backgrounds will not separate cleanly. This is not a matting "
             "model \u2014 it cannot cut out hair or soft, semi-transparent edges."),
            ("Hard alpha edges.",
             "The mask is binary with no feathering or anti-aliasing, which can "
             "leave visible stair-stepping on curves against a contrasting new "
             "background."),
            ("Tolerance affects the latest pick only.",
             "Earlier picks keep the tolerance they were made with; to change "
             "one, delete it and pick again."),
            ("Export is PNG only.",
             "Which is the format that preserves transparency anyway."),
        ]),

        ("h", "About"),
        ("p", "MagicRemover v%s \u00b7 MIT licence \u00b7 runs entirely offline."
              % APP_VERSION),
    ],

    "zh": [
        ("p", "MagicRemover 用传统计算机视觉（漫水填充颜色键控）而不是 AI 模型来去背。"
              "每一次去除都由你自己瞄准、微调、叠加和撤销，且全程不联网，图片不会离开"
              "你的电脑。"),
        ("p", "最适合纯色背景的图片——logo、商品图、截图、扫描稿。"),

        ("h", "快速上手"),
        ("ol", [
            "打开图片，支持 PNG / JPG / BMP / WEBP。",
            "保持在取色模式，点击你想去掉的背景颜色。左右两个视图都可以点。",
            "拖动容差值滑块收紧或放宽这次取色，直到边缘合适。",
            "继续点击其他颜色一并去除。每次都会成为操作历史里的一条，"
            "点某条的 \u2715 即可只撤销那一次。",
            "切到移动模式拖动画面。两种模式下滚轮都能缩放，适应窗口可回到全图。",
            "保存结果——选择原始或自定义导出尺寸，保存为 PNG。",
            "全部重置清空所有操作，回到未处理的原图。",
        ]),

        ("h", "用准星瞄准"),
        ("p", "当鼠标在左侧原图上时，右侧结果预览会出现一个准星，标出鼠标所指的那个"
              "像素。用它来瞄准：先在右边找到你还想去掉的残留区域，移动鼠标让圆环"
              "套上它，然后点击。"),

        ("h", "快捷键"),
        ("kbd", [
            ("Ctrl + O", "打开图片"),
            ("Ctrl + S", "保存结果"),
            ("Ctrl + Z", "撤销最近一次取色"),
            ("F1", "打开本指南"),
        ]),

        ("h", "功能"),
        ("ul", [
            ("点击即去除的颜色键控",
             "点击图中任意颜色，漫水填充按可调容差选出相连区域并写入 alpha 通道。"),
            ("非破坏性的可编辑历史",
             "每次取色都是历史面板中独立的一层，随时可以删掉其中任意一条，"
             "结果立即重新合成。"),
            ("可调容差",
             "滑块会实时重算最近一次取色，不必推倒重来就能调好边缘。"),
            ("双视图同步",
             "原图与透明预览（棋盘格背景）共用同一套缩放/平移视图，"
             "永远在对比同一块区域。"),
            ("取色 / 移动 双模式",
             "滚轮以光标为中心缩放，拖拽平移。只有屏幕上可见的区域会被缩放绘制，"
             "因此再大的图放到多少倍都不卡。"),
            ("导出可缩放",
             "保存为 PNG，可选原始尺寸或自定义尺寸（支持锁定长宽比）。"),
            ("双语界面",
             "中英文可随时切换，无需重启，已有的操作历史和缩放状态都会保留。"),
            ("完全离线",
             "不联网、不上传、不需要账号。"),
        ]),

        ("h", "实现原理"),
        ("p", "图片以 BGRA 格式载入。每次点击调用 cv2.floodFill，使用 "
              "FLOODFILL_MASK_ONLY 加 FLOODFILL_FIXED_RANGE——即每个像素都与你点击的"
              "种子颜色比较（而非与相邻像素比较），各通道容差为 ±容差值。这会产生一张"
              "二值掩码，它与种子点、容差一起被存起来，而不是立刻应用到图上。"),
        ("p", "因为掩码是以列表形式保存的，最终图像在每次变动时都从头重算：从完全"
              "不透明的 alpha 通道开始，把任意掩码覆盖到的位置置零，再写入原图的副本。"
              "这正是历史记录真正非破坏性的原因——删除一次取色只是把它从列表里移除，"
              "原始像素数据从未被修改过。"),

        ("h", "已知限制"),
        ("ul", [
            ("仅适用于纯色背景。",
             "漫水填充依据颜色相似度工作，因此渐变、纹理和复杂背景无法干净分离。"
             "它不是抠图模型，做不了头发丝和半透明的柔和边缘。"),
            ("alpha 边缘是硬的。",
             "掩码是二值的，没有羽化或抗锯齿，换到反差大的新背景上时曲线边缘"
             "可能有可见的锯齿。"),
            ("容差滑块只影响最近一次取色。",
             "更早的操作保持它们当时的容差；要改就删掉重新取色。"),
            ("只能导出 PNG。",
             "本来也只有 PNG 能保留透明度。"),
        ]),

        ("h", "关于"),
        ("p", "MagicRemover v%s \u00b7 MIT 许可证 \u00b7 完全离线运行。" % APP_VERSION),
    ],
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

CURSOR_TAG = "cursor"   # canvas tag for the position marker, deleted per redraw
CURSOR_RING_R = 7
CURSOR_DASH = (5, 5)


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
        self.cursor_pos = None   # image coords under the pointer, mirrored to the result view
        self.guide_win = None
        self._guide_wraps = []   # (label, horizontal chrome) pairs, rewrapped on resize

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
        self.cursor_pos = None
        self.guide_win = None    # a Toplevel is a child of root, so it is destroyed below
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

        # Both viewports share one zoom/pan and are the same size, so canvas-
        # relative event coords mean the same thing in either one — picking and
        # panning work from whichever view you happen to be looking at.
        for c in (self.canvas_orig, self.canvas_result):
            c.bind("<Button-1>", self.on_mouse_down)
            c.bind("<B1-Motion>", self.on_mouse_drag)
            c.bind("<MouseWheel>", self.on_zoom)
            c.bind("<Button-4>", self.on_zoom)
            c.bind("<Button-5>", self.on_zoom)
            c.bind("<Configure>", lambda e: self.redraw_canvases())
        self.canvas_orig.bind("<Motion>", self.on_mouse_move)
        self.canvas_orig.bind("<Leave>", self.on_mouse_leave)

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
        ttk.Button(bar, text=self.t["btn_guide"], style="Lang.TButton",
                   command=self.show_guide).pack(side=tk.RIGHT, padx=(0, 4))
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
        self.root.bind("<F1>", lambda e: self.show_guide())

    # ------------------------------------------------------------------
    # Language
    # ------------------------------------------------------------------
    def toggle_language(self):
        guide_was_open = self.guide_win is not None and self.guide_win.winfo_exists()
        self.lang = "en" if self.lang == "zh" else "zh"
        self.t = TEXTS[self.lang]
        self._build_ui()          # state is preserved; only widgets are rebuilt
        self.update_status()
        if guide_was_open:
            self.show_guide()     # _build_ui destroyed it; bring it back translated

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def set_mode(self, mode):
        self.mode = mode
        picking = mode == "pick"
        self.btn_pick.configure(style="SegOn.TButton" if picking else "Seg.TButton")
        self.btn_move.configure(style="Seg.TButton" if picking else "SegOn.TButton")
        for c in (self.canvas_orig, self.canvas_result):
            c.config(cursor="crosshair" if picking else "fleur")

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

    def on_mouse_move(self, event):
        """Mirror the pointer's image position onto the result view."""
        pos = self.screen_to_image(event.x, event.y)
        if pos == self.cursor_pos:
            return
        self.cursor_pos = pos
        self._draw_cursor_marker()

    def on_mouse_leave(self, _):
        if self.cursor_pos is not None:
            self.cursor_pos = None
            self._draw_cursor_marker()

    def screen_to_image(self, screen_x, screen_y):
        """Canvas coords -> image coords, or None if outside the image."""
        if self.original_cv is None:
            return None
        img_x = int((screen_x - self.offset_x) / self.scale_factor)
        img_y = int((screen_y - self.offset_y) / self.scale_factor)
        h, w = self.original_cv.shape[:2]
        if 0 <= img_x < w and 0 <= img_y < h:
            return img_x, img_y
        return None

    def handle_color_pick(self, screen_x, screen_y):
        pos = self.screen_to_image(screen_x, screen_y)
        if pos is not None:
            self.add_action(pos[0], pos[1], self.tolerance)

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
        self._draw_cursor_marker()   # _render cleared the canvas

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

    def _draw_cursor_marker(self):
        """Crosshair on the result view marking where the pointer is in the source.

        Anchored to image coordinates, not screen ones, so it stays on the same
        pixel while the view is panned or zoomed. Drawn in alternating white and
        accent dashes so it stays visible over both the image and the
        checkerboard.
        """
        canvas = self.canvas_result
        canvas.delete(CURSOR_TAG)
        if self.cursor_pos is None or self.final_cv_result is None:
            return

        img_x, img_y = self.cursor_pos
        s = self.scale_factor
        cx = self.offset_x + (img_x + 0.5) * s   # centre of the pixel, not its corner
        cy = self.offset_y + (img_y + 0.5) * s
        cw, ch = canvas.winfo_width(), canvas.winfo_height()

        # A solid white line under a dashed accent one: the gaps in the dashes
        # show the white through, so the crosshair stays legible over dark
        # pixels, light pixels and the checkerboard alike. (Two offset dashed
        # lines would be tidier, but Tk approximates dash patterns and ignores
        # dashoffset on Windows, which just hides one line under the other.)
        r = CURSOR_RING_R
        gap = r + 3   # the lines stop short of the ring, leaving the target pixel clear
        for coords in ((0, cy, cx - gap, cy), (cx + gap, cy, cw, cy),
                       (cx, 0, cx, cy - gap), (cx, cy + gap, cx, ch)):
            canvas.create_line(*coords, fill="#ffffff", width=1, tags=CURSOR_TAG)
            canvas.create_line(*coords, fill=ACCENT, width=1,
                               dash=CURSOR_DASH, tags=CURSOR_TAG)

        box = (cx - r, cy - r, cx + r, cy + r)
        canvas.create_oval(*box, outline="#ffffff", width=3, tags=CURSOR_TAG)
        canvas.create_oval(*box, outline=ACCENT, width=1, tags=CURSOR_TAG)

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
    # User guide
    # ------------------------------------------------------------------
    GUIDE_PAD = 22           # left/right margin inside the guide
    GUIDE_STEP_W = 30        # width of the step-number gutter
    GUIDE_DETAIL_IN = 16     # extra indent under a feature term

    def show_guide(self):
        """Open the guide, or raise it if it is already up.

        Deliberately not modal: it is meant to stay open beside the main window
        while you work through the steps.
        """
        if self.guide_win is not None and self.guide_win.winfo_exists():
            self.guide_win.deiconify()
            self.guide_win.lift()
            self.guide_win.focus_set()
            return

        win = tk.Toplevel(self.root)
        self.guide_win = win
        win.title(self.t["guide_title"])
        win.configure(bg=BG_APP)
        win.geometry("780x680")
        win.minsize(460, 320)
        win.transient(self.root)

        header = tk.Frame(win, bg=BG_PANEL)
        header.pack(fill=tk.X)
        tk.Label(header, text=self.t["guide_title"], bg=BG_PANEL, fg=TEXT,
                 font=(FONT, 12, "bold"), anchor="w",
                 padx=self.GUIDE_PAD, pady=12).pack(fill=tk.X)
        tk.Frame(win, height=1, bg=BORDER).pack(fill=tk.X)

        # Footer is packed before the body so it keeps its height when the
        # body expands.
        footer = tk.Frame(win, bg=BG_PANEL)
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(footer, text=self.t["guide_close"], style="Tool.TButton",
                   command=win.destroy).pack(side=tk.RIGHT, padx=16, pady=10)
        tk.Frame(win, height=1, bg=BORDER).pack(side=tk.BOTTOM, fill=tk.X)

        body = tk.Frame(win, bg=BG_APP)
        body.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(body, bg=BG_APP, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG_APP)

        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def on_resize(event):
            canvas.itemconfig(window_id, width=event.width)
            self._reflow_guide(event.width)

        canvas.bind("<Configure>", on_resize)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._guide_wraps = []
        self._render_guide(inner)

        def on_wheel(event):
            canvas.yview_scroll(1 if (event.num == 5 or event.delta < 0) else -1, "units")

        # Bound per widget rather than with bind_all: a global binding would
        # also fire over the image viewports and fight with zooming.
        self._bind_wheel(body, on_wheel)

        win.bind("<Escape>", lambda e: win.destroy())
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_width()) // 2
        y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - win.winfo_height()) // 3)
        win.geometry("+%d+%d" % (x, y))

    def _render_guide(self, parent):
        """Turn the GUIDE blocks for the current language into widgets."""
        pad = self.GUIDE_PAD

        def wrapped(label, chrome):
            """Register a label whose wraplength tracks the window width."""
            self._guide_wraps.append((label, chrome))
            return label

        for kind, payload in GUIDE[self.lang]:
            if kind == "h":
                box = tk.Frame(parent, bg=BG_APP)
                box.pack(fill=tk.X, padx=pad, pady=(22, 8))
                tk.Label(box, text=payload, bg=BG_APP, fg=TEXT,
                         font=(FONT, 11, "bold"), anchor="w").pack(fill=tk.X)
                tk.Frame(box, height=1, bg=BORDER).pack(fill=tk.X, pady=(7, 0))

            elif kind == "p":
                lbl = tk.Label(parent, text=payload, bg=BG_APP, fg=TEXT,
                               font=F_BODY, justify="left", anchor="w")
                lbl.pack(fill=tk.X, padx=pad, pady=(0, 9))
                wrapped(lbl, 2 * pad)

            elif kind == "ol":
                for i, step in enumerate(payload, 1):
                    row = tk.Frame(parent, bg=BG_APP)
                    row.pack(fill=tk.X, padx=pad, pady=3)
                    tk.Label(row, text="%d." % i, bg=BG_APP, fg=ACCENT, font=F_LABEL,
                             width=3, anchor="nw").pack(side=tk.LEFT, anchor="n")
                    lbl = tk.Label(row, text=step, bg=BG_APP, fg=TEXT, font=F_BODY,
                                   justify="left", anchor="w")
                    lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    wrapped(lbl, 2 * pad + self.GUIDE_STEP_W)

            elif kind == "ul":
                for term, detail in payload:
                    row = tk.Frame(parent, bg=BG_APP)
                    row.pack(fill=tk.X, padx=pad, pady=(4, 9))
                    lbl_term = tk.Label(row, text="\u2022  " + term, bg=BG_APP, fg=TEXT,
                                        font=(FONT, 10, "bold"), justify="left", anchor="w")
                    lbl_term.pack(fill=tk.X)
                    lbl_detail = tk.Label(row, text=detail, bg=BG_APP, fg=TEXT_DIM,
                                          font=F_SMALL, justify="left", anchor="w")
                    lbl_detail.pack(fill=tk.X, padx=(self.GUIDE_DETAIL_IN, 0), pady=(2, 0))
                    wrapped(lbl_term, 2 * pad)
                    wrapped(lbl_detail, 2 * pad + self.GUIDE_DETAIL_IN)

            elif kind == "kbd":
                for keys, action in payload:
                    row = tk.Frame(parent, bg=BG_APP)
                    row.pack(fill=tk.X, padx=pad, pady=3)
                    tk.Label(row, text=keys, bg=BG_ELEV, fg=TEXT, font=F_SMALL,
                             width=11, padx=8, pady=4, highlightbackground=BORDER,
                             highlightthickness=1).pack(side=tk.LEFT)
                    tk.Label(row, text=action, bg=BG_APP, fg=TEXT_DIM, font=F_BODY,
                             anchor="w").pack(side=tk.LEFT, padx=(14, 0))

    def _reflow_guide(self, width):
        """Rewrap the guide's text to the window's current width."""
        for label, chrome in self._guide_wraps:
            if label.winfo_exists():
                label.configure(wraplength=max(180, width - chrome - 18))

    def _bind_wheel(self, widget, handler):
        """Bind wheel scrolling on a widget and everything inside it."""
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            widget.bind(sequence, handler)
        for child in widget.winfo_children():
            self._bind_wheel(child, handler)

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

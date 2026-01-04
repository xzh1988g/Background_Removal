import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import cv2
import numpy as np

class MagicRemover:
    def __init__(self, root):
        self.root = root
        
        # ========================================================
        # Localization Configuration
        # ========================================================
        
        # 1. English Dictionary
        self.EN_TEXT = {
            "title": "MagicRemover v5.1 (Resize on Export)",
            "btn_open": "📂 Open Image",
            "btn_save": "💾 Save Result",
            "btn_reset": "🔄 Reset All",
            "label_tol": "Tolerance:",
            "mode_pick": "🖌️ Pick Mode",
            "mode_move": "✋ Move Mode",
            "mode_hint": "(Scroll to Zoom, Drag to Move)",
            "area_preview": "Result Preview (Synced)",
            "area_hist": "History",
            "hist_item_text": "Color Removed",
            "msg_error": "Error",
            "msg_success": "Success",
            "msg_saved": "Image saved successfully",
            # New Resize UI Texts
            "resize_title": "Export Settings",
            "resize_opt_orig": "Original Size",
            "resize_opt_custom": "Custom Size",
            "resize_lbl_w": "Width (px):",
            "resize_lbl_h": "Height (px):",
            "resize_chk_ratio": "Lock Aspect Ratio",
            "btn_confirm": "OK",
            "btn_cancel": "Cancel"
        }

        # 2. Chinese Dictionary
        self.CN_TEXT = {
            "title": "MagicRemover v5.1 (支持导出缩放)",
            "btn_open": "📂 打开图片",
            "btn_save": "💾 保存结果",
            "btn_reset": "🔄 全部重置",
            "label_tol": "容差值:",
            "mode_pick": "🖌️ 取色模式",
            "mode_move": "✋ 移动模式",
            "mode_hint": "(滚轮缩放，按住拖拽移动)",
            "area_preview": "最终结果预览 (视图同步)",
            "area_hist": "操作历史",
            "hist_item_text": "去除颜色",
            "msg_error": "错误",
            "msg_success": "成功",
            "msg_saved": "图片保存成功",
            # 新增调整大小文本
            "resize_title": "导出设置",
            "resize_opt_orig": "原始尺寸",
            "resize_opt_custom": "自定义尺寸",
            "resize_lbl_w": "宽度 (px):",
            "resize_lbl_h": "高度 (px):",
            "resize_chk_ratio": "锁定长宽比",
            "btn_confirm": "确认",
            "btn_cancel": "取消"
        }

        # --------------------------------------------------------
        # [Config: Active Language]
        # --------------------------------------------------------
        
        # self.ui_text = self.EN_TEXT  # <--- Active: English
        self.ui_text = self.CN_TEXT  # <--- Active: Chinese

        # ========================================================

        self.root.title(self.ui_text["title"])
        self.root.geometry("1400x850")
        
        # --- Core State Data ---
        self.original_cv = None     
        self.actions = []           
        self.action_counter = 0     
        self.final_cv_result = None 
        
        # --- View Control Parameters ---
        self.mode = "pick"          
        self.scale_factor = 1.0     
        self.offset_x = 0.0         
        self.offset_y = 0.0         
        self.last_mouse_x = 0       
        self.last_mouse_y = 0       
        
        self.tolerance = 40         

        self.setup_ui()

    def setup_ui(self):
        # --- Top Control Bar ---
        top_frame = tk.Frame(self.root, pady=8, bg="#f5f5f5", relief="raised", bd=1)
        top_frame.pack(fill=tk.X)

        tk.Button(top_frame, text=self.ui_text["btn_open"], command=self.upload_image, bg="#ddd", width=12).pack(side=tk.LEFT, padx=10)
        
        tk.Label(top_frame, text=self.ui_text["label_tol"], bg="#f5f5f5").pack(side=tk.LEFT, padx=5)
        self.scale_tol = tk.Scale(top_frame, from_=0, to=150, orient=tk.HORIZONTAL, command=self.update_last_action_tolerance, length=150, bg="#f5f5f5")
        self.scale_tol.set(self.tolerance)
        self.scale_tol.pack(side=tk.LEFT)
        
        tk.Button(top_frame, text=self.ui_text["btn_reset"], command=self.reset_all, bg="#FF9800", fg="white").pack(side=tk.RIGHT, padx=10)
        tk.Button(top_frame, text=self.ui_text["btn_save"], command=self.save_image, bg="#4CAF50", fg="white", font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=10)

        # --- Main Workspace ---
        main_pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg="#ccc", sashwidth=4)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # 1. Left Panel
        frame_left = tk.Frame(main_pane, bg="#333")
        main_pane.add(frame_left, stretch="always", width=600)

        tool_bar = tk.Frame(frame_left, bg="#444", pady=5)
        tool_bar.pack(fill=tk.X)
        
        self.btn_pick = tk.Button(tool_bar, text=self.ui_text["mode_pick"], command=lambda: self.set_mode("pick"), 
                                  bg="#666", fg="white", relief="sunken", width=12)
        self.btn_pick.pack(side=tk.LEFT, padx=5)
        
        self.btn_move = tk.Button(tool_bar, text=self.ui_text["mode_move"], command=lambda: self.set_mode("move"), 
                                  bg="#444", fg="white", relief="raised", width=12)
        self.btn_move.pack(side=tk.LEFT, padx=5)
        
        tk.Label(tool_bar, text=self.ui_text["mode_hint"], fg="#aaa", bg="#444", font=("Arial", 8)).pack(side=tk.RIGHT, padx=10)

        self.canvas_orig = tk.Canvas(frame_left, bg="#2b2b2b", highlightthickness=0)
        self.canvas_orig.pack(fill=tk.BOTH, expand=True)
        
        self.canvas_orig.bind("<Button-1>", self.on_mouse_down)   
        self.canvas_orig.bind("<B1-Motion>", self.on_mouse_drag)  
        self.canvas_orig.bind("<MouseWheel>", self.on_zoom)
        self.canvas_orig.bind("<Button-4>", self.on_zoom)
        self.canvas_orig.bind("<Button-5>", self.on_zoom)

        # 2. Middle Panel
        frame_mid = tk.Frame(main_pane, bg="#333")
        main_pane.add(frame_mid, stretch="always", width=500)
        tk.Label(frame_mid, text=self.ui_text["area_preview"], font=("Arial", 10, "bold"), bg="#eee", pady=5).pack(fill=tk.X)
        
        self.canvas_result = tk.Canvas(frame_mid, bg="#2b2b2b", highlightthickness=0)
        self.canvas_result.pack(fill=tk.BOTH, expand=True)

        # 3. Right Panel
        self.frame_history = tk.Frame(main_pane, bg="white")
        main_pane.add(self.frame_history, stretch="never", width=280)
        
        tk.Label(self.frame_history, text=self.ui_text["area_hist"], font=("Arial", 10, "bold"), bg="#eee", pady=6).pack(fill=tk.X)
        
        self.history_canvas = tk.Canvas(self.frame_history, bg="white", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.frame_history, orient="vertical", command=self.history_canvas.yview)
        self.scrollable_frame = tk.Frame(self.history_canvas, bg="white")

        self.scrollable_frame.bind("<Configure>", lambda e: self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all")))
        self.history_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.history_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.history_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    # --- Interaction Logic ---
    def set_mode(self, mode):
        self.mode = mode
        if mode == "pick":
            self.canvas_orig.config(cursor="crosshair")
            self.btn_pick.config(bg="#666", relief="sunken")
            self.btn_move.config(bg="#444", relief="raised")
        else:
            self.canvas_orig.config(cursor="fleur")
            self.btn_pick.config(bg="#444", relief="raised")
            self.btn_move.config(bg="#666", relief="sunken")

    def on_zoom(self, event):
        if self.original_cv is None: return
        
        if event.num == 5 or event.delta < 0:
            scale_mult = 0.9 
        else:
            scale_mult = 1.1 

        new_scale = self.scale_factor * scale_mult
        if new_scale < 0.1 or new_scale > 20: return

        mouse_img_x = (event.x - self.offset_x) / self.scale_factor
        mouse_img_y = (event.y - self.offset_y) / self.scale_factor

        self.scale_factor = new_scale

        self.offset_x = event.x - (mouse_img_x * self.scale_factor)
        self.offset_y = event.y - (mouse_img_y * self.scale_factor)

        self.redraw_canvases()

    def on_mouse_down(self, event):
        if self.mode == "move":
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
        elif self.mode == "pick":
            self.handle_color_pick(event.x, event.y)

    def on_mouse_drag(self, event):
        if self.mode == "move":
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y
            
            self.offset_x += dx
            self.offset_y += dy
            
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            self.redraw_canvases()

    def handle_color_pick(self, screen_x, screen_y):
        if self.original_cv is None: return

        img_x = int((screen_x - self.offset_x) / self.scale_factor)
        img_y = int((screen_y - self.offset_y) / self.scale_factor)
        
        h, w = self.original_cv.shape[:2]
        if 0 <= img_x < w and 0 <= img_y < h:
            self.add_action(img_x, img_y, self.tolerance)

    # --- Image Processing & IO ---
    def upload_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp")])
        if not path: return
        try:
            self.original_cv = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if self.original_cv is None: raise Exception("Decode Error")
            
            if len(self.original_cv.shape) == 2:
                self.original_cv = cv2.cvtColor(self.original_cv, cv2.COLOR_GRAY2BGRA)
            elif self.original_cv.shape[2] == 3:
                self.original_cv = cv2.cvtColor(self.original_cv, cv2.COLOR_BGR2BGRA)
            
            self.reset_all()
            self.reset_view()
            self.refresh_result_data()
            self.redraw_canvases()
        except Exception as e:
            messagebox.showerror(self.ui_text["msg_error"], str(e))

    def reset_view(self):
        if self.original_cv is None: return
        h, w = self.original_cv.shape[:2]
        c_w = self.canvas_orig.winfo_width() or 600
        c_h = self.canvas_orig.winfo_height() or 500
        scale_w = c_w / w
        scale_h = c_h / h
        self.scale_factor = min(scale_w, scale_h) * 0.9 
        new_w = w * self.scale_factor
        new_h = h * self.scale_factor
        self.offset_x = (c_w - new_w) / 2
        self.offset_y = (c_h - new_h) / 2

    def redraw_canvases(self):
        if self.original_cv is None: return
        self.tk_orig = self.get_view_image(self.original_cv)
        self.canvas_orig.delete("all")
        self.canvas_orig.create_image(0, 0, anchor=tk.NW, image=self.tk_orig)
        
        if self.final_cv_result is not None:
            preview_img = self.composite_checkerboard(self.final_cv_result)
            self.tk_res = self.get_view_image(preview_img)
            self.canvas_result.delete("all")
            self.canvas_result.create_image(0, 0, anchor=tk.NW, image=self.tk_res)

    def get_view_image(self, cv_img):
        canvas_w = self.canvas_orig.winfo_width()
        canvas_h = self.canvas_orig.winfo_height()
        if canvas_w < 10: canvas_w = 600
        if canvas_h < 10: canvas_h = 500

        img_pil = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGRA2RGBA))
        orig_w, orig_h = img_pil.size
        
        new_w = int(orig_w * self.scale_factor)
        new_h = int(orig_h * self.scale_factor)
        
        if new_w <= 0 or new_h <= 0: return None
        
        resample_method = Image.Resampling.NEAREST if new_w > 2000 else Image.Resampling.BILINEAR
        img_resized = img_pil.resize((new_w, new_h), resample_method)
        
        view_img = Image.new('RGBA', (canvas_w, canvas_h), (50, 50, 50, 0))
        view_img.paste(img_resized, (int(self.offset_x), int(self.offset_y)), img_resized)
        
        return ImageTk.PhotoImage(view_img)

    def composite_checkerboard(self, img_bgra):
        h, w = img_bgra.shape[:2]
        cb = np.full((h, w, 3), 200, dtype=np.uint8)
        step = 20
        mask = ((np.indices((h, w))[0] // step) + (np.indices((h, w))[1] // step)) % 2 == 1
        cb[mask] = 255
        
        b, g, r, a = cv2.split(img_bgra)
        alpha = a.astype(float) / 255.0
        
        preview = cb.copy()
        for i in range(3):
            preview[:,:,i] = (preview[:,:,i] * (1-alpha) + np.array([b,g,r])[i] * alpha).astype(np.uint8)
            
        return cv2.cvtColor(preview, cv2.COLOR_BGR2BGRA)

    def add_action(self, x, y, tol):
        b, g, r, a = self.original_cv[y, x]
        hex_color = f'#{r:02x}{g:02x}{b:02x}'
        
        mask = self.compute_flood_mask(x, y, tol)
        
        self.action_counter += 1
        action_item = {
            'id': self.action_counter, 
            'seed': (x, y), 
            'tolerance': tol, 
            'mask': mask, 
            'color_hex': hex_color
        }
        self.actions.append(action_item)
        
        self.add_history_ui_row(action_item)
        self.refresh_result_data()
        self.redraw_canvases()

    def compute_flood_mask(self, x, y, tol):
        img_bgr = self.original_cv[:, :, :3]
        img_to_process = img_bgr.copy() 
        
        h, w = img_to_process.shape[:2]
        mask = np.zeros((h+2, w+2), np.uint8)
        flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE
        try:
            cv2.floodFill(img_to_process, mask, (x, y), (0,0,0), (tol, tol, tol), (tol, tol, tol), flags)
            return mask[1:-1, 1:-1]
        except Exception as e:
            print(f"Mask Error: {e}")
            return np.zeros((h, w), np.uint8)

    def update_last_action_tolerance(self, val):
        if not self.actions: return
        tol = int(val)
        if self.tolerance == tol: return
        self.tolerance = tol
        
        last_action = self.actions[-1]
        x, y = last_action['seed']
        new_mask = self.compute_flood_mask(x, y, tol)
        last_action['tolerance'] = tol
        last_action['mask'] = new_mask
        
        self.refresh_result_data()
        self.redraw_canvases()

    def delete_action(self, action_id, ui_row_frame):
        self.actions = [a for a in self.actions if a['id'] != action_id]
        ui_row_frame.destroy()
        self.refresh_result_data()
        self.redraw_canvases()

    def add_history_ui_row(self, action):
        row_frame = tk.Frame(self.scrollable_frame, bg="white", pady=5)
        row_frame.pack(fill=tk.X, padx=5, pady=2)
        
        tk.Label(row_frame, bg=action['color_hex'], width=6, height=1, relief="solid", bd=1).pack(side=tk.LEFT, padx=8)
        tk.Label(row_frame, text=self.ui_text["hist_item_text"], bg="white", fg="#333", font=("Arial", 10)).pack(side=tk.LEFT)
        tk.Button(row_frame, text="✖", command=lambda a_id=action['id'], f=row_frame: self.delete_action(a_id, f),
                  bg="white", fg="#999", activeforeground="red", relief="flat", bd=0).pack(side=tk.RIGHT, padx=5)
        
        tk.Frame(self.scrollable_frame, height=1, bg="#f0f0f0").pack(fill=tk.X, padx=5)

    def refresh_result_data(self):
        if self.original_cv is None: return
        h, w = self.original_cv.shape[:2]
        total_alpha_mask = np.ones((h, w), dtype=np.uint8) * 255
        for action in self.actions:
            total_alpha_mask = np.where(action['mask'] == 255, 0, total_alpha_mask)
        
        result = self.original_cv.copy()
        result[:, :, 3] = total_alpha_mask
        self.final_cv_result = result

    def reset_all(self):
        self.actions = []
        self.action_counter = 0
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.refresh_result_data()
        self.redraw_canvases()

    # --- SAVE WITH RESIZE LOGIC ---
    
    def ask_resize_dialog(self, original_h, original_w):
        """
        Pop up a dialog to ask for export dimensions.
        Returns: (width, height) tuple or None if cancelled.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title(self.ui_text["resize_title"])
        dialog.geometry("320x220")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set() # Modal dialog

        # Variables
        var_choice = tk.IntVar(value=1) # 1=Original, 2=Custom
        var_w = tk.StringVar(value=str(original_w))
        var_h = tk.StringVar(value=str(original_h))
        var_lock = tk.BooleanVar(value=True)
        
        result = {"size": None} # To store return value

        # Functions for logic
        def toggle_inputs():
            state = "normal" if var_choice.get() == 2 else "disabled"
            entry_w.config(state=state)
            entry_h.config(state=state)
            chk_lock.config(state=state)

        def on_w_change(*args):
            if var_lock.get() and var_choice.get() == 2:
                try:
                    w = int(var_w.get())
                    h = int(w * (original_h / original_w))
                    var_h.set(str(h))
                except: pass

        def on_confirm():
            if var_choice.get() == 1:
                result["size"] = (original_w, original_h)
            else:
                try:
                    w = int(var_w.get())
                    h = int(var_h.get())
                    if w > 0 and h > 0:
                        result["size"] = (w, h)
                    else: return
                except: return
            dialog.destroy()

        # UI Layout
        tk.Radiobutton(dialog, text=f"{self.ui_text['resize_opt_orig']} ({original_w}x{original_h})", 
                       variable=var_choice, value=1, command=toggle_inputs).pack(anchor="w", padx=20, pady=10)
        
        tk.Radiobutton(dialog, text=self.ui_text['resize_opt_custom'], 
                       variable=var_choice, value=2, command=toggle_inputs).pack(anchor="w", padx=20, pady=0)

        f_inputs = tk.Frame(dialog, padx=40)
        f_inputs.pack(fill="x")
        
        tk.Label(f_inputs, text=self.ui_text['resize_lbl_w']).grid(row=0, column=0, sticky="w")
        entry_w = tk.Entry(f_inputs, textvariable=var_w, width=8, state="disabled")
        entry_w.grid(row=0, column=1, padx=5, pady=2)
        var_w.trace("w", on_w_change) # Bind change event

        tk.Label(f_inputs, text=self.ui_text['resize_lbl_h']).grid(row=1, column=0, sticky="w")
        entry_h = tk.Entry(f_inputs, textvariable=var_h, width=8, state="disabled")
        entry_h.grid(row=1, column=1, padx=5, pady=2)

        chk_lock = tk.Checkbutton(f_inputs, text=self.ui_text['resize_chk_ratio'], variable=var_lock, state="disabled")
        chk_lock.grid(row=2, column=0, columnspan=2, sticky="w", pady=5)

        # Buttons
        f_btns = tk.Frame(dialog, pady=10)
        f_btns.pack(fill="x")
        tk.Button(f_btns, text=self.ui_text['btn_confirm'], command=on_confirm, bg="#4CAF50", fg="white", width=8).pack(side="right", padx=10)
        tk.Button(f_btns, text=self.ui_text['btn_cancel'], command=dialog.destroy, width=8).pack(side="right", padx=10)

        self.root.wait_window(dialog) # Wait for close
        return result["size"]

    def save_image(self):
        """Export final result to file with optional resizing."""
        if self.final_cv_result is not None:
            # 1. Ask for dimensions
            h, w = self.final_cv_result.shape[:2]
            target_size = self.ask_resize_dialog(h, w)
            
            if target_size is None: return # Cancelled

            # 2. Ask for file path
            path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
            if path:
                # 3. Resize if needed
                img_to_save = self.final_cv_result
                if target_size != (w, h):
                    # Use INTER_AREA for shrinking (better quality), LINEAR for enlarging
                    interp = cv2.INTER_AREA if (target_size[0] < w) else cv2.INTER_LINEAR
                    img_to_save = cv2.resize(img_to_save, target_size, interpolation=interp)

                # 4. Save
                cv2.imencode(".png", img_to_save)[1].tofile(path)
                messagebox.showinfo(self.ui_text["msg_success"], self.ui_text["msg_saved"])

if __name__ == "__main__":
    root = tk.Tk()
    app = MagicRemover(root)
    root.mainloop()
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import cv2
import numpy as np

class MagicRemover:
    def __init__(self, root):
        self.root = root
        self.root.title("MagicRemover v3.1 (智能实时容差)")
        self.root.geometry("1100x800")
        
        # --- 核心变量 ---
        self.original_cv = None     # 原图
        self.current_alpha_mask = None # 当前显示的蒙版
        
        # 历史记录栈 (存的是“已经固定下来”的蒙版)
        self.history_stack = []     
        
        # --- 实时调整相关的变量 ---
        self.active_click_coords = None # 最后一次点击的坐标 (x, y)
        self.mask_before_active = None  # 最后一次点击“之前”的蒙版状态
        
        self.final_cv_result = None
        self.tolerance = 40 
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0

        self.setup_ui()

    def setup_ui(self):
        top_frame = tk.Frame(self.root, pady=15, bg="#f0f0f0")
        top_frame.pack(fill=tk.X)

        btn_frame = tk.Frame(top_frame, bg="#f0f0f0")
        btn_frame.pack(side=tk.LEFT, padx=15)

        tk.Button(btn_frame, text="📂 打开图片", command=self.upload_image, bg="#ddd", width=10).pack(side=tk.LEFT, padx=2)
        
        self.btn_undo = tk.Button(btn_frame, text="↩️ 撤销", command=self.undo_action, state=tk.DISABLED, bg="#FF9800", fg="white", font=("Arial", 10, "bold"))
        self.btn_undo.pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="🔄 重置", command=self.reset_image, bg="#f44336", fg="white").pack(side=tk.LEFT, padx=2)

        param_frame = tk.Frame(top_frame, bg="#f0f0f0")
        param_frame.pack(side=tk.LEFT, padx=20)

        tk.Label(param_frame, text="选中色:", bg="#f0f0f0").pack(side=tk.LEFT)
        self.lbl_color_preview = tk.Label(param_frame, text="", bg="#FFFFFF", width=6, relief="sunken")
        self.lbl_color_preview.pack(side=tk.LEFT, padx=5)

        tk.Label(param_frame, text="实时容差:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        # command=self.update_tolerance 会在拖动时实时触发
        self.scale_tol = tk.Scale(param_frame, from_=0, to=150, orient=tk.HORIZONTAL, command=self.update_tolerance, length=200, bg="#f0f0f0")
        self.scale_tol.set(self.tolerance)
        self.scale_tol.pack(side=tk.LEFT)
        
        tk.Button(top_frame, text="💾 保存结果", command=self.save_image, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), width=10).pack(side=tk.RIGHT, padx=20)

        frame_img = tk.Frame(self.root)
        frame_img.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        frame_left = tk.Frame(frame_img)
        frame_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(frame_left, text="👇 点击去背 (点完后可拖动滑块微调)", font=("Arial", 10, "bold")).pack()
        
        self.canvas_orig = tk.Canvas(frame_left, bg="#333", cursor="crosshair")
        self.canvas_orig.pack(fill=tk.BOTH, expand=True)
        self.canvas_orig.bind("<Button-1>", self.on_click_bg) 

        frame_right = tk.Frame(frame_img)
        frame_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        tk.Label(frame_right, text="最终效果预览", font=("Arial", 10, "bold")).pack()
        self.lbl_result = tk.Label(frame_right, bg="#eee", relief="sunken")
        self.lbl_result.pack(fill=tk.BOTH, expand=True)

    def upload_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")])
        if not path: return
        try:
            self.original_cv = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if self.original_cv is None: raise Exception("读取失败")
            if self.original_cv.shape[2] == 3:
                self.original_cv = cv2.cvtColor(self.original_cv, cv2.COLOR_BGR2BGRA)
            
            h, w = self.original_cv.shape[:2]
            self.current_alpha_mask = np.ones((h, w), dtype=np.uint8) * 255
            
            # 重置所有状态
            self.history_stack = []
            self.active_click_coords = None
            self.mask_before_active = None
            
            self.update_undo_button()
            self.show_image_on_canvas()
            self.update_result_preview()
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def show_image_on_canvas(self):
        if self.original_cv is None: return
        display_img = self.apply_mask_to_image(self.original_cv, self.current_alpha_mask)
        img_rgb = cv2.cvtColor(display_img, cv2.COLOR_BGRA2RGBA)
        img_pil = Image.fromarray(img_rgb)
        
        w, h = img_pil.size
        cw, ch = 600, 600
        self.scale_factor = min(cw / w, ch / h)
        new_w, new_h = int(w * self.scale_factor), int(h * self.scale_factor)
        
        if new_w <= 0: return
        img_pil = img_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_orig = ImageTk.PhotoImage(img_pil)
        
        canvas_w = self.canvas_orig.winfo_width() or 500
        canvas_h = self.canvas_orig.winfo_height() or 500
        self.offset_x = (canvas_w - new_w) // 2
        self.offset_y = (canvas_h - new_h) // 2
        
        self.canvas_orig.delete("all")
        self.canvas_orig.create_image(self.offset_x, self.offset_y, anchor=tk.NW, image=self.tk_orig)

    def on_click_bg(self, event):
        if self.original_cv is None or self.scale_factor <= 0: return
        click_x = int((event.x - self.offset_x) / self.scale_factor)
        click_y = int((event.y - self.offset_y) / self.scale_factor)
        h, w = self.original_cv.shape[:2]
        
        if 0 <= click_x < w and 0 <= click_y < h:
            # ★★★ 关键逻辑更新 ★★★
            
            # 1. 如果之前已经有一个“活跃”的点击，先把它“提交”进历史记录
            if self.active_click_coords is not None:
                # 这里的 mask_before_active 是上上次的状态，我们要存的是上次的状态
                # 其实很简单：直接把当前的 mask 存入历史，因为它已经包含上一步的结果了
                self.history_stack.append(self.mask_before_active.copy())
            
            # 2. 只有当这是第一步操作，或者刚点了“提交”后，才需要入栈
            # 为了简化逻辑：我们每次点击新位置时，都把“当前蒙版”视为“新操作前的基准蒙版”
            self.mask_before_active = self.current_alpha_mask.copy()
            self.active_click_coords = (click_x, click_y)
            
            self.update_undo_button()
            
            # 更新颜色预览
            b, g, r, a = self.original_cv[click_y, click_x]
            self.lbl_color_preview.config(bg=f'#{r:02x}{g:02x}{b:02x}')
            
            # 3. 立即执行一次去背 (使用当前容差)
            self.perform_flood_fill(click_x, click_y, self.tolerance)

    def update_tolerance(self, val):
        self.tolerance = int(val)
        
        # ★★★ 实时响应滑块 ★★★
        # 只有当我们处于“刚点击完，还没点下一个地方”的状态时，滑块才有效
        if self.active_click_coords is not None:
            cx, cy = self.active_click_coords
            # 基于“基准蒙版”重新计算
            self.perform_flood_fill(cx, cy, self.tolerance)

    def perform_flood_fill(self, x, y, tol):
        """执行去背，输入是基于 mask_before_active"""
        if self.mask_before_active is None: return

        img_bgr = self.original_cv[:, :, :3]
        h, w = img_bgr.shape[:2]
        flood_mask = np.zeros((h+2, w+2), np.uint8)
        
        t = tol
        diff = (t, t, t)
        flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE
        
        # 计算 floodfill
        temp_img = img_bgr.copy()
        cv2.floodFill(temp_img, flood_mask, (x, y), (0,0,0), diff, diff, flags)
        flood_mask = flood_mask[1:-1, 1:-1]
        
        # ★★★ 核心：新蒙版 = 基准蒙版 - 本次计算的区域 ★★★
        # 我们不是在 current_alpha_mask 上改，而是在 mask_before_active 上改
        # 这样拖动滑块时，相当于“撤销重做”了这一步，而不是无限叠加
        self.current_alpha_mask = np.where(flood_mask == 255, 0, self.mask_before_active)
        
        self.update_result_preview()
        self.show_image_on_canvas()

    def undo_action(self):
        """撤销逻辑更新"""
        # 情况A：我有正在调整的活跃点击 -> 取消这一步，回到基准
        if self.active_click_coords is not None:
            self.current_alpha_mask = self.mask_before_active
            self.active_click_coords = None # 退出活跃状态
            self.mask_before_active = None
            # 注意：这里不用 pop history，因为活跃状态还没进 history
            
        # 情况B：没有活跃点击，但有历史记录 -> 取出上一步
        elif self.history_stack:
            prev_mask = self.history_stack.pop()
            self.current_alpha_mask = prev_mask
            
            # 撤销后，我们也需要退出活跃状态，防止逻辑混乱
            self.active_click_coords = None
            self.mask_before_active = None
            
        self.update_undo_button()
        self.update_result_preview()
        self.show_image_on_canvas()

    def reset_image(self):
        if self.original_cv is None: return
        h, w = self.original_cv.shape[:2]
        self.current_alpha_mask = np.ones((h, w), dtype=np.uint8) * 255
        self.history_stack = []
        self.active_click_coords = None
        self.mask_before_active = None
        self.update_undo_button()
        self.update_result_preview()
        self.show_image_on_canvas()

    def update_undo_button(self):
        # 只要有历史，或者当前有正在调整的步骤，都可以撤销
        can_undo = len(self.history_stack) > 0 or self.active_click_coords is not None
        if can_undo:
            # 显示更智能的提示
            txt = "↩️ 撤销"
            if self.active_click_coords:
                txt += " (当前步)"
            self.btn_undo.config(state=tk.NORMAL, text=txt)
        else:
            self.btn_undo.config(state=tk.DISABLED, text="↩️ 撤销")

    def apply_mask_to_image(self, img, mask):
        result = img.copy()
        result[:, :, 3] = mask
        return result

    def update_result_preview(self):
        if self.original_cv is None: return
        self.final_cv_result = self.apply_mask_to_image(self.original_cv, self.current_alpha_mask)
        h, w = self.final_cv_result.shape[:2]
        checkerboard = self.generate_checkerboard(h, w)
        b, g, r, a = cv2.split(self.final_cv_result)
        alpha = a.astype(float) / 255.0
        preview = checkerboard.copy()
        for i in range(3):
             preview[:,:,i] = (preview[:,:,i] * (1-alpha) + np.array([b,g,r])[i] * alpha).astype(np.uint8)
        img_pil = Image.fromarray(cv2.cvtColor(preview, cv2.COLOR_BGR2RGB))
        new_w, new_h = int(w * self.scale_factor), int(h * self.scale_factor)
        if new_w > 0:
            img_pil = img_pil.resize((new_w, new_h))
            self.tk_res = ImageTk.PhotoImage(img_pil)
            self.lbl_result.config(image=self.tk_res)

    def generate_checkerboard(self, h, w, step=20):
        board = np.full((h, w, 3), 255, dtype=np.uint8)
        for y in range(0, h, step):
            for x in range(0, w, step):
                if ((x // step) + (y // step)) % 2 == 1:
                    y_end = min(y + step, h)
                    x_end = min(x + step, w)
                    board[y:y_end, x:x_end] = (220, 220, 220)
        return board

    def save_image(self):
        if self.final_cv_result is not None:
            path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
            if path:
                is_success, buffer = cv2.imencode(".png", self.final_cv_result)
                if is_success:
                    with open(path, "wb") as f:
                        f.write(buffer)
                messagebox.showinfo("成功", "保存成功")

if __name__ == "__main__":
    root = tk.Tk()
    app = MagicRemover(root)
    root.mainloop()
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import cv2
import numpy as np

class NonAI_Remover:
    def __init__(self, root):
        self.root = root
        self.root.title("传统算法去底工具 v2.2 (棋盘格透明显示)")
        self.root.geometry("1100x750")
        
        # 变量初始化
        self.original_cv = None 
        self.processed_image = None
        self.last_click_coords = None
        self.final_cv_result = None
        
        self.tolerance = 40 
        self.display_size = (500, 500)
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0

        self.setup_ui()

    def setup_ui(self):
        # --- 顶部控制栏 ---
        top_frame = tk.Frame(self.root, pady=15, bg="#f0f0f0")
        top_frame.pack(fill=tk.X)

        tk.Button(top_frame, text="📂 打开图片", command=self.upload_image, bg="#ddd", font=("Arial", 10)).pack(side=tk.LEFT, padx=15)
        
        tk.Label(top_frame, text="选中颜色:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.lbl_color_preview = tk.Label(top_frame, text="未选择", bg="#FFFFFF", width=12, relief="sunken")
        self.lbl_color_preview.pack(side=tk.LEFT, padx=5)

        tk.Label(top_frame, text="容差范围:", bg="#f0f0f0").pack(side=tk.LEFT, padx=(20, 5))
        self.scale_tol = tk.Scale(top_frame, from_=0, to=150, orient=tk.HORIZONTAL, command=self.update_tolerance, length=200, bg="#f0f0f0")
        self.scale_tol.set(self.tolerance)
        self.scale_tol.pack(side=tk.LEFT, padx=5)
        
        tk.Button(top_frame, text="💾 保存结果", command=self.save_image, bg="#4CAF50", fg="white", font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=20)

        # --- 图片显示区 ---
        frame_img = tk.Frame(self.root)
        frame_img.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左侧
        frame_left = tk.Frame(frame_img)
        frame_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(frame_left, text="👇 点击下方原图的背景区域", font=("Arial", 10, "bold")).pack()
        
        self.canvas_orig = tk.Canvas(frame_left, bg="#333", cursor="crosshair")
        self.canvas_orig.pack(fill=tk.BOTH, expand=True)
        self.canvas_orig.bind("<Button-1>", self.on_click_bg) 

        # 右侧
        frame_right = tk.Frame(frame_img)
        frame_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        tk.Label(frame_right, text="去底结果预览 (棋盘格=透明)", font=("Arial", 10, "bold")).pack()
        
        self.lbl_result = tk.Label(frame_right, bg="#eee", relief="sunken")
        self.lbl_result.pack(fill=tk.BOTH, expand=True)

    def upload_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")])
        if not path: return
        
        try:
            self.original_cv = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if self.original_cv is None: raise Exception("无法读取图片")
            
            # 强制添加Alpha通道
            if self.original_cv.shape[2] == 3:
                self.original_cv = cv2.cvtColor(self.original_cv, cv2.COLOR_BGR2BGRA)
            
            self.show_original()
            self.lbl_color_preview.config(bg="#FFFFFF", text="请点击背景")
            self.lbl_result.config(image='')
            self.last_click_coords = None 
            self.final_cv_result = None
            
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def show_original(self):
        if self.original_cv is None: return
        
        img_rgb = cv2.cvtColor(self.original_cv, cv2.COLOR_BGRA2RGBA)
        img_pil = Image.fromarray(img_rgb)
        
        w, h = img_pil.size
        cw, ch = 600, 600
        
        self.scale_factor = min(cw / w, ch / h)
        new_w, new_h = int(w * self.scale_factor), int(h * self.scale_factor)
        
        if new_w <= 0 or new_h <= 0: return

        img_pil = img_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_orig = ImageTk.PhotoImage(img_pil)
        
        canvas_w = self.canvas_orig.winfo_width() or 500
        canvas_h = self.canvas_orig.winfo_height() or 500
            
        self.offset_x = (canvas_w - new_w) // 2
        self.offset_y = (canvas_h - new_h) // 2
        
        self.canvas_orig.delete("all")
        self.canvas_orig.create_image(self.offset_x, self.offset_y, anchor=tk.NW, image=self.tk_orig)

    def on_click_bg(self, event):
        if self.original_cv is None: return
        if self.scale_factor <= 0: return
        
        click_x = int((event.x - self.offset_x) / self.scale_factor)
        click_y = int((event.y - self.offset_y) / self.scale_factor)
        
        h, w = self.original_cv.shape[:2]
        
        if 0 <= click_x < w and 0 <= click_y < h:
            self.last_click_coords = (click_x, click_y)
            b, g, r, a = self.original_cv[click_y, click_x]
            
            hex_color = f'#{r:02x}{g:02x}{b:02x}'
            text_color = "white" if (int(r)+int(g)+int(b))/3 < 128 else "black"
            self.lbl_color_preview.config(bg=hex_color, text=hex_color, fg=text_color)
            
            self.remove_bg_logic(click_x, click_y)

    def update_tolerance(self, val):
        self.tolerance = int(val)
        if hasattr(self, 'last_click_coords') and self.last_click_coords:
            self.remove_bg_logic(self.last_click_coords[0], self.last_click_coords[1])

    def remove_bg_logic(self, x, y):
        if self.original_cv is None: return

        img_temp = self.original_cv.copy()
        h, w = img_temp.shape[:2]
        
        img_bgr = img_temp[:, :, :3].copy()
        mask = np.zeros((h+2, w+2), np.uint8)
        
        t = self.tolerance
        diff = (t, t, t)
        
        flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE
        
        try:
            cv2.floodFill(img_bgr, mask, (x, y), (0,0,0), diff, diff, flags)
        except Exception:
            return
            
        mask = mask[1:-1, 1:-1]
        img_temp[:, :, 3] = np.where(mask == 255, 0, img_temp[:, :, 3])
        
        self.final_cv_result = img_temp
        self.display_result(img_temp)

    def generate_checkerboard(self, h, w, step=20):
        """生成棋盘格背景"""
        board = np.full((h, w, 3), 255, dtype=np.uint8) # 白色底
        # 简单的双重循环生成格子 (为了可读性，虽然稍慢但在预览图尺寸下很快)
        # 绘制浅灰色的格子
        for y in range(0, h, step):
            for x in range(0, w, step):
                if ((x // step) + (y // step)) % 2 == 1:
                    y_end = min(y + step, h)
                    x_end = min(x + step, w)
                    board[y:y_end, x:x_end] = (220, 220, 220) # 浅灰色
        return board

    def display_result(self, cv_img):
        h, w = cv_img.shape[:2]
        
        # ★★★ 核心修改：生成棋盘格背景代替纯色背景 ★★★
        preview_bg = self.generate_checkerboard(h, w)
        
        # Alpha混合
        b, g, r, a = cv2.split(cv_img)
        alpha = a.astype(float) / 255.0
        
        b = (b * alpha + preview_bg[:,:,0] * (1-alpha)).astype(np.uint8)
        g = (g * alpha + preview_bg[:,:,1] * (1-alpha)).astype(np.uint8)
        r = (r * alpha + preview_bg[:,:,2] * (1-alpha)).astype(np.uint8)
        
        merged = cv2.merge([b, g, r])
        img_pil = Image.fromarray(cv2.cvtColor(merged, cv2.COLOR_BGR2RGB))
        
        new_w = int(img_pil.width * self.scale_factor)
        new_h = int(img_pil.height * self.scale_factor)
        
        if new_w > 0 and new_h > 0:
            img_pil = img_pil.resize((new_w, new_h))
            self.tk_res = ImageTk.PhotoImage(img_pil)
            self.lbl_result.config(image=self.tk_res)

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
    app = NonAI_Remover(root)
    root.mainloop()
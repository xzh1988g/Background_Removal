import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import cv2
import numpy as np

class MagicRemover:
    def __init__(self, root):
        self.root = root
        self.root.title("MagicRemover v5.0 (缩放移动 + 工具模式)")
        self.root.geometry("1400x850")
        
        # --- 核心数据 ---
        self.original_cv = None     
        self.actions = []           
        self.action_counter = 0     
        self.final_cv_result = None
        
        # --- 视图控制变量 ---
        self.mode = "pick"          # 当前模式: "pick" (取色) 或 "move" (移动)
        self.scale_factor = 1.0     # 缩放比例
        self.offset_x = 0.0         # X轴偏移
        self.offset_y = 0.0         # Y轴偏移
        self.last_mouse_x = 0       # 拖拽时的临时变量
        self.last_mouse_y = 0
        
        # 默认容差
        self.tolerance = 40

        self.setup_ui()

    def setup_ui(self):
        # 1. 顶部主控制栏 (打开/保存/容差)
        top_frame = tk.Frame(self.root, pady=8, bg="#f5f5f5", relief="raised", bd=1)
        top_frame.pack(fill=tk.X)

        tk.Button(top_frame, text="📂 打开图片", command=self.upload_image, bg="#ddd", width=10).pack(side=tk.LEFT, padx=10)
        
        # 容差条
        tk.Label(top_frame, text="容差:", bg="#f5f5f5").pack(side=tk.LEFT, padx=5)
        self.scale_tol = tk.Scale(top_frame, from_=0, to=150, orient=tk.HORIZONTAL, command=self.update_last_action_tolerance, length=150, bg="#f5f5f5")
        self.scale_tol.set(self.tolerance)
        self.scale_tol.pack(side=tk.LEFT)
        
        tk.Button(top_frame, text="🔄 重置", command=self.reset_all, bg="#FF9800", fg="white").pack(side=tk.RIGHT, padx=10)
        tk.Button(top_frame, text="💾 保存", command=self.save_image, bg="#4CAF50", fg="white", font=("bold")).pack(side=tk.RIGHT, padx=10)

        # --- 主体区域 ---
        main_pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg="#ccc", sashwidth=4)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # === 左侧：原图操作区 ===
        frame_left = tk.Frame(main_pane, bg="#333")
        main_pane.add(frame_left, stretch="always", width=600)

        # >> 左侧工具栏 (新增) <<
        tool_bar = tk.Frame(frame_left, bg="#444", pady=5)
        tool_bar.pack(fill=tk.X)
        
        # 模式切换按钮 (使用 Emoji 模拟图标)
        self.btn_pick = tk.Button(tool_bar, text="🖌️ 取色模式", command=lambda: self.set_mode("pick"), 
                                  bg="#666", fg="white", relief="sunken", width=12)
        self.btn_pick.pack(side=tk.LEFT, padx=5)
        
        self.btn_move = tk.Button(tool_bar, text="✋ 移动模式", command=lambda: self.set_mode("move"), 
                                  bg="#444", fg="white", relief="raised", width=12)
        self.btn_move.pack(side=tk.LEFT, padx=5)
        
        tk.Label(tool_bar, text="(滚轮缩放，移动模式下拖拽)", fg="#aaa", bg="#444", font=("Arial", 8)).pack(side=tk.RIGHT, padx=10)

        # 画布
        self.canvas_orig = tk.Canvas(frame_left, bg="#2b2b2b", highlightthickness=0)
        self.canvas_orig.pack(fill=tk.BOTH, expand=True)
        
        # === 绑定鼠标事件 ===
        self.canvas_orig.bind("<Button-1>", self.on_mouse_down)   # 点击/开始拖拽
        self.canvas_orig.bind("<B1-Motion>", self.on_mouse_drag)  # 拖拽中
        self.canvas_orig.bind("<ButtonRelease-1>", self.on_mouse_up) # 释放
        # 绑定滚轮 (Windows用 <MouseWheel>, Linux用 <Button-4>/<Button-5>)
        self.canvas_orig.bind("<MouseWheel>", self.on_zoom) 
        self.canvas_orig.bind("<Button-4>", self.on_zoom)
        self.canvas_orig.bind("<Button-5>", self.on_zoom)

        # === 中间：结果预览 ===
        frame_mid = tk.Frame(main_pane, bg="#333")
        main_pane.add(frame_mid, stretch="always", width=500)
        tk.Label(frame_mid, text="最终结果预览 (同步视角)", font=("Arial", 10, "bold"), bg="#eee", pady=5).pack(fill=tk.X)
        
        self.canvas_result = tk.Canvas(frame_mid, bg="#2b2b2b", highlightthickness=0)
        self.canvas_result.pack(fill=tk.BOTH, expand=True)

        # === 右侧：历史记录 ===
        self.frame_history = tk.Frame(main_pane, bg="white")
        main_pane.add(self.frame_history, stretch="never", width=280)
        
        tk.Label(self.frame_history, text="去色记录", font=("Arial", 10, "bold"), bg="#eee", pady=6).pack(fill=tk.X)
        
        self.history_canvas = tk.Canvas(self.frame_history, bg="white", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.frame_history, orient="vertical", command=self.history_canvas.yview)
        self.scrollable_frame = tk.Frame(self.history_canvas, bg="white")

        self.scrollable_frame.bind("<Configure>", lambda e: self.history_canvas.configure(scrollregion=self.history_canvas.bbox("all")))
        self.history_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.history_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.history_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    # --- 模式切换逻辑 ---
    def set_mode(self, mode):
        self.mode = mode
        if mode == "pick":
            self.canvas_orig.config(cursor="crosshair") # 取色用十字准星
            self.btn_pick.config(bg="#666", relief="sunken") # 按钮按下状态
            self.btn_move.config(bg="#444", relief="raised")
        else:
            self.canvas_orig.config(cursor="fleur") # 移动用移动图标
            self.btn_pick.config(bg="#444", relief="raised")
            self.btn_move.config(bg="#666", relief="sunken")

    # --- 鼠标交互逻辑 (核心) ---
    def on_zoom(self, event):
        """处理滚轮缩放"""
        if self.original_cv is None: return
        
        # 滚轮判定：Windows delta, Linux num
        if event.num == 5 or event.delta < 0:
            scale_mult = 0.9 # 缩小
        else:
            scale_mult = 1.1 # 放大

        # 限制缩放范围
        new_scale = self.scale_factor * scale_mult
        if new_scale < 0.1 or new_scale > 20: return

        # === 核心算法：以鼠标为中心缩放 ===
        # 1. 计算鼠标当前在图片上的相对位置 (Mouse_Image_X)
        # 公式: Screen_X = Image_X * Scale + Offset
        # 所以: Image_X = (Screen_X - Offset) / Scale
        mouse_img_x = (event.x - self.offset_x) / self.scale_factor
        mouse_img_y = (event.y - self.offset_y) / self.scale_factor

        # 2. 更新缩放比例
        self.scale_factor = new_scale

        # 3. 反推新的 Offset，使得 Mouse_Image_X 在屏幕上的位置不变
        # New_Offset = Screen_X - (Image_X * New_Scale)
        self.offset_x = event.x - (mouse_img_x * self.scale_factor)
        self.offset_y = event.y - (mouse_img_y * self.scale_factor)

        self.redraw_canvases()

    def on_mouse_down(self, event):
        if self.mode == "move":
            # 记录拖拽起始点
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
        elif self.mode == "pick":
            # 执行取色逻辑
            self.handle_color_pick(event.x, event.y)

    def on_mouse_drag(self, event):
        if self.mode == "move":
            # 计算位移差
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y
            
            self.offset_x += dx
            self.offset_y += dy
            
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            self.redraw_canvases()

    def on_mouse_up(self, event):
        pass # 暂时不需要

    def handle_color_pick(self, screen_x, screen_y):
        """将屏幕坐标转换为图片坐标，并执行去色"""
        if self.original_cv is None: return

        # 1. 减去偏移量 (offset)
        # 2. 除以缩放比例 (scale)
        # 3. 强制转为整数 (int)
        img_x = int((screen_x - self.offset_x) / self.scale_factor)
        img_y = int((screen_y - self.offset_y) / self.scale_factor)
        
        h, w = self.original_cv.shape[:2]
        
        # 检查是否点击在图片范围内
        if 0 <= img_x < w and 0 <= img_y < h:
            print(f"点击坐标: {img_x}, {img_y}") # 控制台会打印坐标，方便你确认点击是否生效
            self.add_action(img_x, img_y, self.tolerance)

    # --- 图像处理与渲染 ---
    def upload_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp")])
        if not path: return
        try:
            # 读取包含透明通道的图片
            self.original_cv = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
            if self.original_cv is None: raise Exception("读取失败")
            
            # 统一转为 BGRA
            if len(self.original_cv.shape) == 2: # 灰度
                self.original_cv = cv2.cvtColor(self.original_cv, cv2.COLOR_GRAY2BGRA)
            elif self.original_cv.shape[2] == 3: # BGR
                self.original_cv = cv2.cvtColor(self.original_cv, cv2.COLOR_BGR2BGRA)
            
            self.reset_all() # 重置历史
            self.reset_view() # 重置视图(居中)
            self.refresh_result_data() # 计算结果
            self.redraw_canvases() # 绘制
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def reset_view(self):
        """重置为“适应屏幕”大小"""
        if self.original_cv is None: return
        h, w = self.original_cv.shape[:2]
        
        # 获取画布尺寸 (如果没有显示出来，默认给个500)
        c_w = self.canvas_orig.winfo_width() or 600
        c_h = self.canvas_orig.winfo_height() or 500
        
        scale_w = c_w / w
        scale_h = c_h / h
        self.scale_factor = min(scale_w, scale_h) * 0.9 # 留一点边距
        
        new_w = w * self.scale_factor
        new_h = h * self.scale_factor
        self.offset_x = (c_w - new_w) / 2
        self.offset_y = (c_h - new_h) / 2

    def redraw_canvases(self):
        """统一绘制左侧和中间的画布 (应用缩放和偏移)"""
        if self.original_cv is None: return
        
        # 1. 绘制左侧原图
        self.tk_orig = self.get_view_image(self.original_cv)
        self.canvas_orig.delete("all")
        self.canvas_orig.create_image(0, 0, anchor=tk.NW, image=self.tk_orig) # 这里用 (0,0) 因为图片已经处理过了
        
        # 2. 绘制中间结果图 (如果存在)
        if self.final_cv_result is not None:
            # 叠加棋盘格背景以便观察透明度
            preview_img = self.composite_checkerboard(self.final_cv_result)
            self.tk_res = self.get_view_image(preview_img)
            self.canvas_result.delete("all")
            self.canvas_result.create_image(0, 0, anchor=tk.NW, image=self.tk_res)

    def get_view_image(self, cv_img):
        """
        核心渲染函数：根据当前的 scale 和 offset，截取并缩放图片
        方法：创建一个和 Canvas 一样大的黑色底图，把缩放后的图片贴上去
        """
        canvas_w = self.canvas_orig.winfo_width()
        canvas_h = self.canvas_orig.winfo_height()
        
        # 如果窗口太小，给默认值
        if canvas_w < 10: canvas_w = 600
        if canvas_h < 10: canvas_h = 500

        # 转为 PIL
        img_pil = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGRA2RGBA))
        orig_w, orig_h = img_pil.size
        
        # 计算缩放后的尺寸
        new_w = int(orig_w * self.scale_factor)
        new_h = int(orig_h * self.scale_factor)
        
        if new_w <= 0 or new_h <= 0: return None
        
        # 缩放图片 (性能优化：如果是巨大的图片，应该先 crop 再 resize，这里简化为先 resize)
        # 为了流畅度，大图可以使用 Nearest，小图用 Bilinear
        resample_method = Image.Resampling.NEAREST if new_w > 2000 else Image.Resampling.BILINEAR
        img_resized = img_pil.resize((new_w, new_h), resample_method)
        
        # 创建画布背景 (透明)
        view_img = Image.new('RGBA', (canvas_w, canvas_h), (50, 50, 50, 0))
        
        # 粘贴图片 (offset 决定粘贴位置)
        paste_x = int(self.offset_x)
        paste_y = int(self.offset_y)
        
        view_img.paste(img_resized, (paste_x, paste_y), img_resized)
        
        return ImageTk.PhotoImage(view_img)

    def composite_checkerboard(self, img_bgra):
        """给结果图加上棋盘格背景"""
        h, w = img_bgra.shape[:2]
        # 生成小棋盘格
        cb = np.full((h, w, 3), 200, dtype=np.uint8) # 浅灰
        step = 20
        # 快速生成棋盘格的技巧
        mask = ((np.indices((h, w))[0] // step) + (np.indices((h, w))[1] // step)) % 2 == 1
        cb[mask] = 255 # 白色
        
        b, g, r, a = cv2.split(img_bgra)
        alpha = a.astype(float) / 255.0
        
        preview = cb.copy()
        for i in range(3):
            preview[:,:,i] = (preview[:,:,i] * (1-alpha) + np.array([b,g,r])[i] * alpha).astype(np.uint8)
            
        # 补回 Alpha 通道 (为了统一处理函数)
        return cv2.cvtColor(preview, cv2.COLOR_BGR2BGRA)

    # --- 历史记录逻辑 (保留上一版) ---
    def add_action(self, x, y, tol):
        b, g, r, a = self.original_cv[y, x]
        hex_color = f'#{r:02x}{g:02x}{b:02x}'
        mask = self.compute_flood_mask(x, y, tol)
        
        self.action_counter += 1
        action_item = {'id': self.action_counter, 'seed': (x, y), 'tolerance': tol, 'mask': mask, 'color_hex': hex_color}
        self.actions.append(action_item)
        
        self.add_history_ui_row(action_item)
        self.refresh_result_data()
        self.redraw_canvases()

    def compute_flood_mask(self, x, y, tol):
        # 取出 BGR 通道 (因为 floodFill 不支持 Alpha 通道)
        img_bgr = self.original_cv[:, :, :3]
        
        # 【关键修复】必须使用 copy()！
        # 1. floodFill 会修改原图，我们不能破坏 original_cv
        # 2. 也是为了确保内存连续性，避免 OpenCV 报错
        img_to_process = img_bgr.copy() 
        
        h, w = img_to_process.shape[:2]
        mask = np.zeros((h+2, w+2), np.uint8)
        
        # floodFill 的参数设置
        flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY | cv2.FLOODFILL_FIXED_RANGE
        
        try:
            # 注意：这里传入的是 img_to_process (副本)
            cv2.floodFill(img_to_process, mask, (x, y), (0,0,0), (tol, tol, tol), (tol, tol, tol), flags)
            return mask[1:-1, 1:-1]
        except Exception as e:
            print(f"Mask Error: {e}") # 打印错误方便调试
            return np.zeros((h, w), np.uint8)

    def update_last_action_tolerance(self, val):
        if not self.actions: return
        tol = int(val)
        if self.tolerance == tol: return # 避免重复计算
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
        """UI: 历史记录行 (简化版)"""
        row_frame = tk.Frame(self.scrollable_frame, bg="white", pady=5)
        row_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # 色块
        tk.Label(row_frame, bg=action['color_hex'], width=6, height=1, relief="solid", bd=1).pack(side=tk.LEFT, padx=8)
        # 文字
        tk.Label(row_frame, text="去除该颜色", bg="white", fg="#333", font=("Arial", 10)).pack(side=tk.LEFT)
        # 删除按钮
        tk.Button(row_frame, text="✖", command=lambda a_id=action['id'], f=row_frame: self.delete_action(a_id, f),
                  bg="white", fg="#999", activeforeground="red", relief="flat", bd=0).pack(side=tk.RIGHT, padx=5)
        
        tk.Frame(self.scrollable_frame, height=1, bg="#f0f0f0").pack(fill=tk.X, padx=5)

    def refresh_result_data(self):
        """只计算数据，不负责绘制"""
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

    def save_image(self):
        if self.final_cv_result is not None:
            path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
            if path:
                cv2.imencode(".png", self.final_cv_result)[1].tofile(path)
                messagebox.showinfo("成功", "保存成功")

if __name__ == "__main__":
    root = tk.Tk()
    app = MagicRemover(root)
    root.mainloop()
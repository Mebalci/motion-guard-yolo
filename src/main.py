import sys
import os

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_THREADING_LAYER"] = "GNU"


def _get_app_base_dir() -> str:
    """Uygulamanın çalıştığı temel dizin. Frozen ise _MEIPASS, değilse repo kökü."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.abspath("."))
    # src/main.py -> repo kökü = src'nin bir üstü
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def resource_path(relative_path: str) -> str:
    """
    Asset dosyalarını (assets/...) hem dev hem PyInstaller'da doğru bul.
    relative_path örn: "Mebalci.png", "dilili.mp3", "yolov8n.pt"
    """
    base = _get_app_base_dir()

    # 1) Önce assets klasöründe ara
    p_assets = os.path.join(base, "assets", relative_path)
    if os.path.exists(p_assets):
        return p_assets

    # 2) Frozen senaryoda bazen direkt base içine de atılabiliyor (eski build)
    p_root = os.path.join(base, relative_path)
    if os.path.exists(p_root):
        return p_root

    # 3) fallback: repo kökü çalışma dizini
    p_cwd_assets = os.path.join(os.getcwd(), "assets", relative_path)
    if os.path.exists(p_cwd_assets):
        return p_cwd_assets

    return p_assets  # en azından denenen path'i döndür


# --- PyInstaller ile derlenmişse Torch DLL'lerini PATH'e ekle ---
if getattr(sys, "frozen", False):
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))

    candidates = [
        os.path.join(base, "_internal", "torch", "lib"),
        os.path.join(base, "torch", "lib"),
        os.path.join(base, "_internal", "torch_lib"),
        os.path.join(base, "torch_lib"),
        os.path.join(base, "torch", "lib"),  # tekrar ama sorun değil
        base,
        os.path.join(base, "_internal"),
    ]

    torch_lib = next((p for p in candidates if os.path.isdir(p) and p.endswith(os.path.join("torch", "lib"))), None)
    print("MEIPASS:", base)
    print("TORCH_LIB_SELECTED:", torch_lib)

    # tüm candidate dizinlerini PATH'e ekle (Windows DLL resolve için daha sağlam)
    for path in candidates:
        if os.path.isdir(path):
            os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
            try:
                os.add_dll_directory(path)
            except Exception:
                pass


import tkinter as tk
import customtkinter as ctk
import cv2
import time
import numpy as np
from PIL import Image, ImageTk
from ultralytics import YOLO
import pygame

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class SecurityApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("🛡️ Motion Guard - MEBALCI AI")
        self.geometry("1150x820")
        self.minsize(1100, 780)

        self.cap = None
        self.is_running = False
        self.is_monitoring = False

        # ROI şekli: rect | circle_diameter | ellipse | free
        self.roi_shape = "rect"

        self.roi_rect = None
        self.roi_circle = None
        self.roi_ellipse = None
        self.roi_free = None

        self.temp_start = None
        self.freehand_points = []
        self.is_freehand_drawing = False

        self.frame_width = 820
        self.frame_height = 610
        self.camera_index = 0

        print("YOLOv8 Modeli Yükleniyor...")
        self.model = YOLO(resource_path("yolov8n.pt"))

        self.target_mode = "both"
        self.target_classes = [0, 2]

        pygame.mixer.init()
        self.alarm_loaded = False
        try:
            pygame.mixer.music.load(resource_path("dilili.mp3"))
            self.alarm_loaded = True
        except Exception as e:
            print(f"Ses yükleme hatası: {e}")

        self.setup_ui()

    def setup_ui(self):
        self.sidebar = ctk.CTkFrame(self, width=285, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)

        # Logo
        logo_path = resource_path("Mebalci.png")
        if os.path.exists(logo_path):
            try:
                from PIL import Image as PILImage
                logo_image = PILImage.open(logo_path)
                self.logo_ctk = ctk.CTkImage(light_image=logo_image, dark_image=logo_image, size=(170, 170))
                self.logo_img_label = ctk.CTkLabel(self.sidebar, image=self.logo_ctk, text="")
                self.logo_img_label.pack(pady=(18, 6))
            except Exception as e:
                print(f"Logo yüklenirken teknik hata: {e}")
        else:
            print("Logo bulunamadı:", logo_path)

        self.logo_label = ctk.CTkLabel(self.sidebar, text="MEBALCI AI", font=ctk.CTkFont(size=22, weight="bold"))
        self.logo_label.pack(padx=18, pady=(0, 10))

        self.badge_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.badge_frame.pack(padx=18, pady=(0, 12), fill="x")

        self.badge_cam = ctk.CTkLabel(self.badge_frame, text="📷 Kamera: Kapalı", text_color="gray")
        self.badge_cam.pack(anchor="w")

        self.badge_guard = ctk.CTkLabel(self.badge_frame, text="🛡️ Takip: Kapalı", text_color="gray")
        self.badge_guard.pack(anchor="w")

        self.sep1 = ctk.CTkFrame(self.sidebar, height=2, fg_color="#2a2a2a")
        self.sep1.pack(fill="x", padx=18, pady=(6, 12))

        # Hedef seçimi
        self.lbl_target = ctk.CTkLabel(
            self.sidebar, text="🎯 Tetikleme Hedefi",
            text_color="white", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.lbl_target.pack(padx=18, pady=(0, 6), anchor="w")

        self.target_option = ctk.CTkOptionMenu(
            self.sidebar,
            values=["İnsan", "Araba", "İkisi"],
            command=self.on_target_change
        )
        self.target_option.set("İkisi")
        self.target_option.pack(padx=18, pady=(0, 12), fill="x")

        # ROI şekli
        self.lbl_roi_shape = ctk.CTkLabel(
            self.sidebar, text="⭕ Tarama Alanı Şekli",
            text_color="white", font=ctk.CTkFont(size=14, weight="bold")
        )
        self.lbl_roi_shape.pack(padx=18, pady=(0, 6), anchor="w")

        self.roi_shape_option = ctk.CTkOptionMenu(
            self.sidebar,
            values=["Dikdörtgen", "Daire (Çap)", "Elips", "Serbest Çizim"],
            command=self.on_roi_shape_change
        )
        self.roi_shape_option.set("Dikdörtgen")
        self.roi_shape_option.pack(padx=18, pady=(0, 12), fill="x")

        # Butonlar
        self.btn_start_cam = ctk.CTkButton(
            self.sidebar,
            text="📷 Kamerayı Başlat",
            fg_color="#2CC985",
            hover_color="#229A65",
            command=self.start_camera,
            height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.btn_start_cam.pack(padx=18, pady=(8, 10), fill="x")

        self.btn_select_roi = ctk.CTkButton(
            self.sidebar,
            text="🖱️ Alan Seçimi Yap",
            fg_color="#3B8ED0",
            hover_color="#2C6E9F",
            command=self.enable_roi_selection,
            height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_select_roi.pack(padx=18, pady=8, fill="x")
        self.btn_select_roi.configure(state="disabled")

        self.btn_start_monitor = ctk.CTkButton(
            self.sidebar,
            text="🛡️ Takibi Başlat",
            fg_color="#E04F5F",
            hover_color="#A8323E",
            command=self.toggle_monitoring,
            height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.btn_start_monitor.pack(padx=18, pady=8, fill="x")
        self.btn_start_monitor.configure(state="disabled")

        self.btn_stop_alarm = ctk.CTkButton(
            self.sidebar,
            text="🔇 ALARMI SUSTUR",
            fg_color="#F1C40F",
            hover_color="#D4AC0D",
            text_color="black",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.stop_alarm,
            height=46,
        )
        self.btn_stop_alarm.pack(padx=18, pady=(10, 12), fill="x")

        self.sep2 = ctk.CTkFrame(self.sidebar, height=2, fg_color="#2a2a2a")
        self.sep2.pack(fill="x", padx=18, pady=(4, 10))

        self.help_text = ctk.CTkLabel(
            self.sidebar,
            text="ℹ️ ROI seçimi:\n"
                 "• Dikdörtgen: sürükle-bırak\n"
                 "• Daire(Çap): sürükle-bırak (iki uç arası çap)\n"
                 "• Elips: sürükle-bırak\n"
                 "• Serbest: basılı tutup çiz → bırak\n\n"
                 "⚠️ Takip açıkken ayarlar kilitlenir.",
            justify="left",
            text_color="#bdbdbd",
        )
        self.help_text.pack(padx=18, pady=(0, 10), anchor="w")

        self.lbl_status = ctk.CTkLabel(self.sidebar, text="Durum: Bekleniyor...", text_color="gray")
        self.lbl_status.pack(padx=18, pady=(0, 14), side="bottom", anchor="w")

        # Sağ panel
        self.main_area = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_area.pack(side="right", fill="both", expand=True)

        self.canvas_frame = tk.Canvas(
            self.main_area,
            bg="#141414",
            highlightthickness=0,
            width=self.frame_width,
            height=self.frame_height,
        )
        self.canvas_frame.pack(expand=True, padx=10, pady=10)

        self.canvas_frame.bind("<Button-1>", self.on_mouse_down)
        self.canvas_frame.bind("<B1-Motion>", self.on_mouse_move)
        self.canvas_frame.bind("<ButtonRelease-1>", self.on_mouse_up)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.lock_controls(False)

    def lock_controls(self, locked: bool):
        if locked:
            self.btn_start_cam.configure(state="disabled")
            self.btn_select_roi.configure(state="disabled")
            self.target_option.configure(state="disabled")
            self.roi_shape_option.configure(state="disabled")
            self.btn_start_monitor.configure(state="normal")
            return

        self.btn_start_cam.configure(state="normal")
        self.target_option.configure(state="normal")
        self.roi_shape_option.configure(state="normal")

        self.btn_select_roi.configure(state="normal" if self.is_running else "disabled")
        self.btn_start_monitor.configure(state="normal" if (self.is_running and self.has_any_roi()) else "disabled")

    def has_any_roi(self):
        return bool(self.roi_rect or self.roi_circle or self.roi_ellipse or self.roi_free)

    def clear_all_roi(self):
        self.roi_rect = None
        self.roi_circle = None
        self.roi_ellipse = None
        self.roi_free = None
        self.temp_start = None
        self.freehand_points = []
        self.is_freehand_drawing = False

    def stop_monitoring_force(self, reason: str = ""):
        if self.is_monitoring:
            self.is_monitoring = False
            self.stop_alarm()
            self.btn_start_monitor.configure(text="🛡️ Takibi Başlat", fg_color="#E04F5F")
            self.badge_guard.configure(text="🛡️ Takip: Kapalı", text_color="gray")
            self.lock_controls(False)
            if reason:
                self.lbl_status.configure(text=reason, text_color="cyan")

    def on_target_change(self, value):
        if self.is_monitoring:
            self.stop_monitoring_force("Takip durduruldu. Hedef değiştirildi.")

        if value == "İnsan":
            self.target_mode = "person"
            self.target_classes = [0]
        elif value == "Araba":
            self.target_mode = "car"
            self.target_classes = [2]
        else:
            self.target_mode = "both"
            self.target_classes = [0, 2]

        self.lbl_status.configure(text=f"Hedef: {value}", text_color="cyan")

    def on_roi_shape_change(self, value):
        if self.is_monitoring:
            self.stop_monitoring_force("Takip durduruldu. ROI şekli değiştirildi.")

        if value == "Dikdörtgen":
            self.roi_shape = "rect"
        elif value == "Daire (Çap)":
            self.roi_shape = "circle_diameter"
        elif value == "Elips":
            self.roi_shape = "ellipse"
        else:
            self.roi_shape = "free"

        self.clear_all_roi()
        self.btn_start_monitor.configure(state="disabled")
        self.lbl_status.configure(text=f"ROI şekli: {value}. Şimdi alan seç.", text_color="cyan")
        self.lock_controls(False)

    def start_camera(self):
        if not self.is_running:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                self.lbl_status.configure(text="❌ Kamera açılmadı!", text_color="red")
                return

            self.is_running = True
            self.btn_start_cam.configure(text="⏹️ Kamerayı Durdur", fg_color="#555555")
            self.badge_cam.configure(text="📷 Kamera: Açık", text_color="#2CC985")
            self.lbl_status.configure(text="Kamera hazır. Alan seçebilirsin.", text_color="cyan")

            self.lock_controls(False)
            self.video_loop()
        else:
            self.stop_monitoring_force("Takip durduruldu. Kamera kapatılıyor...")

            self.is_running = False
            self.stop_alarm()
            if self.cap:
                self.cap.release()
                self.cap = None

            self.btn_start_cam.configure(text="📷 Kamerayı Başlat", fg_color="#2CC985")
            self.badge_cam.configure(text="📷 Kamera: Kapalı", text_color="gray")

            self.clear_all_roi()
            self.canvas_frame.delete("all")
            self.lbl_status.configure(text="Durum: Bekleniyor...", text_color="gray")

            self.lock_controls(False)

    def video_loop(self):
        if not self.is_running:
            return

        try:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.resize(frame, (self.frame_width, self.frame_height))

                if self.is_monitoring and self.has_any_roi():
                    detected, _ = self.run_detection_on_roi(frame)
                    if detected:
                        self.trigger_alarm()

                img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(img)
                imgtk = ImageTk.PhotoImage(image=img)

                self.canvas_frame.delete("all")
                self.canvas_frame.create_image(0, 0, anchor="nw", image=imgtk)
                self.canvas_frame.image = imgtk

                if not self.is_monitoring:
                    self.draw_roi_preview()

        except Exception as e:
            print("video_loop error:", e)

        self.after(10, self.video_loop)

    def enable_roi_selection(self):
        if self.is_monitoring:
            self.stop_monitoring_force("Takip durduruldu. Yeni alan seçebilirsin.")

        if not self.is_running:
            self.lbl_status.configure(text="❌ Önce kamerayı başlat!", text_color="red")
            return

        self.lbl_status.configure(text="🖱️ Ekranda bir alan çizin...", text_color="cyan")
        self.clear_all_roi()
        self.btn_start_monitor.configure(state="disabled")
        self.lock_controls(False)

    def on_mouse_down(self, event):
        if not self.is_running or self.is_monitoring:
            return

        if self.roi_shape == "free":
            self.is_freehand_drawing = True
            self.freehand_points = [(event.x, event.y)]
            self.temp_start = None
        else:
            self.temp_start = (event.x, event.y)

    def on_mouse_move(self, event):
        if not self.is_running or self.is_monitoring:
            return

        if self.roi_shape == "free" and self.is_freehand_drawing:
            if not self.freehand_points:
                self.freehand_points = [(event.x, event.y)]
                return

            lx, ly = self.freehand_points[-1]
            if (event.x - lx) ** 2 + (event.y - ly) ** 2 >= 25:  # 5px
                self.freehand_points.append((event.x, event.y))

            if len(self.freehand_points) > 2000:
                self.freehand_points = self.freehand_points[-2000:]

    def on_mouse_up(self, event):
        if not self.is_running or self.is_monitoring:
            return

        if self.roi_shape == "free":
            if not self.is_freehand_drawing:
                return
            self.is_freehand_drawing = False

            if len(self.freehand_points) < 3:
                self.freehand_points = []
                self.lbl_status.configure(text="❌ Serbest çizim için daha büyük bir alan çiz.", text_color="red")
                return

            xs = [p[0] for p in self.freehand_points]
            ys = [p[1] for p in self.freehand_points]
            x1, y1 = max(0, min(xs)), max(0, min(ys))
            x2, y2 = min(self.frame_width, max(xs)), min(self.frame_height, max(ys))

            if (x2 - x1) < 10 or (y2 - y1) < 10:
                self.freehand_points = []
                self.lbl_status.configure(text="❌ Çok küçük alan. Tekrar dene.", text_color="red")
                return

            self.roi_free = {"points": self.freehand_points[:], "bbox": (x1, y1, x2, y2)}
            self.freehand_points = []
            self.lbl_status.configure(text="✅ Alan seçildi. Takibi başlatabilirsin.", text_color="cyan")
            self.btn_start_monitor.configure(state="normal")
            self.lock_controls(False)
            return

        if not self.temp_start:
            return

        x1, y1 = self.temp_start
        x2, y2 = event.x, event.y
        self.temp_start = None

        nx1, ny1 = max(0, min(x1, x2)), max(0, min(y1, y2))
        nx2, ny2 = min(self.frame_width, max(x1, x2)), min(self.frame_height, max(y1, y2))

        if (nx2 - nx1) < 8 or (ny2 - ny1) < 8:
            self.lbl_status.configure(text="❌ Çok küçük alan. Tekrar dene.", text_color="red")
            return

        if self.roi_shape == "rect":
            self.roi_rect = (nx1, ny1, nx2, ny2)
        elif self.roi_shape == "ellipse":
            self.roi_ellipse = (nx1, ny1, nx2, ny2)
        else:
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)
            dist = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            r = int(max(6, dist / 2))
            cx = min(max(cx, 0), self.frame_width)
            cy = min(max(cy, 0), self.frame_height)
            self.roi_circle = (cx, cy, r)

        self.lbl_status.configure(text="✅ Alan seçildi. Takibi başlatabilirsin.", text_color="cyan")
        self.btn_start_monitor.configure(state="normal")
        self.lock_controls(False)

    def draw_roi_preview(self):
        if self.roi_shape == "free" and self.is_freehand_drawing and len(self.freehand_points) >= 2:
            recent = self.freehand_points[-400:]
            pts = []
            for (x, y) in recent:
                pts.extend([x, y])
            try:
                self.canvas_frame.create_line(*pts, fill="cyan", width=2)
            except Exception as e:
                print("freehand preview draw error:", e)

        if self.roi_rect:
            x1, y1, x2, y2 = self.roi_rect
            self.canvas_frame.create_rectangle(x1, y1, x2, y2, outline="cyan", width=2)

        if self.roi_circle:
            cx, cy, r = self.roi_circle
            self.canvas_frame.create_oval(cx - r, cy - r, cx + r, cy + r, outline="cyan", width=2)

        if self.roi_ellipse:
            x1, y1, x2, y2 = self.roi_ellipse
            self.canvas_frame.create_oval(x1, y1, x2, y2, outline="cyan", width=2)

        if self.roi_free:
            pts = self.roi_free["points"]
            if len(pts) >= 2:
                flat = []
                for (x, y) in pts:
                    flat.extend([x, y])
                flat.extend([pts[0][0], pts[0][1]])
                try:
                    self.canvas_frame.create_line(*flat, fill="cyan", width=2)
                except Exception as e:
                    print("freehand final preview error:", e)

    def run_detection_on_roi(self, frame):
        detected = False

        if self.roi_rect:
            x1, y1, x2, y2 = self.roi_rect
            roi = frame[y1:y2, x1:x2]
            if roi.size > 0:
                results = self.model.predict(source=roi, conf=0.5, verbose=False, classes=self.target_classes)
                detected = any(len(r.boxes) > 0 for r in results)
            cv2.rectangle(frame, (x1, y1), (x2, y2),
                          (0, 0, 255) if detected else (0, 255, 0),
                          3 if detected else 2)
            return detected, True

        if self.roi_circle:
            cx, cy, r = self.roi_circle
            x1 = max(0, cx - r)
            y1 = max(0, cy - r)
            x2 = min(self.frame_width, cx + r)
            y2 = min(self.frame_height, cy + r)

            roi = frame[y1:y2, x1:x2]
            if roi.size > 0:
                mask = np.zeros((roi.shape[0], roi.shape[1]), dtype=np.uint8)
                cv2.circle(mask, (cx - x1, cy - y1), r, 255, -1)
                roi_masked = cv2.bitwise_and(roi, roi, mask=mask)

                results = self.model.predict(source=roi_masked, conf=0.5, verbose=False, classes=self.target_classes)
                detected = any(len(r.boxes) > 0 for r in results)

            cv2.circle(frame, (cx, cy), r,
                       (0, 0, 255) if detected else (0, 255, 0),
                       3 if detected else 2)
            return detected, True

        if self.roi_ellipse:
            x1, y1, x2, y2 = self.roi_ellipse
            roi = frame[y1:y2, x1:x2]
            if roi.size > 0:
                h, w = roi.shape[:2]
                mask = np.zeros((h, w), dtype=np.uint8)
                center = (w // 2, h // 2)
                axes = (max(1, w // 2), max(1, h // 2))
                cv2.ellipse(mask, center, axes, 0, 0, 360, 255, -1)
                roi_masked = cv2.bitwise_and(roi, roi, mask=mask)

                results = self.model.predict(source=roi_masked, conf=0.5, verbose=False, classes=self.target_classes)
                detected = any(len(r.boxes) > 0 for r in results)

            cv2.ellipse(frame,
                        (int((x1 + x2) / 2), int((y1 + y2) / 2)),
                        (int((x2 - x1) / 2), int((y2 - y1) / 2)),
                        0, 0, 360,
                        (0, 0, 255) if detected else (0, 255, 0),
                        3 if detected else 2)
            return detected, True

        if self.roi_free:
            pts = self.roi_free["points"]
            x1, y1, x2, y2 = self.roi_free["bbox"]
            roi = frame[y1:y2, x1:x2]

            if roi.size > 0:
                poly = [[[px - x1, py - y1] for (px, py) in pts]]
                poly_np = np.array(poly, dtype=np.int32)

                mask = np.zeros((roi.shape[0], roi.shape[1]), dtype=np.uint8)
                cv2.fillPoly(mask, poly_np, 255)

                roi_masked = cv2.bitwise_and(roi, roi, mask=mask)

                results = self.model.predict(source=roi_masked, conf=0.5, verbose=False, classes=self.target_classes)
                detected = any(len(r.boxes) > 0 for r in results)

            color = (0, 0, 255) if detected else (0, 255, 0)
            poly_global = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [poly_global], isClosed=True, color=color, thickness=3 if detected else 2)
            return detected, True

        return False, False

    def toggle_monitoring(self):
        if not self.is_monitoring:
            if not self.is_running:
                self.lbl_status.configure(text="❌ Önce kamerayı başlat!", text_color="red")
                return
            if not self.has_any_roi():
                self.lbl_status.configure(text="❌ Önce alan seç!", text_color="red")
                return

            self.is_monitoring = True
            self.btn_start_monitor.configure(text="⛔ Takibi Durdur", fg_color="#555555")
            self.badge_guard.configure(text="🛡️ Takip: Açık", text_color="#E04F5F")
            self.lbl_status.configure(text="🛡️ GÜVENLİK AKTİF!", text_color="#E04F5F")
            self.lock_controls(True)
            return

        self.stop_monitoring_force("Takip durduruldu.")

    def trigger_alarm(self):
        if self.alarm_loaded and not pygame.mixer.music.get_busy():
            pygame.mixer.music.play(loops=-1)

    def stop_alarm(self):
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

    def on_close(self):
        self.is_running = False
        self.stop_alarm()
        if self.cap:
            self.cap.release()
        self.destroy()
        sys.exit()


if __name__ == "__main__":
    app = SecurityApp()
    app.mainloop()
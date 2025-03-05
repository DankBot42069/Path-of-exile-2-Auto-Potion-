import tkinter as tk
from tkinter import ttk, messagebox
import cv2
import pyautogui
import threading
import time
import numpy as np
import json
import os
import win32gui
from PIL import Image, ImageTk, ImageDraw
import random
import keyboard  # For global hotkey detection

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

# Default thresholds
DEFAULT_THRESHOLD_HP_LOWER = 55
DEFAULT_THRESHOLD_HP_UPPER = 65
DEFAULT_THRESHOLD_MP_LOWER = 55
DEFAULT_THRESHOLD_MP_UPPER = 65

# Default color/potion/delay
DEFAULT_COLOR_TIGHTENING = 0
DEFAULT_HEALTH_POTION_DELAY = 0.5
DEFAULT_MANA_POTION_DELAY = 0.5

# Default keys
DEFAULT_TOGGLE_KEY = "F8"
DEFAULT_PAUSE_KEY = "F9"
DEFAULT_SINGLE_SCREEN_HOTKEY = "F10"

# Default region not set
CONFIG = {}
MONITOR_SLEEP_TIME = 0.2

# Chickening defaults
DEFAULT_CHICKEN_ENABLED = False
DEFAULT_CHICKEN_THRESHOLD = 30  # HP% below which to log out quickly

# NEW: Default increase percentage when poisoned (health bar turns green)
DEFAULT_POISONED_THRESHOLD_INCREASE = 0

# For some older Pillow versions
try:
    RESAMPLE_FILTER = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE_FILTER = Image.ANTIALIAS


# ------------------------------------------------------------------------------
# HELPER FUNCTIONS ADDED (from second snippet for auto-find)
# ------------------------------------------------------------------------------
def list_windows():
    """Return a list of visible window titles."""
    windows = []
    def enum_window(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd)
            if t:
                windows.append(t)
        return True
    win32gui.EnumWindows(enum_window, None)
    return windows

def refine_template_crop(template_img, target_color="red"):
    """
    Crop a template image around the main cluster of target_color pixels,
    so that matchTemplate won't look at empty areas.
    """
    hsv = cv2.cvtColor(template_img, cv2.COLOR_BGR2HSV)
    if target_color.lower() == "red":
        lower_red1 = np.array([0, 50, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 50, 50])
        upper_red2 = np.array([180, 255, 255])
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)
    elif target_color.lower() == "blue":
        lower_blue = np.array([80, 50, 50])
        upper_blue = np.array([140, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)
    else:
        return template_img  # no special handling

    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    coords = cv2.findNonZero(mask)
    if coords is not None:
        x, y, w, h = cv2.boundingRect(coords)
        cropped = template_img[y : y + h, x : x + w]
        return cropped
    else:
        return template_img

def crop_by_max_color_column(template_img, target_color="red", slice_width=4, crop_percent=0.05):
    """
    Another helper that tries to locate the 'best' vertical slice of the image
    that has the most of the target color, to reduce noise in the matchTemplate.
    """
    hsv = cv2.cvtColor(template_img, cv2.COLOR_BGR2HSV)
    if target_color.lower() == "red":
        lower_red1 = np.array([0, 70, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 70, 50])
        upper_red2 = np.array([180, 255, 255])
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)
    elif target_color.lower() == "blue":
        lower_blue = np.array([80, 70, 50])
        upper_blue = np.array([140, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)
    else:
        return template_img

    col_sums = np.sum(mask > 0, axis=0)
    max_col_index = int(np.argmax(col_sums))
    h, w = template_img.shape[:2]
    left = max(0, max_col_index - slice_width // 2)
    right = min(w, left + slice_width)
    cropped = template_img[:, left:right]

    # Optionally remove top/bottom by crop_percent
    crop_pixels = int(cropped.shape[0] * crop_percent)
    cropped = cropped[crop_pixels : cropped.shape[0] - crop_pixels, :]

    # Then refine again
    cropped_refined = refine_template_crop(cropped, target_color=target_color)
    return cropped_refined

def show_auto_found_popup(screenshot_cv, hp_region, mp_region):
    """
    Shows a small popup window (800x600) with rectangles drawn over the
    discovered HP and MP bar regions.
    """
    orig_h, orig_w, _ = screenshot_cv.shape
    target_size = (800, 600)
    screenshot_resized = cv2.resize(screenshot_cv, target_size, interpolation=cv2.INTER_AREA)
    scale_x = target_size[0] / orig_w
    scale_y = target_size[1] / orig_h

    # Re-scale the found rectangles so we can draw them on the 800x600 image
    hp_region_resized = [
        int(hp_region[0] * scale_x),
        int(hp_region[1] * scale_y),
        int(hp_region[2] * scale_x),
        int(hp_region[3] * scale_y),
    ]
    mp_region_resized = [
        int(mp_region[0] * scale_x),
        int(mp_region[1] * scale_y),
        int(mp_region[2] * scale_x),
        int(mp_region[3] * scale_y),
    ]

    screenshot_rgb = cv2.cvtColor(screenshot_resized, cv2.COLOR_BGR2RGB)
    img_pil = Image.fromarray(screenshot_rgb)
    draw = ImageDraw.Draw(img_pil)

    # Draw red rectangle for HP
    draw.rectangle(
        [
            hp_region_resized[0],
            hp_region_resized[1],
            hp_region_resized[0] + hp_region_resized[2],
            hp_region_resized[1] + hp_region_resized[3],
        ],
        outline="red",
        width=3,
    )
    # Draw blue rectangle for MP
    draw.rectangle(
        [
            mp_region_resized[0],
            mp_region_resized[1],
            mp_region_resized[0] + mp_region_resized[2],
            mp_region_resized[1] + mp_region_resized[3],
        ],
        outline="blue",
        width=3,
    )

    popup = tk.Toplevel()
    popup.title("Auto Found Regions")
    popup.geometry("800x600")

    img_tk = ImageTk.PhotoImage(img_pil)
    label = tk.Label(popup, image=img_tk)
    label.image = img_tk
    label.pack()

    confirm_btn = ttk.Button(popup, text="Confirm", command=popup.destroy)
    confirm_btn.pack(pady=5)

    popup.wait_window()


# ------------------------------------------------------------------------------
# Load & Save Config
# ------------------------------------------------------------------------------
def load_config():
    global CONFIG
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            CONFIG = json.load(f)
    else:
        CONFIG = {
            "HP_REGION": [],
            "MP_REGION": [],
            "THRESHOLD_HP_LOWER": DEFAULT_THRESHOLD_HP_LOWER,
            "THRESHOLD_HP_UPPER": DEFAULT_THRESHOLD_HP_UPPER,
            "THRESHOLD_MP_LOWER": DEFAULT_THRESHOLD_MP_LOWER,
            "THRESHOLD_MP_UPPER": DEFAULT_THRESHOLD_MP_UPPER,
            "COLOR_TIGHTENING": DEFAULT_COLOR_TIGHTENING,
            "HEALTH_POTION_DELAY": DEFAULT_HEALTH_POTION_DELAY,
            "MANA_POTION_DELAY": DEFAULT_MANA_POTION_DELAY,
            "TOGGLE_KEY": DEFAULT_TOGGLE_KEY,
            "PAUSE_KEY": DEFAULT_PAUSE_KEY,
            "SINGLE_SCREEN_HOTKEY": DEFAULT_SINGLE_SCREEN_HOTKEY,
            "USE_GRAY_AS_EMPTY": False,
            "TARGET_WINDOW_TITLE": "Path of Exile 2",
            "SHOW_THRESHOLD_OVERLAY": False,
            "CHICKEN_ENABLED": DEFAULT_CHICKEN_ENABLED,
            "CHICKEN_THRESHOLD": DEFAULT_CHICKEN_THRESHOLD,
            # NEW: Poisoned threshold increase percentage
            "POISONED_THRESHOLD_INCREASE": DEFAULT_POISONED_THRESHOLD_INCREASE
        }
        save_config()

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(CONFIG, f, indent=4)


# ------------------------------------------------------------------------------
# Window detection
# ------------------------------------------------------------------------------
def get_game_window_rect():
    """Return (left, top, width, height) for the configured window, or None."""
    hwnd = win32gui.FindWindow(None, CONFIG.get("TARGET_WINDOW_TITLE","Path of Exile 2"))
    if hwnd == 0:
        return None
    rect = win32gui.GetWindowRect(hwnd)
    left, top, right, bottom = rect
    return (left, top, right - left, bottom - top)


# ------------------------------------------------------------------------------
# HP/MP Fill detection (Modified for Poisoned/Green Health)
# ------------------------------------------------------------------------------
def get_health_fill_percentage(region):
    """Return HP fill% from the region. 0 if region is invalid or not found."""
    if not region or len(region) != 4:
        return 0
    screenshot = pyautogui.screenshot(region=tuple(region))
    frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    use_gray = CONFIG.get("USE_GRAY_AS_EMPTY", False)
    if use_gray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        threshold_value = 100
        full_pixels = np.sum(gray < threshold_value)
        total_pixels = gray.size
        return (full_pixels / total_pixels) * 100 if total_pixels else 0
    else:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        # Red detection (normal health)
        lower_red1 = np.array([0, 50, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 50, 50])
        upper_red2 = np.array([180, 255, 255])
        mask_red1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask_red = cv2.bitwise_or(mask_red1, mask_red2)
        
        # Green detection (poisoned health)
        lower_green = np.array([40, 50, 50])
        upper_green = np.array([80, 255, 255])
        mask_green = cv2.inRange(hsv, lower_green, upper_green)
        
        red_pixels = cv2.countNonZero(mask_red)
        green_pixels = cv2.countNonZero(mask_green)
        total_pixels = mask_red.shape[0] * mask_red.shape[1]
        if total_pixels:
            red_fill = (red_pixels / total_pixels) * 100
            green_fill = (green_pixels / total_pixels) * 100
        else:
            return 0
        
        # Determine if the health bar is poisoned (green dominates)
        is_poisoned = green_pixels > red_pixels
        CONFIG["IS_POISONED"] = is_poisoned  # Save state to use in the monitor loop
        
        # Return fill percentage from the dominant color
        return green_fill if is_poisoned else red_fill

def get_mana_fill_percentage(region):
    """Return MP fill% from the region. 0 if region is invalid or not found."""
    if not region or len(region) != 4:
        return 0
    screenshot = pyautogui.screenshot(region=tuple(region))
    frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    use_gray = CONFIG.get("USE_GRAY_AS_EMPTY", False)
    if use_gray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        threshold_value = 100
        full_pixels = np.sum(gray < threshold_value)
        total_pixels = gray.size
        return (full_pixels / total_pixels) * 100 if total_pixels else 0
    else:
        tighten = CONFIG.get("COLOR_TIGHTENING", 0)
        center_blue = 110
        half_width_blue = 30 * (1 - tighten/100)
        new_lower_blue = np.array([max(80,int(center_blue-half_width_blue)), 50, 50])
        new_upper_blue = np.array([min(140,int(center_blue+half_width_blue)), 255, 255])
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, new_lower_blue, new_upper_blue)
        blue_pixels = cv2.countNonZero(mask)
        total_pixels = mask.shape[0] * mask.shape[1]
        return (blue_pixels / total_pixels) * 100 if total_pixels else 0


# ------------------------------------------------------------------------------
# DualThresholdFillSlider
# ------------------------------------------------------------------------------
class DualThresholdFillSlider(tk.Canvas):
    def __init__(self, master, width=250, height=30, fill_color="red",
                 label_text="HP",
                 lower_initial=55, upper_initial=65,
                 threshold_change_callback=None, **kwargs):
        super().__init__(master, width=width, height=height, **kwargs)
        self.width = width
        self.height = height
        self.fill_color = fill_color
        self.label_text = label_text
        self.current_fill = 0
        self.lower_threshold = lower_initial
        self.upper_threshold = upper_initial
        self.threshold_change_callback = threshold_change_callback
        self.random_threshold = None
        self.active_marker = None

        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)

        self.draw()

    def draw(self):
        self.delete("all")
        # background
        self.create_rectangle(0,0,self.width,self.height,
                              fill="lightgray", outline="")
        # fill
        fill_w = (self.current_fill / 100)*self.width
        self.create_rectangle(0,0, fill_w, self.height,
                              fill=self.fill_color, outline="")

        # threshold lines
        l_x = (self.lower_threshold / 100)*self.width
        u_x = (self.upper_threshold / 100)*self.width
        self.create_line(l_x,0,l_x,self.height, fill="black", width=2)
        self.create_line(u_x,0,u_x,self.height, fill="black", width=2)

        # text
        self.create_text(self.width/2, self.height/2,
                         text=f"{self.label_text}: {self.current_fill:.0f}%",
                         fill="white", font=("Arial",10))
        self.create_text(l_x, -5, text=f"{self.lower_threshold:.0f}%",
                         fill="black", font=("Arial",8))
        self.create_text(u_x, -5, text=f"{self.upper_threshold:.0f}%",
                         fill="black", font=("Arial",8))

        # random line
        if self.random_threshold is not None:
            rx = (self.random_threshold/100)*self.width
            self.create_line(rx,0,rx,self.height,
                             fill="lime", width=2, dash=(3,2))

        # external callback
        if self.threshold_change_callback:
            self.threshold_change_callback(self.lower_threshold,
                                           self.upper_threshold)

    def set_fill(self, val):
        self.current_fill = max(0, min(100, val))
        self.draw()

    def on_click(self, e):
        click_val = (e.x / self.width)*100
        d_lower = abs(click_val - self.lower_threshold)
        d_upper = abs(click_val - self.upper_threshold)
        self.active_marker = "lower" if d_lower<d_upper else "upper"
        self.update_marker(e.x)

    def on_drag(self, e):
        self.update_marker(e.x)

    def on_release(self, e):
        self.active_marker = None

    def update_marker(self, x):
        new_val = (x / self.width)*100
        new_val = max(0,min(100,new_val))
        if self.active_marker=="lower":
            self.lower_threshold = min(new_val, self.upper_threshold)
        elif self.active_marker=="upper":
            self.upper_threshold = max(new_val, self.lower_threshold)
        self.draw()


# ------------------------------------------------------------------------------
# ThresholdOverlay
# ------------------------------------------------------------------------------
class ThresholdOverlay:
    def __init__(self):
        self.overlay = None
        self.canvas = None

    def show(self):
        if self.overlay and self.overlay.winfo_exists():
            return  # already
        rect = get_game_window_rect()
        if not rect:
            return
        x, y, w, h = rect

        self.overlay = tk.Toplevel()
        self.overlay.overrideredirect(True)
        self.overlay.attributes('-topmost', True)
        self.overlay.wm_attributes('-transparentcolor','black')
        self.overlay.geometry(f"{w}x{h}+{x}+{y}")

        self.canvas = tk.Canvas(self.overlay, width=w, height=h,
                                bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

    def hide(self):
        if self.overlay and self.overlay.winfo_exists():
            self.overlay.destroy()
        self.overlay = None
        self.canvas = None

    def update_lines(self, hp_t, mp_t):
        """Update the overlay lines for HP & MP thresholds."""
        if not self.overlay or not self.overlay.winfo_exists():
            return
        if not CONFIG.get("HP_REGION") or not CONFIG.get("MP_REGION"):
            return

        self.canvas.delete("hp_line", "mp_line")

        hp_x, hp_y, hp_w, hp_h = CONFIG["HP_REGION"]
        line_x = hp_x + (hp_w*(hp_t/100.0))
        self.canvas.create_line(line_x, hp_y, line_x, hp_y+hp_h,
                                fill="green", width=3, tags="hp_line")

        mp_x, mp_y, mp_w, mp_h = CONFIG["MP_REGION"]
        line_x = mp_x + (mp_w*(mp_t/100.0))
        self.canvas.create_line(line_x, mp_y, line_x, mp_y+mp_h,
                                fill="green", width=3, tags="mp_line")


# ------------------------------------------------------------------------------
# AutoPotionApp
# ------------------------------------------------------------------------------
class AutoPotionApp:
    def __init__(self, root):
        global CONFIG
        self.root = root
        self.root.title("PoE2 Auto-Potion Bot")
        load_config()

        # Must define these BEFORE building the sliders:
        self.hp_lower_var = tk.DoubleVar(value=CONFIG.get("THRESHOLD_HP_LOWER", DEFAULT_THRESHOLD_HP_LOWER))
        self.hp_upper_var = tk.DoubleVar(value=CONFIG.get("THRESHOLD_HP_UPPER", DEFAULT_THRESHOLD_HP_UPPER))
        self.mp_lower_var = tk.DoubleVar(value=CONFIG.get("THRESHOLD_MP_LOWER", DEFAULT_THRESHOLD_MP_LOWER))
        self.mp_upper_var = tk.DoubleVar(value=CONFIG.get("THRESHOLD_MP_UPPER", DEFAULT_THRESHOLD_MP_UPPER))

        # other config vars:
        self.color_tighten_var = tk.IntVar(value=CONFIG.get("COLOR_TIGHTENING", DEFAULT_COLOR_TIGHTENING))
        self.health_pot_delay_var = tk.DoubleVar(value=CONFIG.get("HEALTH_POTION_DELAY", DEFAULT_HEALTH_POTION_DELAY))
        self.mana_pot_delay_var   = tk.DoubleVar(value=CONFIG.get("MANA_POTION_DELAY", DEFAULT_MANA_POTION_DELAY))
        self.toggle_key_var = tk.StringVar(value=CONFIG.get("TOGGLE_KEY", DEFAULT_TOGGLE_KEY))
        self.pause_key_var = tk.StringVar(value=CONFIG.get("PAUSE_KEY", DEFAULT_PAUSE_KEY))
        self.single_screen_var = tk.StringVar(value=CONFIG.get("SINGLE_SCREEN_HOTKEY", DEFAULT_SINGLE_SCREEN_HOTKEY))
        self.use_gray_var = tk.BooleanVar(value=CONFIG.get("USE_GRAY_AS_EMPTY", False))
        self.show_overlay_var = tk.BooleanVar(value=CONFIG.get("SHOW_THRESHOLD_OVERLAY", False))
        self.chicken_enabled_var = tk.BooleanVar(value=CONFIG.get("CHICKEN_ENABLED", DEFAULT_CHICKEN_ENABLED))
        self.chicken_threshold_var = tk.DoubleVar(value=CONFIG.get("CHICKEN_THRESHOLD", DEFAULT_CHICKEN_THRESHOLD))
        # NEW: Poisoned threshold increase variable
        self.poisoned_threshold_var = tk.DoubleVar(value=CONFIG.get("POISONED_THRESHOLD_INCREASE", DEFAULT_POISONED_THRESHOLD_INCREASE))

        self.monitoring = False
        self.paused = False
        self.monitor_thread = None
        self.hotkey_handles = []

        self.current_random_hp_threshold = None
        self.current_random_mp_threshold = None
        self.last_random_update = time.time()

        self.overlay = ThresholdOverlay()

        main_frame = ttk.Frame(root, padding="5")
        main_frame.pack(fill="both", expand=True)

        self.status_label = ttk.Label(main_frame, text="Status: Not Monitoring")
        self.status_label.grid(row=0, column=0, columnspan=3, sticky="w")

        # Target Window
        self.target_window_label = ttk.Label(main_frame,
            text=f"Target Window: {CONFIG.get('TARGET_WINDOW_TITLE')}")
        self.target_window_label.grid(row=1, column=0, sticky="w")

        btn_select_window = ttk.Button(main_frame, text="Select Target Window",
                                       command=self.select_target_window)
        btn_select_window.grid(row=1, column=1, sticky="w")

        # HP/MP region labels
        self.hp_region_label = ttk.Label(main_frame,
            text=f"HP Region: {CONFIG.get('HP_REGION') or 'Not set'}")
        self.hp_region_label.grid(row=2, column=0, sticky="w")

        self.mp_region_label = ttk.Label(main_frame,
            text=f"MP Region: {CONFIG.get('MP_REGION') or 'Not set'}")
        self.mp_region_label.grid(row=2, column=1, sticky="w")

        # HP slider
        hp_frame = ttk.LabelFrame(main_frame, text="HP Fill & Thresholds")
        hp_frame.grid(row=3, column=0, columnspan=3, pady=5, sticky="ew")

        hp_label = "HP Empty" if CONFIG.get("USE_GRAY_AS_EMPTY") else "HP"
        self.hp_slider = DualThresholdFillSlider(
            hp_frame,
            width=250,
            height=30,
            fill_color="red",
            label_text=hp_label,
            lower_initial=self.hp_lower_var.get(),
            upper_initial=self.hp_upper_var.get(),
            threshold_change_callback=self.update_hp_threshold_entries
        )
        self.hp_slider.pack(pady=2)

        # MP slider
        mp_frame = ttk.LabelFrame(main_frame, text="MP Fill & Thresholds")
        mp_frame.grid(row=4, column=0, columnspan=3, pady=5, sticky="ew")

        self.mp_slider = DualThresholdFillSlider(
            mp_frame,
            width=250,
            height=30,
            fill_color="blue",
            label_text="MP",
            lower_initial=self.mp_lower_var.get(),
            upper_initial=self.mp_upper_var.get(),
            threshold_change_callback=self.update_mp_threshold_entries
        )
        self.mp_slider.pack(pady=2)

        # Region selection
        region_frame = ttk.Frame(main_frame)
        region_frame.grid(row=5, column=0, columnspan=3, pady=3, sticky="ew")

        btn_sel_hp = ttk.Button(region_frame, text="Select HP Region",
                                command=lambda: self.select_region("HP"))
        btn_sel_hp.pack(side="left", expand=True, fill="x", padx=2)

        btn_sel_mp = ttk.Button(region_frame, text="Select MP Region",
                                command=lambda: self.select_region("MP"))
        btn_sel_mp.pack(side="left", expand=True, fill="x", padx=2)

        # Auto-Find button replaced to use the advanced approach
        btn_auto_find = ttk.Button(region_frame, text="Auto Find HP/MP Regions",
                                   command=self.auto_find_regions)
        btn_auto_find.pack(side="left", expand=True, fill="x", padx=2)

        # Settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="5")
        settings_frame.grid(row=6, column=0, columnspan=3, sticky="ew")

        # HP
        ttk.Label(settings_frame, text="HP Lower:").grid(row=0, column=0)
        hp_lower_entry = ttk.Entry(settings_frame, textvariable=self.hp_lower_var, width=5)
        hp_lower_entry.grid(row=0,column=1)
        hp_lower_entry.bind("<FocusOut>", self.update_hp_slider_from_entry)
        hp_lower_entry.bind("<Return>", self.update_hp_slider_from_entry)

        ttk.Label(settings_frame, text="HP Upper:").grid(row=0, column=2)
        hp_upper_entry = ttk.Entry(settings_frame, textvariable=self.hp_upper_var, width=5)
        hp_upper_entry.grid(row=0,column=3)
        hp_upper_entry.bind("<FocusOut>", self.update_hp_slider_from_entry)
        hp_upper_entry.bind("<Return>", self.update_hp_slider_from_entry)

        # MP
        ttk.Label(settings_frame, text="MP Lower:").grid(row=1, column=0)
        mp_lower_entry = ttk.Entry(settings_frame, textvariable=self.mp_lower_var, width=5)
        mp_lower_entry.grid(row=1,column=1)
        mp_lower_entry.bind("<FocusOut>", self.update_mp_slider_from_entry)
        mp_lower_entry.bind("<Return>", self.update_mp_slider_from_entry)

        ttk.Label(settings_frame, text="MP Upper:").grid(row=1, column=2)
        mp_upper_entry = ttk.Entry(settings_frame, textvariable=self.mp_upper_var, width=5)
        mp_upper_entry.grid(row=1,column=3)
        mp_upper_entry.bind("<FocusOut>", self.update_mp_slider_from_entry)
        mp_upper_entry.bind("<Return>", self.update_mp_slider_from_entry)

        # Color Tuning
        ttk.Label(settings_frame, text="Color Tuning (%):").grid(row=2, column=0)
        ttk.Entry(settings_frame, textvariable=self.color_tighten_var, width=5).grid(row=2,column=1)

        # Potion Delays
        ttk.Label(settings_frame, text="HP Delay:").grid(row=2, column=2)
        ttk.Entry(settings_frame, textvariable=self.health_pot_delay_var, width=5).grid(row=2,column=3)

        ttk.Label(settings_frame, text="MP Delay:").grid(row=3, column=0)
        ttk.Entry(settings_frame, textvariable=self.mana_pot_delay_var, width=5).grid(row=3,column=1)

        # Hotkeys
        ttk.Label(settings_frame, text="Toggle Key:").grid(row=3, column=2)
        ttk.Entry(settings_frame, textvariable=self.toggle_key_var, width=5).grid(row=3,column=3)

        ttk.Label(settings_frame, text="Pause Key:").grid(row=4, column=0)
        ttk.Entry(settings_frame, textvariable=self.pause_key_var, width=5).grid(row=4,column=1)

        ttk.Label(settings_frame, text="SingleScreen Key:").grid(row=4, column=2)
        ttk.Entry(settings_frame, textvariable=self.single_screen_var, width=5).grid(row=4,column=3)

        # Gray
        chk_gray = ttk.Checkbutton(settings_frame, text="Use Gray as HP/MP?",
                                   variable=self.use_gray_var,
                                   command=self.toggle_gray_mode)
        chk_gray.grid(row=5,column=0,columnspan=2, sticky="w")

        # Overlay
        chk_overlay = ttk.Checkbutton(settings_frame, text="Show Threshold Overlay",
                                      variable=self.show_overlay_var,
                                      command=self.toggle_threshold_overlay)
        chk_overlay.grid(row=5,column=2,columnspan=2, sticky="w")

        # Chickening
        ttk.Label(settings_frame, text="Chicken HP:").grid(row=6, column=0)
        ttk.Entry(settings_frame, textvariable=self.chicken_threshold_var, width=5).grid(row=6,column=1)
        chk_chicken = ttk.Checkbutton(settings_frame, text="Enable Chickening",
                                      variable=self.chicken_enabled_var)
        chk_chicken.grid(row=6,column=2,columnspan=2, sticky="w")

        # NEW: Poisoned Threshold Increase setting
        ttk.Label(settings_frame, text="Poisoned Threshold Increase (%):").grid(row=7, column=0)
        ttk.Entry(settings_frame, textvariable=self.poisoned_threshold_var, width=5).grid(row=7, column=1)

        # Save
        btn_save = ttk.Button(settings_frame, text="Save All Settings",
                              command=self.save_all_settings)
        btn_save.grid(row=8, column=0, columnspan=4, pady=5)

        # Log
        log_frame = ttk.LabelFrame(main_frame, text="Log")
        log_frame.grid(row=9, column=0, columnspan=3, pady=3, sticky="nsew")
        self.log_text = tk.Text(log_frame, height=6, state="disabled")
        self.log_text.pack(fill="both", expand=True)

        # Start/Stop
        self.toggle_button = ttk.Button(main_frame, text="Start Monitoring",
                                        command=self.toggle_monitoring)
        self.toggle_button.grid(row=10, column=0, columnspan=3, pady=5)

        self.update_hotkeys()

    # -------------------------
    # Threshold slider callbacks
    # -------------------------
    def update_hp_threshold_entries(self, lower, upper):
        if hasattr(self, "hp_lower_var") and hasattr(self, "hp_upper_var"):
            self.hp_lower_var.set(lower)
            self.hp_upper_var.set(upper)

    def update_mp_threshold_entries(self, lower, upper):
        if hasattr(self, "mp_lower_var") and hasattr(self, "mp_upper_var"):
            self.mp_lower_var.set(lower)
            self.mp_upper_var.set(upper)

    def update_hp_slider_from_entry(self, event):
        try:
            l = float(self.hp_lower_var.get())
            h = float(self.hp_upper_var.get())
            self.hp_slider.lower_threshold = l
            self.hp_slider.upper_threshold = h
            self.hp_slider.draw()
        except:
            pass

    def update_mp_slider_from_entry(self, event):
        try:
            l = float(self.mp_lower_var.get())
            h = float(self.mp_upper_var.get())
            self.mp_slider.lower_threshold = l
            self.mp_slider.upper_threshold = h
            self.mp_slider.draw()
        except:
            pass

    # -------------------------
    # GUI toggles
    # -------------------------
    def toggle_gray_mode(self):
        CONFIG["USE_GRAY_AS_EMPTY"] = self.use_gray_var.get()
        save_config()
        mode_text = "HP Empty" if CONFIG["USE_GRAY_AS_EMPTY"] else "HP"
        self.hp_slider.label_text = mode_text
        self.hp_slider.draw()

    def toggle_threshold_overlay(self):
        CONFIG["SHOW_THRESHOLD_OVERLAY"] = self.show_overlay_var.get()
        save_config()
        if CONFIG["SHOW_THRESHOLD_OVERLAY"]:
            self.overlay.show()
        else:
            self.overlay.hide()

    # -------------------------
    # Region selection
    # -------------------------
    def select_target_window(self):
        windows = list_windows()
        if not windows:
            messagebox.showerror("Error", "No windows found!")
            return
        sel_win = tk.Toplevel(self.root)
        sel_win.title("Select Target Window")
        lb = tk.Listbox(sel_win, width=60)
        lb.pack(padx=5, pady=5)
        for w in windows:
            lb.insert(tk.END, w)

        def on_select():
            try:
                sel = lb.get(lb.curselection())
                CONFIG["TARGET_WINDOW_TITLE"] = sel
                save_config()
                self.target_window_label.config(text=f"Target Window: {sel}")
                sel_win.destroy()
            except:
                pass

        ttk.Button(sel_win, text="Confirm", command=on_select).pack(pady=5)

    def select_region(self, which):
        from tkinter import messagebox

        screenshot = pyautogui.screenshot()
        orig_img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        orig_h, orig_w = orig_img.shape[:2]

        disp_w, disp_h = 800,600
        resized = cv2.resize(orig_img, (disp_w,disp_h))
        pil_img = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))

        top_sel = tk.Toplevel(self.root)
        top_sel.title(f"Select {which} Region")
        c = tk.Canvas(top_sel, width=disp_w, height=disp_h)
        c.pack()

        tkimg = ImageTk.PhotoImage(pil_img)
        c.create_image(0,0,anchor="nw", image=tkimg)

        selection = {"start": None, "end": None, "rect": None}
        def on_mouse_down(e):
            selection["start"] = (e.x, e.y)
            if selection["rect"]:
                c.delete(selection["rect"])
                selection["rect"] = None

        def on_mouse_move(e):
            if selection["start"]:
                if selection["rect"]:
                    c.delete(selection["rect"])
                selection["end"] = (e.x, e.y)
                selection["rect"] = c.create_rectangle(
                    selection["start"][0], selection["start"][1],
                    e.x, e.y, outline="green", width=2
                )

        def on_mouse_up(e):
            selection["end"] = (e.x, e.y)

        c.bind("<ButtonPress-1>", on_mouse_down)
        c.bind("<B1-Motion>", on_mouse_move)
        c.bind("<ButtonRelease-1>", on_mouse_up)

        def confirm_region():
            if not selection["start"] or not selection["end"]:
                messagebox.showwarning("No region","You must drag a rectangle!")
                return
            x1,y1 = selection["start"]
            x2,y2 = selection["end"]
            x, y = min(x1,x2), min(y1,y2)
            w, h = abs(x2-x1), abs(y2-y1)

            scale_x = orig_w / disp_w
            scale_y = orig_h / disp_h
            rx = int(x*scale_x)
            ry = int(y*scale_y)
            rw = int(w*scale_x)
            rh = int(h*scale_y)

            if which=="HP":
                CONFIG["HP_REGION"] = [rx, ry, rw, rh]
                self.hp_region_label.config(text=f"HP Region: {CONFIG['HP_REGION']}")
            else:
                CONFIG["MP_REGION"] = [rx, ry, rw, rh]
                self.mp_region_label.config(text=f"MP Region: {CONFIG['MP_REGION']}")

            save_config()
            top_sel.destroy()
            messagebox.showinfo("Saved", f"{which} region saved.")
        ttk.Button(top_sel, text="Confirm", command=confirm_region).pack(pady=5)

    # ------------- ADDED: Full auto-find method from second snippet -------------
    def auto_find_regions(self):
        """Attempt to locate HP and MP bars automatically via template matching."""
        target_title = CONFIG.get("TARGET_WINDOW_TITLE")
        if not target_title:
            messagebox.showwarning("Error", "Please select a target window first!")
            return
        hwnd = win32gui.FindWindow(None, target_title)
        if hwnd == 0:
            messagebox.showerror("Error", "Target window not found.")
            return

        rect = win32gui.GetWindowRect(hwnd)
        x, y, w, h = rect[0], rect[1], rect[2]-rect[0], rect[3]-rect[1]
        screenshot = pyautogui.screenshot(region=(x, y, w, h))
        screenshot_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # Expect user to provide health.png / mana.png in same directory
        hp_template_path = os.path.join(SCRIPT_DIR, "health.png")
        mp_template_path = os.path.join(SCRIPT_DIR, "mana.png")
        if not os.path.exists(hp_template_path) or not os.path.exists(mp_template_path):
            messagebox.showerror("Error", "Template images for HP (health.png) and MP (mana.png) not found!")
            return

        hp_template = cv2.imread(hp_template_path, cv2.IMREAD_COLOR)
        mp_template = cv2.imread(mp_template_path, cv2.IMREAD_COLOR)
        hp_refined = refine_template_crop(hp_template, target_color="red")
        mp_refined = refine_template_crop(mp_template, target_color="blue")

        hp_cropped = crop_by_max_color_column(hp_refined, target_color="red", slice_width=4, crop_percent=0.05)
        mp_cropped = crop_by_max_color_column(mp_refined, target_color="blue", slice_width=4, crop_percent=0.05)

        res_hp = cv2.matchTemplate(screenshot_cv, hp_cropped, cv2.TM_CCOEFF_NORMED)
        _, max_val_hp, _, max_loc_hp = cv2.minMaxLoc(res_hp)

        res_mp = cv2.matchTemplate(screenshot_cv, mp_cropped, cv2.TM_CCOEFF_NORMED)
        _, max_val_mp, _, max_loc_mp = cv2.minMaxLoc(res_mp)

        threshold = 0.8
        if max_val_hp < threshold or max_val_mp < threshold:
            messagebox.showerror("Error", "Could not detect health/mana regions automatically.")
            return

        hp_h, hp_w = hp_cropped.shape[:2]
        mp_h, mp_w = mp_cropped.shape[:2]

        # Convert the found location in screenshot to absolute screen coords
        hp_region = [x + max_loc_hp[0], y + max_loc_hp[1], hp_w, hp_h]
        mp_region = [x + max_loc_mp[0], y + max_loc_mp[1], mp_w, mp_h]

        # Show popup so user sees the guess
        show_auto_found_popup(screenshot_cv, hp_region, mp_region)

        # Save to config
        CONFIG["HP_REGION"] = hp_region
        CONFIG["MP_REGION"] = mp_region
        save_config()

        self.hp_region_label.config(text=f"HP Region: {hp_region}")
        self.mp_region_label.config(text=f"MP Region: {mp_region}")
        messagebox.showinfo("Auto Detection", "Health and Mana regions updated automatically!")

    # -------------------------
    # Save & Log
    # -------------------------
    def save_all_settings(self):
        CONFIG["THRESHOLD_HP_LOWER"] = self.hp_lower_var.get()
        CONFIG["THRESHOLD_HP_UPPER"] = self.hp_upper_var.get()
        CONFIG["THRESHOLD_MP_LOWER"] = self.mp_lower_var.get()
        CONFIG["THRESHOLD_MP_UPPER"] = self.mp_upper_var.get()
        CONFIG["COLOR_TIGHTENING"] = self.color_tighten_var.get()
        CONFIG["HEALTH_POTION_DELAY"] = self.health_pot_delay_var.get()
        CONFIG["MANA_POTION_DELAY"] = self.mana_pot_delay_var.get()
        CONFIG["TOGGLE_KEY"] = self.toggle_key_var.get()
        CONFIG["PAUSE_KEY"] = self.pause_key_var.get()
        CONFIG["SINGLE_SCREEN_HOTKEY"] = self.single_screen_var.get()
        CONFIG["USE_GRAY_AS_EMPTY"] = self.use_gray_var.get()
        CONFIG["SHOW_THRESHOLD_OVERLAY"] = self.show_overlay_var.get()
        CONFIG["CHICKEN_ENABLED"] = self.chicken_enabled_var.get()
        CONFIG["CHICKEN_THRESHOLD"] = self.chicken_threshold_var.get()
        # Save the new poisoned threshold increase setting
        CONFIG["POISONED_THRESHOLD_INCREASE"] = self.poisoned_threshold_var.get()

        save_config()

        # update sliders
        self.hp_slider.lower_threshold = CONFIG["THRESHOLD_HP_LOWER"]
        self.hp_slider.upper_threshold = CONFIG["THRESHOLD_HP_UPPER"]
        self.mp_slider.lower_threshold = CONFIG["THRESHOLD_MP_LOWER"]
        self.mp_slider.upper_threshold = CONFIG["THRESHOLD_MP_UPPER"]
        self.hp_slider.draw()
        self.mp_slider.draw()

        self.update_hotkeys()
        messagebox.showinfo("Settings","All settings saved.")

    def log_message(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg+"\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        print(msg)

    # -------------------------
    # Hotkeys
    # -------------------------
    def update_hotkeys(self):
        # Clear old
        for h in self.hotkey_handles:
            keyboard.remove_hotkey(h)
        self.hotkey_handles = []

        tkey = CONFIG.get("TOGGLE_KEY", DEFAULT_TOGGLE_KEY)
        pkey = CONFIG.get("PAUSE_KEY", DEFAULT_PAUSE_KEY)
        skey = CONFIG.get("SINGLE_SCREEN_HOTKEY", DEFAULT_SINGLE_SCREEN_HOTKEY)

        self.hotkey_handles.append(keyboard.add_hotkey(tkey, self.hotkey_toggle))
        self.hotkey_handles.append(keyboard.add_hotkey(pkey, self.hotkey_pause))
        self.hotkey_handles.append(keyboard.add_hotkey(skey, self.show_gui_hotkey))

        self.log_message(f"Hotkeys set: Toggle={tkey}, Pause={pkey}, Single={skey}")

    def hotkey_toggle(self):
        self.root.after(0, self.toggle_monitoring)

    def hotkey_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.log_message("Paused via hotkey.")
            self.status_label.config(text="Status: Paused (Hotkey)")
        else:
            self.log_message("Resumed via hotkey.")
            self.status_label.config(text="Status: Monitoring")

    def show_gui_hotkey(self):
        self.overlay.hide()
        # bring game window front
        hwnd = win32gui.FindWindow(None, CONFIG.get("TARGET_WINDOW_TITLE","Path of Exile 2"))
        if hwnd != 0:
            try:
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.2)
            except:
                pass
        pyautogui.press("esc")
        time.sleep(0.2)
        if self.root.state()=="iconic":
            self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        def revert():
            self.root.attributes("-topmost", False)
        self.root.after(1000, revert)

    # -------------------------
    # Monitoring
    # -------------------------
    def toggle_monitoring(self):
        self.monitoring = not self.monitoring
        if self.monitoring:
            self.toggle_button.config(text="Stop Monitoring")
            self.log_message("Monitoring started.")
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()
        else:
            self.toggle_button.config(text="Start Monitoring")
            self.log_message("Monitoring stopped.")

    def monitor_loop(self):
        """
        Runs in a thread while self.monitoring = True.
        We do NOT break out entirely on chicken; instead we:
         1) Run the chicken flow,
         2) Wait for HP >= 50%,
         3) Resume normal potion usage,
         4) Keep monitoring forever.
        """
        while self.monitoring:
            if self.paused:
                self.status_label.config(text="Status: Paused")
                time.sleep(MONITOR_SLEEP_TIME)
                continue

            # must be in active window
            hwnd_target = win32gui.FindWindow(None, CONFIG.get("TARGET_WINDOW_TITLE","Path of Exile 2"))
            hwnd_active = win32gui.GetForegroundWindow()
            if hwnd_target==0:
                self.status_label.config(text="Status: Game Window Not Found")
                time.sleep(MONITOR_SLEEP_TIME)
                continue
            if hwnd_target!=hwnd_active:
                self.status_label.config(text="Status: Target Window Not Active")
                time.sleep(MONITOR_SLEEP_TIME)
                continue

            # get HP/MP
            hp_fill = get_health_fill_percentage(CONFIG["HP_REGION"])
            mp_fill = get_mana_fill_percentage(CONFIG["MP_REGION"])

            self.root.after(0, self.hp_slider.set_fill, hp_fill)
            self.root.after(0, self.mp_slider.set_fill, mp_fill)

            # if both basically 0 => might be loading
            if hp_fill<1 and mp_fill<1:
                self.status_label.config(text="Status: Pause/Loading/Unknown")
                time.sleep(MONITOR_SLEEP_TIME)
                continue

            self.status_label.config(text="Status: Monitoring")

            # -- Chickening check --
            if CONFIG.get("CHICKEN_ENABLED",False):
                c_thr = CONFIG.get("CHICKEN_THRESHOLD", 30)
                if hp_fill < c_thr:
                    self.log_message(f"HP < {c_thr} => chickening out!")
                    # CHANGED: do not break or stop monitoring
                    self.chicken_and_reconnect()
                    self.log_message("Waiting until HP >= 50% before using potions.")
                    # Wait for HP >= 50 but still keep monitoring loop alive
                    while True:
                        if not self.monitoring:
                            return
                        hp_fill = get_health_fill_percentage(CONFIG["HP_REGION"])
                        mp_fill = get_mana_fill_percentage(CONFIG["MP_REGION"])
                        self.root.after(0, self.hp_slider.set_fill, hp_fill)
                        self.root.after(0, self.mp_slider.set_fill, mp_fill)
                        if hp_fill >= 50:
                            self.log_message("HP >= 50, resuming normal potion usage.")
                            break
                        time.sleep(1.0)

            # random thresholds
            now = time.time()
            if now - self.last_random_update >= 0.5:
                hp_l = self.hp_slider.lower_threshold
                hp_u = self.hp_slider.upper_threshold
                mp_l = self.mp_slider.lower_threshold
                mp_u = self.mp_slider.upper_threshold
                self.current_random_hp_threshold = random.uniform(hp_l, hp_u)
                self.current_random_mp_threshold = random.uniform(mp_l, mp_u)
                self.last_random_update = now

                self.hp_slider.random_threshold = self.current_random_hp_threshold
                self.mp_slider.random_threshold = self.current_random_mp_threshold
                self.root.after(0, self.hp_slider.draw)
                self.root.after(0, self.mp_slider.draw)

                if CONFIG.get("SHOW_THRESHOLD_OVERLAY",False):
                    self.root.after(0, self.overlay.update_lines,
                                    self.current_random_hp_threshold,
                                    self.current_random_mp_threshold)

            # Adjust HP lower threshold if poisoned (green health)
            hp_lower = self.hp_slider.lower_threshold
            if CONFIG.get("IS_POISONED", False):
                increase = CONFIG.get("POISONED_THRESHOLD_INCREASE", 0)
                hp_lower = hp_lower * (1 + increase/100)

            # potions
            hp_delay = CONFIG.get("HEALTH_POTION_DELAY",0.5)
            if (hp_fill < hp_lower) or (hp_fill < self.current_random_hp_threshold):
                self.use_potion("1", hp_fill, "Health", hp_delay)

            mp_lower = self.mp_slider.lower_threshold
            mp_delay = CONFIG.get("MANA_POTION_DELAY",0.5)
            if (mp_fill < mp_lower) or (mp_fill < self.current_random_mp_threshold):
                self.use_potion("2", mp_fill, "Mana", mp_delay)

            time.sleep(MONITOR_SLEEP_TIME)

        print("Exited monitor loop.")

    def use_potion(self, key, fill_val, label, delay):
        pyautogui.press(key)
        self.log_message(f"{label} potion used! (fill={fill_val:.1f}%)")
        time.sleep(delay)

    # ---------------
    # Chicken flow
    # ---------------
    def chicken_and_reconnect(self):
        self.log_message("Chickening flow: pressing ESC, searching for exit button.")
        hwnd = win32gui.FindWindow(None, CONFIG.get("TARGET_WINDOW_TITLE", "Path of Exile 2"))
        if hwnd:
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception as e:
                self.log_message(f"Error setting foreground: {e}")

        pyautogui.press("esc")
        # Reduced delay to 0.1 seconds; adjust as needed based on UI response time
        time.sleep(0.1)

        exit_path = os.path.join(SCRIPT_DIR, "exit_to_log_in_screen.png")
        if not os.path.exists(exit_path):
            self.log_message("ERROR: exit_to_log_in_screen.png not found!")
        else:
            # Use the game window's region to narrow the search area
            game_rect = get_game_window_rect()
            if game_rect:
                x, y, w, h = game_rect
                btn = pyautogui.locateOnScreen(exit_path, confidence=0.8, region=(x, y, w, h), grayscale=True)
            else:
                btn = pyautogui.locateOnScreen(exit_path, confidence=0.8, grayscale=True)

            if btn:
                self.log_message("Exit button found. Clicking center...")
                center_x, center_y = pyautogui.center(btn)
                pyautogui.moveTo(center_x, center_y)
                pyautogui.click()
                self.log_message("Clicked 'Exit to Log In Screen'.")
            else:
                self.log_message("Could NOT find 'Exit to Log In Screen' on screen!")

        time.sleep(2.0)

        self.log_message("Waiting for HP or MP to reappear (load screen) ...")
        while True:
            if not self.monitoring:
                return
            hwnd = win32gui.FindWindow(None, CONFIG.get("TARGET_WINDOW_TITLE", "Path of Exile 2"))
            if hwnd:
                try:
                    win32gui.SetForegroundWindow(hwnd)
                except Exception as e:
                    self.log_message(f"Error setting foreground: {e}")
            hp = get_health_fill_percentage(CONFIG["HP_REGION"])
            mp = get_mana_fill_percentage(CONFIG["MP_REGION"])
            self.root.after(0, self.hp_slider.set_fill, hp)
            self.root.after(0, self.mp_slider.set_fill, mp)
            if hp > 1 or mp > 1:
                self.log_message("HP/MP found (loading complete).")
                break
            time.sleep(1.0)


def main():
    root = tk.Tk()
    app = AutoPotionApp(root)
    root.mainloop()

if __name__=="__main__":
    main()

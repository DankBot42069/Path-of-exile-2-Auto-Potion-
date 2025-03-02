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

# ------------------------------------------------------------------
# Determine the script's directory so we can load files from there
# ------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

# Default thresholds (in percentage)
DEFAULT_THRESHOLD_HP_LOWER = 55
DEFAULT_THRESHOLD_HP_UPPER = 65
DEFAULT_THRESHOLD_MP_LOWER = 55
DEFAULT_THRESHOLD_MP_UPPER = 65

# Default color tightening (0% means use full default ranges)
DEFAULT_COLOR_TIGHTENING = 0

# Default potion delays (in seconds)
DEFAULT_HEALTH_POTION_DELAY = 0.5
DEFAULT_MANA_POTION_DELAY = 0.5

# Key bindings for potions
HEALTH_POTION_KEY = "1"
MANA_POTION_KEY   = "2"

# Default hotkeys for toggling and pausing the bot
DEFAULT_TOGGLE_KEY = "F8"
DEFAULT_PAUSE_KEY = "F9"

# Monitoring speed (seconds)
MONITOR_SLEEP_TIME = 0.2

# ------------------------------------------------------------------
# Paths to images (absolute paths)
# ------------------------------------------------------------------
LOADING_SCREEN_IMAGE = os.path.join(SCRIPT_DIR, "loading_screen_gears.png")
DEATH_SCREEN_IMAGE   = os.path.join(SCRIPT_DIR, "death_screen.png")
# Template images: health.png for HP and mana.png for MP

# Global configuration dictionary.
CONFIG = {}

# Determine the resampling filter for Pillow resizing.
try:
    RESAMPLE_FILTER = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE_FILTER = Image.ANTIALIAS

# ------------------------------------------------------------------
# Dual Threshold Fill Slider Widget
# ------------------------------------------------------------------
class DualThresholdFillSlider(tk.Canvas):
    def __init__(self, master, width=250, height=30, fill_color="red", label_text="HP",
                 lower_initial=55, upper_initial=65, threshold_change_callback=None, **kwargs):
        super().__init__(master, width=width, height=height, **kwargs)
        self.width = width
        self.height = height
        self.fill_color = fill_color
        self.label_text = label_text
        self.current_fill = 0  # Current resource fill (0-100)
        self.lower_threshold = lower_initial
        self.upper_threshold = upper_initial
        self.threshold_change_callback = threshold_change_callback
        self.random_threshold = None  # Random threshold value to be drawn as a green line
        self.active_marker = None  # Which marker is being dragged ("lower" or "upper")
        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.draw()

    def draw(self):
        self.delete("all")
        self.create_rectangle(0, 0, self.width, self.height, fill="lightgray", outline="")
        fill_width = (self.current_fill / 100) * self.width
        self.create_rectangle(0, 0, fill_width, self.height, fill=self.fill_color, outline="")
        lower_x = (self.lower_threshold / 100) * self.width
        upper_x = (self.upper_threshold / 100) * self.width
        self.create_line(lower_x, 0, lower_x, self.height, fill="black", width=2)
        self.create_line(upper_x, 0, upper_x, self.height, fill="black", width=2)
        self.create_text(self.width/2, self.height/2,
                         text=f"{self.label_text}: {self.current_fill:.0f}%",
                         fill="white", font=("Arial", 10))
        self.create_text(lower_x, -5, text=f"{self.lower_threshold:.0f}%", fill="black", font=("Arial", 8))
        self.create_text(upper_x, -5, text=f"{self.upper_threshold:.0f}%", fill="black", font=("Arial", 8))
        if self.random_threshold is not None:
            random_x = (self.random_threshold / 100) * self.width
            self.create_line(random_x, 0, random_x, self.height, fill="lime", width=2, dash=(3,2))
        if self.threshold_change_callback:
            self.threshold_change_callback(self.lower_threshold, self.upper_threshold)

    def set_fill(self, fill_value):
        self.current_fill = max(0, min(100, fill_value))
        self.draw()

    def on_click(self, event):
        click_value = (event.x / self.width) * 100
        lower_dist = abs(click_value - self.lower_threshold)
        upper_dist = abs(click_value - self.upper_threshold)
        self.active_marker = "lower" if lower_dist < upper_dist else "upper"
        self.update_marker(event.x)

    def on_drag(self, event):
        self.update_marker(event.x)

    def on_release(self, event):
        self.active_marker = None

    def update_marker(self, x):
        new_value = (x / self.width) * 100
        new_value = max(0, min(100, new_value))
        if self.active_marker == "lower":
            self.lower_threshold = min(new_value, self.upper_threshold)
        elif self.active_marker == "upper":
            self.upper_threshold = max(new_value, self.lower_threshold)
        self.draw()

# ------------------------------------------------------------------
# Utility Functions
# ------------------------------------------------------------------
def get_game_window_rect():
    target_title = CONFIG.get("TARGET_WINDOW_TITLE", "Path of Exile 2")
    hwnd = win32gui.FindWindow(None, target_title)
    if hwnd == 0:
        print("Game window not found!")
        return None
    rect = win32gui.GetWindowRect(hwnd)
    left, top, right, bottom = rect
    return (left, top, right - left, bottom - top)

def load_config():
    global CONFIG
    rect = get_game_window_rect()
    if rect:
        _, _, gw, gh = rect
    else:
        gw, gh = 1920, 1080
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            CONFIG = json.load(f)
        print("Configuration loaded:", CONFIG)
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
            "WINDOW_RESOLUTION": [gw, gh],
            "TOGGLE_KEY": DEFAULT_TOGGLE_KEY,
            "PAUSE_KEY": DEFAULT_PAUSE_KEY,
            "USE_GRAY_AS_EMPTY": False,
            "TARGET_WINDOW_TITLE": "Path of Exile 2"
        }
        save_config()
        print("Default configuration created and saved.")

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(CONFIG, f, indent=4)
    print("Configuration saved:", CONFIG)

def load_assets():
    if os.path.exists(DEATH_SCREEN_IMAGE):
        _ = cv2.imread(DEATH_SCREEN_IMAGE, cv2.IMREAD_COLOR)
        print(f"Loaded death screen template from {DEATH_SCREEN_IMAGE}")
    else:
        print(f"No death screen image found at {DEATH_SCREEN_IMAGE}")

def get_health_fill_percentage(region):
    screenshot = pyautogui.screenshot(region=tuple(region))
    frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    use_gray = CONFIG.get("USE_GRAY_AS_EMPTY", False)
    if use_gray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        threshold_value = 100
        full_pixels = np.sum(gray < threshold_value)
        total_pixels = gray.size
        return (full_pixels / total_pixels) * 100 if total_pixels > 0 else 0
    else:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0, 50, 50])  # lowered threshold for red
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([160, 50, 50])
        upper_red2 = np.array([180, 255, 255])
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)
        red_pixels = cv2.countNonZero(mask)
        total_pixels = mask.shape[0] * mask.shape[1]
        return (red_pixels / total_pixels) * 100 if total_pixels > 0 else 0

def get_mana_fill_percentage(region):
    screenshot = pyautogui.screenshot(region=tuple(region))
    frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    use_gray = CONFIG.get("USE_GRAY_AS_EMPTY", False)
    if use_gray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        threshold_value = 100
        full_pixels = np.sum(gray < threshold_value)
        total_pixels = gray.size
        return (full_pixels / total_pixels) * 100 if total_pixels > 0 else 0
    else:
        tighten = CONFIG.get("COLOR_TIGHTENING", 0)
        center_blue = 110
        half_width_blue = 30 * (1 - tighten/100)
        new_lower_blue = np.array([max(80, int(center_blue - half_width_blue)), 50, 50])
        new_upper_blue = np.array([min(140, int(center_blue + half_width_blue)), 255, 255])
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, new_lower_blue, new_upper_blue)
        blue_pixels = cv2.countNonZero(mask)
        total_pixels = mask.shape[0] * mask.shape[1]
        return (blue_pixels / total_pixels) * 100 if total_pixels > 0 else 0

def select_region_interactively(region_name):
    screenshot = pyautogui.screenshot()
    orig_img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    orig_h, orig_w = orig_img.shape[:2]
    disp_w, disp_h = 800, 600
    resized_img = cv2.resize(orig_img, (disp_w, disp_h))
    pil_img = Image.fromarray(cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB))
    sel_win = tk.Toplevel()
    sel_win.title(f"Select {region_name} Region")
    canvas = tk.Canvas(sel_win, width=disp_w, height=disp_h)
    canvas.pack()
    tk_img = ImageTk.PhotoImage(pil_img)
    canvas.create_image(0, 0, anchor="nw", image=tk_img)
    selection = {"start": None, "end": None, "rect": None}

    def on_button_press(event):
        selection["start"] = (event.x, event.y)
        if selection.get("rect"):
            canvas.delete(selection["rect"])
            selection["rect"] = None

    def on_move_press(event):
        if selection["start"]:
            if selection.get("rect"):
                canvas.delete(selection["rect"])
            selection["end"] = (event.x, event.y)
            selection["rect"] = canvas.create_rectangle(
                selection["start"][0], selection["start"][1],
                event.x, event.y,
                outline="green", width=2
            )

    def on_button_release(event):
        selection["end"] = (event.x, event.y)

    canvas.bind("<ButtonPress-1>", on_button_press)
    canvas.bind("<B1-Motion>", on_move_press)
    canvas.bind("<ButtonRelease-1>", on_button_release)
    region_result = {}

    def on_confirm():
        if selection["start"] and selection["end"]:
            x1, y1 = selection["start"]
            x2, y2 = selection["end"]
            x = min(x1, x2)
            y = min(y1, y2)
            w = abs(x2 - x1)
            h = abs(y2 - y1)
            region_result["region"] = [x, y, w, h]
            sel_win.destroy()
        else:
            messagebox.showwarning("Selection Error", "No region selected!")

    confirm_btn = ttk.Button(sel_win, text="Confirm", command=on_confirm)
    confirm_btn.pack(pady=5)
    sel_win.wait_window()

    if "region" in region_result:
        scale_x = orig_w / disp_w
        scale_y = orig_h / disp_h
        x, y, w, h = region_result["region"]
        scaled_region = [int(x * scale_x), int(y * scale_y),
                         int(w * scale_x), int(h * scale_y)]
        print(f"Selected {region_name} region (original coords): {scaled_region}")
        return scaled_region
    else:
        print("Region selection cancelled.")
        return None

def list_windows():
    windows = []
    def enum_window(hwnd, lParam):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title:
                windows.append(title)
        return True
    win32gui.EnumWindows(enum_window, None)
    return windows

# ------------------------------------------------------------------
# New Helper: Refine Template Crop to Target Color
# ------------------------------------------------------------------
def refine_template_crop(template_img, target_color="red"):
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
        return template_img
    # Apply morphological closing to fill small holes
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    coords = cv2.findNonZero(mask)
    if coords is not None:
        x, y, w, h = cv2.boundingRect(coords)
        cropped = template_img[y:y+h, x:x+w]
        return cropped
    else:
        return template_img

# ------------------------------------------------------------------
# New Helper: Crop by Maximum Color Column with Top/Bottom Crop
# ------------------------------------------------------------------
def crop_by_max_color_column(template_img, target_color="red", slice_width=4, crop_percent=0.05):
    """
    Scan each vertical column for target color pixels.
    Then, take a vertical slice (of fixed width) from the column with the highest count.
    Next, crop off crop_percent of the height from the top and bottom.
    Finally, refine the crop so that only the target color remains.
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
    max_col = int(np.argmax(col_sums))
    h, w, _ = template_img.shape
    left = max(0, max_col - slice_width//2)
    right = min(w, left + slice_width)
    cropped = template_img[:, left:right]
    # Crop crop_percent from top and bottom
    crop_pixels = int(cropped.shape[0] * crop_percent)
    cropped = cropped[crop_pixels:cropped.shape[0]-crop_pixels, :]
    # Refine crop to target color
    cropped = refine_template_crop(cropped, target_color=target_color)
    return cropped

# ------------------------------------------------------------------
# New Helper: Show Auto-Found Regions Popup (800x600) with Confirm Button
# ------------------------------------------------------------------
def show_auto_found_popup(screenshot_cv, hp_region, mp_region):
    orig_h, orig_w, _ = screenshot_cv.shape
    target_size = (800, 600)
    screenshot_resized = cv2.resize(screenshot_cv, target_size, interpolation=cv2.INTER_AREA)
    scale_x = target_size[0] / orig_w
    scale_y = target_size[1] / orig_h
    hp_region_resized = [int(hp_region[0]*scale_x), int(hp_region[1]*scale_y),
                         int(hp_region[2]*scale_x), int(hp_region[3]*scale_y)]
    mp_region_resized = [int(mp_region[0]*scale_x), int(mp_region[1]*scale_y),
                         int(mp_region[2]*scale_x), int(mp_region[3]*scale_y)]
    screenshot_rgb = cv2.cvtColor(screenshot_resized, cv2.COLOR_BGR2RGB)
    img_pil = Image.fromarray(screenshot_rgb)
    draw = ImageDraw.Draw(img_pil)
    draw.rectangle([hp_region_resized[0], hp_region_resized[1],
                    hp_region_resized[0]+hp_region_resized[2], hp_region_resized[1]+hp_region_resized[3]],
                   outline="red", width=3)
    draw.rectangle([mp_region_resized[0], mp_region_resized[1],
                    mp_region_resized[0]+mp_region_resized[2], mp_region_resized[1]+mp_region_resized[3]],
                   outline="blue", width=3)
    popup = tk.Toplevel()
    popup.iconbitmap(r"C:\Users\dabru\Desktop\poe2auto\Flask.ico")
    popup.title("Auto Found Regions")
    popup.geometry("800x600")
    img_tk = ImageTk.PhotoImage(img_pil)
    label = tk.Label(popup, image=img_tk)
    label.image = img_tk
    label.pack()
    confirm_btn = ttk.Button(popup, text="Confirm", command=popup.destroy)
    confirm_btn.pack(pady=5)
    popup.wait_window()

# ------------------------------------------------------------------
# Tkinter GUI Application
# ------------------------------------------------------------------
class AutoPotionApp:
    def __init__(self, root):
        global CONFIG
        self.root = root
        self.root.title("PoE2 Auto-Potion Bot")
        self.root.resizable(True, True)

        load_config()
        load_assets()

        self.current_random_hp_threshold = None
        self.current_random_mp_threshold = None
        self.last_random_update = time.time()

        main_frame = ttk.Frame(root, padding="5")
        main_frame.pack(fill="both", expand=True)
        
        self.status_label = ttk.Label(main_frame, text="Status: Not Monitoring", font=("Arial", 10))
        self.status_label.grid(row=0, column=0, columnspan=3, pady=3, sticky="w")
        
        # Target Window Selection
        self.target_window_label = ttk.Label(
            main_frame,
            text=f"Target Window: {CONFIG.get('TARGET_WINDOW_TITLE')}",
            font=("Arial", 8)
        )
        self.target_window_label.grid(row=1, column=0, padx=3, sticky="w")
        self.select_target_window_button = ttk.Button(
            main_frame,
            text="Select Target Window",
            command=self.select_target_window
        )
        self.select_target_window_button.grid(row=1, column=1, padx=3, sticky="w")
        
        self.hp_region_label = ttk.Label(
            main_frame,
            text=f"HP Region: {CONFIG.get('HP_REGION') or 'Not set'}",
            font=("Arial", 8)
        )
        self.hp_region_label.grid(row=2, column=0, padx=3, sticky="w")
        self.mp_region_label = ttk.Label(
            main_frame,
            text=f"MP Region: {CONFIG.get('MP_REGION') or 'Not set'}",
            font=("Arial", 8)
        )
        self.mp_region_label.grid(row=2, column=1, padx=3, sticky="w")
        
        hp_frame = ttk.LabelFrame(main_frame, text="HP Fill & Thresholds", padding="5")
        hp_frame.grid(row=3, column=0, columnspan=3, pady=3, sticky="ew")
        hp_label = "HP Empty" if CONFIG.get("USE_GRAY_AS_EMPTY", False) else "HP"
        self.hp_slider = DualThresholdFillSlider(
            hp_frame,
            width=250,
            height=30,
            fill_color="red",
            label_text=hp_label,
            lower_initial=CONFIG.get("THRESHOLD_HP_LOWER", DEFAULT_THRESHOLD_HP_LOWER),
            upper_initial=CONFIG.get("THRESHOLD_HP_UPPER", DEFAULT_THRESHOLD_HP_UPPER),
            threshold_change_callback=self.update_hp_threshold_entries
        )
        self.hp_slider.pack(pady=2)
        
        mp_frame = ttk.LabelFrame(main_frame, text="MP Fill & Thresholds", padding="5")
        mp_frame.grid(row=4, column=0, columnspan=3, pady=3, sticky="ew")
        self.mp_slider = DualThresholdFillSlider(
            mp_frame,
            width=250,
            height=30,
            fill_color="blue",
            label_text="MP",
            lower_initial=CONFIG.get("THRESHOLD_MP_LOWER", DEFAULT_THRESHOLD_MP_LOWER),
            upper_initial=CONFIG.get("THRESHOLD_MP_UPPER", DEFAULT_THRESHOLD_MP_UPPER),
            threshold_change_callback=self.update_mp_threshold_entries
        )
        self.mp_slider.pack(pady=2)
        
        region_frame = ttk.Frame(main_frame)
        region_frame.grid(row=5, column=0, columnspan=3, pady=3, sticky="ew")
        self.select_hp_button = ttk.Button(
            region_frame,
            text="Select HP Region",
            command=lambda: self.select_region("HP")
        )
        self.select_hp_button.pack(side="left", expand=True, fill="x", padx=2)
        self.select_mp_button = ttk.Button(
            region_frame,
            text="Select MP Region",
            command=lambda: self.select_region("MP")
        )
        self.select_mp_button.pack(side="left", expand=True, fill="x", padx=2)
        self.auto_find_button = ttk.Button(
            region_frame,
            text="Auto Find HP/MP Regions",
            command=self.auto_find_regions
        )
        self.auto_find_button.pack(side="left", expand=True, fill="x", padx=2)
        
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="5")
        settings_frame.grid(row=6, column=0, columnspan=3, pady=3, sticky="ew")
        
        ttk.Label(settings_frame, text="HP Lower Threshold:", font=("Arial", 8)).grid(row=0, column=0, padx=3, pady=2)
        self.hp_lower_var = tk.DoubleVar(value=CONFIG.get("THRESHOLD_HP_LOWER", DEFAULT_THRESHOLD_HP_LOWER))
        self.hp_lower_entry = ttk.Entry(settings_frame, textvariable=self.hp_lower_var, width=8)
        self.hp_lower_entry.grid(row=0, column=1, padx=3, pady=2)
        self.hp_lower_entry.bind("<FocusOut>", self.update_hp_slider_from_entry)
        self.hp_lower_entry.bind("<Return>", self.update_hp_slider_from_entry)
        
        ttk.Label(settings_frame, text="HP Upper Threshold:", font=("Arial", 8)).grid(row=0, column=2, padx=3, pady=2)
        self.hp_upper_var = tk.DoubleVar(value=CONFIG.get("THRESHOLD_HP_UPPER", DEFAULT_THRESHOLD_HP_UPPER))
        self.hp_upper_entry = ttk.Entry(settings_frame, textvariable=self.hp_upper_var, width=8)
        self.hp_upper_entry.grid(row=0, column=3, padx=3, pady=2)
        self.hp_upper_entry.bind("<FocusOut>", self.update_hp_slider_from_entry)
        self.hp_upper_entry.bind("<Return>", self.update_hp_slider_from_entry)
        
        ttk.Label(settings_frame, text="MP Lower Threshold:", font=("Arial", 8)).grid(row=1, column=0, padx=3, pady=2)
        self.mp_lower_var = tk.DoubleVar(value=CONFIG.get("THRESHOLD_MP_LOWER", DEFAULT_THRESHOLD_MP_LOWER))
        self.mp_lower_entry = ttk.Entry(settings_frame, textvariable=self.mp_lower_var, width=8)
        self.mp_lower_entry.grid(row=1, column=1, padx=3, pady=2)
        self.mp_lower_entry.bind("<FocusOut>", self.update_mp_slider_from_entry)
        self.mp_lower_entry.bind("<Return>", self.update_mp_slider_from_entry)
        
        ttk.Label(settings_frame, text="MP Upper Threshold:", font=("Arial", 8)).grid(row=1, column=2, padx=3, pady=2)
        self.mp_upper_var = tk.DoubleVar(value=CONFIG.get("THRESHOLD_MP_UPPER", DEFAULT_THRESHOLD_MP_UPPER))
        self.mp_upper_entry = ttk.Entry(settings_frame, textvariable=self.mp_upper_var, width=8)
        self.mp_upper_entry.grid(row=1, column=3, padx=3, pady=2)
        self.mp_upper_entry.bind("<FocusOut>", self.update_mp_slider_from_entry)
        self.mp_upper_entry.bind("<Return>", self.update_mp_slider_from_entry)
        
        ttk.Label(settings_frame, text="Color Tuning (%):", font=("Arial", 8)).grid(row=2, column=0, padx=3, pady=2)
        self.color_tighten_var = tk.IntVar(value=CONFIG.get("COLOR_TIGHTENING", DEFAULT_COLOR_TIGHTENING))
        ttk.Entry(settings_frame, textvariable=self.color_tighten_var, width=8).grid(row=2, column=1, padx=3, pady=2)
        
        ttk.Label(settings_frame, text="Health Potion Delay:", font=("Arial", 8)).grid(row=3, column=0, padx=3, pady=2)
        self.health_pot_delay_var = tk.DoubleVar(value=CONFIG.get("HEALTH_POTION_DELAY", DEFAULT_HEALTH_POTION_DELAY))
        ttk.Entry(settings_frame, textvariable=self.health_pot_delay_var, width=8).grid(row=3, column=1, padx=3, pady=2)
        ttk.Label(settings_frame, text="Mana Potion Delay:", font=("Arial", 8)).grid(row=3, column=2, padx=3, pady=2)
        self.mana_pot_delay_var = tk.DoubleVar(value=CONFIG.get("MANA_POTION_DELAY", DEFAULT_MANA_POTION_DELAY))
        ttk.Entry(settings_frame, textvariable=self.mana_pot_delay_var, width=8).grid(row=3, column=3, padx=3, pady=2)
        
        ttk.Label(settings_frame, text="Toggle Key:", font=("Arial", 8)).grid(row=4, column=0, padx=3, pady=2)
        self.toggle_key_var = tk.StringVar(value=CONFIG.get("TOGGLE_KEY", DEFAULT_TOGGLE_KEY))
        ttk.Entry(settings_frame, textvariable=self.toggle_key_var, width=8).grid(row=4, column=1, padx=3, pady=2)
        ttk.Label(settings_frame, text="Pause Key:", font=("Arial", 8)).grid(row=4, column=2, padx=3, pady=2)
        self.pause_key_var = tk.StringVar(value=CONFIG.get("PAUSE_KEY", DEFAULT_PAUSE_KEY))
        ttk.Entry(settings_frame, textvariable=self.pause_key_var, width=8).grid(row=4, column=3, padx=3, pady=2)
        
        self.use_gray_var = tk.BooleanVar(value=CONFIG.get("USE_GRAY_AS_EMPTY", False))
        self.use_gray_check = ttk.Checkbutton(settings_frame, text="Use Gray/Black as Empty", variable=self.use_gray_var, command=self.toggle_gray_mode)
        self.use_gray_check.grid(row=5, column=0, columnspan=2, padx=3, pady=2)
        
        self.save_all_button = ttk.Button(settings_frame, text="Save All Settings", command=self.save_all_settings)
        self.save_all_button.grid(row=6, column=0, columnspan=4, padx=5, pady=2)
        
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.grid(row=7, column=0, columnspan=3, pady=3, sticky="nsew")
        self.log_text = tk.Text(log_frame, height=6, state="disabled", font=("Arial", 8))
        self.log_text.pack(fill="both", expand=True)
        
        self.toggle_button = ttk.Button(main_frame, text="Start Monitoring", command=self.toggle_monitoring)
        self.toggle_button.grid(row=8, column=0, columnspan=3, pady=5)
        
        self.monitoring = False
        self.paused = False
        self.monitor_thread = None
        self.hotkey_handles = []
        self.update_hotkeys()

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
            lower = float(self.hp_lower_var.get())
            upper = float(self.hp_upper_var.get())
            self.hp_slider.lower_threshold = lower
            self.hp_slider.upper_threshold = upper
            self.hp_slider.draw()
        except Exception:
            pass

    def update_mp_slider_from_entry(self, event):
        try:
            lower = float(self.mp_lower_var.get())
            upper = float(self.mp_upper_var.get())
            self.mp_slider.lower_threshold = lower
            self.mp_slider.upper_threshold = upper
            self.mp_slider.draw()
        except Exception:
            pass

    def toggle_gray_mode(self):
        CONFIG["USE_GRAY_AS_EMPTY"] = self.use_gray_var.get()
        save_config()
        mode_text = "HP Empty" if CONFIG["USE_GRAY_AS_EMPTY"] else "HP"
        self.hp_slider.label_text = mode_text
        self.hp_slider.draw()
        self.log_message(f"Health mode set to {'Gray/Black (Empty)' if CONFIG['USE_GRAY_AS_EMPTY'] else 'Red (Full)'}")

    def update_hotkeys(self):
        if self.hotkey_handles:
            for handle in self.hotkey_handles:
                keyboard.remove_hotkey(handle)
            self.hotkey_handles = []
        toggle_key = CONFIG.get("TOGGLE_KEY", DEFAULT_TOGGLE_KEY)
        pause_key = CONFIG.get("PAUSE_KEY", DEFAULT_PAUSE_KEY)
        self.hotkey_handles = [
            keyboard.add_hotkey(toggle_key, self.hotkey_toggle),
            keyboard.add_hotkey(pause_key, self.hotkey_pause)
        ]
        self.log_message(f"Hotkeys set: Toggle - {toggle_key}, Pause - {pause_key}")

    def hotkey_toggle(self):
        self.root.after(0, self.toggle_monitoring)

    def hotkey_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.root.after(0, self.status_label.config, {"text": "Status: Paused (Hotkey)"})
            self.log_message("Monitoring paused via hotkey.")
        else:
            self.root.after(0, self.status_label.config, {"text": "Status: Monitoring"})
            self.log_message("Monitoring resumed via hotkey.")

    def save_all_settings(self):
        CONFIG["COLOR_TIGHTENING"] = self.color_tighten_var.get()
        CONFIG["HEALTH_POTION_DELAY"] = self.health_pot_delay_var.get()
        CONFIG["MANA_POTION_DELAY"] = self.mana_pot_delay_var.get()
        CONFIG["TOGGLE_KEY"] = self.toggle_key_var.get()
        CONFIG["PAUSE_KEY"] = self.pause_key_var.get()
        CONFIG["USE_GRAY_AS_EMPTY"] = self.use_gray_var.get()
        CONFIG["THRESHOLD_HP_LOWER"] = self.hp_lower_var.get()
        CONFIG["THRESHOLD_HP_UPPER"] = self.hp_upper_var.get()
        CONFIG["THRESHOLD_MP_LOWER"] = self.mp_lower_var.get()
        CONFIG["THRESHOLD_MP_UPPER"] = self.mp_upper_var.get()
        save_config()
        self.hp_slider.lower_threshold = self.hp_lower_var.get()
        self.hp_slider.upper_threshold = self.hp_upper_var.get()
        self.mp_slider.lower_threshold = self.mp_lower_var.get()
        self.mp_slider.upper_threshold = self.mp_upper_var.get()
        self.hp_slider.draw()
        self.mp_slider.draw()
        self.update_hotkeys()
        messagebox.showinfo("Settings Saved", "All settings have been saved successfully!")

    def log_message(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def select_region(self, region_name):
        roi = select_region_interactively(region_name)
        if roi:
            if region_name == "HP":
                CONFIG["HP_REGION"] = roi
                self.hp_region_label.config(text=f"HP Region: {roi}")
            elif region_name == "MP":
                CONFIG["MP_REGION"] = roi
                self.mp_region_label.config(text=f"MP Region: {roi}")
            save_config()
            messagebox.showinfo("Configuration Updated", f"{region_name} region updated successfully!")
        else:
            messagebox.showwarning("Configuration", "Region selection cancelled.")

    def select_target_window(self):
        win_list = list_windows()
        if not win_list:
            messagebox.showerror("Error", "No windows found!")
            return
        sel_win = tk.Toplevel(self.root)
        sel_win.title("Select Target Window")
        tk.Label(sel_win, text="Select a window:").pack(pady=5)
        listbox = tk.Listbox(sel_win, width=50, height=15)
        listbox.pack(padx=5, pady=5)
        for win_title in win_list:
            listbox.insert(tk.END, win_title)
        def on_select():
            try:
                selection = listbox.get(listbox.curselection())
                CONFIG["TARGET_WINDOW_TITLE"] = selection
                save_config()
                self.target_window_label.config(text=f"Target Window: {selection}")
                sel_win.destroy()
                messagebox.showinfo("Target Window", f"Target window set to: {selection}")
            except Exception:
                messagebox.showwarning("Selection Error", "No window selected!")
        confirm_btn = ttk.Button(sel_win, text="Confirm", command=on_select)
        confirm_btn.pack(pady=5)

    def auto_find_regions(self):
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
        hp_template_path = os.path.join(SCRIPT_DIR, "health.png")
        mp_template_path = os.path.join(SCRIPT_DIR, "mana.png")
        if not os.path.exists(hp_template_path) or not os.path.exists(mp_template_path):
            messagebox.showerror("Error", "Template images for HP and MP not found!")
            return
        hp_template = cv2.imread(hp_template_path, cv2.IMREAD_COLOR)
        mp_template = cv2.imread(mp_template_path, cv2.IMREAD_COLOR)
        # Refine each template to include only target color
        hp_refined = refine_template_crop(hp_template, target_color="red")
        mp_refined = refine_template_crop(mp_template, target_color="blue")
        # Crop a vertical slice from the column with the most target color, then crop 5% from top and bottom.
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
        hp_region = [x + max_loc_hp[0], y + max_loc_hp[1], hp_w, hp_h]
        mp_region = [x + max_loc_mp[0], y + max_loc_mp[1], mp_w, mp_h]
        show_auto_found_popup(screenshot_cv, hp_region, mp_region)
        CONFIG["HP_REGION"] = hp_region
        CONFIG["MP_REGION"] = mp_region
        save_config()
        self.hp_region_label.config(text=f"HP Region: {hp_region}")
        self.mp_region_label.config(text=f"MP Region: {mp_region}")
        messagebox.showinfo("Auto Detection", "Health and Mana regions updated automatically!")

    def toggle_monitoring(self):
        self.monitoring = not self.monitoring
        if self.monitoring:
            self.toggle_button.config(text="Stop Monitoring")
            self.log_message("Monitoring started.")
            self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
            self.monitor_thread.start()
            print("Monitoring started.")
        else:
            self.toggle_button.config(text="Start Monitoring")
            self.log_message("Monitoring stopped.")
            print("Monitoring stopped.")

    def monitor_loop(self):
        self.dead = False
        while self.monitoring:
            try:
                if self.paused:
                    self.root.after(0, self.status_label.config, {"text": "Status: Paused"})
                    time.sleep(MONITOR_SLEEP_TIME)
                    continue
                load_config()
                hp_fill = get_health_fill_percentage(CONFIG["HP_REGION"]) if CONFIG.get("HP_REGION") else 0
                mp_fill = get_mana_fill_percentage(CONFIG["MP_REGION"]) if CONFIG.get("MP_REGION") else 0
                effective_hp = hp_fill
                self.root.after(0, self.hp_slider.set_fill, hp_fill)
                self.root.after(0, self.mp_slider.set_fill, mp_fill)
                if effective_hp <= 1:
                    if mp_fill <= 1:
                        self.root.after(0, self.status_label.config, {"text": "Status: Pause Menu"})
                    else:
                        self.root.after(0, self.status_label.config, {"text": "Status: Dead"})
                        if not self.dead:
                            self.dead = True
                            self.root.after(0, self.log_message, f"[{time.strftime('%H:%M:%S')}] Dead detected! Stopping potion use.")
                    time.sleep(MONITOR_SLEEP_TIME)
                    continue
                else:
                    self.dead = False
                    self.root.after(0, self.status_label.config, {"text": "Status: Monitoring"})
                health_delay = CONFIG.get("HEALTH_POTION_DELAY", DEFAULT_HEALTH_POTION_DELAY)
                mana_delay = CONFIG.get("MANA_POTION_DELAY", DEFAULT_MANA_POTION_DELAY)
                hp_lower = self.hp_slider.lower_threshold
                hp_upper = self.hp_slider.upper_threshold
                mp_lower = self.mp_slider.lower_threshold
                mp_upper = self.mp_slider.upper_threshold
                current_time = time.time()
                if current_time - self.last_random_update >= 0.5:
                    self.current_random_hp_threshold = random.uniform(hp_lower, hp_upper)
                    self.current_random_mp_threshold = random.uniform(mp_lower, mp_upper)
                    self.last_random_update = current_time
                    self.hp_slider.random_threshold = self.current_random_hp_threshold
                    self.mp_slider.random_threshold = self.current_random_mp_threshold
                    self.hp_slider.draw()
                    self.mp_slider.draw()
                if effective_hp < hp_lower:
                    self.use_potion(HEALTH_POTION_KEY, effective_hp, "Health", health_delay)
                elif effective_hp < self.current_random_hp_threshold:
                    self.use_potion(HEALTH_POTION_KEY, effective_hp, "Health", health_delay)
                if mp_fill < mp_lower:
                    self.use_potion(MANA_POTION_KEY, mp_fill, "Mana", mana_delay)
                elif mp_fill < self.current_random_mp_threshold:
                    self.use_potion(MANA_POTION_KEY, mp_fill, "Mana", mana_delay)
            except Exception as e:
                err_msg = f"Monitoring error: {e}"
                print(err_msg)
                self.root.after(0, self.log_message, err_msg)
            time.sleep(MONITOR_SLEEP_TIME)

    def use_potion(self, key, fill_value, label, hold_delay):
        pyautogui.press(key)
        msg = f"[{time.strftime('%H:%M:%S')}] {label} potion used! ({label} fill: {fill_value:.1f}%)"
        self.root.after(0, self.log_message, msg)
        print(msg)
        time.sleep(hold_delay)

def main():
    load_config()
    load_assets()
    root = tk.Tk()
    root.iconbitmap(r"C:\Users\dabru\Desktop\poe2auto\Flask.ico")
    app = AutoPotionApp(root)
    root.mainloop()
    

if __name__ == "__main__":
    main()

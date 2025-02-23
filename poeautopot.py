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

# ------------------------------------------------------------------
# Determine the script's directory so we can load files from there
# ------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

# Default maximum values (for configuration purposes)
DEFAULT_MAX_HP = 1000
DEFAULT_MAX_MP = 6932

# Default thresholds for triggering potions (in percentage)
DEFAULT_THRESHOLD_HP = 60
DEFAULT_THRESHOLD_MP = 60

# Default color tightening (0% means use full default ranges)
DEFAULT_COLOR_TIGHTENING = 0

# Default key press delay (in seconds)
DEFAULT_KEY_PRESS_DELAY = 0.5

# Key bindings for potions
HEALTH_POTION_KEY = "1"
MANA_POTION_KEY = "2"

# Monitoring speed (seconds)
MONITOR_SLEEP_TIME = 0.2

# ------------------------------------------------------------------
# Paths to images (absolute paths)
# ------------------------------------------------------------------
LOADING_SCREEN_IMAGE = os.path.join(SCRIPT_DIR, "loading_screen_gears.png")
DEATH_SCREEN_IMAGE   = os.path.join(SCRIPT_DIR, "death_screen.png")
FLASK_IMAGE          = os.path.join(SCRIPT_DIR, "flask.png")

# Global configuration dictionary.
CONFIG = {}

# Determine the resampling filter for Pillow resizing.
try:
    RESAMPLE_FILTER = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE_FILTER = Image.ANTIALIAS

# ------------------------------------------------------------------
# Custom FillSlider Widget
# ------------------------------------------------------------------
class FillSlider(tk.Canvas):
    def __init__(self, master, width=200, height=20, fill_color="red", label_text="Fill", initial_threshold=50, **kwargs):
        super().__init__(master, width=width, height=height, **kwargs)
        self.width = width
        self.height = height
        self.fill_color = fill_color
        self.threshold = initial_threshold  # value between 0 and 100
        self.current_fill = 0  # value between 0 and 100; updated externally
        self.label_text = label_text

        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
        self.draw()

    def draw(self):
        self.delete("all")
        # Draw the background bar.
        self.create_rectangle(0, 0, self.width, self.height, fill="lightgray", outline="")
        # Draw the fill portion.
        fill_width = (self.current_fill / 100) * self.width
        self.create_rectangle(0, 0, fill_width, self.height, fill=self.fill_color, outline="")
        # Draw the threshold marker (vertical line).
        threshold_x = (self.threshold / 100) * self.width
        self.create_line(threshold_x, 0, threshold_x, self.height, fill="black", width=2)
        # Draw a label showing the current fill percentage.
        self.create_text(self.width/2, self.height/2, text=f"{self.label_text}: {self.current_fill:.0f}%", fill="white", font=("Arial", 10))

    def set_fill(self, fill_value):
        """Update the current fill value and redraw."""
        self.current_fill = max(0, min(100, fill_value))
        self.draw()

    def get_threshold(self):
        """Return the current threshold value."""
        return self.threshold

    def on_click(self, event):
        # Update the threshold marker based on the click position.
        self.threshold = (event.x / self.width) * 100
        self.draw()

    def on_drag(self, event):
        # Update the threshold marker as the user drags.
        self.threshold = (event.x / self.width) * 100
        self.draw()

# ------------------------------------------------------------------
# Utility Functions (Configuration, Window, etc.)
# ------------------------------------------------------------------
def get_game_window_rect():
    """Return the Path of Exile 2 window rectangle as (left, top, width, height)."""
    hwnd = win32gui.FindWindow(None, "Path of Exile 2")
    if hwnd == 0:
        print("Game window not found!")
        return None
    rect = win32gui.GetWindowRect(hwnd)
    left, top, right, bottom = rect
    return (left, top, right - left, bottom - top)

def load_config():
    """Load configuration from file or create defaults."""
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
            "MAX_HP": DEFAULT_MAX_HP,
            "MAX_MP": DEFAULT_MAX_MP,
            "THRESHOLD_HP": DEFAULT_THRESHOLD_HP,
            "THRESHOLD_MP": DEFAULT_THRESHOLD_MP,
            "COLOR_TIGHTENING": DEFAULT_COLOR_TIGHTENING,
            "KEY_PRESS_DELAY": DEFAULT_KEY_PRESS_DELAY,
            "WINDOW_RESOLUTION": [gw, gh]
        }
        save_config()
        print("Default configuration created and saved.")

def save_config():
    """Save configuration to file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(CONFIG, f, indent=4)
    print("Configuration saved:", CONFIG)

def load_assets():
    """
    Load assets for detection.
    (For this example, we load the death screen image if available.)
    """
    if os.path.exists(DEATH_SCREEN_IMAGE):
        _ = cv2.imread(DEATH_SCREEN_IMAGE, cv2.IMREAD_COLOR)
        print(f"Loaded death screen template from {DEATH_SCREEN_IMAGE}")
    else:
        print(f"No death screen image found at {DEATH_SCREEN_IMAGE}")

def get_health_fill_percentage(region):
    """Compute HP fill percentage using HSV detection."""
    tighten = CONFIG.get("COLOR_TIGHTENING", 0)
    center1 = 5
    half_width1 = 5 * (1 - tighten/100)
    new_lower_red1 = np.array([max(0, int(center1 - half_width1)), 70, 50])
    new_upper_red1 = np.array([min(10, int(center1 + half_width1)), 255, 255])
    center2 = 175
    half_width2 = 5 * (1 - tighten/100)
    new_lower_red2 = np.array([max(170, int(center2 - half_width2)), 70, 50])
    new_upper_red2 = np.array([min(180, int(center2 + half_width2)), 255, 255])
    
    screenshot = pyautogui.screenshot(region=tuple(region))
    frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, new_lower_red1, new_upper_red1)
    mask2 = cv2.inRange(hsv, new_lower_red2, new_upper_red2)
    mask = cv2.bitwise_or(mask1, mask2)
    red_pixels = cv2.countNonZero(mask)
    total_pixels = mask.shape[0] * mask.shape[1]
    return (red_pixels / total_pixels) * 100 if total_pixels > 0 else 0

def get_mana_fill_percentage(region):
    """Compute MP fill percentage using HSV detection."""
    tighten = CONFIG.get("COLOR_TIGHTENING", 0)
    center_blue = 110
    half_width_blue = 30 * (1 - tighten/100)
    new_lower_blue = np.array([max(80, int(center_blue - half_width_blue)), 50, 50])
    new_upper_blue = np.array([min(140, int(center_blue + half_width_blue)), 255, 255])
    
    screenshot = pyautogui.screenshot(region=tuple(region))
    frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, new_lower_blue, new_upper_blue)
    blue_pixels = cv2.countNonZero(mask)
    total_pixels = mask.shape[0] * mask.shape[1]
    return (blue_pixels / total_pixels) * 100 if total_pixels > 0 else 0

def select_region_interactively(region_name):
    """Allow the user to select a region via a Tkinter Toplevel window with a canvas (800x600)."""
    screenshot = pyautogui.screenshot()
    orig_img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    orig_h, orig_w = orig_img.shape[:2]
    disp_w, disp_h = 800, 600
    resized_img = cv2.resize(orig_img, (disp_w, disp_h))
    from PIL import Image, ImageTk
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
            selection["rect"] = canvas.create_rectangle(selection["start"][0], selection["start"][1],
                                                         event.x, event.y, outline="green", width=2)
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
        scaled_region = [int(x * scale_x), int(y * scale_y), int(w * scale_x), int(h * scale_y)]
        print(f"Selected {region_name} region (original coords): {scaled_region}")
        return scaled_region
    else:
        print("Region selection cancelled.")
        return None

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

        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        self.status_label = ttk.Label(main_frame, text="Status: Not Monitoring", font=("Arial", 14))
        self.status_label.grid(row=0, column=0, columnspan=2, pady=5, sticky="w")

        self.hp_region_label = ttk.Label(main_frame, text=f"HP Region: {CONFIG.get('HP_REGION') if CONFIG.get('HP_REGION') else 'Not set'}", font=("Arial", 10))
        self.hp_region_label.grid(row=1, column=0, padx=5, sticky="w")
        self.mp_region_label = ttk.Label(main_frame, text=f"MP Region: {CONFIG.get('MP_REGION') if CONFIG.get('MP_REGION') else 'Not set'}", font=("Arial", 10))
        self.mp_region_label.grid(row=1, column=1, padx=5, sticky="w")

        # Create custom FillSlider widgets for flask fill and threshold.
        slider_frame = ttk.LabelFrame(main_frame, text="Flask Fill & Threshold", padding="5")
        slider_frame.grid(row=2, column=0, columnspan=2, pady=5, sticky="ew")
        self.hp_slider = FillSlider(slider_frame, width=200, height=20, fill_color="red", label_text="HP", initial_threshold=CONFIG.get("THRESHOLD_HP", DEFAULT_THRESHOLD_HP))
        self.hp_slider.grid(row=0, column=0, padx=5, pady=5)
        self.mp_slider = FillSlider(slider_frame, width=200, height=20, fill_color="blue", label_text="MP", initial_threshold=CONFIG.get("THRESHOLD_MP", DEFAULT_THRESHOLD_MP))
        self.mp_slider.grid(row=1, column=0, padx=5, pady=5)

        # Region selection buttons.
        region_frame = ttk.Frame(main_frame)
        region_frame.grid(row=3, column=0, columnspan=2, pady=5, sticky="ew")
        self.select_hp_button = ttk.Button(region_frame, text="Select HP Region", command=lambda: self.select_region("HP"))
        self.select_hp_button.pack(side="left", expand=True, fill="x", padx=2)
        self.select_mp_button = ttk.Button(region_frame, text="Select MP Region", command=lambda: self.select_region("MP"))
        self.select_mp_button.pack(side="left", expand=True, fill="x", padx=2)

        # MAX values frame.
        max_frame = ttk.LabelFrame(main_frame, text="MAX Values", padding="5")
        max_frame.grid(row=4, column=0, pady=5, sticky="ew")
        ttk.Label(max_frame, text="MAX_HP: ").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.max_hp_var = tk.IntVar(value=CONFIG.get("MAX_HP", DEFAULT_MAX_HP))
        ttk.Entry(max_frame, textvariable=self.max_hp_var, width=10).grid(row=0, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(max_frame, text="MAX_MP: ").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.max_mp_var = tk.IntVar(value=CONFIG.get("MAX_MP", DEFAULT_MAX_MP))
        ttk.Entry(max_frame, textvariable=self.max_mp_var, width=10).grid(row=1, column=1, padx=5, pady=2, sticky="w")
        self.save_max_button = ttk.Button(max_frame, text="Save MAX Values", command=self.save_max_values)
        self.save_max_button.grid(row=2, column=0, columnspan=2, pady=5)

        # Color tuning frame.
        color_frame = ttk.LabelFrame(main_frame, text="Color Tuning (%)", padding="5")
        color_frame.grid(row=5, column=0, columnspan=2, pady=5, sticky="ew")
        ttk.Label(color_frame, text="Tightening (%): ").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.color_tighten_var = tk.IntVar(value=CONFIG.get("COLOR_TIGHTENING", DEFAULT_COLOR_TIGHTENING))
        ttk.Entry(color_frame, textvariable=self.color_tighten_var, width=10).grid(row=0, column=1, padx=5, pady=2, sticky="w")
        self.save_color_button = ttk.Button(color_frame, text="Save Color Tuning", command=self.save_color_tuning)
        self.save_color_button.grid(row=1, column=0, columnspan=2, pady=5)

        # Key Press Delay frame.
        delay_frame = ttk.LabelFrame(main_frame, text="Key Press Delay", padding="5")
        delay_frame.grid(row=6, column=0, columnspan=2, pady=5, sticky="ew")
        ttk.Label(delay_frame, text="Delay (sec): ").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.key_delay_var = tk.DoubleVar(value=CONFIG.get("KEY_PRESS_DELAY", DEFAULT_KEY_PRESS_DELAY))
        ttk.Entry(delay_frame, textvariable=self.key_delay_var, width=10).grid(row=0, column=1, padx=5, pady=2, sticky="w")
        self.save_delay_button = ttk.Button(delay_frame, text="Save Delay", command=self.save_key_delay)
        self.save_delay_button.grid(row=1, column=0, columnspan=2, pady=5)

        # Log frame.
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.grid(row=7, column=0, columnspan=2, pady=5, sticky="nsew")
        self.log_text = tk.Text(log_frame, height=10, state="disabled")
        self.log_text.pack(fill="both", expand=True)

        # Start/Stop Monitoring button.
        self.toggle_button = ttk.Button(main_frame, text="Start Monitoring", command=self.toggle_monitoring)
        self.toggle_button.grid(row=8, column=0, columnspan=2, pady=10)

        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(7, weight=1)

        self.monitoring = False
        self.monitor_thread = None

    def log_message(self, message):
        """Append a message to the log text widget."""
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def select_region(self, region_name):
        global CONFIG
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
            load_config()
            self.hp_region_label.config(text=f"HP Region: {CONFIG.get('HP_REGION') if CONFIG.get('HP_REGION') else 'Not set'}")
            self.mp_region_label.config(text=f"MP Region: {CONFIG.get('MP_REGION') if CONFIG.get('MP_REGION') else 'Not set'}")

    def save_max_values(self):
        global CONFIG
        CONFIG["MAX_HP"] = self.max_hp_var.get()
        CONFIG["MAX_MP"] = self.max_mp_var.get()
        save_config()
        messagebox.showinfo("Configuration Updated", "MAX values updated successfully!")

    def save_color_tuning(self):
        global CONFIG
        CONFIG["COLOR_TIGHTENING"] = self.color_tighten_var.get()
        save_config()
        messagebox.showinfo("Configuration Updated", "Color tuning updated successfully!")

    def save_key_delay(self):
        global CONFIG
        CONFIG["KEY_PRESS_DELAY"] = self.key_delay_var.get()
        save_config()
        messagebox.showinfo("Configuration Updated", "Key press delay updated successfully!")

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
        while self.monitoring:
            try:
                load_config()
                if CONFIG.get("HP_REGION"):
                    hp_fill = get_health_fill_percentage(CONFIG["HP_REGION"])
                else:
                    hp_fill = 0

                if CONFIG.get("MP_REGION"):
                    mp_fill = get_mana_fill_percentage(CONFIG["MP_REGION"])
                else:
                    mp_fill = 0

                # Update the fill sliders with the current fill values.
                self.root.after(0, self.hp_slider.set_fill, hp_fill)
                self.root.after(0, self.mp_slider.set_fill, mp_fill)

                # Update status based on current fills.
                if hp_fill == 0 and mp_fill == 0:
                    self.root.after(0, self.status_label.config, {"text": "Status: Loading Screen"})
                else:
                    self.root.after(0, self.status_label.config, {"text": "Status: Monitoring"})
                    current_hp_threshold = self.hp_slider.get_threshold()
                    current_mp_threshold = self.mp_slider.get_threshold()
                    print(f"Current HP fill: {hp_fill:.1f}%, Threshold: {current_hp_threshold:.1f}%")
                    print(f"Current MP fill: {mp_fill:.1f}%, Threshold: {current_mp_threshold:.1f}%")

                    # Use key press delay from configuration.
                    delay = CONFIG.get("KEY_PRESS_DELAY", DEFAULT_KEY_PRESS_DELAY)

                    if hp_fill < current_hp_threshold and CONFIG.get("HP_REGION"):
                        pyautogui.press(HEALTH_POTION_KEY)
                        msg = f"[{time.strftime('%H:%M:%S')}] Health potion used! (HP fill: {hp_fill:.1f}%)"
                        self.root.after(0, self.log_message, msg)
                        print(msg)
                        time.sleep(delay)

                    if mp_fill < current_mp_threshold and CONFIG.get("MP_REGION"):
                        pyautogui.press(MANA_POTION_KEY)
                        msg = f"[{time.strftime('%H:%M:%S')}] Mana potion used! (MP fill: {mp_fill:.1f}%)"
                        self.root.after(0, self.log_message, msg)
                        print(msg)
                        time.sleep(delay)

            except Exception as e:
                err_msg = f"Monitoring error: {e}"
                print(err_msg)
                self.root.after(0, self.log_message, err_msg)

            time.sleep(MONITOR_SLEEP_TIME)

def main():
    load_config()
    load_assets()
    root = tk.Tk()
    app = AutoPotionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

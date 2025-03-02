PoE Auto-Potion Bot ⚔️💊
A Python-based auto-potion bot for Path of Exile! This tool works for both PoE 1 and PoE 2, with the auto-location feature optimized for PoE 2. It monitors your health and mana bars and automatically uses potions when needed—so you can focus on the action! 🚀

✨ Key Features
Auto Location Detection
The bot automatically finds your health (❤️) and mana (💙) bar regions by processing template images (health.png and mana.png).

Template Refinement:
It thresholds the images to keep only the target colors (red for health, blue for mana).
Scans vertical columns to find the area with the most target pixels.
Crops a fixed-width slice and removes a small percentage from the top and bottom for accurate readings.
Manual Region Selection
If auto-detection isn't perfect, manually select the regions via an interactive window. 🎯

Graphical User Interface (GUI)
A friendly Tkinter-based control panel to:

View real-time health/mana percentages.
Adjust thresholds with entry fields and dual sliders.
Choose your target window from a list of active windows.
Save settings (stored in config.json).
Hotkey Support
Start/stop and pause the bot with global hotkeys (default: F8 to toggle, F9 to pause). ⌨️

Resolution Independent
The detection and popup are scaled so that it works on any resolution!

🔍 How It Works
Screenshot Capture
The bot uses pyautogui to capture the target game window based on the selected window title.

Template Matching

Refine Template Crop:
The function refine_template_crop(template_img, target_color) converts the template image to HSV, thresholds for red or blue, and crops to the bounding box of the target color.
Crop by Maximum Color Column:
The function crop_by_max_color_column(template_img, target_color, slice_width, crop_percent):
Scans each vertical column to find the one with the highest target color intensity.
Extracts a vertical slice (default 4 pixels wide) from that column.
Crops off a small percentage (default 5% for mana and 2% for health) from the top and bottom.
Finally, refines the crop so only the target color remains.
Auto-Found Regions Popup:
A popup (800×600) shows the detected regions with red (HP) and blue (MP) rectangles overlaid. Click "Confirm" to accept the selection.
Monitoring & Potion Usage
The bot continuously reads the percentage of target pixels from your health and mana regions. If these fall below your set thresholds, it simulates key presses to use the appropriate potion. 💥

⚙️ Functions Overview
refine_template_crop(template_img, target_color)
Thresholds the template image in HSV to keep only red (❤️) or blue (💙) pixels and crops to that area.

crop_by_max_color_column(template_img, target_color, slice_width, crop_percent)
Finds the vertical column with the most target color, extracts a fixed-width slice, and crops a percentage off the top and bottom before refining the crop.

show_auto_found_popup(screenshot_cv, hp_region, mp_region)
Resizes the screenshot to 800×600, overlays the detected HP and MP regions, and shows a popup with a Confirm button.

GUI Functions:

select_region_interactively(region_name) – Opens an interactive window for manual region selection.
select_target_window() – Lets you choose the game window from a list of active windows.
auto_find_regions() – Automatically locates health and mana regions using the refined template cropping.
toggle_monitoring() and monitor_loop() – Start/stop monitoring and automatically use potions based on thresholds.
🚀 Getting Started
Prerequisites
Python 3.x
Dependencies:
Install the following packages:
bash
Copy
pip install opencv-python pillow pyautogui keyboard pywin32
Installation
Clone the Repository:

bash
Copy
git clone https://github.com/yourusername/poe-auto-potion-bot.git
cd poe-auto-potion-bot
Add Template Images:
Place your health.png and mana.png template images in the repository root. These should be screenshots of your health and mana bars.

Run the Bot:

bash
Copy
python your_script_name.py
🔧 Configuration & Usage
Config File:
Settings are stored in config.json (thresholds, delays, target window, region coordinates).

GUI:
Use the control panel to:

View and adjust health/mana thresholds.
Manually select regions if auto-detection isn't perfect.
Choose the game window to capture.
Monitor real-time health/mana values.
Auto-Detection:
Click "Auto Find HP/MP Regions" to capture a screenshot, process your template images, and display a popup (800×600) with detected regions. Confirm to save the regions.

Hotkeys:
Use F8 to toggle monitoring and F9 to pause.

🤝 Contributing
Contributions are welcome! Feel free to fork the repository and submit pull requests. For major changes, please open an issue to discuss your ideas first.

📄 License
This project is licensed under the MIT License.

🙏 Acknowledgments
Thanks to the developers behind OpenCV, pyautogui, Pillow, and keyboard for their fantastic libraries.
Inspired by the PoE community and the need for improved automation in gameplay. 🎮

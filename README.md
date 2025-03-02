PoE Auto-Potion Bot
A Python-based auto-potion bot for Path of Exile. This tool works with both PoE 1 and PoE 2, with the auto-location feature optimized for PoE 2. It monitors your health and mana bars and automatically uses potions when needed.

Key Features
Auto Location Detection:
Uses image processing to find the health (red) and mana (blue) bar regions on the screen automatically (optimized for PoE 2).

Template Refinement: The bot refines your provided template images (health.png and mana.png) by:
Thresholding to isolate the target color.
Selecting the vertical column with the highest concentration of red/blue.
Cropping a fixed-width slice and removing 5% from the top and bottom.
Further refining the crop so that only the desired color remains.
Manual Region Selection:
If auto-detection does not work perfectly, you can manually select the health and mana regions.

GUI Control Panel:
A Tkinter-based interface that displays real-time fill percentages, allows threshold configuration, and lets you choose the target game window.

Hotkey Support:
Start, stop, and pause the bot using global hotkeys (default F8 for toggling and F9 for pausing).

How It Works
Screenshot Capture:
The bot uses pyautogui to capture the game window based on the target window title.

Template Matching:

Refine Template Crop:
The function refine_template_crop(template_img, target_color) crops each template to only include areas with the target color (red for health, blue for mana).
Crop by Maximum Color Column:
The function crop_by_max_color_column(template_img, target_color, slice_width, crop_percent) analyzes each vertical column to find the one with the highest target color intensity, extracts a vertical slice of a fixed width, then crops 5% from the top and bottom of that slice.
Template Matching:
The bot uses OpenCV’s matchTemplate function to locate these cropped regions within the screenshot of the game window.
Auto-Found Regions Popup:
A popup window (800×600 pixels) displays the detected health (red) and mana (blue) regions for confirmation before the regions are saved.
Monitoring & Potion Usage:
The bot reads the health/mana percentages from the selected regions. If a value drops below a user-defined threshold, it simulates a key press (using pyautogui.press()) to use the corresponding potion.

Functions Overview
refine_template_crop(template_img, target_color)
Converts a template image to HSV, thresholds for the target color, and crops to the bounding box that contains the color.

crop_by_max_color_column(template_img, target_color, slice_width, crop_percent)
Scans each vertical column, selects the column with the most target color pixels, extracts a vertical slice (default width is 4 pixels), crops off a percentage (default 5%) from the top and bottom, and then refines the crop.

show_auto_found_popup(screenshot_cv, hp_region, mp_region)
Resizes a screenshot to 800×600 pixels, overlays the detected HP and MP regions with red and blue rectangles respectively, and displays a popup window with a confirm button.

GUI Functions:

select_region_interactively(region_name) – Opens a window for manual region selection.
select_target_window() – Allows you to choose the game window from a list of active windows.
auto_find_regions() – Automatically locates the health and mana regions using the template images and cropping functions.
toggle_monitoring() and monitor_loop() – Start, pause, or stop monitoring and use potions when necessary.
Compatibility
Works for PoE 1 and PoE 2:
The code is designed to work with both versions. However, the auto-location feature is optimized for PoE 2.
Resolution Independence:
All coordinates are computed relative to the captured screenshot, so the bot should work on any resolution.
Getting Started
Clone the Repository:

bash
Copy
git clone https://github.com/yourusername/poe-auto-potion-bot.git
cd poe-auto-potion-bot
Install Dependencies:

bash
Copy
pip install opencv-python pillow pyautogui keyboard pywin32
Add Template Images:
Place your health.png and mana.png in the repository root.

Run the Bot:

bash
Copy
python your_script_name.py
Configuration
All settings are stored in config.json. You can change thresholds, potion delays, and hotkeys via the GUI. Manual region selection is also available if auto-detection isn’t perfect.

Contributing
Contributions are welcome! Please fork this repository and create pull requests for any enhancements or bug fixes.

License
This project is licensed under the MIT License.

Acknowledgments
OpenCV
pyautogui
Pillow
keyboard
Special thanks to the PoE community for inspiring automation projects.

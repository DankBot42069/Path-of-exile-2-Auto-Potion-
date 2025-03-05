# PoE2 Auto-Potion & Chickening Bot

This is a simple Python/Tkinter utility that automatically uses health and mana potions in Path of Exile 2 when your HP/MP falls below certain thresholds. It can also perform a "chicken" (emergency logout) when health is critically low.

## Features

1. **Automatic Potion Usage**  
   - Monitors HP and MP using on-screen recognition.  
   - Presses assigned hotkeys for Health and Mana potions when thresholds are reached.

2. **Adjustable Thresholds (Dual Sliders)**  
   - You can set a **lower** and **upper** threshold for both HP and MP.  
   - The script uses a randomly varying trigger within your specified (lower, upper) range to avoid a too-consistent pattern.

3. **Chickening (Emergency Logout)**  
   - If HP dips below a critical threshold (e.g., 30%), the bot presses ESC and clicks **Exit to Log In Screen**.  
   - Waits until the game is back and HP is at least 50% before resuming normal potion usage.

4. **Configurable Delays**  
   - You can set custom delays for HP and MP potion presses.

5. **Overlay**  
   - Optionally shows real-time threshold lines over the HP and MP bars in the game window.

6. **Region Selection**  
   - Manually select the on-screen regions for HP and MP bars.  
   - Optionally use “gray detection” if the HP/MP bars appear mostly gray or black when empty.

7. **Global Hotkeys**  
   - Start/Stop monitoring.  
   - Pause/Resume.  
   - Bring up the UI quickly from inside the game.

## Basic Usage

1. **Install Dependencies**  
   - [Python 3.8+](https://www.python.org/downloads/)  
   - `pip install opencv-python pyautogui pillow keyboard pywin32`

2. **Run the Script**  
   - Open a terminal or command prompt and run:  
     ```bash
     python your_script_name.py
     ```
   - The GUI should appear.

3. **Select Target Window**  
   - Click “Select Target Window” and choose the title of your Path of Exile 2 client.

4. **Select HP/MP Regions**  
   - Click **Select HP Region** or **Select MP Region**.  
   - A screenshot preview appears; drag a rectangle around the respective bars and confirm.

5. **Adjust Threshold Sliders**  
   - In the “HP Fill & Thresholds” and “MP Fill & Thresholds” sections, move the sliders or enter numeric values.  
   - The **lower** threshold is the baseline; the **upper** threshold sets how much random variance you allow.

6. **Configure Settings**  
   - Potion Delays (HP Delay, MP Delay)  
   - Hotkeys (Toggle Key, Pause Key, SingleScreen Key)  
   - Chickening (Enable, plus the HP threshold).  
   - [Optional] Check “Use Gray as HP/MP?” if your bars are mostly grayscale when empty.

7. **Press “Start Monitoring”**  
   - The bot begins watching your HP/MP and automatically presses potions.  
   - If chickening is enabled and your HP drops below the critical threshold, it will automatically exit to the log-in screen and wait to re-enter.

8. **Hotkeys**  
   - By default, `F8` toggles Monitoring On/Off.  
   - `F9` pauses/resumes.  
   - `F10` shows the UI on top (and presses ESC in-game).  
   - You can edit these to your preference.

## Donation

If you find this tool helpful and would like to support continued development, you can donate to any of these addresses:

- **Solana**: `bJEqC85NdYkaAA8mxHygM3HCo5VhBzG15XLmw18KSZj`
- **Ethereum (ETH)**: `0xf9d3a12F836fCB3D2788b49531CbeaC92300E3BA`
- **Bitcoin (BTC)**: `bc1q9vqp8z78ryhw824wrafer9vrdn8g67w8lslmfs`

Thank you for your support!

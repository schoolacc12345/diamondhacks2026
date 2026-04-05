import time
import json
import urllib.request
from arduino.app_utils import App, Bridge

# --- CONFIGURATION ---
# IMPORTANT: Update this with the IP printed by main.py on your PC!
BASE_URL = "http://192.168.137.1:5000"
# ---------------------

current_matrix_state = "IDLE"

def get_matrix_state():
    global current_matrix_state
    return current_matrix_state

def snooze_pressed():
    print("🔘 PHYSICAL BUTTON: Snooze!")
    try:
        urllib.request.urlopen(f"{BASE_URL}/snooze", timeout=2)
    except Exception as e:
        print(f"Failed to snooze: {e}")
    return "OK"

def toggle_session():
    print("🔘 PHYSICAL BUTTON: Long Press! Toggling Session...")
    try:
        # Ping the PC's test endpoint or a new toggle endpoint
        # For simplicity, we can use a custom header or just a specific URL
        urllib.request.urlopen(f"{BASE_URL}/toggle_session", timeout=2)
    except Exception as e:
        print(f"Failed to toggle: {e}")
    return "OK"

def main_loop():
    global current_matrix_state
    try:
        # Poll the PC for the current "Source-Aware" state
        with urllib.request.urlopen(f"{BASE_URL}/arduino_poll", timeout=1) as response:
            data = json.loads(response.read().decode())
            command = data.get("command", "IDLE")
            
            # The PC will now send back strings like "WEBCAM", "PHONE", "FOCUS", or "IDLE"
            current_matrix_state = command
                
    except Exception as e:
        pass
        
    time.sleep(0.5)

def init():
    print("--- ARDUINO MULTIVERSE BRIDGE ONLINE ---")
    Bridge.provide("get_matrix_state", get_matrix_state)
    Bridge.provide("snooze_pressed", snooze_pressed)
    Bridge.provide("toggle_session", toggle_session)

if __name__ == "__main__":
    init()
    App.run(user_loop=main_loop)

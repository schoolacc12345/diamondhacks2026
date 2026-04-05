import time
import json
import urllib.request
from arduino.app_utils import App, Bridge

PC_URL = "http://192.168.137.1:5000/arduino_poll"

# The state variable that the C++ sketch will constantly ask for
current_matrix_state = "IDLE"

def get_matrix_state():
    """This function is exposed to the C++ Bridge"""
    global current_matrix_state
    return current_matrix_state

def snooze_pressed():
    """C++ calls this when the physical button is pressed!"""
    print("🔘 PHYSICAL BUTTON PRESSED! Sending Snooze to PC...")
    try:
        # PING THE PC TO SHUT OFF THE ALARM!
        urllib.request.urlopen(f"{PC_URL.replace('/arduino_poll', '/snooze')}", timeout=2)
    except Exception as e:
        print(f"Failed to snooze: {e}")
    return "OK"

def main_loop():
    global current_matrix_state
    try:
        # Arduino asks the PC over Wi-Fi: "Do you have any commands for me?"
        with urllib.request.urlopen(PC_URL, timeout=1) as response:
            data = json.loads(response.read().decode())
            command = data.get("command", "NONE")
            
            if command == "R":
                print("Wi-Fi Poll: Found 'R' command. State updated to RED!")
                current_matrix_state = "RED"
            elif command == "G":
                print("Wi-Fi Poll: Found 'G' command. State updated to GREEN!")
                current_matrix_state = "GREEN"
                
    except Exception as e:
        pass
        
    time.sleep(0.5)

def init():
    print("--- ARDUINO BRIDGE ENGINE ONLINE ---")
    # Make the python function explicitly available to C++ via the Bridge!
    Bridge.provide("get_matrix_state", get_matrix_state)
    Bridge.provide("snooze_pressed", snooze_pressed)

if __name__ == "__main__":
    init()
    App.run(user_loop=main_loop)

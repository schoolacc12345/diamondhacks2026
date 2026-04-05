# initial manual phone test


import os
import requests
import time

PC_URL = "http://192.168.137.1:5000"

def main():
    print("=== TERMUX DISTRACTION TRIGGER ===")
    print("Simulating phone unlock...")
    print("-> ⏳ Grace Period Active (10s)")
    print("-> Press CTRL+C within 10s to simulate locking your phone!")
    
    try:
        # This POST request mathematically synchronizes everything.
        # It asks the PC to start the timer.
        # It will wait exactly 10s + the AI's thinking time before receiving a response!
        response = requests.post(f"{PC_URL}/distracted", timeout=90)
        data = response.json()
        
        # Once the PC returns the response, the red screen is up, the Arduino is red,
        # and we trigger the phone haptics at the exact same millisecond!
        if data.get("vibrate") == True:
            print("\n🚨 ALARM TRIGGERED! VIBRATING!")
            # Trigger the Termux API vibration command for 2 seconds
            os.system("termux-vibrate -f -d 2000")
        else:
            print(f"\n✅ Server Response: {data.get('status')}")
            
    except KeyboardInterrupt:
        # If you press CTRL+C, you simulate locking the phone!
        print("\n\n[!] User 'locked' the phone! Sending abort signal...")
        try:
            requests.post(f"{PC_URL}/locked", timeout=5)
            print("[✅] Distraction successfully cancelled on the PC.")
        except:
            print("[X] Failed to send cancel signal.")
            
    except requests.exceptions.Timeout:
        print("\n[X] Connection to PC Timed out.")
    except Exception as e:
        print(f"\n[X] Error: {e}")

if __name__ == "__main__":
    main()

import os
import requests
import time
import json
import subprocess

PC_URL = "http://192.168.137.1:5000"

def get_gravity_z():
    """Polls the gravity sensor once and returns the Z-axis value."""
    try:
        # We use termux-sensor to get one reading of the gravity sensor
        # Timeout added to prevent hanging if the sensor doesn't respond
        raw_bytes = subprocess.check_output(["termux-sensor", "-n", "1", "-s", "gravity"], timeout=2)
        raw_text = raw_bytes.decode('utf-8').strip()
        
        # Handle cases where multiple readings are returned in one string
        if "}{" in raw_text:
            raw_text = raw_text.split("}{")[0] + "}"
            
        data = json.loads(raw_text)
        
        # Version-agnostic parsing
        if isinstance(data, dict):
            # Try to find 'values' in any root key
            for key in data:
                if isinstance(data[key], dict) and "values" in data[key]:
                    return data[key]["values"][2]
                if key == "values": # Direct access
                    return data["values"][2]
        
        return 9.8 # Fallback
    except Exception as e:
        # If this prints, we know the phone has a permission or package issue
        print(f"\n[!] Sensor Access Error: {e} | Ensure 'termux-api' is installed.")
        return 9.8 

def main():
    print("=== 🤖 AUTO-SENTRY: Phone Heartbeat Node ===")
    print(f"Monitoring Gravity Sensors... Lay phone FLAT to begin.")
    
    is_distracted = False
    
    while True:
        try:
            z = get_gravity_z()
            # LIVE CALIBRATION (helpful for judges too!)
            print(f"Sensor Z: {z:.2f} | Status: {'[DISTRACTED]' if is_distracted else '[SAFE]'}", end="\r")
            
            # THE LOGIC FLIP:
            # Below 8.0 = Handheld / Tilted
            # Above 8.0 = On Desk / Flat
            
            if z < 8.0 and not is_distracted:
                print(f"\n🚨 [PICKUP] Motion detected! Z={z:.2f}. Notifying PC...")
                requests.post(f"{PC_URL}/distracted", json={"source": "motion"}, timeout=2)
                is_distracted = True
                
            elif z >= 8.0 and is_distracted:
                print(f"\n✅ [PUTDOWN] Stability detected! Z={z:.2f}. Cancelling Alarm...")
                # We send the locked signal to abort any active grace period
                requests.post(f"{PC_URL}/locked", timeout=2)
                is_distracted = False
                
        except Exception as e:
            # If network fails, we don't flip 'is_distracted' so it retries next loop
            pass 
            
        time.sleep(0.3) # Slightly faster polling for snappiness

if __name__ == "__main__":
    main()

import os
import requests
import time
import json
import subprocess

PC_URL = "http://192.168.137.1:5000" # Update this to your PC's IP

def get_gravity_z():
    """Polls the gravity sensor exactly once and returns the Z-axis value."""
    try:
        raw_bytes = subprocess.check_output(["termux-sensor", "-n", "1", "-s", "gravity"], timeout=4)
        raw_text = raw_bytes.decode('utf-8').strip()
        data = json.loads(raw_text)
        
        if isinstance(data, dict):
            if "gravity" in data and "values" in data["gravity"]:
                return data["gravity"]["values"][2]
            elif "values" in data:
                return data["values"][2]
            else:
                for key in data:
                    if isinstance(data[key], dict) and "values" in data[key]:
                        return data[key]["values"][2]
        return None
    except Exception as e:
        return None 

def main():
    print("\n=== 🤖 AUTO-SENTRY: Stable Heartbeat Node ===")
    print(f"Target PC: {PC_URL}\n")
    
    # 1. The Explicit Boolean the user requested
    is_flat = True 
    
    while True:
        try:
            z = get_gravity_z()
            if z is None:
                continue
                
            print(f"Sensor Z: {z:.2f} | State: {'[FLAT]' if is_flat else '[NOT FLAT]'}      ", end="\r")
            
            # --- USER LOGIC: Switch states ONLY ONCE across bounds ---
            
            # Out of safe bound -> Go to NOT FLAT just once
            if z < 8.0 and is_flat:
                is_flat = False # Update state BEFORE network request to guarantee no spam
                print(f"\n🚨 [PICKUP] Phone left the safe zone (Z={z:.2f}). Notifying PC...")
                try:
                    requests.post(f"{PC_URL}/distracted", json={"source": "motion"}, timeout=2)
                except Exception:
                    pass # Ignore connection errors to prevent pausing the loop
                    
            # Back in safe bound -> Go to FLAT just once
            elif z > 8.0 and not is_flat:
                is_flat = True # Update state BEFORE network request
                print(f"\n✅ [PUTDOWN] Phone returned to safe zone (Z={z:.2f}). Cancelling...")
                try:
                    requests.post(f"{PC_URL}/locked", timeout=2)
                except Exception:
                    pass
                    
        except Exception:
            pass
            
        # 2. Slow it down like it was before
        time.sleep(0.4)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")

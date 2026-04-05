import tkinter as tk
import threading
import requests
import json
import time
import queue
import winsound
import keyboard
import webbrowser
import os
import logging
from flask import Flask, jsonify, request
from dotenv import load_dotenv

# Silence Flask/Werkzeug "GET /arduino_poll" noise
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Load credentials from .env file
load_dotenv()

app = Flask(__name__)

# --- SUPABASE CLOUD CONFIG ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

# --- NEW: ARDUINO POLLING CACHE ---
arduino_pending_command = "IDLE"
arduino_poll_count = 0


# Global session trackers
session_active = False
session_start_time = time.time()
distraction_count = 0
snooze_count = 0
current_distraction_start = 0
total_distracted_seconds = 0

def upload_analytics_to_cloud(elapsed_secs, dist_secs, dist_count, snooze_count):
    print("\n☁️ Pushing Edge Logs to Supabase Cloud...")
    payload = {
        "elapsed_seconds": int(elapsed_secs),
        "distracted_seconds": int(dist_secs),
        "distraction_count": dist_count,
        "snooze_count": snooze_count
    }
    try:
        url = f"{SUPABASE_URL}/rest/v1/focus_sessions"
        req = requests.post(url, json=payload, headers=SUPABASE_HEADERS, timeout=5)
        print(f"✅ Supabase Cloud Upload Success! Status: {req.status_code}")
    except Exception as e:
        print("⚠️ Cloud Upload Failed:", e)

def get_lifetime_stats():
    print("📊 Fetching Historical Data from Cloud...")
    try:
        url = f"{SUPABASE_URL}/rest/v1/focus_sessions?select=*"
        req = requests.get(url, headers=SUPABASE_HEADERS, timeout=5)
        if req.status_code == 200:
            data = req.json()
            total_focus_secs = sum(max(0, s.get('elapsed_seconds',0) - s.get('distracted_seconds',0)) for s in data)
            total_distractions = sum(s.get('distraction_count',0) for s in data)
            return int(total_focus_secs / 60), total_distractions, len(data)
    except Exception as e:
        print(f"Stats Error: {e}")
    return 0, 0, 0 

def get_recent_sessions():
    print("📋 Fetching Last 20 Sessions from Cloud...")
    try:
        # Fetching last 20 sessions ordered by ID descending
        url = f"{SUPABASE_URL}/rest/v1/focus_sessions?select=*&order=id.desc&limit=20"
        req = requests.get(url, headers=SUPABASE_HEADERS, timeout=5)
        if req.status_code == 200:
            return req.json()
    except Exception as e:
        print(f"History Error: {e}")
    return []

def generate_web_dashboard(elapsed_secs, dist_secs, dist_count, snooze_count):
    focus_secs = max(0, elapsed_secs - dist_secs)
    
    try:
        with open("report_template.html", 'r') as f:
            html = f.read()
            
        elapsed_m, elapsed_s = divmod(int(elapsed_secs), 60)
        focus_m, focus_s = divmod(int(focus_secs), 60)
        dist_m, dist_s = divmod(int(dist_secs), 60)
            
        html = html.replace("{ELAPSED_MINUTES}", str(elapsed_m))
        html = html.replace("{ELAPSED_SECONDS}", str(elapsed_s))
        html = html.replace("{FOCUS_MINUTES}", str(focus_m))
        html = html.replace("{FOCUS_SECONDS}", str(focus_s))
        html = html.replace("{DISTRACTED_MINUTES}", str(dist_m))
        html = html.replace("{DISTRACTED_SECONDS}", str(dist_s))
        
        # Decimal values for the bar chart
        html = html.replace("{FOCUS_TIME_DECIMAL}", str(round(focus_secs / 60.0, 2)))
        html = html.replace("{DISTRACTED_TIME_DECIMAL}", str(round(dist_secs / 60.0, 2)))
        html = html.replace("{TOTAL_DISTRACTIONS}", str(dist_count))
        html = html.replace("{TOTAL_SNOOZES}", str(snooze_count))
        
        # --- NEW: Historical Injections ---
        life_minutes, life_dist, life_sessions = get_lifetime_stats()
        history_data = get_recent_sessions()
        
        html = html.replace("{LIFETIME_MINUTES}", str(life_minutes))
        html = html.replace("{LIFETIME_DISTRACTIONS}", str(life_dist))
        html = html.replace("{SESSION_COUNT}", str(life_sessions))
        html = html.replace("{SESSION_HISTORY_JSON}", json.dumps(history_data))
        
        output_path = os.path.abspath("session_report.html")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
            
        # Open the generated HTML in the default browser!
        # Passing the path directly without the file:/// prefix prevents the download prompt
        webbrowser.open(output_path)
        print("📊 Generated beautiful Web Dashboard!")
    except Exception as e:
        print("⚠️ Failed to generate web dash:", e)

def toggle_session():
    global session_active, session_start_time, distraction_count, snooze_count
    global current_distraction_start, total_distracted_seconds, arduino_pending_command

    if not session_active:
        # Start a new session
        session_active = True
        session_start_time = time.time()
        distraction_count = 0
        snooze_count = 0
        current_distraction_start = 0
        total_distracted_seconds = 0
        total_distracted_seconds = 0
        arduino_pending_command = "FOCUS" # Tell Arduino to show Heart Icon
        print("\n=======================================")
        print("🟢 [GLOBAL HOTKEY] FOCUS SESSION STARTED!")
        print("   Tracking is now ON.")
        print("=======================================")
    else:
        # End the session
        session_active = False
        arduino_pending_command = "IDLE" # Clear Arduino Matrix

        
        # If they end the session while distracted, tally the final seconds!
        if current_distraction_start > 0:
            total_distracted_seconds += (time.time() - current_distraction_start)
            
        total_elapsed_seconds = (time.time() - session_start_time)
        print("\n=======================================")
        print("🛑 [GLOBAL HOTKEY] FOCUS SESSION ENDED!")
        print("=======================================")
        
        # 1. Edge-to-Cloud Upload
        upload_analytics_to_cloud(total_elapsed_seconds, total_distracted_seconds, distraction_count, snooze_count)
        
        # 2. Generate and open Web Dashboard
        generate_web_dashboard(total_elapsed_seconds, total_distracted_seconds, distraction_count, snooze_count)

# Queue to safely pass messages from the Flask background thread to the Tkinter main thread
ui_queue = queue.Queue()

# --- 1. THE LOCAL AI ENGINE ---
def evaluate_distraction(minutes_worked, count):
    print("🧠 AI is evaluating the telemetry...")
    system_prompt = f"""
    You are the logic engine for a focus application. The user has been working for {minutes_worked} minutes. This is distraction number {count} during this session.
    Evaluate their behavior.
    If distraction_count is 1, severity is 1, command is 'R'.
    If distraction_count is > 2, severity is 3, command is 'R'.
    If severity is 3, set trigger_siren to true. Otherwise, false.
    You MUST respond with ONLY a raw JSON object in this exact format:
    {{
        "severity": <int>,
        "hardware_command": "<'R' or 'G'>",
        "ui_message": "<A short, context-aware message to the user>",
        "trigger_siren": <true or false>
    }}
    """
    try:
        response = requests.post("http://localhost:11434/api/generate", json={
            "model": "phi3",
            "prompt": system_prompt,
            "stream": False,
            "format": "json"
        }, timeout=30)
        return json.loads(response.json()['response'])
    except Exception as e:
        print("AI Engine Error:", e)
        # Fallback if Ollama times out
        return {"severity": 1, "hardware_command": "R", "ui_message": "Focus, Richard!"}

# --- 2. THE SERVER COMPONENT ---
# --- SENSOR LANE TRACKING ---
# True means "Currently seeing a distraction", False means "All safe"
sensor_states = {"WEBCAM": False, "PHONE": False}
grace_period_in_progress = {"WEBCAM": False, "PHONE": False}


@app.route('/distracted', methods=['POST'])
def distracted():
    global distraction_count, arduino_pending_command, session_active
    global current_distraction_start, grace_period_in_progress, sensor_states
    
    if not session_active:
        print("\n[Ignore] Trigger detected, but no active focus session.")
        return {"status": "Timer inactive. Distractions allowed!"}, 200

    # Determine source (Standardize on WEBCAM / PHONE)
    source = "WEBCAM"
    if request.is_json:
        data = request.get_json()
        raw_source = data.get("source", "WEBCAM").upper()
        source = "PHONE" if raw_source in ["PHONE", "MOTION"] else "WEBCAM"

    if grace_period_in_progress.get(source):
        return {"status": "Already counting down"}, 200

    grace_period_in_progress[source] = True
    sensor_states[source] = True # Mark this sensor as "in-trouble"
    
    print(f"\n[!] 🚦 LANE [{source}] Triggered! 10-Second Grace Period Started")
    
    try:
        # 10 second grace period loop: only checks its OWN sensor state
        for _ in range(10):
            if not sensor_states[source]:
                print(f"[✅] Safe: Lane [{source}] grace period respected. Cancelled.")
                return {"status": "Grace period respected. No alarm."}, 200
            time.sleep(1)
            
        if not sensor_states[source]:
            return {"status": "Aborted"}, 200

        # --- GRACE PERIOD EXPIRED ---
        distraction_count += 1
        minutes_worked = int((time.time() - session_start_time) / 60)
        print(f"🚨 LANE [{source}] EXPIRED! Distraction #{distraction_count}")
        
        current_distraction_start = time.time()

        # --- BLOCKING AI EVALUATION ---
        decision = evaluate_distraction(minutes_worked, distraction_count)
        
        # --- FINAL SAFETY CHECK ---
        if not sensor_states[source]:
            print(f"[✅] Safety Abort: Lane [{source}] safe detected during AI thinking. Alarm skipped!")
            current_distraction_start = 0 
            return {"status": "Aborted at last second."}, 200

        # Trigger Alarm
        arduino_pending_command = source
        print(f"🚀 PC: AI evaluation complete. Triggering {source} Alarm!")

        ui_message = decision.get('ui_message', 'Get back to work!')
        ui_queue.put(ui_message)

        try:
            winsound.PlaySound("alarm.wav", winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
        except:
            winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_LOOP)

        return {"status": "ALARM_TRIGGERED", "vibrate": True}, 200

    finally:
        grace_period_in_progress[source] = False


@app.route('/test', methods=['GET'])
def test_connection():
    """Simple ping to verify the phone can reach the PC."""
    print("📡 [NETWORK] Connectivity test: Phone reach successful!")
    return {"status": "PC is online"}, 200

@app.route('/toggle_session', methods=['GET'])
def remote_toggle():
    toggle_session()
    return {"status": "Toggled"}, 200

@app.route('/locked', methods=['POST'])
def locked():
    global sensor_states
    source = "WEBCAM"
    if request.is_json:
        data = request.get_json()
        raw_source = data.get("source", "WEBCAM").upper()
        source = "PHONE" if raw_source in ["PHONE", "MOTION"] else "WEBCAM"
        
    print(f"\n🔒 [PC SERVER] ABORT RECEIVED! Cancelling Lane [{source}].")
    sensor_states[source] = False 
    return {"status": f"Lane {source} aborted"}, 200


@app.route('/arduino_poll', methods=['GET'])
def arduino_poll():
    global arduino_pending_command, arduino_poll_count
    
    arduino_poll_count += 1
    if arduino_poll_count % 5 == 0:
        print("📡 [DEBUG] Arduino: Connected & Polling...")

    # Arduino asks "What should I do?"
    cmd = arduino_pending_command
    
    # If a distraction was cleared, set back to FOCUS icon if session still active
    if cmd in ["WEBCAM", "PHONE"]:
        # We don't clear it immediately, we let it stay until snooze or manual end
        pass 
    
    return jsonify({"command": cmd})


@app.route('/snooze', methods=['GET'])
def snooze_endpoint():
    global arduino_pending_command, snooze_count, sensor_states
    global current_distraction_start, total_distracted_seconds
    
    print(f"\n✋ PC: Physical Snooze Button Pressed! Aborting ALL Alarms!")
    snooze_count += 1
    
    # Reset all sensor states on snooze
    for key in sensor_states:
        sensor_states[key] = False

    
    # Calculate exactly how many seconds they were distracted during this event
    if current_distraction_start > 0:
        dist_duration = time.time() - current_distraction_start
        total_distracted_seconds += dist_duration
        current_distraction_start = 0 # reset
        print(f"⏱️ Distraction lasted {int(dist_duration)} seconds.")

    
    # Ask Arduino to turn green / show heart
    if session_active:
        arduino_pending_command = "FOCUS"
    else:
        arduino_pending_command = "IDLE"

    
    # Silence the Windows Audio Siren!
    winsound.PlaySound(None, winsound.SND_PURGE)
    
    # Send a magic signal to the Tkinter queue to hide the red screen
    ui_queue.put("SNOOZE_ACTION")
    
    return {"status": "Snoozed"}, 200

# --- 3. THE UI COMPONENT (Main Thread) ---
def setup_ui():
    root = tk.Tk()
    root.title("DISTRACTION ALERT")
    root.attributes('-fullscreen', True)
    root.attributes('-alpha', 0.85)
    root.configure(bg='red')
    root.attributes('-topmost', True)
    
    # Hide the window immediately on boot until we need it
    root.withdraw()
    
    label = tk.Label(root, text="", font=("Arial", 40, "bold"), fg="white", bg="red", wraplength=1200)
    label.pack(expand=True)

    def on_snooze():
        global arduino_pending_command
        arduino_pending_command = "G"
        print(f"📡 PC: Queued 'G' (Clear) command for Arduino to pick up!")
        winsound.PlaySound(None, winsound.SND_PURGE)
        root.withdraw()

    dismiss_btn = tk.Button(root, text="Snooze (I'll focus)", font=("Arial", 20), command=on_snooze)
    dismiss_btn.pack(pady=50)
    
    def check_queue():
        try:
            msg = ui_queue.get_nowait()
            if msg == "SNOOZE_ACTION":
                # A physical button forced the window to close
                root.withdraw()
            else:
                # Normal AI message handling
                label.config(text=msg)
                root.deiconify() # Bring window to front
        except queue.Empty:
            pass
        root.after(100, check_queue) # Check again in 100ms
        
    root.after(100, check_queue)
    
    return root

if __name__ == '__main__':
    from webcam import Webcam
    
    print("\n=======================================")
    print(" FocusGrid Core System is ONLINE.")
    print(" Mode: AI-Automated Sentry")
    
    # NEW: Helpful IP finder for the phone
    import socket
    hostname = socket.gethostname()
    ips = [ip for ip in socket.gethostbyname_ex(hostname)[2] if not ip.startswith("127.")]
    print(f" PC IP Addresses: {', '.join(ips)}")
    print(" -> Use one of these in your Phone's 'PC_URL'!")
    
    print("\n -> Press CTRL+SHIFT+S anywhere to Start/Stop a session!")
    print("=======================================\n")
    
    # Start Webcam Sentry
    sentry = Webcam()
    sentry.start()
    
    # Register global hotkey (suppress=True prevents 'Save As' popups in editors)
    keyboard.add_hotkey('ctrl+shift+s', toggle_session, suppress=True)
    
    # Run Flask in a background thread
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, use_reloader=False), daemon=True).start()
    
    # Tkinter loop MUST run on the main thread
    root = setup_ui()
    root.mainloop()

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np
import time
import threading
import requests
import os

class Webcam:
    def __init__(self, endpoint_url="http://localhost:5000"):
        self.model_path = 'face_landmarker.task'
        self.endpoint_url = endpoint_url
        self.running = False
        
        self.distracted = False
        self.distracted_start_time = 0
        self.distraction_threshold = 1.2 # 1.2 second lookaway validation
        
        self.show_preview = False
        self.thread = None
        
        # Initialize detector
        if not os.path.exists(self.model_path):
            print("⚠️ [Webcam Sentry] Model file missing. Attempting download...")
            self._download_model()
            
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            num_faces=1
        )
        self.detector = vision.FaceLandmarker.create_from_options(options)
        
    def _download_model(self):
        url = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'
        try:
            r = requests.get(url)
            with open(self.model_path, 'wb') as f:
                f.write(r.content)
            print("✅ Model downloaded successfully.")
        except Exception as e:
            print(f"❌ Failed to download model: {e}")

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
            print("👁️ [Webcam Sentry] Initialized (Tasks API) and watching...")
        
    def stop(self):
        self.running = False
            
    def _notify_server(self, endpoint):
        def task():
            try:
                requests.post(f"{self.endpoint_url}/{endpoint}", json={"source": "WEBCAM"}, timeout=1)
            except requests.exceptions.RequestException:
                pass
        threading.Thread(target=task, daemon=True).start()
            
    def _loop(self):
        cap = cv2.VideoCapture(0)
        
        while self.running:
            success, image = cap.read()
            if not success:
                time.sleep(0.1)
                continue
                
            # Convert to RGB for MediaPipe
            rgb_image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
            
            # Detect landmarks
            detection_result = self.detector.detect(mp_image)
            
            # Reset UI frame (to BGR for OpenCV display)
            display_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)

            is_looking = False
            pitch = 0
            yaw = 0
            
            if detection_result.face_landmarks:
                img_h, img_w, img_c = display_image.shape
                face_3d = []
                face_2d = []
                
                # Use the first face detected
                face_landmarks = detection_result.face_landmarks[0]
                
                # Indices for head pose estimation
                # 33: Left eye inner, 263: Right eye inner, 1: Nose, 61: Mouth left, 291: Mouth right, 199: Chin
                pose_indices = [33, 263, 1, 61, 291, 199]
                
                for idx in pose_indices:
                    lm = face_landmarks[idx]
                    px, py = int(lm.x * img_w), int(lm.y * img_h)
                    face_2d.append([px, py])
                    face_3d.append([px, py, lm.z]) # z is relative, but solvable for rotation
                            
                face_2d = np.array(face_2d, dtype=np.float64)
                face_3d = np.array(face_3d, dtype=np.float64)
                    
                focal_length = 1 * img_w
                cam_matrix = np.array([
                    [focal_length, 0, img_w / 2],
                    [0, focal_length, img_h / 2],
                    [0, 0, 1]
                ])
                dist_matrix = np.zeros((4, 1), dtype=np.float64)
                    
                success_pnp, rot_vec, trans_vec = cv2.solvePnP(face_3d, face_2d, cam_matrix, dist_matrix)
                if success_pnp:
                    rmat, _ = cv2.Rodrigues(rot_vec)
                    angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)
                    
                    pitch = angles[0] * 360 
                    yaw = angles[1] * 360 
                        
                    # Broad focal zone
                    if yaw < -35 or yaw > 35 or pitch < -25 or pitch > 30:
                        is_looking = False
                    else:
                        is_looking = True
            else:
                is_looking = False # No face detected
                
            now = time.time()
            if not is_looking:
                if self.distracted_start_time == 0:
                    self.distracted_start_time = now
                elif now - self.distracted_start_time > self.distraction_threshold:
                    if not self.distracted:
                        self.distracted = True
                        print(f"\n[📷] Webcam: Looked away! (Pitch: {int(pitch)}, Yaw: {int(yaw)})")
                        self._notify_server("distracted")
            else:
                self.distracted_start_time = 0
                if self.distracted:
                    self.distracted = False
                    print("\n[📷] Webcam: User refocus detected.")
                    self._notify_server("locked")

                    
            if self.show_preview:
                if self.distracted_start_time == 0:
                    text = "FOCUSED"
                    color = (0, 255, 0)
                else:
                    if self.distracted:
                        text = "LOOKING AWAY!"
                        color = (0, 0, 255)
                    else:
                        text = "VALIDATING..."
                        color = (0, 165, 255)
                
                cv2.putText(display_image, text, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 3)
                if detection_result.face_landmarks:
                    cv2.putText(display_image, f"Pitch: {int(pitch)} Yaw: {int(yaw)}", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    # Draw a small box on the nose to show tracking works
                    nose = face_landmarks[1]
                    cv2.circle(display_image, (int(nose.x * img_w), int(nose.y * img_h)), 5, (255, 0, 0), -1)
                
                cv2.imshow('FocusGrid Webcam Sentry (MODERN)', display_image)
                
                if cv2.waitKey(10) & 0xFF == 27:
                    break

        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    sentry = Webcam()
    sentry.start()

    print("Testing locally... Press ESC in the camera window to stop.")
    while sentry.running:
        time.sleep(1)

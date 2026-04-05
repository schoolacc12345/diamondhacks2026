#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>

Arduino_LED_Matrix matrix;

// --- EYE ANIMATION (Webcam) ---
uint8_t frameEye[104] = {
  0,0,0,1,1,1,1,1,1,1,0,0, 0,
  0,0,1,0,0,0,0,0,0,0,1,0, 0,
  0,1,0,0,0,7,7,0,0,0,0,1, 0,
  0,1,0,0,7,7,7,7,0,0,0,1, 0,
  0,1,0,0,7,7,7,7,0,0,0,1, 0,
  0,1,0,0,0,7,7,0,0,0,0,1, 0,
  0,0,1,0,0,0,0,0,0,0,1,0, 0,
  0,0,0,1,1,1,1,1,1,1,0,0, 0
};
uint8_t frameEye2[104] = {
  0,0,0,0,0,0,0,0,0,0,0,0, 0,
  0,0,0,0,0,0,0,0,0,0,0,0, 0,
  0,0,0,0,0,0,0,0,0,0,0,0, 0,
  0,0,0,1,1,1,1,1,1,1,0,0, 0,
  0,0,0,1,1,1,1,1,1,1,0,0, 0,
  0,0,0,0,0,0,0,0,0,0,0,0, 0,
  0,0,0,0,0,0,0,0,0,0,0,0, 0,
  0,0,0,0,0,0,0,0,0,0,0,0, 0
};

// --- PHONE ANIMATION (Horizontal) ---
uint8_t framePhone[104] = {
  0,0,0,0,0,0,0,0,0,0,0,0, 0,
  0,7,7,7,7,7,7,7,7,7,7,0, 0,
  7,7,0,0,0,0,0,0,0,0,7,0, 0,
  7,7,0,0,0,0,0,0,0,0,7,0, 0,
  0,7,7,7,7,7,7,7,7,7,7,0, 0,
  0,0,0,0,0,0,0,0,0,0,0,0, 0,
  0,0,0,0,0,0,0,0,0,0,0,0, 0,
  0,0,0,0,0,0,0,0,0,0,0,0, 0
};
uint8_t framePhone2[104] = {
  0,0,0,0,0,0,0,0,0,0,0,0, 0,
  0,0,7,7,7,7,7,7,7,7,7,7, 0,
  0,7,7,0,0,0,0,0,0,0,0,7, 0,
  0,7,7,0,0,0,0,0,0,0,0,7, 0,
  0,0,7,7,7,7,7,7,7,7,7,7, 0,
  0,0,0,0,0,0,0,0,0,0,0,0, 0,
  0,0,0,0,0,0,0,0,0,0,0,0, 0,
  0,0,0,0,0,0,0,0,0,0,0,0, 0
};

// --- HEART ANIMATION (Focus) ---
uint8_t frameHeart[104] = {
  0,0,7,7,0,0,0,0,7,7,0,0, 0,
  0,7,7,7,7,0,0,7,7,7,7,0, 0,
  0,7,7,7,7,7,7,7,7,7,7,0, 0,
  0,7,7,7,7,7,7,7,7,7,7,0, 0,
  0,0,7,7,7,7,7,7,7,7,0,0, 0,
  0,0,0,7,7,7,7,7,7,0,0,0, 0,
  0,0,0,0,7,7,7,7,0,0,0,0, 0,
  0,0,0,0,0,7,7,0,0,0,0,0, 0
};
uint8_t frameHeart2[104] = {
  0,0,0,0,0,0,0,0,0,0,0,0, 0,
  0,0,0,7,7,0,0,7,7,0,0,0, 0,
  0,0,7,7,7,7,7,7,7,7,0,0, 0,
  0,0,7,7,7,7,7,7,7,7,0,0, 0,
  0,0,0,7,7,7,7,7,7,0,0,0, 0,
  0,0,0,0,7,7,7,7,0,0,0,0, 0,
  0,0,0,0,0,7,7,0,0,0,0,0, 0,
  0,0,0,0,0,0,0,0,0,0,0,0, 0
};

uint8_t blankFrame[104] = {0};

String current_state = "IDLE";
const int BUTTON_PIN = 2;

// Animation Control
unsigned long animation_start = 0;
bool show_alternate_frame = false;

// Button Control
unsigned long button_press_start = 0;
bool button_was_pressed = false;
bool long_press_triggered = false;

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(3);
  matrix.draw(blankFrame);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  Bridge.begin(); 
}

void loop() {
  int buttonState = digitalRead(BUTTON_PIN);
  if (buttonState == LOW) {
      if (!button_was_pressed) {
          button_was_pressed = true;
          button_press_start = millis();
          long_press_triggered = false;
      } else if (!long_press_triggered && (millis() - button_press_start > 1500)) {
          long_press_triggered = true;
          String res;
          Bridge.call("toggle_session").result(res);
      }
  } else {
      if (button_was_pressed) {
          if (!long_press_triggered) {
              String res;
              Bridge.call("snooze_pressed").result(res);
          }
          button_was_pressed = false;
      }
  }

  // Animation Toggle (every 500ms)
  if (millis() - animation_start > 500) {
      show_alternate_frame = !show_alternate_frame;
      animation_start = millis();
      
      // Forces re-draw even if state hasn't changed!
      String state;
      bool ok = Bridge.call("get_matrix_state").result(state);
      if (ok) {
        if (state == "WEBCAM") {
            matrix.draw(show_alternate_frame ? frameEye2 : frameEye);
        } else if (state == "PHONE" || state == "MOTION") {
            matrix.draw(show_alternate_frame ? framePhone2 : framePhone);
        } else if (state == "FOCUS") {
            matrix.draw(show_alternate_frame ? frameHeart2 : frameHeart);
        } else {
            matrix.draw(blankFrame);
        }
        current_state = state;
      }
  }
  
  delay(50);
}

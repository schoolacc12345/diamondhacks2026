#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>

Arduino_LED_Matrix matrix;

// ICON: Eye (Webcam Distraction) - Re-aligned to 13-byte stride
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

// ICON: Smartphone (Horizontal) - Re-aligned to 13-byte stride
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


// ICON: Heart (Focus State) - Re-aligned to 13-byte stride
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

uint8_t blankFrame[104] = {0};

String last_drawn_state = "IDLE";
const int BUTTON_PIN = 2;

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

  String state;
  bool ok = Bridge.call("get_matrix_state").result(state);
  if (ok && state != last_drawn_state) {
      // Unified handling: MOTION is displayed as the PHONE icon
      if (state == "WEBCAM") {
          matrix.draw(frameEye);
      } else if (state == "PHONE" || state == "MOTION") {
          matrix.draw(framePhone);
      } else if (state == "FOCUS") {
          matrix.draw(frameHeart);
      } else {
          matrix.draw(blankFrame);
      }
      last_drawn_state = state;
  }
  delay(50);
}

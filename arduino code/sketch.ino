#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>

Arduino_LED_Matrix matrix;

uint8_t frameX[104] = {
  7,0,0,0,0,0,0,0,0,0,0,0,7,
  0,7,0,0,0,0,0,0,0,0,0,7,0,
  0,0,7,0,0,0,0,0,0,0,7,0,0,
  0,0,0,7,0,0,0,0,0,7,0,0,0,
  0,0,0,0,7,0,0,0,7,0,0,0,0,
  0,0,0,0,0,7,0,7,0,0,0,0,0,
  0,0,0,0,0,0,7,0,0,0,0,0,0,
  0,0,0,0,0,7,0,7,0,0,0,0,0
}; 
uint8_t blankFrame[104] = {0};

// Remember what we are currently showing so we don't spam the matrix
String last_drawn_state = "IDLE";

// The physical button wired to Digital Pin 2 and GND
const int BUTTON_PIN = 2;
bool button_was_pressed = false;

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(3);
  matrix.draw(blankFrame);
  
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  // CRITICAL: We were missing this previously!
  Bridge.begin(); 
}

void loop() {
  // 1. Check the Physical Button first!
  if (digitalRead(BUTTON_PIN) == LOW) {
      if (!button_was_pressed) {
          button_was_pressed = true;
          String res;
          // Tell the Python chip the button was pressed!
          Bridge.call("snooze_pressed").result(res);
      }
  } else {
      button_was_pressed = false;
  }

  String gameState;
  
  // C++ asks the Python script: "What color should I be?"
  bool ok = Bridge.call("get_matrix_state").result(gameState);
  
  if (ok && gameState != last_drawn_state) {
      if (gameState == "RED") {
          matrix.draw(frameX);
          last_drawn_state = "RED";
      } else if (gameState == "GREEN" || gameState == "IDLE") {
          matrix.draw(blankFrame);
          last_drawn_state = "GREEN";
      }
  }
  
  // Wait 50ms before asking Python again (20 times a second)
  delay(50);
}

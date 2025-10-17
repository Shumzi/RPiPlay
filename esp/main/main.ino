#include <BleMouse.h>

BleMouse bleMouse("ESP32 BLE Mouse", "Ariel", 100);

void setup() {
  Serial.begin(115200);
  bleMouse.begin();
  Serial.println("BLE Mouse started. Waiting for connection...");
}

void loop() {
  delay(10);
  if (bleMouse.isConnected()) {
    if (Serial.available()) {
      char input = Serial.read();

      switch (input) {
        case 'w': // Up arrow
          for (int i=0;i<2;++i){
            bleMouse.move(0, -127);  // negative Y = up
            delay(100);
          }
          Serial.println("↑");
          break;

        case 's': // Down arrow
          for (int i=0;i<2;++i){
            bleMouse.move(0, 127);  // negative Y = up
            delay(100);
          }
          Serial.println("↓");
          break;

        case 'a': // Left arrow
          for (int i=0;i<2;++i){
            bleMouse.move(-50, 0);  // negative Y = up
            delay(50);
          }
          Serial.println("←");
          break;

        case 'd': // Right arrow
          for (int i=0;i<2;++i){
            bleMouse.move(50, 0);  // negative Y = up
            delay(40);
          }
          Serial.println("→");
          break;

        case 'c': // Click
          bleMouse.click(MOUSE_LEFT);
          Serial.println("Click");
          break;

        case 'r': // Right click
          bleMouse.click(MOUSE_RIGHT);
          Serial.println("Right click");
          break;

        case 'm': // Middle click
          bleMouse.click(MOUSE_MIDDLE);
          Serial.println("Middle click");
          break;

        default:
          Serial.print("Unknown input: ");
          Serial.println(input);
          break;
      }
    }
  } else {
    // Not connected yet
    delay(500);
  }
}
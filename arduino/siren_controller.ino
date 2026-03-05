/*
  Elevator Siren Controller - Arduino

  PC에서 Serial(JSON)로 명령을 받아 릴레이를 ON/OFF 합니다.

  수신 형식: {"elevator":"elevator_1","floor":3,"action":"ON"}
  수신 형식: {"elevator":"elevator_1","floor":3,"action":"OFF"}

  배선:
    D2 = 1층 릴레이 (CH1)
    D3 = 2층 릴레이 (CH2)
    D4 = 3층 릴레이 (CH3)
    D5 = 4층 릴레이 (CH4)

  Baud Rate: 9600
*/

// 릴레이 핀 매핑 (층 번호 -> 디지털 핀)
const int RELAY_PINS[] = {0, 2, 3, 4, 5};  // index 0은 미사용, 1~4층
const int NUM_FLOORS = 4;

// 릴레이 활성 레벨 (대부분의 릴레이 모듈은 LOW가 ON)
const int RELAY_ON  = LOW;
const int RELAY_OFF = HIGH;

String inputBuffer = "";

void setup() {
  Serial.begin(9600);

  // 릴레이 핀 초기화 (모두 OFF)
  for (int i = 1; i <= NUM_FLOORS; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], RELAY_OFF);
  }

  Serial.println("{\"status\":\"ready\",\"floors\":4}");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      processCommand(inputBuffer);
      inputBuffer = "";
    } else {
      inputBuffer += c;
    }
  }
}

void processCommand(String json) {
  // 간단한 JSON 파싱 (ArduinoJson 라이브러리 없이)
  int floor = 0;
  String action = "";

  // "floor": 숫자 파싱
  int floorIdx = json.indexOf("\"floor\"");
  if (floorIdx >= 0) {
    int colonIdx = json.indexOf(':', floorIdx);
    if (colonIdx >= 0) {
      String floorStr = "";
      for (int i = colonIdx + 1; i < json.length(); i++) {
        char ch = json.charAt(i);
        if (ch >= '0' && ch <= '9') {
          floorStr += ch;
        } else if (floorStr.length() > 0) {
          break;
        }
      }
      floor = floorStr.toInt();
    }
  }

  // "action": "ON" 또는 "OFF" 파싱
  int actionIdx = json.indexOf("\"action\"");
  if (actionIdx >= 0) {
    if (json.indexOf("ON", actionIdx) >= 0 && json.indexOf("OFF", actionIdx) < 0) {
      action = "ON";
    } else if (json.indexOf("OFF", actionIdx) >= 0) {
      action = "OFF";
    }
  }

  // 유효성 검사
  if (floor < 1 || floor > NUM_FLOORS) {
    Serial.println("{\"error\":\"invalid floor\"}");
    return;
  }
  if (action != "ON" && action != "OFF") {
    Serial.println("{\"error\":\"invalid action\"}");
    return;
  }

  // 릴레이 제어
  if (action == "ON") {
    digitalWrite(RELAY_PINS[floor], RELAY_ON);
    Serial.print("{\"floor\":");
    Serial.print(floor);
    Serial.println(",\"relay\":\"ON\"}");
  } else {
    digitalWrite(RELAY_PINS[floor], RELAY_OFF);
    Serial.print("{\"floor\":");
    Serial.print(floor);
    Serial.println(",\"relay\":\"OFF\"}");
  }
}

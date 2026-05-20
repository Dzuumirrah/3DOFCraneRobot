/*
ESP32 Robot Crane Firmware

Serial protocol: newline-delimited JSON.

Commands from Python:
  {"command":"MOVE","theta":45.0,"r":25.0,"h":20.0,"magnet":true}
  {"command":"HOME"}
  {"command":"ESTOP"}
  {"command":"STATUS"}

Feedback to Python:
  {"status":"READY"}
  {"status":"MOVING"}
  {"status":"DONE"}
  {"status":"ERROR","message":"Invalid command"}
  {"type":"position","theta":90.0,"r":25.0,"h":0.0}
*/

#include <Arduino.h>
#include <ArduinoJson.h>

#define SERIAL_BAUDRATE 9600
#define TIMEOUT_MS 30000

#define S_MOTOR_THETA_PIN 14
#define S_MOTOR_THETA_DIR 27
#define S_MOTOR_R_PIN 12
#define S_MOTOR_R_DIR 26
#define DC_MOTOR_H_PIN 13
#define DC_MOTOR_H_DIR 25
#define MAGNET_PIN 23

const float HOME_POSITION[3] = {90.0, 25.0, 0.0};   // theta_deg (base), r_cm (shoulder), h_cm (hoist)

enum CommandType {
  CMD_MOVE,
  CMD_HOME,
  CMD_ESTOP,
  CMD_STATUS,
  CMD_INVALID
};

struct Command {
  CommandType type;
  float theta_deg;
  float r_cm;
  float h_cm;
  bool magnet_on;
};

enum SystemState {
  STATE_IDLE,
  STATE_MOVING,
  STATE_ESTOP,
  STATE_ERROR
};

SystemState current_state = STATE_IDLE;
Command current_command;
unsigned long last_command_time = 0;

float current_theta = 0.0;
float current_r = 0.0;
float current_h = 0.0;

void executeCommand(Command cmd);
void moveMotors(float theta_deg, float r_cm, float h_cm, bool magnet_on);
void emergencyStop();
void updateMotorFeedback();
void reportStatus();

void sendStatus(const char *status) {
  JsonDocument doc;
  doc["status"] = status;
  serializeJson(doc, Serial);
  Serial.println();
}

void sendError(const char *message) {
  JsonDocument doc;
  doc["status"] = "ERROR";
  doc["message"] = message;
  serializeJson(doc, Serial);
  Serial.println();
}

void sendPosition() {
  JsonDocument doc;
  doc["type"] = "position";
  doc["theta"] = current_theta;
  doc["r"] = current_r;
  doc["h"] = current_h;
  serializeJson(doc, Serial);
  Serial.println();
}

const char *stateToString(SystemState state) {
  switch (state) {
    case STATE_IDLE:
      return "IDLE";
    case STATE_MOVING:
      return "MOVING";
    case STATE_ESTOP:
      return "ESTOP";
    case STATE_ERROR:
      return "ERROR";
    default:
      return "UNKNOWN";
  }
}

Command parseCommand(const String &input) {
  /*
    Parses a JSON command string and returns a Command struct.
    expected input:
    {"command":"MOVE",
        "theta":45.0,
        "r":25.0,
        "h":20.0,
        "magnet":true
    }
    {"command":"HOME"}
    {"command":"ESTOP"}
    {"command":"STATUS"}    
  */
  
  Command cmd;
  cmd.type = CMD_INVALID;
  cmd.theta_deg = 0.0;
  cmd.r_cm = 0.0;
  cmd.h_cm = 0.0;
  cmd.magnet_on = false;

  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, input);
  if (error) {
    sendError("Invalid JSON");
    return cmd;
  }

  const char *command = doc["command"] | "";

  if (strcmp(command, "MOVE") == 0) {
    if (!doc["theta"].is<float>() || !doc["r"].is<float>() || !doc["h"].is<float>()) {
      sendError("MOVE requires theta, r, and h");
      return cmd;
    }

    cmd.type = CMD_MOVE;
    cmd.theta_deg = doc["theta"].as<float>();
    cmd.r_cm = doc["r"].as<float>();
    cmd.h_cm = doc["h"].as<float>();
    cmd.magnet_on = doc["magnet"] | false;
  } else if (strcmp(command, "HOME") == 0) {
    cmd.type = CMD_HOME;
    cmd.theta_deg = 90.0;
    cmd.r_cm = 25.0;
    cmd.h_cm = 0.0;
    cmd.magnet_on = false;
  } else if (strcmp(command, "ESTOP") == 0) {
    cmd.type = CMD_ESTOP;
  } else if (strcmp(command, "STATUS") == 0) {
    cmd.type = CMD_STATUS;
  } else {
    sendError("Invalid command");
  }

  return cmd;
}

void setup() {
  Serial.begin(SERIAL_BAUDRATE);

  pinMode(S_MOTOR_THETA_PIN, OUTPUT);
  pinMode(S_MOTOR_THETA_DIR, OUTPUT);
  pinMode(S_MOTOR_R_PIN, OUTPUT);
  pinMode(S_MOTOR_R_DIR, OUTPUT);
  pinMode(DC_MOTOR_H_PIN, OUTPUT);
  pinMode(DC_MOTOR_H_DIR, OUTPUT);
  pinMode(MAGNET_PIN, OUTPUT);

  digitalWrite(MAGNET_PIN, LOW);

  sendStatus("READY");
  current_state = STATE_IDLE;
  last_command_time = millis();
}

void loop() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input.length() > 0) {
      Command cmd = parseCommand(input);

      if (cmd.type != CMD_INVALID) {
        current_command = cmd;
        last_command_time = millis();
        executeCommand(cmd);
      }
    }
  }

  if (millis() - last_command_time > TIMEOUT_MS && current_state != STATE_ESTOP) {
    emergencyStop();
  }

  updateMotorFeedback();
}

void executeCommand(Command cmd) {
  switch (cmd.type) {
    case CMD_MOVE:
      moveMotors(cmd.theta_deg, cmd.r_cm, cmd.h_cm, cmd.magnet_on);
      break;
    case CMD_HOME:
      moveMotors(HOME_POSITION[0], HOME_POSITION[1], HOME_POSITION[2], false);
      break;
    case CMD_ESTOP:
      emergencyStop();
      break;
    case CMD_STATUS:
      reportStatus();
      break;
    case CMD_INVALID:
      sendError("Invalid command");
      break;
  }
}

void moveMotors(float theta_deg, float r_cm, float h_cm, bool magnet_on) {
  current_state = STATE_MOVING;
  sendStatus("MOVING");

  digitalWrite(MAGNET_PIN, magnet_on ? HIGH : LOW);

  // TODO: Replace this delay with non-blocking stepper control.
  delay(2000);

  current_theta = theta_deg;
  current_r = r_cm;
  current_h = h_cm;

  sendPosition();
  sendStatus("DONE");
  current_state = STATE_IDLE;
}

void emergencyStop() {
  current_state = STATE_ESTOP;

  digitalWrite(S_MOTOR_THETA_PIN, LOW);
  digitalWrite(S_MOTOR_R_PIN, LOW);
  digitalWrite(DC_MOTOR_H_PIN, LOW);
  digitalWrite(MAGNET_PIN, LOW);

  sendError("EMERGENCY_STOP");
}

void updateMotorFeedback() {
  // TODO: Read encoders and update current_theta, current_r, and current_h.
}

void reportStatus() {
  sendPosition();
  sendStatus(stateToString(current_state));
}

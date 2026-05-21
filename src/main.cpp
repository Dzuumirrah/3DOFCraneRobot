#include <Arduino.h>
#include <AccelStepper.h>
#include <ArduinoJson.h>

#define DRIVER_ENABLE 8
#define DEGREES_PER_STEP 1.8
#define ROTATOR_GEAR_RATIO 3.25
#define SLIDER_GEAR_DIAMETER 37.5
#define OBJECT_CENTER_OFFSET 11.5

#define MOTOR_DC_PWM1 9
#define MOTOR_DC_PWM2 10
#define LIMIT_ROTATOR A4
#define LIMIT_SLIDER A5

/// @brief Status stepper motor
typedef enum {
  BUSY,
  READY
} Stepper_Status_t;

/// @brief Status motor DC
typedef enum {
  MOTOR_RUNNING,
  MOTOR_STOPPED
} MotorDC_Status_t;

/// @brief Perintah sistem
typedef enum {
  STANDBY,

  SEQ_MOVE_START,
  
  SEQ_MOVE_DC_REVERSE_INITIAL,
  SEQ_MOVE_DC_REVERSE_INITIAL_WAIT,
  
  SEQ_MOVE_STEPPER,
  SEQ_MOVE_STEPPER_WAIT,
  
  SEQ_MOVE_DELAY,
  SEQ_MOVE_DELAY_WAIT,
  
  SEQ_MOVE_DC_FORWARD,
  SEQ_MOVE_DC_FORWARD_WAIT,

  SEQ_MOVE_POST_DELAY,
  SEQ_MOVE_POST_DELAY_WAIT,
  
  SEQ_MOVE_DC_REVERSE_FINAL,
  SEQ_MOVE_DC_REVERSE_FINAL_WAIT,


  SEQ_HOME_INIT,
  SEQ_HOME_DC_UP,
  SEQ_HOME_DC_UP_WAIT,
  SEQ_HOME_START,
  SEQ_HOME_RUNNING,

  STOP,
  STATUS
} System_Command_t;

/// @brief Inisialisasi objek AccelStepper untuk slider dan rotator
AccelStepper slider(AccelStepper::DRIVER, 2, 5);
AccelStepper rotator(AccelStepper::DRIVER, 3, 6);

/// @brief Status dan variabel global lainnya
Stepper_Status_t slider_status = READY;
Stepper_Status_t rotator_status = READY;
MotorDC_Status_t motor_dc_status = MOTOR_STOPPED;

System_Command_t current_command = STANDBY;
System_Command_t last_command = STANDBY;

String inputBuffer = "";
unsigned long sequenceTimeout = 0;

double target_theta = 0.0;
double target_r = 0.0;
double target_h = 0.0;
bool target_magnet = false;

bool is_dc_motor_down = false;


/// @brief  Konversi panjang dalam cm ke jumlah langkah untuk slider
/// @param lenCm 
/// @return 
long lenToStep(double lenCm) {
  double lenMm = lenCm * 10.0; 
  double circumference = 3.14159265f * SLIDER_GEAR_DIAMETER;
  double stepsPerRev = 360.0f / DEGREES_PER_STEP;
  double steps = (lenMm / circumference) * stepsPerRev;
  
  return round(steps);
}

/// @brief  Konversi sudut dalam derajat ke jumlah langkah untuk rotator
/// @param degree 
/// @return 
long degToStep(double degree) {
  double motorSteps = degree / DEGREES_PER_STEP;
  
  return round(motorSteps * ROTATOR_GEAR_RATIO);
}

/// @brief  Konversi jumlah langkah ke panjang dalam cm untuk slider
/// @param steps 
/// @return 
double stepToLen(long steps) {
  double circumference = 3.14159265f * SLIDER_GEAR_DIAMETER;
  
  return ((double)steps * DEGREES_PER_STEP / 360.0f) * circumference;
}

/// @brief  Konversi jumlah langkah ke sudut dalam derajat untuk rotator
/// @param steps 
/// @return 
double stepToDeg(long steps) {
  return ((double)steps * DEGREES_PER_STEP) / ROTATOR_GEAR_RATIO;
}

/// @brief  Mengatur gerakan motor DC
/// @param pwm 
void motorDrive(int16_t pwm) {
  analogWrite(MOTOR_DC_PWM1, (pwm > 0) ? pwm : 0);
  analogWrite(MOTOR_DC_PWM2, (pwm < 0) ? -pwm : 0);
}

/// @brief  Memroses pesan JSON yang diterima
/// @param jsonString 
void processJSON(String jsonString) {
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, jsonString);

  if (error) {
    Serial.print("{\"status\":\"error\",\"msg\":\"Parsing gagal: ");
    Serial.print(error.f_str());
    Serial.println("\"}");
    return;
  }

  if (doc.containsKey("command")) {
    String cmdStr = doc["command"].as<String>();
    
    if (cmdStr == "MOVE") {
      
      if (doc.containsKey("theta"))   target_theta = doc["theta"].as<double>();
      if (doc.containsKey("r"))       target_r = doc["r"].as<double>() - OBJECT_CENTER_OFFSET;
      if (doc.containsKey("h"))       target_h = doc["h"].as<double>();
      if (doc.containsKey("magnet"))  target_magnet = doc["magnet"].as<bool>();

      current_command = SEQ_MOVE_START;
      
      Serial.println("{\"status\":\"ok\",\"msg\":\"Executing MOVE sequence\"}");

    } else if (cmdStr == "HOME") {
      
      current_command = SEQ_HOME_INIT;
      Serial.println("{\"status\":\"ok\",\"msg\":\"Executing HOME sequence\"}");

    } else if (cmdStr == "ESTOP") {
      
      current_command = STOP;
      Serial.println("{\"status\":\"emergency\",\"msg\":\"Sistem Berhenti Total\"}");

    } else if (cmdStr == "STATUS") {
      
      current_command = STATUS;
      
    }
  }
}

void setup() {
  Serial.begin(9600);
  
  pinMode(DRIVER_ENABLE, OUTPUT);
  pinMode(LIMIT_ROTATOR, INPUT_PULLUP);
  pinMode(LIMIT_SLIDER, INPUT_PULLUP);

  digitalWrite(DRIVER_ENABLE, HIGH);

  rotator.setAcceleration(500);
  rotator.setMaxSpeed(1000);
  rotator.setCurrentPosition(0);
  
  slider.setAcceleration(500);
  slider.setMaxSpeed(1000);
  slider.setCurrentPosition(0);

  rotator.setAcceleration(100);
  rotator.setMaxSpeed(300);
  
  slider.setAcceleration(100);
  slider.setMaxSpeed(300);

  rotator.setSpeed(-90);
  slider.setSpeed(-100);


  while (digitalRead(LIMIT_SLIDER) || digitalRead(LIMIT_ROTATOR)) {
    digitalWrite(DRIVER_ENABLE, LOW);
    
    if (digitalRead(LIMIT_ROTATOR) == HIGH) {
      rotator.runSpeed();
    }
    
    if (digitalRead(LIMIT_SLIDER) == HIGH) {
      slider.runSpeed();
    }
  }
  
  rotator.setCurrentPosition(0);
  slider.setCurrentPosition(0);
  
  digitalWrite(DRIVER_ENABLE, HIGH);
}

void loop() {
  while (Serial.available() > 0) {
    char inChar = (char)Serial.read();
    
    if (inChar == '\n') {
      processJSON(inputBuffer);
      inputBuffer = "";
    } else {
      inputBuffer += inChar;
    }
  }

  switch (current_command) {
    
    
    case SEQ_MOVE_START:
      if (target_magnet) {
        current_command = SEQ_MOVE_STEPPER;
      } else {
        current_command = SEQ_MOVE_DC_REVERSE_INITIAL;
      }
      break;

    case SEQ_MOVE_DC_REVERSE_INITIAL:
      motorDrive(-100);
      sequenceTimeout = millis() + 1000;
      current_command = SEQ_MOVE_DC_REVERSE_INITIAL_WAIT;
      break;

    case SEQ_MOVE_DC_REVERSE_INITIAL_WAIT:
      if (millis() >= sequenceTimeout) {
        motorDrive(0);
        is_dc_motor_down = false; 
        current_command = SEQ_MOVE_STEPPER;
      }
      break;

    case SEQ_MOVE_STEPPER:
      digitalWrite(DRIVER_ENABLE, LOW);
      
      rotator.moveTo(degToStep(target_theta));
      slider.moveTo(lenToStep(target_r));
      
      slider_status = BUSY;
      rotator_status = BUSY;
      
      current_command = SEQ_MOVE_STEPPER_WAIT;
      break;

    case SEQ_MOVE_STEPPER_WAIT:
      if (slider.distanceToGo() == 0 && rotator.distanceToGo() == 0) {
        current_command = SEQ_MOVE_DELAY;
      }
      break;

    case SEQ_MOVE_DELAY:
      digitalWrite(DRIVER_ENABLE, HIGH); 
      sequenceTimeout = millis() + 300;
      current_command = SEQ_MOVE_DELAY_WAIT;
      break;

    case SEQ_MOVE_DELAY_WAIT:
      if (millis() >= sequenceTimeout) {
        current_command = SEQ_MOVE_DC_FORWARD;
      }
      break;

    case SEQ_MOVE_DC_FORWARD:
      motorDrive(100);
      sequenceTimeout = millis() + 1000;
      current_command = SEQ_MOVE_DC_FORWARD_WAIT;
      break;

    case SEQ_MOVE_DC_FORWARD_WAIT:
      if (millis() >= sequenceTimeout) {
        motorDrive(0); 
        is_dc_motor_down = true; 
        
        if (target_magnet) {
          current_command = STANDBY;
        } else {
          current_command = SEQ_MOVE_POST_DELAY;
        }
      }
      break;

    case SEQ_MOVE_POST_DELAY:
      sequenceTimeout = millis() + 1000;
      current_command = SEQ_MOVE_POST_DELAY_WAIT;
      break;

    case SEQ_MOVE_POST_DELAY_WAIT:
      if (millis() >= sequenceTimeout) {
        current_command = SEQ_MOVE_DC_REVERSE_FINAL;
      }
      break;

    case SEQ_MOVE_DC_REVERSE_FINAL:
      motorDrive(-100);
      sequenceTimeout = millis() + 1000;
      current_command = SEQ_MOVE_DC_REVERSE_FINAL_WAIT;
      break;

    case SEQ_MOVE_DC_REVERSE_FINAL_WAIT:
      if (millis() >= sequenceTimeout) {
        motorDrive(0);
        is_dc_motor_down = false; 
        current_command = STANDBY;
      }
      break;



    case SEQ_HOME_INIT:
      if (is_dc_motor_down) {
        current_command = SEQ_HOME_DC_UP;
      } else {
        current_command = SEQ_HOME_START;
      }
      break;

    case SEQ_HOME_DC_UP:
      motorDrive(-100); 
      sequenceTimeout = millis() + 1000;
      current_command = SEQ_HOME_DC_UP_WAIT;
      break;

    case SEQ_HOME_DC_UP_WAIT:
      if (millis() >= sequenceTimeout) {
        motorDrive(0);
        is_dc_motor_down = false; 
        current_command = SEQ_HOME_START;
      }
      break;

    case SEQ_HOME_START:
      digitalWrite(DRIVER_ENABLE, LOW);
      
      rotator.setSpeed(-90);
      slider.setSpeed(-100);
      
      slider_status = BUSY;
      rotator_status = BUSY;
      
      current_command = SEQ_HOME_RUNNING;
      break;

    case SEQ_HOME_RUNNING:

      if (digitalRead(LIMIT_ROTATOR) == LOW && digitalRead(LIMIT_SLIDER) == LOW) {
        
        rotator.setCurrentPosition(0);
        slider.setCurrentPosition(0);
        
        target_theta = 0.0;
        target_r = 0.0;
        
        current_command = STANDBY;
      }
      break;



    case STOP:
      digitalWrite(DRIVER_ENABLE, LOW); 
      
      slider.stop();
      rotator.stop();
      motorDrive(0); 
      
      slider_status = READY;
      rotator_status = READY;
      
      target_r = stepToLen(slider.currentPosition());
      target_theta = stepToDeg(rotator.currentPosition());
      
      current_command = STANDBY;
      break;

    case STATUS:
      {
        JsonDocument statusDoc;
        
        statusDoc["slider"] = (slider_status == READY) ? "READY" : "BUSY";
        statusDoc["rotator"] = (rotator_status == READY) ? "READY" : "BUSY";
        statusDoc["slider_pos"] = slider.currentPosition();
        statusDoc["rotator_pos"] = rotator.currentPosition();
        
        serializeJson(statusDoc, Serial);
        Serial.println();
      }
      
      current_command = STANDBY;
      break;

    case STANDBY:
      if (slider.distanceToGo() == 0) {
        slider_status = READY;
      } else {
        slider_status = BUSY;
      }

      if (rotator.distanceToGo() == 0) {
        rotator_status = READY;
      } else {
        rotator_status = BUSY;
      }

      if (slider_status == READY && rotator_status == READY) {
        digitalWrite(DRIVER_ENABLE, HIGH);
      }
      break;
  }



  if (digitalRead(DRIVER_ENABLE) == LOW) {
    
    if (current_command == SEQ_HOME_RUNNING) {
      
      if (digitalRead(LIMIT_ROTATOR) == HIGH) {
        rotator.runSpeed();
      }
      
      if (digitalRead(LIMIT_SLIDER) == HIGH) {
        slider.runSpeed();
      }
      
    } else {
      slider.run();
      rotator.run();
    }
  }
}
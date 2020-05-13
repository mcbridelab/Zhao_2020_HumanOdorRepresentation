/* -----------------------------------------------------------------------------
 * Zhilei Zhao, Princeton University 
 *----------------------------------------------------------------------------*/

#include "CmdMessenger.h"
// manually edit this header file, increase MESSENGERBUFFERSIZE to 512

/* Define available CmdMessenger commands */
enum {
    start_PID_log,
};

int sampling = 20;  // sampling interval in units of ms

/* Initialize CmdMessenger -- this should match PyCmdMessenger instance */
CmdMessenger c = CmdMessenger(Serial,',',';','/');

void on_start_PID_log(void){
  unsigned long last_update = millis();  // get the current time
  int sensorValue;
  while(1){
    while(millis() - last_update < sampling){
      sensorValue = analogRead(A2);  // keep reading untile the sampling interval
    }
    Serial.println(sensorValue);  // print out the last read
    last_update = millis();
  }
}

/* Attach callbacks for CmdMessenger commands */
void attach_callbacks(void) { 
    c.attach(start_PID_log, on_start_PID_log);
}

// the setup routine runs once when you press reset:
void setup() {
  // initialize serial communication at 9600 bits per second:
  Serial.begin(115200);
  attach_callbacks(); 
}


void loop() {
    c.feedinSerialData();
}

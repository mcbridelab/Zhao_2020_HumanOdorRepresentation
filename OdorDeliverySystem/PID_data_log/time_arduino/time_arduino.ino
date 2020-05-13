/* -----------------------------------------------------------------------------
 * Zhilei Zhao, Princeton University 
 *----------------------------------------------------------------------------*/

#include "CmdMessenger.h"
// manually edit this header file, increase MESSENGERBUFFERSIZE to 512

/* Define available CmdMessenger commands */
enum {
    start_time_it,
};

/* Initialize CmdMessenger -- this should match PyCmdMessenger instance */
CmdMessenger c = CmdMessenger(Serial,',',';','/');

void on_start_time_it(void){
  unsigned long millis_now = millis();
//  Serial.println(millis_now);
  while(millis() - millis_now < 18000){}
  Serial.println(millis()- millis_now);
}
/* Attach callbacks for CmdMessenger commands */
void attach_callbacks(void) { 
    c.attach(start_time_it, on_start_time_it);
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

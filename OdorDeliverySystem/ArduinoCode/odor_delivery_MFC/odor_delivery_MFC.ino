/* -----------------------------------------------------------------------------
 * Zhilei Zhao, Princeton University 
 *----------------------------------------------------------------------------*/

#include "CmdMessenger.h"
// manually edit this header file, increase MESSENGERBUFFERSIZE to 512

/* Define available CmdMessenger commands */
enum {
    flow_setup,
    trigger_markes,
};

/* Initialize CmdMessenger -- this should match PyCmdMessenger instance */
CmdMessenger c = CmdMessenger(Serial,',',';','/');

// MFCs, need to use PWM pins
int ctrlMFC = 5;
int carrierMFC = 9;
int odorMFC = 6;
int CO2MFC = 10;
int ctrl2MFC = 11;

// pins to trigger the Markes system
int markes = 4;


/* function to deal with long delay */
void delay_long(int ten_ms){
  unsigned long millis_now = millis();
  long factor = 10;
  long ms = ten_ms * factor;  // int multiplication is tricky
  while(millis() - millis_now < ms){}
}


void on_flow_setup(void){
    /* grab the MFC flow rate */
    int carrierFlow = c.readBinArg<int>();
    int ctrlFlow = c.readBinArg<int>();
    int odorFlow = c.readBinArg<int>();
    int CO2Flow = c.readBinArg<int>();
    int ctrl2Flow = c.readBinArg<int>();
    /* change flow rate */
    analogWrite(carrierMFC, carrierFlow);
    analogWrite(odorMFC, odorFlow);
    analogWrite(ctrlMFC, ctrlFlow);  
    analogWrite(CO2MFC, CO2Flow);
    analogWrite(ctrl2MFC, ctrl2Flow);
}


void on_trigger_markes(void){
  /* send signal to the Markes input pins, make the GC ready */
  // read in the trigger on duration, unit is sec
  int trigger_duration = c.readBinArg<int>();
  // for markes trigger, the logic is reversed, HIGH means no trigger
  digitalWrite(markes, LOW);
  // send the time to python when trigger is on
  Serial.print(1);
  int delay_duration = trigger_duration * 100;
  delay_long(delay_duration);
  digitalWrite(markes, HIGH);
}


/* Attach callbacks for CmdMessenger commands */
void attach_callbacks(void) { 
    c.attach(flow_setup, on_flow_setup);
    c.attach(trigger_markes, on_trigger_markes);
}

void setup() {
    Serial.begin(115200);
    attach_callbacks(); 
    // set the default MFC value
    // default: carrier 400mL/min, odor/ctrl 400mL/min, CO2 33mL/min
    analogWrite(carrierMFC, 109);
    analogWrite(odorMFC, 219);
    analogWrite(ctrlMFC, 108);  
    analogWrite(CO2MFC, 35);
    analogWrite(ctrl2MFC, 35); 
    pinMode(markes, OUTPUT);
    

//    // for calibration:
//    int flow = 50;
//    analogWrite(carrierMFC, flow);
//    analogWrite(odorMFC, flow);
//    analogWrite(ctrlMFC, flow);  
//    analogWrite(CO2MFC, flow);
//    analogWrite(ctrl2MFC, flow); 
}

void loop() {
    c.feedinSerialData();
    // for markes trigger, the logic is reversed, HIGH means no trigger
    digitalWrite(markes, HIGH);
//    delay(10000);
//    digitalWrite(markes, HIGH);
//    delay(100);
}

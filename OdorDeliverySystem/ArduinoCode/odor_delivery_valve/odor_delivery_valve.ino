/* -----------------------------------------------------------------------------
 * Zhilei Zhao, Princeton University
 *----------------------------------------------------------------------------*/

#include "CmdMessenger.h"
// manually edit this header file, increase MESSENGERBUFFERSIZE to 512

/* Define available CmdMessenger commands */
enum {
    open_odor_valve,
    switch_panel,
    extra_flush,
    purge_system,
    solvent_wash,
    open_CO2_valve,
    open_odor_CO2,
};

/* Initialize CmdMessenger -- this should match PyCmdMessenger instance */
CmdMessenger c = CmdMessenger(Serial,',',';','/');

// set preparation time for odor channel to fill the tubing line
int prepare = 100;  // in units of 10ms


/* settings for IO pins*/
/* specify pins for MFCs and valves here */
/* need to be consistent with python script */
// master valves on the final mixing manifold
// valve for odor stream
int masterOdorValve = 4;
// control valve for control stream 1
int masterCtrlValve = 3;  // a N.O. 3-way valve
// valve for CO2 stream
int masterCO2Valve = 2;
// control valve for control stream 2
int masterCtrl2Valve = 5;


// source valves on the source manifold to input filter air
int sourceValves[] = {65,64}; // N.C. 3-way valve, mounted as N.O., corresponding to 1st and 2nd panel
// flush channel valves
// a pair of N.C. 2-way valves mounted one each panel to flush residual odorants with low flow rate
int flushInPins[] = {7,40};
int flushOutPins[] = {38,63};
// odor channel valves
// put pins for two panels together in a list
int allInPins[] =  {9,12, 23, 25, 27, 29, 31, 33, 35, 37, 39, 42, 44, 46, 48, 67, 52, 66, 56, 58, 60, 62};  // in the order of channel A, B, C...
int allOutPins[] = {6, 8, 11, 22, 24, 26, 28, 30, 32, 34, 36, 41, 43, 45, 47, 49, 68, 53, 55, 69, 59, 61};  // same order as input
int allDigitalPins[70];
// pins for the flush stream valves with high flow rate
int vacuumOutPins[] = {36, 62};
//int flushDur = 300;  // in unit of 10ms
//int vacuumDur = 4000; // in unit of 10ms


// a volatile variabe to indicate which panel is in use
volatile int panel = 0;  // default is the fist panel
// get the pin for current panel
volatile int flushIn = flushInPins[panel];
volatile int flushOut = flushOutPins[panel];
volatile int vacuumOut = vacuumOutPins[panel];


/* function to deal with long delay */
void delay_long(int ten_ms){
  unsigned long millis_now = millis();
  long factor = 10;
  long ms = ten_ms * factor;  // int multiplication is tricky
  while(millis() - millis_now < ms){}
}


/* function to operate the odor panel valves */
void valve_operation(int in, int out, int dur){
  // open the specified channel and close flush channel on the same pannel
  // but keep masterOdorValve to exhaust
  digitalWrite(in, HIGH);
  digitalWrite(out, HIGH);
  digitalWrite(flushIn, LOW);
  digitalWrite(flushOut, LOW);
  // wait for the odor to fill the tubing space
  delay_long(prepare);
  // open the masterOdorValve to pressure, close the masterCtrlVale to exhaust
  digitalWrite(masterOdorValve, HIGH);
  digitalWrite(masterCtrlValve, HIGH);  // since masterCtrlValve is N.O.
  // send the time to python when valve open
  Serial.print(1);
  // delay for the specified duration to keep odor channel ON
  delay_long(dur);
  // close the masterOdorValve to exhaust, open the masterCtrlVale to pressure
  digitalWrite(masterOdorValve, LOW);
  digitalWrite(masterCtrlValve, LOW);  // since masterCtrlValve is N.O.
  // send the time to python when valve close
  Serial.print(1);
  // close the specified valve and open flush channel to clean the Panel manifold
  digitalWrite(in, LOW);
  digitalWrite(out, LOW);
  digitalWrite(flushIn, HIGH);
  digitalWrite(flushOut, HIGH);
}


/* Create callback functions to deal with incoming messages */
void on_open_odor_valve(void){
  // write into serial so python know when arduino receives the command
  Serial.print(1);
  int idx = c.readBinArg<int>() - 65;  // which valve, A is ascii 65
  int inPin = allInPins[idx];
  int outPin = allOutPins[idx];
  int duration = c.readBinArg<int>();  // in units of 10ms
  valve_operation(inPin, outPin, duration);
}


/* function to open the CO2 valve */
void on_open_CO2_valve(void){
  // open the CO2 master valve
  // write into serial so python know when arduino receives the command
  int duration = c.readBinArg<int>();  // in units of 10ms
  int timestamp = c.readBinArg<int>(); // 1 or 0
  Serial.print(1);
  // open the CO2 valve, while close the control valve
  digitalWrite(masterCO2Valve, HIGH);
  digitalWrite(masterCtrl2Valve, HIGH);  // since masterCtrlValve is N.O.
  // send the time to python when valve open
  Serial.print(1);
  // delay for the specified duration to keep odor channel ON
  delay_long(duration);
  // close the masterOdorValve to exhaust, open the masterCtrlVale to pressure
  digitalWrite(masterCO2Valve, LOW);
  digitalWrite(masterCtrl2Valve, LOW);  // since masterCtrlValve is N.O.
  // send the time to python when valve close
  Serial.print(1);
}


/* function to open odor and CO2 valve the same time */
void on_open_odor_CO2(void){
  Serial.print(1);
  int idx = c.readBinArg<int>() - 65;  // which valve, A is ascii 65
  int in = allInPins[idx];
  int out = allOutPins[idx];
  int dur = c.readBinArg<int>();  // in units of 10ms
   // open the specified channel and close flush channel on the same pannel
  // but keep masterOdorValve to exhaust
  digitalWrite(in, HIGH);
  digitalWrite(out, HIGH);
  digitalWrite(flushIn, LOW);
  digitalWrite(flushOut, LOW);
  // wait for the odor to fill the tubing space
  delay_long(prepare);
  // open the masterOdorValve to pressure, close the masterCtrlVale to exhaust
  digitalWrite(masterOdorValve, HIGH);
  digitalWrite(masterCtrlValve, HIGH);  // since masterCtrlValve is N.O.
  digitalWrite(masterCO2Valve, HIGH);
  digitalWrite(masterCtrl2Valve, HIGH);  // since masterCtrlValve is N.O.
  // send the time to python when valve open
  Serial.print(1);
  // delay for the specified duration to keep odor channel ON
  delay_long(dur);
  // close the masterOdorValve to exhaust, open the masterCtrlVale to pressure
  digitalWrite(masterOdorValve, LOW);
  digitalWrite(masterCtrlValve, LOW);  // since masterCtrlValve is N.O.
  digitalWrite(masterCO2Valve, LOW);
  digitalWrite(masterCtrl2Valve, LOW);  // since masterCtrlValve is N.O.
  // send the time to python when valve close
  Serial.print(1);
  // close the specified valve and open flush channel to clean the Panel manifold
  digitalWrite(in, LOW);
  digitalWrite(out, LOW);
  digitalWrite(flushIn, HIGH);
  digitalWrite(flushOut, HIGH);
}

/* function to switch between the two odor panels */
void on_switch_panel(void){
  // switch the source valve, update the pin for flush and masterOdorValve
  digitalWrite(flushInPins[panel],LOW);
  digitalWrite(flushOutPins[panel],LOW);
  if(panel==0){
    digitalWrite(sourceValves[0], LOW);
    digitalWrite(sourceValves[1], HIGH);
    panel = 1;
  }
  else{
    digitalWrite(sourceValves[0], HIGH);
    digitalWrite(sourceValves[1], LOW);
    panel = 0;
  }
  flushIn = flushInPins[panel];
  flushOut = flushOutPins[panel];
  vacuumOut = vacuumOutPins[panel];
  digitalWrite(flushIn, HIGH);
  digitalWrite(flushOut, HIGH);
}


/* extra flush with high flow rate */
void on_extra_flush(void){
  int pre_flush_dur = c.readBinArg<int>();  // in units of 10ms
  int extra_flush_dur = c.readBinArg<int>();  // in units of 10ms
  // flush some seconds with z-flush line
  delay_long(pre_flush_dur);
  // open the extra flush line
  digitalWrite(vacuumOut, HIGH);
//  digitalWrite(vacuumOutOther, LOW);
  // flush some seconds with z + extra lines
  delay_long(extra_flush_dur);
  // close the extra flush to balance flow rate
  digitalWrite(vacuumOut, LOW);
//  digitalWrite(vacuumOutOther, HIGH);
}


/* function to purge the system with clean air */
void on_purge_system(void){
  // get num of purges to perform
  int numP = c.readBinArg<int>();
  for(int n=0; n<numP; n++){
    // loop through two panels
    for(int p=0; p<2; p++){
      // open the master valve to purge to animal for 30 sec
//      digitalWrite(masterOdorValve, HIGH);
      digitalWrite(flushIn, HIGH);
      digitalWrite(flushOut, HIGH);
      // open the vaccumOut valve to allow high flow rate stream
      digitalWrite(vacuumOut, HIGH);
      delay_long(6000);
//      digitalWrite(masterOdorValve, LOW);
      // open each valve sequentially to purge the valve and fittings
      // close the z-flush, so all air comes out from input fittings
      for(int c=0; c<10; c++){
        int pinIdx = 11 * panel + c;
        int inPinNow = allInPins[pinIdx];
        int outPinNow = allOutPins[pinIdx];
        digitalWrite(inPinNow, HIGH);
        digitalWrite(outPinNow, HIGH);
        // purge for 3mins
        delay_long(18000);
        digitalWrite(inPinNow, LOW);

//        delay_long(6000);
        digitalWrite(outPinNow, LOW);
      }
      // close the vaccumOut valve
      digitalWrite(vacuumOut, LOW);
      on_switch_panel();
    }
  }
}


/* function to wash the system with solvent hexane */
void on_solvent_wash(void){
  // flow solvent through the system to wash odorant residuals
  // wait a few seconds for MFC to reach setting values
  delay_long(2000);
  // first manifold panel
  // close the Z-in
  digitalWrite(flushIn, LOW);
  // open the in valvles sequentially to flow solvent
  for(int c=0; c<10; c++){
    int pinIdx = 11 * panel + c;
    int inPinNow = allInPins[pinIdx];
    int outPinNow = allOutPins[pinIdx];
    digitalWrite(inPinNow, HIGH);
    // wash for 5 sec
    if(c==0){
      delay_long(1000);
    }else{
      delay_long(1000);
    }
    digitalWrite(inPinNow, LOW);
  }
  // open the Z-in
  digitalWrite(flushIn, HIGH);
  // delay a few seconds to allow solvent fill the tubing
  delay_long(1000);
  // open the in valvles sequentially to flow solvent
  for(int c=0; c<10; c++){
    int pinIdx = 11 * panel + c;
    int inPinNow = allInPins[pinIdx];
    int outPinNow = allOutPins[pinIdx];
    digitalWrite(outPinNow, HIGH);
    // wash for 5 sec
    if(c==0){
      delay_long(2000);
    }else{
      delay_long(2000);
    }
    digitalWrite(outPinNow, LOW);
  }
  // open the master valve to flow solvent for a few seconds
  digitalWrite(masterOdorValve, HIGH);
  delay_long(1000);
  digitalWrite(masterOdorValve, LOW);
}


/* Attach callbacks for CmdMessenger commands */
void attach_callbacks(void) {
    c.attach(open_odor_valve, on_open_odor_valve);
    c.attach(switch_panel, on_switch_panel);
    c.attach(extra_flush, on_extra_flush);
    c.attach(purge_system, on_purge_system);
    c.attach(solvent_wash, on_solvent_wash);
    c.attach(open_CO2_valve, on_open_CO2_valve);
    c.attach(open_odor_CO2, on_open_odor_CO2);
}


void setup() {
  // set all pins as OUTPUT
    for(int i=0; i<70; i++){
      pinMode(i, OUTPUT);
    }
    Serial.begin(115200);
    attach_callbacks();

    // default settings for valves
    // control valves should be open
    digitalWrite(masterCtrlValve, LOW);  // since masterCtrlValve is N.O.
    // odor valves should be closed
//    digitalWrite(masterOdorValves[0], LOW);
//    digitalWrite(masterOdorValves[1], LOW);
    digitalWrite(masterOdorValve, LOW);
    digitalWrite(masterCO2Valve, LOW);
    // flush channel on Panel One should be open
    digitalWrite(flushIn, HIGH);
    digitalWrite(flushOut, HIGH);
    // source valve on panel one should be open, panel two be closed at default
    digitalWrite(sourceValves[0], HIGH);
    digitalWrite(sourceValves[1], LOW);
    // the other extra flush valve should be open when start
//    digitalWrite(vacuumOutOther, HIGH);
}

void loop() {
    c.feedinSerialData();
}

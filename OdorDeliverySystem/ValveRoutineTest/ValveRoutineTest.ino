// which pins are connected to valves
int const numPins = 54;
int outPins[numPins] = {2,3,4,5,6,7,8,9,11,12,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65};

void setup() {
  int i;
  for (i=0;i<numPins;i=i+1){
     pinMode(outPins[i], OUTPUT);
  }
}

void loop() {
  // put your main code here, to run repeatedly:
  int j;
  int i;
  // to check if valves work properly and if there is crosslink bewteen valves
  // turn on valves that are not adjacent to each other, check the pattern of LED
  for (j=0; j<4; j++){
    for (i=j;i<numPins;i=i+4){
       digitalWrite(outPins[i], HIGH);
    }
    delay(15000);
    for (i=j;i<numPins;i=i+4){
       digitalWrite(outPins[i], LOW);
    }
    delay(5000);
  }
}

# Zhao_2020_HumanOdorRepresentation
Codes for Zhao et al, 2020. A robust neural code for human odour in the Aedes aegypti mosquito brain.    
bioRxiv link:     
<br>
Notes:
- ArduinoPlot: used to read and plot photoionization detector (PID) data, forked from https://github.com/gregpinero/ArduinoPlot
- OdorDeliverySystem: Arduino codes and Python GUI for odor delivery system
  - ArduinoCode needs to be uploaded to Arduino boards.
  - Install Python modules in required_modules.txt
  - Change com port names in MarkesSingleOdorants.py
  - Run in terminal: python MarkesSingleOdorants.py
  - Python version tested: 3.6
- TwoPhotonMosquitoHolder: design files for mosquito holder used for two-photon imaging
  - MosquitoHolder.stl: 3D printed plastic frames
  - MosqMetalPlate.dxf: photochemically etched stainless steel plate

# Zhao_2020_HumanOdorRepresentation
Codes for Zhao et al, 2020. Chemical signatures of human odour generate a unique neural code in the brain of _Aedes aegypti_ mosquitoes. bioRxiv, [https://doi.org/10.1101/2020.11.01.363861](https://doi.org/10.1101/2020.11.01.363861)       
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
  - MosquitoHolder.stl: 3D-printed plastic frame
  - MosqMetalPlate.dxf: photochemically etched stainless steel plate

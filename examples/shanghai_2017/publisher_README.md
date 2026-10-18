# The Dataset Used in Energy Detective 2020
## Dataset description
With the prediction case provided in the competition, which is to predict the energy consumption of a building with some physical information but without historical data of its own, the dataset will include two parts, which is the test building dataset and the reference building dataset. The test building dataset includes more data about the physical description for the building while the reference building dataset includes more historical consumption data.     
All the hourly energy consumption data comes from office buildings located in Shanghai, China during 2015-2017. Energy consumption data is divided into two meter type in the data set. Energy cost by lights and plugs is one of the meter type (marked as “Q”) and that cost by the HVAC system is the other(marked as “W”).The consumption records of two meter types are gathered by raw meta data, which comes from a private dataset built by an energy management company.     
In the meanwhile, weather data is given in the dataset. And the weather data is collected by a real weather station in Shanghai, China.     

### test building dataset
#### test building information     
Basic building information and some physical parameters of the test building.     
Including:     
- Area
- Stairs (number of up ground and number of the underground)
- Type of HVAC terminals
- Thermal parameters of building envelope and windows (basement, podium and tower)
- Description of some energy-saving measures on building envelope
- Equipment information of the HVAC system (number and capacity of chillers and pumps)      

#### test building records     
The actual records of the hourly historical data of two meter types in 2017 for the test building.       
Including variables:      
- Time: timestamp
- Type: meter type (“Q” for light and plug and “W” for HVAC system)
- Record: hourly electric consumption (kWh)      

#### floor plan
Construction drawings of the target building.     
Including:     
- 7 typical floor plans in jpg format
- Brief introduction of the floor plans

### reference building dataset
#### reference building information     
Basic building information of the reference building.     
Including:     
- BuildingID: serial number of the reference building
- Space usage
- Stair1: number of stairs up ground 
- Stair2: number of stairs underground
- Area (m^2)
- HVACType: Type of HVAC terminals   

#### reference building records     
Hourly energy consumption data of the reference buildings during 2015 to 2017 in csv format.       
Including variables:      
- Time: timestamp   
- BuildingID: serial number of the reference building   
- Type: meter type (“Q” for light and plug and “W” for HVAC system)   
- Record: hourly electric consumption (kWh)       

### weather data     
Hourly weather data during 2015 to 2017 in epw format and csv format.        
Including variables:      
- Timestamp   
- Temperature (℃)   
- Dew point temperature (℃)   
- Relative humidity (%)   
- Atmospheric pressure (Pa)   
- Wind speed (m/s)   

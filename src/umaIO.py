import interface as uma
import json
import random

def readJsonUmaIncomingPackets(strPath : str) -> tuple[uma.Truck, list[uma.Package]]:
    with open(strPath, 'r') as file:
        data = json.load(file)
        uma_truck_data = data['uma_truck']
        uma_truck = uma.Truck(uma.Box(uma_truck_data['Dimensions'][0],uma_truck_data['Dimensions'][1],uma_truck_data['Dimensions'][2]), uma_truck_data['MaxCapacity'])
        packages_data = data['uma_packages']
        incoming_uma_packets : list[uma.Package] = []
        for obj in packages_data:
            incoming_uma_packets.append(readPackage(obj))
        

            
    return uma_truck, incoming_uma_packets

def readPackage(data) -> uma.Package:
    return uma.Package(data["id"], uma.Box(data['Dimensions'][0],data['Dimensions'][1],data['Dimensions'][2]), data['Orientation'], data['Value'], data['Weight'], data['IsFragile'], data['ETA'], color=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))



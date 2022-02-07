# ==========================================================================================================
# Import necessary modules
# ==========================================================================================================

import moteinogw
import struct
from timeit import default_timer as timer
import sys
import json
import time
from datetime import datetime
from influxdb import InfluxDBClient

# ==========================================================================================================
# Pack data into JSON packet
# ==========================================================================================================
def pack_JSON():

    json_body = []
    json_dict = {}

    # copy all node data into a JSON list
    json_dict["measurement"] = "node_data"
    json_dict["tags"] = node_tags.copy()
    json_dict["fields"] = measurements.copy()
    json_body.append(json_dict)

    # print data on screen for debugging
    print("==================================")
    print(datetime.now().strftime("%Y/%m/%d %H:%M:%S"))
    print (json.dumps(json_body, indent = 4, sort_keys=True))

    return json_body

# ==========================================================================================================
# Upload data to database
# ==========================================================================================================
def upload():
    
    # Influxdb credentials
    server = 'data.elemental-platform.com'
    influx_port = 8086
    user = 'berg'
    passwd = 'Validation132'
    db = 'berg'

    # start influx session and upload
    try:
        client = InfluxDBClient(server, influx_port, user, passwd, db)
        result = client.write_points(pack_JSON())
        client.close()
        print("Result: {0}".format(result))
    except:
        print('Error connecting/uploading to InfluxDB')

# ==========================================================================================================
# MAIN
# ==========================================================================================================
if __name__ == '__main__':

    # get the COM port from the cli argument
    com_port = sys.argv[1]

    # create gateway object
    gw = moteinogw.MoteinoGateway()

    # startup gateway object on specified COM port
    gw.startup(com_port)

    # Wait for the packet that tells us the gateway is alive
    packet = gw.wait_for_message()

    # Initialize the radio: 915 Mhz, Node ID 1, Network ID 100
    gw.init_radio(915, 1, 100)

    # Set the encryption key
    gw.set_encryption_key(b'1234123412341234')

    print("Initialized!")

    radio_format = '<BBBBHHH'
    radio_size   = struct.calcsize(radio_format)

    # Sit in a loop, displaying incoming radio packets and occasionally replying to one
    counter = 0
    response_id = 0
    while True:

        # wait for the next message
        packet = gw.wait_for_message()
     
        # check if the packet received is of RadioPacket type
        if isinstance(packet, moteinogw.RadioPacket):

            # if so, unpack the message into individual components
            version, setpoint, manual_index, hum, temp_f, battery, pwm = struct.unpack(radio_format, packet.data[:radio_size])

            # create a dictionary of node tags
            node_tags = {
                "node_id"       : packet.src_node,
                "fw_version"    : version,
            }

            # create a dictionary of measurements from the node
            measurements = {
                'temperature'   : temp_f/100,
                'humidity'      : hum,
                'setpoint'      : setpoint,
                'manual_index'  : manual_index,
                'battery'       : battery,
                'servo_PWM'     : pwm,
                'RSSI'          : packet.rssi
            }

            # pack the data into JSON and upload database
            upload()
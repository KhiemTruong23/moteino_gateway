# ==========================================================================================================
# Import necessary modules
# ==========================================================================================================

from asyncio import tasks
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
def pack_JSON(node_tags, measurements):

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
def upload(json_body):
    
    # Influxdb credentials
    server = 'data.elemental-platform.com'
    influx_port = 8086
    user = 'berg'
    passwd = 'Validation132'
    db = 'berg'

    # start influx session and upload
    try:
        client = InfluxDBClient(server, influx_port, user, passwd, db)
        result = client.write_points(json_body)
        client.close()
        print("Result: {0}".format(result))
    except:
        print('Error connecting/uploading to InfluxDB')


# ==========================================================================================================
# Unpacks a configuration packet from the node
# ==========================================================================================================
def unpack_config_packet():

    # BORC data packet format
    radio_format = '<BBBH'
    radio_size   = struct.calcsize(radio_format)

    # unpack the message into individual components
    _, version, device_type, firmware_version = struct.unpack(radio_format, packet.data[:5])

    # # second byte is device type
    # device_type = packet.data[1]
    
    # create a unique ID variable to save the unique ID in
    uid = ""

    # bytes 4-11 are UID (16-char)
    for b in packet.data[5:]:
        # format each byte into HEX
        uid += '{:X}'.format(b)

    # clear contents from dictionaries if previously populated
    node_tags = {}
    measurements = {}
    node_tags.clear()
    measurements.clear()

    # create a new dictionary of node tags
    node_tags = {
        "device_type"       : device_type,
        "uid"               : uid,
        "config_version"    : version,
        "fw_version"        : firmware_version
    }

    # create a new dictionary of measurements from the node
    measurements = {
        'RSSI'          : packet.rssi
    }

    # return back a neatly packed JSON packet to upload
    return (pack_JSON(node_tags, measurements))
# ==========================================================================================================



# ==========================================================================================================
# Unpacks a telemetry packet from a BORC
# ==========================================================================================================
def unpack_borc_telemetry_packet():

    # BORC telemetry packet format
    radio_format = '<BBBBBBHHHH'
    radio_size   = struct.calcsize(radio_format)

    # unpack the message into individual components
    _, version, setpoint, manual_index, error_byte, transaction_id, hum, temp_f, battery, pwm = struct.unpack(radio_format, packet.data[:radio_size])

    # send a response back to BORC
    send_response(packet.src_node)

    # clear contents from dictionaries if previously populated
    node_tags = {}
    measurements = {}
    node_tags.clear()
    measurements.clear()

    # create a new dictionary of node tags
    node_tags = {
        "node_id"           : packet.src_node,
        "telemetry_version" : version,
        "transaction_id"    : transaction_id,
        "error_byte"        : error_byte
    }

    # create a new dictionary of measurements from the node
    measurements = {
        'temperature'    : temp_f/100,
        'humidity'       : hum/100,
        'setpoint'       : setpoint,
        'manual_index'   : manual_index,
        'battery'        : battery,
        'servo_PWM'      : pwm,
        'RSSI'           : packet.rssi
    }

    # return JSON packet
    return (pack_JSON(node_tags, measurements))
# ==========================================================================================================


# ==========================================================================================================
# Send a response back to Node
# ==========================================================================================================
def send_response(destination):

    # define the struct format we want to pack as a response
    radio_format = '<BBBBBH16s'

    # packet types:
    # CONFIG_PACKET       = 0,
    # TELEMETRY_PACKET    = 1,
    # RESPONSE_PACKET     = 2

    # tasks_bit_field:
    # Change setpoint        (1 << 0)
    # Update manual index    (1 << 1)
    # Reboot node            (1 << 2)
    # Update Node params     (1 << 3)
    
    packet_type = 2
    tasks_bit_field = 0
    setpoint = 72
    manual_index = 0
    network_id = 10
    node_id = 2
    encryption_key = bytes('1234123412341234', 'utf-8')

    packet_components = struct.pack(radio_format, packet_type, tasks_bit_field, setpoint, manual_index, network_id, node_id, encryption_key)

    # send response to gateway for transmission
    gw.send_radio_packet(destination, packet_components)

# ==========================================================================================================


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
    gw.init_radio(915, 1, 10)

    # Set the encryption key
    gw.set_encryption_key(b'1234123412341234')

    print("Initialized!")

    try:

        # Sit in a loop, displaying incoming radio packets
        while True:

            # wait for the next message
            packet = gw.wait_for_message()
        
            # check if the packet received is of RadioPacket type
            if isinstance(packet, moteinogw.RadioPacket):
                
                # If it is a config packet
                if (packet.data[0] == 0):
                    print ("Config packet received")
                    
                    # send a response back
                    send_response(packet.src_node)
                    
                    # unpack packet
                    json_body = unpack_config_packet()

                # If it is a telemetry packet
                elif (packet.data[0] == 1):
                    print ("Telemetry packet received")

                    # send a response back to BORC
                    send_response(packet.src_node)

                    # unpack packet
                    json_body = unpack_borc_telemetry_packet()

                # pack the data into JSON and upload to database
                upload(json_body)
    
    except KeyboardInterrupt:

        # close out the sockets in use
        print ("\nShutting down...\n")
        gw.close()

# ==========================================================================================================
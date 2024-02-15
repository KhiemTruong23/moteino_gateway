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
import configparser
from flask import Flask, request, jsonify
from datetime import datetime
from influxdb import InfluxDBClient



# ==========================================================================================================
# Define multiple device types
# ==========================================================================================================
TYPE_BORC_DEVICE = 1
TYPE_STM_DEVICE = 2

# ==========================================================================================================
# Define multiple packet types
# ==========================================================================================================
TYPE_CONFIG_PACKET       = 0
TYPE_TELEMETRY_PACKET    = 1
TYPE_RESPONSE_PACKET     = 2
def read_db_config(filename='database.ini', section='influxdb'):
    # Create a parser
    parser = configparser.ConfigParser()
    # Read the config file
    parser.read(filename)

    # Get section, default to influxdb
    db_config = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db_config[param[0]] = param[1]
    else:
        raise Exception(f'Section {section} not found in the {filename} file')

    return db_config

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
    db_config = read_db_config()
    # start influx session and upload
    try:
        client = InfluxDBClient(db_config['server'], db_config['influx_port'], db_config['user'], db_config['passwd'], db_config['db'])
        result = client.write_points(json_body)
        print("Result: {0}".format(result))
    except Exception as e:
        print(f"Error uploading to InfluxDB: {e}")
    finally:
        client.close()


# ==========================================================================================================
# Unpacks a configuration packet from the node
# ==========================================================================================================
def unpack_config_packet(device_type_mappings: dict):

    # BORC data packet format
    radio_format = '<BBBH'
    radio_size   = struct.calcsize(radio_format)

    # unpack the message into individual components
    _, version, device_type, firmware_version = struct.unpack(radio_format, packet.data[:5])
    
    # map the node to a device type for receiving telemetry later
    device_type_mappings[packet.src_node] = device_type

    # create a unique ID variable to save the unique ID in
    uid = ""

    # bytes 4-11 are UID (16-char)
    for b in packet.data[5:]:
        # format each byte into HEX
        uid += '{:X}'.format(b)

    # clear contents from dictionaries if previously populated
    node_tags = {}
    measurements = {}

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
    return (pack_JSON(node_tags, measurements)), device_type_mappings
# ==========================================================================================================

# ==========================================================================================================
# Determine type of telemetry packet for device that has not yet transmit config
# ==========================================================================================================
def force_detect_device_type():
    
    # update user of what is happening
    print("Force reading device type...")
    
    # check if it's BORC
    try:
        radio_format = '<BBBBBBHHHH'
        _ = struct.unpack(radio_format, packet.data[:struct.calcsize(radio_format)])
        return TYPE_BORC_DEVICE
    except: pass
    
    # check if it's STM
    try:
        radio_format = '<BBHHBB'
        _ = struct.unpack(radio_format, packet.data[:struct.calcsize(radio_format)])
        return TYPE_STM_DEVICE
    except: pass
    
    # return a generic error if neither fits
    return -1

# ==========================================================================================================
# Determine device type and unpack accordingly
# ==========================================================================================================
def process_telemetry_packet(device_type_mappings):

    # determine device type
    try:
        device_type = device_type_mappings[packet.src_node]
    except KeyError:
        print(f"No config seen yet from node {packet.src_node}, please restart node to determine device type.")
        device_type = force_detect_device_type()

    # handle BORC packet
    if device_type == TYPE_BORC_DEVICE:
        return unpack_borc_telemetry_packet()

    # handle STM packet
    elif device_type == TYPE_STM_DEVICE:
        return unpack_stm_telemetry_packet()
    
    else:
        print(f"Unrecognized packet type from node {packet.src_node}.")


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
# Unpacks a telemetry packet from a STM
# ==========================================================================================================
def unpack_stm_telemetry_packet():

    # STM telemetry packet format
    radio_format = '<BBHHBB'
    radio_size   = struct.calcsize(radio_format)

    # unpack the message into individual components
    _, version, before_temp, after_temp, error_byte, transaction_id = struct.unpack(radio_format, packet.data[:radio_size])

    # send a response back to STM
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
        'temp_before'    : before_temp/100,
        'temp_after'     : after_temp/100,
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

    # tasks_bit_field:
    # Change setpoint        (1 << 0)
    # Update manual index    (1 << 1)
    # Reboot node            (1 << 2)
    # Update Node params     (1 << 3)
    
    packet_type = TYPE_RESPONSE_PACKET
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
# Send packet API
# ==========================================================================================================
app = Flask(__name__)
@app.route('/thermal/<node_id>', methods=['GET'])
def thermal_api_post(node_id):
    # Influxdb credentials
    db_config = read_db_config()

    # start influx session and upload
    try:
        client = InfluxDBClient(db_config['server'], db_config['influx_port'], db_config['user'], db_config['passwd'], db_config['db'])
        result = client.query("select * from node_data limit 1")
        #Result: ResultSet({'('node_data', None)': [{'time': '2022-02-07T21:40:13.561208Z', 'RSSI': -29, 'after_temp': None, 'battery': 4187, 'before_temp': None, 'config_version': None, 'device_type': None, 'error_byte': None, 'fw_version': '1', 'humidity': 22.85, 'is_working': None, 'manual_index': 3, 'node_id': '2', 'servo_PWM': 3562, 'setpoint': 73, 'telemetry_version': None, 'temp_after': None, 'temp_before': None, 'temperature': 80.75, 'transaction_id': None, 'uid': None}]})
        client.close()
        print("Result: {0}".format(result))
    except:
        print('Error connecting/uploading to InfluxDB')



# ==========================================================================================================

# ==========================================================================================================
# MAIN
# ==========================================================================================================
if __name__ == '__main__':

    if len(sys.argv) != 2:
        print("Usage: python3 script.py <serial_port>")
        sys.exit(1)

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

    # a dictionary to link known devices to their respective device types
    device_type_mappings = {}

    try:

        # Sit in a loop, displaying incoming radio packets
        while True:

            # wait for the next message
            packet = gw.wait_for_message()
        
            # check if the packet received is of RadioPacket type
            if isinstance(packet, moteinogw.RadioPacket):
                
                # If it is a config packet
                if (packet.data[0] == TYPE_CONFIG_PACKET):
                    print ("Config packet received")
                    
                    # send a response back
                    send_response(packet.src_node)
                    
                    # unpack packet
                    json_body, device_type_mappings = unpack_config_packet(device_type_mappings)

                # If it is a telemetry packet
                elif (packet.data[0] == TYPE_TELEMETRY_PACKET):
                    print ("Telemetry packet received")

                    # send a response back to BORC
                    send_response(packet.src_node)

                    # process and unpack packet
                    json_body = process_telemetry_packet(device_type_mappings)
                    if not json_body:
                        print("Failed to unpack telemetry.")
                        continue

                # pack the data into JSON and upload to database
                upload(json_body)
    
    except KeyboardInterrupt:

        # close out the sockets in use
        print ("\nShutting down...\n")
        gw.close()

# ==========================================================================================================
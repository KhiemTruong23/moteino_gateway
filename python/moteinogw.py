import serial
import threading
import socket
import collections
import select

# ==========================================================================================================
# 8-bit CRC lookup table for polynomial 0x31
# ==========================================================================================================
crc8_table = [
    0x00, 0x31, 0x62, 0x53, 0xC4, 0xF5, 0xA6, 0x97, 0xB9, 0x88, 0xDB, 0xEA, 0x7D, 0x4C, 0x1F, 0x2E,
    0x43, 0x72, 0x21, 0x10, 0x87, 0xB6, 0xE5, 0xD4, 0xFA, 0xCB, 0x98, 0xA9, 0x3E, 0x0F, 0x5C, 0x6D,
    0x86, 0xB7, 0xE4, 0xD5, 0x42, 0x73, 0x20, 0x11, 0x3F, 0x0E, 0x5D, 0x6C, 0xFB, 0xCA, 0x99, 0xA8,
    0xC5, 0xF4, 0xA7, 0x96, 0x01, 0x30, 0x63, 0x52, 0x7C, 0x4D, 0x1E, 0x2F, 0xB8, 0x89, 0xDA, 0xEB,
    0x3D, 0x0C, 0x5F, 0x6E, 0xF9, 0xC8, 0x9B, 0xAA, 0x84, 0xB5, 0xE6, 0xD7, 0x40, 0x71, 0x22, 0x13,
    0x7E, 0x4F, 0x1C, 0x2D, 0xBA, 0x8B, 0xD8, 0xE9, 0xC7, 0xF6, 0xA5, 0x94, 0x03, 0x32, 0x61, 0x50,
    0xBB, 0x8A, 0xD9, 0xE8, 0x7F, 0x4E, 0x1D, 0x2C, 0x02, 0x33, 0x60, 0x51, 0xC6, 0xF7, 0xA4, 0x95,
    0xF8, 0xC9, 0x9A, 0xAB, 0x3C, 0x0D, 0x5E, 0x6F, 0x41, 0x70, 0x23, 0x12, 0x85, 0xB4, 0xE7, 0xD6,
    0x7A, 0x4B, 0x18, 0x29, 0xBE, 0x8F, 0xDC, 0xED, 0xC3, 0xF2, 0xA1, 0x90, 0x07, 0x36, 0x65, 0x54,
    0x39, 0x08, 0x5B, 0x6A, 0xFD, 0xCC, 0x9F, 0xAE, 0x80, 0xB1, 0xE2, 0xD3, 0x44, 0x75, 0x26, 0x17,
    0xFC, 0xCD, 0x9E, 0xAF, 0x38, 0x09, 0x5A, 0x6B, 0x45, 0x74, 0x27, 0x16, 0x81, 0xB0, 0xE3, 0xD2,
    0xBF, 0x8E, 0xDD, 0xEC, 0x7B, 0x4A, 0x19, 0x28, 0x06, 0x37, 0x64, 0x55, 0xC2, 0xF3, 0xA0, 0x91,
    0x47, 0x76, 0x25, 0x14, 0x83, 0xB2, 0xE1, 0xD0, 0xFE, 0xCF, 0x9C, 0xAD, 0x3A, 0x0B, 0x58, 0x69,
    0x04, 0x35, 0x66, 0x57, 0xC0, 0xF1, 0xA2, 0x93, 0xBD, 0x8C, 0xDF, 0xEE, 0x79, 0x48, 0x1B, 0x2A,
    0xC1, 0xF0, 0xA3, 0x92, 0x05, 0x34, 0x67, 0x56, 0x78, 0x49, 0x1A, 0x2B, 0xBC, 0x8D, 0xDE, 0xEF,
    0x82, 0xB3, 0xE0, 0xD1, 0x46, 0x77, 0x24, 0x15, 0x3B, 0x0A, 0x59, 0x68, 0xFF, 0xCE, 0x9D, 0xAC
]
# ==========================================================================================================


# ==========================================================================================================
# fast_crc8() - Computes the 8-bit CRC of a byte string
# ==========================================================================================================
def fast_crc8(data):
    crc = 0xFF
    for value in data:
        crc = crc8_table[crc ^ value]
    return crc
# ==========================================================================================================



# ==========================================================================================================
# RadioPacket() - Decodes an incoming radio packet
# ==========================================================================================================
class RadioPacket:

    def __init__(self, raw_packet):
        self.src_node = int.from_bytes(raw_packet[3:5], 'little')
        self.dst_node = int.from_bytes(raw_packet[5:7], 'little')
        datalen = int.from_bytes(raw_packet[7:8], 'little')
        self.data = raw_packet[8:8+datalen]
# ==========================================================================================================


# ==========================================================================================================
# MoteinoGateway - Manages communications with the Moteino gateway driving an RFM69 radio
# ==========================================================================================================
class MoteinoGateway(threading.Thread):

    comport    = None  # A PySerial object
    queue      = None  # A queue of incoming packets
    mutex      = None  # Mutex that protects the queue
    event      = None  # An event that signals receipt of an ack from the gateway
    pipe_in    = None  # The read-side of a socket used for notifications
    pipe_out   = None  # The write-side of a socket used for notifications
    local_port = 32122

    SP_PRINT       =   0x01      # From Gateway
    SP_READY       =   0x02      # From Gateway
    SP_ECHO        = b'\x03'     # To Gateway
    SP_ALIVE       =   0x04      # From Gateway
    SP_INIT_RADIO  = b'\x05'     # To Gateway
    SP_ENCRYPT_KEY = b'\x06'     # To Gateway
    SP_FROM_RADIO  =   0x07      # From Gateway
    SP_TO_RADIO    = b'\x08'     # To Gateway
    SP_NAK         =   0x09      # From Gateway

    # ------------------------------------------------------------------------------
    # Constructor - Just calls the threading base-class constructor and creates
    #               objects we'll need to communicate between threads
    # ------------------------------------------------------------------------------
    def __init__(self):

        # Call the base class constructor
        threading.Thread.__init__(self)

        # Create an empty queue for our incoming messages
        self.queue = collections.deque()

        # Create a mutex to protect the queue
        self.mutex = threading.Lock()

        # Create an event to notify other thread of message receipts
        self.event = threading.Event()

    # ------------------------------------------------------------------------------


    # ------------------------------------------------------------------------------
    # startup() - Begins the process of monitoring the gateway
    # ------------------------------------------------------------------------------
    def startup(self, port):

        # Create a socket to start listening on
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', self.local_port))
        sock.listen(1)

        # Open the connection to the serial port
        self.comport = serial.Serial(port, 115200)

        # Launch the thread that does a blocking read on the serial port
        self.launch_serial_reader_thread()

        # Accept a connection from the other thread
        self.pipe_in, _ = sock.accept()
    # ------------------------------------------------------------------------------


    # ------------------------------------------------------------------------------
    # wait_for_message() - Blocks, waiting for an incoming packet.  Returns
    #                      the packet as bytes
    # ------------------------------------------------------------------------------
    def wait_for_message(self, timeout_seconds = None):

        # If the user wants a timeout, wait for data to arrive
        if timeout_seconds:
            ready = select.select([self.pipe_in], [], [], timeout_seconds)
            if not ready[0]: return None

        # Blocking read, waiting for a notification that a message is available
        self.pipe_in.recv(1)

        # And return the packet at the top of the FIFO
        self.mutex.acquire()
        packet = self.queue.popleft()
        self.mutex.release()
        return packet
    # ------------------------------------------------------------------------------


    # ------------------------------------------------------------------------------
    # echo() - Ask the gateway to echo a message back to us
    # ------------------------------------------------------------------------------
    def echo(self, packet_data):
        self.send_packet(self.SP_ECHO + packet_data)
    # ------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------
    # init_radio() - Initialize the radio.
    #
    # Passed: frequency must be 433, 868, or 915
    #         node_id = Between 0 and 1023
    #         network_id = Between 0 and 255
    # ------------------------------------------------------------------------------
    def init_radio(self, frequency, node_id, network_id):
        packet = self.SP_INIT_RADIO
        packet = packet + frequency.to_bytes(2, 'little')
        packet = packet + node_id.to_bytes(2, 'little')
        packet = packet + network_id.to_bytes(1, 'little')
        self.send_packet(packet)
    # ------------------------------------------------------------------------------


    # ------------------------------------------------------------------------------
    # set_encryption_key() - Tells the radio what the network encryption key is
    #
    # The key must be exactly 16 bytes long
    # ------------------------------------------------------------------------------
    def set_encryption_key(self, key):
        self.send_packet(self.SP_ENCRYPT_KEY + key)
    # ------------------------------------------------------------------------------


    # ------------------------------------------------------------------------------
    # send_radio_packet() - Sends a data-packet to a node via the radio
    # ------------------------------------------------------------------------------
    def send_radio_packet(self, node_id, data):
        packet = self.SP_TO_RADIO
        packet = packet + node_id.to_bytes(2, 'little')
        packet = packet + len(data).to_bytes(1, 'little')
        packet = packet + data
        self.send_packet(packet)
    # ------------------------------------------------------------------------------


    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # From here on down are methods that are private to this class
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>
    # <><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><><>


    # ------------------------------------------------------------------------------
    # send_packet() - Sends a generic packet expressed as bytes and waits for
    #                 the gateway to send the acknowledgement
    # ------------------------------------------------------------------------------
    def send_packet(self, packet_data):
        crc = fast_crc8(packet_data)
        packet_length = len(packet_data) + 2
        packet_header = packet_length.to_bytes(1, 'little')
        packet_header = packet_header + crc.to_bytes(1, 'little')

        # Keep track of the most recent packet that we've sent out
        self.last_packet_sent = packet_header + packet_data

        self.event.clear()
        self.comport.write(self.last_packet_sent)
        if not self.event.wait(5):
            print("Timed out waiting for serial response!")
    # ------------------------------------------------------------------------------



    # ---------------------------------------------------------------------------
    # launch_serial_reader_thread() - Starts the thread that does a blocking
    #                                 read on the serial port
    # ---------------------------------------------------------------------------
    def launch_serial_reader_thread(self):

        # Ensure that this thread exits when the main program does
        self.daemon = True

        # Create the socket that we will use to send notifications
        self.pipe_out = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Make the socket connection to the other thread
        self.pipe_out.connect(('localhost', self.local_port))

        # This launches the "self.run()" routine in it's own thread
        self.start()
    # ---------------------------------------------------------------------------


    # ---------------------------------------------------------------------------
    # run() - A blocking thread that permanently waits for incoming messages
    # ---------------------------------------------------------------------------
    def run(self):

        # Wait for the receive line to go quiet
        self.comport.timeout = .1
        while not self.comport.read() == b'':
            pass
        self.comport.timeout = None

        # We're going to wait for incoming messages forever
        while True:

            # Read in a packet
            self.comport.timeout = None
            packet = self.comport.read(1)
            count = int.from_bytes(packet, 'little')
            self.comport.timeout = .1
            packet = packet + self.comport.read(count - 1)

            # If the packet is the wrong length, throw it away
            if len(packet) != count:
                print("Throwing away malformed packet")
                continue

            # Packet-type is the 3rd byte in the packet
            packet_type = packet[2]

            # If this is a "print this" packet, make it so
            if packet_type == self.SP_PRINT:
                print("Gateway says:", packet[3:])
                continue

            # If this is a "Ready to receive" notification, tell the other thread
            if packet_type == self.SP_READY:
                self.event.set()
                continue

            if packet_type == self.SP_NAK:
                print("Got NAK!")
                self.event.set()
                continue

            # If this is a radio packet, decode it
            if packet_type == self.SP_FROM_RADIO:
                packet = RadioPacket(packet)

            # Place this packet into our queue
            self.mutex.acquire()
            self.queue.append(packet)
            self.mutex.release()

            # Notify the other thread that there is a packet in the queue
            self.pipe_out.send(b'\x01')
    # ---------------------------------------------------------------------------


# ==========================================================================================================



import serial
import threading
import socket
import collections
import select
import struct

# ==========================================================================================================
# RadioPacket - Decodes an incoming radio packet
# ==========================================================================================================
class RadioPacket:

    # 4-byte header, 2-byte src_mode, 2-byte dst_node, data
    def __init__(self, raw_packet):
        format = '<4sHH'
        fixed_size = struct.calcsize(format)
        _, self.src_node, self.dst_node = struct.unpack(format, raw_packet[:fixed_size])
        self.data = raw_packet[fixed_size:]
# ==========================================================================================================

# ==========================================================================================================
# EchoPacket - Contains the payload of an SP_ECHO packet
# ==========================================================================================================
class EchoPacket:
    def __init__(self, raw_packet):
        self.payload = raw_packet[4:]
# ==========================================================================================================

# ==========================================================================================================
# BadPacket - Indicates a packet that was thrown away due to bad CRC
# ==========================================================================================================
class BadPacket:
    def __init__(self, raw_packet):
        self.raw_packet = raw_packet
# ==========================================================================================================


# ==========================================================================================================
# 8-bit CRC lookup table for polynomial 0x31
# ==========================================================================================================
crc16_table = [
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7,
    0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
    0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6,
    0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,
    0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485,
    0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,
    0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,
    0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,
    0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823,
    0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,
    0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12,
    0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A,
    0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41,
    0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
    0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70,
    0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
    0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F,
    0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,
    0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E,
    0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,
    0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,
    0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
    0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C,
    0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,
    0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB,
    0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,
    0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A,
    0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
    0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9,
    0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,
    0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8,
    0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0
]
# ==========================================================================================================

# ==========================================================================================================
# fast_crc16() - Computes the 16-bit CRC of a byte string
# ==========================================================================================================
def fast_crc16(data):
    crc = 0xFFFF
    for value in data:
        pos = (crc >> 8) ^ value
        crc = ((crc << 8) ^ crc16_table[pos]) & 0xFFFF
    return crc
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
    packet_ack = False # True when the most recently sent packet gets acknowledged
    local_port = 32122

    SP_PRINT       = 0x01      # From Gateway
    SP_READY       = 0x02      # From Gateway
    SP_ECHO        = 0x03      # To Gateway
    SP_ALIVE       = 0x04      # From Gateway
    SP_INIT_RADIO  = 0x05      # To Gateway
    SP_ENCRYPT_KEY = 0x06      # To Gateway
    SP_FROM_RADIO  = 0x07      # From Gateway
    SP_TO_RADIO    = 0x08      # To Gateway
    SP_NAK         = 0x09      # From Gateway

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
        self.comport = serial.Serial(port, 250000)

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
    def echo(self, payload):
        return self.send_packet(self.SP_ECHO, payload)
    # ------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------
    # init_radio() - Initialize the radio.
    #
    # Passed: frequency must be 433, 868, or 915
    #         node_id = Between 0 and 1023
    #         network_id = Between 0 and 255
    # ------------------------------------------------------------------------------
    def init_radio(self, frequency, node_id, network_id):
        packet = frequency.to_bytes(2, 'little')
        packet = packet + node_id.to_bytes(2, 'little')
        packet = packet + network_id.to_bytes(1, 'little')
        return self.send_packet(self.SP_INIT_RADIO, packet)
    # ------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------
    # set_encryption_key() - Tells the radio what the network encryption key is
    #
    # The key must be exactly 16 bytes long
    # ------------------------------------------------------------------------------
    def set_encryption_key(self, key):
        return self.send_packet(self.SP_ENCRYPT_KEY, key)
    # ------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------
    # send_radio_packet() - Sends a data-packet to a node via the radio
    #
    # Returns: True on success, otherwise false
    # ------------------------------------------------------------------------------
    def send_radio_packet(self, node_id, payload):
        packet = node_id.to_bytes(2, 'little') + payload
        return self.send_packet(self.SP_TO_RADIO, packet)
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
    def send_packet(self, packet_type, payload):

        # Prepend the packet type to the packet data
        packet = packet_type.to_bytes(1, 'little') + payload

        # Compute the CRC of the packet data (including the packet type)
        crc = fast_crc16(packet).to_bytes(2, 'little')

        # Prepend the CRC to the packet
        packet = crc + packet

        # The total length of the packet includes the length byte
        packet_length = len(packet) + 1

        # Make multiple attempts to transmit the prologue + packet
        for attempt in range(0, 10):
            if not self.send_prologue(packet_length):
                break
            if self.send_and_wait(packet, 5):
                return True

        print("Gave up sending packet!")
        return False
    # ------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------
    # send_prologue() - Constructs a 2-byte prologue from a length, and makes
    #                   multiple attempts to send it to the gateway
    # ------------------------------------------------------------------------------
    def send_prologue(self, length):

        # Create the two-byte packet prologue
        prologue = bytes([length, ~length & 0xFF])

        # Make multiple attempts to send the prologue
        for attempt in range(0,10):
            if self.send_and_wait(prologue, 1):
                return True

        # If we get here, we couldn't send it
        return False
    # ------------------------------------------------------------------------------

    # ------------------------------------------------------------------------------
    # send_and_wait() - Sends data and waits for an ACK or NAK
    #
    # Returns True if an ACK was received, else false
    # ------------------------------------------------------------------------------
    def send_and_wait(self, data, timeout):
        self.event.clear()
        self.packet_ack = False
        self.comport.write(data)
        return self.event.wait(timeout) and self.packet_ack
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

            # Packet-type is the 4th byte in the packet
            packet_type = packet[3]

            # If this is a "print this" packet, make it so
            if packet_type == self.SP_PRINT:
                print("Gateway says:", packet[4:])
                continue

            # If this is a "Ready to receive" notification, tell the other thread
            if packet_type == self.SP_READY:
                self.packet_ack = True
                self.event.set()
                continue

            # If this is a NAK, tell the other thread
            if packet_type == self.SP_NAK:
                self.packet_ack = False
                self.event.set()
                continue

            # Extract the CRC from the packet
            packet_crc = int.from_bytes(packet[1:3], 'little')

            # Compute a new CRC for the packet
            new_crc = fast_crc16(packet[3:])

            # --------------------------------------------------------
            # Convert the packet to specialized packet class
            # --------------------------------------------------------
            if packet_crc != new_crc:
                packet = BadPacket(packet)
                print(">>> CRC MISMATCH DETECTED <<<")

            elif packet_type == self.SP_FROM_RADIO:
                packet = RadioPacket(packet)

            elif packet_type == self.SP_ECHO:
                packet = EchoPacket(packet)
            # --------------------------------------------------------

            # Place this packet into our queue
            self.mutex.acquire()
            self.queue.append(packet)
            self.mutex.release()

            # Notify the other thread that there is a packet in the queue
            self.pipe_out.send(b'\x01')
    # ---------------------------------------------------------------------------


# ==========================================================================================================



import serial
import threading
import socket
import collections
import select

class RadioPacket:

    def __init__(self, raw_packet):
        self.src_node = int.from_bytes(raw_packet[2:4], 'little')
        self.dst_node = int.from_bytes(raw_packet[4:6], 'little')
        datalen = int.from_bytes(raw_packet[6:7], 'little')
        self.data = raw_packet[7:7+datalen]

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
        packet_length = len(packet_data) + 1
        self.event.clear()
        self.comport.write(packet_length.to_bytes(1, 'little') + packet_data)
        self.event.wait(5)
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

            # If this is a "print this" packet, make it so
            if packet[1] == self.SP_PRINT:
                print("Gateway says:", packet[2:])
                continue

            # If this is a "Ready to receive" notification, tell the other thread
            if packet[1] == self.SP_READY:
                self.event.set()
                continue

            # Place this packet into our queue
            self.mutex.acquire()
            self.queue.append(packet)
            self.mutex.release()

            # Notify the other thread that there is a packet in the queue
            self.pipe_out.send(b'\x01')

    # ---------------------------------------------------------------------------


# ==========================================================================================================





if __name__ == '__main__':
    gw = MoteinoGateway()
    gw.startup('COM10')

    # Wait for the packet that tells us the gateway is alive
    packet = gw.wait_for_message()

    # Initialize the radio: 915 Mhz, Node ID 1, Network ID 100
    gw.init_radio(915, 1, 100)

    # Set the encryption key
    gw.set_encryption_key(b'1234123412341234')

    print("Initialized!")
    count = 0
    while True:
        packet = gw.wait_for_message()
        if packet[1] == gw.SP_FROM_RADIO:
            message = RadioPacket(packet)
            print("From :", message.src_node)
            print("To   :", message.dst_node)
            print("Data :", message.data)
            print()

    print("Exiting program")
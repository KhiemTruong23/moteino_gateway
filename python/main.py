import serial
import threading
import time
import socket
import collections
import select

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
        SP_ECHO = b'\x03'
        self.send_packet(SP_ECHO + packet_data)
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
        self.comport.write(packet_length.to_bytes(1, 'big') + packet_data)
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

        SP_PRINT = 1
        SP_READY = 2

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
            count = int.from_bytes(packet, 'big')
            self.comport.timeout = .1
            packet = packet + self.comport.read(count - 1)

            # If the packet is the wrong length, throw it away
            if len(packet) != count:
                print("Throwing away malformed packet")
                continue

            # If this is a "print this" packet, make it so
            if packet[1] == SP_PRINT:
                print("Gateway says:", packet[2:])
                continue

            # If this is a "Ready to receive" notification, tell the other thread
            if packet[1] == SP_READY:
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

    count = 0
    while True:
        packet = gw.wait_for_message(.1)
        if packet == None:
            count = count + 1
            gw.echo(b'ECHO ' + count.to_bytes(4, 'big'))
        else:
            print("Handling packet: ", packet)

    print("Exiting program")
import serial
import threading
import time
import socket
import collections
import select

# ==========================================================================================================
# wifi_i2c - Manages communications with ESP32 wifi-i2c server
# ==========================================================================================================
class MoteinoGateway:

    comport  = None
    listener = None
    sock     = None

    # ------------------------------------------------------------------------------
    # start() - Begins the process of monitoring the gateway
    # ------------------------------------------------------------------------------
    def start(self, port):
        local_port = 32122

        # Create a socket to start listening on
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('localhost', local_port))
        sock.listen(1)
        self.comport = serial.Serial(port, 115200)
        self.listener = Listener(self.comport, local_port)
        self.listener.begin()

        # Accept a connection from the other thread
        self.sock, _ = sock.accept()
    # ------------------------------------------------------------------------------


    # ------------------------------------------------------------------------------
    # wait_for_message() - Blocks, waiting for an incoming packet.  Returns
    #                      the packet as bytes
    # ------------------------------------------------------------------------------
    def wait_for_message(self, timeout_seconds = None):

        # If the user wants a timeout, wait for data to arrive
        if timeout_seconds:
            ready = select.select([self.sock], [], [], timeout_seconds)
            if not ready[0]: return None

        # Blocking read, waiting for a notification that a message is available
        self.sock.recv(1)

        # And return the packet at the top of the FIFO
        return self.listener.read_fifo()
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
        self.listener.event.clear()
        self.comport.write(packet_length.to_bytes(1, 'big') + packet_data)
        self.listener.event.wait(5)
    # ------------------------------------------------------------------------------





# ==========================================================================================================
# listener - A helper thread that listens for reply packets
# ==========================================================================================================
class Listener(threading.Thread):

    comport    = None
    local_port = None
    sock       = None
    mutex      = None
    event      = None

    # ------------------------------------------------------------------------------
    # Constructor - Records the comport object we want to listen on
    # ------------------------------------------------------------------------------
    def __init__(self, comport, local_port):

        # Call the threading base class constructor
        threading.Thread.__init__(self)

        # Save the comport we want to listen to
        self.comport = comport

        # Save the local port number that we will use to send notifications
        self.local_port = local_port

        # Create an empty queue for our incoming messages
        self.queue = collections.deque()

        # Create a mutex to protect the queue
        self.mutex = threading.Lock()

        # Create an event to notify other thread of message receipts
        self.event = threading.Event()
    # ----------------------------------------------------------------------------



    # ---------------------------------------------------------------------------
    # begin() - Starts a thread and begins listening for incoming messages
    # ---------------------------------------------------------------------------
    def begin(self):

        # Ensure that this thread exits when the main program does
        self.daemon = True

        # Create an event that other threads can wait on
        self.event = threading.Event()

        # Create the socket that we will use to send notifications
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Make the socket connection to the other thread
        self.sock.connect(('localhost', self.local_port))

        # Start the thread
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
            self.sock.send(b'\x01')

    # ---------------------------------------------------------------------------

    # ---------------------------------------------------------------------------
    # read_fifo() - Returns the packet at the front of the queue
    # ---------------------------------------------------------------------------
    def read_fifo(self):
        self.mutex.acquire()
        packet = self.queue.popleft()
        self.mutex.release()
        return packet

    # ---------------------------------------------------------------------------



# ==========================================================================================================





if __name__ == '__main__':
    gw = MoteinoGateway()
    gw.start('COM10')

    count = 0
    while True:
        packet = gw.wait_for_message(5)
        if packet == None:
            count = count + 1
            gw.echo(b'ECHO ' + count.to_bytes(4, 'big'))
        else:
            print("Handling packet: ", packet)

    print("Exiting program")
import serial
import threading
import time


# ==========================================================================================================
# wifi_i2c - Manages communications with ESP32 wifi-i2c server
# ==========================================================================================================
class MoteinoGateway:
    comport = None

    def start(self, port):
        self.comport = serial.Serial(port, 115200)
        self.listener = Listener(self.comport)
        self.listener.begin()


# ==========================================================================================================
# listener - A helper thread that listens for reply packets
# ==========================================================================================================
class Listener(threading.Thread):

    comport = None

    # ------------------------------------------------------------------------------
    # Constructor - Records the comport object we want to listen on
    # ------------------------------------------------------------------------------
    def __init__(self, comport):

        # Call the threading base class constructor
        threading.Thread.__init__(self)

        # Save the comport we want to listen to
        self.comport = comport
    # ----------------------------------------------------------------------------



    # ---------------------------------------------------------------------------
    # begin() - Starts a thread and begins listening for incoming messages
    # ---------------------------------------------------------------------------
    def begin(self):

        # Ensure that this thread exits when the main program does
        self.daemon = True

        # Create an event that other threads can wait on
        self.event = threading.Event()

        # Start the thread
        self.start()
    # ---------------------------------------------------------------------------





    # ---------------------------------------------------------------------------
    # run() - A blocking thread that permanently waits for incoming messages
    # ---------------------------------------------------------------------------
    def run(self):

        packet = b''

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
                continue

            # If this is a "print this" packet, make it so
            if packet[1] == 1:
                print(packet[2:])
                continue

    # ---------------------------------------------------------------------------

# ==========================================================================================================







def testit():
    ser = serial.Serial('COM10', 115200)
    ser.set_buffer_size(rx_size=10000, tx_size=10000)

    time.sleep(2)
    print('starting')
    ser.write(b'testing\n')


    s= b''
    count = 0
    while True:
        c = ser.read()
        s = s + c
        if c == b'\n':
            print(s)
            count = count + 1
            if count == 35:
                quit(0)

            s = b''
            tag = 'Hi there %i\n' % (count)
            time.sleep(.001)
            ser.write(bytes(tag, 'utf-8'))

if __name__ == '__main__':
    print("Here!")
    gw = MoteinoGateway()
    gw.start('COM10')
    time.sleep(10000)
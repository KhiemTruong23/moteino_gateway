import moteinogw
from timeit import default_timer as timer

# ==========================================================================================================
# echo_test() - Transmits / receives a large number of packets across the serial interface
#
# Measures the round-trip time, then examines each queued up packet to ensure that it matches
# the original packet that was sent
# ==========================================================================================================
def echo_test():
    count = 10000
    print("Start test")
    start = timer()
    for n in range(0, count):
        packet = n.to_bytes(4, 'big') + b'abcdefghijklmnopqrstuvwxyz'
        gw.echo(packet)
    end = timer()
    print("Round trip for", count, "packets took", end - start, "seconds")

    print("Checking data integrity")
    for n in range(0,count):
        packet = gw.wait_for_message(5)
        expected = n.to_bytes(4, 'big') + b'abcdefghijklmnopqrstuvwxyz'
        if not packet.payload == expected:
            print("Fault on packet", n)
            quit()
    print("Data integrity confirmed")
    quit()
# ==========================================================================================================


if __name__ == '__main__':
    gw = moteinogw.MoteinoGateway()
    gw.startup('COM11')

    # Wait for the packet that tells us the gateway is alive
    packet = gw.wait_for_message()

    # Serial-interface throughput test
    echo_test()

    # Initialize the radio: 915 Mhz, Node ID 1, Network ID 100
    gw.init_radio(915, 1, 100)

    # Set the encryption key
    gw.set_encryption_key(b'1234123412341234')

    print("Initialized!")
    counter = 0
    response_id = 0

    # Change this to "while True:" to bombard the serial interface with messages
    while False:
        counter = counter + 1;
        message = "Hello %i" % (counter)
        if not gw.echo(bytes(message, 'utf-8')):
            print("ECHO FAILED")
            quit()

    # Sit in a loop, displaying incoming radio packets and occasionally replying to one
    while True:
        packet = gw.wait_for_message()
        if isinstance(packet, moteinogw.RadioPacket):
            print("From :", packet.src_node, "To :", packet.dst_node, "Data :", packet.data)

            counter = counter + 1
            if counter % 1 == 0:
                response_id = response_id + 1
                response = 'I see you %i' % (response_id)
                gw.send_radio_packet(packet.src_node, bytes(response, 'utf-8'))
            continue

        if packet[2] == gw.SP_ECHO:
            print("Echo", packet)
            continue




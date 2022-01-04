import moteinogw

if __name__ == '__main__':
    gw = moteinogw.MoteinoGateway()
    gw.startup('COM10')

    # Wait for the packet that tells us the gateway is alive
    packet = gw.wait_for_message()

    # Initialize the radio: 915 Mhz, Node ID 1, Network ID 100
    gw.init_radio(915, 1, 100)

    # Set the encryption key
    gw.set_encryption_key(b'1234123412341234')

    print("Initialized!")

    # Sit in a loop, displaying incoming radio packets
    while True:
        packet = gw.wait_for_message()
        if isinstance(packet, moteinogw.RadioPacket):
            print("From :", packet.src_node)
            print("To   :", packet.dst_node)
            print("Data :", packet.data)
            print()

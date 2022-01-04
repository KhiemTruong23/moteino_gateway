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
    count = 0
    while True:
        packet = gw.wait_for_message()
        if packet[1] == gw.SP_FROM_RADIO:
            message = moteinogw.RadioPacket(packet)
            if isinstance(message, moteinogw.RadioPacket):
                print(type(message))
                print("From :", message.src_node)
                print("To   :", message.dst_node)
                print("Data :", message.data)
                print()

    print("Exiting program")
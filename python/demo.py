import moteinogw

if __name__ == '__main__':
    gw = moteinogw.MoteinoGateway()
    gw.startup('COM10')

    # Wait for the packet that tells us the gateway is alive
    packet = gw.wait_for_message()
    print("Initial packet was", packet)

    # Initialize the radio: 915 Mhz, Node ID 1, Network ID 100
    gw.init_radio(915, 1, 100)

    # Set the encryption key
    gw.set_encryption_key(b'1234123412341234')

    print("Initialized!")
    counter = 0
    response_id = 0

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

#include <stdint.h>
#include "packet_uart.h"
#include "forked_RFM69.h"


uint8_t fast_crc8(const uint8_t* in, uint8_t count);
bool is_radio_initialized = false;
CPacketUART UART;
ForkedRFM69 Radio;

//=========================================================================================================
// maps a structure onto a buffer named "raw"
//=========================================================================================================
#define map_struct(t,m) t& m=*(t*)raw
//=========================================================================================================


//=========================================================================================================
// Formats of messages to and from the gateway
//=========================================================================================================
struct echo_t
{
    uint8_t   packet_len;
    uint8_t   uart_crc;
    uint8_t   packet_type;
    uint8_t   data[0];
};


struct init_radio_t
{
    uint8_t   packet_len;
    uint8_t   uart_crc;
    uint8_t   packet_type;
    uint16_t  frequency;
    uint16_t  node_id;
    uint8_t   network_id;
};

struct encrypt_key_t
{
    uint8_t   packet_len;
    uint8_t   uart_crc;
    uint8_t   packet_type;
    uint8_t   encryption_key[16];
};

struct from_radio_t
{
    uint8_t  packet_len;
    uint8_t  uart_crc;
    uint8_t  packet_type;
    uint16_t src_node;
    uint16_t dst_node;    
    uint8_t  data_len;
    uint8_t  data[0];
};

struct to_radio_t
{
    uint8_t  packet_len;
    uint8_t  uart_crc;
    uint8_t  packet_type;
    uint16_t dst_node;
    uint8_t  data_len;
    uint8_t  data[0];
};
//=========================================================================================================


//=========================================================================================================
// setup() - Runs once at boot
//=========================================================================================================
void setup()
{
    UART.begin(250000);
}
//=========================================================================================================

//=========================================================================================================
// handle_echo() - Echos back data as an SP_PRINT command
//=========================================================================================================
void handle_echo(const unsigned char* raw)
{
    // Map our structure on top of the raw packet
    map_struct(echo_t, msg);

    // Replace the SP_ECHO with an SP_PRINT
    msg.packet_type = SP_PRINT;

    // And send the packet to the client
    UART.transmit_raw(raw);
}
//=========================================================================================================

//=========================================================================================================
// handle_init_radio() - Initialize the radio 
//=========================================================================================================
void handle_init_radio(const unsigned char* raw)
{
    unsigned char freq_code;

    // Map our structure on top of the raw packet
    map_struct(init_radio_t, msg);

    // Decode the frequency into one of the frequency constants
    switch(msg.frequency)
    {
        case 915:
            freq_code = RF69_915MHZ;
            break;
        case 868:
            freq_code = RF69_868MHZ;
            break;
        case 433:
            freq_code = RF69_433MHZ;
            break;
        default:
            UART.printf("Bad frequency: %i", msg.frequency);
            return;
    }

    // Initialize the radio
    Radio.initialize(freq_code, msg.node_id, msg.network_id);

    // The radio is now initialized
    is_radio_initialized = true;
}
//=========================================================================================================



//=========================================================================================================
// handle_encrypt_key() - Tells the radio what the network encryption key is
//=========================================================================================================
void handle_encrypt_key(const unsigned char* raw)
{
    // Map our structure on top of the raw packet
    map_struct(encrypt_key_t, msg);

    // Tell the radio what the encryption key is
    Radio.encrypt(msg.encryption_key);
}
//=========================================================================================================


//=========================================================================================================
// handle_to_radio() - Sends a packet to the radio
//=========================================================================================================
void handle_to_radio(const unsigned char* raw)
{
    // Map our structure on top of the raw packet
    map_struct(to_radio_t, msg);

    // Make sure the radio is initialized before trying to send a message
    if (!is_radio_initialized)
    {
        UART.printf("Radio not initialized!");
        return;
    }

    if (strncmp(msg.data, "I see you ", 10) != 0) UART.printf("Bad outgoing data!");

    // Ask the radio to send this message
    Radio.send(msg.dst_node, &msg.data, msg.data_len);
}
//=========================================================================================================



//=========================================================================================================
// dispatch_serial_message() - Processes messages from the serial port
//=========================================================================================================
void dispatch_serial_message(const unsigned char* packet)
{
    unsigned char packet_len  = packet[0];
    unsigned char packet_crc  = packet[1];
    unsigned char packet_type = packet[2];
    unsigned char* msg = packet + 3;

    switch(packet_type)
    {
        case SP_ECHO:
            handle_echo(packet);
            break;

        case SP_INIT_RADIO:
            handle_init_radio(packet);
            break;
        
        case SP_ENCRYPT_KEY:
            handle_encrypt_key(packet);
            break;

        case SP_TO_RADIO:
            handle_to_radio(packet);
            break;

        default:
            UART.printf("Recvd unknown packet type %i", packet_type);
            break;
    }
    
    // Tell the backhaul that we processed his command
    UART.ready_to_receive(true);
}
//=========================================================================================================



//=========================================================================================================
// handle_incoming_radio_packet() - Sends an incoming packet to the client
//=========================================================================================================
void handle_incoming_radio_packet()
{
    from_radio_t    packet;

    packet.packet_len  = sizeof(packet) + Radio.DATALEN;
    packet.packet_type = SP_FROM_RADIO;
    packet.src_node    = Radio.SENDERID;
    packet.dst_node    = Radio.TARGETID;
    packet.data_len    = Radio.DATALEN;
    memcpy(packet.data,  Radio.DATA, packet.data_len);
    UART.transmit_raw((unsigned char*)&packet);
}
//=========================================================================================================


//=========================================================================================================
// loop() - The big loop, waits forever for incoming messages from the serial port or the radio
//=========================================================================================================
void loop()
{
    unsigned char* msg;

    if (UART.is_message_waiting(&msg))
    {
        dispatch_serial_message(msg);
    }

    if (is_radio_initialized && Radio.receiveDone())
    {
        handle_incoming_radio_packet();
    }
}
//========================================================================================================= 

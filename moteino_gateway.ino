#include <stdint.h>
#include "packet_uart.h"
#include "RFM69.h"


#define map_struct(t,m) t& m=*(t*)raw

//=========================================================================================================
// Formats of messages to and from the gateway
//=========================================================================================================
struct init_radio_t
{
    uint8_t   packet_len;
    uint8_t   packet_type;
    uint16_t  frequency;
    uint16_t  node_id;
    uint8_t   network_id;
};

struct encrypt_key_t
{
    uint8_t   packet_len;
    uint8_t   packet_type;
    uint8_t   encryption_key[16];
};

//=========================================================================================================



CPacketUART UART;
RFM69       Radio;

void setup()
{
    UART.begin(250000);
}




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
// dispatch_serial_message() - Processes messages from the serial port
//=========================================================================================================
void dispatch_serial_message(const unsigned char* packet)
{
    unsigned char packet_len  = packet[0];
    unsigned char packet_type = packet[1];
    unsigned char* msg = packet + 2;

    switch(packet_type)
    {
        case SP_ECHO:
            UART.echo(msg, packet_len - 2);
            break;

        case SP_INIT_RADIO:
            handle_init_radio(packet);
            break;
        
        case SP_ENCRYPT_KEY:
            handle_encrypt_key(packet);
            break;

        default:
            UART.printf("Recvd unknown packet type %i", packet_type);
            break;
    }
    
    // Tell the backhaul that we processed his command
    UART.ready_to_receive();
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
}
//========================================================================================================= 

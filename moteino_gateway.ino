#include <stdint.h>
#include "packet_uart.h"


CPacketUART UART;

void setup()
{
    UART.begin(115200);
    UART.printf("Firmware booted");
}


//=========================================================================================================
// handle_serial_message() - Processes messages from the serial port
//=========================================================================================================
void handle_serial_message(const unsigned char* packet)
{
    unsigned char packet_len  = packet[0];
    unsigned char packet_type = packet[1];
    unsigned char* msg = packet + 2;

    switch(packet_type)
    {
        case SP_ECHO:
            UART.echo(msg, packet_len - 2);
            break;
    }
    
    UART.printf("Recvd packet type %i", packet_type);
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
        handle_serial_message(msg);
    }
}
//========================================================================================================= 

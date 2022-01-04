//=========================================================================================================
// packet_uart() - A fast UART that sends and receives packets
//=========================================================================================================
#ifndef _PACKET_UART_H_
#define _PACKET_UART_H_

enum
{
    SP_PRINT       = 0x01,  // To client
    SP_READY       = 0x02,  // To client
    SP_ECHO        = 0x03,  // From client
    SP_ALIVE       = 0x04,  // To client
    SP_INIT_RADIO  = 0x05,  // From client
    SP_ENCRYPT_KEY = 0x06,  // From client
    SP_FROM_RADIO  = 0x07   // To client
};

class CPacketUART
{
public:

    // Call this once at boot with the desired baudrate.  250000 is optimal
    void    begin(uint32_t baud);

    // Sets up the buffer to receive a packet and sends a "ready to receive" message
    void    ready_to_receive();

    // Returns true if a message is waiting
    bool    is_message_waiting(unsigned char** p = nullptr);

    // Print a debug string on the client
    void    printf(const char* format, ...);

    // Tell the client we're alive
    void    indicate_alive();

    // Print arbitray data to the client
    void    echo(const unsigned char* s, int length);

    // Send a raw packet to the client
    void    transmit_raw(const void* vp);
};


#endif
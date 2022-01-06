//=========================================================================================================
// packet_uart() - A fast UART that sends and receives packets
//=========================================================================================================
#ifndef _PACKET_UART_H_
#define _PACKET_UART_H_

enum
{
    SP_PRINT       = 0x01,  // To client
    SP_READY       = 0x02,  // To client
    SP_ECHO        = 0x03,  // To and From client
    SP_ALIVE       = 0x04,  // To client
    SP_INIT_RADIO  = 0x05,  // From client
    SP_ENCRYPT_KEY = 0x06,  // From client
    SP_FROM_RADIO  = 0x07,  // To client
    SP_TO_RADIO    = 0x08,  // From client
    SP_NAK         = 0x09   // To client
};

class CPacketUART
{
public:

    // Call this once at boot with the desired baudrate.  250000 is optimal
    void    begin(uint32_t baud);

    // Call this to find out if there is a packet waiting to be processed
    bool    is_message_waiting(unsigned char** p = nullptr);

    // Call this to acknowledge an incoming packet has been handled
    void    acknowledge_handled_packet();

    // Print a debug string on the client
    void    printf(const char* format, ...);

    // Tell the client we're alive
    void    indicate_alive();

    // Send a raw packet to the client
    void    transmit_raw(const void* vp);

protected:

    // The state machine that manages the receipt of incoming serial packets
    bool    rx_state_machine();

    // This places the rx machinery ready to receive an incoming packet
    void    make_ready_to_receive();

};


#endif
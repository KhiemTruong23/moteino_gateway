//=========================================================================================================
// packet_uart() - A fast UART that sends and receives packets
//=========================================================================================================
#ifndef _PACKET_UART_H_
#define _PACKET_UART_H_


class CPacketUART
{
public:

    // Call this once at boot with the desired baudrate.  250000 is optimal
    void    begin(uint32_t baud);

    // Sets up the buffer to receive a packet and sends a "ready to receive" message
    void    ready_to_receive();

    // Returns true if a message is waiting
    bool    is_message_waiting(unsigned char** p = nullptr);

};


#endif
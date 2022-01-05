//=========================================================================================================
// packet_uart() - A fast UART that sends and receives packets
//=========================================================================================================
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <arduino.h>
#include "packet_uart.h"

uint8_t fast_crc8(const uint8_t* in, uint8_t count);

//=========================================================================================================
// Change this to "#if 0" to use USART0, and "#if 1" to use USART1
//=========================================================================================================
#if 0
    #define xUBRRH UBRR1H
    #define xUBRRL UBRR1L
    #define xUCSRA UCSR1A
    #define xUCSRB UCSR1B
    #define xUCSRC UCSR1C
    #define xUDR   UDR1
    #define bitRXEN  (1 << RXEN1)
    #define bitTXEN  (1 << TXEN1)
    #define bitRXCIE (1 << RXCIE1)
    #define xUSART_RX_vect USART1_RX_vect
#else
    #define xUBRRH UBRR0H
    #define xUBRRL UBRR0L
    #define xUCSRA UCSR0A
    #define xUCSRB UCSR0B
    #define xUCSRC UCSR0C
    #define xUDR   UDR0
    #define bitRXEN  (1 << RXEN0)
    #define bitTXEN  (1 << TXEN0)
    #define bitRXCIE (1 << RXCIE0)
    #define xUSART_RX_vect USART0_RX_vect
#endif
//=========================================================================================================


//=========================================================================================================
// The incoming serial buffer
//=========================================================================================================
static volatile unsigned char rx_buffer[256];
static volatile unsigned char* rx_ptr;
static volatile unsigned char rx_count;
static volatile unsigned long rx_start;
//=========================================================================================================



//=========================================================================================================
// xUSART_RX_vect() - The interrupt service routine to store incoming serial characters
//=========================================================================================================
ISR(xUSART_RX_vect)
{
    *rx_ptr++ = xUDR;
    if (++rx_count == 1) rx_start = millis();
}
//=========================================================================================================


//=========================================================================================================
// transmit() - Transmits a string of bytes to the client side
//=========================================================================================================
void CPacketUART::transmit_raw(const void* vp)
{
    // Transmute our pointer into a byte pointer
    const unsigned char* s = (const unsigned char*)(vp);

    // Fetch the number of bytes we need to transmit
    unsigned char len = s[0];

    // So long as we have characters left to output...
    while (len--)
    {
        // Wait for the UART transmitter to become available
        while ((xUCSRA & (1 << UDRE0)) == 0);
        
        // And write the next byte to the UART transmitter
        xUDR = *s++;
    }
}
//=========================================================================================================


//=========================================================================================================
// ready_to_receive() - Tells the backhaul that we are ready to receive a serial packet
//=========================================================================================================
void CPacketUART::ready_to_receive(bool is_ACK)
{
    static const unsigned char ack[] = {3, 0, SP_READY};
    static const unsigned char nak[] = {3, 0, SP_NAK};
    
    // We have no bytes in our RX buffer
    rx_buffer[0] = rx_count = 0;

    // The next incoming byte gets stored in the first byte of the RX buffer
    rx_ptr = rx_buffer;

    // Tell the backhaul that we're ready for another packet
    transmit_raw(is_ACK ? ack : nak);
}
//=========================================================================================================


//=========================================================================================================
// begin() - Sets of the UART configuration, enables the interrupts, and sends a "ready to receive" msg
//=========================================================================================================
void CPacketUART::begin(uint32_t baud)
{
    // Turn off interrupts
    cli();

    // Compute the baud-rate pre-scaler assuming we're going to use baud doubling
    uint32_t baud_prescaler = (F_CPU / 8 / baud) - 1;

    // Turn on the U2X baud-rate doubling bit
    xUCSRA = 2;
  
    // Set up the baud-rate pre-scaler
    xUBRRH = (baud_prescaler >> 8) & 0xFF;
    xUBRRL = baud_prescaler & 0xFF;

    // Set data format to 8/N/1
    xUCSRC = 6;

    // Enable the UART TX and RX pins
    xUCSRB |= bitRXEN;
    xUCSRB |= bitTXEN;
  
    // Enable the interrupt that gets generated every time a byte is received
    xUCSRB |= bitRXCIE;

    // Tell the backhaul that we're ready to receive a packet
    ready_to_receive(true);

    // Tell the backhaulthat we're alive
    indicate_alive();

    // Allow incoming serial interrupts to occur
    sei();
}
//=========================================================================================================


//=========================================================================================================
// printf() - Performs a printf to the client side
//=========================================================================================================
void CPacketUART::printf(const char* format, ...)
{
    unsigned char buffer[256];
    va_list va;

    va_start(va, format);
    int len = vsprintf(buffer+3, format, va);
    va_end(va);

    buffer[0] = len + 3;
    buffer[1] = 0;
    buffer[2] = SP_PRINT;
    transmit_raw(buffer);
}
//=========================================================================================================

//=========================================================================================================
// indicate_alive() - Tell the client we're up and running
//=========================================================================================================
void CPacketUART::indicate_alive()
{
    unsigned char packet[] = {3, 0, SP_ALIVE};
    transmit_raw(packet);
}
//=========================================================================================================




//=========================================================================================================
// is_message_waiting() - Returns true if a message is waiting in the receive buffer
//=========================================================================================================
bool CPacketUART::is_message_waiting(unsigned char** p = nullptr)
{
    // If there are no bytes in the receive buffer, we're done
    if (rx_count == 0) return false;
    
    // Is there an entire packet waiting in the input buffer?
    bool is_packet_waiting = (rx_buffer[0] == rx_count);

    // If we don't have a complete packet waiting...
    if (!is_packet_waiting)
    {
        // How long have we been waiting for the packet to complete?
        unsigned long elapsed = millis() - rx_start;

        // If we've timed out waiting for the packet to complete, tell the client
        if (elapsed > 20)
        {
            printf("DROPPED BYTE!");
            ready_to_receive(false);
        }

        // And tell the caller that there's no packet waiting
        return false;
    }

    //--------------------------------------------------------------
    //  If we get here, there is a complete packet waiting for us
    //--------------------------------------------------------------

    // Check the CRC
    uint8_t old_crc = rx_buffer[1];
    uint8_t new_crc = fast_crc8(rx_buffer+2, rx_count - 2);
    if (old_crc != new_crc)
    {
        ready_to_receive(false);
        return false;
    }

    // Hand the caller a pointer to the message buffer
    if (p) *p = rx_buffer;

    // Tell the caller they have a message waiting to process
    return true;
}
//=========================================================================================================

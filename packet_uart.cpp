//=========================================================================================================
// packet_uart() - A fast UART that sends and receives packets
//=========================================================================================================
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <arduino.h>
#include "packet_uart.h"


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
//=========================================================================================================



//=========================================================================================================
// xUSART_RX_vect() - The interrupt service routine to store incoming serial characters
//=========================================================================================================
ISR(xUSART_RX_vect)
{
    *rx_ptr++ = xUDR;
    ++rx_count;
}
//=========================================================================================================



//=========================================================================================================
// transmit() - Transmits a string of bytes to the client side
//=========================================================================================================
static void transmit(const unsigned char* s, int len)
{
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
void CPacketUART::ready_to_receive()
{
    rx_buffer[0] = rx_count = 0;
    rx_ptr = rx_buffer;
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
    ready_to_receive();

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
    int len = vsprintf(buffer+2, format, va);
    va_end(va);

    buffer[0] = len + 2;
    buffer[1] = 1;
    transmit(buffer, buffer[0]);
}
//=========================================================================================================

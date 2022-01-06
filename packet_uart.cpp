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
// DEVICE_TYPE: 0 = AVR1284p-SerialPort0.  1 = AVR1284p-SerialPort1   2 = AVR328p
//=========================================================================================================
#define DEVICE_TYPE 2

// AVR-1284p, Serial Port 0
#if DEVICE_TYPE == 0
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


// AVR-1284p, Serial Port 1
#if DEVICE_TYPE == 1
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
#endif


// AVR-328p
#if DEVICE_TYPE == 2
    #define xUBRRH UBRR0H
    #define xUBRRL UBRR0L
    #define xUCSRA UCSR0A
    #define xUCSRB UCSR0B
    #define xUCSRC UCSR0C
    #define xUDR   UDR0
    #define bitRXEN  (1 << RXEN0)
    #define bitTXEN  (1 << TXEN0)
    #define bitRXCIE (1 << RXCIE0)
    #define xUSART_RX_vect USART_RX_vect
#endif
//=========================================================================================================

enum rx_state_t
{
    WAIT_PROLOGUE_1,
    WAIT_PROLOGUE_2,
    WAIT_PACKET_COMPLETE
};



//=========================================================================================================
// The incoming serial buffer
//=========================================================================================================
static volatile unsigned char rx_buffer[256];
static volatile unsigned char* rx_ptr;
static volatile unsigned char rx_count;
static volatile unsigned long rx_start;
static          rx_state_t    rx_state;
//=========================================================================================================


//=========================================================================================================
// These messages are used to ACK or NAK the receipt of a prologue or a packet
//=========================================================================================================
static const unsigned char ACK[] = {3, 0, SP_READY};
static const unsigned char NAK[] = {3, 0, SP_NAK};
//=========================================================================================================


//=========================================================================================================
// xUSART_RX_vect() - The interrupt service routine to store incoming serial characters
//=========================================================================================================
ISR(xUSART_RX_vect)
{
    // Store the incoming byte into the rx buffer
    *rx_ptr++ = xUDR;

    // If this is the first or second byte in the buffer, record when we received it
    if (rx_count < 2) rx_start = millis();
    
    // We now have one more byte in the rx buffer
    ++rx_count;
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

    // Make the RX machinery ready to receive a packet
    make_ready_to_receive();
    
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
// rx_state_machine() - Runs the state machine that manages the reliable receipt of serial packets
//=========================================================================================================
bool CPacketUART::rx_state_machine()
{
    unsigned long elapsed;

    // If we're waiting for the first prologue byte to arrive...
    if (rx_state == WAIT_PROLOGUE_1)
    {
        // If no bytes have arrived, there is no message waiting
        if (rx_count == 0) return false;

        // If we've received at least one byte, we're waiting for the 2nd prologue byte
        rx_state = WAIT_PROLOGUE_2;            
    }

    // If we're waiting for the 2nd prologue byte to arrive and it hasn't...
    if (rx_state == WAIT_PROLOGUE_2 && rx_count == 1)
    {
        // How long have we been waiting the arrival of the second?
        elapsed = millis() - rx_start;
            
        // If the 2nd prologue byte is overdue, send the client a NAK
        if (elapsed > 20)
        {
            make_ready_to_receive();
            transmit_raw(NAK);
        }

        // Indicate that no packet has yet arrived
        return false;
    }

    // If we're waiting for the 2nd prologue byte to arrive and it has...
    if (rx_state == WAIT_PROLOGUE_2 && rx_count == 2)
    {
        // If the prologue bytes are complements of each other, we have a good prologue
        if (rx_buffer[0] == (~rx_buffer[1] & 0xFF))
        {
            // Throw away the 2nd prologue byte
            --rx_ptr;
            --rx_count;

            // Tell the client side he may continue sending
            transmit_raw(ACK);

            // Now we're waiting for the rest of the packet to arrive
            rx_state = WAIT_PACKET_COMPLETE;
        }

        // If we get here, one of the prologue bytes was corrupted by noise
        else
        {
            make_ready_to_receive();
            transmit_raw(NAK);
        }

        // We don't have a packet waiting
        return false;
    }

    //-----------------------------------------------------------------------------------
    // If we get here, we are by definition waiting for the rest of the packet to arrive
    //-----------------------------------------------------------------------------------
    
    // If we don't have at least two bytes in the buffer, we haven't received any 
    // bytes after the prologue yet
    if (rx_count == 1) return false;

    // If we don't have a complete message yet...
    if (rx_count != rx_buffer[0])
    {
        // How long have we been waiting for the the packet to complete?
        elapsed = millis() - rx_start; 

        // If we've timed out, send a NAK to the client
        if (elapsed > 20)
        {
            make_ready_to_receive();
            transmit_raw(NAK);
        }

        // We don't yet have a complete packet
        return false;
    }

    //-----------------------------------------------------------------------------------
    // If we get here, we have a complete packet!
    //-----------------------------------------------------------------------------------

    // Extract the packet CRC that the client computed
    uint8_t old_crc = rx_buffer[1];

    // Compute our own CRC of the packet
    uint8_t new_crc = fast_crc8(rx_buffer+2, rx_count - 2);
    
    // If the CRC's don't match, reject this packet
    if (old_crc != new_crc)
    {
        make_ready_to_receive();
        transmit_raw(NAK);
        return false;
    }

    // If we get here, we have received an entire packet, and the CRCs match!
    return true;
}
//=========================================================================================================


//=========================================================================================================
// is_message_waiting() - Returns true if a message is waiting in the receive buffer
//=========================================================================================================
bool CPacketUART::is_message_waiting(unsigned char** p)
{

    // Hand the caller a pointer to the message buffer
    if (p) *p = rx_buffer;

    // Tell the caller whether they have a message waiting to process
    return rx_state_machine();
}
//=========================================================================================================


//=========================================================================================================
// make_ready_to_receive() - Makes the RX machinery ready to receive a new packet
//=========================================================================================================
void CPacketUART::make_ready_to_receive()
{
    // We have no bytes in our RX buffer
    rx_buffer[0] = rx_count = 0;

    // The next incoming byte gets stored in the first byte of the RX buffer
    rx_ptr = rx_buffer;

    // We're waiting for the arrival of the first prologue byte
    rx_state = WAIT_PROLOGUE_1;
}
//=========================================================================================================



//=========================================================================================================
// acknowledge_handled_packet() - Tells the client he is free to transmit a new packet to us
//=========================================================================================================
void CPacketUART::acknowledge_handled_packet()
{
    make_ready_to_receive();
    transmit_raw(ACK);
}
//=========================================================================================================

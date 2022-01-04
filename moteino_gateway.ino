#include <stdint.h>
#include "packet_uart.h"

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



#define BAUD_PRESCALER ((F_CPU/8/115200)-1)



#if 0
ISR(xUSART_RX_vect)
{
  unsigned char c = xUDR;
  if (c != 10) c++;
  xUDR = c;
}
#endif



CPacketUART UART;
void testit()
{
  UART.begin(115200);
}

void transmit(const char* s, int len)
{
  while (len--)
  {
    while ((xUCSRA & (1 << UDRE0)) == 0);
    xUDR = *s++;
  }
}

void setup()
{
  testit();

  // Turn on the U2X baud-rate doubling bit
  xUCSRA = 2;
  
  // Set up the baud-rate pre-scaler
  xUBRRH = BAUD_PRESCALER >> 8;
  xUBRRL = BAUD_PRESCALER & 0xFF;

  // Enable the UART TX and RX pins
  xUCSRB |= bitRXEN;
  xUCSRB |= bitTXEN;
  
  // Enable the interrupt that gets generated every time a byte is received
  xUCSRB |= bitRXCIE;

  // Set data format to 8/N/1
  xUCSRC = 6;

  transmit("hello\n", 6);

  sei();
  while(true);  
  
  #if 0
  while (true)
  {
    while ((xUCSRA & 0x80) == 0);
    unsigned char c = UDR0;
    UDR0 = (c == '\n') ? c : c+1;
  }
  #endif
  
}


void loop() {}
 

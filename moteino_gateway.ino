#include <stdint.h>
#include "packet_uart.h"



CPacketUART UART;
void testit()
{
  UART.begin(115200);

  int count = 0;
  while (true)
  {
    UART.printf("Hello world %i", ++count);
    delay(1000);
  }

}

void setup()
{
  testit();
  
}


void loop() {}
 

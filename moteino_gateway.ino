#include <stdint.h>
#include "packet_uart.h"



CPacketUART UART;
void testit()
{
  UART.begin(115200);
}

void setup()
{
  testit();
  
}


void loop() {}
 

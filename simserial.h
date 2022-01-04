//=========================================================================================================
// simserial.h - Defines a simulation of the Arduino "Serial" object
//=========================================================================================================
#ifndef _SIMSERIAL_H_
#define _SIMSERIAL_H_

class CSimSerial
{
public:

    void    println(const char* s = "") {}
    void    print(int x, int style = 0) {}
    void    println(int x, int style = 0) {}

};

extern CSimSerial SerialX;

#endif
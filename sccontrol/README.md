sccontrol
==========

Turns a Raspberry Pi into a simple scanner controller.

Currently uses the luma.oled library to talk to a sh1106 I2C OLED display, as the main control screen. And the Pi's GPIO as buttons. It communicates over sockets to `scingest` which performs the scanner communication.

**sccontrol** is designed to be a bit lighter on resources to ensure smooth running on a Pi.
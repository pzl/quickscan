#!/usr/bin/env python3
try:
	from RPi import GPIO
except RuntimeError:
	pass
import atexit
import termios, tty, sys
import logging

class Button(object):
	"""a physical button"""
	def __init__(self, pin):
		super(Button, self).__init__()
		self.pin = pin
		GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

	def listen(self, callback):
		GPIO.add_event_detect(self.pin, GPIO.FALLING, callback=callback, bouncetime=200)
	def stop_listening(self):
		GPIO.remove_event_detect(self.pin)



class Button_Interface(object):
	"""using Pi's GPIO for interacting"""
	def __init__(self, pins):
		super(Button_Interface, self).__init__()
		self.pins = pins
		self.buttons = []
		GPIO.setmode(GPIO.BOARD)
		atexit.register(self.cleanup)
		#GPIO.setup(pins, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		for p in pins:
			self.buttons.append(Button(p))

	def cleanup(self):
		GPIO.cleanup()

	def listen(self, event_callback):
		"""Synchronously waits for main button press
			while other buttons are handled in another thread
		"""
		SCAN_BTN=16
		menu_btns = [b for b in self.buttons if b.pin != SCAN_BTN]
		self.event_callback = event_callback
		logging.debug("enabling buttons")
		for b in menu_btns:
			b.listen(self.button_press)
		logging.debug("waiting for scan button")
		GPIO.wait_for_edge(SCAN_BTN, GPIO.FALLING)
		logging.debug("scan button pressed")
		logging.debug("disabling buttons")
		for b in menu_btns:
			b.stop_listening()
		event_callback("scan")

	def button_press(self,pin):
		if self.screen.is_asleep():
			self.screen.on()
			return
		if pin == 11:
			self.event_callback("up")
		elif pin == 13:
			self.event_callback("down")
		elif pin == 15:
			self.event_callback("enter")
		#elif pin == 16: #SCAN
		# not handling scan press in thread because
		# self.buttons[x].stop_listening crashes on Pi Zero

class Keys_Interface(object):
	"""Keyboard interface for interacting via terminal (e.g. desktop testing)"""
	def __init__(self):
		super(Keys_Interface, self).__init__()
		self.old_term_stg = termios.tcgetattr(sys.stdin.fileno())
		atexit.register(self.cleanup)

	def cleanup(self):
		termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.old_term_stg)

	def listen(self, event_callback):
		try:
			tty.setraw(sys.stdin.fileno())
			ch = sys.stdin.read(1)
			if ch == "\x1b":
				ar = sys.stdin.read(2)
				ch = ch+ar
		finally:
			termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.old_term_stg)
		
		if ch == "\x1b[A":
			event_callback("up")
		elif ch == "\x1b[B":
			event_callback("down")
		elif ch == "\r":
			event_callback("enter")
		elif ch == " ":
			event_callback("scan")
		elif ch == "\x03":
			raise KeyboardInterrupt

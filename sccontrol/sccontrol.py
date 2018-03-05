#!/usr/bin/env python3

from RPi import GPIO
from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from luma.core.render import canvas
#from luma.emulator.device import pygame
from PIL import ImageFont
import os, sys
from signal import signal, SIGTERM, SIGINT
import atexit
import time
from threading import Timer


def circle(x,y,r):
	return (x-r,y-r,x+r,y+r)

class screen_timeout(object):
	"""simple context manager for controlling a screen sleep time"""
	def __init__(self, screen, t=5):
		super(screen_timeout, self).__init__()
		self.screen = screen
		self.t=t
	def __enter__(self):
		pass
		#self.screen.activate()
	def __exit__(self, *_):
		self.screen.activate() # activate after drawing has finished
		self.screen.sleep_timeout(self.t)
def loadfont(name, size=12):
		fontp = os.path.abspath(os.path.join(
			os.path.dirname(__file__),
			'fonts', name))
		return ImageFont.truetype(fontp, size)



class Setting(object):
	"""Settings collection object"""
	def __init__(self, name, values, current=None):
		super(Setting, self).__init__()
		self.name = name
		self.values = values
		self.current = current if current else values[0]
	def __str__(self):
		return "{}: {}".format(self.name, self.current)
	def __repr__(self):
		return self.__str__()
	def index(self):
		return self.values.index(self.current)


class Sidebar(object):
	"""draws the button sidebar"""

	edge_pad=4
	y=0
	arrow_height=6
	btn_gap=9.5
	font = loadfont("tiny.ttf",6)

	def __init__(self,width):
		super(Sidebar, self).__init__()
		self.width = width

	def draw_arrow(self,c,d,direction="UP"):
		if direction == "UP":
			pts = (
					d.width-self.width+self.edge_pad+1,self.y+self.arrow_height,
					d.width-self.width/2+1,self.y,
					d.width-self.edge_pad+1,self.y+self.arrow_height
				)
		else:
			pts = (
					d.width-self.width+self.edge_pad+1,self.y,
					d.width-self.width/2+1,self.y+self.arrow_height,
					d.width-self.edge_pad+1,self.y
				)
		c.polygon(pts,fill="white")
		self.y += self.arrow_height

	def draw_line(self,c,d):
		self.y+=self.btn_gap
		c.line((d.width-self.width,self.y,d.width,self.y),fill="white",width=1)
		self.y+=self.btn_gap

	def draw_txt(self,c,d,txt):
		w,h = c.textsize(txt,font=self.font)
		c.text((d.width-self.width/2-w/2,self.y),txt,font=self.font,fill="white")
		self.y+=h

	def draw(self,c,d,page):
		self.y=4
		c.line((d.width-self.width,0,d.width-self.width,d.height),width=1,fill="white")
		self.draw_arrow(c,d,"UP")
		self.draw_line(c,d)
		self.draw_arrow(c,d,"DOWN")
		self.draw_line(c,d)
		if type(page) == SettingPage:
			self.draw_txt(c,d, "SET")
		else:
			self.draw_txt(c,d,"OK")




class MenuPage(object):
	"""Draws an individual Menu"""

	page_font = loadfont("tiny.ttf",6)
	menu_font = loadfont("ProggyTiny.ttf",16)
	menu_item_vpad=1 # for highlight box
	menu_item_hpad=2 # for highlight box
	menu_item_x=20
	menu_item_x_stop=100
	menu_item_vstart=10
	menu_item_vstep=12

	scanbtn_height=10
	sidebar_width=20

	def __init__(self, title, items, highlighted=0):
		super(MenuPage, self).__init__()
		self.items = items
		self.title = title
		self.highlighted=highlighted
		self.sidebar = Sidebar(self.sidebar_width)

	def up(self):
		self.highlighted -= 1
		if self.highlighted < 0:
			self.highlighted = 0
	def down(self):
		self.highlighted += 1
		if self.highlighted >= len(self.items):
			self.highlighted = len(self.items)-1

	def _draw_title(self,c):
		c.text((0,0), self.title, font=self.page_font, fill="white")
	def _draw_items(self, c, d):
		if len(self.items) > self.highlighted+2 and len(self.items) > 3:
			c.polygon(( # down arrow
					self.menu_item_x-12,d.height-self.scanbtn_height-7,
					self.menu_item_x-8 ,d.height-self.scanbtn_height-7,
					self.menu_item_x-10,d.height-self.scanbtn_height-5),
				fill="white")

		if self.highlighted > 2:
			c.polygon(( # up arrow
					self.menu_item_x-12,10,
					self.menu_item_x-8 ,10,
					self.menu_item_x-10,8),
				fill="white")

		if len(self.items) < 4 or self.highlighted < 3:
			for i,item in enumerate(self.items[:4]):
				c.text((self.menu_item_x,i*self.menu_item_vstep+self.menu_item_vstart), str(item), font=self.menu_font, fill="white")
				if i == self.highlighted:
					self._draw_highlight_box(c, i*self.menu_item_vstep+self.menu_item_vstart)
		else:
			self._draw_highlight_box(c, 2*self.menu_item_vstep+self.menu_item_vstart)
			for i,item in enumerate(self.items[self.highlighted-2:self.highlighted+2]):
				c.text((self.menu_item_x,i*self.menu_item_vstep+self.menu_item_vstart), str(item), font=self.menu_font, fill="white")

	def _draw_highlight_box(self,c,y):
		_,height = c.textsize("X",font=self.menu_font)
		c.rectangle((self.menu_item_x-self.menu_item_hpad,
					y-self.menu_item_vpad,
					self.menu_item_x_stop,
					y+height+self.menu_item_vpad*2),
				outline="white")
	def _draw_scan_btn(self,c, d):
		c.rectangle((0,d.height-self.scanbtn_height,d.width-self.sidebar_width,d.height),fill="white")
		w,h = c.textsize("SCAN!",font=self.menu_font)
		c.text(((d.width-self.sidebar_width)/2-w/2,d.height-self.scanbtn_height/2-h/2),"SCAN!", font=self.menu_font, fill="black")

	def draw(self, c, d):
		self._draw_title(c)
		self._draw_items(c, d)
		self._draw_scan_btn(c, d)
		self.sidebar.draw(c,d,self)


class SettingPage(MenuPage):
	def __init__(self, setting):
		super(SettingPage, self).__init__(setting.name, setting.values)
		self.setting = setting
		self.highlighted = self.setting.index()
	def select(self):
		self.setting.current = self.setting.values[self.highlighted]

class Menu(object):
	"""Main menu"""
	def __init__(self):
		super(Menu, self).__init__()
		self.settings = []
		self.settings.append(Setting("Mode",("Color","Gray","B/W")))
		self.settings.append(Setting("DPI",list(range(50,601,50)),500))
		self.settings.append(Setting("Sides",(1,2),2))
		self.main = MenuPage("Main Menu", self.settings)
		self.page = self.main

	def up(self):
		self.page.up()
	def down(self):
		self.page.down()
	def enter(self):
		if self.page == self.main:
			setting = self.settings[self.page.highlighted]
			self.page = SettingPage(setting)
		else:
			self.page.select()
			self.page = self.main
	def draw(self, canvas, device):
		self.page.draw(canvas, device)

class Screen(object):
	"""Represents the OLED scren"""
	def __init__(self,init_menu):
		super(Screen, self).__init__()
		self.sleep_timer=None
		self.state='OFF'
		self.oled = sh1106(i2c(port=1, address=0x3C))
		#self.oled = pygame(width=128, height=64)
		self._welcome()
		time.sleep(1)
		self.draw_menu(init_menu)
		atexit.register(self.cleanup)

	def _welcome(self):
		self.activate()
		font = loadfont("Raleway-Bold.ttf",18)
		FA = loadfont("fontawesome-webfont.ttf",25)
		char = "\uf118"
		with canvas(self.oled) as draw:
			draw.text((25,5), "Welcome",fill="white",font=font)
			w,h = draw.textsize(char,font=FA)
			draw.text((self.oled.width/2-w/2,self.oled.height*2/3-h/2),char,fill="white",font=FA)
			"""
			x=self.oled.width/2
			y=self.oled.height*2/3
			r=12
			draw.ellipse(circle(x,y,r), fill="white")
			draw.ellipse(circle(x-5,y-r/2,2),fill="black")
			draw.ellipse(circle(x+5,y-r/2,2),fill="black")
			draw.chord((x-r+3,y-4,x+r-3,y+9), 0, 180, fill="black")
			"""

	def is_asleep(self):
		return self.state == 'OFF'
	def activate(self):
		if self.sleep_timer:
			self.sleep_timer.cancel()
			self.sleep_timer = None
		else:
			self.on()
	def _sleep(self):
		self.off()
		self.sleep_timer = None
	def sleep_timeout(self, t):
		self.sleep_timer = Timer(t, self._sleep)
		self.sleep_timer.start()
	def cleanup(self):
		self.off()

	def on(self):
		self.state='ON'
		self.oled.show()
	def off(self):
		self.state = 'OFF'
		self.oled.hide()

	def draw_menu(self, menu):
		with screen_timeout(self), canvas(self.oled) as draw:
			menu.draw(draw, self.oled)

	def draw_scan(self):
		font = loadfont("Raleway-Bold.ttf",18)
		self.activate() # not auto-dimming here
		with canvas(self.oled) as draw:
			w,h = draw.textsize("Scanning...",font=font)
			draw.text((self.oled.width/2-w/2,self.oled.height/2-h/2),"Scanning...",font=font,fill="white")

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

class IO_Mgr(object):
	"""Manager for a collection of buttons"""
	def __init__(self, pins, screen, menu):
		super(IO_Mgr, self).__init__()
		self.buttons=[]
		self.pins = pins
		self.screen=screen
		self.menu = menu
		self.atexit(self.cleanup)
		GPIO.setmode(GPIO.BOARD)
		for p in pins:
			self.buttons.append(Button(p))
		#GPIO.setup(pins, GPIO.IN, pull_up_down=GPIO.PUD_UP)

	def cleanup(self):
		GPIO.cleanup()

	def listen(self):
		SCAN_BTN=16
		menu_btns = [b for b in self.buttons if b.pin != SCAN_BTN]
		while True:
			for b in menu_btns:
				b.listen(self.button_press)
			GPIO.wait_for_edge(SCAN_BTN, GPIO.FALLING)
			for b in menu_btns:
				b.stop_listening()
			self.screen.draw_scan()
	def button_press(self,pin):
		if self.screen.is_asleep():
			self.screen.on()
			return
		if pin == 11:
			self.menu.up()
			self.screen.draw_menu(self.menu)
		elif pin == 13:
			self.menu.down()
			self.screen.draw_menu(self.menu)
		elif pin == 15:
			self.menu.enter()
			self.screen.draw_menu(self.menu)
		"""
		elif pin == 16:
			# SCAN

			# note: the following crashes on Pi Zero
			#for b in self.buttons:
			#	b.stop_listening()
			self.screen.draw_scan()
		"""


def cleanup_at_exit():
	signal(SIGTERM, lambda signum, stack_frame: sys.exit(1))
	signal(SIGINT, lambda signum, stack_frame: sys.exit(1))

def main():
	cleanup_at_exit()
	pins=(11,13,15,16)
	menu = Menu()
	screen = Screen(menu)
	io = IO_Mgr(pins, screen, menu)
	io.listen()

if __name__ == "__main__":
	main()
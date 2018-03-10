#!/usr/bin/env python3
from util import loadfont, circle, document, is_pi, screen_timeout
from threading import Timer
import time
import atexit
from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from luma.core.render import canvas
try:
	from luma.emulator.device import pygame
except ImportError:
	pass
try:
	from RPi import GPIO
	from tft import TFT24T
	import spidev
except (ImportError, RuntimeError):
	pass
from PIL import Image



def draw_bottom_button(draw, device, sidebar_width, height, text, font):
	draw.rectangle((0,device.height-height, device.width-sidebar_width, device.height), fill="white")
	w,h = draw.textsize(text, font=font)
	draw.text( ((device.width-sidebar_width)/2-w/2, device.height-height/2-h/2), text, font=font, fill="black" )

class Mock_LCD(object):
	"""LCD imitator for development purposes"""
	def __init__(self):
		super(Mock_LCD, self).__init__()
	def backlight(self, onoff):
		pass
	def cleanup(self):
		pass
	def clear(self):
		pass
	def show(self, data):
		image = Image.frombytes('RGB', (240,320), data, 'raw')
		image.show()

class LCD(object):
	"""TFT display"""

	# pin definitions
	DC = 18
	RST = 22 # if omitted, tie to +3.3V
	LED = 12 # if omitted, tie to +3.3V

	def __init__(self):
		super(LCD, self).__init__()
		GPIO.setmode(GPIO.BOARD)
		self.device = TFT24T(spidev.SpiDev(), GPIO, landscape=False)
		self.state=0
		atexit.register(self.cleanup)

	def backlight(self, onoff):
		self.device.backlite(onoff)
	def off(self):
		GPIO.output(self.RST, GPIO.LOW)
		self.backlight(0)
		self.state=0
	def on(self):
		self.device.initLCD(self.DC, self.RST, self.LED)
		self.backlight(1)
		self.state=1
	def cleanup(self):
		self.off()

	def clear(self):
		self.device.clear()

	def show(self, data):
		if not self.state:
			self.on()
		image = Image.frombytes('RGB', (240,320), data, 'raw')
		self.device.display(image)

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

	def draw(self, c, d):
		self._draw_title(c)
		self._draw_items(c, d)
		draw_bottom_button(c, d, self.sidebar_width, self.scanbtn_height, "SCAN!", self.menu_font)
		self.sidebar.draw(c,d,self)


class SettingPage(MenuPage):
	def __init__(self, setting):
		super(SettingPage, self).__init__(setting.name, setting.values)
		self.setting = setting
		self.highlighted = self.setting.index()
	def select(self):
		self.setting.current = self.setting.values[self.highlighted]

class ProgressPage(object):
	"""Displays in-progress scan info, and actions"""
	def __init__(self):
		super(ProgressPage, self).__init__()
		self.pages=[]
		self.proggy = loadfont("ProggyTiny.ttf",12)
		self.button_font = loadfont("ProggyTiny.ttf",16)
		self.sidebar = Sidebar(15)
		self.selected=0
		self.complete=False
		
	def up(self):
		self.selected = max(0, self.selected-1)

	def down(self):
		self.selected = min(self.selected+1, len(self.pages)-1)

	def draw(self, c, d, msg):
		if msg == "feed start":
			txt = "Scanning next page..."
		elif msg == "page fed":
			txt = "saving data"
			self.pages.append("f")
		elif msg == "backside":
			txt = "Saving backside"
			self.pages.append("b")
		elif msg.startswith("PAGE"):
			_,pagenum = msg.split(" ")
			txt = "Saving Page {}".format(pagenum)
		else:
			txt = msg

		if self.complete:
			self.sidebar.draw(c,d,self)
			draw_bottom_button(c, d, self.sidebar.width, 10, "Accept", self.button_font)

		x,y=5,5
		xsep=20
		ysep=20
		for i,p in enumerate(self.pages):
			back = p == "b"
			if back:
				x -= xsep
			document(c,x,y+(ysep if back else 0),i+1,backside=back,active=i==self.selected and self.complete)
			x += xsep
		if txt:
			c.text((3,50),txt,font=self.proggy)



class Screen(object):
	"""Represents the OLED scren"""

	FA = loadfont("fontawesome-webfont.ttf",25)

	def __init__(self,init_menu):
		super(Screen, self).__init__()
		self.sleep_timer=None
		self.state='OFF'

		self.oled = sh1106(i2c(port=1, address=0x3C)) if is_pi() else pygame(width=128, height=64)
		self._welcome()
		time.sleep(1)
		self.draw_menu(init_menu)
		atexit.register(self.cleanup)

	def _welcome(self):
		self.activate()
		font = loadfont("Raleway-Bold.ttf",18)
		char = "\uf118"
		with canvas(self.oled) as draw:
			draw.text((25,5), "Welcome",fill="white",font=font)
			w,h = draw.textsize(char,font=self.FA)
			draw.text((self.oled.width/2-w/2,self.oled.height*2/3-h/2),char,fill="white",font=self.FA)
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

	def draw_icon_text(self, icon, txt, txtfont=None):
		if txtfont is None:
			txtfont = loadfont("Volter__28Goldfish_29.ttf",9)
		with canvas(self.oled) as draw:
			w,h = draw.textsize(txt,font=txtfont)
			draw.text((self.oled.width/2-w/2,self.oled.height*2/3-h/2), txt,fill="white",font=txtfont)
			w,h = draw.textsize(icon,font=self.FA)
			draw.text((self.oled.width/2-w/2,self.oled.height/3-h/2),icon,fill="white",font=self.FA)

	def draw_err(self, msg):
		self.draw_icon_text("\uf071", msg)
	def draw_complete(self):
		self.draw_icon_text("\uf00c", "Scan Complete", loadfont("Raleway-Bold.ttf",16))
	def draw_empty(self):
		self.draw_icon_text("\uf05a", "no pages found")

	def draw_progress(self, progress, *args):
		with canvas(self.oled) as draw:
			progress.draw(draw, self.oled, *args)


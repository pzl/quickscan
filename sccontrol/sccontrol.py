#!/usr/bin/env python3
try:
	from RPi import GPIO
except RuntimeError:
	pass
from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from luma.core.render import canvas
try:
	from luma.emulator.device import pygame
except ImportError:
	pass
from PIL import ImageFont
import os, sys
from signal import signal, SIGTERM, SIGINT
import atexit
import time
import socket
from threading import Timer
import json
import logging

logging.basicConfig(level=logging.DEBUG,format="%(asctime)s %(levelname)7s : %(message)s")

def is_pi():
	return os.uname().machine[:3] == 'arm'

def circle(x,y,r):
	return (x-r,y-r,x+r,y+r)

def document(d,x,y,n,backside=False):
	ratio=(8.5,11)
	scale=1.5
	#d.rectangle((x,y,x+ratio[0]*scale,y+ratio[1]*scale),outline="white")
	if backside:
		d.polygon(
			(
				x+(ratio[0]*scale)/3,y,
				x+ratio[0]*scale,y,
				x+ratio[0]*scale,y+ratio[1]*scale,
				x,y+ratio[1]*scale,
				x,y+(ratio[1]*scale)/4
			),
			outline="white"
		)
	else:
		d.polygon(
			(
				x,y,
				x+(ratio[0]*scale)*2/3,y,
				x+(ratio[0]*scale)*2/3,y+(ratio[1]*scale)/4,
				x+ratio[0]*scale,y+(ratio[1]*scale)/4,
				x+ratio[0]*scale,y+ratio[1]*scale,
				x,y+ratio[1]*scale,
			),
			outline="white"
		)
		d.line(( x+(ratio[0]*scale)*2/3,y,  x+ratio[0]*scale,y+(ratio[1]*scale)/4 ),fill="white",width=1)
	d.text((x+(ratio[0]*scale)/2,y+(ratio[1]*scale)/2),str(n),fill="white",font=loadfont("tiny.ttf",6))

class screen_timeout(object):
	"""simple context manager for controlling a screen sleep time"""
	def __init__(self, screen, t=5):
		super(screen_timeout, self).__init__()
		self.screen = screen
		self.t=t
	def __enter__(self):
		pass
		self.screen.activate()
	def __exit__(self, *_):
		#self.screen.activate() # activate after drawing has finished
		self.screen.sleep_timeout(self.t)
def loadfont(name, size=12):
		fontp = os.path.abspath(os.path.join(
			os.path.dirname(__file__),
			'fonts', name))
		return ImageFont.truetype(fontp, size)

class Scanner(object):
	"""communication with scingest"""
	def __init__(self):
		super(Scanner, self).__init__()
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.connect(("192.168.1.28",5555))
		atexit.register(self.cleanup)

	def cleanup(self):
		self.socket.close()
	def run(self, options, callback):
		self._send({"scan":True,"options":options})

		msg = self._get()
		while msg is not None:
			s = msg.decode("utf8")
			logging.info(s)
			ex = callback(s)
			if ex:
				break
			msg = self._get()

	def _send(self, thing):
		binjson = json.dumps(thing).encode('utf8')
		msglen = len(binjson).to_bytes(4, byteorder='big')
		self.socket.send(msglen+binjson)
	def _get(self):
		pkt_len = self.socket.recv(4)
		if pkt_len == b'':
			return None
		pkt_len = int.from_bytes(pkt_len, byteorder='big')
		nbytes=0
		chunks=[]
		while nbytes < pkt_len:
			chunk = self.socket.recv(min(pkt_len - nbytes, 2048))
			if chunk == b'':
				return None
			chunks.append(chunk)
			nbytes += len(chunk)
		return b''.join(chunks)


class Setting(object):
	"""Settings collection object"""
	def __init__(self, name, values, current=None):
		super(Setting, self).__init__()
		if type(name) is dict:
			self.name = list(name.keys())[0]
			self.setting_name = name[self.name]
		else:
			self.name=name
			self.setting_name=name
		self.values = [ list(x.keys())[0] if type(x) is dict else x for x in values ]
		self.setting_values = [ list(x.values())[0] if type(x) is dict else x for x in values ]
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
		self.settings.append(Setting({"Mode":"mode"},("Color","Gray",{"B/W":"Lineart"})))
		self.settings.append(Setting({"DPI":"resolution"},list(range(50,601,50)),500))
		self.settings.append(Setting({"Sides":"source"},({1:"ADF Front"},{2:"ADF Duplex"}),2))
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

class ProgressPage(object):
	"""Displays in-progress scan info, and actions"""
	def __init__(self):
		super(ProgressPage, self).__init__()
		self.pages=[]
		self.proggy = loadfont("ProggyTiny.ttf",12)
		self.sidebar = Sidebar(15)
		
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

		self.sidebar.draw(c,d,self)

		x,y=5,5
		xsep=20
		ysep=20
		for i,p in enumerate(self.pages):
			if p == "b":
				x -= xsep
				document(c,x,y+ysep,i+1,backside=True)
			else:
				document(c,x,y,i+1)
			x += xsep
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

	def listen(self, cb):
		SCAN_BTN=16
		menu_btns = [b for b in self.buttons if b.pin != SCAN_BTN]
		self.cb = cb
		logging.debug("enabling buttons")
		for b in menu_btns:
			b.listen(self.button_press)
		logging.debug("waiting for scan button")
		GPIO.wait_for_edge(SCAN_BTN, GPIO.FALLING)
		logging.debug("scan button pressed")
		logging.debug("disabling buttons")
		for b in menu_btns:
			b.stop_listening()
		self.cb("scan")

	def button_press(self,pin):
		if self.screen.is_asleep():
			self.screen.on()
			return
		if pin == 11:
			self.cb("up")
		elif pin == 13:
			self.cb("down")
		elif pin == 15:
			self.cb("enter")
		"""
		elif pin == 16:
			# SCAN

			# note: the following crashes on Pi Zero
			#for b in self.buttons:
			#	b.stop_listening()
			self.screen.draw_scan()
		"""

class Keys_Interface(object):
	"""Keyboard interface for interacting via terminal (e.g. desktop testing)"""
	def __init__(self):
		super(Keys_Interface, self).__init__()
		import termios
		self.old_term_stg = termios.tcgetattr(sys.stdin.fileno())
		atexit.register(self.cleanup)

	def cleanup(self):
		import termios
		termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.old_term_stg)

	def listen(self, cb):
		import tty, termios
		try:
			tty.setraw(sys.stdin.fileno())
			ch = sys.stdin.read(1)
			if ch == "\x1b":
				ar = sys.stdin.read(2)
				ch = ch+ar
		finally:
			termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.old_term_stg)
		
		if ch == "\x1b[A":
			cb("up")
		elif ch == "\x1b[B":
			cb("down")
		elif ch == "\r":
			cb("enter")
		elif ch == " ":
			cb("scan")
		elif ch == "\x03":
			raise KeyboardInterrupt


class IO_Mgr(object):
	"""Manager for a collection of buttons"""
	def __init__(self, interface, screen, menu):
		super(IO_Mgr, self).__init__()
		self.buttons=[]
		self.interface = interface
		self.screen=screen
		self.menu = menu

	# called as callback from server scanner.run, server comms
	# return true to exit scanner running
	def handle_status(self):
		progress = ProgressPage()
		def response(msg):
			msg,*args = msg.split(":",maxsplit=1)
			msg = msg.strip()
			if msg == "error":
				self.screen.draw_err(*args)
			elif msg == "pages end":
				self.screen.draw_complete()
			elif msg == "empty scan":
				self.screen.draw_empty()
			else:
				self.screen.draw_progress(progress, msg)
		return response


	def listen(self):
		while True:
			self.interface.listen(self.button_press)

	def button_press(self,action):
		if self.screen.is_asleep():
			self.screen.on()
			return
		if action == 'up':
			self.menu.up()
			self.screen.draw_menu(self.menu)
		elif action == 'down':
			self.menu.down()
			self.screen.draw_menu(self.menu)
		elif action == 'enter':
			self.menu.enter()
			self.screen.draw_menu(self.menu)
		elif action == 'scan':
			self.screen.draw_scan()
			try:
				scanner = Scanner()
			except ConnectionRefusedError:
				logging.debug("could not connect to scingest")
				self.screen.draw_err("couldn't find server")
				time.sleep(2)
				self.screen.draw_menu(self.menu)
			else:
				settings = {}
				for s in self.menu.settings:
					logging.debug("setting {} = {}".format(s.setting_name,s.setting_values[s.index()]))
					settings[s.setting_name] = s.setting_values[s.index()]
				scanner.run(settings,self.handle_status())
				scanner.cleanup()


def cleanup_at_exit():
	signal(SIGTERM, lambda signum, stack_frame: sys.exit(1))
	signal(SIGINT, lambda signum, stack_frame: sys.exit(1))

def main():
	cleanup_at_exit()
	pins=(11,13,15,16)
	menu = Menu()
	screen = Screen(menu)
	interface = Button_Interface(pins) if is_pi() else Keys_Interface()
	io = IO_Mgr(interface, screen, menu)
	io.listen()

if __name__ == "__main__":
	main()
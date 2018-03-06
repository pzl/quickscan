import json
import socket
import time
import logging
import random

logging.basicConfig(level=logging.DEBUG,format="%(asctime)s %(levelname)7s : %(message)s")


def sendjson(sock, obj):
	return send(sock,json.dumps(obj))
def send(sock, s):
	bindata = s.encode('utf8')
	msglen = len(bindata).to_bytes(4, byteorder='big')
	sock.send(msglen+bindata)

def recv(sock):
	pkt_len = sock.recv(4)
	if pkt_len == b'':
		return None
	pkt_len = int.from_bytes(pkt_len, byteorder='big')
	nbytes=0
	chunks=[]
	while nbytes < pkt_len:
		chunk = sock.recv(min(pkt_len - nbytes, 2048))
		if chunk == b'':
			return None
		chunks.append(chunk)
		nbytes += len(chunk)
	return b''.join(chunks)


def handle_conn(sock, addr):
	logging.debug("got connection from {}".format(addr))
	init = json.loads(recv(sock).decode('utf8'))
	cmd = init['scan']
	opts = init['options']
	logging.debug('got SCAN command: {}, options: {}'.format(cmd,opts))

	if opts['mode'] == 'Color':
		logging.debug('simulating a normal scan')
		normal_scan(sock)
	elif opts['mode'] == 'Gray':
		logging.debug('simulating empty paper tray')
		empty_scan(sock)
	else:
		logging.debug('simulating an error')
		error_scan(sock)

	logging.debug('connection finished')
	sock.close()



def normal_scan(sock):
	side="f"
	for i in range(random.randint(2,10)):
		send(sock, "feed start")
		time.sleep(3 if side == "f" else 0.5)
		send(sock, "page fed" if side == "f" else "backside")
		time.sleep(0.5)
		send(sock, "PAGE {}".format(i+1))
		if side == "b":
			side = "f"
		else:
			side = random.choice(["f","b"])
	send(sock, "feed start")
	send(sock, "pages end")


def empty_scan(sock):
	send(sock, "feed start")
	send(sock, "pages end")
	send(sock, "empty scan")

def error_scan(sock):
	send(sock, "feed start")
	send(sock, "error:Document feeder jammed")

if __name__ == "__main__":
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	bound=False
	while not bound:
		try:
			s.bind(('',5555))
		except OSError:
			logging.info("Socket in use, trying again")
			time.sleep(1)
		else:
			bound=True	
	logging.debug("server listening")
	s.listen(5)
	while True:
		handle_conn(*s.accept())
	s.close()
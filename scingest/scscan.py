import json
import socket

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

if __name__ == "__main__":
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.connect(("localhost",5555))

	sendjson(s,{
		"scan":True,
		"options": {
			"resolution": 400
		}
	})


	msg = recv(s)
	while msg is not None:
		print(msg.decode('utf8'))
		msg = recv(s)
	s.close()


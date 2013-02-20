import gevent
from gevent import socket
from metropsrv import DgramServer



# this handler will be run for each incoming connection in a dedicated greenlet
def echo(msg, address):
    print 'New message from %s:%s' % (msg, address)



if __name__ == '__main__':
    # to make the server use SSL, pass certfile and keyfile arguments to the constructor
    udp_sock = gevent.socket.socket(gevent.socket.AF_INET, gevent.socket.SOCK_DGRAM)
    udp_sock.setsockopt(gevent.socket.SOL_SOCKET, gevent.socket.SO_BROADCAST, 1)
    udp_sock.bind(('127.0.0.1', 6000))
    server = DgramServer(udp_sock, echo)
    # to start the server asynchronously, use its start() method;
    # we use blocking serve_forever() here because we have no other jobs
    print 'Starting echo server on port 6000'
    server.serve_forever()

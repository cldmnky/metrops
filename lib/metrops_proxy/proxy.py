import gevent
import struct
from ZEO import ClientStorage
from ZODB import DB
import transaction
from gevent import socket
from metrops_udp import DgramServer
from collectd_parser import *
import logging
# Set up logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(msg)s")
logger = logging.getLogger(__file__)

TYPE_SIGN_SHA256     = 0x0200
TYPE_ENCR_AES256     = 0x0210
header = struct.Struct("!2H")
username_len = struct.Struct("!H")

addr = 'localhost', 8090
storage = ClientStorage.ClientStorage(addr)
db = DB(storage)
conn = db.open()
root = conn.root()

def get_collectd_dest(instance):
    conn.sync()
    if root['instances'].has_key(instance):
        return root['instances'][instance]['dest']
    else:
        return False

# this handler will be run for each incoming connection in a dedicated greenlet
def proxy(msg, address):
    off = 0
    ptype, plen = header.unpack_from(msg, off)
    if ptype == 528:
        off = header.size
        ulen = username_len.unpack_from(msg, off)[0]
        uname = struct.Struct("!%ss" % ulen)
        off = header.size + username_len.size
        u = uname.unpack_from(msg, off)
        # Resend message if user matches a known user
        dest_address = get_collectd_dest(u[0])
        if dest_address:
            sock = socket.socket(type=socket.SOCK_DGRAM)
            sock.connect(dest_address)
            sock.send(msg)
            logger.debug("Proxied collectd metric from %s to %s"  % (u[0], dest_address))
        else:
            logger.debug("Dropping collectd metric due to unknown instance")
    else:
        logger.debug("Dropping collectd message due to unkown type")


def run(configfile):
    #addr = 'localhost', 8090
    #storage = ClientStorage.ClientStorage(addr)
    #db = DB(storage)
    #conn = db.open()
    #root = conn.root()
    #root['_v_stats'] = {}
    #transaction.commit()
    udp_sock = gevent.socket.socket(gevent.socket.AF_INET, gevent.socket.SOCK_DGRAM)
    udp_sock.setsockopt(gevent.socket.SOL_SOCKET, gevent.socket.SO_BROADCAST, 1)
    udp_sock.bind(('', 6000))
    server = DgramServer(udp_sock, proxy)
    # to start the server asynchronously, use its start() method;
    # we use blocking serve_forever() here because we have no other jobs
    print 'Starting metricops server on port 6000'
    server.serve_forever()

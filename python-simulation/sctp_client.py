#!/usr/bin/python3
# script that can test that it is possible to send a sc

import socket
import sctp
import time

#sk = sctp.sctpsocket_tcp(socket.AF_INET)
#sk.connect(("127.0.0.1", 36412))
addr_server = ("127.0.0.1", 36412)
addr_client = ("127.0.0.1", 10002)

cli = sctp.sctpsocket_tcp(socket.AF_INET)
# config SCTP number of streams
cli.initparams.max_instreams = 3
cli.initparams.num_ostreams = 3
# disable SCTP events
cli.events.clear()
cli.events.data_io = 1
#
cli.bind(addr_client)
cli.connect(addr_server)
#
buf = b"TEST MESSAGE\n\l"
cli.sctp_send(buf)

print("Sending Message")
time.sleep(0.01)
cli.sctp_send(buf)

cli.close()


#sk.close()


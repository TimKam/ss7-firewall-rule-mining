#!/usr/bin/python3

## SCTP server that can handle multiple of clients in parallel
# The server stores the events when a client is accepted and when conneciton to a client is lost.
# These events are stored in a file using logger
# use --help to see the input argument

import socket
import sctp
import argparse
import threading
import logging
import sys

client_dict = dict()

# Handles an incoming connection from a client
# @param[in] client_socket  The socket to the client
# @param[in] client_addr    The address to the client
def handle_client(client_socket, client_addr):         
    global client_dict
    logger.info("Call from {0}:{1}".format(client_addr[0], client_addr[1]))

    if client_addr not in client_dict:
        client_dict[client_addr] = 0
    try:
        while True:
            data = client_socket.recv(999)
            if data:
                # output received data

                client_dict[client_addr] += 1
                #print ("Data: %s" % data)
                #connection.sendall("We recieved " + str(len(data)) + " bytes from you")
            else:
                # no more data -- quit the loop
                logger.info("no more data. Received {0} packets for client {1}:{2}".format( client_dict[client_addr], client_addr[0], client_addr[1]))
                break
    finally:
        # Clean up the connection
        client_socket.close()   
    
## starts the sctp server, the server will listen for a incoming connection.
# When there is a incoming connection the server will start a new thread that handles the connection
# @param[in] listen_port    the port number that the server will listen on
# @param[in] num_conn       The maximum number of clients that the server can handle at the same time
#
def start_server(listen_port, num_conn):
    server_ip = '127.0.0.1'
    client_dict = dict()

    my_tcp_socket = sctp.sctpsocket_tcp(socket.AF_INET)          
    pkt_count = 0

    # Let's set up a connection:                                            
    my_tcp_socket.events.clear()
    my_tcp_socket.bind((server_ip, listen_port))
    my_tcp_socket.listen(num_conn)
    
    while True:  
        # wait for a connection and start a thread to handle the connection
        client, client_addr   = my_tcp_socket.accept()                                                     
        print("Call from {0}:{1}".format(client_addr[0], client_addr[1]))
        client_handler = threading.Thread(target = handle_client, args = (client,client_addr))
        client_handler.start()


if __name__ == '__main__':
    #start logger
    LOG_FILE = "log_sctp_server.log"
    logger = logging.getLogger('log_upd_server')
    logger.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    fh = logging.FileHandler(LOG_FILE, mode='w')
    fh.setLevel(logging.DEBUG)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    fh.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.info("starting")

    parser = argparse.ArgumentParser(description='SCTP server')
    parser.add_argument('--port', metavar='<sctp server port>', type=int,
                        help='server port (0-65536)', default=36412)
    parser.add_argument('--conn', metavar='<number of allowed connections>', type=int,
                        help='The number of allowed connections, which is also the number of threads that can work in parallel', default=500)

    args = parser.parse_args()
    listen_port = args.port
    num_conn = args.conn

    start_server(listen_port, num_conn)



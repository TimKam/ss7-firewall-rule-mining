#!/usr/bin/python3

# UDP server that receives packets on a specified port, start the server before running the clients
# For each packet received a line is written to a file log. The line contains, timestamp size of the packet received and the client_id
# The data sent to the server must contain the client_id followed by : in the beginning of the data (client_id:data)
# The log is overwritten each run (could easily be changed if a timestamp is added to the logfile name)

import socket
import time
import logging

# Here we define the UDP IP address as well as the port number that we have
# already defined in the client python script.
UDP_IP_ADDRESS = "127.0.0.1"
UDP_PORT_NO = 6789
num_rec_msg = 0
LOG_FILE = 'log_udp_server.log'
MAX_SIZE_MESSAGE = 1024

if __name__ == "__main__":
    #start logger
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

    # declare our serverSocket upon which
    # we will be listening for UDP messages
    serverSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    serverSock.bind((UDP_IP_ADDRESS, UDP_PORT_NO))

    while True:
        data, addr = serverSock.recvfrom(MAX_SIZE_MESSAGE)
        client_id, message = data.split(":", 1)
        logger.info(client_id +" "+str(len(data)))
        #print "id: ", client_id," Data: ",message," addr: ", addr
        num_rec_msg = num_rec_msg +1


#!/usr/bin/python3

# UDP client generator, The generator tries to keep a specified number of clients active sending udp data to a udp server. 
# When a client is started the generator randomly chooses a model to use for the client. 
# The model contains information about the size of the packets that should be sent,
# number of packets to send before the client ends and how many packets per minute the client should send.
# The NUM_SEONDS_TO_RUN specifies how many seconds that the generator should run

import socket
import time
import threading
import logging
import string
import random
import os

# tests give that maximum speed on virtual env is 0.5 Gbps and about 45000 packets per sec

LOG_FILE = 'log_udp_generator.log'
# Below are some models for the client listed, the arrays contains:
# size packet (bytes), num packets to sned, packets/min
m0 = [3, 2, 60]
m1 = [30, 10000, 100]
m2 = [100, 20000, 200]
m3 = [15, 5000, 300]
m4 = [50, 10000, 120]
m5 = [300, 10000, 200]

all_models = [m1,m2,m3,m4,m5]
#all_models = [m0]
list_of_clients = []
NUM_SECONDS_TO_RUN = 10*1  # specifies the time that this script will run

# Returns a randomized string with a specified length
def randomString(stringLength=10):
    #"""Generate a random string of fixed length """
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(stringLength))

# The client functionality, sends a specified number of packets and then ends
def udp_client_create(client_id,packet_size, num_packets_to_send, packets_per_min):
    UDP_IP_ADDRESS = "127.0.0.1"
    UDP_PORT_NO = 6789
    Message = format(client_id) +":" +randomString(packet_size)
   # Message = '{}:'.randomString(packet_size).format(client_id)

    packets_sent = 0
    sleep_time_sec = 60 /packets_per_min
    #min 1 ms
    if sleep_time_sec < 0.001:
        sleep_time_sec = 0.001

    clientSock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while packets_sent < num_packets_to_send:
        clientSock.sendto(Message, (UDP_IP_ADDRESS, UDP_PORT_NO))
        time.sleep(sleep_time_sec)
        packets_sent = packets_sent + 1

# starts a client
def start_client(client_id,model):
    global list_of_clients
    client = threading.Thread(target=udp_client_create, args=(client_id,model[0],model[1],model[2],))
    client.start()
    list_of_clients.append(client)


if __name__ == "__main__":
    logger = logging.getLogger('log_upd_generator')
    logger.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    fh = logging.FileHandler(LOG_FILE, mode='w')
    fh.setLevel(logging.DEBUG)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)

    num_models = len(all_models)
    num_packets_to_send = 0
    NUM_CLIENTS = 2
    SLEEP_TIME_ENOUGH_CLIENTS = 0.1
    client_id = 0

    start_time = time.time()
    TIME_LEFT = True

    # Loop tries to keep specified number of clients active, sleeps a short time if there is enough of clients
    while TIME_LEFT:
        num_active_threads = threading.active_count() - 1 #remove main thread (this)
        if num_active_threads < NUM_CLIENTS:
            num_clients_to_start = NUM_CLIENTS - num_active_threads
            for i in range(0,num_clients_to_start):
                model_num = random.randrange(num_models)
                model_chosen = all_models[model_num]
                num_packets_to_send = num_packets_to_send + model_chosen[1]
                start_client(client_id,model_chosen)
                client_id = client_id + 1
        else:
            time_now = time.time()
            if time_now - start_time > NUM_SECONDS_TO_RUN:
                print "Times up! " + str(NUM_SECONDS_TO_RUN) +" sec has now passed, exiting..."
                TIME_LEFT = False
                os._exit(1)
            else:
                time.sleep(SLEEP_TIME_ENOUGH_CLIENTS)


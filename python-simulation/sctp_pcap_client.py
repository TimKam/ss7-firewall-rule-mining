#!/usr/bin/python3

## SCTP client generator, uses pcap files to start multipls sctp clients that reads the pcap files and send the packets in the pcap file to a specified server
# The client generator will run for a specified number of seconds and will try to keep a number of clients rnning in parallel.
# usage: use --help to see the input arguments

import socket
import sctp
import argparse
import os
import time
import sys
from scapy.all import rdpcap, Ether, IP, SCTP, SCTPChunkData, wrpcap, hexdump
import threading
import glob
import random

LOG_FILE = 'log_sctp_generator.log'
list_of_clients = []

# starts a client
# @param[in] file_name  name of the pcap file to use when sending data
# @param[in] stream_id  The id of the stream
# @param[in] src_port   the src port to use when sending sctp messages
# @param[in] dst_port   The server port to connect to
def start_client(file_name, stream_id, src_port, dst_port):
    global list_of_clients
    global clients_started
    client_id = clients_started
    client = threading.Thread(target=pcap_parse_send, args=(client_id,file_name, stream_id, src_port, dst_port))
    client.start()
    list_of_clients.append(client)
    clients_started += 1


## parses the pcap file containing sctp packets
# for each packet it sends a packet to the sctp server
# the time in the pcap file will be used to mimic a delay between each message
#
# @param[in] client_id      id of the clint performing the parsing and sending
# @param[in] file_name      name of the pcap file to parse
# @param[in] stream_id      sctp stream id to use (some bug makes it only possible to specify id between 0-9
# @param[in] src_port       the port that the sctp message will be sent from
# @param[in] dst_port       the port of the sctp server to which the messages will be sent
def pcap_parse_send(client_id,file_name, stream_id, src_port, dst_port):
    pcap = rdpcap(file_name)
    packets_sent_count = 0
    count = 0
    time_to_wait = 0
    

    sk = sctp.sctpsocket_tcp(socket.AF_INET)
    sk.bind(('', src_port))
    sk.connect(("127.0.0.1", dst_port))
    sctp_count = 0

    for pkt in pcap:
        count += 1        
        ip = pkt['IP']
        layer = ip.payload
        pkt_time = pkt.time
        # wait until packet should be sent according to pcap file
        if count > 1:
            diff_time = pkt_time - last_pkt_time
            time.sleep(diff_time)
        while layer.name != 'NoPayload':
            if layer.name == 'SCTP':
                sctp_count += 1
            if layer.name == 'SCTPChunkData':
                packets_sent_count += 1 
                sctpDataPkt = SCTPChunkData(reserved=0, delay_sack=0, unordered=0, beginning=1, ending=1, stream_id=layer.stream_id, proto_id=layer.proto_id, stream_seq=layer.stream_seq, tsn=layer.tsn, data=layer.data)
                sk.sctp_send(msg=sctpDataPkt.data,ppid=0x03000000,flags=0, stream=stream_id)
                last_pkt_time = pkt_time

            layer = layer.payload
    
    print('{} contains {} packets ({} interesting)'.
          format(file_name, count, packets_sent_count))
    sk.shutdown(0)
    sk.close()

## returns a list with all files in the directory
# @param[in] file_dir   directory conatining pcap files
# @param[out] a list of files in the given directory
def getPcapFilesInDir(file_dir):
    return glob.glob(file_dir +"/*.pcap")


## main function
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SCTP pcap client creator')
    #parser.add_argument('--stream', metavar='<sctp stream id>', type=int,
    #                    help='id of the sctp stream (0-9)', default=0)
   # parser.add_argument('--sport', metavar='<sctp src port>', type=int,
    #                    help='src port (0-65536)', default=12345)
    parser.add_argument('--dport', metavar='<sctp dst port>', type=int,
                        help='server port (0-65536)', default=36412)
    parser.add_argument('--dir', metavar='<pcap file dir>', type=str,
                        help='each client shooses an pcap file in the directory given', required=True)
    parser.add_argument('--num_clients', metavar='<number of clients>', type=int,
                        help='Number of parallel sctp clients that this script will try to keep running', default=5)
    parser.add_argument('--sec_to_run', metavar='<number of seconds to run>', type=int,
                        help='The client generator will try to run the specified number of clients for this time', default=30)

    args = parser.parse_args()
    #file_name = args.pcap
    #stream_id = args.stream
    #src_port = args.sport
    src_port = 10000
    stream_id = 0
    dst_port = args.dport

    pcap_dir = args.dir
    sec_to_run = args.sec_to_run
    num_clients = args.num_clients
    pcap_files = getPcapFilesInDir(pcap_dir)
   
    clients_started = 0
    SLEEP_TIME_ENOUGH_CLIENTS = 0.1
    MAX_SRC_PORT = 65536
    
    #if not os.path.isfile(file_name):
    #    print(format(file_name)," does not exist")
    #    sys.exit(-1)
    TIME_LEFT = True
    start_time = time.time()    

    while TIME_LEFT:
        num_active_threads = threading.active_count() - 1 #remove main thread (this)
        if num_active_threads < num_clients:
            num_clients_to_start = num_clients - num_active_threads
            for i in range(0,num_clients_to_start):
                pcap_file = random.choice(pcap_files)
                src_port += 1
                if src_port > MAX_SRC_PORT:
                    src_port = 0
                print("starting client with pcap file: ",pcap_file, " and src_port: ",src_port)
                start_client(pcap_file, stream_id, src_port, dst_port)

        else:
            time_now = time.time()
            if time_now - start_time > sec_to_sun:
                print("Times up! " + str(sec_to_run) +" sec has now passed, exiting...")
                #for client in list_of_clients:
                # TODO kill thread
                    
                TIME_LEFT = False
                os._exit(1)
            else:
                time.sleep(SLEEP_TIME_ENOUGH_CLIENTS)

    sys.exit(0)


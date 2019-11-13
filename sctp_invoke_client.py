#!/usr/bin/python3

## SCTP client generator, uses a json file to create clients that send invoke update requests to the sctp server
# Each client uses a list with time stamps and zones to simulate that they are moving through a landscape with
# Mobile Switching Centers (MSC)
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
import copy
import json

LOG_FILE = 'log_sctp_generator.log'
list_of_clients = []

## read a json list which contains a list of zones and their corresponding msc and vlr
#
# @param[out] zone_dict dictionary that contains all zones with corresponding msc and vlr, key to list is the zone id 
#
def getZoneDict():
    zone_dict = dict()
    with open('msc.json') as json_file:
        data = json.load(json_file)
        for zone in data['zones']:
            #first element in dictionary item is msc and the second vlr
            zone_dict[zone['id']] = bytes.fromhex(zone['msc']),bytes.fromhex(zone['vlr'])
    return zone_dict

## Reads a json file containing movement in a grid world
# the list is stored as a list of agents where each agent has a list of 
# movements containing zone id and time to be in each zone
#
# @param[out] agent_list    list of agents, each agent has a list of movements which contains zone id and time to stay in each zone
#
def getAgentList():
    with open('walk.json') as json_file:
        data = json.load(json_file)
        zones_list = data['zones']
        log_list = data['log']
        agent_list = []

        for log in log_list:

            #print('time: ' + log['time'])
            agents = log['agents']
            #for agent in agents:
            #    print("agent id: ", agent['id'], agent['zone'])

    #TODO add real list
    agent_list.append([[1,5],[2,4]])
    agent_list.append([[2,10],[1,5]])
    return agent_list

## starts a client on a new thread
# @param[in] agent_id   The id of the agent, is used to fetch data for the agent
# @param[in] layer  The data that shall be sent for the invoke client
# @param[in] src_port   the src port to use when sending sctp messages
# @param[in] dst_port   The server port to connect to
#
def start_client(agent_id, layer, src_port, dst_port):
    global list_of_clients
    client = threading.Thread(target=invokeClient, args=(agent_id, layer, src_port, dst_port))
    client.start()
    list_of_clients.append(client)

## reads a invokeUpdate packet from a pcap file and returns the sctpChunkData
# @param[out] layer     the sctpChunkData from the packet
#
def getInvokeUpdatePacket():
    invoke_file = "invokeUpdate.pcap"
    if not os.path.isfile(invoke_file):
        print(format(invoke_file)," does not exist")
        sys.exit(-1)

    pcap = rdpcap(invoke_file)
    pkt = pcap[0]
    ip = pkt['IP']
    layer = ip.payload
    while layer.name != 'NoPayload':
        if layer.name == 'SCTPChunkData':
            break

        layer = layer.payload
    return layer

## updates the imsi, msc and vlr in the packet
# the packet is a byte array so it is mutable, which means that it is impossible to change specific bytes
# This means that we need to join parts to create a new packet
# @param[in] imsi   imsi number
# @param[in] msc    the Mobile Switching Center number
# @param[in] vlr    The visitor Location Registry
# @param[in] data   The input data
# @param[out] data  The changed packet
#
def updateImsiVlrMscInPacket(imsi, vlr, msc, data):
    start_imsi = 108 #in this particular packet the imsi starts at 108
    len_msc_vlr = 6
    data = data[0:start_imsi]+imsi + data[start_imsi+8:start_imsi + 10] \
            + msc + data[start_imsi + 16:start_imsi + 18] \
            +vlr + data[start_imsi + 18 + len_msc_vlr:]
    #data = data[0:start_imsi + 10] + msc + data[start_imsi + 16:start_imsi + 18] + vlr + data[start_imsi + 18 + len_msc_vlr:]

    return data

## A sctp client sending invoke update packets is started
# @param[in] agent_id   an id that is used to fecth agent information
# @param[in] layer      the sctp chunk data
# @param[in] src_port   the sctp src port that is used when sending messages to the server
# @param[in] dst_port   the port of the sctp server
#
def invokeClient(agent_id, layer, src_port, dst_port):
    global agent_list
    global zone_dict
    sk = sctp.sctpsocket_tcp(socket.AF_INET)
    sk.bind(('', src_port))
    sk.connect(("127.0.0.1", dst_port))
    sctp_count = 0
    index = 0
    stream_id = 0
    imsi = bytes.fromhex(imsi_dict[str(agent_id)])
    agent_list_data = agent_list[agent_id]

    sctpDataPkt = SCTPChunkData(reserved=0, delay_sack=0, unordered=0, beginning=1, ending=1, stream_id=layer.stream_id, proto_id=layer.proto_id, stream_seq=layer.stream_seq, tsn=layer.tsn, data=layer.data)

    for zone_time in agent_list_data:
        zone_id = zone_time[0]
        time_sec = zone_time[1]
        msc = zone_dict[str(zone_id)][0]
        vlr = zone_dict[str(zone_id)][1]
        sctpDataPkt.data = updateImsiVlrMscInPacket(imsi, vlr, msc, sctpDataPkt.data)
        sk.sctp_send(msg=sctpDataPkt.data,ppid=0x03000000,flags=0, stream=stream_id)
        time.sleep(time_sec)

## returns an dictionary containing the imsi number, if the file containing the imsi
# numbers doesn't exist, the file is created. the key to the imsi dictionary is the agent id
# @param[out] imsi_dict an dictionary of imsi number where the key is the agent id
#
def getImsiDict():
    IMSI_FILE = "imsi.json"
    imsi_dict = dict()
     # if no imsi file exist, then generate a new imsi with 1000 unique imsi
    if not os.path.isfile(IMSI_FILE):
        for i in range(0,1000):
            imsi = 54046001073104 + i
            imsi_dict[str(i)] = str(imsi) + "f0"  #15 digits, the f will not be used
            with open('imsi.json', 'w') as fp:
                json.dump(imsi_dict, fp)
    else:
        with open(IMSI_FILE) as json_file:
            imsi_dict = json.load(json_file)
        
    return imsi_dict


## main function
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SCTP pcap client creator')
    parser.add_argument('--dport', metavar='<sctp dst port>', type=int,
                        help='server port (0-65536)', default=36412)
    parser.add_argument('--num_clients', metavar='<number of clients>', type=int,
                        help='Number of parallel sctp clients that this script will try to keep running', default=5)
    parser.add_argument('--sec_to_run', metavar='<number of seconds to run>', type=int,
                        help='The client generator will try to run the specified number of clients for this time', default=20)

    args = parser.parse_args()
    src_port = 10000
    stream_id = 0
    dst_port = args.dport

    sec_to_run = args.sec_to_run
    num_clients = args.num_clients
   
    clients_started = 0
    SLEEP_TIME_ENOUGH_CLIENTS = 1
    MAX_SRC_PORT = 65536
    layer = getInvokeUpdatePacket()

    TIME_LEFT = True
    start_time = time.time()    
    agent_id = 0

    agent_list = getAgentList()
    zone_dict = getZoneDict()
    num_agents = len(agent_list)
    print("number of agents: ", num_agents)

    imsi_dict = getImsiDict()
 
    while TIME_LEFT:
        if agent_id < num_agents:
            src_port += 1
            if src_port > MAX_SRC_PORT:
                src_port = 0
            print("starting agent id: ",agent_id, " and src_port: ",src_port)

            start_client(agent_id, copy.copy(layer), src_port, dst_port)
            agent_id += 1

        else:
            time_now = time.time()
            if time_now - start_time > sec_to_run:
                print("Times up! " + str(sec_to_run) +" sec has now passed, exiting...")
                #for client in list_of_clients:
                # TODO kill thread
                    
                TIME_LEFT = False
                os._exit(1)
            else:
                time.sleep(SLEEP_TIME_ENOUGH_CLIENTS)

    sys.exit(0)


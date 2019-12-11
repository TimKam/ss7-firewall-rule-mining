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
import enum

LOG_FILE = 'log_sctp_generator.log'
list_of_clients = []

class AttackEnum(enum.Enum): 
    invoke = 1 
    dod = 2

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
# @param[out] agent_list    list of agents, each agent has a list of movements which contains zone ids
#
def getAgentList():
    with open('walk2.json') as json_file:
        data = json.load(json_file)
        zones_list = data['zones']
        agent_list = data['clients']
    
    return agent_list

## Reads a json file containing movement in a grid world
# the list is stored as a list of agents where each agent has a list of 
# movements containing zone id and time to be in each zone
# This list contains the msc and vlr in which the invoke attacker is present in
#
# @param[out] agent_list    list of attack agents, each agent has a list of movements which contains zone ids
#
def getAttackAgentList(file_name):
    with open(file_name) as json_file:
        data = json.load(json_file)
        agent_list = data['clients']
    
    return agent_list


## starts a client on a new thread
# @param[in] agent_id   The id of the agent, is used to fetch data for the agent
# @param[in] layer  The data that shall be sent for the invoke client
# @param[in] src_port   the src port to use when sending sctp messages
# @param[in] dst_port   The server port to connect to
#
def startClient(agent_id, layer, src_port, dst_port, agent_walk):
    global list_of_clients
    client = threading.Thread(target=invokeClient, args=(agent_id, layer, src_port, dst_port, agent_walk))
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
# @param[in] agent_walk A list of movement through msc zones

#
def invokeClient(agent_id, layer, src_port, dst_port, agent_walk):
    global zone_dict

    sk = sctp.sctpsocket_tcp(socket.AF_INET)
    sk.bind(('', src_port))
    sk.connect(("127.0.0.1", dst_port))
    sctp_count = 0
    index = 0
    stream_id = 0
    imsi = bytes.fromhex(imsi_dict[str(agent_id)])
    sctpDataPkt = SCTPChunkData(reserved=0, delay_sack=0, unordered=0, beginning=1, ending=1, stream_id=layer.stream_id, proto_id=layer.proto_id, stream_seq=layer.stream_seq, tsn=layer.tsn, data=layer.data)
    prev_msc = bytes.fromhex("000000")

    for position in agent_walk["positions"]:
        msc = zone_dict[position][0]
        vlr = zone_dict[position][1]
        #only send packet if msc changes, its only then an invoke update request is needed
        if prev_msc != msc:
            sctpDataPkt.data = updateImsiVlrMscInPacket(imsi, vlr, msc, sctpDataPkt.data)
            sk.sctp_send(msg=sctpDataPkt.data,ppid=0x03000000,flags=0, stream=stream_id)
            prev_msc = msc
        
        time_sec = 1 #hard coded at the moment
        time.sleep(time_sec)

## A sctp attack client sending invoke update packets is started, 
# the client will wait with the attack until the time sent in
# @param[in] agent_id       an id that is used to fecth agent information
# @param[in] layer          the sctp chunk data
# @param[in] src_port       the sctp src port that is used when sending messages to the server
# @param[in] dst_port       the port of the sctp server
# @param[in] agent_walk     A list of movement through msc zones
# @param[in] time_for_attack    The time the attack should occur (unix epoc)
#
def invokeClientAttack(agent_id, layer, src_port, dst_port, agent_walk, time_for_attack):
    global zone_dict

    sk = sctp.sctpsocket_tcp(socket.AF_INET)
    sk.bind(('', src_port))
    sk.connect(("127.0.0.1", dst_port))
    sctp_count = 0
    index = 0
    stream_id = 0
    imsi = bytes.fromhex(imsi_dict[str(agent_id)])
    sctpDataPkt = SCTPChunkData(reserved=0, delay_sack=0, unordered=0, beginning=1, ending=1, stream_id=layer.stream_id, proto_id=layer.proto_id, stream_seq=layer.stream_seq, tsn=layer.tsn, data=layer.data)
    prev_msc = bytes.fromhex("000000")
    
    time_before_attack = time_for_attack - time.time()
    if time_before_attack > 0:
        time.sleep(time_before_attack)
    else:
        print("no time before attack, time overdue: ", time_before_attack)

    for position in agent_walk["positions"]:
        msc = zone_dict[position][0]
        vlr = zone_dict[position][1]
        #only send packet if msc changes, its only then an invoke update request is needed
        if prev_msc != msc:
            sctpDataPkt.data = updateImsiVlrMscInPacket(imsi, vlr, msc, sctpDataPkt.data)
            sk.sctp_send(msg=sctpDataPkt.data,ppid=0x03000000,flags=0, stream=stream_id)
            prev_msc = msc
        

## Starts an attack after a random amount of time
#
# @param[in] attack     kind of attack (invoke, dod...)
# @param[in] layer      the sctp chunk data that will be sent
# @param[in] src_port   the sctp src port that is used when sending messages to the server
# @param[in] dst_port   the port of the sctp server

def launchAttack(attack, layer, src_port, dst_port):
    wait_attack = random.randint(5,10)
    print("attack will occur after ", wait_attack, " sec.")
    #This is the time the attack should occur
    time_for_attack = time.time() + wait_attack

    if attack == AttackEnum.invoke.value:
        # send a invoke update request from a MSC in another network
        agent_id = 0
        agent_attack_list = getAttackAgentList('walk_invoke_attack.json')
        agent_walk = agent_attack_list[str(agent_id)]
        src_port = 60000
        
        client = threading.Thread(target=invokeClientAttack, args=(agent_id, layer, src_port, dst_port, agent_walk, time_for_attack))
        client.start()

    elif attack == AttackEnum.dod.value:
        # starts multiple clients and then at a certain time all clients starts to send data toward the server
        agent_id = 0
        agent_attack_list = getAttackAgentList('walk_dod_attack.json')
        agent_walk = agent_attack_list[str(agent_id)]
        src_port = 60000

        NUM_ATTACKERS = 1000
        for i in range(0,NUM_ATTACKERS):
            client = threading.Thread(target=invokeClientAttack, args=(agent_id, layer, src_port, dst_port, agent_walk, time_for_attack))
            client.start()
            src_port += 1



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
    parser.add_argument('--sec_to_run', metavar='<number of seconds to run>', type=int,
                        help='The client generator will try to run the specified number of clients for this time', default=20)
    parser.add_argument('--attack', metavar='<attack number>', type=int,
                        help='1 = invoke update attack', default=0)

    args = parser.parse_args()
    dst_port = args.dport
    sec_to_run = args.sec_to_run
    attack = args.attack
    
    SLEEP_TIME_ENOUGH_CLIENTS = 1
    src_port = 10000
    stream_id = 0
    clients_started = 0
    MAX_SRC_PORT = 65536
    layer = getInvokeUpdatePacket()

    TIME_LEFT = True
    start_time = time.time()    
    agent_id = 0

    agent_list = getAgentList()
    zone_dict = getZoneDict()
    num_agents = len(agent_list)
    imsi_dict = getImsiDict()

    print("number of agents: ", num_agents)

    if attack > 0:
        launchAttack(attack, copy.copy(layer), src_port, dst_port)
 
    while TIME_LEFT:
        if agent_id < num_agents:
            src_port += 1
            if src_port > MAX_SRC_PORT:
                src_port = 0
            print("starting agent id: ",agent_id, " and src_port: ",src_port)
            startClient(agent_id, copy.copy(layer), src_port, dst_port, agent_list[str(agent_id)])
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


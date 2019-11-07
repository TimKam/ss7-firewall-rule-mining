#!/usr/bin/python3

## @package m3u_pcap_parser
#  This script can be used to extract valuable information from a pcap file containing ss7 mtps signals
#  The output is stored in a file called ss7_filtered_data.pack, the output file is in msgpack format
#
#  In order to understand the structure of the ss7 messages, read ITU-T Q.713, ITU-T Q.773 and https://tools.ietf.org/html/rfc3868
# 
# Usage: m3u_pcap_parser.py --pcap <pcap_file>

import socket
import sctp
import argparse
import os
import time
import sys
import enum
from scapy.all import rdpcap, Ether, IP, SCTP, SCTPChunkData, wrpcap, hexdump
from csv import writer 
from io import StringIO
import pandas as pd
import msgpack
from scapy.all import sniff



## Use this to be able to run script with annotation added for the profiler
# run profiler: sudo kernprof -l -v m3u_pcap_parser3.py --pcap <file>
try:
    # Python 2
    import __builtin__ as builtins
except ImportError:
    # Python 3
    import builtins

try:
    builtins.profile
except AttributeError:
    # No line profiler, provide a pass-through version
    def profile(func): return func
    builtins.profile = profile

output = StringIO() #BytesIO()
csv_writer = writer(output)
output_file="ss7_filtered_data.pack"
pkt_count = chunk_count = 0


#TAG definitions
M3UA_ID = 3
PROTOCOL_DATA_TAG = 528
TCAP_BEGIN_TAG = 98
TCAP_END_TAG = 100
TCAP_CONTINUE_TAG = 101
TCAP_ABORT_TAG = 103
DIALOGUE_PORTION_TAG = 107
INFINITE_LENGTH = 128 # hex 80
COMPONENT_TAG = 108 # hex 6c
LOCAL_OP_CODE_TAG = 2
GLOBAL_OP_CODE_TAG = 6
COMP_INVOKE_TAG = 161 # hex a1
COMP_RETURN_RESULT_LAST_TAG = 162 # hex a1
COMP_RETURN_RESULT_NOT_LAST_TAG = 163 # hex a3
SEQUENCE_TAG = 48 # hex 30
TRANSFER_MESSAGE = 1
PAYLOAD_DATA = 1
CHUNK_TYPE_DATA = 0
IMSI_NOT_KNOWN_TAG = 48


class FilterTagEnum(enum.Enum): 
    stream = "stream" 
    src_port = "srcPort"
    cgGT = "cgGT"
    imsi = "imsi"
    

## Extracts the Calling/Called Global Title from the SCCP PDU
# see definitions of SCCP (Signalling Connection Control Part) in ITU-T Q.713
# SCCP includes pointers that point to called Global Title, Calling Global Title and TCAP
#
# @param[in] sccp_index     index in the m3u_data where the SCCP PDU starts
# @param[in] m3u_data       The data to search through.
# @param[out] cdGT          Called Global Title
# @param[out] cgGT          Calling Global Title
# @param[out] index_tcap    The index in the m3u_data where the TCAP PDU starts
#
@profile
def parseSCCP(sccp_index, m3u_data):
    # see definitions of pdu in ITU-T Q.713
    ptr_to_first_var = m3u_data[sccp_index + 2]
    ptr_to_sec_var = m3u_data[sccp_index + 3]
    ptr_to_third_var = m3u_data[sccp_index + 4]
    index_called_part_addr = sccp_index + 2 + ptr_to_first_var
    index_calling_part_addr = sccp_index + 3 + ptr_to_sec_var
    index_tcap =  sccp_index + 4 + ptr_to_third_var + 1 #the pointer points to the length, step one to get to the tcap_tag
    length_called_part = m3u_data[index_called_part_addr]
    length_calling_part = m3u_data[index_calling_part_addr]
    cdGT =  m3u_data[index_called_part_addr + 3:index_called_part_addr + length_called_part + 1]
    cgGT =  m3u_data[index_calling_part_addr + 3:index_calling_part_addr + length_calling_part + 1]
    
    return cdGT, cgGT, index_tcap

## Loop through an element to find special tags (list of tags)
# @param[in] index          The start index.
# @param[in] m3u_data       The data to search through.
# @param[in] max_index      Index of the end of the data.
# @param[in] tags_to_find   A list of tags to search for
# @param[out] index_tag     The index where the tag was found, set to -1 if not found 
#
@profile
def loopAndFindTag(index,m3u_data,max_index, tags_to_find):
    index_loop = index
    next_tag = m3u_data[index_loop]
    keep_search = True
    index_tag = -1
    while keep_search:
        length =  m3u_data[index_loop + 1]  #length is always one octet after tag
        index_loop += 2 #step from tag to data
        if length != INFINITE_LENGTH: #if length is infinite then there is no data for the dialogue portion, so no extra step due to length
            index_loop += length
        if index_loop >= max_index:
            break
        next_tag = m3u_data[index_loop]
        for tag in tags_to_find:
            if tag == next_tag:
                keep_search = False
                index_tag = index_loop

    return index_tag

## Function used to parse the Dialogue Portion PDU
# see definitions of Dialougue Portion in TCAP (Transaction Capabilities Application Part) in ITU-T Q.773
#
# @param[in] dial_index     Index where the Dialogue Portion starts.
# @param[in] m3u_data       The data to search through.
# @param[in] max_tcap_index Index of the end of the data.
# @param[in] tags_to_find   A list of tags to search for
# @param[out] index_tag     The index where the tag was found, set to -1 if not found 
#
@profile
def parseDialoguePortion(dial_index, m3u_data, max_tcap_index):
    #We are only interested in finding the index of the Component, so skip DialoguePortion
    index_comp = loopAndFindTag(dial_index,m3u_data,max_tcap_index, [COMPONENT_TAG])
    return index_comp

def extractImsi(imsi_orig):
    imsi = [0x0] * 8
    # for each byte switch the last and first 4 bits
    for i in range(0,8):
        test = imsi_orig[i]
        low = test & 0x0F;
        high = test >> 4;
        switched = low << 4 | high
        imsi[i] = switched
    imsi_str = ''.join('{:02x}'.format(x) for x in imsi)
    imsi_str = imsi_str[:-1] #imsi is only 15 digits, remove the last one
    return imsi_str

## Parses the Component part of TCAP PDU
# see definitions of Component in TCAP (Transaction Capabilities Application Part) in ITU-T Q.773
#
# @param[in] index_comp     index in the m3u_data where the Component PDU starts
# @param[in] m3u_data       The data to search through.
# @param[out] comp_type_tag The Component Type tag
# @param[out] comp_op_code  Component Operational Code
# @param[out] imsi          imsi number, return -1 if not found
#
# Component consists of:
#  - component portion tag, length (mandatory)
#  - Component type tag, length (Mandatory)
#  - Invoke ID Tag, length, invoke ID (Mandatory)
#  - Sequence tag, sequence length (optional for return result)
#  - operation code (mandatory for invoke, optional for return result)
#
@profile
def parseComponent(index_comp, m3u_data):
    comp_portion_tag = m3u_data[index_comp]
    comp__portion_length, extra_octets = getLength(index_comp + 1, m3u_data)
    # step forward index if more octets was used for length
    index_comp += extra_octets
    #comp__portion_length = m3u_data[index_comp + 1]
    comp_type_tag = m3u_data[index_comp + 2]
    comp_type_length, extra_octets2 = getLength(index_comp + 3, m3u_data)
    # step forward index if more octets was used for length
    index_comp += extra_octets2

    max_comp_index = index_comp + comp__portion_length + 2 +extra_octets + extra_octets2

    comp_op_code = imsi = -1
    if comp_type_tag == COMP_INVOKE_TAG or comp_type_tag == COMP_RETURN_RESULT_LAST_TAG or comp_type_tag == COMP_RETURN_RESULT_NOT_LAST_TAG:
        invoke_length = m3u_data[index_comp + 4]
        next_index = index_comp + 5 + invoke_length
        if next_index < max_comp_index:
            next_tag =  m3u_data[next_index]
            if next_tag == SEQUENCE_TAG:
                #just skip sequence
                next_index += 2
                next_tag = m3u_data[next_index]
            if next_index < max_comp_index:
                if next_tag == LOCAL_OP_CODE_TAG or next_tag == GLOBAL_OP_CODE_TAG:
                    comp_op_code = m3u_data[next_index + 2]
                    next_index += 3 #step to next tag
                    next_tag =  m3u_data[next_index]
                if next_tag == IMSI_NOT_KNOWN_TAG:
                    length = m3u_data[next_index + 3]
                    if length == 8:
                        imsi = extractImsi(m3u_data[next_index + 4:next_index + 12])

    return comp_type_tag, comp_op_code, imsi

## Returns the length of an pdu
# 
# @param[in] index          index in the m3u_data where the Component PDU starts
# @param[in] m3u_data       The data to search through.
# @param[out] length        The length of the PDU, returns -1 if the length is not specified and the first octet is then set to 80 hex
# @param[out] extra octets  If length is larger than 127 octets then an extra octet is used for the length
#
def getLength(index, m3u_data):
    length = m3u_data[index]
    extra_octets = 0
    if length == INFINITE_LENGTH: #PDU ends with end of tag instead
        length = -1
    elif length > INFINITE_LENGTH: # use next octet for length
        length = m3u_data[index+1]
        extra_octets = 1
    return length, extra_octets

## Finds the index of the Component in the TCAP PDU
#
# @param[in] index_tcap         Index in the m3u_data where the TCAP PDU starts
# @param[in] m3u_data           The data to search through.
# @param[in] num_transaction_id Number of transaction PDUs (Originating/Destination)
# @param[out] length            The length of the PDU, returns -1 if the length is not specified and the fir
# @param[out] imsi              imsi number, -1 if not found
## tcap Begin/End PDU contains:
#   - Type_tag, msg_length
#   - Originating (begin)/Destination (End) Transaction ID Tag, length and ID (could be present depending of the tcap type (begin, end, continue)
#   - Dialogue Portion (optional)
#   - Component portion Tag, length (optional)
#   - One or several components (optional)
#
@profile
def findComponentInTcap(index_tcap, m3u_data, num_transaction_id):
    #tcap_length = m3u_data[index_tcap + 1]
    tcap_length, extra_octets = getLength(index_tcap + 1, m3u_data)
    # step forward index if more octets was used for length
    index_tcap += extra_octets
    trans_length = m3u_data[index_tcap + 3]
    if num_transaction_id == 2:
        #tcap_tag(0), tcap_length(1), tag_1(2), length_1(3), id_1(4:4+l1), tag_2(4+l1), length_2(5+l1), id_2(6+l1:6+l1+l2), next_tag(6+l1+l2)
        trans_length2 = m3u_data[index_tcap + 5 + trans_length]
        next_index = index_tcap + 6 + trans_length + trans_length2
    else:
        #tcap_tag(0), tcap_length(1), tag_1(2), length_1(3), id_1(4:4+l1), next_tag(4+l1)
        next_index = index_tcap + 4 + trans_length
    
    next_tag = m3u_data[next_index]

    comp_op_code = comp_tag = imsi = -1
    if next_tag == DIALOGUE_PORTION_TAG: # hex 6b
        index_comp = parseDialoguePortion(next_index, m3u_data, index_tcap + tcap_length + 2)
        if index_comp != -1:
            comp_op_code, comp_tag, imsi = parseComponent(index_comp, m3u_data)
    elif next_tag == COMPONENT_TAG: # hex 6c
        index_comp = next_index
        comp_op_code, comp_tag, imsi = parseComponent(index_comp, m3u_data)
        
    return tcap_length, comp_op_code, comp_tag, imsi

## Extracts important parameters in the TCAP PDU
#
# @param[in] index_tcap     Index in the m3u_data where the TCAP PDU starts
# @param[in] m3u_data       The data to search through.
# @param[out] tcap_tag      transaction PDUs (Originating/Destination)
# @param[out] tcap_length   The length of the TCAP PDU
# @param[out] comp_op_code  The Component operational code
# @param[out] comp_tag      The Component TAG, -1 if not found
# @param[out] imsi          imsi number, -1 if not found
@profile
def parseTCAP(index_tcap, m3u_data):
    tcap_tag = m3u_data[index_tcap]
    tcap_length = comp_op_code = comp_tag = imsi = -1
    if tcap_tag == TCAP_BEGIN_TAG or tcap_tag == TCAP_END_TAG:
        num_transaction_id = 1
        tcap_length, comp_op_code, comp_tag, imsi = findComponentInTcap(index_tcap, m3u_data, num_transaction_id)
    elif tcap_tag == TCAP_CONTINUE_TAG:
        num_transaction_id = 2
        tcap_length, comp_op_code, comp_tag, imsi = findComponentInTcap(index_tcap, m3u_data, num_transaction_id)
    elif tcap_tag == TCAP_ABORT_TAG:
        tcap_length = m3u_data[index_tcap + 1]

    return tcap_tag, tcap_length, comp_op_code ,comp_tag, imsi

## Finds the index of the Payload data
#
# @param[in] index_tcap     Index in the m3u_data where the TCAP PDU starts
# @param[in] m3u_data       The data to search through.
# @param[out] index_tag     the index of the payload data, reutrns -1 if not found

# PAYLOAD_DATA contains:
# Network Appearance       Optional
# Routing Context          Conditional
# Protocol Data            Mandatory
# Correlation Id           Optional
#
# see definition in https://tools.ietf.org/html/rfc4666
@profile
def parsePayloadData(start_index, m3u_data):
    payloadDataTags = {'Network Appearance': 512, 'Routing Context': 6, 'Protocol Data': 528, 'Correlation Id': 19}

    index_loop = start_index
    next_tag = int.from_bytes(m3u_data[index_loop:index_loop + 2], byteorder='big')
    keep_search = True
    index_tag = -1
    while keep_search:
        if next_tag in payloadDataTags.values():
            if next_tag == payloadDataTags['Protocol Data']:
                index_tag = index_loop
                keep_search = False
            else:
                length = int.from_bytes(m3u_data[index_loop + 2:index_loop + 4], byteorder='big')
                index_loop += length
                next_tag = int.from_bytes(m3u_data[index_loop:index_loop + 2], byteorder='big')
        else:
            keep_search = False
    return index_tag

## The packet is added into a list of a certain key element in the dictionary
# The dictionary can be very large if the pcap file is large
# @param[in] key        key to the dictionary
# @param[in] sport      source port of the sctp message
# @param[in] dport      destination port of the sctp message
# @param[in] tag        the sctp verification tag
# @param[in] stream_id  the id of the sctp stream
# @param[in] proto_id   the payload protocal identifier (3 for m3ua)
# @param[in] stream_seq  the stream sequence number
# @param[in] tsn        transmission sequence number
# @param[in] data       the payload data
def addPktToDict(key,sport,dport,tag,stream_id,proto_id,stream_seq,tsn,data):
    global filter_dict
    if key not in filter_dict:
        filter_dict[key] = []
    #the pkt can contain several sctp chunks and if filter is done within the sctp chunk, then create a new packet only containing the sctp chunk data
    filter_dict[key].append(Ether()/IP()/SCTP(sport=sport,dport=dport,tag=tag)/SCTPChunkData(reserved=0, delay_sack=0, unordered=0, beginning=1, ending=1, stream_id=stream_id, proto_id=proto_id, stream_seq=stream_seq, tsn=tsn, data=data))

    #filter_dict[key].append(pkt)

## for each list of packets in the dictionary, this function creates one pcap file.
# @param[in] split_folder   the Folder in which the files are placed
def createPcapFilesFromDict(split_folder):
    global filter_dict
    global filter_tag
    for key, value in filter_dict.items():

        file_name = split_folder + filter_tag.name +"_"+str(key)+".pcap"
        wrpcap(file_name, value)
    

## Looks through one packet to find the SCTP chunk data and then parses out important ss7 mtp3 data
# the data is stored in a row in the StringIO output
#
# @param[in] pkt    Packet containing ss7 sctp mtp3 data
#
@profile
def parsePkt(pkt):
    # First check that it is a SCTP msg
    global pkt_count
    global chunk_count
    global filter_tag
    global filter_dict

    pkt_count += 1
    ip = pkt['IP']
    layer = ip.payload
    src_ip = ip.src
    dst_ip = ip.dst
    #print("pkt_count: ",pkt_count)
    while layer.name != 'NoPayload':
        if layer.name == 'SCTP':
            #Store attributes for sctp to be used in sctp chunk
            src_port = layer.sport
            dst_port = layer.dport
            tag = layer.tag

        elif layer.name == 'SCTPChunkData':
                stream_id = layer.stream_id
                proto_id = layer.proto_id
                stream_seq = layer.stream_seq
                tsn = layer.tsn

                if filter_tag == FilterTagEnum.src_port:
                    addPktToDict(src_port,src_port,dst_port,tag,stream_id,proto_id,stream_seq,tsn,layer.data)
                    layer = layer.payload
                    continue

                elif filter_tag == FilterTagEnum.stream:
                    if stream_id != -1:
                        addPktToDict(stream_id,src_port,dst_port,tag,stream_id,proto_id,stream_seq,tsn,layer.data)
                    layer = layer.payload
                    continue
                    
                chunk_count += 1
                if layer.proto_id == M3UA_ID:
                    m3u_data = layer.data
                    mtp3_msg_class = m3u_data[2]
                    mtp3_msg_type = m3u_data[3]
                    mtp3_length = int.from_bytes(m3u_data[4:8], byteorder='big')
                    
                    if mtp3_length > 8: #if length contains something more than the length itself that ends on octet 8.
                        if mtp3_msg_class == TRANSFER_MESSAGE:
                            if mtp3_msg_type == PAYLOAD_DATA:
                                
                                # Find start of protocol data in order to find the sccp parameter
                                start_index = 8
                                index_protocol_data = parsePayloadData(start_index, m3u_data)
                                if index_protocol_data != -1:
                                    # We are not interested in parameters in the protocol data tag, the user data begins 16 octets after the protcol data
                                    index_sccp = index_protocol_data + 16
                                    cdGT, cgGT, index_tcap = parseSCCP(index_sccp, m3u_data)
                                    if filter_tag == FilterTagEnum.cgGT:
                                        #print("pkt_count: ", pkt_count)
                                        if cgGT != -1:
                                            addPktToDict(cgGT.hex(),src_port,dst_port,tag,stream_id,proto_id,stream_seq,tsn,layer.data)
                                        layer = layer.payload                
                                        continue
                                    tcap_tag, tcap_length, comp_op_code,comp_type_tag, imsi =  parseTCAP(index_tcap, m3u_data)
                                    if filter_tag == FilterTagEnum.imsi:
                                        #print("pkt_count: ", pkt_count)
                                        if imsi != -1:
                                            addPktToDict(imsi,src_port,dst_port,tag,stream_id,proto_id,stream_seq,tsn,layer.data)
                                        layer = layer.payload                
                                        continue

                            else:
                                print("message type: ", mtp3_msg_type, " pkt nr: ",pkt_count)
                        else:
                            print("message class: ", mtp3_msg_class, " pkt nr: ",pkt_count)
                    else:
                        cdGT = cgGT = b'0x00'
                        tcap_length = tcap_tag = comp_op_code = comp_type_tag = -1

        layer = layer.payload

## returns an enum for the split choice chosen
# @param[in]    choice      What to split the pcap files on, default is imsi
# @param[out]   filterTag   The enum representation fo the choice
def convertSplitChoiceToFilterTag(choice):
    filterTag = FilterTagEnum.imsi
    if choice == "stream":
        filterTag = FilterTagEnum.stream
    elif choice == "src_port":
        filterTag = FilterTagEnum.src_port
    elif choice == "cgGT":
        filterTag = FilterTagEnum.cgGT
    elif choice == "imsi":
        filterTag = FilterTagEnum.imsi
    return filterTag


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PCAP reader')
    parser.add_argument('--pcap', metavar='<pcap file name>',
                        help='pcap file to parse', required=True)
    parser.add_argument('--out', metavar='<out put file name>',
                        help='out put file name where the parsed data is stored', default="ss7_filtered_data.pack")
    parser.add_argument('--split', metavar='<what to split on (stream_id, src_port, cgGT, imsi)>',
                        help='choos what variable to split the pcap files on (stream_id, src_port, cgGT, imsi)', type=str,  required=True)
    args = parser.parse_args()
    
    file_name = args.pcap
    if not os.path.isfile(file_name):
        print(format(file_name)," does not exist")
        sys.exit(-1)
    output_file = args.out
    split_choice = args.split

    filter_tag = convertSplitChoiceToFilterTag(split_choice)
    filter_dict = dict()

    split_folder = "split_" +filter_tag.name +"/"
    
    if not os.path.exists(split_folder):
        os.makedirs(split_folder)

    output = StringIO() 
    csv_writer = writer(output)
    start_time = time.time()
    sniff(offline=file_name,prn=parsePkt,store=0)
    print("parse took ", (time.time() - start_time), " sec")

    createPcapFilesFromDict(split_folder)

    print("pcap files stored")

    sys.exit(0)

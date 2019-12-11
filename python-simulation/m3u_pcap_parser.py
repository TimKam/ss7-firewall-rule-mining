#!/usr/bin/python3

## @package m3u_pcap_parser
#  This script can be used to extract valuable information from a pcap file containing ss7 mtps signals
#  The output can be stored as either csv or msg pack file, the default is to store as msg pack format 
#  The output is the stored in the file ss7_filtered_data.pack
#  use --help to see the options for the script
#
#  In order to understand the structure of the ss7 messages, read ITU-T Q.713, ITU-T Q.773 and https://tools.ietf.org/html/rfc3868
# 
# Usage: m3u_pcap_parser.py --pcap <pcap_file>
# 
# output values that specifies what kind of signal it is (only common values listed, read above docs to learn more):
#  mtp3_msg_type:   (1=payload data)
#  tcap_tag:        (98=begin, 100=end, 101=continue, 103=abort)
#  op_code:         (2=update location, 56=send authentication info, 67=purgeMS, 7=insert subscriber data
#  comp_type_tag:   (161=invoke, 162=Return result last, 163=Return result not last)

import socket
import sctp
import argparse
import os
import time
import sys
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
MSC_NOT_KNOWN_TAG = 129
VLR_NOT_KNOWN_TAG = 4
IMSI_NOT_KNOWN_TAG = 48


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

def extractMscVlr(data):
    ret_value = [0x0] * 6
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
# @param[in]  index_comp    index in the m3u_data where the Component PDU starts
# @param[in]  m3u_data      The data to search through.
# @param[out] comp_op_code  Component Operational Code
# @param[out] comp_type_tag The Component Type tag
# @param[out] imsi          imsi number, return -1 if not found
# @param[out] msc_str       The number to the Mobile Switching Center, return -1 if not found
# @param[out] vlr_str       The number to the Visitor Location Register, return -1 if not found
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

    comp_op_code = msc_str = vlr_str = imsi = -1
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
                    
                    while next_index < max_comp_index:
                        if next_tag == IMSI_NOT_KNOWN_TAG:
                            #check length to be sure it is imsi
                            length = m3u_data[next_index + 3]
                            if length == 8:
                                imsi = extractImsi(m3u_data[next_index + 4:next_index + 12])
                                next_index += 12
                                next_tag = m3u_data[next_index]
                                continue
                            else:
                                break
                        elif next_tag == MSC_NOT_KNOWN_TAG:
                            length = m3u_data[next_index + 1]
                            #check also the length to be sure
                            if length == 6:
                                msc = m3u_data[next_index + 2:next_index + 8]
                                msc_str = ''.join('{:02x}'.format(x) for x in msc)
                                next_index += 8 #step to vlr
                                next_tag =  m3u_data[next_index]
                                continue
                            else:
                                break
                        elif next_tag == VLR_NOT_KNOWN_TAG:
                            length = m3u_data[next_index + 1]
                            #check also the length to be sure
                            if length == 6:
                                vlr = m3u_data[next_index + 2:next_index + 8]
                                vlr_str = ''.join('{:02x}'.format(x) for x in vlr)
                                break
                            else:
                                break
                        else:
                            break

    return comp_op_code, comp_type_tag, imsi, msc_str, vlr_str

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
# @param[out] length            The length of the PDU, returns -1 if the length is not specified
# @param[out] imsi              imsi number
# @param[out] msc_str           The number to the Mobile Switching Center
# @param[out] vlr_str           The number to the Visitor Location Register
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

    comp_op_code = comp_tag = msc_str = vlr_str = imsi = -1
    if next_tag == DIALOGUE_PORTION_TAG: # hex 6b
        index_comp = parseDialoguePortion(next_index, m3u_data, index_tcap + tcap_length + 2)
        if index_comp != -1:
            comp_op_code, comp_tag, imsi, msc_str, vlr_str = parseComponent(index_comp, m3u_data)
    elif next_tag == COMPONENT_TAG: # hex 6c
        index_comp = next_index
        comp_op_code, comp_tag, imsi, msc_str, vlr_str = parseComponent(index_comp, m3u_data)
        
    return tcap_length, comp_op_code, comp_tag, imsi, msc_str, vlr_str

## Extracts important parameters in the TCAP PDU
#
# @param[in] index_tcap     Index in the m3u_data where the TCAP PDU starts
# @param[in] m3u_data       The data to search through.
# @param[out] tcap_tag      transaction PDUs (Originating/Destination)
# @param[out] tcap_length   The length of the TCAP PDU
# @param[out] comp_op_code  The Component operational code
# @param[out] comp_tag      The Component TAG
# @param[out] imsi          imsi number
# @param[out] msc_str       The number to the Mobile Switching Center
# @param[out] vlr_str       The number to the Visitor Location Register
@profile
def parseTCAP(index_tcap, m3u_data):
    tcap_tag = m3u_data[index_tcap]
    tcap_length = comp_op_code = comp_tag = imsi = msc_str = vlr_str = -1
    if tcap_tag == TCAP_BEGIN_TAG or tcap_tag == TCAP_END_TAG:
        num_transaction_id = 1
        tcap_length, comp_op_code, comp_tag, imsi, msc_str, vlr_str = findComponentInTcap(index_tcap, m3u_data, num_transaction_id)
    elif tcap_tag == TCAP_CONTINUE_TAG:
        num_transaction_id = 2
        tcap_length, comp_op_code, comp_tag, imsi, msc_str, vlr_str = findComponentInTcap(index_tcap, m3u_data, num_transaction_id)
    elif tcap_tag == TCAP_ABORT_TAG:
        tcap_length = m3u_data[index_tcap + 1]

    return tcap_tag, tcap_length, comp_op_code ,comp_tag, imsi, msc_str, vlr_str

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
    pkt_count += 1
    ip = pkt['IP']
    layer = ip.payload
    while layer.name != 'NoPayload':
        #if layer.name == 'SCTP':
            #Maybe extract stream id, sender and receiver IP
        if layer.name == 'SCTPChunkData':
            #sctpDataPkt = SCTPChunkData(reserved=0, delay_sack=0, unordered=0, beginning=1, ending=1, stream_id=layer.stream_id, proto_id=layer.proto_id, stream_seq=layer.stream_seq, tsn=layer.tsn, data=layer.data)
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
                                    tcap_tag, tcap_length, comp_op_code,comp_type_tag, imsi, msc_str, vlr_str = parseTCAP(index_tcap, m3u_data)
                            else:
                                print("message type: ", mtp3_msg_type, " pkt nr: ",pkt_count)
                        else:
                            print("message class: ", mtp3_msg_class, " pkt nr: ",pkt_count)
                    else:
                        cdGT = cgGT = b'0x00'
                        tcap_length = tcap_tag = comp_op_code = comp_type_tag = -1
                        imsi = msc_str = vlr_str = "-1"
                    #store data for packet
                    row = [pkt.time,pkt_count,chunk_count,mtp3_length,mtp3_msg_type,cdGT.hex(),cgGT.hex(),tcap_length,tcap_tag,comp_op_code,comp_type_tag, imsi, msc_str, vlr_str]
                    csv_writer.writerow(row)

        layer = layer.payload

## Verifies that the output file either ends with .csv or .pack
# @param[in] file_name  name of the file that should be tested
# 
def checkOutPutFile(file_name):
    file_parts = file_name.split('.')
    allOk = False
    if len(file_parts) == 2:
        file_type = file_parts[1]
        if file_type == "csv" or file_type == "pack":
            allOk = True
    if allOk == False:
        print("output file name is not correct, should only contain one . and should end with .csv or .pack")
        sys.exit(-1)
    return file_parts[0], file_parts[1]
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PCAP reader')
    parser.add_argument('--pcap', metavar='<pcap file name>',
                        help='pcap file to parse', required=True)
    parser.add_argument('--out', metavar='<out put file name, should end with .csv or .pack>',
                        help='out put file name where the parsed data is stored', default="ss7_filtered_data.pack")
    args = parser.parse_args()
    
    file_name = args.pcap
    if not os.path.isfile(file_name):
        print(format(file_name)," does not exist")
        sys.exit(-1)
    output_file = args.out
    #check if file ends with .pack or .csv
    out_file_name, out_file_type = checkOutPutFile(output_file)

    output = StringIO() 
    csv_writer = writer(output)
    start_time = time.time()
    sniff(offline=file_name,prn=parsePkt,store=0)
    print("parse took ", (time.time() - start_time), " sec")
    #these column names should be the same as the rows that is stored in the parsePkt function
    column_names = ['time_stamp','pkt_nr','chunk_nr','mtp3_length','mtp3_msg_type','cdGT','cgGT','tcap_length','tcap_tag','op_code','comp_type_tag', 'imsi', 'msc', 'vlr']
    #rewind the output (if not then nothing will be stored)
    output.seek(0)
    ss7_data = pd.read_csv(output, header = None, names = column_names)

    path = os.path.dirname(os.path.abspath(__file__))
    file_path = path +"/" +output_file
    print("writing to file: " + file_path)

    if out_file_type == "csv":
        export_csv = ss7_data.to_csv (file_path, index = None, header=True)
    else:
        ss7_data.to_msgpack(file_path)

    sys.exit(0)

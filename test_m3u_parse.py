## Tests the m3u_pcap_parser

import unittest
import m3u_pcap_parser
from scapy.all import sniff
from scapy.all import rdpcap, Ether, IP, SCTP, SCTPChunkData, wrpcap, hexdump
from csv import writer 
from io import StringIO
import pandas as pd
import msgpack
import glob, os

class TestParse(unittest.TestCase):

    def test_pars_pack(self):
        for test_file in glob.glob("test_pcap/test*.pcap"):
            output = StringIO() 
            csv_writer = writer(output)

            sniff(offline=test_file,prn=m3u_pcap_parser.parsePkt,store=0)

            column_names = ['time_stamp','pkt_nr','chunk_nr','mtp3_length','mtp3_msg_type','cdGT','cgGT','tcap_length','tcap_tag','op_code','comp_type_tag']
            output.seek(0)
            ss7_data = pd.read_csv(output, header = None, names = column_names)

            op_codeDF = ss7_data.loc[ss7_data['op_code'] == -1]
            num_not_valid_op_code = op_codeDF.shape[0]
            self.assertEqual(num_not_valid_op_code, 0, "Should be 0 not valid op_codes")


if __name__ == '__main__':
    unittest.main()

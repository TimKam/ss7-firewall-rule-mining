# ss7-firewall-rule-mining

#Things to read: https://medium.com/@vasanthavanan59439/ss7-the-deadliest-attack-6423de7fe8c0

#Requirements:
#pysctp to be able to send and recive sctp messages (LGPL license)
- sudo apt-get install libsctp-dev
- pip3 install git+https://github.com/P1sec/pysctp.git

#sniff packets from pcap file
- sudo pip3 install python3-scapy
- sudo pip3 install scapy

- sudo pip3 install pandas
- sudo pip3 install msgpack


# UDP Files:
- udp_server.py - receives udp messages from clients

- udp_client_generator.py - starts and keeps alive a certain amount of threads sending udp messages to the udp server, each thread has its unique client id

# Good to have scripts
- packet_per_sec.py - script that can be used to monitor the total amount of packets/s and bytes/s that is sent on a certain interface.

# Scripts for parsing pcap files
- m3u_pcap_parser.py - script that can parse a pcap file to find ss7 mtp3 messages and stores important variables for each mtp3 message, the output is stored either in a csv file or msg pack file.

- m3u_pcap_splitter.py - script that parses one pcap file and splits it into smaller pcap files based on some variable, for example sctp src_port, stream id, cgGT or imsi number.

# Script used to sort csv files obtained using pcap parser scripts
- sort_csv.py - script that can both read a csv file or an msg pack file and sorts the rows based on some column chosen by the user, could be perhaps calling Global Title (cgGT), imsi or other columns, also uses the time_stamp to sort on after first sorting has taken place and adds a time diff column that shows the difference in time since last signal that had the same column value as sorted on. first time diff value is always -1

## SCTP files
- sctp_client.py  - a sctp client that send one message to a sctp server

- sctp_server.py - SCTP server that can handles multiple of clients, stores events in file using logger when connection is established and closed.

- sctp_pcap_client.py - script that starts a certain amount of pcap clients, each client uses a pcap file to know what to send and how often. these files have been created by the m3u_pcap_splitter.py script.

- flatten_sctp.py - In order to make it more easy to view the SCTP messages in a pcap file all SCTP chunks are seperated into its own signal and the output is stored in a new pcap file

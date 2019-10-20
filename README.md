# ss7-firewall-rule-mining

#Things to read: https://medium.com/@vasanthavanan59439/ss7-the-deadliest-attack-6423de7fe8c0

#Requirements:
#pysctp to be able to send and recive sctp messages (LGPL license)
- sudo apt-get install libsctp-dev
- pip install git+https://github.com/P1sec/pysctp.git

# Files:
- udp_server.py - receives udp messages from clients

- udp_client_generator.py - starts and keeps alive a certain amount of threads sending udp messages to the udp server, each thread has its unique client id

- packet_per_sec.py - script that can be used to monitor the total amount of packets/s and bytes/s that is sent on a certain interface.

- m3u_pcap_parser.py - script that can parse a pcap file to find ss7 mtp3 messages and stores important variables for each mtp3 messages in a output file using msgpack

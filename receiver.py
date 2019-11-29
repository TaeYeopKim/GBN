from socket import *
import sys
import signal
import os
import packet
from packet import packet
from threading import Thread

# variables to hold command line arguments
host_addr = sys.argv[1]
emu_port = int(sys.argv[2])
rcv_data_port = int(sys.argv[3])
new_file_to_write = sys.argv[4]

if os.path.exists(new_file_to_write):
	os.remove(new_file_to_write)

# create output file
new_file = open(new_file_to_write, "w+")

arrival_file = open("arrival.log", "w+")

# sockets to send and receive data and ack
rcv_data_socket = socket(AF_INET, SOCK_DGRAM)
rcv_data_socket.bind(('', rcv_data_port))
send_ack_socket = socket(AF_INET, SOCK_DGRAM)

next_seq = 0
first_ever_packet_recvd = False
packet_type = 1
should_send_ack = False
ack_packet = None
while True:
	received_packet, sender_address = rcv_data_socket.recvfrom(1024) 	# receive data packet, and analyze
	received_packet = packet.parse_udp_data(received_packet)
	packet_type = received_packet.type
	packet_data = received_packet.data
	packet_seq_num = received_packet.seq_num

	arrival_file.write(str(packet_seq_num) + "\n") 		# write data's seq_num to arrival_file

	if packet_type == 2:		# exit out if EOT packet received
		break

	if packet_seq_num == next_seq:		# if true, then valid data packet with expected seq_num
		new_file.write(packet_data)
		ack_packet = packet.create_ack(next_seq)
		should_send_ack = True
		next_seq = (next_seq + 1) % 32

	if should_send_ack:		# if first ever packet received does not have seq_num of 0, ignore. If not, start sending ACK
		send_ack = ack_packet.get_udp_data()	# if first ever ACK packet sent, if receved seq_num is not expected, just send
		send_ack_socket.sendto(send_ack, (host_addr, emu_port))		# latest sent valid ACK packet

new_file.close()
ack_packet = packet.create_eot(next_seq)
send_ack_socket.sendto(ack_packet.get_udp_data(), (host_addr, emu_port))
arrival_file.close()
rcv_data_socket.close()
send_ack_socket.close()

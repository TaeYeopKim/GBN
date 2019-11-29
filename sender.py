from socket import *
import sys
import signal
import os
from packet import packet
import threading
import time


# variables to hold command line arguments
host_addr = sys.argv[1]
emu_port = int(sys.argv[2])
rcv_ack_port = int(sys.argv[3])
input_file_name = sys.argv[4]

# GoBackN variables
window = 10
max_seq = 32
send_base = 0
next_seq_num = 0

# sockets to send and receive data and ack
send_data_socket = socket(AF_INET, SOCK_DGRAM)
rcv_ack_socket = socket(AF_INET, SOCK_DGRAM)
rcv_ack_socket.bind(('', rcv_ack_port))

# lock for synchronization of critical section
my_lock = threading.Lock()
my_cv = threading.Condition()

# variable to hold timers to resend data
my_timer = None

# holds packets
packet_list = []

# create record files
seqnum_file = open("seqnum.log", "w+")
ack_file = open("ack.log", "w+")
time_file = open("time", "w+")

first_ever_packet = True
start_time = None
end_time = None

def send_unack_packets():
	global next_seq_num			# both needs to be global
	global my_timer
	
	my_lock.acquire()
	next_seq_num = send_base

	if my_timer:
		my_timer.cancel()
	my_timer = threading.Timer(0.1, send_unack_packets)		# stop the timer, and start again
	my_timer.start()
	my_lock.release()

	my_cv.acquire()
	my_cv.notify()		# wakes up sleeping data sending thread
	my_cv.release()

def wait_for_ack():
	global next_seq_num
	global my_timer
	global send_base

	while True:
		ACK_from_rcver, address = rcv_ack_socket.recvfrom(1024) 	# receive ACK packet, and analyze
		ack_packet = packet.parse_udp_data(ACK_from_rcver)
		ack_type = ack_packet.type
		ack_seqnum = ack_packet.seq_num

		if ack_type == 2:	# if EOT packet, exit since ACK received
			end_time = time.time()
			time_file.write(str(end_time - start_time))
			break

		ack_file.write(str(ack_seqnum) + "\n") 		# write ack_seqnum to ack_file

		my_lock.acquire()
		check_num = next_seq_num - send_base	# indicates sent, but unACK'ed packets
		for i in range(0, check_num):
			if ack_seqnum == ((send_base + i) % max_seq):
				send_base = send_base + i + 1
		
		if my_timer:	# needs to stop the timer in both cases: stop or stop and start again
			my_timer.cancel()
		if send_base != next_seq_num:	# if received ACK not the last packet in window, restart timer
			my_timer = threading.Timer(0.1, send_unack_packets)
			my_timer.start()
		my_lock.release()

		my_cv.acquire()
		my_cv.notify()		# wakes up sleeping data sending thread
		my_cv.release()

	rcv_ack_socket.close()



listen_ack_thread = threading.Thread(target=wait_for_ack, daemon=True)
listen_ack_thread.start()			# start the listening thread
f = open(input_file_name, "r")		# open input file
contents = f.read(500)

while True:
	packet_list.append(packet.create_packet(next_seq_num, contents)) # divide input file into 500 byte chunks
	next_seq_num += 1
	contents = f.read(500)
	if len(contents) < 500:
		break

packet_list.append(packet.create_packet(next_seq_num, contents)) # store divided chunks into an array
next_seq_num = 0

while True:

	my_lock.acquire()
	seqnum_file.write(str(next_seq_num) + "\n")		# write next_seq_num to seqnum_file
	if send_base >= len(packet_list):	# if this is true, all data packets have been sent, so exit
		my_lock.release()
		break

	if next_seq_num < len(packet_list) and (next_seq_num < send_base + window): 	# check if there is room available in window
		send_data = packet_list[next_seq_num].get_udp_data()

		if first_ever_packet:		# checking if transmission time needs to start
			start_time = time.time()
			first_ever_packet = False
		send_data_socket.sendto(send_data, (host_addr, emu_port))
		if send_base == next_seq_num:		# if true, then sending first packet of window, so start timer
			if my_timer:
				my_timer.cancel()
			my_timer = threading.Timer(0.1, send_unack_packets)
			my_timer.start()
		next_seq_num += 1
		my_lock.release()
	else:
		my_lock.release()
		my_cv.acquire()
		my_cv.wait()		# if no room in window, needs to sleep until room appears
		my_cv.release()

data_packet = packet.create_eot(next_seq_num)
send_data = data_packet.get_udp_data()
send_data_socket.sendto(send_data, (host_addr, emu_port))

f.close()
listen_ack_thread.join()
seqnum_file.close()		# close all record files
ack_file.close()
time_file.close()
send_data_socket.close()

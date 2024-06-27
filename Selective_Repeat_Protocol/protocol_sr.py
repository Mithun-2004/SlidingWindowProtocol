# Name: P. Mithun, Roll No. : 2203314
# SimPy models for rdt_Sender and rdt_Receiver
# implementing the SR Protocol

import simpy
# import random
# import sys
from Packet import Packet



class rdt_Sender(object):
	
	def __init__(self,env):
		
		# Initialize variables and parameters
		self.env=env 
		self.channel=None
		
		# some default parameter values
		self.data_packet_length=10 # bits
		self.timeout_value=10 # default timeout value for the sender
		self.N=5 # Sender's Window size
		self.K=16 # Packet Sequence numbers can range from 0 to K-1

		# some state variables and parameters for the SR Protocol
		self.base=1 # base of the current window 
		self.nextseqnum=1 # next sequence number
		self.sndpkt= {} # a buffer for storing the packets to be sent (implemented as a Python dictionary)
		self.recvpkt = {}

		# some other variables to maintain sender-side statistics
		self.total_packets_sent=0
		self.num_retransmissions=0

		
		# timer-related variables
		self.timers = {}
		self.timers_is_running = {}

		for i in range(self.K):
			self.timers[i] = None
			
	
	def rdt_send(self,msg):
		# This function is called by the 
		# sending application.
			
		# check if the nextseqnum lies within the 
		# range of sequence numbers in the current window.
		# If it does, make a packet and send it,
		# else, refuse this data.

				
		if(self.nextseqnum in [(self.base+i)%self.K for i in range(0,self.N)]):
			print("TIME:",self.env.now,"RDT_SENDER: rdt_send() called for nextseqnum=",self.nextseqnum," within current window. Sending new packet.")
			# create a new packet and store a copy of it in the buffer
			self.sndpkt[self.nextseqnum]= Packet(seq_num=self.nextseqnum, payload=msg, packet_length=self.data_packet_length)

			# send the packet
			self.channel.udt_send(self.sndpkt[self.nextseqnum])
			self.total_packets_sent+=1
			
			# start the timer for the sent packet
			self.start_timer(self.nextseqnum)

			# update the nextseqnum
			self.nextseqnum = (self.nextseqnum+1)%self.K
			return True
		else:
			# refuse the data
			print("TIME:",self.env.now,"RDT_SENDER: rdt_send() called for nextseqnum=",self.nextseqnum," outside the current window. Refusing data.")
			return False
		
		
	
	def rdt_rcv(self,packt):
		# This function is called by the lower-layer 
		# when an ACK packet arrives
		
		# check if we got uncorrupted packet
		if (packt.corrupted==False):
			# check if we got an ACK for a packet within the current window.
			if(packt.seq_num in list(self.sndpkt.keys())):
				#storing the received ACK packet in a buffer so that we can check it to update the base of the window
				self.recvpkt[packt.seq_num] = packt

				#removing the packet with the ACK received and stoping the timer of that packet
				# del self.sendpkt[packt.seq_num]
				# if (self.timers_is_running[packt.seq_num] == True):
				self.stop_timer(packt.seq_num)

				# update the base of the window
				while self.base in list(self.recvpkt.keys()):
					del self.sndpkt[self.base]
					del self.recvpkt[self.base]
					self.base  = (self.base+1)%self.K
				
				print("TIME:",self.env.now,"RDT_SENDER: Got an ACK",packt.seq_num,". Updated window:", [(self.base+i)%self.K for i in range(0,self.N)],"base =",self.base,"nextseqnum =",self.nextseqnum)
			else:
				print("TIME:",self.env.now,"RDT_SENDER: Got an ACK",packt.seq_num," for a packet in the old window. Ignoring it.")
		else:
			print("TIME:",self.env.now,"RDT_SENDER: Got a corrupted ACK. Ignoring it")

	# Finally, these functions are used for modeling a Timer's behavior.
	def timer_behavior(self, timer_id):
		try:
			# Wait for timeout 
			self.timers_is_running[timer_id] = True
			yield self.env.timeout(self.timeout_value)
			self.timers_is_running[timer_id] = False
			# self.timers[timer_id] = None
			# take some actions 
			self.timeout_action(timer_id)
		except simpy.Interrupt:
			# stop the timer
			print("timer stopped for timer", timer_id)
			self.timers_is_running[timer_id] = False
			# self.timers[timer_id] = None

	# This function can be called to start the timer
	def start_timer(self, timer_id):
		print("TIME:", self.env.now, "RDT_SENDER:", "Timers before sending the current packet", timer_id, ": ", self.timers_is_running)
		# assert(timer_id not in list(self.timers_is_running.keys()))
		self.timers[timer_id] = self.env.process(self.timer_behavior(timer_id))
		print("TIME:",self.env.now,"TIMER STARTED for a timeout of ",self.timeout_value, "for packet no", timer_id)
		print("TIME:", self.env.now, "RDT_SENDER:", "Timers after sending the current packet", timer_id, ": ", self.timers_is_running)

	# This function can be called to stop the timer
	def stop_timer(self, timer_id):
		assert(timer_id in list(self.timers_is_running.keys()))
		self.timers[timer_id].interrupt()
		print("TIME:",self.env.now,"TIMER STOPPED for packet", timer_id)
		


	# Actions to be performed upon timeout
	def timeout_action(self, timer_id):
		
		# re-send all the packets for which an ACK has been pending
		print("timeout action:", timer_id)
		packet_to_be_resent = self.sndpkt[timer_id]
		print("TIME:",self.env.now,"RDT_SENDER: TIMEOUT OCCURED. Re-transmitting packets",packet_to_be_resent)
		self.channel.udt_send(packet_to_be_resent)
		self.num_retransmissions+=1
		self.total_packets_sent+=1
		
		# Re-start the timer
		self.start_timer(timer_id)
		
	# A function to print the current window position for the sender.
	def print_status(self):
		print("TIME:",self.env.now,"Current window:", [(self.base+i)%self.K for i in range(0,self.N)],"base =",self.base,"nextseqnum =",self.nextseqnum)
		print("---------------------")


#==========================================================================================

class rdt_Receiver(object):
	
	def __init__(self,env):
		
		# Initialize variables
		self.env=env 
		self.receiving_app=None
		self.channel=None

		# some default parameter values
		self.ack_packet_length=10 # bits
		self.K=16 # range of sequence numbers expected
		self.N=5 #window size
		self.base = 1
		self.sndpkt= Packet(seq_num=0, payload="ACK",packet_length=self.ack_packet_length)
		self.total_packets_sent=0
		self.num_retransmissions=0
		self.packets = {}
		self.old_packets_ack = {}
		

	def rdt_rcv(self,packt):
		# This function is called by the lower-layer 
		# when a packet arrives at the receiver

		print("TIME:", self.env.now, "RDT_Receiver: old packets ACK", self.old_packets_ack)

		if (packt.corrupted==False and packt.seq_num in [(self.base+i)%self.K for i in range(0, self.N)]):
			# if the packet is not corrupted and its seq no. is within the window, then storing the packet in the buffer.
			self.packets[packt.seq_num] = packt.payload
			
			print("TIME:",self.env.now,"RDT_RECEIVER: got expected packet",packt.seq_num,". Sent ACK")
			# sending the corresponding ACK for the packet received.
			self.sndpkt= Packet(seq_num=packt.seq_num, payload="ACK",packet_length=self.ack_packet_length) 
			self.channel.udt_send(self.sndpkt)
			self.total_packets_sent+=1
 
			# delivering the packets to the receiving app and updating the base.
			while (self.base in list(self.packets.keys())):
				self.receiving_app.deliver_data(self.packets[self.base])
				del self.packets[self.base]

				self.base = (self.base+1) % self.K
				self.old_packets_ack = [(self.base - self.N + i) % self.K for i in range(0, self.N)] # assuming that window of the sequence numbers before the current base have been received to avoid overlapping.

			print("TIME:",self.env.now,"RDT_Receiver: Receiver's packet buffer: ",self.packets.keys())
			print("TIME:",self.env.now,"RDT_Receiver: Updated Window ",[(self.base+i)% self.K for i in range(self.N)],"base =",self.base)
			

		# Sends the ACK for old packets defined in old_packets_ack
		elif (packt.seq_num in self.old_packets_ack):
			self.sndpkt= Packet(seq_num=packt.seq_num, payload="ACK",packet_length=self.ack_packet_length) 
			print("TIME:", self.env.now, "RDT_Receiver: sent ACK for older packet with packet no", packt.seq_num)
			self.channel.udt_send(self.sndpkt)
			self.total_packets_sent+=1
			self.num_retransmissions+=1
			
			
		else:
			# got a corrupted or unexpected packet. ignore it.
			if(packt.corrupted):
				print("TIME:",self.env.now,"RDT_RECEIVER: got corrupted packet")
			# got an unexpected packet
			else:
				print("TIME:",self.env.now,"RDT_RECEIVER: got unexpected packet with sequence number",packt.seq_num,". Sent ACK",packt.seq_num)
				# self.sndpkt= Packet(seq_num=self.base-1, payload="ACK",packet_length=self.ack_packet_length)
				# self.channel.udt_send(self.sndpkt)
				# self.total_packets_sent+=1
				# self.num_retransmissions+=1
			
			
		print("TIME:", self.env.now, "RDT_RECEIVER: expected sequence numbers:", [(self.base+i)%self.K for i in range(0, self.N)], "base of window:", self.base)


import socket, random, time
from btcp.lossy_layer import LossyLayer
from btcp.btcp_socket import BTCPSocket
from btcp.constants import *
from btcp.btcp_segment import BTCPSegment, ACKSegment, SYNSegment, SYNACKSegment, FINSegment


# The bTCP server socket
# A server application makes use of the services provided by bTCP by calling accept, recv, and close
class BTCPServerSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self._lossy_layer = LossyLayer(self, SERVER_IP, SERVER_PORT, CLIENT_IP, CLIENT_PORT)
        self._state = 0
        # States:
        # 0: Default
        # 1: Accepting
        # 2: Sent SYNACK, waiting for ACK
        # 3: Connection established

    # Called by the lossy layer from another thread whenever a segment arrives
    def lossy_layer_input(self, segment):
        segment_data, (c_ip, c_port) = segment
        seq_n, ack_n, flags, window, data_length, checksum, body = BTCPSegment.unpack(segment_data)
        # Check checksum
        out = BTCPSegment.in_cksum(segment_data, checksum)
        print("Checksum check:", out)
        
        print("Flag:", flags)

        # If we are in the "accepting" state and flag is SYN
        if self._state == 1 and flags == 2:
            new_seq_n = random.randrange(0, 65535)
            new_ack_n = seq_n + 1
            self._lossy_layer.send_segment(SYNACKSegment(new_seq_n, new_ack_n, self._window).pack())
            self._state = 2
        
        # If we are in the "Sent SYNACK, waiting for ACK" state and flag is ACK
        elif self._state == 2 and flags == 4:
            self._state = 3

    # Wait for the client to initiate a three-way handshake
    def accept(self):
        self._state = 1
        while self._state != 3:
            time.sleep(1)

    # Send any incoming data to the application layer
    def recv(self):
        if self._state == 3:
            pass

    # Clean up any state
    def close(self):
        self._state = 0
        self._lossy_layer.destroy()

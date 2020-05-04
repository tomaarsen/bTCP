import time
from btcp.btcp_socket import BTCPSocket
from btcp.lossy_layer import LossyLayer
from btcp.constants import *
from btcp.btcp_segment import BTCPSegment, ACKSegment, SYNSegment, SYNACKSegment, FINSegment

# bTCP client socket
# A client application makes use of the services provided by bTCP by calling connect, send, disconnect, and close
class BTCPClientSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self._lossy_layer = LossyLayer(self, CLIENT_IP, CLIENT_PORT, SERVER_IP, SERVER_PORT)
        self._state = 0
        # States:
        # 0: Default 
        # 1: SYN sent, waiting on SYNACK
        # 2: SYNACK received, sent ACK, should be connected

    # Called by the lossy layer from another thread whenever a segment arrives. 
    def lossy_layer_input(self, segment):
        segment_data, (c_ip, c_port) = segment
        seq_n, ack_n, flags, window, data_length, checksum, body = BTCPSegment.unpack(segment_data)

        print(flags)

        # If in state "SYN sent, waiting on SYNACK" and flag is SYNACK
        if self._state == 1 and flags == 6 and ack_n == self.x + 1:
            new_seq_n = ack_n
            new_ack_n = seq_n + 1
            self._lossy_layer.send_segment(ACKSegment(new_seq_n, new_ack_n, self._window).pack())
            self._state = 2

    # Perform a three-way handshake to establish a connection
    def connect(self):
        # TODO: Send segment over lossy layer
        self._state = 1
        segment = SYNSegment(self._window)
        self.x = segment.seq_n
        self._lossy_layer.send_segment(segment.pack())
        while self._state != 2:
            time.sleep(1)

    # Send data originating from the application in a reliable way to the server
    def send(self, data):
        pass

    # Perform a handshake to terminate a connection
    def disconnect(self):
        pass

    # Clean up any state
    def close(self):
        self._lossy_layer.destroy()

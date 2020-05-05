import time, threading
from btcp.btcp_socket import BTCPSocket
from btcp.lossy_layer import LossyLayer
from btcp.constants import *
from btcp.btcp_segment import BTCPSegment, ACKSegment, SYNSegment, SYNACKSegment, FINSegment

# bTCP client socket
# A client application makes use of the services provided by bTCP by calling connect, send, disconnect, and close
class BTCPClientSocket(BTCPSocket):
    def __init__(self, window, timeout):
        # TODO: Consider using timeout vs TIMEOUT_TIME from constants.py for connecting and disconnecting
        super().__init__(window, timeout)
        self._connection_event = threading.Event()
        self._lossy_layer = LossyLayer(self, CLIENT_IP, CLIENT_PORT, SERVER_IP, SERVER_PORT)
        # States:
        # 0: Default 
        # 1: SYN sent, waiting on SYNACK
        # 2: SYNACK received, sent ACK, should be connected
        # 3: FIN Sent, attempting to disconnect
        # 4: Sending data

        # TODO: Rework default, update receive window
        self.receive_window = window
        self.last_unacked = 0
        self.last_sent = 0

    # Called by the lossy layer from another thread whenever a segment arrives. 
    def lossy_layer_input(self, segment):
        # TODO: Timeout
        segment_data, (c_ip, c_port) = segment
        seq_n, ack_n, flags_int, window, data_length, checksum, body = BTCPSegment.unpack(segment_data)
        flags = BTCPSegment.convert_int_to_flags(flags_int)
        # Check checksum
        out = BTCPSegment.in_cksum(segment_data)
        print(f"R: {str(flags):<15}, Checksum Output: {out}, Checksum Value: {checksum}")
        if out != 0:
            print(f"Segment discarded as Checksum output: {out}")
            return

        # If in state "SYN sent, waiting on SYNACK" and flag is SYNACK
        if self.state == 1 and flags == {"SYN", "ACK"} and ack_n == self.x + 1:
            new_seq_n = ack_n
            new_ack_n = seq_n + 1
            self._lossy_layer.send_segment(ACKSegment(new_seq_n, new_ack_n, self._window).pack())
            # Set state to connected
            self.state = 2
            self._connection_event.set()
            print("-= Connection Established =-")

        # Receive FINACK from Server after attempting to disconnect
        elif self.state == 3 and flags == {"FIN", "ACK"}:
            # Disconnect
            # State will already be set to 0 in disconnect()
            #self.state = 0
            self._connection_event.clear()

        elif flags == {"ACK"}:
            # Updating receive window
            #print(f"Updating receive window from {self.receive_window} to {window}")
            #self.receive_window = window
            # Update last unacked
            print(f"Updating last_unacked from {self.last_unacked} to {ack_n}")
            self.last_unacked = ack_n

        else:
            print(self.state, flags)

    # Perform a three-way handshake to establish a connection
    def connect(self):
        # TODO: Go back to state 0 if fail
        self.state = 1
        tries = 0
        while not self._connection_event.is_set() and tries < MAX_TRIES:
            segment = SYNSegment(self._window)
            self.x = segment.seq_n
            self._lossy_layer.send_segment(segment.pack())
            tries += 1
            time.sleep(TIMEOUT_TIME)
        # TODO: Rework Exception
        if not self._connection_event.is_set():
            self.state = 0
            raise Exception("Could not connect to Server.")
    
    # Send data originating from the application in a reliable way to the server
    def send(self, file_obj):
        # TODO: Find advertised window
        # TODO: Store last_ack'd, which is the seq_n of the "oldest" unacked packet
        # TODO: Compare "in flight" packet count (unacked packets) with most recent advertised window size
        if self.state == 2:
            # Set state to "Sending data"
            self.state = 4

            # Get all data, and split it up into chunks of at most 1008 bytes
            byte_arr = bytearray(file_obj.read().encode())
            n = 1008
            # Dict with seq_n as a key. Note that dicts keep their ordering
            split_byte_arr = {i % 65535: byte_arr[i:i + n] for i in range(0, len(byte_arr), n)}
            # Initial sequence number
            seq_n = 0
            # Set oldest unacked segment to this default seq number
            self.last_unacked = seq_n
            self.last_sent = seq_n
            # in_flight is the amount of segments that have been sent but not acked
            sent = 0
            while True: #TODO: Fix
                while (self.last_sent - self.last_unacked) / 1008 < self.receive_window:
                    data = split_byte_arr[seq_n]
                    ack_n = (seq_n + len(data)) % 65535
                    self._lossy_layer.send_segment(BTCPSegment(seq_n, ack_n, self._window, data).pack())
                    self.last_sent = seq_n
                    seq_n = ack_n
                    sent += 1
                time.sleep(0.1)
            print(f"Sent {sent} segments")
            # Return to just "Connected"
            #self.state == 2

    # Perform a handshake to terminate a connection
    def disconnect(self):
        # Only disconnect if not already disconnected
        if self._state != 0:
            self.state = 3
            tries = 0
            # We use a default sequence number of 0
            seq_n = 0
            segment = FINSegment(seq_n, self._window)
            # Try to disconnect
            while self._connection_event.is_set() and tries < MAX_TRIES:
                self._lossy_layer.send_segment(segment.pack())
                tries += 1
                time.sleep(TIMEOUT_TIME)
            # Reset to default state regardless of server response
            self.state = 0
            self._connection_event.clear()
            print("-= Connection Terminated =-")

    # Clean up any state
    def close(self):
        self.state = 0
        self._connection_event.clear()
        self._lossy_layer.destroy()

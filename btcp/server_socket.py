# ------------------------
# Tom Aarsen   - s1027401
# Bart Janssen - s4630270
# ------------------------

import socket, random, time, threading, queue
from btcp.lossy_layer import LossyLayer
from btcp.btcp_socket import BTCPSocket
from btcp.constants import *
from btcp.btcp_segment import BTCPSegment, ACKSegment, SYNSegment, SYNACKSegment, FINSegment, FINACKSegment

# The bTCP server socket
# A server application makes use of the services provided by bTCP by calling accept, recv, and close

# States:
# 0: Default
# 1: Accepting
# 2: Sent SYNACK, waiting for ACK
# 3: Connection established

class BTCPServerSocket(BTCPSocket):
    def __init__(self, window, timeout, debug):
        super().__init__(window, timeout, debug, "Server")
        self._lossy_layer = LossyLayer(self, SERVER_IP, SERVER_PORT, CLIENT_IP, CLIENT_PORT)
        # Threading event for connections
        self._connection_event = threading.Event()
        self._disconnection_event = threading.Event()
        # Set default values
        self.buffer = queue.Queue(window)
        self.last_sent_ack_n = None
        self.last_ack = None
        self.receiving = True
        self.mutex = threading.Lock()
        self.stored_seq_n = []

    # Called by the lossy layer from another thread whenever a segment arrives
    def lossy_layer_input(self, segment):
        # Split segment into values
        segment_data, (c_ip, c_port) = segment
        # Unpack the segment into the corresponding values
        seq_n, ack_n, flags_int, window, data_length, checksum, body = BTCPSegment.unpack(segment_data)
        flags = BTCPSegment.convert_int_to_flags(flags_int)
        # Check whether this segment should be discarded
        out = BTCPSegment.get_checksum(segment_data)
        if out != 0:
            self.print("Corrupted Segment received. Discarding...")
            return
        
        # If we are in the "accepting" state and flag is SYN
        if (self.state == 1 or self.state == 2) and flags == {"SYN"}:
            # Set state to Sent SYNACK, waiting for ACK
            self.state = 2
            new_seq_n = random.randrange(0, 65535)
            new_ack_n = seq_n + 1
            self._lossy_layer.send_segment(SYNACKSegment(new_seq_n, new_ack_n, self._window).pack())
        
        # If we are in the "Sent SYNACK, waiting for ACK" state and flag is ACK
        elif self.state == 2 and flags == {"ACK"}:
            # Set state to Connection established
            self.state = 3
            # Stop accept() waiting
            self._connection_event.set()
            self.print("-= Connection Established =-")

        # If the client wants to disconnect, and sends a FIN
        # Only respond if connected or attempting to connect
        elif flags == {"FIN"} and (self.state == 2 or self.state == 3):
            if self._connection_event.is_set():
                self.print("-= Connection Terminated =-")
            # Set state to closed connection
            self.state = 0
            self._connection_event.clear()
            self._disconnection_event.set()
            # And send FINACK
            segment = FINACKSegment(self._window)
            self._lossy_layer.send_segment(segment.pack())
        
        # If the segment has no flags, it is data
        elif flags == set():
            # Only respond if this segment is the first, or follows a previously acked segment
            if (self.last_sent_ack_n is None and seq_n == 0) or seq_n == self.last_sent_ack_n:
                # Get new sequence numbers and acknowledgement numbers for the ACK
                new_seq_n = ack_n
                new_ack_n = (seq_n + data_length) % 65535
                # Store the new_ack_n, as the next segment from the client should have that value as its seq_n.
                self.last_sent_ack_n = new_ack_n
                
                # If the data length is 65534, then this is the final segment.
                if data_length == 65534:
                    if self.receiving:
                        self.print("Final segment received.")
                        self.receiving = False
                else:
                    # Otherwise, store the body in the buffer
                    with self.mutex:
                        self.buffer.put_nowait(body[:data_length])
                
                # Send the new ACK
                self.last_ack = ACKSegment(new_seq_n, new_ack_n, self._window - self.buffer.qsize())
                self._lossy_layer.send_segment(self.last_ack.pack())
            
            else:
                # If this segment is out of order, duplicated or something similar
                # eg, it isn't the segment we expect, then we send the last acknowledged segment.
                if self.last_ack:
                    self._lossy_layer.send_segment(self.last_ack.pack())

    # Wait for the client to initiate a three-way handshake
    def accept(self, blocked = True):
        # Set the state to 1, which lossy_layer_input can use to accept connection requests
        # from the client. By default wait until we are properly connected.
        self.state = 1
        if blocked:
            self._connection_event.wait()

    # Send any incoming data to the application layer
    def recv(self):
        # Get value from buffer, unless empty, and only if the state is connected.
        # If not connected, throw an exception.
        if self.state == 3 or not self.buffer.empty():
            try:
                with self.mutex:
                    return self.buffer.get_nowait()
            except queue.Empty:
                return bytearray()
        return bytearray()

    # Clean up any state
    def close(self):
        # Reset all variables to defaults
        self._connection_event.clear()
        self.state = 0
        self.stored_seq_n = []
        self.last_ack = None
        self.buffer.empty()
        # Destroy lossy layer thread
        self._lossy_layer.destroy()

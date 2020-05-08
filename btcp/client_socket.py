# ------------------------
# Tom Aarsen   - s1027401
# Bart Janssen - s4630270
# ------------------------

import time, threading
from btcp.btcp_socket import BTCPSocket
from btcp.lossy_layer import LossyLayer
from btcp.constants import *
from btcp.btcp_segment import BTCPSegment, ACKSegment, SYNSegment, SYNACKSegment, FINSegment

# bTCP client socket
# A client application makes use of the services provided by bTCP by calling connect, send, disconnect, and close

# States:
# 0: Default 
# 1: SYN sent, waiting on SYNACK
# 2: SYNACK received, sent ACK, should be connected
# 3: FIN Sent, attempting to disconnect
# 4: Sending data

class BTCPClientSocket(BTCPSocket):
    def __init__(self, window, timeout, debug, retries):
        super().__init__(window, timeout, debug, "Client")
        self.retries = retries
        self._lossy_layer = LossyLayer(self, CLIENT_IP, CLIENT_PORT, SERVER_IP, SERVER_PORT)
        # Threading event for connections
        self._connection_event = threading.Event()
        # Set default values
        self.receive_window = window
        self.last_acked = 0
        self.last_sent = 0
        self.x = []
        self.duplicate = 0
        self.last_duplicate_ack = -1
        self.mutex = threading.Lock()

    # Called by the lossy layer from another thread whenever a segment arrives. 
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
        
        # Update the receive window to the advertised window by the server
        self.receive_window = window

        # If in state "SYN sent, waiting on SYNACK" and flag is SYNACK
        if self.state == 1 and flags == {"SYN", "ACK"} and ack_n in self.x:
            new_seq_n = ack_n
            new_ack_n = seq_n + 1
            self._lossy_layer.send_segment(ACKSegment(new_seq_n, new_ack_n, self._window).pack())
            # Set state to connected
            self.state = 2
            self._connection_event.set()
            self.print("-= Connection Established =-")

        # Receive FINACK from Server after attempting to disconnect
        elif self.state == 3 and flags == {"FIN", "ACK"}:
            # Disconnect, state will already be set to 0 in disconnect()
            self.print("-= Connection Terminated =-")
            self._connection_event.clear()

        # If there is an ACK from the Server in response to our sending
        elif flags == {"ACK"} and self.state == 4:
            # Translate the ack_n (ranging from 0..65535), to a value from 0..n_segments - 1.
            # Do this using the list of sequence numbers. If the ack_n is not in the list, 
            # then it is the ACK for the final segment, and we are done sending.
            try:
                new_ack = self.seq_ns.index(ack_n)
                # Check for a duplicate ack. 
                # Note that we only allow duplicate ACKs once per sequence number.
                if self.last_acked == new_ack and self.last_duplicate_ack < new_ack:
                    self.duplicate += 1
                else:
                    self.last_acked = max(new_ack, self.last_acked)
                    self.duplicate = 0
            except ValueError:
                self.last_acked = -1
                self.duplicate = 0
            
            # If there is a triple duplicate ACK, get a hold of the mutex for send_times, 
            # last_sent and last_acked, and hit the timeout.
            if self.duplicate >= 3:
                self.print(f"Triple Duplicate ACK received. Resetting last_sent from {self.last_sent} to {self.last_acked}")
                self.duplicate = 0
                self.last_duplicate_ack = new_ack
                with self.mutex:
                    # Reset time dictionary
                    self.send_times = {}
                    # Reset last sent to last acked to resend segments
                    self.last_sent = self.last_acked

    # Perform a three-way handshake to establish a connection
    def connect(self):
        # Set state to "SYN sent, waiting on SYNACK"
        self.state = 1
        tries = 0
        # Send at most self.retries connection attempts until we are connected.
        while not self._connection_event.is_set() and tries < self.retries:
            segment = SYNSegment(self._window)
            # Note that we store a list of sequence numbers + 1.
            # If the server has one of these values in the ack_n field of their ACKSYN,
            # then we proceed with the threeway handshake.
            self.x.append(segment.seq_n + 1)
            self._lossy_layer.send_segment(segment.pack())
            tries += 1
            time.sleep(self._timeout / 1000)
        # If afterward we still aren't connected, reset 
        if not self._connection_event.is_set():
            self.close()
            raise Exception("Could not connect to Server.")
    
    # Send data originating from the application in a reliable way to the server
    def send(self, file_obj):
        # If the state is "Connected"
        if self.state == 2:
            # Set state to "Sending data"
            self.state = 4

            # Get all data, and split it up into chunks of at most 1008 bytes
            byte_arr = bytearray(file_obj.read().encode())
            n = 1008

            # Get a list of BTCPSegments to send with actual data
            btcp_segments = []
            for i in range(0, len(byte_arr), n):
                data_length = len(byte_arr[i:i + n])
                seq_n = i % 65535
                ack_n = (seq_n + data_length) % 65535
                btcp_segments.append(BTCPSegment(seq_n, ack_n, self._window, byte_arr[i:i + n]))
            
            # Add one more BTCPSegment, with no data, modified to have a data_length of 65535
            # This segment acts as a "final" segment.
            final_seq_n = (i + data_length) % 65535
            final_ack_n = (final_seq_n + 1008) % 65535
            btcp_segments.append(BTCPSegment(final_seq_n, final_ack_n, self._window, b""))
            btcp_segments[-1].data_length = 65534

            # Get list of sequence numbers, number of segments total and a dict to store timeout times
            self.seq_ns = [segment.seq_n for segment in btcp_segments]
            self.n_segments = len(self.seq_ns)
            self.send_times = {}
            
            # Loop until self.last_acked is -1, which only occurs when the very last segment is ACKed
            while self.last_acked != -1:
                # Ensure mutual exclusion of this portion. The lossy layer thread will rarely attempt to access this lock
                # That thread only wants this mutex when there is a triple duplicate ACK and wants to reset
                with self.mutex:
                    # Get number of segments to send
                    num_to_send = min(
                        self.receive_window - (self.last_sent - self.last_acked), 
                        self.n_segments - self.last_sent
                    )

                    for n in range(num_to_send):
                        # Store time sent in dict for this segment
                        self.send_times[self.last_sent] = time.time()
                        # Send Segment and increment self.last_sent
                        self._lossy_layer.send_segment(btcp_segments[self.last_sent].pack())
                        self.last_sent += 1

                    # Shrink timer dictionary by removing acked segments
                    self.send_times = {key: self.send_times[key] for key in self.send_times if key > self.last_acked}

                    # If the timer dict is not empty
                    if self.send_times:
                        # If any segment is going to be timed out, it will be the first value in the send_times dictionary
                        # In Python 3.6+, dicts are guaranteed to be ordered.
                        seq_n, send_time = next(iter(self.send_times.items()))
                        if time.time() > send_time + (self._timeout / 1000):
                            self.print(f"Timeout hit. Resetting last_sent from {self.last_sent} to {self.last_acked}")
                            # Reset dictionary
                            self.send_times = {}
                            # Reset last sent to last acked to resend segments
                            self.last_sent = self.last_acked
        else:
            self.close()
            raise Exception("Not Connected to Server, cannot send")

    # Perform a handshake to terminate a connection
    def disconnect(self):
        # Only disconnect if not already disconnected
        if self._state != 0:
            self.state = 3
            tries = 0
            # We use a default sequence number of 0
            seq_n = 0
            segment = FINSegment(seq_n, self._window)
            # Send at most self.retries disconnection attempts until we are disconnected.
            while self._connection_event.is_set() and tries < self.retries:
                self._lossy_layer.send_segment(segment.pack())
                tries += 1
                time.sleep(self._timeout / 1000)
            # Reset to default state regardless of server response
            self.state = 0
            self._connection_event.clear()

    # Clean up any state
    def close(self):
        # Reset all variables to defaults
        self._connection_event.clear()
        self.state = 0
        self.receive_window = self._window
        self.last_acked = 0
        self.last_sent = 0
        self.x = []
        self.duplicate = 0
        self.last_duplicate_ack = -1
        # Destroy lossy layer thread
        self._lossy_layer.destroy()

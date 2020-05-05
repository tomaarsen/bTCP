import socket, random, time, threading, queue
from btcp.lossy_layer import LossyLayer
from btcp.btcp_socket import BTCPSocket
from btcp.constants import *
from btcp.btcp_segment import BTCPSegment, ACKSegment, SYNSegment, SYNACKSegment, FINSegment, FINACKSegment

# The bTCP server socket
# A server application makes use of the services provided by bTCP by calling accept, recv, and close
class BTCPServerSocket(BTCPSocket):
    def __init__(self, window, timeout):
        super().__init__(window, timeout)
        self._connection_event = threading.Event()
        self._lossy_layer = LossyLayer(self, SERVER_IP, SERVER_PORT, CLIENT_IP, CLIENT_PORT)
        # States:
        # 0: Default
        # 1: Accepting
        # 2: Sent SYNACK, waiting for ACK
        # 3: Connection established
        # 4: Receiving data
        self.buffer = queue.Queue(window)

    # Called by the lossy layer from another thread whenever a segment arrives
    def lossy_layer_input(self, segment):
        segment_data, (c_ip, c_port) = segment
        seq_n, ack_n, flags_int, window, data_length, checksum, body = BTCPSegment.unpack(segment_data)
        flags = BTCPSegment.convert_int_to_flags(flags_int)
        # Check checksum
        out = BTCPSegment.in_cksum(segment_data)
        print(f"R: {str(flags):<15}, Checksum Output: {out}, Checksum Value: {checksum}")
        if out != 0:
            print(f"Segment discarded as Checksum output: {out}")
            return

        # If we are in the "accepting" state and flag is SYN
        if self.state == 1 and flags == {"SYN"}:
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
            print("-= Connection Established =-")

        # If the client wants to disconnect, and sends a FIN
        elif flags == {"FIN"}:
            # Set state to closed connection
            self.state = 0
            self._connection_event.clear()
            print("-= Connection Terminated =-")
            # And send FINACK
            segment = FINACKSegment(self._window)
            self._lossy_layer.send_segment(segment.pack())
        
        else:# self.state == 4:
            print(f"Segment with body {body[:data_length]} received.")
            #self.buffer.append(body[:data_length])
            try:
                self.buffer.put_nowait(body[:data_length])
            except queue.Full:
                # TODO:
                pass
            self._lossy_layer.send_segment(ACKSegment(ack_n, (seq_n + data_length) % 65535, self._window - self.buffer.qsize()).pack())

    # Wait for the client to initiate a three-way handshake
    def accept(self):
        self.state = 1
        self._connection_event.wait()

    # Send any incoming data to the application layer
    def recv(self):
        if self.state == 3:
            try:
                return self.buffer.get()
            except queue.Empty:
                return bytearray()
            # Set state to receiving data
            #self.state = 4

            #"""
            #a = b""
            #while not self._connection_event.is_set() or not self.buffer.empty():
            #    a += self.buffer.get(timeout=0.1)
            #"""
            # TODO: Rework this blocking
            """
            try:
                while 1:
                    time.sleep(1)
            except KeyboardInterrupt:
                import pdb; pdb.set_trace()
            """
        else:
            # TODO: Rework
            raise Exception("Not Connected to client, cannot receive")

    # Clean up any state
    def close(self):
        self.state = 0
        self._lossy_layer.destroy()

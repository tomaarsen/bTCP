# ------------------------
# Tom Aarsen   - s1027401
# Bart Janssen - s4630270
# ------------------------

import struct, random
import numpy as np

class BTCPSegment:
    def __init__(self, seq_n: int, ack_n: int, window: int, data: bytes):
        super().__init__()
        self.seq_n = seq_n
        self.ack_n = ack_n
        self.flags = {
            "ACK": 0,
            "SYN": 0,
            "FIN": 0
        }
        self.byte_flags = self.convert_flags_to_int()
        self.window = window
        self.data_length = len(data)
        self.data = data

    def convert_flags_to_int(self):
        # ACK SYN FIN
        # So, ACK SYN is
        # 0000 0110
        # and FIN is
        # 0000 0001
        val = 0
        if self.flags["ACK"]:
            val += 4
        if self.flags["SYN"]:
            val += 2
        if self.flags["FIN"]:
            val += 1
        return val

    @staticmethod
    def convert_int_to_flags(val: int) -> set:
        # ACK SYN FIN
        # So, ACK SYN is
        # 0000 0110
        # and FIN is
        # 0000 0001
        flags = set()
        if val >= 4:
            val -= 4
            flags.add("ACK")
        if val >= 2:
            val -= 2
            flags.add("SYN")
        if val >= 1:
            val -= 1
            flags.add("FIN")
        return flags

    @staticmethod
    def get_checksum(packet):
        # Round down to nearest multiple of 2
        n = (len(packet) // 2) * 2
        checksum = 0

        # Range from 0 to count with steps of 2 
        for i in range(0, n, 2):
            checksum += packet[i + 1] * 256 + packet[i]
            checksum &= 0xffffffff

        # If len(packet) is not a multiple of two, add the final packet
        if n < len(packet):
            checksum += packet[-1]
            checksum &= 0xffffffff

        # Remove overflow
        checksum = (checksum >> 16) + (checksum & 0xffff)
        checksum += (checksum >> 16)
        # Flip and remove overflow
        out = ~checksum
        out &= 0xffff
        out = out >> 8 | (out << 8 & 0xff00)
        return out

    def _pack(self, checksum = 0):
        # Place all values with the given checksum in a struct of the right format
        return struct.pack("!HHBBHH1008s", self.seq_n, 
                                     self.ack_n, 
                                     self.byte_flags, 
                                     self.window,
                                     self.data_length,
                                     checksum,
                                     self.data)
    
    def pack(self):
        # Get the segment with an empty checksum
        data = self._pack()
        # Get the checksum over this segment
        checksum = self.get_checksum(data)
        # And get the segment with the actual checksum value filled in.
        return self._pack(checksum)

    @staticmethod
    def unpack(data):
        # Unpack a segment using the format
        return struct.unpack("!HHBBHH1008s", data)

class SYNSegment(BTCPSegment):
    def __init__(self, window):
        # For SYN segments, seq_n is random
        seq_n = random.randrange(0, 65535)
        ack_n = 0
        super().__init__(seq_n, ack_n, window, b"")
        self.flags["SYN"] = 1
        self.byte_flags = self.convert_flags_to_int()

class ACKSegment(BTCPSegment):
    def __init__(self, seq_n, ack_n, window):
        super().__init__(seq_n, ack_n, window, b"")
        self.flags["ACK"] = 1
        self.byte_flags = self.convert_flags_to_int()

class FINSegment(BTCPSegment):
    def __init__(self, seq_n, window):
        ack_n = 0
        super().__init__(seq_n, ack_n, window, b"")
        self.flags["FIN"] = 1
        self.byte_flags = self.convert_flags_to_int()

class SYNACKSegment(BTCPSegment):
    def __init__(self, seq_n, ack_n, window):
        # For SYN segments, seq_n is random
        super().__init__(seq_n, ack_n, window, b"")
        self.flags["ACK"] = 1
        self.flags["SYN"] = 1
        self.byte_flags = self.convert_flags_to_int()

class FINACKSegment(BTCPSegment):
    def __init__(self, window):
        # For FINACK segments, seq_n and ack_n are both unused, and are hence set to 0
        seq_n = 0
        ack_n = 0
        super().__init__(seq_n, ack_n, window, b"")
        self.flags["ACK"] = 1
        self.flags["FIN"] = 1
        self.byte_flags = self.convert_flags_to_int()


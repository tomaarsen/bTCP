
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
        self.byte_flags = self.convert_flags()
        self.window = window
        self.data_length = len(data)
        self.data = data

    def convert_flags(self):
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

    """
    @staticmethod
    def in_cksum(str_):
        #str_ = bytearray(str_)
        csum = 0
        countTo = (len(str_) // 2) * 2

        for count in range(0, countTo, 2):
            thisVal = str_[count+1] * 256 + str_[count]
            csum = csum + thisVal
            csum = csum & 0xffffffff

        if countTo < len(str_):
            csum = csum + str_[-1]
            csum = csum & 0xffffffff

        csum = (csum >> 16) + (csum & 0xffff)
        csum = csum + (csum >> 16)
        answer = ~csum
        answer = answer & 0xffff
        answer = answer >> 8 | (answer << 8 & 0xff00)
        return answer
    """

    @staticmethod
    def in_cksum(data, sum_var=0):
        # make 16 bit words out of every two adjacent 8 bit words in the packet
        # and add them up
        #print(data)
        #data = data.decode("utf-8")
        for i in range(0,len(data),2):
            sum_var += ((data[i] << 8) & 0xF0) + (data[i+1] & 0xF)

        # take only 16 bits out of the 32 bit sum and add up the carries
        while (sum_var >> 16) > 0:
            sum_var = (sum_var & 0xFF) + (sum_var >> 16)

        #print(sum_var)
        # one's complement the result
        sum_var = ~sum_var

        return sum_var & 0xFF

    """
    @staticmethod
    def adding(x, y):
        z = x+y
        if z > 2**16 - 1:
            z = (z & 2**16 - 1) + 1
        return z

    # computes the Internet checksum
    @staticmethod
    def in_cksum(data):
        addition = 0
        
        if len(data) % 2 != 0:
            bytes(1) + data

        integers = []
        
        for i in range(0, len(data), 2):
            y = int.from_bytes(data[i:i+1], byteorder="big")
            integers.append(y)

        addition = BTCPSegment.adding(integers[0], integers[1])

        for i in integers[2:]:
            addition = BTCPSegment.adding(addition, i)

        return ~np.uint16(addition)
    """

    def _pack(self, checksum = 0):
        return struct.pack("HHBBHH1008s", self.seq_n, 
                                     self.ack_n, 
                                     self.byte_flags, 
                                     self.window,
                                     self.data_length,
                                     checksum,
                                     self.data)
    
    def pack(self):
        data = self._pack()
        #print(data)
        #breakpoint()
        checksum = self.in_cksum(data)
        #print(checksum)
        return self._pack(checksum)

    @staticmethod
    def unpack(data):
        return struct.unpack("HHBBHH1008s", data)

class SYNSegment(BTCPSegment):
    def __init__(self, window):
        # For SYN segments, seq_n is random
        seq_n = random.randrange(0, 65535)
        ack_n = 0
        super().__init__(seq_n, ack_n, window, b"")#Hello how are you doing, this is random text to fill up this data section")
        self.flags["SYN"] = 1
        self.byte_flags = self.convert_flags()

class ACKSegment(BTCPSegment):
    def __init__(self, seq_n, ack_n, window):
        super().__init__(seq_n, ack_n, window, b"")
        self.flags["ACK"] = 1
        self.byte_flags = self.convert_flags()

class FINSegment(BTCPSegment):
    def __init__(self, seq_n, window):
        ack_n = 0
        super().__init__(seq_n, ack_n, window, b"")
        self.flags["FIN"] = 1
        self.byte_flags = self.convert_flags()

class SYNACKSegment(BTCPSegment):
    def __init__(self, seq_n, ack_n, window):
        # For SYN segments, seq_n is random
        super().__init__(seq_n, ack_n, window, b"")
        self.flags["ACK"] = 1
        self.flags["SYN"] = 1
        self.byte_flags = self.convert_flags()

#"""
if __name__ == "__main__":
    segment = SYNSegment(100)
    checksum = BTCPSegment.unpack(segment.pack())[-2]
    #print(checksum)
    out = BTCPSegment.in_cksum(segment.pack(), checksum)
    #out2 = BTCPSegment.in_cksum(segment.pack())

    # 59803
    # 65513
    breakpoint()
#"""

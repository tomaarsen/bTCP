# ------------------------
# Tom Aarsen   - s1027401
# Bart Janssen - s4630270
# ------------------------

import unittest, threading
import socket
import time
import sys

timeout = 300
winsize = 100
retries = 20
debug = False
intf="lo"
netem_add="sudo tc qdisc add dev {} root netem".format(intf)
netem_change="sudo tc qdisc change dev {} root netem {}".format(intf,"{}")
netem_del="sudo tc qdisc del dev {} root netem".format(intf)

"""run command and retrieve output"""
def run_command_with_output(command, input=None, cwd=None, shell=True):
    import subprocess
    try:
        process = subprocess.Popen(command, cwd=cwd, shell=shell, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    except Exception as inst:
        print("problem running command : \n   ", str(command))

    [stdoutdata, stderrdata]=process.communicate(input)  # no pipes set for stdin/stdout/stdout streams so does effectively only just wait for process ends  (same as process.wait()

    if process.returncode:
        print(stderrdata)
        print("problem running command : \n   ", str(command), " ",process.returncode)

    return stdoutdata

"""run command with no output piping"""
def run_command(command,cwd=None, shell=True):
    import subprocess
    process = None
    try:
        process = subprocess.Popen(command, shell=shell, cwd=cwd)
        print(str(process))
    except Exception as inst:
        print("1. problem running command : \n   ", str(command), "\n problem : ", str(inst))

    process.communicate()  # wait for the process to end

    if process.returncode:
        print("2. problem running command : \n   ", str(command), " ", process.returncode)

from btcp.server_socket import BTCPServerSocket
from btcp.client_socket import BTCPClientSocket

class TestbTCPFramework(unittest.TestCase):
    """Test cases for bTCP"""
    
    def setUp(self):
        """Prepare for testing"""
        # default netem rule (does nothing)
        run_command(netem_add)
        
        # launch localhost server
        self.serv_socket = BTCPServerSocket(args.window, args.timeout, args.debug)
        self.serv_socket.accept(blocked=False)

    def tearDown(self):
        """Clean up after testing"""
        # clean the environment
        run_command(netem_del)
        
        # close server
        self.serv_socket.close()

    def _test_ideal_network(self, msg, a):
        # server receives content from client
        self.serv_socket._connection_event.wait()
        while self.serv_socket.receiving or not self.serv_socket.buffer.empty():
            a += self.serv_socket.recv()

    def test_ideal_network(self, msg="Over ideal network"):
        """reliability over an ideal framework"""
        # setup environment (nothing to set)
        # launch localhost client connecting to server
        client_socket = BTCPClientSocket(args.window, args.timeout, args.debug, args.retries)
        client_socket.connect()
        
        # Sleep a bit before starting a thread
        time.sleep(0.2)
        # Create a bytearray to be filled by the thread.
        a = bytearray()
        t = threading.Thread(target=lambda: self._test_ideal_network(msg, a))
        t.start()

        # client sends content to server
        with open("input.file", "r") as f:
            client_socket.send(f)
        
        # Join the thread to wait until we are done filling a
        t.join()

        # content received by server matches the content sent by client
        with open("input.file", "r") as f:
            self.assertEqual(bytearray(f.read().encode()), a, msg)
    
    def test_flipping_network(self):
        # reliability over network with bit flips 
        # (which sometimes results in lower layer packet loss)
        # setup environment
        run_command(netem_change.format("corrupt 1%"))
        self.test_ideal_network("Over 1% corrupt network")

    def test_duplicates_network(self):
        # reliability over network with duplicate packets
        # setup environment
        run_command(netem_change.format("duplicate 10%"))
        self.test_ideal_network("Over 10% duplicate network")

    def test_lossy_network(self):
        # reliability over network with packet loss
        # setup environment
        run_command(netem_change.format("loss 10% 25%"))
        self.test_ideal_network("Over lossy network")

    def test_reordering_network(self):
        # reliability over network with packet reordering
        # setup environment
        run_command(netem_change.format("delay 20ms reorder 25% 50%"))
        self.test_ideal_network("Over delayed, reordering network")

    def test_delayed_network(self):
        # reliability over network with delay relative to the timeout value
        # setup environment
        run_command(netem_change.format("delay "+str(timeout/3)+"ms 20ms"))
        self.test_ideal_network("Over delayed network")
    
    def test_allbad_network(self):
        # reliability over network with all of the above problems
        # setup environment
        run_command(netem_change.format("corrupt 1% duplicate 10% loss 10% 25% delay 20ms reorder 25% 50%"))
        self.test_ideal_network("Over all bad network")
    
if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="bTCP tests")
    parser.add_argument("-w", "--window", help="Define bTCP window size used", type=int, default=winsize)
    parser.add_argument("-t", "--timeout", help="Define the timeout value used (ms)", type=int, default=timeout)
    parser.add_argument("-d", "--debug", help="Whether to print debugging statements", default=debug)
    parser.add_argument("-r", "--retries", help="How many times to retry connecting/disconnecting", default=retries)
    args, extra = parser.parse_known_args()
    timeout = args.timeout
    winsize = args.window
    retries = args.retries
    debug = args.debug

    # Pass the extra arguments to unittest
    sys.argv[1:] = extra

    # Start test suite
    unittest.main()

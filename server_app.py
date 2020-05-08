#!/usr/local/bin/python3
# ------------------------
# Tom Aarsen   - s1027401
# Bart Janssen - s4630270
# ------------------------

import argparse, time, threading
from btcp.server_socket import BTCPServerSocket


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-w", "--window", help="Define bTCP window size", type=int, default=100)
    parser.add_argument("-t", "--timeout", help="Define bTCP timeout in milliseconds", type=int, default=300)
    parser.add_argument("-d", "--debug", help="Whether to print output", type=int, default=True)
    parser.add_argument("-o", "--output", help="Where to store the file", default="output.file")
    args = parser.parse_args()

    # Create a bTCP server socket
    socket = BTCPServerSocket(args.window, args.timeout, args.debug)

    # Wait for connection from client
    socket.accept()
    
    # Write or override output file with new data until buffer is empty 
    # and server socket is no longer receiving data
    with open(args.output, "w+") as f:
        while socket.receiving or not socket.buffer.empty():
            f.write(socket.recv().decode())
    # Wait a bit before closing, client might be able to disconnect gracefully, 
    # and normally a server wouldn't just shut down immediately after receiving data.
    socket._disconnection_event.wait(timeout=5)
    
    # Clean up any state
    socket.close()

main()

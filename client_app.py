#!/usr/local/bin/python3
# ------------------------
# Tom Aarsen   - s1027401
# Bart Janssen - s4630270
# ------------------------

import argparse, time
from btcp.client_socket import BTCPClientSocket


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-w", "--window", help="Define bTCP window size", type=int, default=100)
    parser.add_argument("-t", "--timeout", help="Define bTCP timeout in milliseconds", type=int, default=300)
    parser.add_argument("-d", "--debug", help="Whether to print debugging statements", type=int, default=True)
    parser.add_argument("-r", "--retries", help="How many times to retry connecting/disconnecting", default=10)
    parser.add_argument("-i", "--input", help="File to send", default="input.file")
    args = parser.parse_args()

    # Create a bTCP client socket with the given window size and timeout value
    socket = BTCPClientSocket(args.window, args.timeout, args.debug, args.retries)
    
    socket.connect()

    with open(args.input, "r") as f:
        socket.send(f)

    socket.disconnect()

    # Clean up any state
    socket.close()


main()

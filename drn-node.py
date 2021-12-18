from colorama import Fore, Back
import threading
import sys
import argparse
import logging
import socket
import json
import random
import time

commands = {

}

logger = logging.getLogger('drn-node')

class Node:
    def __init__(self, ip, port, 
                node_id: int, directly_connected: bool = True, 
                client: bool = True, sock: socket.socket = None, 
                hostname: str = None, public_key: str = None):
        self.ip = ip
        self.port = port
        self.directly_connected = directly_connected
        self.client = client
        self.node_id = node_id
        self.sock = sock
        self.recent_reqs = {}
        self.hostname = hostname
        self.thread = threading.Thread(target=self.handle_connection, args=(sock,))
        self.thread.start()
        logger.debug('Created node %s:%s (%s)', ip, port, node_id)
    
    def receive(self):
        data = b""
        while True:
            recv = self.sock.recv(1024)
            if not recv:
                break
            data += recv
        return data.decode()
    
    def wait_for_resp(self, reqid):
        for _ in range(50):
            if reqid in self.recent_reqs and self.recent_reqs[reqid]:
                resp = self.recent_reqs[reqid]
                self.recent_reqs[reqid] = None
                return resp
            time.sleep(0.1)
        logger.error('%s: %s: Timeout waiting for response', self.node_id, reqid)
        del self.recent_reqs[reqid]
        return None

    def handle_connection(self):
        while True:
            try:
                data = self.receive()
                if data:
                    logger.debug('%s: Received %s', self.node_id, data)
                    resp = json.loads(data.decode())
                    cmd = resp[0]
                    args = resp[2:]
                    reqid = resp[1]
                    if reqid in self.recent_reqs:
                        self.recent_reqs[reqid] = resp
                    self.exec_command(reqid, cmd, *args)
            except Exception as e:
                logger.exception('Error in %s', self.node_id)
                break

    def exec_command(self, reqid, command, *args):
        if command in commands:
            self.recent_reqs[reqid] = None
            commands[command](self, reqid, *args)
        else:
            logger.error('%s: Unknown command %s', self.node_id, command)
    
    def send(self, command, *args):
        reqid = ''.join(random.choice('0123456789abcdef') for _ in range(8))
        data = json.dumps([command, reqid, *args])
        logger.debug('%s: Sending %s', self.node_id, data)
        self.sock.sendall(data.encode())

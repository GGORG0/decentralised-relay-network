from colorama import Fore, Back
import threading
import sys
import argparse
import logging
import socket
import json
import random

connected_nodes = {} # ip: str, client: socket.socket
discovered_domains = {}

def new_node(client, args):
    if args[0] not in connected_nodes:
        connected_nodes[args[0]] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connected_nodes[args[0]].connect((args[0], int(args[1])))
        logging.getLogger('drn-node').debug('Added node at %s', args[0])
        threading.Thread(target=new_connection, args=(connected_nodes[args[0]],args[0])).start()
        for n in connected_nodes.values():
            if n != client:
                n.send(json.dumps(['NEWNODE', args[0]]).encode())

def new_nodes(client, args):
    for n in args[0]:
        if n not in connected_nodes:
            connected_nodes[n] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            connected_nodes[n].connect((n, int(args[1])))
            logging.getLogger('drn-node').debug('Added node at %s', n)
            threading.Thread(target=new_connection, args=(connected_nodes[n],n)).start()
            for n in connected_nodes.values():
                if n != client:
                    n.send(json.dumps(['NEWNODE', n]).encode())

def discover_domain(client, args):
    if args[0] in discovered_domains:
        client.send(json.dumps(['NEWDOMAIN', args[0], discovered_domains[args[0]]]).encode())
    else:
        randomnode = random.choice(list(connected_nodes.values()))
        randomnode.send(json.dumps(['DISCOVERDOMAIN', args[0]]).encode())
        resp = json.loads(randomnode.recv(1024).decode())
        if resp[0] == 'NEWDOMAIN':
            client.send(json.dumps(['NEWDOMAIN', args[0], resp[2]]).encode())

def new_domain(client, args):
    discovered_domains[args[0]] = args[1]

commands = {
    'GETNODES': lambda client, args: client.send(json.dumps(['NEWNODES', list(connected_nodes.keys())]).encode()),
    'NEWNODE': new_node,
    'NEWNODES': new_nodes,
    'SENDTONODE': lambda client, args: connected_nodes[args[0]].send(args[1].encode()),
    'SENDTOALL': lambda client, args: [connected_nodes[ip].send(args[0].encode()) for ip in connected_nodes.keys()],
    'MESSAGE': lambda client, args: logging.getLogger('drn-node').info('%s: %s', client.getpeername()[0], args[0]),
    'PING': lambda client, args: client.send(b'#PONG'),
    'DISCOVERDOMAIN': discover_domain,
    'NEWDOMAIN': new_domain,
    'GETDOMAINS': lambda client, args: client.send(json.dumps(discovered_domains).encode()),
}

def new_connection(client, address):
    for n in connected_nodes.keys():
        if n != address:
            connected_nodes[n].send(json.dumps(['NEWNODE', address]).encode())
    while True:
        try:
            data = client.recv(1024)
            if data:
                logging.getLogger('drn-node').debug('%s: Received data: %s', address, data.decode())
                if data.decode().startswith('#'):
                    logging.getLogger('drn-node').info('%s: Received comment %s', address, data.decode())
                else:
                    dat = json.loads(data.decode())
                    if dat[0] in commands:
                        logging.getLogger('drn-node').debug('%s: Received command %s', address, dat[0])
                        commands[dat[0]](client, dat[1:] if len(dat) > 1 else [])
                    else:
                        logging.getLogger('drn-node').error('%s: Unknown command %s', address, dat[0])
            else:
                logging.getLogger('drn-node').info('%s: Connection closed', address)
                client.close()
                del connected_nodes[address]
                break
        except Exception:
            logging.getLogger('drn-node').exception('Error in %s', address)
            break
    
# def cmdline():
#     while True:
#         cmd = input()
#         if cmd == 'send':
#             connected_nodes[input('node: ')].send(input('> ').encode())
#         elif cmd == 'ping':
#             connected_nodes[input('node: ')].send(b'["PING"]')
#         elif cmd == 'getnodes':
#             print(list(connected_nodes.keys()))
#         elif cmd == 'getdomains':
#             print(discovered_domains)
#         elif cmd == 'getdomain':
#             print(discovered_domains[input('ip: ')])
#         elif cmd == 'newdomain':
#             new_domain(None, [input('domain: '), input('ip: ')])
#         elif cmd == 'newnode':
#             new_node(None, [input('ip: '), input('port: ')])
#         elif cmd == 'help':
#             print('send: send data to a node')
#             print('ping: ping a node')
#             print('getnodes: get a list of all connected nodes')
#             print('getdomains: get a list of all discovered domains')
#             print('getdomain: get a list of all discovered domains')
#             print('newdomain: add a new discovered domain')
#             print('newnode: add a new node')
#             print('help: show this help')
#         else:
#             print('Unknown command')

def main():
    print(Fore.RED + """
888888ba   888888ba  888888ba  
88    `8b  88    `8b 88    `8b 
88     88 a88aaaa8P' 88     88 
88     88  88   `8b. 88     88 
88    .8P  88     88 88     88 
8888888P   dP     dP dP     dP 

Welcome to the Decentralised Relay Network node server
""" + Fore.RESET)

    parser = argparse.ArgumentParser(description='Decentralised Relay Network Node')
    parser.add_argument('-p', '--lport', help='Port to listen on', default=9357)
    parser.add_argument('-d', '--debug', help='Debug mode', action='store_true')
    parser.add_argument('-v', '--version', help='Print version and exit', action='store_true')
    # parser.add_argument('-l', '--log', help='Path to log file', default='drn-node.log')
    parser.add_argument('nip', help='IP address of another node to connect to', nargs='?', default=None)
    parser.add_argument('nport', help='Port of the node to connect to', nargs='?', default=9357)
    args = parser.parse_args()

    if args.version:
        print('Version: 0.0.1')
        sys.exit(0)

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format='[%(asctime)s %(levelname)s] %(message)s')
    logger = logging.getLogger('drn-node')

    logger.log(logging.INFO, 'Starting DRN Node')

    s = None
    if args.nip and args.nport:
        logger.debug('Connecting to node at %s:%s', args.nip, args.nport)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((args.nip, int(args.nport)))
            s.send(json.dumps(['GETNODES']).encode())
            connected_nodes[args.nip] = s
            threading.Thread(target=new_connection, args=(s, args.nip)).start()
        except socket.error as e:
            logger.error('Could not connect to node at %s: %s', args.nip, e)

        logger.debug('Connected to node at %s:%s', args.nip, args.nport)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('', int(args.lport)))
    server.listen(5)

    logger.log(logging.INFO, 'Listening on port %s', args.lport)

    # threading.Thread(target=cmdline).start()

    threads = []

    while True:
        try:
            client, address = server.accept()
            logger.info('Accepted connection from %s', address)
            connected_nodes[address[0]] = client
            threads.append(threading.Thread(target=new_connection, args=(client,address[0])).start())
        except KeyboardInterrupt:
            logger.info('Shutting down')
            if s:
                s.close()
            server.close()
            for t in threads:
                if t and t.is_alive():
                    t.join()
            sys.exit(0)


if __name__ == '__main__':
    main()
    
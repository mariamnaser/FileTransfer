"""
/*******************************************************************************
 * Name          : FileTransfer.py
 * Author        : Mariam Naser
 * Date          : April 25, 2023
 * Description   : TCP and UDP File Transfer
 ******************************************************************************/
"""
##Libraries 
import contextlib
import socket
import sys
import getopt
import re
import os
import pickle
import time
import threading
from tabulate import tabulate

##Variables 
serverIPmain = 'localhost'
serverport = 5053
serveradd = (serverIPmain, serverport)
exit_flag = False
clientTable = []
filesOffered = []
clientList = []
serverstat = True
dir = None


##Varifying Input
def verifyport(port): 
    if not isinstance(port, str):
        sys.exit(f">>> [Invalid: <{port}> Input Not String]")
    try:
        port = int(port)
    except ValueError:
        sys.exit(f">>> [Invalid: <{port}> Port Number Not Integer]")
    if port < 1024 or port > 65535:
        sys.exit(f">>> [Invalid: <{port}> Port Number Not In Range]")
    port = str(port)
    return True
def verifyip(ip):
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        sys.exit(f">>> [Invalid: <{ip}> Incorrect IP Formate]")
    parts = ip.split('.')
    for part in parts:
        if int(part) < 0 or int(part) > 255:
            sys.exit(">>> [Invalid: Invalid IP Address]")
    return True
##Table Management 
def broadcast(addresses, table):
    for address in addresses:
        UDP_send(address[1:], table, "")
    print("Broadcast Completed!")

def count_unique_names(table):
    names = set()
    for row in table:
        names.add(row[1])
    return len(names)

def set_exit_flag(flag):
    global exit_flag
    exit_flag = flag

##UDP Connection
def UDP_send(address, message, onsuccess):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        chunks = [message[i:i+1024] for i in range(0, len(message), 1024)]
        for i, chunk in enumerate(chunks):
            data = pickle.dumps(chunk)
            attempts = 0
            while attempts <= 3:
                try:
                    sock.sendto(data, address)
                    if i == len(chunks) - 1:
                        with contextlib.suppress(socket.timeout):
                            sock.settimeout(0.5)
                            ack_data, ack_addr = sock.recvfrom(1024)
                            if ack_data == b'ACK':
                                if onsuccess:
                                    print(onsuccess)
                                break 
                            else: 
                                return 0
                    attempts += 1
                except (socket.timeout, ConnectionRefusedError, OSError, TypeError):
                    attempts += 1
            if attempts > 3:
                return 0 
def UDP_receive(udp_port):
    oldtable = 0
    try:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.bind((serverIPmain, int(udp_port)))
        message = b''
        sender_addr = None
        while not exit_flag:
            data, addr = udp_socket.recvfrom(1024)
            if sender_addr is None:
                sender_addr = addr
            elif addr != sender_addr:
                continue
            if data:
                message += data 
                if len(data) < 1024:
                    udp_socket.sendto(b'ACK', addr)
            if not data:
                break
            try:
                message_dict = pickle.loads(message)
                global clientTable
                try:
                    if message_dict in {'Name', 'UDP', 'TCP'}:
                        clientTable = message_dict
                        break
                    else: 
                        clientTable = message_dict
                        newtable = count_unique_names(clientTable)
                        if newtable > oldtable: 
                            oldtable = newtable
                            print(">>> [Client Table Updated]")
                except TypeError:
                        clientTable = message_dict
                        newtable = count_unique_names(clientTable)
                        if newtable > oldtable: 
                            oldtable = newtable
                            print(">>> [Client Table Updated]")
            except pickle.PickleError:
                print('>>> [Failed to unpack data]')
            message = b''
            sender_addr = None
    except OSError:
        clientTable = 'UDP'

##TCP Connection  
def TCP_receive(tcp_port):
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.bind((serverIPmain, int(tcp_port)))
    tcp_socket.listen()
    tcp_socket.settimeout(1)
    while not exit_flag:
        try:
            conn, addr = tcp_socket.accept()
            data = conn.recv(1024)
            message = b''
            while data:
                message += data
                if len(data) < 1024:
                    break
                data = conn.recv(1024)
            if message:
                filename = pickle.loads(message)
                print(filename)
                for files in filesOffered:
                    if files == filename:
                        filepath = os.path.join(dir, filename)
                        if os.path.isfile(filepath):
                            with open(filepath, 'rb') as f:
                                file_data = f.read()
                            conn.sendall(pickle.dumps(file_data))
                else:
                        conn.sendall(pickle.dumps(None))
            conn.close()
        except socket.timeout:
            continue
    tcp_socket.close()

def TCP_send(message):
    i = 0
    name = message[3]
    filename = message[2]
    tcp_port = message[3]
    for client in clientTable[1:]:
        if tcp_port == client[1]:
            tcp_port = client[4]
            if client[2] == 'online':
                tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_socket.connect((serverIPmain, int(tcp_port)))
                print(f'< Connection with client {client} established. >')
                tcp_socket.sendall(pickle.dumps(filename))
                while True:
                    data = tcp_socket.recv(1024)
                    if data:
                        file_data = pickle.loads(data)
                        print("< Downloading foo.txt... >")
                        if file_data is not None:
                            with open(filename, 'wb') as f:
                                f.write(file_data)
                            print(f"< {filename} downloaded successfully! >")
                            print(f'< Connection with client {name} closed. >')
                            tcp_socket.close()
                            return 0
                        else:
                            print(f"File '{filename}' is not available on the server.")
                        break
            else: 
                print('>>> [Error: User is Offlin]e')
                pass
        else:
            i += 1
    if i == len(clientTable)-1:
        print('< Invalid Request >')

##Modes: -c || -s 
def client(data):
    global filesOffered
    udpport = data[2]
    tcpport = data[3]
    global dir 
    dir = None
    open = True
    printable = []
    set_exit_flag(False)
    data = list(data)
    name = data[0]
    data.insert(0, 'register')
    number = UDP_send(serveradd, data, '')
    number 
    if number == 0:
        print('>>> [Server is down, Try again later]')
        open = False 
    else: 
        receivetable = threading.Thread(target=UDP_receive, args=(udpport, ))
        receivetable.start()
        while clientTable == []:
            time.sleep(0.001)
        if clientTable == 'Name':
            print('>>> [Name is already taken]')
            set_exit_flag(True)
            open = False 
        elif clientTable == 'UDP':
            print('>>> [UDP PORT is already in use]')
            set_exit_flag(True)
            open = False 
        elif clientTable == 'TCP':
            print('>>> [TCP PORT is already in use]')
            set_exit_flag(True)
            open = False 
        else:
            # Start of main loop 
            print('>>> [Welcome, You are registered.]')
            sendfile = threading.Thread(target= TCP_receive , args = (tcpport, ) )
            sendfile.start()
    while open: 
        set_exit_flag(False)
        message = input(">>> ")
        message = message.split()
        message.insert(0,name)
        # List
        if message[1] == 'cd'or message[1] =='ls':
            for item in os.listdir('.'):
                print(item)
        elif message[1] == 'clear':
            os.system('clear')
        elif message[1] == 'list':
            printable = []
            for client in clientTable[1:]:
                if client[0] != []:
                    printable.append(client)
            if len(printable) == 0:
                print('>>> [No files available for download at the moment.]')
                #print(tabulate(clientTable[1:], headers=clientTable[0]))
            else:
                print(tabulate(printable, headers=clientTable[0]))
        # Set dir
        elif message[1] == 'setdir':
            if len(message) < 2:
                print(">>> [Format Error: setdir <dir>]")
            elif os.path.isdir(message[2]):
                dir = message[2]
                print(f">>> [Successfully set <{dir}> as the directory for searching offered files.]")
            else: 
                dirtemp = message[2]
                print(f">>> [setdir failed: <{dirtemp}> does not exist.]")
        # Offer file
        elif message[1] == 'offer':
            i = 0
            if dir and len(message) >= 2:
                for file in message[2:]:
                    filepath = os.path.join(dir, file)
                    if os.path.exists(filepath):
                        filesOffered.append(file)
                    else:
                        i += 1
                        print(f'>>> [Error: <{file}> does not exit]')
                        break
                if(i == len(file)):
                    print('None of the files are avalible')
                elif (len(message[2:]) != i):
                    success_message = '>>> [Offer Message received by Server.]'
                    UDP_send(serveradd, message, success_message)                
            else:
                if not dir:
                    print(">>> [Error: Directory not set]")
                else:
                    print(">>> [Invalid number of arguments]")
        # Deregister
        elif message[1] == 'request':
            filename = message[2]
            if len(message) <=3:
                print('>>> [Format Error: request <file/files> ')
            elif os.path.exists(filename):
                print(f'>>> [You are OverWriting {filename}]')
                TCP_send(message)
            else:
                TCP_send(message)
        elif message[1] == 'dereg':
            success_message = '>>> [You are Offline. Bye.]'
            UDP_send(serveradd, message, success_message)
            if receivetable.is_alive() or sendfile.is_alive():
                set_exit_flag(True)
                receivetable.join()
                sendfile.join()
            open = False
        elif message[1] == 'close':
            success_message = '>>> [Files are removed]'
            UDP_send(serveradd, message, success_message)
        # Any other message
        else:
            print(">>> [Unknown command]")

def server(data):
    global serverid, clientTable, clientList
    serverid = True 
    title = ["Files", "Name", "Status", "ClientUDP", "ClientTCP"]
    clientTable.append(title)
    files = []
    udpadds = []
    tcpadds = []
    open = True
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((serverIPmain, int(data)))
    message = b''
    sender_addr = None
    while open:
        data, addr = udp_socket.recvfrom(1024)
        if sender_addr is None:
            sender_addr = addr
        elif addr != sender_addr:
            continue
        if data:
            message += data 
            if len(data) < 1024:
                udp_socket.sendto(b'ACK', addr)
        if not data:
            break
        try:
            message = pickle.loads(message)
            print(clientTable)
            if message[1] == 'close':
                for names in clientTable[1:]: 
                    if names[1] == message[0]:
                        names[0].clear()
                broadcast(clientList, clientTable)
            elif message[1] == 'offer':
                for names in clientTable[1:]: 

                    if names[1] == message[0]:
                        for file in message[2:]:
                            names[0].append(file)
                broadcast(clientList, clientTable)
            elif message[1] == 'dereg':
                for names in clientTable[1:]: 
                    if names[1] == message[0]:
                        names[2] = 'offline'
                    broadcast(clientList, clientTable)
            elif message[0] == 'register':
                add = (addr[0], int(message[3]))
                holder = []
                name = message[1]
                udpadd = (sender_addr[0], int(message[3]))
                tcpadd = (sender_addr[0], int(message[4]))
                if any(name == client[1] for client in clientTable):
                    i = 0 
                    # Name already exists, update client information
                    for client in clientTable:
                        if client[1] == name:
                            holder = [client[0], name, 'offline', (message[3]), (message[4])]
                            if holder == client:
                                i = 0
                                client[2] = 'online'
                                print(holder)
                                print(client)
                            else:
                                i +=1    
                    if(i > 0):
                        UDP_send(add, 'Name', "Name already taken")
                    broadcast(clientList, clientTable)
                elif any(udpadd == client for client in udpadds):
                    UDP_send(add, 'UDP', "Name already taken")
                elif any(tcpadd == client for client in tcpadds):
                    UDP_send(add, 'TCP', "Name already taken")
                else:
                    message = list(message)
                    newclient = (message[1], sender_addr[0], int(message[3]))
                    clientList.append(newclient)
                    files = []
                    status = 'online'
                    message[0] = files
                    message[2] = status
                    udpadds.append(udpadd)
                    tcpadds.append(tcpadd)
                    clientTable.append(message)
                    broadcast(clientList, clientTable)
            message = b''
            sender_addr = None
        except pickle.PickleError:
            print('Failed to send data')

##Initial parser 
def main(argv):
    try:
        opts, args = getopt.getopt(argv, "s:c:")
    except getopt.GetoptError:
        sys.exit(">>> [Invalid arguments]")
    for opt, arg in opts:
        if opt == "-s":
            if verifyport(arg):
                server(arg)
        elif opt == "-c":
            x = len(argv)
            if len(argv) != 5:
                sys.exit(">>>[Invalid amount of arguments]")
            else: 
                name = argv[1]
                if verifyip(argv[2]):
                    serverip = str(argv[2])
                if verifyport(argv[3]):
                    clientudp = (argv[3])
                if verifyport(argv[4]):
                    clienttcp = (argv[4])
                data = [name, serverip, clientudp, clienttcp]
                client(tuple(data))
        else: 
            sys.exit(">>> [Invalid Input, Client Flags: -c.]")
    if len(opts) == 0:
        sys.exit(">>> [Invalid input]")
    
if __name__ == "__main__":
    main(sys.argv[1:])

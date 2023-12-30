from socket import *
import threading
import select
import db


# This class is used to process the peer messages sent to registry
# for each peer connected to registry, a new client thread is created
class ClientThread(threading.Thread):
    # initializations for client thread
    def __init__(self, ip, port, tcpClientSocket):
        threading.Thread.__init__(self)
        # ip of the connected peer
        self.ip = ip
        # port number of the connected peer
        self.port = port
        # socket of the peer
        self.tcpClientSocket = tcpClientSocket
        # username, online status and udp server initializations
        self.username = None
        self.isOnline = True
        self.udpServer = None
        print("New thread started for " + ip + ":" + str(port))

    def Security(self, message):  # Security
        #   JOIN    #
        if message[0] == "JOIN":
            # join-exist is sent to peer,
            # if an account with this username already exists
            if db.is_account_exist(message[1]):
                response = "join-exist"
                print("From-> " + self.ip + ":" + str(self.port) + " " + response)
                self.tcpClientSocket.send(response.encode())
            # join-success is sent to peer,
            # if an account with this username is not exist, and the account is created
            else:
                db.register(message[1], message[2])
                response = "join-success"
                self.tcpClientSocket.send(response.encode())
        #   LOGIN    #
        elif message[0] == "LOGIN":
            # login-account-not-exist is sent to peer,
            # if an account with the username does not exist
            if not db.is_account_exist(message[1]):
                response = "login-account-not-exist"
                self.tcpClientSocket.send(response.encode())
            # login-online is sent to peer,
            # if an account with the username already online
            elif db.is_account_online(message[1]):
                response = "login-online"
                self.tcpClientSocket.send(response.encode())
            # login-success is sent to peer,
            # if an account with the username exists and not online
            else:
                # retrieves the account's password, and checks if the one entered by the user is correct
                retrievedPass = db.get_password(message[1])
                # if password is correct, then peer's thread is added to threads list
                # peer is added to db with its username, port number, and ip address
                if retrievedPass == message[2]:
                    self.username = message[1]
                    self.lock.acquire()
                    try:
                        tcpThreads[self.username] = self
                    finally:
                        self.lock.release()
                    db.user_login(message[1], self.ip, message[3])
                    # login-success is sent to peer,
                    # and an udp server thread is created for this peer, and thread is started
                    # timer thread of the udp server is started
                    response = "login-success"
                    self.tcpClientSocket.send(response.encode())
                    self.udpServer = UDPServer(self.username, self.tcpClientSocket)
                    self.udpServer.start()
                    self.udpServer.timer.start()
                # if password not matches and then login-wrong-password response is sent
                else:
                    response = "login-wrong-password"
                    self.tcpClientSocket.send(response.encode())
        elif message[0] == "CREATE":
            if db.chat_room_exists(message[1]):
                response = "REJECT"
                print("From-> " + self.ip + ":" + str(self.port) + " " + response)
                self.tcpClientSocket.send(response.encode())
            # join-success is sent to peer,
            # if an account with this username is not exist, and the account is created
            else:
                db.create_chat_room(message[1])
                response = "DONE"
                self.tcpClientSocket.send(response.encode())

    # main of the thread
    def Logout(self, message):
        if len(message) > 1 and message[1] is not None and db.is_account_online(message[1]):
            db.user_leave_room(message[1])
            db.user_logout(message[1])
            self.lock.acquire()
            try:
                if message[1] in tcpThreads:
                    del tcpThreads[message[1]]
            finally:
                self.lock.release()
            print(self.ip + ":" + str(self.port) + " is logged out")
            self.tcpClientSocket.close()
            self.udpServer.timer.cancel()
        else:
            self.tcpClientSocket.close()

    def Cancel(self, message):
        # if user is online,
        # removes the user from onlinePeers list
        # and removes the thread for this user from tcpThreads
        # socket is closed and timer thread of the udp for this
        # user is cancelled
        if len(message) > 1 and message[1] is not None and db.is_account_online(message[1]):
            db.user_leave_room(message[1])
            db.user_logout(message[1])
            self.lock.acquire()
            try:
                if message[1] in tcpThreads:
                    del tcpThreads[message[1]]
            finally:
                self.lock.release()
            print(self.ip + ":" + str(self.port) + " is logged out")
            self.tcpClientSocket.close()
            self.udpServer.timer.cancel()
            self.udpServer.waitHelloMessage()

        else:
            self.tcpClientSocket.close()
            self.udpServer.waitHelloMessage()

    def Search(self, message):
        # checks if an account with the username exists
        if db.is_account_exist(message[1]):
            # checks if the account is online
            # and sends the related response to peer
            if db.is_account_online(message[1]):
                peer_info = db.get_peer_ip_port(message[1])
                response = "search-success " + peer_info[0] + ":" + peer_info[1]
                self.tcpClientSocket.send(response.encode())
            else:
                response = "search-user-not-online"
                self.tcpClientSocket.send(response.encode())
        # enters if username does not exist
        else:
            response = "search-user-not-found"
            self.tcpClientSocket.send(response.encode())

    # this function is used to get the online users from the database and send it to the peer
    def ListOnlineUsers(self):
        # Get the list of online users from MongoDB
        online_users = db.get_online_peers()
        # Send the list of online users back to the peer
        if online_users:
            response = f"ONLINE_USERS {' '.join(online_users)}"
            self.tcpClientSocket.send(response.encode())
        else:
            self.tcpClientSocket.send("NO_ONLINE_USERS".encode())

    # this function is used to get the chat rooms from the database and send it to the peer
    def ListChatRooms(self):
        # Get the list of chat rooms from MongoDB
        chat_rooms = db.get_chat_rooms()
        # Send the list of chat rooms back to the peer
        if chat_rooms:
            response = f"CHAT_ROOMS {' '.join(chat_rooms)}"
            self.tcpClientSocket.send(response.encode())
        else:
            self.tcpClientSocket.send("NO_CHAT_ROOMS".encode())

    def joinChatRoom(self, message):
        username = message[1]
        group_name = message[2]
        if db.user_join_room(username, group_name):
            response = "DONE"
        else:
            response = "REJECT"

        self.tcpClientSocket.send(response.encode())

    def leaveChatRoom(self, message):
        username = message[1]
        if db.user_leave_room(username):
            response = "DONE"
        else:
            response = "REJECT"

        self.tcpClientSocket.send(response.encode())

    def getChatRoomMembers(self, message):
        if db.chat_room_exists(message[1]):
            # Get the list of online users from MongoDB
            members = db.get_chat_room_members(message[1])
            # Send the list of online users back to the peer
            if members:
                response = f"MEMBERS {' '.join(members)}"
                self.tcpClientSocket.send(response.encode())
            else:
                self.tcpClientSocket.send("NO_MEMBERS".encode())
        else:
            response = "NO_CHAT_ROOM"
            self.tcpClientSocket.send(response.encode())

    def run(self):
        # locks for thread which will be used for thread synchronization
        self.lock = threading.Lock()
        print("Connection from: " + self.ip + ":" + str(port))
        print("IP Connected: " + self.ip)

        while True:
            try:
                # waits for incoming messages from peers
                message = self.tcpClientSocket.recv(1024).decode().split()

                if len(message) == 0:
                    break
                #   JOIN    #
                if message[0] == "JOIN" or message[0] == "LOGIN" or message[0] == "CREATE":
                    self.Security(message)

                # LOGOUT #
                elif message[0] == "LOGOUT":
                    self.Logout(message)
                    break
                # CANCEL #    
                elif message[0] == "CANCEL":
                    self.Cancel(message)
                    break
                #  SEARCH  #
                elif message[0] == "SEARCH":
                    self.Search(message)

                #  LIST ONLINE USERS  #
                elif message[0] == "GET_ONLINE_USERS":
                    self.ListOnlineUsers()

                elif message[0] == "GET_CHAT_ROOMS":
                    self.ListChatRooms()

                elif message[0] == "JOIN_CHAT_ROOM":
                    self.joinChatRoom(message)
                elif message[0] == "LEAVE_CHAT_ROOM":
                    self.leaveChatRoom(message)
                elif message[0] == "GET_CHAT_ROOM_MEMBERS":
                    self.getChatRoomMembers(message)

            except OSError:
                pass

    # function for resetting the timeout for the udp timer thread
    def resetTimeout(self):
        self.udpServer.resetTimer()


# implementation of the udp server thread for clients
class UDPServer(threading.Thread):

    # udp server thread initializations
    def __init__(self, username, clientSocket):
        threading.Thread.__init__(self)
        self.username = username
        # timer thread for the udp server is initialized
        self.timer = threading.Timer(3, self.waitHelloMessage)
        self.tcpClientSocket = clientSocket

    # if hello message is not received before timeout
    # then peer is disconnected
    def waitHelloMessage(self):
        if self.username is not None:
            db.user_leave_room(self.username)
            db.user_logout(self.username)
            if self.username in tcpThreads:
                del tcpThreads[self.username]
        self.tcpClientSocket.close()
        print("Removed " + self.username + " from online peers")

    # resets the timer for udp server
    def resetTimer(self):
        self.timer.cancel()
        self.timer = threading.Timer(3, self.waitHelloMessage)
        self.timer.start()


# tcp and udp server port initializations
print("Registry started...")
port = 15600
portUDP = 15500

# db initialization
db = db.DB()

# gets the ip address of this peer
# first checks to get it for Windows devices
# if the device that runs this application is not windows
# it checks to get it for macOS devices
hostname = gethostname()
try:
    host = gethostbyname(hostname)
except gaierror:
    import netifaces as ni

    host = ni.ifaddresses('en0')[ni.AF_INET][0]['addr']

print("Registry IP address: " + host)
print("Registry port number: " + str(port))

# onlinePeers list for online account
onlinePeers = {}
# accounts list for accounts
accounts = {}
# tcpThreads list for online client's thread
tcpThreads = {}

# tcp and udp socket initializations
tcpSocket = socket(AF_INET, SOCK_STREAM)
udpSocket = socket(AF_INET, SOCK_DGRAM)
tcpSocket.bind((host, port))
udpSocket.bind((host, portUDP))
tcpSocket.listen(5)

# input sockets that are listened
inputs = [tcpSocket, udpSocket]

# as long as at least a socket exists to listen registry runs
while inputs:

    print("Listening for incoming connections...")
    # monitors for the incoming connections
    readable, writable, exceptional = select.select(inputs, [], [])
    for s in readable:
        # if the message received comes to the tcp socket
        # the connection is accepted and a thread is created for it, and that thread is started
        if s is tcpSocket:
            tcpClientSocket, addr = tcpSocket.accept()
            newThread = ClientThread(addr[0], addr[1], tcpClientSocket)
            newThread.start()
        # if the message received comes to the udp socket
        elif s is udpSocket:
            # received the incoming udp message and parses it
            message, clientAddress = s.recvfrom(1024)
            message = message.decode().split()
            # checks if it is a hello message
            if message[0] == "HELLO":
                # checks if the account that this hello message
                # is sent from is online
                if message[1] in tcpThreads:
                    # resets the timeout for that peer since the hello message is received
                    tcpThreads[message[1]].resetTimeout()
                    print("Hello is received from " + message[1])

# registry tcp socket is closed
tcpSocket.close()

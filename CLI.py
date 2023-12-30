"""
    ##  Implementation of peer
    ##  Each peer has a client and a server side that runs on different threads
    ##  150114822 - Eren Ulaş
"""
from socket import *
import hashlib
import threading
# import time
import select
import pwinput
from colorama import Fore, init
from PeerClient import PeerClient
from PeerServer import PeerServer

init()


# main process of the peer
class CommandLineInterface:

    # peer initializations
    def __init__(self):
        # ip address of the registry
        # self.registryName = input("Enter IP address of registry: ")
        self.account_created = None
        self.logged_in = None
        self.registryName = gethostbyname(gethostname())
        # self.registryName = 'localhost'
        # port number of the registry
        self.registryPort = 15600
        # tcp socket connection to registry
        self.tcpClientSocket = socket(AF_INET, SOCK_STREAM)
        self.tcpClientSocket.connect((self.registryName, self.registryPort))
        # initializes udp socket which is used to send hello messages
        self.udpClientSocket = socket(AF_INET, SOCK_DGRAM)
        # udp port of the registry
        self.registryUDPPort = 15500
        # login info of the peer
        self.loginCredentials = ("", "")
        # online status of the peer
        self.isOnline = False
        # server port number of this peer
        self.peerServerPort = None
        # server of this peer
        self.peerServer = None
        # client of this peer
        self.peerClient = None

        self.peerClientsArray = []
        # timer initialization
        self.timer = None

        # as long as the user is not logged out, asks to select an option in the menu
        self.logged_in = False
        self.account_created = False
        logout = False
        while not logout:
            if (not self.logged_in) and (not self.account_created):
                # menu selection prompt
                print(Fore.LIGHTBLUE_EX, end='')
                print("Choose: \n1 Create account\n2 Login")
                print(Fore.LIGHTBLACK_EX, end='')
                choice = input()
                # if choice is 1, creates an account with the username
                # and password entered by the user
                if choice == "1":
                    self.create_account()
                # if choice is 2 and user is not logged in, asks for the username
                # and the password to login
                elif choice == "2" and self.isOnline:
                    print(Fore.RED + "You are already logged in!")

                elif choice == "2" and not self.isOnline:
                    self.user_login()
                elif choice == "CANCEL":
                    print(Fore.RESET, end='')
                    break
                else:
                    print(Fore.RED + "Invalid input!")

            elif self.logged_in:
                print(Fore.LIGHTBLUE_EX, end='')
                print("Choose: \n1 Logout\n2 Search\n3 Start a chat\n4 List online users\n5 Create a chat room\n"
                      "6 List chat rooms\n7 Join chat room")
                print(Fore.LIGHTBLACK_EX, end='')
                choice = input()
                # if choice is 3 and user is logged in, then user is logged out
                # and peer variables are set, and server and client sockets are closed
                if choice == "1" and self.isOnline:
                    self.user_logout()
                    # logout = True
                    self.logged_in = False
                    logout = True
                # is peer is not logged in and exits the program
                elif choice == "1":
                    self.logout(2)
                    # logout = True
                    self.logged_in = False
                    logout = True
                    print(Fore.RESET, end='')
                # if choice is 2 and user is online, then user is asked
                # for a username that is wanted to be searched
                elif choice == "2" and self.isOnline:
                    self.user_search()
                elif choice == "2":
                    print(Fore.RED + "You have to be logged in to search for users!")
                # if choice is 3 and user is online, then user is asked
                # to enter the username of the user that is wanted to be chatted
                elif choice == "3" and self.isOnline:
                    self.start_chat()
                elif choice == "3":
                    print(Fore.RED + "You have to be logged in to start a chat!")
                elif choice == "4":
                    self.list_users()
                elif choice == "5":
                    self.user_create_chat_room()
                elif choice == "6":
                    if self.list_chat_rooms() == "CANCEL":
                        self.user_cancel()
                        break
                elif choice == "7":
                    print(Fore.LIGHTBLUE_EX + "Group name: ", end='')
                    print(Fore.LIGHTBLACK_EX, end='')
                    group_name = input('')
                    self.user_join_chat_room(group_name)
                # if this is the receiver side then it will get the prompt to accept an incoming request during the
                # main loop that's why response is evaluated in main process not the server thread even though the
                # prompt is printed by server if the response is ok then a client is created for this peer with the
                # OK message and that's why it will directly send an OK message to the requesting side peer server
                # and waits for the user input main process waits for the client thread to finish its chat
                elif choice == "OK" and self.isOnline:
                    self.user_ok()
                # if user rejects the chat request then reject message is sent to the requester side
                elif choice == "REJECT" and self.isOnline:
                    self.user_reject()
                # if choice is cancel timer for hello message is cancelled
                elif choice == "CANCEL":
                    self.user_cancel()
                    break
                else:
                    print(Fore.RED + "Wrong input!")

            elif self.account_created:
                self.user_login()

    @staticmethod
    def hash_password(password):
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        return hashed_password

    def create_account(self):
        print(Fore.LIGHTBLUE_EX + "username: ", end='')
        print(Fore.LIGHTBLACK_EX, end='')
        username = input('')
        print(Fore.LIGHTBLUE_EX + "password: ", end='')
        print(Fore.LIGHTBLACK_EX, end='')
        confirm = False
        password = pwinput.pwinput(prompt='')
        while not confirm:
            print(Fore.LIGHTBLUE_EX + "confirm password: ", end='')
            print(Fore.LIGHTBLACK_EX, end='')
            confirm_password = pwinput.pwinput(prompt='')
            if confirm_password == password:
                confirm = True
            else:
                print(Fore.RED + "passwords doesn't match!\nEnter your password again please.")
                print(Fore.LIGHTBLUE_EX + "password: ", end='')
                print(Fore.LIGHTBLACK_EX, end='')
                password = pwinput.pwinput(prompt='')

        self.Register(username, password)

    # account creation function
    def Register(self, username, password):
        # join message to create an account is composed and sent to registry
        # if response is success then informs the user for account creation
        # if response is existed then informs the user for account existence
        hashPassword = self.hash_password(password)
        message = "JOIN " + username + " " + hashPassword
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode()
        if response == "join-success":
            print(Fore.LIGHTGREEN_EX + "Account created...")
            self.account_created = True
            print(Fore.LIGHTBLUE_EX + "Login:")
        elif response == "join-exist":
            print(Fore.RED + "choose another username or login...")

    def user_login(self):
        print(Fore.LIGHTBLUE_EX + "username: ", end='')
        print(Fore.LIGHTBLACK_EX, end='')
        username = input('')
        print(Fore.LIGHTBLUE_EX + "password: ", end='')
        print(Fore.LIGHTBLACK_EX, end='')
        password = pwinput.pwinput(prompt='')
        while True:
            print(Fore.LIGHTBLUE_EX + "Enter a port number for peer server: ", end='')
            print(Fore.LIGHTBLACK_EX, end='')
            try:
                # asks for the port number for the server's tcp socket
                peerServerPort = int(input(""))

                # Check if the port number is within the valid range
                if 1 <= peerServerPort <= 65535:
                    break
                else:
                    print(Fore.RED + "Port number must be between 1 and 65535. Please try again.")
            except ValueError:
                print(Fore.RED + "Invalid input. Please enter a valid integer.")

        try:
            status = self.Authentication(username, password, peerServerPort)
            # is user logs in successfully, peer variables are set
            if status == 1:
                self.isOnline = True
                self.loginCredentials = (username, password)
                self.peerServerPort = peerServerPort
                # creates the server thread for this peer, and runs it
                self.peerServer = PeerServer(self.loginCredentials[0], self.peerServerPort)
                self.peerServer.start()
                # hello message is sent to registry
                self.sendHelloMessage()
                self.logged_in = True
                self.account_created = False

        except Exception as e:

            print(f"An error occurred: {e}")

    # login function
    def Authentication(self, username, password, peerServerPort):
        # a login message is composed and sent to registry
        # an integer is returned according to each response
        hashPass = self.hash_password(password)
        message = "LOGIN " + username + " " + hashPass + " " + str(peerServerPort)
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode()
        if response == "login-success":
            print(Fore.LIGHTGREEN_EX + "Logged in successfully...")
            return 1
        elif response == "login-account-not-exist":
            print(Fore.RED + "Account does not exist!!...")
            return 0
        elif response == "login-online":
            print(Fore.RED + "Account is already online...")
            return 2
        elif response == "login-wrong-password":
            print(Fore.RED + "Wrong password...")
            return 3

    # logout function
    def logout(self, option):
        # a logout message is composed and sent to registry
        # timer is stopped
        if option == 1:
            message = "LOGOUT " + self.loginCredentials[0]
            self.timer.cancel()
        else:
            message = "LOGOUT"
        self.tcpClientSocket.send(message.encode())

    def user_search(self):
        print(Fore.LIGHTBLUE_EX + "Username to be searched: ", end='')
        print(Fore.LIGHTBLACK_EX)
        username = input('')
        if self.loginCredentials[0] == username:
            print(Fore.RED + "You can't search for yourself!")
            return
        searchStatus = self.searchUser(username)
        # if user is found its ip address is shown to user
        if searchStatus is not None and searchStatus != 0:
            print(Fore.LIGHTGREEN_EX + "IP address of " + username + " is " + searchStatus)

    # function for searching an online user
    def searchUser(self, username, print_flag=1):
        # a search message is composed and sent to registry
        # custom value is returned according to each response
        # to this search message
        message = "SEARCH " + username
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode().split()
        if response[0] == "search-success":
            if print_flag:
                print(Fore.LIGHTGREEN_EX + username + " is found successfully...")
            return response[1]
        elif response[0] == "search-user-not-online":
            if print_flag:
                print(Fore.RED + username + " is not online...")
            return 0
        elif response[0] == "search-user-not-found":
            if print_flag:
                print(Fore.RED + username + " is not found")
            return None

    def start_chat(self):
        print(Fore.LIGHTBLUE_EX + "Enter the username of user to start chat: ", end='')
        print(Fore.LIGHTBLACK_EX)
        username = input('')
        if self.loginCredentials[0] == username:
            print(Fore.RED + "You can't start a chat with yourself!")
            return
        searchStatus = self.searchUser(username)
        # if searched user is found, then its ip address and port number is retrieved
        # and a client thread is created
        # main process waits for the client thread to finish its chat
        if searchStatus is not None and searchStatus != 0:
            searchStatus = searchStatus.split(":")
            self.peerClient = PeerClient(searchStatus[0], int(searchStatus[1]), self.loginCredentials[0],
                                         self.peerServer, None)
            self.peerClient.start()
            self.peerClient.join()

    def list_users(self):
        try:
            # Establish a TCP connection with the registry
            # registry_socket = socket(AF_INET, SOCK_STREAM)
            # registry_socket.connect((self.registryName,self.registryPort))
            # Send a request to the registry for online users
            request_message = "GET_ONLINE_USERS"
            self.tcpClientSocket.send(request_message.encode())
            # Receive the response from the registry
            response = self.tcpClientSocket.recv(1024).decode()
            if response.startswith("ONLINE_USERS"):
                # Extract the online users from the response and display them
                online_users = response.split()[1:]
                if len(online_users) >= 2:
                    print(Fore.LIGHTGREEN_EX + "Online Users:")
                    for user in online_users:
                        if user == self.loginCredentials[0]:
                            continue
                        print(user)
                else:
                    print(Fore.RED + "No online users found.")
            else:
                print(Fore.RED + "No online users found.")

        # # Close the socket
        #     self.tcpClientSocket.close()

        except ConnectionError as e:
            print(f"Connection error: {e}")
        except Exception as ex:
            print(f"An error occurred: {ex}")

    def user_logout(self):
        self.logout(1)
        self.isOnline = False
        self.loginCredentials = (None, None)
        self.peerServer.isOnline = False
        self.peerServer.tcpServerSocket.close()
        if self.peerClient is not None:
            self.peerClient.tcpClientSocket.close()
        print(Fore.LIGHTGREEN_EX + "Logged out successfully")
        print(Fore.RESET, end='')
        CommandLineInterface()

    def user_cancel(self):
        self.cancel()
        self.isOnline = False
        self.loginCredentials = (None, None)
        self.peerServer.isOnline = False
        self.peerServer.tcpServerSocket.close()
        if self.peerClient is not None:
            self.peerClient.tcpClientSocket.close()
        print(Fore.LIGHTGREEN_EX + "Good Bye ")
        print(Fore.RESET, end='')

    def cancel(self):
        # a logout message is composed and sent to registry
        # timer is stopped
        message = "CANCEL " + self.loginCredentials[0]
        self.timer.cancel()
        self.tcpClientSocket.send(message.encode())

    # function for sending hello message
    # a timer thread is used to send hello messages to udp socket of registry
    def sendHelloMessage(self):
        message = "HELLO " + self.loginCredentials[0]
        self.udpClientSocket.sendto(message.encode(), (self.registryName, self.registryUDPPort))
        self.timer = threading.Timer(1, self.sendHelloMessage)
        self.timer.start()

    def user_ok(self):
        okMessage = "OK " + self.loginCredentials[0]
        self.peerServer.connectedPeerSocket.send(okMessage.encode())
        self.peerClient = PeerClient(self.peerServer.connectedPeerIP, self.peerServer.connectedPeerPort,
                                     self.loginCredentials[0], self.peerServer, "OK")
        self.peerClient.start()
        self.peerClient.join()

    def user_reject(self):
        self.peerServer.connectedPeerSocket.send("REJECT".encode())
        self.peerServer.isChatRequested = 0

    def user_create_chat_room(self):
        print(Fore.LIGHTBLUE_EX + "chat room name: ", end='')
        print(Fore.LIGHTBLACK_EX, end='')
        name = input('')

        self.create_chat_room(name)

    def create_chat_room(self, group_name):
        message = "CREATE " + group_name
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode()
        if response == "DONE":
            print(Fore.LIGHTGREEN_EX + "Chat room created...")
            self.user_join_chat_room(group_name)
        elif response == "REJECT":
            print(Fore.RED + "choose another name...")

    def user_join_chat_room(self, group_name):
        message = "JOIN_CHAT_ROOM " + self.loginCredentials[0] + " " + group_name
        self.tcpClientSocket.send(message.encode())
        response = self.tcpClientSocket.recv(1024).decode()
        if response == "DONE":
            print(Fore.LIGHTGREEN_EX + "Chat room joined...")
            searchStatus = self.searchUser(self.loginCredentials[0], 0)
            # if searched user is found, then its ip address and port number is retrieved
            # and a client thread is created
            # main process waits for the client thread to finish its chat
            if searchStatus is not None and searchStatus != 0:
                searchStatus = searchStatus.split(":")
                self.peerClient = PeerClient(searchStatus[0], int(searchStatus[1]), self.loginCredentials[0],
                                             self.peerServer, "CHAT-ROOM")

                members = self.get_users_in_chat_room(group_name, 0)
                for member in members:
                    searchStatus = self.searchUser(member, 0)
                    if searchStatus is not None and searchStatus != 0:
                        searchStatus = searchStatus.split(":")
                        self.peerClient.setChattingClients([searchStatus[0], int(searchStatus[1])])
                        self.peerClient.peerServer.setServerChattingClients([searchStatus[0], int(searchStatus[1])])

                self.peerClient.start()
                self.peerClient.join()

        elif response == "REJECT":
            print(Fore.RED + "Room doesn't exist...")

    def list_chat_rooms(self):
        try:
            # Send a request to the registry for online users
            request_message = "GET_CHAT_ROOMS"
            self.tcpClientSocket.send(request_message.encode())
            # Receive the response from the registry
            response = self.tcpClientSocket.recv(1024).decode()
            if response.startswith("CHAT_ROOMS"):
                # Extract the online users from the response and display them
                chat_rooms = response.split()[1:]
                print(Fore.LIGHTGREEN_EX + "Chat rooms:")
                for index, room in enumerate(chat_rooms):
                    print(f"{index + 1}: {room}")

                choice = "1"
                while choice != "2":
                    print(Fore.LIGHTBLUE_EX + "1 See the members of the chat room\n2 return ")
                    print(Fore.LIGHTBLACK_EX, end='')
                    choice = input('')
                    if choice == "1":
                        print(Fore.LIGHTBLUE_EX + "Enter the index of the group or it's name")
                        print(Fore.LIGHTBLACK_EX, end='')
                        group = input('')
                        if group.isdigit():
                            if 1 <= int(group) < len(chat_rooms) + 1:
                                chat_room_name = chat_rooms[int(group) - 1]
                                self.get_users_in_chat_room(chat_room_name)
                            else:
                                self.get_users_in_chat_room(group)
                        elif group == "CANCEL":
                            return "CANCEL"
                        else:
                            self.get_users_in_chat_room(group)

                    elif choice == "CANCEL":
                        return "CANCEL"
                    elif choice != "2":
                        print(Fore.RED + "Invalid input!")
            else:
                print(Fore.RED + "No Chat rooms found.")
            return None
        except ConnectionError as e:
            print(Fore.RED + f"Connection error: {e}")
        except Exception as ex:
            print(Fore.RED + f"An error occurred: {ex}")

    def get_users_in_chat_room(self, chat_room_name, print_flag=1):
        try:
            # Establish a TCP connection with the registry
            # registry_socket = socket(AF_INET, SOCK_STREAM)
            # registry_socket.connect((self.registryName,self.registryPort))
            # Send a request to the registry for online users
            request_message = "GET_CHAT_ROOM_MEMBERS " + chat_room_name
            self.tcpClientSocket.send(request_message.encode())
            # Receive the response from the registry
            response = self.tcpClientSocket.recv(1024).decode()
            if response.startswith("MEMBERS"):
                # Extract the online users from the response and display them
                members = response.split()[1:]
                if print_flag:
                    print(Fore.LIGHTGREEN_EX + "Members:")
                for member in members:
                    if print_flag:
                        print(member)
                if len(members) > 0:
                    return members
                else:
                    return []
            elif response.startswith("NO_MEMBERS"):
                if print_flag:
                    print(Fore.RED + "Chat room is empty!")
                return []
            elif response.startswith("NO_CHAT_ROOM"):
                if print_flag:
                    print(Fore.RED + "Chat room doesn't exist!")
                return []

        except ConnectionError as e:
            print(f"Connection error: {e}")
        except Exception as ex:
            print(f"An error occurred: {ex}")


# peer is started
main = CommandLineInterface()

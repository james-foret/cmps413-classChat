import threading
import socketserver
import json
import time

# below are the global variables needed for running the server and the JSON protocol the server uses
users = {}
server_json = {
    "username": "",
    "status": 0,
    "msg": "",
    "recipient": "",
    "time": 0.0,
}

HOST = 'localhost'
PORT = 8080
# lock creates a way to handle threads safely, it forces a thread to finish its process before the next one in a queue
# can begin, this is important for sending messages and other functions because it prevents the server from iterating and
# altering the same list at the same time.
lock = threading.Lock()

# This is the server, it extends the socketserver.TCPServer class
# socketserver.ThreadingMixIn allows for a new thread to be created when a new client joins
# Handles the sending, logging, and receiving of messages and tracking active clients, this is the only instance of the server running.
class ThreadedChatServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    # when a new thread is created, it's a child of the main program of the server, so if the server quits, all it's children threads do too.
    daemon_threads = True
    # allows for the server to come back online without a long or manual timeout
    allow_reuse_address = True
    # don't wait for all the active request threads to finish whenever the server is shutdown. This means that you can shut it down
    # immediately in the event of infinite loops or other issues.
    block_on_close = False

    def broadcast(self, msg, sender_name="[broadcast]", status=0, sender_sock=None):
        """
        Sends a message to all connected clients.
        :param msg: String contents of the message
        :param sender_name: String name of the sending client
        :param status: A numeric code for server handling purposes
        :param sender_sock: Lets the server ID who sent the message, so this way they don't receive thier own message twice, the
        message sent by the clients will echo client side on their TUI
        :return:
        """
        # server debug output
        print(f"[broadcast]: {msg}")
        # copy the JSON protocol and fill it in
        outbound = server_json.copy()
        outbound["username"] = sender_name
        outbound["msg"] = msg
        outbound["status"] = status
        outbound["recipient"] = "general"
        outbound["time"] = time.time()
        # lock is required here because if 2 users are iterating and changing it from some request at the same time
        # errors can be thrown. this means that only 1 client can iterate and make changes at a time, and the lock
        # is used in this way throughout the project.
        # only 1 thread can execute here right now, and if another tries, it has to wait its turn.
        with lock:
            # create a list of users who need to be disconnected
            disconnected = []
            # for all users but the sender
            for username, sock in list(users.items()):
                if sock != sender_sock:
                    # try to send the message broadcast
                    try:
                        sock.sendall((json.dumps(outbound) + "\n").encode())
                    except OSError:
                        disconnected.append(username)
            # if the client can't be reached, has DC'd, remove them from the list of active clients
            for dc in disconnected:
                del users[dc]

    def broadcast_user_list(self):
        """
        Sends the list of all clients to all connected clients so they can see who is online.
        """
        # copy JSON protocol
        outbound = server_json.copy()
        outbound["username"] = "server"
        outbound["status"] = 3
        outbound["recipient"] = "all"
        outbound["time"] = time.time()
        # same logic as above for safe parsing and making threads wait in a queue styled line
        with lock:
            outbound["msg"] = json.dumps(list(users.keys()))
            disconnected = []
            for username, sock in list(users.items()):
                try:
                    sock.sendall((json.dumps(outbound) + "\n").encode())
                except OSError:
                    disconnected.append(username)
            # if the user can't be found, they need to be disconnected and removed from the list of active clients
            for dc in disconnected:
                del users[dc]

    def send_to_user(self, msg, recipient="", sender="server", status=0):
        """
        Sends a message to a specific connected client
        :param msg: String contents of the message
        :param recipient: String name of the receiving client
        :param sender: String name of the sending client
        :param status: Numeric code for server handling purposes
        :return: boolean True - messaage sent, False - sending failed
        """
        # copy JSON protocol and fill
        outbound = server_json.copy()
        outbound["username"] = sender
        outbound["msg"] = msg
        outbound["status"] = status
        outbound["recipient"] = recipient
        outbound["time"] = time.time()
        # see abouve with blocks, for thread safety
        with lock:
            if recipient in users:
                # try to send the message if the client appears online
                try:
                    #send the message
                    users[recipient].sendall((json.dumps(outbound) + "\n").encode())
                    return True
                # if the socket didn't work
                except OSError:
                    # delete the user and return False
                    del users[recipient]
                    return False
        # Safety return for unforeseen errors
        return False

# This is the handler that is created every time a new client is created, it is instantied by the server.
# It handles all the basics, login, messaging loop (recv for the server), and managing a client during the connection.
# Reads inbound messages for the server to forward.
# makes the decisions for the routing of the message and passes that to the main server.
# only sends back to its own socket when the client invokes an error, this reduces overhead on the server.
class ThreadedChatHandler(socketserver.BaseRequestHandler):
    def handle(self):
        username = ""
        try:
            # login handshake
            incoming = self.request.recv(4096).decode().strip()
            # if empty packet
            if not incoming:
                return
            # try to decode the packet
            try:
                packet = json.loads(incoming)
            except json.JSONDecodeError:
                return
            # if the error code is wrong, abort
            if packet.get("recipient") != "server" or packet.get("status") != 2:
                return
            # if username is empty
            username = packet.get("username", "").strip()
            if not username:
                return
            # thread safety
            with lock:
                if username in users:
                    # reject duplicate usernames
                    err = server_json.copy()
                    err["username"] = "server"
                    err["msg"] = "Username already taken."
                    err["status"] = -1
                    err["recipient"] = username
                    err["time"] = time.time()
                    self.request.sendall((json.dumps(err) + "\n").encode())
                    return
                # add them if all checks pass!
                users[username] = self.request
            # server side debug print
            print(f"{username} connected from {self.client_address}")
            # client confirmation of joining
            class_chat.broadcast(f"{username} joined.")
            # update the list of active users for all clients
            class_chat.broadcast_user_list()
            # message loop
            while True:
                msg = self.request.recv(4096).decode().strip()
                if not msg:
                    break
                # try to decode the packet, if there is one
                try:
                    packet = json.loads(msg)
                    sender = packet.get("username", username)
                    recipient = packet.get("recipient", "bad")
                    contents = packet.get("msg", "")
                    status = packet.get("status", 0)
                except json.JSONDecodeError:
                    # falls back to the known username from the login, bad triggers an error, others are defaults "" or 0
                    sender, recipient, contents, status = username, "bad", msg, 0
                # skip a message with no content
                if not contents:
                    continue

                # server debug statement
                print(f"[{sender}] -> [{recipient}]: {contents}")

                # message is intended for everyone
                if recipient in ("general", "broadcast", "server"):
                    class_chat.broadcast(contents, sender_name=sender, sender_sock=self.request)
                # messages that fail to decode or are empty in recipients are handled here
                elif recipient in ("", "bad"):
                    self.request.sendall(
                        "SERVER ERROR: Invalid or missing recipient.\n".encode()
                    )
                # Attempt to send the message to an individual
                else:
                    if not class_chat.send_to_user(contents, recipient, sender, status):
                        self.request.sendall(
                            f"SERVER ERROR: Could not deliver to {recipient}.\n".encode()
                        )
        # this is the block that handles disconnects, runs after the While loop in the Try block to let the clients
        # know that another client has left or DC'd
        finally:
            with lock:
                if username in users:
                    users.pop(username)
            if username:
                # server debug
                print(f"{username} disconnected.")
                # client broadcast
                class_chat.broadcast(f"{username} left.")
                class_chat.broadcast_user_list()


if __name__ == '__main__':
    # create the address for ThreadedChatServer
    ADDRESS = (HOST, PORT)
    class_chat = ThreadedChatServer(ADDRESS, ThreadedChatHandler)
    print(f"ClassChat server started on {HOST}:{PORT}")
    # run until terminated
    try:
        class_chat.serve_forever()
    # end with ctrl+c
    except KeyboardInterrupt:
        class_chat.broadcast("Server shutting down.")
        class_chat.shutdown()
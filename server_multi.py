import threading
import socketserver
import json
import time

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
lock = threading.Lock()

class ThreadedChatServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True
    block_on_close = False

    def broadcast(self, msg, sender_name="[broadcast]", status=0, sender_sock=None):
        print(f"[broadcast]: {msg}")
        outbound = server_json.copy()
        outbound["username"] = sender_name
        outbound["msg"] = msg
        outbound["status"] = status
        outbound["recipient"] = "general"
        outbound["time"] = time.time()

        with lock:
            disconnected = []
            for username, sock in list(users.items()):
                if sock != sender_sock:
                    try:
                        sock.sendall((json.dumps(outbound) + "\n").encode())
                    except OSError:
                        disconnected.append(username)
            for dc in disconnected:
                del users[dc]

    def broadcast_user_list(self):
        outbound = server_json.copy()
        outbound["username"] = "server"
        outbound["status"] = 3
        outbound["recipient"] = "all"
        outbound["time"] = time.time()

        with lock:
            outbound["msg"] = json.dumps(list(users.keys()))
            disconnected = []
            for username, sock in list(users.items()):
                try:
                    sock.sendall((json.dumps(outbound) + "\n").encode())
                except OSError:
                    disconnected.append(username)
            for dc in disconnected:
                del users[dc]

    def send_to_user(self, msg, recipient="", sender="server", status=0):
        outbound = server_json.copy()
        outbound["username"] = sender
        outbound["msg"] = msg
        outbound["status"] = status
        outbound["recipient"] = recipient
        outbound["time"] = time.time()

        with lock:
            if recipient in users:
                try:
                    users[recipient].sendall((json.dumps(outbound) + "\n").encode())
                    return True
                except OSError:
                    del users[recipient]
                    return False
        return False


class ThreadedChatHandler(socketserver.BaseRequestHandler):

    def handle(self):
        username = ""

        try:
            # login handshake
            incoming = self.request.recv(4096).decode().strip()
            if not incoming:
                return

            try:
                packet = json.loads(incoming)
            except json.JSONDecodeError:
                return

            if packet.get("recipient") != "server" or packet.get("status") != 2:
                return

            username = packet.get("username", "").strip()
            if not username:
                return

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
                users[username] = self.request

            print(f"{username} connected from {self.client_address}")
            class_chat.broadcast(f"{username} joined.")
            class_chat.broadcast_user_list()

            # message loop
            while True:
                msg = self.request.recv(4096).decode().strip()
                if not msg:
                    break

                try:
                    packet = json.loads(msg)
                    sender    = packet.get("username", username)
                    recipient = packet.get("recipient", "bad")
                    contents  = packet.get("msg", "")
                    status    = packet.get("status", 0)
                except json.JSONDecodeError:
                    sender, recipient, contents, status = username, "bad", msg, 0

                if not contents:
                    continue

                print(f"[{sender}] -> [{recipient}]: {contents}")  # add this line

                if recipient in ("general", "broadcast", "server"):
                    class_chat.broadcast(contents, sender_name=sender, sender_sock=self.request)
                elif recipient in ("", "bad"):
                    self.request.sendall(
                        "SERVER ERROR: Invalid or missing recipient.\n".encode()
                    )
                else:
                    if not class_chat.send_to_user(contents, recipient, sender, status):
                        self.request.sendall(
                            f"SERVER ERROR: Could not deliver to {recipient}.\n".encode()
                        )

        finally:
            with lock:
                if username in users:
                    users.pop(username)
            if username:
                print(f"{username} disconnected.")
                class_chat.broadcast(f"{username} left.")
                class_chat.broadcast_user_list()


if __name__ == '__main__':
    ADDRESS = (HOST, PORT)
    class_chat = ThreadedChatServer(ADDRESS, ThreadedChatHandler)
    print(f"ClassChat server started on {HOST}:{PORT}")
    try:
        class_chat.serve_forever()
    except KeyboardInterrupt:
        class_chat.broadcast("Server shutting down.")
        class_chat.shutdown()
                
        
                
                    
                    
                
            
            
            
            
            
            
            
                
            
                

                
    

"""
Entry point for the server when the program is run
"""

if __name__ == '__main__':
    # open the server up and create it 
    ADDRESS = (HOST, PORT)
    class_chat = ThreadedChatServer(ADDRESS, ThreadedChatHandler)
    print(f"ClassChat server started on {HOST}, PORT {PORT}...")
    
    # this opens it up for new sockets to connect
    try:
        class_chat.serve_forever()
    except KeyboardInterrupt:
        class_chat.broadcast("\nClass Chat is shutting down.")
        class_chat.shutdown()
    








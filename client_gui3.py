import socket
import threading
import json
import time
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, VSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

# below are the global variables needed for running the server as well as the json protocol definition for messaging with clients
HOST = "localhost"
PORT = 8080
client_json = {
    "username": "",
    "status": 0,
    "msg": "",
    "recipient": "",
    "time": 0.0,
}

COLORS = [
# COLORS: a list for storing the possible user assigned colors when signed on. Should make it easier to see who's who at a glance.
# The ansi colors were used for max compatibility, they were chosen before prompt-toolkit was added in.
    "ansicyan",
    "ansiblue",
    "ansiyellow",
    "ansiwhite",
    "ansibrightyellow",
    "ansimagenta",
    "ansibrightcyan",
    "ansibrightblue",
    "ansibrightmagenta",
]

style = Style.from_dict({
# color and style codes for prompt-toolkit package, these determine the color of the "UI" in the terminal once logged in
    "tab-active":   "bg:#2e2e2e #ffffff bold",
    "tab-inactive": "bg:#1a1a1a #666666",
    "tab-unread":   "bg:#1a1a1a #cc3333",
    "tab-bar":      "bg:#1a1a1a",
    "chat-area":    "bg:#1a1a1a #cccccc",
    "input-area":   "bg:#111111 #ffffff",
    "prompt":       "#555555",
    "online-panel": "bg:#1a1a1a #888888",
    "online-title": "#444444",
    "separator":    "#333333",
    "sys":          "#666666",
    "broadcast":    "#888888",
})

class Client:
    def __init__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.username = ''
        # auto join the general chat
        self.conversations = {"general": []}
        # tab_order tracks the order of tabs, they are maintained sequentially
        self.tab_order = ["general"]
        # set active view to the general chat
        self.active_tab = "general"
        # tabs with unread messages, the tabs will appear red on the client side.
        self.unread = set()
        self.online_users = []
        self.user_colors = {}
        self.color_index = 0
        self.app = None

    def _get_color(self, username):
        """
        Returns the color assigned to a user, it's based on login order. The %len() call prevents index errors
        :param username: from client_json, the name a user logs in with
        :return: a String from the list COLORS
        """
        if username not in self.user_colors:
            self.user_colors[username] = COLORS[self.color_index % len(COLORS)]
            self.color_index += 1
        return self.user_colors[username]

    def connect(self):
        """
        Prompts a new client for their username, then attempts to connect them to the server.
        """
        self.socket.connect((HOST, PORT))
        self.username = input("Enter username: ")
        self._login()
        # opens a thread for recieving, this is needed because the prompt-toolkit opens a thread only for input and user action, not for incoming messages
        threading.Thread(target=self._receive_loop, daemon=True).start()

    def _login(self):
        """
        Copies over the client_json protocol format, fills in details, and sends a request to the server for a new login.
        """
        packet = client_json.copy()
        packet["username"] = self.username
        packet["status"] = 2
        packet["recipient"] = "server"
        packet["msg"] = f"{self.username} is trying to sign on"
        packet["time"] = time.time()
        self.socket.send(json.dumps(packet).encode())

    def _receive_loop(self):
        """
        This is being run by the thread opened when a client connects. The idea here is to allow the client to receive
        and input messages at the same time while in the TUI.
        """
        buffer = ""
        # asserts that while the thread is running, this is going to loop
        while True:
            try:
                data = self.socket.recv(4096).decode()
                if not data:
                    self._store_message("general", "server", "Disconnected.")
                    break
                # this occurs when the client gets a message from the server.
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        # converts the packet into parsable format
                        packet = json.loads(line)
                        # get() attempts to read the data from the packet, provides default values for safety, but sometimes
                        # defines a default value, like with 'recipient'
                        sender = packet.get("username", "Unknown")
                        msg = packet.get("msg", "")
                        recipient = packet.get("recipient", "general")
                        status = packet.get("status", 0)

                        # status code 3 is a code from the server that tells the client to update the list of online clients
                        # it means that a new user has logged in or logged out
                        if status == 3:
                            # msg was decoded above, if status == 3, it's a list of active users, so it's assigned to that variable for the client
                            self.online_users = json.loads(msg)
                            # tells prompt_toolkit to redraw the screen on the next cycle with invalidate()
                            if self.app:
                                self.app.invalidate()
                            # repeat the loop, the message has been decoded
                            continue

                        # finding which tab to assign the message to in the client
                        if recipient == self.username:
                            # incoming private DM, it will go under the tab for the sender for the recieving client
                            convo = sender
                        else:
                            # if the client is not a specifically listed recipient, it goes to general.
                            convo = "general"
                    # this except block happens when an error occurs in the JSON decode, so it just dumps the raw JSON string to
                    # general as an "error"... ideally this doesn't happen and is more so for debugging
                    except json.JSONDecodeError:
                        sender, msg, convo = "raw", line, "general"

                    # this appends the message to the correct TUI tab and calls prompt_tookit to redraw the TUI with invalidate()
                    self._store_message(convo, sender, msg)
                    if self.app:
                        # redraw
                        self.app.invalidate()
            # this happens if there's a network or server crash, it exits the loop instead of causing a complete crash
            except OSError:
                break

    def send(self, msg, recipient="general", status=0):
        """
        Sends a message to the server from the client.
        :param msg: a String containing the message from the client
        :param recipient: default = "general" the public chat. Otherwise, it tells the server to send it to the DM of another client, or is a server only message like login.
        :param status: default = 0, tells the server the status code of the message so it can properly handle it.
        """
        # copy JSON form
        packet = client_json.copy()
        # fill JSON form with params
        packet["username"] = self.username
        packet["msg"] = msg
        packet["status"] = status
        packet["recipient"] = recipient
        packet["time"] = time.time()
        # send it!
        self.socket.sendall(json.dumps(packet).encode())

    # Below are several helper methods for the TUI and handling conversations

    def _ensure_tab(self, name):
        """
        Creates a tab if one does not exist for an incoming message
        :param name: the name of the sender, and by extension, the name of the tab that will be created
        """
        if name not in self.conversations:
            self.conversations[name] = []
        if name not in self.tab_order:
            self.tab_order.append(name)

    def _store_message(self, convo, sender, msg):
        """
        This saves the message to the tab so it persists during the ongoing client session
        :param convo: The conversation the message was sent to
        :param sender: The sender of the message
        :param msg: content of the message
        """
        # runs a check to ensure the conversation has an open tab, opens one if not
        self._ensure_tab(convo)
        # append the message to the chat
        self.conversations[convo].append((sender, msg))
        # if the user is not viewing the tab, it marks it as unread
        if convo != self.active_tab:
            self.unread.add(convo)

    def _switch_tab(self, name):
        # runs a check to ensure the conversation has an open tab, opens one if not
        self._ensure_tab(name)
        # move the active tab variable to the name of the current tab
        self.active_tab = name
        # removes the unread label from a tab once switched
        self.unread.discard(name)

    def _next_tab(self):
        # idx is the current tab, aka actvie_tab
        idx = self.tab_order.index(self.active_tab)
        # calls switch tab to move forward 1 or wrap around to the beginning if at the end of the list.
        self._switch_tab(self.tab_order[(idx + 1) % len(self.tab_order)])

    def _prev_tab(self):
        # idx is the current tab, aka actvie_tab
        idx = self.tab_order.index(self.active_tab)
        # calls switch tab to move back 1 or wrap around to the beginning if at the end of the list.
        self._switch_tab(self.tab_order[(idx - 1) % len(self.tab_order)])

# The methods below call for the TUI to format and redraw the page for the client whenever events occur like incoming messages.
    def _get_tab_bar(self):
        """
        Gets the tab bar for the client for the TUI
        :return: result [] : The list of open tabs for a client and the status of the tabs, viewing, unread, or general
        """
        result = []
        for name in self.tab_order:
            if name == self.active_tab:
                # this is for the current tab, should be white
                result.append(("class:tab-active", f" {name} "))
            elif name in self.unread:
                # for the unread tabs, should be red with an asterisk to denote a notification
                result.append(("class:tab-unread", f" {name}* "))
            else:
                # inactive tabs are read, no new messages
                result.append(("class:tab-inactive", f" {name} "))
            # this an appended spacer to tell the TUI to render some extra room to prevent long names from running together
            result.append(("class:tab-bar", " "))

        return result

    def _get_chat_text(self):
        """
        Builds a list of (style, text) tuples for the TUI to render. prompt_tookit allows for mixing styles with pairs
        of tuples, so we can make the usernames bold and visible and keep the text unstyled to improve visibility in the
        TUI.

        :return: result[]: the tuples for the TUI to render for color and style
        """
        result = []
        for sender, msg in self.conversations.get(self.active_tab, []):
            # this is for the broadcast, server only messages, and raw error JSON strings
            if sender in ("server", "[broadcast]", "raw"):
                result.append(("class:broadcast", f"  {msg}\n"))
            # This appends two tuples because of the stylization methods of prompt_toolkit, this allows you to style the
            # name (you in this case) and make it bold and easier to read, but keeps the message a regular style of text
            elif sender == self.username:
                result.append(("ansigreen bold", f"  you"))
                result.append(("class:chat-area", f": {msg}\n"))
            # other users' colors are found with _get_color() and do the same thing with mixing styles for prompt_toolkit
            else:
                color = self._get_color(sender)
                result.append((color + " bold", f"  {sender}"))
                result.append(("class:chat-area", f": {msg}\n"))

        return result

    def _get_online_text(self):
        """

        :return: result []: a list of online users.
        """
        # start with the header, never changes so is appended always
        result = [("class:online-title", "  online\n  ------\n")]

        for user in self.online_users:
            # renders the user as {your_username}(you)
            if user == self.username:
                result.append(("ansigreen", f"  {user} (you)\n"))
            else:
                # gets user color, appends them to the list
                color = self._get_color(user)
                result.append((color, f"  {user}\n"))

        return result

    def _get_prompt_text(self):
        """
        Gets the tuple for the input box at the bottom of the active tab.
        :return: result []: The tuple for the input box at the bottom of the active tab.
        """
        # active_tab also matches the intended recipient(s), so
        # for general: " general > "
        # for another user in a DM: " user > "
        return [("class:prompt", f" {self.active_tab} > ")]

    def _handle_input(self, text):

        """
        Handles the commands a user may send as part of a message.

        /help: lists available commands for a client,
        /dm <user> <msg>: sends or starts a DM with another user,
        /who: lists active members in a client's local general tab,
        /close: closes the current tab

        :param text: The message as a raw String before being packaged and sent in a JSON format
        :return: None: used as a function exit
        """
        # gets raw message and removes whitespace
        text = text.strip()
        # if empty, quit
        if not text:
            return
        # /dm <user> <msg>
        if text.startswith("/dm "):
            # split the message for parsing the recipient, the command, and msg
            # the limit of 2 prevents the message from being split too many times in a multi-worded message
            parts = text.split(" ", 2)
            # this is an error thrown by the client to let them know they didn't properly format the DM command, defaults to sending to the client's general
            if len(parts) < 3:
                self._store_message("general", "sys", "usage: /dm <username> <message>")
                return
            # discards '/dm ' this has already been determined as the intended command
            _, target, msg = parts
            # checks for tab, creates if non-existent
            self._ensure_tab(target)
            # switches to the tab client just sent the DM to
            self._switch_tab(target)
            # stores the message in the client's memory for the session, shows it locally
            self._store_message(target, self.username, msg)
            # sends the message to the intended recipient
            self.send(msg, recipient=target, status=1)
            return

        # /who
        if text == "/who":
            # grabs the list of online users, if there are any
            users_str = ", ".join(self.online_users) if self.online_users else "none"
            # displays the message for the client, not sent from the server, that is updated by server to client when someone
            # joins or leaves.
            self._store_message(self.active_tab, "sys", f"online: {users_str}")
            return

        # close current tab
        if text == "/close":
            # similar to above with DM, a local error message basically saying you're not allowed to close the general
            # chat and remain online. Note, closing a tab does not close the conversation history unless the clients connection ends so
            # a conversation can persist throughout a session
            if self.active_tab == "general":
                self._store_message("general", "sys", "cannot close general.")
                return
            # asserts the active tab so it can be deleted after moving the client off of it
            tab = self.active_tab
            # move the active_tab back by 1, because you can't delete general, it will always be the general or the previous tab
            self._prev_tab()
            # remove the tab the user intends to close from the list of available tabs
            self.tab_order.remove(tab)
            return

        # /help
        if text == "/help":
            help_text = "/dm <user> <msg>  open DM | /who  list online | /close  close tab | <tab>  switch tabs | <shift + tab>  go back a tab\n<ctrl + c> or <ctrl + q> to quit."
            self._store_message(self.active_tab, "sys", help_text)
            return

        # message with no parsable commands, the sender is either general or the user's active tab
        recipient = "general" if self.active_tab == "general" else self.active_tab
        # store the message client side
        self._store_message(self.active_tab, self.username, text)
        # send the message
        self.send(text, recipient=recipient)

# the methods below set up the client and prompt_toolkit for running the client
    def run(self):
        # create the keybindings for the client
        kb = KeyBindings()
        # move to the next tab with <tab> key
        @kb.add("tab")
        def _(event):
            self._next_tab()
        # move to the previous tab with <shift> + <tab> keys
        @kb.add("s-tab")
        def _(event):
            self._prev_tab()
        # exit with <Ctrl> + <c> or <Ctrl> + <q>
        @kb.add("c-c")
        @kb.add("c-q")

        def _(event):
            event.app.exit()

        input_field = TextArea(
            height=3,
            # prompt_toolkit expects a function here, lambda used for brevity
            prompt=lambda: self._get_prompt_text(),
            # defines the style for prompt_toolkit
            style="class:input-area",
            # no multiline messages supported here
            multiline=False,
            # it will wrap the text for longer messages though, prevents cut-off messages.
            wrap_lines=True,
        )

        def on_enter(event=None):
            """
            Grabs text from the input box, clears the field for the client, and passes it to _handle_input() for parsing.
            :param event: None: prompt_toolkit expects an event obj, but accept_handler() needs no args, this prevents
            issues.
            """
            # grabs input from the text box
            text = input_field.text
            # clears it
            input_field.text = ""
            # passes the text from the input box to the parsing _handle_input()
            self._handle_input(text)

        # this is called on by TextArea() when enter is pressed, this is a default behavior of prompt_toolkit
        input_field.accept_handler = on_enter

        # I also decided to bind it here because it fixed a bug when messages are sometimes not sent, unsure
        input_field.control.key_bindings = KeyBindings()
        @kb.add("enter")
        def _(event):
            on_enter()

        # Layout() is the formatting top-level layer for a 'screen' in prompt_toolkit, this is the layout
        # for the client UI
        layout = Layout(
            # Note on redraws, when invalidate() is called, prompt_toolkit flags the app as "out-of-date" and in need
            # of a redraw. On its next cycle, the call is made for a redraw. This is why you need to pass functions in as
            # references so that they can be called whenever an update is required. Passing in a function call with () would
            # mean that it would never update, it would just call once and repeat the output.
            HSplit([
                 # tab bar
                Window(
                    content=FormattedTextControl(self._get_tab_bar),
                    height=1,
                    style="class:tab-bar",
                ),
                # main area
                VSplit([
                    # chat log
                    Window(
                        content=FormattedTextControl(
                            self._get_chat_text,
                            focusable=False,
                        ),
                        style="class:chat-area",
                        wrap_lines=True,
                    ),
                    # online panel
                    Window(width=1, char="│", style="class:separator"),
                    # list the names of the online clients
                    Window(
                        content=FormattedTextControl(self._get_online_text),
                        width=16,
                        wrap_lines=True,
                        style="class:online-panel",
                    ),
                ]),
                # divider
                Window(height=1, char="─", style="class:separator"),
                # input
                input_field,
            ]),
        )

        self.app = Application(
            # builds the TUI as an object
            layout=layout,
            key_bindings=kb,
            style=style,
            full_screen=True,
            mouse_support=False,
        )
        # repeat the loop, the UI is only closed when the client quits.
        self.app.run()

if __name__ == "__main__":
    client = Client()
    client.connect()
    client.run()
# classChat

*classChat* is a terminal chat application built with Python. It allows for multiple users to connect and send messages in an instant-messenger styled enviroment.
Users are connected to a multithreaded, centralized server that handles the receiving and forwarding of messages on the clients' behalf.

*classChat* allows users to chat in "general" channel for a class-wide groupchat, send private messages directly to other users,
and utilized a stylized TUI interface created with the library `prompt_toolkit`.

## Features

- Multi-user general chat: all connected users can send and view messages in a shared channel. They automatically join the channel upon connection.
- Direct messaging: clients can send a message to any other connected client by using the simple command in the general chat `/dm <username> <message>`
- See who is online: there is a live window displaying which clients are currently connected.
- Tabs for conversations: clients can manage multiple conversations from one window using `<tab>` & `<shift + tab>` to navigate thier active chats.
- Color assignment: users are assigned a color for their username that is persistent throughout the session so it is easier to distinguish who sent what... especially in "general"!
- Connection handling: the server notifies connected clients when a new client joins or disconnects.
- Threaded server: the server supports simultaneous connections without blocking.
- low-CPU client: achieved in a two-threaded model, the main thread runs the `prompt_toolkit` TUI. This event-driven library means that updates only occur client side when a message is sent or received, preventing excessive redrawing. The secondary receiving thread for incoming messages blocks while no data is being streamed in.
- arg parsing: client can call commands to navigate the chat controls easily from the keyboard.

## Client commands

`/dm <user> <msg>` : sends a private message, opens a new conversation tab.

`/who` : list currently online users

`/close` : close the current conversation tab

`/help` : show available commands

`<Tab>` : move forward a tab

`<Shift + Tab>` : move back a tab

`<Ctrl + c>` or `<Ctrl + q>` : quit the chat, disconnect from the session gracefully.

## Requirements
1. Written and tested on MacOS Tahoe 26.3.1 with Python3.14, should be compatible with other Unix based OS.
2. `prompt_toolkit`: see `requirements.txt` for details.

## Installation
Clone the repository, then from the project root:

Create a venv 
```bash
python -m venv .venv
```

Activate the venv
```bash
source .venv/bin/activate
```

Install dependencies with pip
```bash
pip install -r requirements.txt
```

## Running the program locally
When your venv is running and dependecies are installed, run the following to start the server:

```bash
python server_multi.py
```

The server should begin listening on localhost:8080

Connect a (or a few) client(s):

```bash
python client_gui3.py
```

Enter a username for the client, and then you're chatting!

## Troubleshooting

- The server and all clients will be running on the same machine (localhost) unless you update the HOST variable in both files to use a network IP address.
- The server must be started before any clients can connect.

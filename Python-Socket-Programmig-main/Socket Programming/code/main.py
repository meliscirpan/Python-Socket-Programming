import socket
import sys
from threading import Thread
from room_server import RoomServer
from activity_server import ActivityServer
from reservation_server import ReservationServer

def start_server(server, port):
    # Create a socket and bind it to the specified port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', port))
    # Listen for incoming connections
    sock.listen()
    print(f'{server.__class__.__name__} running on port {port}')

    while True:
        # Accept incoming connections
        connection, _ = sock.accept()
        # Handle the request on a separate thread
        handle_request(server, connection)

def handle_request(server, connection):
    try:
        # Receive the request from the client
        request = connection.recv(1024)
        # Process the request and get a response from the server
        response = server.handle_request(request)
        # Send the response back to the client
        connection.sendall(response)
    finally:
        # Close the connection
        connection.close()

def main():
    if len(sys.argv) < 4:
        print('Usage: python main.py room_server_port activity_server_port reservation_server_port')
        return

    host = 'localhost'
    # Get the port numbers from the command line arguments
    room_server_port = int(sys.argv[1])
    activity_server_port = int(sys.argv[2])
    reservation_server_port = int(sys.argv[3])

    # Create the room server, activity server, and reservation server
    room_server = RoomServer()
    activity_server = ActivityServer()
    reservation_server = ReservationServer(host, room_server_port, activity_server_port)

    # Start a new thread for each server and start listening for incoming connections
    Thread(target=start_server, args=(room_server, room_server_port)).start()
    Thread(target=start_server, args=(activity_server, activity_server_port)).start()
    Thread(target=start_server, args=(reservation_server, reservation_server_port)).start()

if __name__ == '__main__':
    main()

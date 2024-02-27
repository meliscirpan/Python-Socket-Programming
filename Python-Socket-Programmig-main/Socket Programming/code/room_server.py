import sqlite3
import socket
import sys

class RoomServer:

    # List of accepted sub-URLs that the server can handle
    accepted_sub_urls = ['/add', '/remove', '/reserve', '/checkavailability']

    # HTML template for responses
    base_html = """<HTML>
<HEAD>
<TITLE>{}</TITLE>
</HEAD>
<BODY>{}</BODY>
</HTML>"""


    def __init__(self):
        # The self.db variable will be used to store the connection to the database. It is initialized as None.
        self.db = None

    def handle_request(self, request):
        # If the database connection has not been established, create it and the tables
        if self.db is None:
            self.db = sqlite3.connect('room.db')
            self.create_tables()

        # Parse the request and get the sub-URL and query parameters
        sub_url, query = self.parse_request(request)

        # Call the appropriate method based on the sub-URL
        if sub_url == '/add':
            response = self.get_add(query)
        elif sub_url == '/remove':
            response = self.get_remove(query)
        elif sub_url == '/reserve':
            response = self.get_reserve(query)
        elif sub_url == '/checkavailability':
            response = self.get_check_availability(query)
        else:
            # If the sub-url is not in the list of accepted sub-urls, return a Bad Request error.
            response = f'HTTP/1.1 400 Bad Request\n\n{self.base_html.format("Error", "Invalid URL")}'.encode()

        return response

    def parse_request(self, request):
        # This method parses the request to get the sub-url and the query parameters.
        # Split the request by spaces and get the second element, which is the URL. Decode it to get a string.
        url = request.split(b' ', 2)[1].decode()

        #Split the URL by the '?' character to separate the sub-url from the query parameters. The sub-url is the first element
        sub_url = url.split('?')[0]
        if not sub_url in self.accepted_sub_urls:
            # If the sub-URL is not in the list of accepted sub-URLs, return it
            return sub_url, False

        # Use a dictionary comprehension to create a dictionary where the keys are the parameter names and the values are the parameter values.
        # Split the query string by '&' to get a list of individual parameters.
        query = {param.split('=')[0]:param.split('=')[1] for param in url.split('?')[1].split('&')}
        return sub_url, query

    def get_add(self, query):
        # Check that the required parameters are present in the query
        parameters_check = self.check_parameters(['name'], query)
        if parameters_check:
            return parameters_check

        # Get the name of the room to add
        room_name = query['name']
        cursor = self.db.cursor()
        # Check if a room with the same name already exists
        cursor.execute("SELECT * FROM rooms WHERE name=?", (room_name,))
        if cursor.fetchone() is not None:
            # If a room with the same name already exists, return a "403 Forbidden" response
            response = f'HTTP/1.1 403 Forbidden\n\n{self.base_html.format("Error", "Room already exists")}'.encode()
            return response

        # Insert a new row into the rooms table with the given name
        cursor.execute("INSERT INTO rooms (name) VALUES (?)", (room_name,))
        self.db.commit()

        # Return a "200 OK" response
        response = f'HTTP/1.1 200 OK\n\n{self.base_html.format("Room Added", f"Room with name {room_name} is successfully added.")}'.encode()
        return response

    def get_remove(self, query):
        # Check that the required parameters are present in the query
        parameters_check = self.check_parameters(['name'], query)
        if parameters_check:
            return parameters_check

        # Get the name of the room to remove
        room_name = query['name']
        cursor = self.db.cursor()
        # Check if a room with the given name exists
        cursor.execute("SELECT * FROM rooms WHERE name=?", (room_name,))
        if cursor.fetchone() is None:
            # If a room with the given name does not exist, return a "403 Forbidden" response
            response = f'HTTP/1.1 403 Forbidden\n\n{self.base_html.format("Error", "Room does not exist")}'.encode()
            return response

        # Delete the row from the rooms table with the given name
        cursor.execute("DELETE FROM rooms WHERE name=?", (room_name,))
        self.db.commit()

        # Return a "200 OK" response
        response = f'HTTP/1.1 200 OK\n\n{self.base_html.format("Room Removed", f"Room with name {room_name} is successfully removed")}'.encode()
        return response

    def get_reserve(self, query):
        # Check if all required parameters are present in the query dictionary
        parameters_check = self.check_parameters(['name', 'day', 'hour', 'duration'], query)
        if parameters_check:
            return parameters_check

        room_name = query['name']
        day = int(query['day'])
        hour = int(query['hour'])
        duration = int(query['duration'])

        # Check if the specified day is a valid day of the week
        if not 1 <= day <= 7:
            # If the day is not a valid day of the week, return a 400 Bad Request response
            response = f'HTTP/1.1 400 Bad Request\n\n{self.base_html.format("Error", "Invalid day parameter")}'.encode()
            return response
        # Check if the specified hour is a valid hour of the day
        if not 9 <= hour <= 17:
            # If the hour is not a valid hour of the day, return a 400 Bad Request response
            response = f'HTTP/1.1 400 Bad Request\n\n{self.base_html.format("Error", "Invalid hour parameter")}'.encode()
            return response
        # Check if the duration is valid for the specified hour
        if hour + duration > 18:
            # If the duration is not valid, return a 400 Bad Request response
            response = f'HTTP/1.1 400 Bad Request\n\n{self.base_html.format("Error", "Invalid duration parameter")}'.encode()
            return response

        # Get a cursor for the database
        cursor = self.db.cursor()
        # Check if the specified room exists in the database
        cursor.execute("SELECT * FROM rooms WHERE name=?", (room_name,))
        if cursor.fetchone() is None:
            # If the room does not exist, return a 400 Bad Request response
            response = f'HTTP/1.1 400 Bad Request\n\n{self.base_html.format("Error", "Room does not exist")}'.encode()
            return response

        # Check if the room is already reserved for any of the hours in the duration
        for d in range(duration):
            cursor.execute("SELECT * FROM reservations WHERE name=? AND day=? AND hour=?", (room_name, day, hour+d))
            if cursor.fetchone() is not None:
                # If the room is already reserved at any of the specified hours, return a 403 Forbidden response
                response = f'HTTP/1.1 403 Forbidden\n\n{self.base_html.format("Error", f"Room is already reserved at {hour+d}")}'.encode()
                return response

            # If all checks pass, reserve the room for the specified duration
            for d in range(duration):
                cursor.execute("INSERT INTO reservations (name, day, hour) VALUES (?, ?, ?)", (room_name, day, hour+d))
                self.db.commit()

            # Return a 200 OK response to confirm that the reservation was successful
            response = f'HTTP/1.1 200 OK\n\n{self.base_html.format("Reservation Successful", f"Room {room_name} is succesfuly reserved.")}'.encode()
            return response

    def get_check_availability(self, query):
        # Check if all required parameters are present in the query dictionary
        parameters_check = self.check_parameters(['name', 'day'], query)
        if parameters_check:
            return parameters_check

        room_name = query['name']
        day = int(query['day'])

        # Get a cursor for the database
        cursor = self.db.cursor()
        # Check if the specified room exists in the database
        cursor.execute("SELECT * FROM rooms WHERE name=?", (room_name,))
        if cursor.fetchone() is None:
            # If the room does not exist, return a 400 Bad Request response
            response = f'HTTP/1.1 400 Bad Request\n\n{self.base_html.format("Error", "Room Does not exist")}'.encode()
            return response

        # Check if the specified day is a valid day of the week
        if not 1 <= day <= 7:
            # If the day is not a valid day of the week, return a 400 Bad Request response
            response = f'HTTP/1.1 400 Bad Request\n\n{self.base_html.format("Error", "Invalid day paramater")}'.encode()
            return response

        # Get a list of all reservations for the specified room and day
        cursor.execute("SELECT hour FROM reservations WHERE name=? AND day=?", (room_name, day))
        reservations = cursor.fetchall()

        # Create a list of all available hours (9-17)
        availability = list(range(9, 18))
        # Remove any reserved hours from the availability list
        for reservation in reservations:
            hour = reservation[0]
            try:
                availability.remove(hour)
            except ValueError:
                pass

        # Create a string of available hours separated by commas
        return_string = ',  '.join(map(str, availability))
        # Create a 200 OK response with the availability information
        response = f'HTTP/1.1 200 OK\n\n{self.base_html.format("Availability", f"The following hours are available: {return_string}")}'.encode()
        return response


    def create_tables(self):
        cursor = self.db.cursor()
        # Create the rooms and reservations tables if they do not already exist
        cursor.execute(
            '''CREATE TABLE IF NOT EXISTS rooms (name text)'''
        )
        cursor.execute(
            '''CREATE TABLE IF NOT EXISTS reservations (name text, day integer, hour integer)'''
        )
        self.db.commit()

    def check_parameters(self, parameters, query):
        # Check that each required parameter is present in the query
        for parameter in parameters:
            if parameter not in query:
                # If a required parameter is not present, return an error response
                response = f'HTTP/1.1 400 Bad Request\n\n{self.base_html.format("Error", f"{parameter} parameter is mandatory")}'.encode()
                return response
        # If all required parameters are present, return False
        return False


def handle_request(server, connection):
    try:
        # Receive the request from the client
        request = connection.recv(1024)
        # Handle the request and get the response from the server
        response = server.handle_request(request)
        # Send the response to the client
        connection.sendall(response)
    finally:
        # Close the connection
        connection.close()

if __name__ == '__main__':
    # Check that the server_port argument was passed to the script
    if len(sys.argv) < 2:
        print('Usage: python main.py server_port')
        exit()

    # Set the server_port variable from the command line argument
    host = 'localhost'
    server_port = int(sys.argv[1])

    # Create a RoomServer instance
    server = RoomServer()

    # Create a TCP/IP socket and bind it to the host and server_port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, server_port))
    # Start listening for incoming connections
    sock.listen()

    # Print a message indicating that the server is running on the specified port
    print(f'{server.__class__.__name__} running on port {server_port}')

    while True:
        # Wait for a connection and pass it to the handle_request function
        connection, _ = sock.accept()
        handle_request(server, connection)

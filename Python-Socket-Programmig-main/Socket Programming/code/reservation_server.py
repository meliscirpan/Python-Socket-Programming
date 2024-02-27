import socket
import sqlite3
import re
import sys

class ReservationServer:
    # List of accepted sub-URLs that the server can handle
    accepted_sub_urls = ['/reserve', '/listavailability', '/display']

    # This is a list of the names of the days of the week.
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    # HTML template for responses
    base_html = """<HTML>
<HEAD>
<TITLE>{}</TITLE>
</HEAD>
<BODY>{}</BODY>
</HTML>"""

    def __init__(self, host, room_server_port, activity_server_port):
        # This is the constructor for the ReservationServer class. It initializes the host, room_server_port, and activity_server_port.
        self.host = host
        self.room_server_port = room_server_port
        self.activity_server_port = activity_server_port

        self.db = None
        # The self.db variable will be used to store the connection to the database. It is initialized as None.

    def handle_request(self, request):
        # If the database connection has not been established, create it and the tables
        if self.db is None:
            self.db = sqlite3.connect('reservation.db')
            self.create_tables()

        # Parse the request and get the sub-URL and query parameters
        sub_url, query = self.parse_request(request)

        # Call the appropriate method based on the sub-URL
        if sub_url == '/reserve':
            response = self.get_reserve(query)
        elif sub_url == '/listavailability':
            response = self.get_listavailability(query)
        elif sub_url == '/display':
            response = self.get_display(query)
        else:
            # If the sub-url is not in the list of accepted sub-urls, return a Bad Request error.
            response = f'HTTP/1.1 400 Bad Request\n\n{self.base_html.format("Error", "Invalid URL")}'.encode()

        return response

    def parse_request(self, request):
        # This method parses the request to get the sub-url and the query parameters.
        # Split the request by spaces and get the second element, which is the URL. Decode it to get a string.
        url = request.split(b' ', 2)[1].decode()

        #Split the URL by the '?' character to separate the sub-url from the query parameters. The sub-url is the first element.
        sub_url = url.split('?')[0]
        if not sub_url in self.accepted_sub_urls:
            # If the sub-URL is not in the list of accepted sub-URLs, return it
            return sub_url, False

        # Use a dictionary comprehension to create a dictionary where the keys are the parameter names and the values are the parameter values.
        # Split the query string by '&' to get a list of individual parameters.
        query = {param.split('=')[0]: param.split('=')[1] for param in url.split('?')[1].split('&')}
        return sub_url, query

    def get_reserve(self, query):
        # Check if required parameters are present in the query dictionary
        parameters_check = self.check_parameters(['activity', 'room', 'day', 'hour', 'duration'], query)
        if parameters_check:
            return parameters_check

        activity_name = query['activity']
        # Connect to the activity server and check if the specified activity exists
        activity_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        activity_server_socket.connect((self.host, self.activity_server_port))
        activity_server_socket.sendall(f'GET /check?name={activity_name} HTTP/1.1\n\n'.encode())
        activity_server_response = activity_server_socket.recv(1024).decode('utf-8')

        # If the activity does not exist, return the 404 Not Found error
        if '404 Not Found' in activity_server_response: return activity_server_response.encode()

        room_name = query['room']
        day = query['day']
        hour = query['hour']
        duration = query['duration']
        # Connect to the room server and attempt to reserve the specified room
        room_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        room_server_socket.connect((self.host, self.room_server_port))
        room_server_socket.sendall(
            f'GET /reserve?name={room_name}&day={day}&hour={hour}&duration={duration} HTTP/1.1\n\n'.encode())
        room_server_response = room_server_socket.recv(1024).decode('utf-8')
        # If the room reservation fails, return the error message
        if '400 Bad Request' in room_server_response or '403 Forbidden' in room_server_response: return room_server_response.encode()

        cursor = self.db.cursor()
        # Insert the reservation into the database
        cursor.execute(
            '''INSERT INTO reservations (room, activity, day, hour, duration) VALUES (?, ?, ?, ?, ?)''',
            (room_name, activity_name, day, hour, duration))
        self.db.commit()
        reservation_id = cursor.lastrowid

        # Return a message indicating that the reservation was successful, along with the reservation ID
        response = f'HTTP/1.1 200 Bad Request\n\n{self.base_html.format("Reservation Succesfull", f"Reservation ID: {reservation_id}")}'.encode()
        return response

    def get_listavailability(self, query):
        # Check if the required "room" parameter is present in the query dictionary
        parameters_check = self.check_parameters(['room'], query)
        if parameters_check:
            return parameters_check

        room_name = query['room']

        # If the "day" parameter is present, only check availability for that day
        if 'day' in query:
            day = int(query['day'])
            request_strings = [(f'GET /checkavailability?name={room_name}&day={day} HTTP/1.1\n\n', self.day_names[day-1])]
        # If the "day" parameter is not present, check availability for all days of the week
        else:
            request_strings = [(f'GET /checkavailability?name={room_name}&day={i} HTTP/1.1\n\n', self.day_names[i-1]) for i in range(1,8)]

        response_string = ''
        # Iterate through each day and request availability from the room server
        for i, (request_string, day) in enumerate(request_strings):
            room_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            room_server_socket.connect(('localhost', self.room_server_port))
            room_server_socket.sendall(request_string.encode())
            room_server_response = room_server_socket.recv(1024).decode('utf-8')
            room_server_socket.close()

            # If the room server returns a 404 Not Found or 400 Bad Request error, return the error message
            if '404 Not Found' in room_server_response or '400 Bad Request' in room_server_response:
                return room_server_response.encode()

            # Extract the availability information from the room server's response
            body = re.search('<BODY>(.*)</BODY>', room_server_response).group(1)
            # Add the availability information to the response string
            response_string += f'For {day}: {body}<br></br>'

        # Return an HTML page with the availability information for each day
        response = f'HTTP/1.1 200 OK\n\n{self.base_html.format("Availabilities", response_string)}'.encode()
        return response

    def get_display(self, query):
        # Check if the required "id" parameter is present in the query dictionary
        parameters_check = self.check_parameters(['id'], query)
        if parameters_check:
            return parameters_check
        # Get the reservations for the specified reservation ID
        reservation_id = query['id']
        cursor = self.db.cursor()
        cursor.execute('''SELECT * FROM reservations WHERE id=?''', (reservation_id,))
        reservation = cursor.fetchone()
        if reservation is None:
            # Reservation does not exist, return a 404 Not Found response
            return b'HTTP/1.1 404 Not Found'

        # Create an HTML page with the reservation details
        room_name = reservation[1]
        activity_name = reservation[2]
        day = reservation[3]
        hour = reservation[4]
        duration = reservation[5]
        body = f'''
        <h1>Reservation Details</h1>
        <p>Room name: {room_name}</p>
        <p>Activity name: {activity_name}</p>
        <p>Day: {self.day_names[day - 1]}</p>
        <p>Time: {hour}:00 - {hour+duration}:00</p>
        <p>Duration: {duration} hours</p>
        '''

        response = f'HTTP/1.1 200 OK\n\n{self.base_html.format("Reservation Info", body)}'.encode()
        return response

    def create_tables(self):
        # Create the "reservations" table in the database if it does not already exist
        cursor = self.db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY,
                room TEXT NOT NULL,
                activity TEXT NOT NULL,
                day INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                duration INTEGER NOT NULL
            )
        ''')
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
    if len(sys.argv) < 4:
        print('Usage: python main.py room_server_port activity_server_port reservation_server_port')
        exit()

    host = 'localhost'
    room_server_port = int(sys.argv[1])
    activity_server_port = int(sys.argv[2])
    reservation_server_port = int(sys.argv[3])

    server = ReservationServer(host, room_server_port, activity_server_port)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', reservation_server_port))
    sock.listen()
    print(f'{server.__class__.__name__} running on port {reservation_server_port}')

    while True:
        connection, _ = sock.accept()
        handle_request(server, connection)

import sqlite3
import sys
import socket

class ActivityServer:
    # List of accepted sub-URLs that the server can handle
    accepted_sub_urls = ['/add', '/remove', '/check']

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
            self.db = sqlite3.connect('activity.db')
            self.create_tables()

        # Parse the request and get the sub-URL and query parameters
        sub_url, query = self.parse_request(request)

        # Call the appropriate method based on the sub-URL
        if sub_url == '/add':
            response = self.get_add(query)
        elif sub_url == '/remove':
            response = self.get_remove(query)
        elif sub_url == '/check':
            response = self.get_check(query)
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
            # If the required parameters are not present, return the error response
            return parameters_check

        # Get the activity name from the query parameters
        activity_name = query['name']

        # Get a cursor for the database connection
        cursor = self.db.cursor()

        # Check if an activity with the same name already exists
        cursor.execute("SELECT * FROM activities WHERE name=?", (activity_name,))
        if cursor.fetchone() is not None:
            # If the activity already exists, return a "403 Forbidden" response
            response = f'HTTP/1.1 403 Forbidden\n\n{self.base_html.format("Error", "Activity already exists")}'.encode()
            return response

        # Insert the new activity into the database
        cursor.execute("INSERT INTO activities (name) VALUES (?)", (activity_name,))
        self.db.commit()

        # Return a "200 OK" response indicating that the activity was added
        response = f'HTTP/1.1 200 OK\n\n{self.base_html.format("Activity Added", f"Activity with name {activity_name} is added")}'.encode()
        return response

    def get_remove(self, query):
        # Check that the required parameters are present in the query
        parameters_check = self.check_parameters(['name'], query)
        if parameters_check:
            # If the required parameters are not present, return the error response
            return parameters_check

        # Get the activity name from the query parameters
        activity_name = query['name']

        # Get a cursor for the database connection
        cursor = self.db.cursor()

        # Check if an activity with the given name exists
        cursor.execute("SELECT * FROM activities WHERE name=?", (activity_name,))
        if cursor.fetchone() is None:
            # If the activity does not exist, return a "403 Forbidden" response
            response = f'HTTP/1.1 403 Forbidden\n\n{self.base_html.format("Error", f"Activity with name {activity_name} does not exist")}'.encode()
            return response

        # Delete the activity from the database
        cursor.execute("DELETE FROM activities WHERE name=?", (activity_name,))
        self.db.commit()

        # Return a "200 OK" response indicating that the activity was removed
        response = f'HTTP/1.1 200 OK\n\n{self.base_html.format("Activity Removed", f"Activity with name {activity_name} is removed")}'.encode()
        return response

    def get_check(self, query):
        # Check that the required parameters are present in the query
        parameters_check = self.check_parameters(['name'], query)
        if parameters_check:
            # If the required parameters are not present, return the error response
            return parameters_check

        # Get the activity name from the query parameters
        activity_name = query['name']

        # Get a cursor for the database connection
        cursor = self.db.cursor()

        # Check if an activity with the given name exists
        cursor.execute("SELECT * FROM activities WHERE name=?", (activity_name,))
        if cursor.fetchone() is not None:
            # If the activity exists, return a "200 OK" response indicating that the activity exists
            response = f'HTTP/1.1 200 OK\n\n{self.base_html.format("Activity Check", f"Activity Exists")}'.encode()
            return response

        else:
            # If the activity does not exist, return a "404 Not Found" response indicating that the activity does not exist
            response = f'HTTP/1.1 404 Not Found\n\n{self.base_html.format("Activity Check", f"Activity does not exist")}'.encode()
            return response


    def create_tables(self):
        cursor = self.db.cursor()
        # Create the "activities" table if it does not already exist
        cursor.execute('CREATE TABLE IF NOT EXISTS activities (name text PRIMARY KEY)')
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
    if len(sys.argv) < 2:
        print('Usage: python main.py server_port')
        exit()

    # Set the server_port variable from the command line argument
    host = 'localhost'
    server_port = int(sys.argv[1])

    # Create an instance of the ActivityServer class
    server = ActivityServer()

    # Create a TCP/IP socket and bind it to the host and server_port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', server_port))
    # Start listening for incoming connections
    sock.listen()

    # Print a message indicating that the server is running on the specified port
    print(f'{server.__class__.__name__} running on port {server_port}')

    while True:
        # Wait for a connection and pass it to the handle_request function
        connection, _ = sock.accept()
        handle_request(server, connection)

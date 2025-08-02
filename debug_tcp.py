#!/usr/bin/env python3
"""Debug TCP MCP server responses."""
import socket
import json

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.connect(('localhost', 3333))
    
    # Send initialize
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }
    sock.send((json.dumps(request) + '\n').encode())
    
    # Read response
    data = sock.recv(4096)
    print("Raw response:")
    print(data.decode())
    
    # Try to parse
    try:
        response = json.loads(data.decode().strip())
        print("\nParsed response:")
        print(json.dumps(response, indent=2))
    except:
        print("\nCould not parse as JSON")
        
finally:
    sock.close()
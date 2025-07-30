#!/usr/bin/env python3
"""
HTTP wrapper for TCP MCP server to work with Cloudflare tunnel.
Provides an HTTP interface that forwards requests to the TCP server.
"""
from flask import Flask, request, jsonify
import socket
import json
import logging

app = Flask(__name__)
logger = logging.getLogger(__name__)

MCP_HOST = 'localhost'
MCP_PORT = 3333


@app.route('/', methods=['POST'])
def handle_mcp_request():
    """Handle MCP requests over HTTP and forward to TCP server."""
    try:
        # Get JSON-RPC request
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Forward to TCP server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30)
        sock.connect((MCP_HOST, MCP_PORT))
        
        # Send request
        sock.send((json.dumps(data) + '\n').encode())
        
        # Read response
        response_data = sock.recv(65536)
        sock.close()
        
        if response_data:
            response = json.loads(response_data.decode().strip())
            return jsonify(response)
        else:
            return jsonify({"error": "No response from MCP server"}), 502
            
    except socket.timeout:
        return jsonify({"error": "MCP server timeout"}), 504
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        # Check if MCP server is responsive
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((MCP_HOST, MCP_PORT))
        sock.close()
        return jsonify({"status": "healthy", "mcp_server": "connected"})
    except:
        return jsonify({"status": "unhealthy", "mcp_server": "disconnected"}), 503


if __name__ == '__main__':
    # Run HTTP wrapper on port 8080
    print(f"Starting HTTP wrapper for MCP server at http://localhost:8080")
    print(f"Forwarding to TCP MCP server at {MCP_HOST}:{MCP_PORT}")
    app.run(host='0.0.0.0', port=8080, debug=False)
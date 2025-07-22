"""
Health check endpoint for MCP server
"""
import json
import time
from typing import Dict, Any

class HealthCheck:
    """Health check functionality for MCP server"""
    
    def __init__(self, server):
        self.server = server
        self.start_time = time.time()
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status of the server"""
        uptime = time.time() - self.start_time
        
        return {
            "status": "healthy",
            "uptime_seconds": round(uptime, 2),
            "active_sessions": len(self.server.sessions),
            "server_info": {
                "port": self.server.port,
                "version": "1.0.0",
                "agent_type": "software_engineer"
            },
            "timestamp": time.time()
        }
    
    async def handle_health_request(self, session_id: str, message: Dict) -> Dict:
        """Handle health check requests"""
        health_status = self.get_health_status()
        
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": health_status
        }

"""
SSL/HTTPS Configuration for Expenso
"""

import os
import ssl

class SSLConfig:
    """SSL configuration management"""
    
    def __init__(self):
        self.ssl_dir = "ssl"
        self.cert_file = os.path.join(self.ssl_dir, "cert.pem")
        self.key_file = os.path.join(self.ssl_dir, "key.pem")
        self.port = 5000
        self.host = '0.0.0.0'
    
    def is_ssl_available(self):
        """Check if SSL certificates are available"""
        return os.path.exists(self.cert_file) and os.path.exists(self.key_file)
    
    def create_ssl_context(self):
        """Create SSL context for HTTPS"""
        if not self.is_ssl_available():
            return None
        
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            context.load_cert_chain(self.cert_file, self.key_file)
            return context
        except Exception as e:
            print(f"Error creating SSL context: {e}")
            return None
    
    def get_server_url(self, use_https=None):
        """Get server URL based on SSL availability"""
        if use_https is None:
            use_https = self.is_ssl_available()
        
        protocol = "https" if use_https else "http"
        return f"{protocol}://{self.host}:{self.port}"
    
    def get_local_url(self, use_https=None):
        """Get localhost URL for browser access"""
        if use_https is None:
            use_https = self.is_ssl_available()
        
        protocol = "https" if use_https else "http"
        return f"{protocol}://localhost:{self.port}"

# Global SSL configuration instance
ssl_config = SSLConfig()

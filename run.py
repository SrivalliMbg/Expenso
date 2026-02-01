import os
import ssl
from app import create_app

app = create_app()

def create_ssl_context():
    """Create SSL context for HTTPS"""
    cert_file = "ssl/cert.pem"
    key_file = "ssl/key.pem"
    
    if os.path.exists(cert_file) and os.path.exists(key_file):
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.load_cert_chain(cert_file, key_file)
        return context
    else:
        print("⚠️  SSL certificates not found!")
        print("Run 'python generate_ssl_cert.py' to generate certificates")
        return None

if __name__ == "__main__":
    # Check for SSL certificates
    ssl_context = create_ssl_context()
    
    if ssl_context:
        print("🔐 Starting Expenso with HTTPS...")
        print("🌐 Access your app at: https://localhost:5000")
        print("⚠️  You may need to accept the self-signed certificate in your browser")
        app.run(debug=True, ssl_context=ssl_context, host='0.0.0.0', port=5000)
    else:
        print("🔓 Starting Expenso with HTTP...")
        print("🌐 Access your app at: http://localhost:5000")
        print("💡 Run 'python generate_ssl_cert.py' to enable HTTPS")
        app.run(debug=True, host='0.0.0.0', port=5000)

#!/usr/bin/env python3
"""
Expenso Server Startup Script
Handles both HTTP and HTTPS startup with SSL certificate management
"""

import os
import sys
import subprocess
import ssl
from app import create_app

def check_ssl_certificates():
    """Check if SSL certificates exist"""
    cert_file = "ssl/cert.pem"
    key_file = "ssl/key.pem"
    return os.path.exists(cert_file) and os.path.exists(key_file)

def generate_ssl_certificates():
    """Generate SSL certificates if they don't exist"""
    print("🔐 Generating SSL certificates...")
    try:
        result = subprocess.run([sys.executable, "generate_ssl_cert.py"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ SSL certificates generated successfully!")
            return True
        else:
            print(f"❌ Error generating certificates: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error running certificate generator: {e}")
        return False

def create_ssl_context():
    """Create SSL context for HTTPS"""
    cert_file = "ssl/cert.pem"
    key_file = "ssl/key.pem"
    
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.load_cert_chain(cert_file, key_file)
        return context
    except Exception as e:
        print(f"❌ Error creating SSL context: {e}")
        return None

def start_server(use_https=True, host='0.0.0.0', port=5000, debug=True):
    """Start the Flask server with or without HTTPS"""
    app = create_app()
    
    if use_https:
        if not check_ssl_certificates():
            print("⚠️  SSL certificates not found!")
            print("🔧 Attempting to generate certificates...")
            if not generate_ssl_certificates():
                print("❌ Failed to generate certificates. Starting with HTTP...")
                use_https = False
            else:
                print("✅ Certificates generated successfully!")
        
        if use_https:
            ssl_context = create_ssl_context()
            if ssl_context:
                print("🔐 Starting Expenso with HTTPS...")
                print(f"🌐 Access your app at: https://{host}:{port}")
                print("⚠️  You may need to accept the self-signed certificate in your browser")
                print("🔒 TOTP authentication is now secure with HTTPS!")
                app.run(debug=debug, ssl_context=ssl_context, host=host, port=port)
                return
            else:
                print("❌ Failed to create SSL context. Starting with HTTP...")
                use_https = False
    
    if not use_https:
        print("🔓 Starting Expenso with HTTP...")
        print(f"🌐 Access your app at: http://{host}:{port}")
        print("💡 Run 'python generate_ssl_cert.py' to enable HTTPS")
        print("⚠️  TOTP authentication is less secure over HTTP")
        app.run(debug=debug, host=host, port=port)

def main():
    """Main function to handle command line arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Start Expenso server')
    parser.add_argument('--http', action='store_true', 
                       help='Force HTTP mode (disable HTTPS)')
    parser.add_argument('--https', action='store_true', 
                       help='Force HTTPS mode (generate certificates if needed)')
    parser.add_argument('--host', default='0.0.0.0', 
                       help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=5000, 
                       help='Port to bind to (default: 5000)')
    parser.add_argument('--no-debug', action='store_true', 
                       help='Disable debug mode')
    
    args = parser.parse_args()
    
    # Determine HTTPS mode
    if args.http:
        use_https = False
    elif args.https:
        use_https = True
    else:
        # Auto-detect based on certificate availability
        use_https = check_ssl_certificates()
    
    print("🚀 Starting Expenso Server...")
    print("=" * 50)
    
    start_server(
        use_https=use_https,
        host=args.host,
        port=args.port,
        debug=not args.no_debug
    )

if __name__ == "__main__":
    main()

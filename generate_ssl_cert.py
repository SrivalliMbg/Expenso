#!/usr/bin/env python3
"""
SSL Certificate Generator for Expenso
Generates self-signed SSL certificates for HTTPS development
"""

import os
import subprocess
import sys
from datetime import datetime, timedelta

def generate_ssl_certificates():
    """Generate self-signed SSL certificates"""
    
    # Create ssl directory if it doesn't exist
    ssl_dir = "ssl"
    if not os.path.exists(ssl_dir):
        os.makedirs(ssl_dir)
        print(f"Created SSL directory: {ssl_dir}")
    
    # Certificate details
    cert_file = os.path.join(ssl_dir, "cert.pem")
    key_file = os.path.join(ssl_dir, "key.pem")
    
    # Check if certificates already exist
    if os.path.exists(cert_file) and os.path.exists(key_file):
        print("SSL certificates already exist!")
        print(f"Certificate: {cert_file}")
        print(f"Private Key: {key_file}")
        return cert_file, key_file
    
    try:
        # Generate private key
        print("Generating private key...")
        subprocess.run([
            "openssl", "genrsa", "-out", key_file, "2048"
        ], check=True)
        
        # Generate certificate
        print("Generating certificate...")
        subprocess.run([
            "openssl", "req", "-new", "-x509", "-key", key_file, 
            "-out", cert_file, "-days", "365", "-subj",
            "/C=US/ST=State/L=City/O=Expenso/OU=IT/CN=localhost"
        ], check=True)
        
        print("✅ SSL certificates generated successfully!")
        print(f"Certificate: {cert_file}")
        print(f"Private Key: {key_file}")
        print("Valid for 365 days")
        
        return cert_file, key_file
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error generating certificates: {e}")
        print("Make sure OpenSSL is installed on your system")
        return None, None
    except FileNotFoundError:
        print("❌ OpenSSL not found. Please install OpenSSL:")
        print("  - Windows: Download from https://slproweb.com/products/Win32OpenSSL.html")
        print("  - macOS: brew install openssl")
        print("  - Linux: sudo apt-get install openssl")
        return None, None

def generate_ssl_certificates_python():
    """Generate SSL certificates using Python cryptography library"""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from datetime import datetime, timedelta
        import ipaddress
        
        # Create ssl directory if it doesn't exist
        ssl_dir = "ssl"
        if not os.path.exists(ssl_dir):
            os.makedirs(ssl_dir)
            print(f"Created SSL directory: {ssl_dir}")
        
        cert_file = os.path.join(ssl_dir, "cert.pem")
        key_file = os.path.join(ssl_dir, "key.pem")
        
        # Check if certificates already exist
        if os.path.exists(cert_file) and os.path.exists(key_file):
            print("SSL certificates already exist!")
            return cert_file, key_file
        
        print("Generating SSL certificates using Python cryptography...")
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Save private key
        with open(key_file, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "City"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Expenso"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # Save certificate
        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        print("✅ SSL certificates generated successfully!")
        print(f"Certificate: {cert_file}")
        print(f"Private Key: {key_file}")
        print("Valid for 365 days")
        
        return cert_file, key_file
        
    except ImportError:
        print("❌ cryptography library not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "cryptography"], check=True)
        return generate_ssl_certificates_python()
    except Exception as e:
        print(f"❌ Error generating certificates: {e}")
        return None, None

if __name__ == "__main__":
    print("🔐 SSL Certificate Generator for Expenso")
    print("=" * 50)
    
    # Try OpenSSL first, then fallback to Python
    cert_file, key_file = generate_ssl_certificates()
    
    if cert_file is None:
        print("\nTrying Python cryptography library...")
        cert_file, key_file = generate_ssl_certificates_python()
    
    if cert_file and key_file:
        print("\n🚀 Next steps:")
        print("1. Run your Flask app with HTTPS enabled")
        print("2. Access your app at https://localhost:5000")
        print("3. Accept the self-signed certificate in your browser")
    else:
        print("\n❌ Failed to generate SSL certificates")
        print("Please install OpenSSL or ensure cryptography library is available")

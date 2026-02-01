import pyotp
import qrcode
import io
import base64
from flask import current_app

class TOTPManager:
    """TOTP (Time-based One-Time Password) management utilities"""
    
    @staticmethod
    def generate_secret():
        """Generate a new TOTP secret"""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_qr_code(secret, username, issuer="Expenso"):
        """Generate QR code for TOTP setup"""
        # Create TOTP URI
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=username,
            issuer_name=issuer
        )
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 string for embedding in HTML
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    @staticmethod
    def verify_totp(secret, token):
        """Verify a TOTP token"""
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)  # Allow 1 window of tolerance
    
    @staticmethod
    def get_current_totp(secret):
        """Get current TOTP code (for testing purposes)"""
        totp = pyotp.TOTP(secret)
        return totp.now()
    
    @staticmethod
    def is_totp_enabled(user_id):
        """Check if TOTP is enabled for a user"""
        try:
            cursor = current_app.mysql.cursor(dictionary=True)
            cursor.execute("SELECT totp_secret FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            cursor.close()
            
            return user and user.get('totp_secret') is not None
        except Exception as e:
            current_app.logger.error(f"Error checking TOTP status: {str(e)}")
            return False
    
    @staticmethod
    def get_user_totp_secret(user_id):
        """Get TOTP secret for a user"""
        try:
            cursor = current_app.mysql.cursor(dictionary=True)
            cursor.execute("SELECT totp_secret FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            cursor.close()
            
            return user.get('totp_secret') if user else None
        except Exception as e:
            current_app.logger.error(f"Error getting TOTP secret: {str(e)}")
            return None
    
    @staticmethod
    def enable_totp(user_id, secret):
        """Enable TOTP for a user"""
        try:
            cursor = current_app.mysql.cursor()
            cursor.execute(
                "UPDATE users SET totp_secret = %s WHERE id = %s",
                (secret, user_id)
            )
            current_app.mysql.commit()
            cursor.close()
            return True
        except Exception as e:
            current_app.logger.error(f"Error enabling TOTP: {str(e)}")
            return False
    
    @staticmethod
    def disable_totp(user_id):
        """Disable TOTP for a user"""
        try:
            cursor = current_app.mysql.cursor()
            cursor.execute(
                "UPDATE users SET totp_secret = NULL WHERE id = %s",
                (user_id,)
            )
            current_app.mysql.commit()
            cursor.close()
            return True
        except Exception as e:
            current_app.logger.error(f"Error disabling TOTP: {str(e)}")
            return False

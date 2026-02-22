import pyotp
import qrcode
import io
import base64
from flask import current_app, g

# Use PIL image factory so QR code is a real PNG (requires Pillow)
try:
    from qrcode.image.pil import PilImage
    _qr_image_factory = PilImage
except ImportError:
    _qr_image_factory = None  # fallback to qrcode default if no PIL


class TOTPManager:
    """TOTP (Time-based One-Time Password) management utilities"""
    
    @staticmethod
    def generate_secret():
        """Generate a new TOTP secret"""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_qr_code(secret, username, issuer="Expenso"):
        """Generate QR code for TOTP setup. Returns a data:image/png;base64,... string."""
        # Create TOTP URI (safe for QR: alphanumeric + a few chars)
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=username,
            issuer_name=issuer
        )
        
        # Build QRCode; use PIL factory when available so we get a proper PNG
        kwargs = {
            "version": 1,
            "error_correction": qrcode.constants.ERROR_CORRECT_L,
            "box_size": 10,
            "border": 4,
        }
        if _qr_image_factory is not None:
            kwargs["image_factory"] = _qr_image_factory

        qr = qrcode.QRCode(**kwargs)
        qr.add_data(totp_uri)
        qr.make(fit=True) 
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 PNG for embedding in HTML
        buffer = io.BytesIO()
        try:
            img.save(buffer, format="PNG")
        except Exception as e:
            if current_app:
                current_app.logger.warning("QR save failed (PIL may be missing): %s", e)
            raise ValueError("QR image could not be generated. Install Pillow: pip install Pillow") from e
        buffer.seek(0)
        img_str = base64.b64encode(buffer.getvalue()).decode("ascii")
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
            cursor = g.mysql.cursor(dictionary=True)
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
            cursor = g.mysql.cursor(dictionary=True)
            cursor.execute("SELECT totp_secret FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            cursor.close()
            
            return user.get('totp_secret') if user else None
        except Exception as e:
            current_app.logger.error(f"Error getting TOTP secret: {str(e)}")
            return None
    
    @staticmethod
    def enable_totp(user_id, secret):
        """Enable TOTP for a user; set two_factor_enabled = True."""
        try:
            cursor = g.mysql.cursor()
            cursor.execute(
                "UPDATE users SET totp_secret = %s, two_factor_enabled = TRUE WHERE id = %s",
                (secret, user_id)
            )
            g.mysql.commit()
            cursor.close()
            return True
        except Exception as e:
            if current_app and getattr(current_app, "logger", None):
                current_app.logger.error("Error enabling TOTP: %s", str(e))
            return False
    
    @staticmethod
    def disable_totp(user_id):
        """Disable TOTP for a user; set two_factor_enabled = FALSE."""
        try:
            cursor = g.mysql.cursor()
            cursor.execute(
                "UPDATE users SET totp_secret = NULL, two_factor_enabled = 0 WHERE id = %s",
                (user_id,)
            )
            g.mysql.commit()
            cursor.close()
            return True
        except Exception as e:
            if current_app and getattr(current_app, "logger", None):
                current_app.logger.error("Error disabling TOTP: %s", str(e))
            return False

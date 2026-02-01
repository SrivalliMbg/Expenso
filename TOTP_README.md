# TOTP (Two-Factor Authentication) Implementation

This document describes the TOTP (Time-based One-Time Password) implementation added to the Expenso application.

## Overview

TOTP adds an extra layer of security to user authentication by requiring a time-based code from an authenticator app in addition to the username and password.

## Features

- ✅ TOTP secret generation and QR code creation
- ✅ User-friendly setup process with step-by-step instructions
- ✅ Integration with popular authenticator apps (Google Authenticator, Microsoft Authenticator, Authy, etc.)
- ✅ Seamless login flow with TOTP verification
- ✅ TOTP management (enable/disable) from user profile
- ✅ Secure storage of TOTP secrets in database
- ✅ Automatic form submission when 6-digit code is entered

## Installation

1. **Install Dependencies**
   ```bash
   pip install -r requirements_simple.txt
   ```

2. **Database Migration**
   Run the SQL migration script to add TOTP support to your database:
   ```sql
   -- Execute the contents of database/migration_add_totp.sql
   ALTER TABLE users ADD COLUMN totp_secret VARCHAR(32) NULL;
   ALTER TABLE users ADD COLUMN totp_enabled_at TIMESTAMP NULL;
   CREATE INDEX idx_users_totp_secret ON users(totp_secret);
   ```

## Usage

### For Users

#### Setting up TOTP
1. Log in to your account
2. Go to your Profile page
3. In the Security Settings section, click "Enable TOTP"
4. Follow the setup instructions:
   - Install an authenticator app on your mobile device
   - Scan the QR code or manually enter the secret key
   - Enter the 6-digit code to verify setup

#### Logging in with TOTP
1. Enter your username and password
2. If TOTP is enabled, you'll be prompted to enter the 6-digit code
3. Open your authenticator app and enter the current code
4. The form will auto-submit when you enter 6 digits

#### Managing TOTP
- **Enable**: Go to Profile → Security Settings → Enable TOTP
- **Disable**: Go to Profile → Security Settings → Disable TOTP

### For Developers

#### API Endpoints

**TOTP Setup**
```http
POST /totp/setup
Content-Type: application/json

{
  "user_id": 123
}
```

**TOTP Verification (during setup)**
```http
POST /totp/verify
Content-Type: application/json

{
  "user_id": 123,
  "secret": "JBSWY3DPEHPK3PXP",
  "totp_code": "123456"
}
```

**TOTP Status Check**
```http
GET /totp/status?user_id=123
```

**Disable TOTP**
```http
POST /totp/disable
Content-Type: application/json

{
  "user_id": 123
}
```

**Login with TOTP**
```http
POST /login
Content-Type: application/json

{
  "username": "user",
  "password": "password",
  "totp_code": "123456"  // Optional, only if TOTP is enabled
}
```

#### Response Codes

- `200`: Success
- `400`: Bad request (missing parameters)
- `401`: Invalid credentials or TOTP code
- `404`: User not found
- `500`: Server error

#### TOTP Manager Class

The `TOTPManager` class in `app/totp_utils.py` provides utility methods:

```python
from app.totp_utils import TOTPManager

# Generate a new secret
secret = TOTPManager.generate_secret()

# Generate QR code
qr_code = TOTPManager.generate_qr_code(secret, username, issuer)

# Verify TOTP code
is_valid = TOTPManager.verify_totp(secret, totp_code)

# Check if TOTP is enabled for user
is_enabled = TOTPManager.is_totp_enabled(user_id)

# Enable/disable TOTP
TOTPManager.enable_totp(user_id, secret)
TOTPManager.disable_totp(user_id)
```

## Security Considerations

1. **Secret Storage**: TOTP secrets are stored in the database and should be treated as sensitive data
2. **Time Window**: TOTP codes are valid for 30 seconds with a 1-window tolerance (60 seconds total)
3. **Rate Limiting**: Consider implementing rate limiting for login attempts
4. **Backup Codes**: Consider implementing backup codes for account recovery
5. **Session Management**: TOTP verification is required on each login

## Supported Authenticator Apps

- Google Authenticator (iOS/Android)
- Microsoft Authenticator (iOS/Android)
- Authy (iOS/Android)
- 1Password (iOS/Android)
- Any TOTP-compatible app

## File Structure

```
app/
├── totp_utils.py          # TOTP utility functions
└── routes.py              # Updated with TOTP endpoints

templates/
├── login.html             # Updated with TOTP input
├── totp_setup.html        # TOTP setup page
└── profile.html           # Updated with TOTP management

static/js/
└── main.js                # Updated with TOTP handling

database/
└── migration_add_totp.sql # Database migration script
```

## Testing

To test the TOTP implementation:

1. **Setup Test**:
   - Register a new user or use existing user
   - Go to profile and enable TOTP
   - Follow setup process

2. **Login Test**:
   - Try logging in without TOTP code (should prompt for code)
   - Enter valid TOTP code (should login successfully)
   - Enter invalid TOTP code (should show error)

3. **Management Test**:
   - Disable TOTP from profile
   - Try logging in (should not require TOTP)
   - Re-enable TOTP

## Troubleshooting

### Common Issues

1. **QR Code not displaying**: Check if PIL/Pillow is installed correctly
2. **TOTP codes not working**: Ensure system time is synchronized
3. **Setup fails**: Verify database migration was run successfully
4. **Login issues**: Check browser console for JavaScript errors

### Debug Mode

To enable debug logging for TOTP operations, add to your Flask app:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Future Enhancements

- [ ] Backup codes for account recovery
- [ ] SMS-based 2FA as alternative
- [ ] Remember device functionality
- [ ] Admin panel for TOTP management
- [ ] Audit logging for security events
- [ ] Rate limiting for failed attempts

## Dependencies

- `pyotp==2.9.0` - TOTP implementation
- `qrcode==7.4.2` - QR code generation
- `Pillow==10.0.1` - Image processing for QR codes

## License

This TOTP implementation is part of the Expenso application and follows the same license terms.

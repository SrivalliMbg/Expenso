document.addEventListener("DOMContentLoaded", () => {
  // ----- Registration -----
  const registerForm = document.getElementById("registerForm");
  if (registerForm) {
    const regPhone = document.getElementById("phone");
    if (regPhone) regPhone.addEventListener("input", function() { this.value = this.value.replace(/\D/g, "").slice(0, 15); });
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const fullName = document.getElementById("username").value.trim();
      const username = fullName.toLowerCase().replace(/\s+/g, "");

      const countryCodeEl = document.getElementById("countryCode");
      const phoneEl = document.getElementById("phone");
      const phoneVal = phoneEl ? (countryCodeEl ? countryCodeEl.value : "") + (phoneEl.value || "").replace(/\D/g, "") : "";
      const data = {
        username,
        email: document.getElementById("email").value.trim(),
        password: document.getElementById("password").value,
        status: document.getElementById("status").value,
        dob: document.getElementById("dob").value,
        phone: phoneVal || (phoneEl ? phoneEl.value.trim() : ""),
        profession: document.getElementById("profession").value
      };

      try {
        const res = await fetch("/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data)
        });

        const result = await res.json();
        if (res.status === 201) {
          alert(result.message || "Registration successful!");
          window.location.href = "/login_page";
        } else {
          // Show the actual error message from server
          alert(result.message || "Registration failed. Please check your information and try again.");
        }
      } catch (err) {
        // Show actual error if available
        const errorMsg = err.message || "Network error. Please check your connection and try again.";
        alert(`Registration failed: ${errorMsg}`);
        console.error("Registration error:", err);
      }
    });
  }

  // ----- Login with TOTP Support -----
const loginForm = document.getElementById("loginForm");
if (loginForm) {
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    const totpCode = document.getElementById("totpCode") ? document.getElementById("totpCode").value : null;

    const data = {
      username,
      password
    };

    // Add TOTP code if provided
    if (totpCode) {
      data.totp_code = totpCode;
    }

    try {
      const res = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });

      const result = await res.json();

      if (res.status === 200) {
        if (result.requires_totp) {
          // Show TOTP input section
          showTOTPSection();
          alert("Please enter the 6-digit code from your authenticator app.");
          return;
        } else if (result.user) {
          // Login successful
          sessionStorage.setItem("user", JSON.stringify(result.user));
          window.location.href = `/?username=${result.user.username}`;
          return;
        }
      }

      // Show the actual error message from server
      alert(result.message || "Login failed. Please check your credentials.");
      
    } catch (err) {
      // Show actual error if available
      const errorMsg = err.message || "Network error. Please check your connection and try again.";
      alert(`Login failed: ${errorMsg}`);
      console.error("Login error:", err);
    }
  });
}

// Function to show TOTP input section
function showTOTPSection() {
  const totpSection = document.getElementById("totpSection");
  const loginButton = document.getElementById("loginButton");
  
  if (totpSection) {
    totpSection.style.display = "block";
    totpSection.scrollIntoView({ behavior: "smooth" });
    
    // Focus on TOTP input
    const totpInput = document.getElementById("totpCode");
    if (totpInput) {
      totpInput.focus();
    }
  }
  
  if (loginButton) {
    loginButton.textContent = "Complete Login";
  }
}

// TOTP input validation
document.addEventListener("DOMContentLoaded", () => {
  const totpInput = document.getElementById("totpCode");
  if (totpInput) {
    totpInput.addEventListener("input", function(e) {
      // Only allow numbers
      e.target.value = e.target.value.replace(/[^0-9]/g, '');
      
      // Auto-submit when 6 digits are entered
      if (e.target.value.length === 6) {
        setTimeout(() => {
          const loginForm = document.getElementById("loginForm");
          if (loginForm) {
            loginForm.dispatchEvent(new Event("submit"));
          }
        }, 500);
      }
    });
  }
});


  // ----- Profile Page -----
  // ----- Profile Page -----
const profileSection = document.getElementById("profileInfo");

if (profileSection) {
  try {
    const user = JSON.parse(sessionStorage.getItem("user"));

    if (!user || !user.username) {
      window.location.href = "/login_page";
    } else {
      // Fill in profile fields (handle null/undefined)
      const formatDate = (d) => { if (!d) return '—'; try { return new Date(d).toLocaleDateString(); } catch (_) { return d || '—'; } };
      document.getElementById("profileName").textContent = user.username || '—';
      document.getElementById("profileEmail").textContent = user.email || '—';
      document.getElementById("profileStatus").textContent = user.status || '—';
      document.getElementById("profileDOB").textContent = formatDate(user.dob);
      document.getElementById("profilePhone").textContent = user.phone || '—';
      document.getElementById("profileProfession").textContent = user.profession || '—';

      // Personalized greeting
      const header = document.getElementById("profileNameHeader");
      if (header) {
        header.textContent = user.username || 'User';
      }
    }
  } catch (err) {
    console.error("Error loading profile:", err);
    window.location.href = "/login_page";
  }
}


  // ----- Logout -----
  const logoutBtn = document.getElementById("logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", () => {
      sessionStorage.removeItem("user");
      window.location.href = "/login_page";
    });
  }

  // ----- Password Toggle -----
  window.togglePassword = function () {
    const passwordInput = document.getElementById("password");
    if (passwordInput) {
      passwordInput.type = passwordInput.type === "password" ? "text" : "password";
    }
  };
});

document.addEventListener("DOMContentLoaded", () => {
  // ----- Registration -----
  const registerForm = document.getElementById("registerForm");
  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const fullName = document.getElementById("username").value.trim();
      const username = fullName.toLowerCase().replace(/\s+/g, "");

      const data = {
        username,
        email: document.getElementById("email").value.trim(),
        password: document.getElementById("password").value,
        status: document.getElementById("status").value,
        dob: document.getElementById("dob").value,
        phone: document.getElementById("phone").value.trim(),
        profession: document.getElementById("profession").value
      };

      try {
        const res = await fetch("/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data)
        });

        const result = await res.json();
        alert(result.message);
        if (res.status === 201) window.location.href = "/login_page";
      } catch (err) {
        alert("Registration failed. Please try again.");
        console.error(err);
      }
    });
  }

  // ----- Login -----
  // ----- Login -----
const loginForm = document.getElementById("loginForm");
if (loginForm) {
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const data = {
      username: document.getElementById("username").value.trim(),
      password: document.getElementById("password").value
    };

    try {
      const res = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });

      const result = await res.json();
      alert(result.message);

      if (res.status === 200 && result.user) {
        sessionStorage.setItem("user", JSON.stringify(result.user));
        window.location.href = `/?username=${result.user.username}`; // ✅ Redirect to home
      }
    } catch (err) {
      alert("Login failed. Please check your credentials.");
      console.error(err);
    }
  });
}


  // ----- Profile Page -----
  // ----- Profile Page -----
const profileSection = document.getElementById("profileInfo");

if (profileSection) {
  try {
    const user = JSON.parse(sessionStorage.getItem("user"));

    if (!user || !user.username) {
      window.location.href = "/login_page";
    } else {
      // Fill in profile fields
      document.getElementById("profileName").textContent = user.username;
      document.getElementById("profileEmail").textContent = user.email;
      document.getElementById("profileStatus").textContent = user.status;
      document.getElementById("profileDOB").textContent = new Date(user.dob).toDateString();
      document.getElementById("profilePhone").textContent = user.phone;
      document.getElementById("profileProfession").textContent = user.profession;

      // Personalized greeting
      const header = document.getElementById("profileNameHeader");
      if (header) {
        header.textContent = user.username;
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

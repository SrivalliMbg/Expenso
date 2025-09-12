// Logout functionality
function handleLogout() {
    // Call logout API
    fetch('/logout', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        console.log('Logout successful:', data);
        // Clear session storage
        sessionStorage.clear();
        // Redirect to login page
        window.location.href = '/login_page';
    })
    .catch(error => {
        console.error('Error during logout:', error);
        // Even if API call fails, clear session and redirect
        sessionStorage.clear();
        window.location.href = '/login_page';
    });
}

function confirmLogout() {
    if (confirm("Are you sure you want to logout?")) {
        handleLogout();
        return false; // Prevent default link behavior
    }
    return false;
}

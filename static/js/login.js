function initLoginWidgets({
    loginForm,
    emailInput,
    passwordInput,
    loginButton,
    togglePasswordButton
}) {
    loginForm.addEventListener('submit', (event) => {
        event.preventDefault();
        handleLogin(emailInput.value, passwordInput.value);
    });
    emailInput.addEventListener('input', validateEmail);
    passwordInput.addEventListener('input', validatePassword);
    togglePasswordButton.addEventListener('click', () => togglePassword(passwordInput, togglePasswordButton));
}

async function handleLogin(email, password) {
    try {
        const response = await fetch('/api/v1/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                user_email: email, 
                user_password: password 
            }),
        });

        const data = await response.json();

        if (response.ok) {
            localStorage.setItem('sessionId', data.session_id);
            window.location.href = `/app/${data.session_id}`;
        } else {
            displayError(data.message || 'Login failed. Please check your credentials.');
        }
    } catch (error) {
        console.error('Login error:', error);
        displayError('An error occurred during login.');
    }
}

function validateEmail() {
    // Implement email validation logic
}

function validatePassword() {
    // Implement password validation logic
}

function displayError(message) {
    alert(message);
}

function togglePassword(passwordInput, toggleButton) {
    const toggleIcon = toggleButton.querySelector('i');
    const toggleText = toggleButton.querySelector('span');

    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleIcon.classList.remove('fa-eye');
        toggleIcon.classList.add('fa-eye-slash');
        toggleText.textContent = 'Hide';
    } else {
        passwordInput.type = 'password';
        toggleIcon.classList.remove('fa-eye-slash');
        toggleIcon.classList.add('fa-eye');
        toggleText.textContent = 'Show';
    }
}

window.initLoginWidgets = initLoginWidgets;

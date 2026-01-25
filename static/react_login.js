/* React-based login/register (no build step)
   Uses the existing backend endpoints:
   - POST /api/auth/login
   - POST /api/auth/register
   - GET  /api/auth/status
*/

(function () {
    const API_BASE = window.location.origin;
    const h = React.createElement;
    const { useEffect, useState } = React;

    function setBodyError(setError, message) {
        setError(message || '');
    }

    function LoginApp() {
        const [tab, setTab] = useState('login');
        const [busy, setBusy] = useState(false);

        const [loginUsername, setLoginUsername] = useState('');
        const [loginPassword, setLoginPassword] = useState('');
        const [loginError, setLoginError] = useState('');

        const [registerUsername, setRegisterUsername] = useState('');
        const [registerPassword, setRegisterPassword] = useState('');
        const [registerError, setRegisterError] = useState('');

        const [infoMessage, setInfoMessage] = useState('');

        async function checkStatus() {
            try {
                const res = await fetch(`${API_BASE}/api/auth/status`, { credentials: 'include' });
                const data = await res.json();
                if (data && data.logged_in) {
                    window.location.href = '/dashboard.html';
                }
            } catch {
                // ignore
            }
        }

        useEffect(() => {
            checkStatus();
        }, []);

        async function handleLoginSubmit(e) {
            e.preventDefault();
            setInfoMessage('');
            setBodyError(setLoginError, '');

            if (!loginUsername || !loginPassword) {
                setBodyError(setLoginError, 'Please enter username and password');
                return;
            }

            try {
                setBusy(true);
                const response = await fetch(`${API_BASE}/api/auth/login`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ username: loginUsername, password: loginPassword })
                });
                const result = await response.json();
                if (result && result.success) {
                    window.location.href = '/dashboard.html';
                } else {
                    setBodyError(setLoginError, result.error || 'Login failed');
                }
            } catch (err) {
                setBodyError(setLoginError, 'Error logging in: ' + (err && err.message ? err.message : String(err)));
            } finally {
                setBusy(false);
            }
        }

        async function handleRegisterSubmit(e) {
            e.preventDefault();
            setInfoMessage('');
            setBodyError(setRegisterError, '');

            if (!registerUsername || !registerPassword) {
                setBodyError(setRegisterError, 'Please enter username and password');
                return;
            }

            try {
                setBusy(true);
                const response = await fetch(`${API_BASE}/api/auth/register`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ username: registerUsername, password: registerPassword })
                });
                const result = await response.json();

                if (result && result.success) {
                    setRegisterUsername('');
                    setRegisterPassword('');
                    setTab('login');
                    setInfoMessage('Registration successful! Please login.');
                } else {
                    setBodyError(setRegisterError, result.error || 'Registration failed');
                }
            } catch (err) {
                setBodyError(setRegisterError, 'Error registering: ' + (err && err.message ? err.message : String(err)));
            } finally {
                setBusy(false);
            }
        }

        function TabButton({ id, children }) {
            return h('button', {
                className: 'tab-btn' + (tab === id ? ' active' : ''),
                onClick: () => {
                    setInfoMessage('');
                    setLoginError('');
                    setRegisterError('');
                    setTab(id);
                },
                type: 'button',
                disabled: busy
            }, children);
        }

        return h('div', { className: 'login-container' },
            h('div', { className: 'login-card' }, [
                h('h1', { key: 'title' }, '📈 Currency Analyzer'),

                infoMessage
                    ? h('div', { key: 'info', style: { marginBottom: 12, color: '#93c5fd', fontSize: 13, textAlign: 'center' } }, infoMessage)
                    : null,

                h('div', { className: 'tabs', key: 'tabs' }, [
                    h(TabButton, { id: 'login', key: 't1' }, 'Login'),
                    h(TabButton, { id: 'register', key: 't2' }, 'Register'),
                ]),

                tab === 'login'
                    ? h('form', { key: 'loginForm', onSubmit: handleLoginSubmit }, [
                        h('div', { className: 'form-group', key: 'lu' }, [
                            h('label', null, 'Username'),
                            h('input', {
                                type: 'text',
                                value: loginUsername,
                                onChange: (e) => setLoginUsername(e.target.value),
                                placeholder: 'Enter username',
                                autoComplete: 'username',
                                disabled: busy
                            })
                        ]),
                        h('div', { className: 'form-group', key: 'lp' }, [
                            h('label', null, 'Password'),
                            h('input', {
                                type: 'password',
                                value: loginPassword,
                                onChange: (e) => setLoginPassword(e.target.value),
                                placeholder: 'Enter password',
                                autoComplete: 'current-password',
                                disabled: busy
                            })
                        ]),
                        h('button', { className: 'btn-primary', type: 'submit', disabled: busy, key: 'btn' }, busy ? 'Please wait…' : 'Login'),
                        h('div', { className: 'error-msg', key: 'err' }, loginError)
                    ])
                    : h('form', { key: 'registerForm', onSubmit: handleRegisterSubmit }, [
                        h('div', { className: 'form-group', key: 'ru' }, [
                            h('label', null, 'Username'),
                            h('input', {
                                type: 'text',
                                value: registerUsername,
                                onChange: (e) => setRegisterUsername(e.target.value),
                                placeholder: 'Choose username (min 3 chars)',
                                autoComplete: 'username',
                                disabled: busy
                            })
                        ]),
                        h('div', { className: 'form-group', key: 'rp' }, [
                            h('label', null, 'Password'),
                            h('input', {
                                type: 'password',
                                value: registerPassword,
                                onChange: (e) => setRegisterPassword(e.target.value),
                                placeholder: 'Choose password (min 6 chars)',
                                autoComplete: 'new-password',
                                disabled: busy
                            })
                        ]),
                        h('button', { className: 'btn-primary', type: 'submit', disabled: busy, key: 'btn' }, busy ? 'Please wait…' : 'Register'),
                        h('div', { className: 'error-msg', key: 'err' }, registerError)
                    ])
            ].filter(Boolean))
        );
    }

    function mount() {
        const mountEl = document.getElementById('reactLoginRoot');
        if (!mountEl) return;
        const root = ReactDOM.createRoot(mountEl);
        root.render(h(LoginApp));
    }

    document.addEventListener('DOMContentLoaded', mount);
})();

"""
Simple Role-Based Access Control (RBAC) for the Recruitment Platform.

Provides:
- Password hashing and verification
- User authentication
- Streamlit session-based login gate
- Role requirement checks

Roles: admin, recruiter, viewer
"""

import hashlib
import secrets
from config.logging_config import logger


def _hash_password(password: str) -> str:
    """Hashes a password with SHA-256 and a salt prefix for basic security."""
    salted = f"kshamata_salt_{password}"
    return hashlib.sha256(salted.encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """Verifies a plaintext password against its stored hash."""
    return _hash_password(password) == password_hash


def authenticate(username: str, password: str) -> dict:
    """
    Authenticates a user against the database.
    
    Returns:
        dict: {"authenticated": bool, "user": dict or None, "error": str or None}
    """
    try:
        from database.connection import SessionLocal
        from database.models import User

        db = SessionLocal()
        try:
            user = db.query(User).filter(
                User.username == username,
                User.is_active == True
            ).first()

            if not user:
                return {"authenticated": False, "user": None, "error": "Invalid username or password"}

            if not verify_password(password, user.password_hash):
                return {"authenticated": False, "user": None, "error": "Invalid username or password"}

            logger.info(f"User '{username}' authenticated successfully (role: {user.role})")
            return {
                "authenticated": True,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "display_name": user.display_name or user.username,
                    "role": user.role
                },
                "error": None
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        return {"authenticated": False, "user": None, "error": f"System error: {str(e)}"}


def create_user(username: str, password: str, role: str = "viewer",
                display_name: str = None) -> dict:
    """Creates a new user account with hashed password."""
    try:
        from database.connection import SessionLocal
        from database.models import User

        db = SessionLocal()
        try:
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                return {"success": False, "error": f"Username '{username}' already exists"}

            user = User(
                username=username,
                password_hash=_hash_password(password),
                display_name=display_name or username.title(),
                role=role,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Created user '{username}' with role '{role}'")
            return {"success": True, "user_id": user.id}
        finally:
            db.close()
    except Exception as e:
        logger.error(f"User creation failed: {str(e)}")
        return {"success": False, "error": str(e)}


def seed_default_users():
    """Seeds default users if they don't exist. Called during app initialization."""
    defaults = [
        {"username": "admin", "password": "admin123", "role": "admin", "display_name": "Platform Admin"},
        {"username": "recruiter", "password": "recruit123", "role": "recruiter", "display_name": "Recruitment Manager"},
        {"username": "viewer", "password": "view123", "role": "viewer", "display_name": "Read-Only Viewer"},
    ]
    for user_data in defaults:
        result = create_user(**user_data)
        if result.get("success"):
            logger.info(f"Seeded default user: {user_data['username']} ({user_data['role']})")


def require_login(st_module):
    """
    Streamlit login gate. Call at the top of any page to enforce authentication.
    
    Args:
        st_module: The streamlit module (pass `st`)
    
    Returns:
        dict: The authenticated user data, or halts the page if not logged in.
    """
    if "authenticated_user" in st_module.session_state and st_module.session_state["authenticated_user"]:
        return st_module.session_state["authenticated_user"]

    # Show login form
    st_module.markdown(
        '<div style="text-align:center; padding-top: 2rem;">'
        '<h1 style="background: linear-gradient(135deg, #ffd700, #ff8c00); '
        '-webkit-background-clip: text; -webkit-text-fill-color: transparent; '
        'font-size: 2.5rem;">🏭 Kshamata</h1>'
        '<p style="color: #8f9bb3; font-size: 1.1rem;">Industrial Workforce Recruitment Platform</p>'
        '</div>',
        unsafe_allow_html=True
    )

    col1, col2, col3 = st_module.columns([1, 2, 1])
    with col2:
        with st_module.form("login_form"):
            st_module.markdown("#### 🔐 Login")
            username = st_module.text_input("Username", placeholder="e.g. admin")
            password = st_module.text_input("Password", type="password")
            submitted = st_module.form_submit_button("Sign In", use_container_width=True)

            if submitted:
                if not username or not password:
                    st_module.error("Please enter both username and password.")
                else:
                    result = authenticate(username, password)
                    if result["authenticated"]:
                        st_module.session_state["authenticated_user"] = result["user"]
                        st_module.rerun()
                    else:
                        st_module.error(result["error"])

        st_module.markdown(
            '<p style="color: #555; font-size: 0.85rem; text-align: center; margin-top: 1rem;">'
            'Default accounts: admin/admin123, recruiter/recruit123, viewer/view123'
            '</p>',
            unsafe_allow_html=True
        )

    st_module.stop()


def require_role(st_module, required_role: str):
    """
    Checks if the currently logged-in user has the required role.
    Admin always passes. Recruiter can access recruiter + viewer pages.
    
    Args:
        st_module: The streamlit module
        required_role: 'admin', 'recruiter', or 'viewer'
    """
    user = require_login(st_module)
    role_hierarchy = {"admin": 3, "recruiter": 2, "viewer": 1}
    user_level = role_hierarchy.get(user.get("role", "viewer"), 0)
    required_level = role_hierarchy.get(required_role, 0)

    if user_level < required_level:
        st_module.error(
            f"⛔ Access Denied. This page requires '{required_role}' role. "
            f"Your role: '{user.get('role', 'unknown')}'"
        )
        st_module.stop()

    return user

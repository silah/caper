from flask_login import UserMixin

class User(UserMixin):
    """User model for Flask-Login"""
    
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email
    
    @staticmethod
    def from_dict(user_dict):
        """Create User instance from database dict"""
        if not user_dict:
            return None
        return User(
            id=user_dict['id'],
            username=user_dict['username'],
            email=user_dict['email']
        )

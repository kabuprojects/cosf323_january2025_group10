import re

def validate_email(email):
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_password(password):
    """Ensure password is at least 8 characters with one letter and one number."""
    return len(password) >= 8 and any(c.isalpha() for c in password) and any(c.isdigit() for c in password)

def validate_role(role):
    """Ensure role is non-empty and less than 50 characters."""
    return role.strip() != "" and len(role) <= 50

def validate_task_data(description, frequency, due_date, assigned_role, compliance_ref):
    """Validate task input data."""
    return (description.strip() != "" and len(description) <= 200 and
            frequency in ["monthly", "yearly"] and
            due_date is not None and
            assigned_role.strip() != "" and len(assigned_role) <= 50 and
            compliance_ref.strip() != "" and len(compliance_ref) <= 100)
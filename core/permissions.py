# =====================================
# Role Based Permissions
# =====================================

from core.helpers import load_data, save_data, TITLE_FILE

def get_executive_titles():
    return load_data(TITLE_FILE)

def add_executive_title(title):
    titles = load_data(TITLE_FILE)
    if title not in titles:
        titles.append(title)
        save_data(TITLE_FILE, titles)
        return True
    return False

# Which roles each role is allowed to add
ADDABLE_ROLES = {
    "Watcher": ["Admin", "Executive", "General"],
    "Admin": ["Executive", "General"],
    "Executive": ["General"],
    "General": []
}

# Which roles each role is allowed to change a member's role INTO
ASSIGNABLE_ROLES = {
    "Watcher": ["Admin", "Executive", "General"],
    "Admin": ["Executive", "General"],
}

PERMISSIONS = {

    "Admin": [
        "add_donation",
        "add_donor",
        "view_donors",
        "manage_members",
        "manage_notices",
        "view_notices",
        "create_request",
        "complete_request",
        "manage_access",
        "view_statistics",
        "view_requests",
        "view_members",
        "edit_data",
        "delete_data",
        "change_role",
        "reset_credentials",
        "contact_donor",
        "view_contacts",
        "edit_donor",
        "delete_donor"
    
    ],

    "Executive": [
        "add_donation",
        "add_donor",
        "view_donors",
        "manage_members",
        "manage_notices",
        "view_notices",
        "create_request",
        "complete_request",
        "manage_access",
        "view_statistics",
        "view_requests",
        "view_members",
        "contact_donor",
        "view_contacts",
        "edit_donor",
        "delete_donor"
    
    ],

    "General": [
        "add_donation",
        "view_donors",
        "view_notices",
        "view_members",
        "view_requests",
        "create_request",
        "complete_request",
        "view_statistics",
        "contact_donor",
        "view_contacts"
    ]
}

# Permissions that an Executive/Admin can temporarily grant to a General member
GRANTABLE_PERMISSIONS = [
    "add_donor",
    "manage_members",
    "manage_notices",
    "edit_donor",
    "delete_donor",
]


def has_permission(member, action):

    if member is None:
        return False

    # Watcher always has full access, no exceptions
    if member.get("type") == "Watcher":
        return True

    member_type = member.get("type")

    if action in PERMISSIONS.get(member_type, []):
        return True

    if member_type == "General":
        return action in member.get("temp_permissions", [])

    return False


def can_add_role(current_role, target_role):
    return target_role in ADDABLE_ROLES.get(current_role, [])


def can_assign_role(current_role, target_role):
    if current_role == "Watcher":
        return True
    return target_role in ASSIGNABLE_ROLES.get(current_role, [])
from core.helpers import *
from core.permissions import *

def add_member(members):

    print("\n========== ADD MEMBER ==========")

    # -----------------------------
    # Name
    # -----------------------------

    name = input(
        "Member Name: "
    ).strip()

    if not name:

        print("Name cannot be empty.")
        return

    # -----------------------------
    # Phone
    # -----------------------------

    phone = input(
        "Phone: "
    ).strip()

    if not phone:

        print("Phone cannot be empty.")
        return

    clean_phone = (
        phone
        .replace(" ", "")
        .replace("-", "")
        .replace("+", "")
    )

    if not clean_phone.isdigit():

        print("Invalid phone number.")
        return

    # Duplicate phone

    for member in members:

        existing = (
            member["phone"]
            .replace(" ", "")
            .replace("-", "")
            .replace("+", "")
        )

        if existing == clean_phone:

            print(
                "Phone number already exists."
            )

            return

    # -----------------------------
    # Username
    # -----------------------------

    username = input(
        "Username: "
    ).strip()

    if not username:

        print("Username cannot be empty.")
        return

    # -----------------------------
    # Password
    # -----------------------------

    password = input(
        "Password: "
    ).strip()

    if len(password) < 4:

        print(
            "Password must contain at least 4 characters."
        )

        return

    # -----------------------------
    # Member Type
    # -----------------------------

    print("\nMember Type:")
    print("1. General")
    print("2. Executive")

    choice = input(
        "Enter choice: "
    )

    if choice == "1":

        member_type = "General"

    elif choice == "2":

        member_type = "Executive"

    else:

        print("Invalid member type.")
        return

    # -----------------------------
    # Duplicate Username
    # -----------------------------

    for member in members:

        if (
            member["username"].lower()
            == username.lower()
        ):

            print(
                "Username already exists."
            )

            return

    # -----------------------------
    # Unique Member ID
    # -----------------------------

    if members:

        member_id = max(
            member["id"]
            for member in members
        ) + 1

    else:

        member_id = 1

    # -----------------------------
    # Create Member
    # -----------------------------

    member = {

        "id": member_id,

        "name": name,

        "phone": phone,

        "username": username,

        "password": password,

        "type": member_type,

        "active": True,

        "requests_managed": 0,

        "donors_contacted": 0,

        "successful_cases": 0,

        "blood_managed": 0
    }

    members.append(member)

    save_data(
        MEMBER_FILE,
        members
    )

    print("\n================================")

    print("Member added successfully!")

    print("================================")

    print("Member ID:", member_id)

    print("Username:", username)

    print("Member Type:", member_type)

    print("Status: Active")
# =====================================
# Member List
# =====================================

def show_members(members):

    print("\n========== MEMBERS ==========")

    if not members:

        print("No members found.")
        return

    for member in members:

        status = (
            "Active"
            if member["active"]
            else "Inactive"
        )

        print(
            f'{member["id"]}. '
            f'{member["name"]} | '
            f'{member["type"]} | '
            f'{member["phone"]} | '
            f'{status}'
        )

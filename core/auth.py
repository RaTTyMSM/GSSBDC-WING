from core.helpers import *
from core.permissions import *
from modules.member import *
# =====================================
# Member Login
# =====================================

def member_login(members):

    print("\n========================================")
    print("          GSSBDC LOGIN")
    print("========================================")

    username = input(
        "Username: "
    )

    password = input(
        "Password: "
    )

    for member in members:

        if (
            member.get("username")
            == username
            and
            member.get("password")
            == password
        ):

            if not member.get("active", True):

                print("\nYour account is currently inactive.")
                print("Please contact an Executive.")

                return None
            print(
                "\nLogin successful!"
            )

            print(
                "Welcome,",
                member["name"]
            )

            print(
                "Role:",
                member["type"]
            )

            return member

    print(
        "\nInvalid username or password."
    )

    return None

# =====================================
# Member Management
# =====================================

def member_management(members):

    while True:

        print("\n================================")
        print("       MEMBER MANAGEMENT")
        print("================================")

        print("1. Show Members")
        print("2. Activate Member")
        print("3. Deactivate Member")
        print("4. Back")

        choice = input("\nEnter choice: ")

        # --------------------------------
        # Show Members
        # --------------------------------

        if choice == "1":

            show_members(members)

        # --------------------------------
        # Activate Member
        # --------------------------------

        elif choice == "2":

            show_members(members)

            try:

                member_id = int(
                    input("\nEnter Member ID: ")
                )

            except ValueError:

                print("Invalid Member ID.")
                continue

            found = False

            for member in members:

                if member.get("id") == member_id:

                    if member.get("active", True):

                        print(
                            "\nMember is already active."
                        )

                    else:

                        member["active"] = True

                        save_data(
                            MEMBER_FILE,
                            members
                        )

                        print(
                            "\nMember activated successfully!"
                        )

                    found = True
                    break

            if not found:

                print(
                    "\nMember not found."
                )

        # --------------------------------
        # Deactivate Member
        # --------------------------------

        elif choice == "3":

            show_members(members)

            try:

                member_id = int(
                    input("\nEnter Member ID: ")
                )

            except ValueError:

                print("Invalid Member ID.")
                continue

            found = False

            for member in members:

                if member.get("id") == member_id:

                    if not member.get("active", True):

                        print(
                            "\nMember is already inactive."
                        )

                    else:

                        print(
                            "\nMember:",
                            member["name"]
                        )

                        confirm = input(
                            "Deactivate this member? (Yes/No): "
                        ).strip().upper()

                        if confirm == "YES":

                            member["active"] = False

                            save_data(
                                MEMBER_FILE,
                                members
                            )

                            print(
                                "\nMember deactivated successfully!"
                            )

                        else:

                            print(
                                "\nOperation cancelled."
                            )

                    found = True
                    break

            if not found:

                print(
                    "\nMember not found."
                )

        # --------------------------------
        # Back
        # --------------------------------

        elif choice == "4":

            break

        else:

            print(
                "\nInvalid choice!"
            )


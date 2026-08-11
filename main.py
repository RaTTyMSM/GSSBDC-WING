from core.helpers import *
from core.auth import *

from modules.donor import *
from modules.donation import *
from modules.request import *
from modules.member import *
from modules.notice import *
from modules.statistics import *

# =====================================
# MAIN PROGRAM
# =====================================

donors = load_data(DONOR_FILE)
donations = load_data(DONATION_FILE)
requests = load_data(REQUEST_FILE)
members = load_data(MEMBER_FILE)
contacts = load_data(CONTACT_FILE)
notices = load_data(NOTICE_FILE)


# =====================================
# UPDATE OLD DATA
# =====================================

update_old_requests(
    requests,
    members
)

update_missing_locations(
    donors
)


# =====================================
# MEMBER LOGIN
# =====================================

current_member = member_login(
    members
)

if current_member is None:

    print("\nAccess denied.")
    exit()


# =====================================
# MEMBER MENU
# =====================================

def member_menu(
    current_member,
    donors,
    donations,
    requests,
    members,
    contacts,
    notices
):  # sourcery skip: extract-duplicate-method

    if current_member is None:
        print("Access denied.")
        return

    if not current_member.get("active", True):
        print("\nYour account is inactive.")
        return

    role = current_member.get("type")

    if role not in ["General", "Executive"]:
        print("\nInvalid member role.")
        return

    while True:

        print("\n")
        print("========================================")
        print("          GSSBDC v0.2")
        print("========================================")

        print(
            "Logged in:",
            current_member["name"]
        )

        print(
            "Role:",
            current_member["type"]
        )

        print("----------------------------------------")


        # =================================
        # GENERAL MEMBER MENU
        # =================================

        if current_member["type"] == "General":

            print("1. Show Donors")
            print("2. Search Blood Group")
            print("3. Find Matching Donors")
            print("4. Monthly Statistics")
            print("5. Donation Management")
            print("6. Blood Requests")
            print("7. Create Blood Request")
            print("8. Complete Blood Request")
            print("9. Record Donor Contact")
            print("10. Notices")
            print("0. Logout")

        # =================================
        # EXECUTIVE MEMBER MENU
        # =================================

        elif current_member["type"] == "Executive":

            print("1. Add Donor")
            print("2. Show Donors")
            print("3. Search Blood Group")
            print("4. Find Matching Donors")
            print("5. Donation Management")
            print("6. Donor Statistics")
            print("7. Member Statistics")
            print("8. Monthly Statistics")
            print("9. Blood Requests")
            print("10. Create Blood Request")
            print("11. Complete Blood Request")
            print("12. Add Member")
            print("13. Member Management")
            print("14. Record Donor Contact")
            print("15. Notices")
            print("16. Manage Notices")
            print("0. Logout")



        else:

            print("\nInvalid member role.")
            break


        # =================================
        # GET CHOICE
        # =================================

        choice = input("\nEnter choice: ")


        # =================================
        # GENERAL MEMBER
        # =================================

        if current_member["type"] == "General":


            if choice == "1":

                show_all_donors(
                    donors,
                    donations
                )


            elif choice == "2":

                search_by_blood_group(
                    donors
                )


            elif choice == "3":

                find_matching_donors(
                    donors,
                    donations,
                    requests
                )


            elif choice == "4":

                monthly_statistics(
                    donations,
                    requests,
                    members,
                    contacts
                )
            elif choice == "5":
                donation_menu(donors, donations, current_member)

            elif choice == "6":

                show_blood_requests(
                    requests
                )


            elif choice == "7":

                create_blood_request(
        requests,
        current_member
    )

            elif choice == "8":

                complete_blood_request(
        requests,
        donors,
        members,
        donations,
        current_member
    )
            elif choice == "9":

                record_donor_contact(
        contacts,
        donors,
        members,
        current_member
    )

            elif choice == "10":

                show_notices(notices)

            elif choice == "0":

                print(
        "\nLogged out successfully."
    )

                break


            else:

                print(
                    "\nInvalid choice!"
                )


        # =================================
        # EXECUTIVE MEMBER
        # =================================

        elif current_member["type"] == "Executive":


            if choice == "1":

                add_donor(
                    donors
                )


            elif choice == "2":

                show_all_donors(donors, donations)

            elif choice == "3":

                search_by_blood_group(
                    donors
                )


            elif choice == "4":

                find_matching_donors(
                    donors,
                    donations,
                    requests
                )


            elif choice == "5":
                donation_menu(donors, donations, current_member)


            elif choice == "6":

                donor_statistics(
                    donors,
                    donations
                )


            elif choice == "7":

                member_statistics(
                    members,
                    contacts,
                    donations,
                    requests
                )


            elif choice == "8":

                monthly_statistics(
                    donations,
                    requests,
                    members,
                    contacts
                )


            elif choice == "9":

                show_blood_requests(
                    requests
                )


            elif choice == "10":

                create_blood_request(
        requests,
        current_member
    )


            elif choice == "11":

                complete_blood_request(
        requests,
        donors,
        members,
        donations,
        current_member
    )


            elif choice == "12":

                add_member(
                    members
                )


            elif choice == "13":

                member_management(
                    members
                )


            elif choice == "14":

                record_donor_contact(
        contacts,
        donors,
        members,
        current_member
    )

            elif choice == "15":

                show_notices(notices)

            elif choice == "16":

                manage_notices(
        notices,
        current_member
    )

            elif choice == "0":

                print(
                    "\nLogged out successfully."
                )

                break

            else:

                print(
                    "\nInvalid choice!"
                )


# START GSSBDC

member_menu(
    current_member,
    donors,
    donations,
    requests,
    members,
    contacts,
    notices
)
from datetime import date
from datetime import datetime
from datetime import timedelta

from core.helpers import *
from core.permissions import *

def pause():
    input("\nPress Enter to continue...")

# =====================================
# Automatic Donation Record
# =====================================

def create_automatic_donation(
    donor,
    donations,
    donation_date,
    bags,
    source="club",
    request_id=None,
    managed_by=None,
    managed_by_name=None
):
    """
    source: "club"  -> counts toward club statistics (blood managed
                        by our members, whether standalone or via a
                        request).
            "external" -> donor donated somewhere else / a request
                        bag was arranged by the patient's family or
                        someone outside the club. Still recorded so
                        eligibility / next-eligible-date stays
                        accurate, but excluded from club statistics.
    """

    donation = {
        "id": max((d.get("id", 0) for d in donations), default=0) + 1,
        "donor_id": donor["id"],
        "donor_name": donor["name"],
        "blood_group": donor["blood_group"],
        "date": donation_date,
        "bags": bags,
        "source": source,
        "request_id": request_id,
        "managed_by": managed_by,
        "managed_by_name": managed_by_name
    }

    donations.append(donation)

    save_data(
        DONATION_FILE,
        donations
    )

    return donation

# =====================================
# Donor Contact Tracking
# =====================================

def record_donor_contact(
    contacts,
    donors,
    members,
    current_member
):

    print("\n========== RECORD DONOR CONTACT ==========")

    # -----------------------------
    # Current Member
    # -----------------------------

    member_id = current_member["id"]

    member = None

    for m in members:

        if m["id"] == member_id:

            member = m
            break

    if member is None:

        print("Current member not found.")
        return

    # --------------------------------
    # Select Active Donor
    # --------------------------------

    active_donors = []

    for donor in donors:

        if donor.get("active", True):

            active_donors.append(donor)

    if not active_donors:

        print("No active donors found.")
        return

    print("\nAvailable Donors:")

    for donor in active_donors:

        print(
            f'{donor["id"]}. '
            f'{donor["name"]} | '
            f'{donor["blood_group"]} | '
            f'{donor["area"]}'
        )

    try:

        donor_id = int(
            input("\nEnter Donor ID: ")
        )

    except ValueError:

        print("Invalid Donor ID.")
        return

    donor = None

    for d in active_donors:

        if d.get("id") == donor_id:

            donor = d
            break

    if donor is None:

        print("Active donor not found.")
        return

    # --------------------------------
    # Contact Status
    # --------------------------------

    print("\nContact Status:")

    print("1. Contacted")
    print("2. Agreed")
    print("3. Donated")
    print("4. Failed")

    status_choice = input(
        "\nEnter status: "
    ).strip()

    status_map = {
        "1": "Contacted",
        "2": "Agreed",
        "3": "Donated",
        "4": "Failed"
    }

    if status_choice not in status_map:

        print("Invalid status.")
        return

    status = status_map[status_choice]

    # --------------------------------
    # Create Contact Record
    # --------------------------------

    contact = {

        "id": len(contacts) + 1,

        "member_id": member["id"],

        "member_name": member["name"],

        "donor_id": donor["id"],

        "donor_name": donor["name"],

        "blood_group": donor["blood_group"],

        "date": date.today().isoformat(),

        "status": status
    }

    contacts.append(contact)

    # --------------------------------
    # Update Member Contact Count
    # --------------------------------

    member["donors_contacted"] = (
        member.get("donors_contacted", 0) + 1
    )

    # --------------------------------
    # Save Data
    # --------------------------------

    save_data(
        CONTACT_FILE,
        contacts
    )

    save_data(
        MEMBER_FILE,
        members
    )

    # --------------------------------
    # Result
    # --------------------------------

    print("\n========================================")
    print("       CONTACT RECORDED")
    print("========================================")

    print(
        "Member:",
        member["name"]
    )

    print(
        "Donor:",
        donor["name"]
    )

    print(
        "Blood Group:",
        donor["blood_group"]
    )

    print(
        "Status:",
        status
    )

    print(
        "Date:",
        contact["date"]
    )

# =====================================
# Donation Functions
# =====================================

def add_donation(donors, donations, current_member):

    print("\n========== ADD DONATION ==========")

    if not has_permission(current_member, "add_donation"):
        print("Permission denied.")
        pause()
        return

    donor_id = int(input("Enter donor ID: "))

    donor = None

    for d in donors:
        if d["id"] == donor_id:
            donor = d
            break

    if donor is None:
        print("Donor not found.")
        return

    date_input = input("Donation date (YYYY-MM-DD): ").strip()

    try:
        datetime.strptime(date_input, "%Y-%m-%d")
    except ValueError:
        print("\nInvalid date format. Please use YYYY-MM-DD (e.g. 2026-08-06).")
        return

    try:
        bags = int(input("Number of bags: "))
    except ValueError:
        print("\nInvalid number of bags.")
        return

    if bags <= 0:
        print("\nNumber of bags must be greater than 0.")
        return

    donation = {
        "id": len(donations) + 1,
        "donor_id": donor_id,
        "donor_name": donor["name"],
        "blood_group": donor["blood_group"],
        "date": date_input,
        "bags": bags
    }

    donations.append(donation)

    save_data(DONATION_FILE, donations)

    print("\nDonation recorded successfully!")

    print("\nDonation recorded successfully!")
    pause()

# =====================================
# Donation History
# =====================================

def donation_history(donors, donations):

    print("\n========== DONATION HISTORY ==========")

    donor_id = int(input("Enter donor ID: "))

    found = False

    for donation in donations:

        if donation["donor_id"] == donor_id:

            print(
                f'Date: {donation["date"]} | '
                f'Bags: {donation["bags"]} | '
                f'Blood: {donation["blood_group"]}'
            )

            found = True

    if not found:
        print("No donation history found.")
    if not found:
        print("No donation history found.")

    pause()
# =====================================
# Donor Eligibility
# =====================================

DONATION_WAITING_DAYS = 90


def get_eligibility(donor_id, donations):

    # ---------------------------------
    # Find Last Donation
    # ---------------------------------

    last_donation = get_last_donation(
        donor_id,
        donations
    )

    # ---------------------------------
    # Never Donated
    # ---------------------------------

    if last_donation is None:

        return {
            "eligible": True,
            "last_date": None,
            "next_date": None,
            "days_remaining": 0
        }

    # ---------------------------------
    # Last Donation Date
    # ---------------------------------

    last_date = datetime.strptime(
        last_donation["date"],
        "%Y-%m-%d"
    ).date()

    # ---------------------------------
    # Next Eligible Date
    # ---------------------------------

    next_date = last_date + timedelta(
        days=DONATION_WAITING_DAYS
    )

    # ---------------------------------
    # Today
    # ---------------------------------

    today = date.today()

    # ---------------------------------
    # Days Remaining
    # ---------------------------------

    days_remaining = (
        next_date - today
    ).days

    # ---------------------------------
    # Eligibility
    # ---------------------------------

    eligible = today >= next_date

    # If eligible, remaining days = 0

    if days_remaining < 0:

        days_remaining = 0

    # ---------------------------------
    # Return Result
    # ---------------------------------

    return {
        "eligible": eligible,
        "last_date": last_date,
        "next_date": next_date,
        "days_remaining": days_remaining
    }

def get_last_donation(donor_id, donations):

    donor_donations = []

    for donation in donations:

        if donation["donor_id"] == donor_id:
            donor_donations.append(donation)

    if not donor_donations:
        return None

    donor_donations.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    return donor_donations[0]



def donation_menu(donors, donations, current_member):
    while True:
        clear_screen()
        print("=" * 50)
        print("         DONATION MANAGEMENT")
        print("=" * 50)

        print("1. Add Donation")
        print("2. Donation History")
        print("0. Back")

        choice = input("\nEnter your choice: ")

        if choice == "1":
            add_donation(donors, donations, current_member)

        elif choice == "2":
            donation_history(donors, donations)

        elif choice == "0":
            break

        else:
            print("\nInvalid choice!")
            pause()
            
def find_donation_by_id(donations, donation_id):
    for donation in donations:
        if donation["id"] == donation_id:
            return donation
    return None
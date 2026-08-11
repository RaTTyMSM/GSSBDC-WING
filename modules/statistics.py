from datetime import datetime
from collections import Counter
from modules.donation import get_eligibility
from core.helpers import *

# =====================================
# Donor Statistics
# =====================================

def donor_statistics(donors, donations):

    print("\n========== DONOR STATISTICS ==========")

    try:
        donor_id = int(input("Enter donor ID: "))

    except ValueError:
        print("Invalid donor ID.")
        return

    donor = None

    for d in donors:

        if d["id"] == donor_id:
            donor = d
            break

    if donor is None:

        print("Donor not found.")
        return

    total_donations = 0
    total_bags = 0

    for donation in donations:

        if donation["donor_id"] == donor_id:

            total_donations += 1
            total_bags += donation["bags"]

    eligibility = get_eligibility(
        donor_id,
        donations
    )

    print("\nName:", donor["name"])
    print("Blood Group:", donor["blood_group"])
    print("Phone:", donor["phone"])
    print("Area:", donor["area"])

    print("\nTotal Donations:", total_donations)
    print("Total Blood:", total_bags, "Bags")

    if eligibility["last_date"] is None:

        print("Last Donation: Never")
        print("Eligibility: AVAILABLE")

    else:

        print(
            "Last Donation:",
            eligibility["last_date"]
        )

        print(
            "Next Eligible Date:",
            eligibility["next_date"]
        )

        if eligibility["eligible"]:

            print("Eligibility: AVAILABLE")

        else:

            print("Eligibility: NOT AVAILABLE")

# =====================================
# Monthly Statistics
# =====================================

def monthly_statistics(
    donations,
    requests,
    members,
    contacts
):

    print("\n========== MONTHLY STATISTICS ==========")

    month = input(
        "Enter month (YYYY-MM): "
    ).strip()

    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        print("\nInvalid month format. Please use YYYY-MM (e.g. 2026-08).")
        return

    # =================================
    # Donation Statistics
    # =================================

    total_bags = 0
    total_donations = 0

    for donation in donations:

        donation_date = donation.get("date", "")

        if donation_date[:7] == month:

            total_donations += 1

            total_bags += donation.get(
                "bags",
                0
            )

    # =================================
    # Request Statistics
    # =================================

    successful_requests = 0

    request_bags = 0

    for request in requests:

        if request.get("status") != "Fulfilled":
            continue

        completed_date = request.get(
            "completed_date"
        )

        # Old requests may not have completed_date
        if not completed_date:
            continue

        if completed_date[:7] == month:

            successful_requests += 1

            request_bags += request.get(
                "collected_bags",
                0
            )

    # =================================
    # Contact Statistics
    # =================================

    total_contacts = 0
    total_agreed = 0
    total_failed = 0
    total_donated_contacts = 0

    for contact in contacts:

        contact_date = contact.get(
            "date",
            ""
        )

        if contact_date[:7] != month:
            continue

        total_contacts += 1

        status = contact.get(
            "status"
        )

        if status == "Agreed":

            total_agreed += 1

        elif status == "Failed":

            total_failed += 1

        elif status == "Donated":

            total_donated_contacts += 1

    # =================================
    # Main Monthly Result
    # =================================

    print("\n========================================")
    print("       MONTHLY BLOOD STATISTICS")
    print("========================================")

    print(
        "Month:",
        month
    )

    print(
        "Total Donations:",
        total_donations
    )

    print(
        "Total Blood Collected:",
        total_bags,
        "Bags"
    )

    print(
        "Successful Requests:",
        successful_requests
    )

    print(
        "Blood Managed Through Requests:",
        request_bags,
        "Bags"
    )

    print(
        "Donors Contacted:",
        total_contacts
    )

    print(
        "Donors Agreed:",
        total_agreed
    )

    print(
        "Donors Donated:",
        total_donated_contacts
    )

    print(
        "Failed Contacts:",
        total_failed
    )

    # =================================
    # Member Performance
    # =================================

    print(
        "\n========== MEMBER PERFORMANCE =========="
    )

    if not members:

        print("No members found.")
        return

    for member in members:

        member_id = member["id"]

        member_contacts = 0
        member_agreed = 0
        member_donated = 0
        member_failed = 0

        member_requests = 0
        member_blood = 0

        # ---------------------------------
        # Contact Statistics
        # ---------------------------------

        for contact in contacts:

            if (
                contact.get("member_id")
                == member_id
                and contact.get("date", "")[:7]
                == month
            ):

                member_contacts += 1

                status = contact.get(
                    "status"
                )

                if status == "Agreed":

                    member_agreed += 1

                elif status == "Donated":

                    member_donated += 1

                elif status == "Failed":

                    member_failed += 1

        # ---------------------------------
        # Request / Blood Statistics
        # ---------------------------------

        for request in requests:

            if (
                request.get("managed_by")
                != member_id
            ):

                continue

            if (
                request.get("status")
                != "Fulfilled"
            ):

                continue

            completed_date = request.get(
                "completed_date"
            )

            if not completed_date:
                continue

            # Only count requests completed
            # during selected month

            if completed_date[:7] != month:
                continue

            member_requests += 1

            member_blood += request.get(
                "collected_bags",
                0
            )

        # ---------------------------------
        # Display Member
        # ---------------------------------

        print(
            f'\n{member["id"]}. '
            f'{member["name"]} | '
            f'{member["type"]}'
        )

        print(
            "   Donors Contacted:",
            member_contacts
        )

        print(
            "   Agreed:",
            member_agreed
        )

        print(
            "   Donated:",
            member_donated
        )

        print(
            "   Failed:",
            member_failed
        )

        print(
            "   Successful Requests:",
            member_requests
        )

        print(
            "   Blood Managed:",
            member_blood,
            "Bags"
        )

    # =================================
    # Overall Club Total
    # =================================

    overall_bags = 0

    for donation in donations:

        overall_bags += donation.get(
            "bags",
            0
        )

    print("\n========================================")
    print("          OVERALL CLUB TOTAL")
    print("========================================")

    print(
        "Overall Blood Collected:",
        overall_bags,
        "Bags"
    )
# =====================================
# Member Statistics
# =====================================

def member_statistics(
    members,
    contacts,
    donations,
    requests
):

    print("\n========== MEMBER STATISTICS ==========")

    if not members:

        print("No members found.")
        return

    print("\nAvailable Members:")

    for member in members:

        print(
            f'{member["id"]}. '
            f'{member["name"]} | '
            f'{member["type"]}'
        )

    try:

        member_id = int(
            input("\nEnter Member ID: ")
        )

    except ValueError:

        print("Invalid Member ID.")
        return

    member = None

    for m in members:

        if m["id"] == member_id:

            member = m
            break

    if member is None:

        print("Member not found.")
        return

    # =================================
    # Contact Statistics
    # =================================

    total_contacted = 0
    total_agreed = 0
    total_donated = 0
    total_failed = 0

    for contact in contacts:

        if contact["member_id"] == member_id:

            total_contacted += 1

            if contact["status"] == "Agreed":
                total_agreed += 1

            elif contact["status"] == "Donated":
                total_donated += 1

            elif contact["status"] == "Failed":
                total_failed += 1

    # =================================
    # Blood Managed
    # =================================

    blood_managed = 0
    successful_requests = 0

    for request in requests:

        if (
            request.get("managed_by")
            == member_id
            and request.get("status")
            == "Fulfilled"
        ):

            successful_requests += 1

            blood_managed += request.get(
                "collected_bags",
                0
            )

    # =================================
    # Display
    # =================================

    print("\n========================================")
    print("          MEMBER STATISTICS")
    print("========================================")

    print("Name:", member["name"])
    print("Phone:", member["phone"])
    print("Type:", member["type"])

    status = (
        "Active"
        if member.get("active", True)
        else "Inactive"
    )

    print("Status:", status)

    print("\n---------- DONOR CONTACT ----------")

    print(
        "Donors Contacted:",
        total_contacted
    )

    print(
        "Donors Agreed:",
        total_agreed
    )

    print(
        "Donors Donated:",
        total_donated
    )

    print(
        "Failed Contacts:",
        total_failed
    )

    print("\n---------- BLOOD MANAGEMENT ----------")

    print(
        "Successful Requests:",
        successful_requests
    )

    print(
        "Blood Managed:",
        blood_managed,
        "Bags"
    )
# =====================================
# Overall Statistics
# =====================================

def overall_statistics(donors, donations):

    total_bags = 0

    for donation in donations:

        total_bags += donation["bags"]

    print("\n========== CLUB STATISTICS ==========")

    print("Total Donors:", len(donors))

    print("Total Donations:", len(donations))

    print("Total Blood Collected:", total_bags, "Bags")
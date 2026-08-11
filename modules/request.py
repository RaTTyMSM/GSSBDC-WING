
from datetime import date
from datetime import datetime
from modules.donation import create_automatic_donation
from core.helpers import *
from modules.donation import get_eligibility

def create_blood_request(requests, current_member):

    print("\n========== BLOOD REQUEST ==========")

    # --------------------------------
    # Blood Group Validation
    # --------------------------------

    valid_blood_groups = [
        "A+", "A-",
        "B+", "B-",
        "AB+", "AB-",
        "O+", "O-"
    ]

    blood_group = input(
        "Required Blood Group: "
    ).strip().upper()

    if blood_group not in valid_blood_groups:

        print(
            "\nInvalid blood group."
        )

        print(
            "Valid groups:",
            ", ".join(valid_blood_groups)
        )

        return

    # --------------------------------
    # Area
    # --------------------------------

    area = input(
        "Required Area: "
    ).strip()

    if not area:

        print(
            "Area cannot be empty."
        )

        return

    # --------------------------------
    # Latitude / Longitude
    # --------------------------------

    try:

        latitude = float(
            input("Request Latitude: ")
        )

        longitude = float(
            input("Request Longitude: ")
        )

    except ValueError:

        print(
            "\nInvalid latitude or longitude."
        )

        return

    # Validate geographical range

    if not -90 <= latitude <= 90:

        print(
            "Latitude must be between -90 and 90."
        )

        return

    if not -180 <= longitude <= 180:

        print(
            "Longitude must be between -180 and 180."
        )

        return

    # --------------------------------
    # Number of Bags
    # --------------------------------

    try:

        bags = int(
            input("Number of Bags: ")
        )

    except ValueError:

        print(
            "Invalid number of bags."
        )

        return

    if bags <= 0:

        print(
            "Number of bags must be greater than 0."
        )

        return

    # --------------------------------
    # Urgency
    # --------------------------------

    print("\nUrgency:")

    print("1. Normal")
    print("2. Emergency")

    urgency_choice = input(
        "Enter choice: "
    ).strip()

    urgency_map = {

        "1": "Normal",

        "2": "Emergency"
    }

    if urgency_choice not in urgency_map:

        print(
            "Invalid urgency."
        )

        return

    urgency = urgency_map[
        urgency_choice
    ]

    # --------------------------------
    # Generate Unique Request ID
    # --------------------------------

    if requests:

        request_id = max(
            request["id"]
            for request in requests
        ) + 1

    else:

        request_id = 1

    # --------------------------------
    # Create Request
    # --------------------------------

    request = {

        "id": request_id,

        "blood_group": blood_group,

        "area": area,

        "latitude": latitude,

        "longitude": longitude,

        "bags": bags,

        "urgency": urgency,

        "status": "Open",

        "created_by": current_member["id"],

        "managed_by": None,

        "donor_id": None,

        "collected_bags": 0
    }

    # --------------------------------
    # Save
    # --------------------------------

    requests.append(request)

    save_data(
        REQUEST_FILE,
        requests
    )

    # --------------------------------
    # Result
    # --------------------------------

    print("\n================================")
    print("   BLOOD REQUEST CREATED")
    print("================================")

    print(
        "Request ID:",
        request_id
    )

    print(
        "Blood Group:",
        blood_group
    )

    print(
        "Area:",
        area
    )

    print(
        "Required Bags:",
        bags
    )

    print(
        "Urgency:",
        urgency
    )

    print(
        "Created By:",
        current_member["name"]
    )

    print(
        "Status: Open"
    )


# =====================================
# Show Blood Requests
# =====================================

def show_blood_requests(requests):

    print("\n========== BLOOD REQUESTS ==========")

    if not requests:
        print("No blood requests found.")
        return

    for request in requests:

        status = request.get("status", "Open")

        print("\n--------------------------------")

        print(
            "Request ID:",
            request.get("id")
        )

        print(
            "Blood Group:",
            request.get("blood_group")
        )

        print(
            "Area:",
            request.get("area")
        )

        print(
            "Required Bags:",
            request.get("bags")
        )

        print(
            "Urgency:",
            request.get("urgency")
        )

        print(
            "Status:",
            status
        )

        if request.get("managed_by") is not None:

            print(
                "Managed By Member ID:",
                request.get("managed_by")
            )

        if request.get("collected_bags") is not None:

            print(
                "Collected Bags:",
                request.get("collected_bags")
            )

    print("\n--------------------------------")

# =====================================
# Smart Donor Matching
# =====================================

def find_matching_donors(
    donors,
    donations,
    requests
):

    print("\n========== SMART DONOR SEARCH ==========")

    if not requests:

        print("No blood request found.")
        return

    # =================================
    # Select Open Request
    # =================================

    print("\n========== OPEN REQUESTS ==========")

    open_requests = []

    for request in requests:

        if request.get("status") == "Open":

            open_requests.append(request)

            print(
                f'ID: {request["id"]} | '
                f'{request["blood_group"]} | '
                f'{request["area"]} | '
                f'{request["bags"]} Bags | '
                f'{request["urgency"]}'
            )

    if not open_requests:

        print("No open blood request found.")
        return

    try:

        request_id = int(
            input("\nEnter Request ID: ")
        )

    except ValueError:

        print("Invalid Request ID.")
        return

    # =================================
    # Find Selected Request
    # =================================

    request = None

    for r in requests:

        if r["id"] == request_id:

            request = r
            break

    if request is None:

        print("Request not found.")
        return

    # =================================
    # Request Information
    # =================================

    print("\n========================================")
    print("          REQUEST INFORMATION")
    print("========================================")

    print(
        "Request ID:",
        request["id"]
    )

    print(
        "Blood Group:",
        request["blood_group"]
    )

    print(
        "Area:",
        request["area"]
    )

    print(
        "Required Bags:",
        request["bags"]
    )

    print(
        "Urgency:",
        request["urgency"]
    )

    # =================================
    # Find Matching Donors
    # =================================

    matched_donors = []

    for donor in donors:

        # ---------------------------------
        # Blood Group Check
        # ---------------------------------

        if donor["blood_group"] != request["blood_group"]:

            continue

        # ---------------------------------
        # Active Check
        # ---------------------------------

        if not donor.get("active", True):

            continue

        # ---------------------------------
        # Eligibility Check
        # ---------------------------------

        eligibility = get_eligibility(
            donor["id"],
            donations
        )

        if not eligibility["eligible"]:

            continue

        # ---------------------------------
        # Location Check
        # ---------------------------------

        if (
            "latitude" not in donor
            or "longitude" not in donor
        ):

            continue

        if (
            "latitude" not in request
            or "longitude" not in request
        ):

            continue

        # ---------------------------------
        # Calculate Distance
        # ---------------------------------

        distance = calculate_distance(

            request["latitude"],
            request["longitude"],

            donor["latitude"],
            donor["longitude"]
        )

        # ---------------------------------
        # Donation Statistics
        # ---------------------------------

        donation_count = 0
        total_bags = 0

        for donation in donations:

            if donation["donor_id"] == donor["id"]:

                donation_count += 1

                total_bags += donation.get(
                    "bags",
                    0
                )

        # ---------------------------------
        # Add Matched Donor
        # ---------------------------------

        matched_donors.append({

            "donor": donor,

            "distance": distance,

            "eligibility": eligibility,

            "donation_count": donation_count,

            "total_bags": total_bags

        })

    # =================================
    # Sort By Distance
    # =================================

    matched_donors.sort(
        key=lambda x: x["distance"]
    )

    # =================================
    # Display Matched Donors
    # =================================

    print("\n========================================")
    print("          MATCHED DONORS")
    print("========================================")

    if not matched_donors:

        print(
            "No active and eligible donor found."
        )

        return

    for i, result in enumerate(
        matched_donors,
        start=1
    ):

        donor = result["donor"]

        distance = result["distance"]

        eligibility = result["eligibility"]

        donation_count = result[
            "donation_count"
        ]

        total_bags = result[
            "total_bags"
        ]

        print("\n----------------------------------------")

        print(
            f"#{i}"
        )

        print(
            "Donor ID:",
            donor["id"]
        )

        print(
            "Name:",
            donor["name"]
        )

        print(
            "Blood Group:",
            donor["blood_group"]
        )

        print(
            "Phone:",
            donor["phone"]
        )

        print(
            "Area:",
            donor["area"]
        )

        print(
            f"Distance: {distance:.2f} km"
        )

        # ---------------------------------
        # Donation History
        # ---------------------------------

        print(
            "Total Donations:",
            donation_count
        )

        print(
            "Total Blood:",
            total_bags,
            "Bags"
        )

        # ---------------------------------
        # Eligibility Information
        # ---------------------------------

        if eligibility["last_date"] is None:

            print(
                "Last Donation: Never"
            )

            print(
                "Next Eligible: Available Now"
            )

            print(
                "Days Remaining: 0"
            )

        else:

            print(
                "Last Donation:",
                eligibility["last_date"]
            )

            print(
                "Next Eligible Date:",
                eligibility["next_date"]
            )

            print(
                "Days Remaining:",
                eligibility["days_remaining"]
            )

        print(
            "Status: AVAILABLE"
        )

    # =================================
    # Summary
    # =================================

    print("\n========================================")

    print(
        "Showing",
        len(matched_donors),
        "eligible donors."
    )

    print(
        "Sorted by nearest distance."
    )

    print("========================================")



# =====================================
# Update Old Requests
# =====================================

def update_old_requests(requests, members):

    changed = False

    for request in requests:

        # --------------------------------
        # Old request: managed_by missing
        # --------------------------------

        if "managed_by" not in request:

            request["managed_by"] = None
            changed = True


        # --------------------------------
        # Old request: donor_id missing
        # --------------------------------

        if "donor_id" not in request:

            request["donor_id"] = None
            changed = True


        # --------------------------------
        # Old request: collected_bags missing
        # --------------------------------

        if "collected_bags" not in request:

            request["collected_bags"] = 0
            changed = True


        # --------------------------------
        # Old request: completed_date missing
        # --------------------------------

        if "completed_date" not in request:

            request["completed_date"] = None
            changed = True


        # --------------------------------
        # Old request: managed_by_name missing
        # --------------------------------

        if "managed_by_name" not in request:

            request["managed_by_name"] = None
            changed = True


    # --------------------------------
    # Save updated requests
    # --------------------------------

    if changed:

        save_data(
            REQUEST_FILE,
            requests
        )

        print(
            "\nOld request data updated successfully!"
        )

# =====================================
# Complete Blood Request
# =====================================

def complete_blood_request(
    requests,
    donors,
    members,
    donations,
    current_member
):

    print("\n========== COMPLETE BLOOD REQUEST ==========")

    # --------------------------------
    # 1. Find Open Requests
    # --------------------------------

    open_requests = []

    for request in requests:

        if request.get("status") == "Open":

            open_requests.append(request)

    if not open_requests:

        print("No open blood request found.")
        return

    print("\n========== OPEN REQUESTS ==========")

    for request in open_requests:

        print(
            f'ID: {request["id"]} | '
            f'{request["blood_group"]} | '
            f'{request["area"]} | '
            f'{request["bags"]} Bags | '
            f'{request["urgency"]}'
        )

    # --------------------------------
    # 2. Select Request
    # --------------------------------

    try:

        request_id = int(
            input("\nEnter Request ID: ")
        )

    except ValueError:

        print("Invalid Request ID.")
        return

    selected_request = None

    for request in requests:

        if request.get("id") == request_id:

            selected_request = request
            break

    if selected_request is None:

        print("Request not found.")
        return

    # --------------------------------
    # 3. Check Request Status
    # --------------------------------

    if selected_request.get("status") != "Open":

        print(
            "\nThis request is already completed."
        )

        return

    # --------------------------------
    # 4. Current Member as Manager
    # --------------------------------

    manager_id = current_member.get("id")

    manager = None

    for member in members:

        if member.get("id") == manager_id:

            manager = member
            break

    if manager is None:

        print(
            "\nCurrent member not found."
        )

        return

    # --------------------------------
    # 5. Select Donor
    # --------------------------------

    try:

        donor_id = int(
            input("\nEnter Donor ID: ")
        )

    except ValueError:

        print("Invalid Donor ID.")
        return

    donor = None

    for d in donors:

        if d.get("id") == donor_id:

            donor = d
            break

    if donor is None:

        print("Donor not found.")
        return

    # --------------------------------
    # 6. Check Blood Group
    # --------------------------------

    if (
        donor.get("blood_group")
        != selected_request.get("blood_group")
    ):

        print(
            "\nDonor blood group does not match "
            "the requested blood group."
        )

        return

    # --------------------------------
    # 7. Check Active Status
    # --------------------------------

    if not donor.get("active", True):

        print(
            "\nThis donor is inactive."
        )

        return

    # --------------------------------
    # 8. Check Eligibility
    # --------------------------------

    eligibility = get_eligibility(
        donor_id,
        donations
    )

    if not eligibility["eligible"]:

        print(
            "\nThis donor is currently not eligible "
            "to donate blood."
        )

        if eligibility["next_date"]:

            print(
                "Next Eligible Date:",
                eligibility["next_date"]
            )

            print(
                "Days Remaining:",
                eligibility["days_remaining"]
            )

        return

    # --------------------------------
    # 9. Collected Blood
    # --------------------------------

    try:

        collected_bags = int(
            input("Collected Blood Bags: ")
        )

    except ValueError:

        print("Invalid number of bags.")
        return

    if collected_bags <= 0:

        print(
            "Number of bags must be greater than 0."
        )

        return

    # --------------------------------
    # 10. Check Requested Bags
    # --------------------------------

    requested_bags = selected_request.get(
        "bags",
        0
    )

    if collected_bags > requested_bags:

        print(
            "\nCollected bags cannot be greater "
            "than requested bags."
        )

        return

    # --------------------------------
    # 11. Confirmation
    # --------------------------------

    print("\n========== CONFIRMATION ==========")

    print(
        "Request ID:",
        selected_request["id"]
    )

    print(
        "Blood Group:",
        selected_request["blood_group"]
    )

    print(
        "Donor:",
        donor["name"]
    )

    print(
        "Collected Bags:",
        collected_bags
    )

    print(
        "Managed By:",
        manager["name"]
    )

    confirm = input(
        "\nConfirm completion? (Yes/No): "
    ).strip().upper()

    if confirm != "Yes":

        print(
            "\nRequest completion cancelled."
        )

        return

    # --------------------------------
    # 12. Update Request
    # --------------------------------

    selected_request["status"] = "Fulfilled"

    selected_request["managed_by"] = manager_id

    selected_request["managed_by_name"] = (
        manager["name"]
    )

    selected_request["donor_id"] = donor_id

    selected_request["donor_name"] = (
        donor["name"]
    )

    selected_request["collected_bags"] = (
        collected_bags
    )

    selected_request["completed_date"] = (
        date.today().isoformat()
    )

    # --------------------------------
    # 13. Automatic Donation Record
    # --------------------------------

    donation_date = date.today().isoformat()

    create_automatic_donation(
        donor,
        donations,
        donation_date,
        collected_bags
    )

    # --------------------------------
    # 14. Update Member Statistics
    # --------------------------------

    manager["requests_managed"] = (
        manager.get("requests_managed", 0) + 1
    )

    manager["successful_cases"] = (
        manager.get("successful_cases", 0) + 1
    )

    manager["blood_managed"] = (
        manager.get("blood_managed", 0)
        + collected_bags
    )

    # --------------------------------
    # 15. Save Request Data
    # --------------------------------

    save_data(
        REQUEST_FILE,
        requests
    )

    # --------------------------------
    # 16. Save Member Data
    # --------------------------------

    save_data(
        MEMBER_FILE,
        members
    )

    # --------------------------------
    # 17. Save Donation Data
    # --------------------------------

    save_data(
        DONATION_FILE,
        donations
    )

    # --------------------------------
    # 18. Final Result
    # --------------------------------

    print("\n========================================")
    print("          REQUEST FULFILLED")
    print("========================================")

    print(
        "Request ID:",
        selected_request["id"]
    )

    print(
        "Blood Group:",
        selected_request["blood_group"]
    )

    print(
        "Donor:",
        donor["name"]
    )

    print(
        "Collected:",
        collected_bags,
        "Bags"
    )

    print(
        "Managed By:",
        manager["name"]
    )

    print(
        "Member Type:",
        manager["type"]
    )

    print(
        "Completed Date:",
        selected_request["completed_date"]
    )

    print(
        "Status: Fulfilled"
    )

    print(
        "\nDonation record created successfully!"
    )

    print(
        "Member statistics updated successfully!"
    )


from core.helpers import *
from core.permissions import *
from modules.donation import get_eligibility

# =====================================
# Donor Functions
# =====================================

def add_donor(donors):

    print("\n========== ADD DONOR ==========")

    # ---------------------------------
    # Name
    # ---------------------------------

    name = input("Name: ").strip()

    if not name:

        print("Name cannot be empty.")
        return

    # ---------------------------------
    # Blood Group
    # ---------------------------------

    valid_blood_groups = [
        "A+", "A-",
        "B+", "B-",
        "AB+", "AB-",
        "O+", "O-"
    ]

    blood_group = input(
        "Blood Group: "
    ).strip().upper()

    if blood_group not in valid_blood_groups:

        print("\nInvalid blood group.")

        print(
            "Valid groups:",
            ", ".join(valid_blood_groups)
        )

        return

    # ---------------------------------
    # Phone
    # ---------------------------------

    phone = input(
        "Phone: "
    ).strip()

    if not phone:

        print("Phone number cannot be empty.")
        return

    # Remove spaces and common symbols
    clean_phone = (
        phone
        .replace(" ", "")
        .replace("-", "")
        .replace("+", "")
    )

    if not clean_phone.isdigit():

        print(
            "Invalid phone number."
        )

        return

    if len(clean_phone) < 10:

        print(
            "Phone number is too short."
        )

        return

    # ---------------------------------
    # Duplicate Phone Check
    # ---------------------------------

    for donor in donors:

        existing_phone = (
            donor.get("phone", "")
            .replace(" ", "")
            .replace("-", "")
            .replace("+", "")
        )

        if existing_phone == clean_phone:

            print(
                "\nA donor with this phone "
                "number already exists."
            )

            print(
                "Donor ID:",
                donor["id"]
            )

            print(
                "Name:",
                donor["name"]
            )

            return

    # ---------------------------------
    # Area
    # ---------------------------------

    area = input(
        "Area: "
    ).strip()

    if not area:

        print(
            "Area cannot be empty."
        )

        return

    # ---------------------------------
    # Latitude / Longitude
    # ---------------------------------

    try:

        latitude = float(
            input("Latitude: ")
        )

        longitude = float(
            input("Longitude: ")
        )

    except ValueError:

        print(
            "\nInvalid latitude or longitude."
        )

        return

    # ---------------------------------
    # Location Range Validation
    # ---------------------------------

    if not -90 <= latitude <= 90:

        print(
            "Latitude must be between "
            "-90 and 90."
        )

        return

    if not -180 <= longitude <= 180:

        print(
            "Longitude must be between "
            "-180 and 180."
        )

        return

    # ---------------------------------
    # Generate Unique Donor ID
    # ---------------------------------

    if donors:

        donor_id = max(
            donor["id"]
            for donor in donors
        ) + 1

    else:

        donor_id = 1

    # ---------------------------------
    # Create Donor
    # ---------------------------------

    donor = {

        "id": donor_id,

        "name": name,

        "blood_group": blood_group,

        "phone": phone,

        "area": area,

        "latitude": latitude,

        "longitude": longitude,

        "active": True
    }

    # ---------------------------------
    # Save Donor
    # ---------------------------------

    donors.append(donor)

    save_data(
        DONOR_FILE,
        donors
    )

    # ---------------------------------
    # Result
    # ---------------------------------

    print("\n================================")
    print("       DONOR ADDED")
    print("================================")

    print(
        "Donor ID:",
        donor_id
    )

    print(
        "Name:",
        name
    )

    print(
        "Blood Group:",
        blood_group
    )

    print(
        "Phone:",
        phone
    )

    print(
        "Area:",
        area
    )

    print(
        "Status: Active"
    )

    print(
        "\nDonor added successfully!"
    )

# =====================================
# Show All Donors
# =====================================

def show_all_donors(donors, donations):

    print("\n========== ALL DONORS ==========")

    if not donors:

        print("No donors found.")
        return

    for donor in donors:

        # --------------------------------
        # Active / Inactive
        # --------------------------------

        active_status = (
            "Active"
            if donor.get("active", True)
            else "Inactive"
        )

        # --------------------------------
        # Eligibility
        # --------------------------------

        # donations variable is available
        # globally in this program

        eligibility = get_eligibility(
            donor["id"],
            donations
        )

        # --------------------------------
        # Basic Information
        # --------------------------------

        print("\n----------------------------------------")

        print(
            f'ID: {donor["id"]}'
        )

        print(
            f'Name: {donor["name"]}'
        )

        print(
            f'Blood Group: {donor["blood_group"]}'
        )

        print(
            f'Phone: {donor["phone"]}'
        )

        print(
            f'Area: {donor["area"]}'
        )

        print(
            f'Activity Status: {active_status}'
        )

        # --------------------------------
        # Donation Information
        # --------------------------------

        if eligibility["last_date"] is None:

            print(
                "Last Donation: Never"
            )

            print(
                "Next Eligible Date: Available Now"
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

        # --------------------------------
        # Final Availability
        # --------------------------------

        if not donor.get("active", True):

            print(
                "Blood Availability: NOT AVAILABLE"
            )

        elif eligibility["eligible"]:

            print(
                "Blood Availability: AVAILABLE"
            )

        else:

            print(
                "Blood Availability: NOT AVAILABLE"
            )

    print("\n----------------------------------------")

# =====================================
# Blood Group Search
# =====================================

def search_by_blood_group(donors):

    blood_group = input("\nEnter blood group: ").upper()

    found = False

    print("\n========== RESULTS ==========")

    for donor in donors:

        if donor["blood_group"] == blood_group:

            status = "Active" if donor["active"] else "Inactive"

            print(
                f'{donor["name"]} | '
                f'{donor["phone"]} | '
                f'{donor["area"]} | '
                f'{status}'
            )

            found = True

    if not found:
        print("No donor found.")

# =====================================
# Update Missing Locations
# =====================================

def update_missing_locations(donors):

    changed = False

    for donor in donors:

        if "latitude" not in donor:

            print("\n==============================")
            print("Location missing for:", donor["name"])
            print("==============================")

            while True:

                try:
                    latitude = float(
                        input("Enter latitude: ")
                    )
                    break

                except ValueError:
                    print("Please enter a valid number.")

            while True:

                try:
                    longitude = float(
                        input("Enter longitude: ")
                    )
                    break

                except ValueError:
                    print("Please enter a valid number.")

            donor["latitude"] = latitude
            donor["longitude"] = longitude

            changed = True

    if changed:

        save_data(
            DONOR_FILE,
            donors
        )

        print("\nDonor locations updated successfully!")


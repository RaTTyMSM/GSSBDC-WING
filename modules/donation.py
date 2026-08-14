from datetime import date
from datetime import datetime
from datetime import timedelta

from core.helpers import *
from core.permissions import *

# Standard minimum gap between whole-blood donations (WHO/BDS guideline: 90 days / ~3 months)
DONATION_WAITING_DAYS = 90

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
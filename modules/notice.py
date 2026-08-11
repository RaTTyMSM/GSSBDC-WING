from core.helpers import *
from core.permissions import *

# =====================================
# Notice System
# =====================================

def add_notice(notices, current_member):

    print("\n========== ADD NOTICE ==========")

    title = input("Notice Title: ").strip()

    if not title:
        print("Notice title cannot be empty.")
        return

    message = input("Notice Message: ").strip()

    if not message:
        print("Notice message cannot be empty.")
        return

    print("\nPriority:")
    print("1. Normal")
    print("2. Important")
    print("3. Emergency")

    priority_choice = input("Enter priority: ")

    priority_map = {
        "1": "Normal",
        "2": "Important",
        "3": "Emergency"
    }

    if priority_choice not in priority_map:

        print("Invalid priority.")
        return

    priority = priority_map[priority_choice]

    notice = {

        "id": len(notices) + 1,

        "title": title,

        "message": message,

        "priority": priority,

        "date": date.today().isoformat(),

        "posted_by": current_member["id"],

        "posted_by_name": current_member["name"],

        "active": True
    }

    notices.append(notice)

    save_data(
        NOTICE_FILE,
        notices
    )

    print("\nNotice created successfully!")


def show_notices(notices):

    print("\n========== CLUB NOTICES ==========")

    active_notices = []

    for notice in notices:

        if notice.get("active", True):

            active_notices.append(notice)

    if not active_notices:

        print("No active notices found.")
        return

    for notice in active_notices:

        print("\n========================================")

        print(
            "Notice ID:",
            notice["id"]
        )

        print(
            "Title:",
            notice["title"]
        )

        print(
            "Priority:",
            notice["priority"]
        )

        print(
            "Message:",
            notice["message"]
        )

        print(
            "Date:",
            notice["date"]
        )

        print(
            "Posted By:",
            notice["posted_by_name"]
        )

    print("\n========================================")

# =====================================
# Manage Notices
# =====================================

def manage_notices(notices, current_member):

    while True:

        print("\n========================================")
        print("          MANAGE NOTICES")
        print("========================================")

        print("1. Add Notice")
        print("2. Edit Notice")
        print("3. Delete Notice")
        print("4. Activate Notice")
        print("5. Deactivate Notice")
        print("6. Back")

        choice = input("\nEnter choice: ")


        if choice == "1":

            add_notice(
        notices,
        current_member
    )


        elif choice == "2":

            if not notices:

                print("No notices found.")
                continue

            show_notices(notices)

            try:

                notice_id = int(
                    input("\nEnter Notice ID: ")
                )

            except ValueError:

                print("Invalid Notice ID.")
                continue

            notice = None

            for n in notices:

                if n["id"] == notice_id:

                    notice = n
                    break

            if notice is None:

                print("Notice not found.")
                continue

            print("\nLeave blank to keep the current value.")

            new_title = input(
                f'Title [{notice["title"]}]: '
            ).strip()

            new_message = input(
                f'Message [{notice["message"]}]: '
            ).strip()

            print("\nPriority:")
            print("1. Normal")
            print("2. Important")
            print("3. Emergency")

            new_priority = input(
                f'Priority [{notice["priority"]}]: '
            ).strip()

            if new_title:

                notice["title"] = new_title

            if new_message:

                notice["message"] = new_message

            if new_priority in ["1", "2", "3"]:

                priority_map = {
                    "1": "Normal",
                    "2": "Important",
                    "3": "Emergency"
                }

                notice["priority"] = priority_map[
                    new_priority
                ]

            notice["edited_by"] = current_member["id"]

            notice["edited_by_name"] = current_member["name"]

            notice["edited_date"] = date.today().isoformat()

            save_data(
                NOTICE_FILE,
                notices
            )

            print("\nNotice updated successfully!")


        elif choice == "3":

            if not notices:

                print("No notices found.")
                continue

            show_notices(notices)

            try:

                notice_id = int(
                    input("\nEnter Notice ID: ")
                )

            except ValueError:

                print("Invalid Notice ID.")
                continue

            notice = None

            for n in notices:

                if n["id"] == notice_id:

                    notice = n
                    break

            if notice is None:

                print("Notice not found.")
                continue

            confirm = input(
                "Are you sure you want to delete this notice? (Yes/No): "
            ).lower()

            if confirm != "yes":

                print("Delete cancelled.")
                continue

            notices.remove(notice)

            save_data(
                NOTICE_FILE,
                notices
            )

            print("\nNotice deleted successfully!")


        elif choice == "4":

            if not notices:

                print("No notices found.")
                continue

            show_notices(notices)

            try:

                notice_id = int(
                    input("\nEnter Notice ID: ")
                )

            except ValueError:

                print("Invalid Notice ID.")
                continue

            found = False

            for notice in notices:

                if notice["id"] == notice_id:

                    notice["active"] = True

                    found = True

                    break

            if found:

                save_data(
                    NOTICE_FILE,
                    notices
                )

                print(
                    "\nNotice activated successfully!"
                )

            else:

                print("Notice not found.")


        elif choice == "5":

            if not notices:

                print("No notices found.")
                continue

            show_notices(notices)

            try:

                notice_id = int(
                    input("\nEnter Notice ID: ")
                )

            except ValueError:

                print("Invalid Notice ID.")
                continue

            found = False

            for notice in notices:

                if notice["id"] == notice_id:

                    notice["active"] = False

                    found = True

                    break

            if found:

                save_data(
                    NOTICE_FILE,
                    notices
                )

                print(
                    "\nNotice deactivated successfully!"
                )

            else:

                print("Notice not found.")


        elif choice == "6":

            break

        else:

            print("Invalid choice!")


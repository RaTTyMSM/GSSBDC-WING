from core.security import hash_password, is_hashed
from core.helpers import load_data, save_data, MEMBER_FILE

members = load_data(MEMBER_FILE)
changed = 0
for m in members:
    pw = m.get("password", "")
    if pw and not is_hashed(pw):
        m["password"] = hash_password(pw)
        changed += 1

save_data(MEMBER_FILE, members)
print(f"Done. Hashed {changed} password(s).")
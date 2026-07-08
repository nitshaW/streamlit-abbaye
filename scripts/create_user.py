"""Generate a DASHBOARD_USERS INSERT with a bcrypt-hashed password.

Usage:
    python scripts/create_user.py <email> "<Full Name>" <customer>

Prompts for the password (never echoed / never logged), bcrypt-hashes it, and
prints the INSERT statement to run in Snowflake. The plaintext password never
leaves this process.
"""
import getpass
import sys

import bcrypt


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    email = sys.argv[1].strip().lower()
    name = sys.argv[2].strip()
    customer = sys.argv[3].strip().lower()

    pw = getpass.getpass("Password: ")
    if pw != getpass.getpass("Confirm password: "):
        sys.exit("Passwords do not match.")
    if len(pw) < 10:
        sys.exit("Use at least 10 characters.")

    pw_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

    def q(s):
        return s.replace("'", "''")

    print("\n-- Run in Snowflake:")
    print(
        "INSERT INTO SALES_ANALYTICS.PUBLIC.DASHBOARD_USERS "
        "(EMAIL, NAME, PASSWORD_HASH, CUSTOMER, ACTIVE)\n"
        f"VALUES ('{q(email)}', '{q(name)}', '{q(pw_hash)}', '{q(customer)}', TRUE);"
    )


if __name__ == "__main__":
    main()

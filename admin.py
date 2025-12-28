import sqlite3

username = input("Enter username to make admin: ")

conn = sqlite3.connect("glambeauty.db")
c = conn.cursor()

c.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (username,))
conn.commit()

if c.rowcount > 0:
    print(f"✅ {username} is now an admin!")
else:
    print(f"❌ User {username} not found!")

conn.close()

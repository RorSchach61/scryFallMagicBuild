"""The one user this single-person app runs as.

Decks are still stored per user, so rather than reshaping the database the app
quietly uses a single account and never asks anyone to sign in.
"""
LOCAL_USERNAME = "local"


# reuses the oldest existing account so decks made back when the app had a
# sign-in screen stay visible; a fresh install gets a new one
def local_user(users):
    existing = users.all_users()
    if existing:
        return existing[0]
    return users.create(LOCAL_USERNAME)

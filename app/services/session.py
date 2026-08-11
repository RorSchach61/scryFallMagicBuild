"""Who is currently signed in.

Holds no widgets and no storage of its own, so the sign-in rules can be tested
without a window and the interface has one place to ask who the user is.
"""


class Session:

    def __init__(self, users):
        self._users = users
        self._user = None

    @property
    def user(self):
        return self._user

    def is_authenticated(self):
        return self._user is not None

    # a failed attempt leaves an existing session alone, so mistyping a
    # password while already signed in does not sign the user out
    def login(self, username, password):
        user = self._users.authenticate(username, password)
        if user is not None:
            self._user = user
        return user

    def logout(self):
        self._user = None

    # the name to show in the interface, or None when signed out
    def label(self):
        return self._user.label() if self._user else None

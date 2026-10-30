"""Who is currently signed in.

Holds no widgets and no storage of its own, so the sign-in rules can be tested
without a window and the interface has one place to ask who the user is.
"""


class Session:

    def __init__(self, users):
        self._users = users
        self._user_id = None

    # only the id is kept and the user is read fresh, so a rename shows at
    # once and a deleted user simply reads as signed out
    @property
    def user(self):
        return None if self._user_id is None else self._users.get(self._user_id)

    def is_authenticated(self):
        return self.user is not None

    # a failed attempt leaves an existing session alone, so mistyping a
    # password while already signed in does not sign the user out
    def login(self, username, password):
        user = self._users.authenticate(username, password)
        if user is not None:
            self._user_id = user.user_id
        return user

    def logout(self):
        self._user_id = None

    # the name to show in the interface, or None when signed out
    def label(self):
        user = self.user
        return user.label() if user else None

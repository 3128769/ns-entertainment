"""Background task handlers, one module per kind of work.

Each handler is ``async run(account_id, source) -> result`` and returns the same
result dict that is stored in history and shown to the user.
"""
from nsapp.tasks import checkin, cookie_check, keywords, messages

HANDLERS = {
    "sign": checkin.run,
    "monitor": keywords.run,
    "message": messages.run,
    "offline": cookie_check.run,
}

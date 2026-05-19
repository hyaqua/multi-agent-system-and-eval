"""
Protocol definitions for the collaborative text editor.
All messages are newline-delimited JSON objects.
"""

# Message types
TYPE_CONNECT = "connect"
TYPE_ACK = "ack"
TYPE_OPERATION = "operation"
TYPE_CURSOR_UPDATE = "cursor_update"
TYPE_LOCK_REQUEST = "lock_request"
TYPE_LOCK_GRANT = "lock_grant"
TYPE_LOCK_RELEASE = "lock_release"
TYPE_SAVE_REQUEST = "save_request"
TYPE_SAVE_ACK = "save_ack"
TYPE_DISCONNECT = "disconnect"
TYPE_ERROR = "error"
TYPE_USER_JOIN = "user_join"
TYPE_USER_LEAVE = "user_leave"

# Operation types
OP_INSERT = "insert"
OP_DELETE = "delete"

# Lock actions
LOCK_ACQUIRE = "acquire"
LOCK_RELEASE = "release"


def make_connect(username, room, password=""):
    return {
        "type": TYPE_CONNECT,
        "username": username,
        "room": room,
        "password": password,
    }


def make_ack(document, revision, users, lock_owner=None):
    return {
        "type": TYPE_ACK,
        "document": document,
        "revision": revision,
        "users": users,
        "lock_owner": lock_owner,
    }


def make_operation(msg_id, base_revision, ops):
    return {
        "type": TYPE_OPERATION,
        "id": msg_id,
        "base_revision": base_revision,
        "ops": ops,
    }


def make_cursor_update(username, revision, position):
    return {
        "type": TYPE_CURSOR_UPDATE,
        "username": username,
        "revision": revision,
        "position": position,
    }


def make_lock_request(username, action):
    return {
        "type": TYPE_LOCK_REQUEST,
        "username": username,
        "action": action,
    }


def make_lock_grant(username):
    return {
        "type": TYPE_LOCK_GRANT,
        "username": username,
    }


def make_lock_release(username):
    return {
        "type": TYPE_LOCK_RELEASE,
        "username": username,
    }


def make_save_request(username):
    return {
        "type": TYPE_SAVE_REQUEST,
        "username": username,
    }


def make_save_ack(username):
    return {
        "type": TYPE_SAVE_ACK,
        "username": username,
    }


def make_disconnect(username):
    return {
        "type": TYPE_DISCONNECT,
        "username": username,
    }


def make_error(message):
    return {
        "type": TYPE_ERROR,
        "message": message,
    }


def make_user_join(username):
    return {
        "type": TYPE_USER_JOIN,
        "username": username,
    }


def make_user_leave(username):
    return {
        "type": TYPE_USER_LEAVE,
        "username": username,
    }

"""
Protocol definitions for the collaborative text editor.
All communication uses newline-delimited JSON over TCP.

Message types and helper functions for creating/parsing messages.
"""

import json

# Message type constants
MSG_CONNECT = 'connect'
MSG_ACK = 'ack'
MSG_OPERATION = 'operation'
MSG_CURSOR_UPDATE = 'cursor_update'
MSG_LOCK_REQUEST = 'lock_request'
MSG_LOCK_GRANT = 'lock_grant'
MSG_LOCK_RELEASE = 'lock_release'
MSG_LOCK_STATUS = 'lock_status'
MSG_SAVE_REQUEST = 'save_request'
MSG_SAVE_ACK = 'save_ack'
MSG_DISCONNECT = 'disconnect'
MSG_ERROR = 'error'
MSG_UNDO = 'undo'
MSG_USER_JOIN = 'user_join'
MSG_USER_LEAVE = 'user_leave'


def encode_message(msg):
    """Encode a message dict to a JSON string with newline terminator."""
    return json.dumps(msg) + '\n'


def decode_message(data):
    """Decode a JSON string to a message dict."""
    return json.loads(data.strip())


def make_connect(username, room, password):
    return {
        'type': MSG_CONNECT,
        'username': username,
        'room': room,
        'password': password
    }


def make_ack(client_id, document, version, clients, lock_holder):
    return {
        'type': MSG_ACK,
        'client_id': client_id,
        'document': document,
        'version': version,
        'clients': clients,
        'lock_holder': lock_holder
    }


def make_operation(ops, base_version, client_id):
    return {
        'type': MSG_OPERATION,
        'ops': ops,
        'base_version': base_version,
        'client_id': client_id
    }


def make_cursor_update(client_id, username, row, col):
    return {
        'type': MSG_CURSOR_UPDATE,
        'client_id': client_id,
        'username': username,
        'row': row,
        'col': col
    }


def make_lock_request(client_id):
    return {
        'type': MSG_LOCK_REQUEST,
        'client_id': client_id
    }


def make_lock_release(client_id):
    return {
        'type': MSG_LOCK_RELEASE,
        'client_id': client_id
    }


def make_lock_status(holder, queue):
    return {
        'type': MSG_LOCK_STATUS,
        'holder': holder,
        'queue': queue
    }


def make_lock_grant(client_id, holder):
    return {
        'type': MSG_LOCK_GRANT,
        'client_id': client_id,
        'holder': holder
    }


def make_save_request(client_id):
    return {
        'type': MSG_SAVE_REQUEST,
        'client_id': client_id
    }


def make_save_ack():
    return {
        'type': MSG_SAVE_ACK
    }


def make_error(message):
    return {
        'type': MSG_ERROR,
        'message': message
    }


def make_undo(client_id):
    return {
        'type': MSG_UNDO,
        'client_id': client_id
    }


def make_user_join(client_id, username, cursor_row, cursor_col):
    return {
        'type': MSG_USER_JOIN,
        'client_id': client_id,
        'username': username,
        'cursor_row': cursor_row,
        'cursor_col': cursor_col
    }


def make_user_leave(client_id, username):
    return {
        'type': MSG_USER_LEAVE,
        'client_id': client_id,
        'username': username
    }

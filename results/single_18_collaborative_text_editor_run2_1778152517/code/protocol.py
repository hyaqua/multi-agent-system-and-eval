"""Protocol definitions for collaborative text editor.

All communication uses newline-delimited JSON messages over TCP.
"""

import json

# Message types
MSG_CONNECT = 'connect'
MSG_ACK = 'ack'
MSG_OPERATION = 'operation'
MSG_OPERATION_BROADCAST = 'operation_broadcast'
MSG_OPERATION_ACK = 'operation_ack'
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
MSG_USER_JOINED = 'user_joined'
MSG_USER_LEFT = 'user_left'


def encode(msg):
    """Encode a message dict to a JSON string with newline terminator."""
    return json.dumps(msg) + '\n'


def decode(data):
    """Decode a JSON string to a message dict."""
    return json.loads(data.strip())


def make_connect(username, room, password=''):
    return {
        'type': MSG_CONNECT,
        'username': username,
        'room': room,
        'password': password
    }


def make_operation(op, version, op_id):
    return {
        'type': MSG_OPERATION,
        'op': op,
        'version': version,
        'id': op_id
    }


def make_cursor_update(cursor_row, cursor_col):
    return {
        'type': MSG_CURSOR_UPDATE,
        'cursor_row': cursor_row,
        'cursor_col': cursor_col
    }


def make_lock_request():
    return {'type': MSG_LOCK_REQUEST}


def make_lock_release():
    return {'type': MSG_LOCK_RELEASE}


def make_save_request():
    return {'type': MSG_SAVE_REQUEST}


def make_undo():
    return {'type': MSG_UNDO}

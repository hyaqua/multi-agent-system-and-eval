"""
server.py – Entry point.

Parses arguments, configures logging, creates the server with routes,
and starts serving.
"""

import argparse
import json
import logging
from http.server import ThreadingHTTPServer

from handler import RequestHandler
from router import Router
from storage import ItemStorage


# ---------------------------------------------------------------------------
# View functions – these receive the handler instance plus extracted params.
# ---------------------------------------------------------------------------

def list_items(handler: RequestHandler, path_params, query_params, body):
    storage: ItemStorage = handler.shared_storage
    if query_params:
        items = storage.filter_by_field(query_params)
    else:
        items = storage.get_all()
    handler._send_json(200, items)
    handler._log_request(200)


def get_item(handler: RequestHandler, path_params, query_params, body):
    storage: ItemStorage = handler.shared_storage
    item_id = int(path_params["id"])
    item = storage.get_by_id(item_id)
    if item is None:
        handler._send_error(404, "Not found")
        handler._log_request(404)
    else:
        handler._send_json(200, item)
        handler._log_request(200)


def create_item(handler: RequestHandler, path_params, query_params, body):
    storage: ItemStorage = handler.shared_storage
    if not isinstance(body, dict):
        handler._send_error(400, "Request body must be a JSON object")
        handler._log_request(400)
        return
    created = storage.add(body)
    body_bytes = json.dumps(created).encode("utf-8")
    handler.send_response(201)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Location", f"/items/{created['id']}")
    handler.send_header("Content-Length", str(len(body_bytes)))
    handler.end_headers()
    handler.wfile.write(body_bytes)
    handler._log_request(201)


def update_item(handler: RequestHandler, path_params, query_params, body):
    storage: ItemStorage = handler.shared_storage
    item_id = int(path_params["id"])
    if not isinstance(body, dict):
        handler._send_error(400, "Request body must be a JSON object")
        handler._log_request(400)
        return
    updated = storage.update(item_id, body)
    if updated is None:
        handler._send_error(404, "Not found")
        handler._log_request(404)
    else:
        handler._send_json(200, updated)
        handler._log_request(200)


def delete_item(handler: RequestHandler, path_params, query_params, body):
    storage: ItemStorage = handler.shared_storage
    item_id = int(path_params["id"])
    if storage.delete(item_id):
        handler.send_response(204)
        handler.send_header("Content-Length", "0")
        handler.end_headers()
        handler._log_request(204)
    else:
        handler._send_error(404, "Not found")
        handler._log_request(404)


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------


def build_router() -> Router:
    r = Router()
    r.add_route("GET", r"/items/?", list_items)
    r.add_route("GET", r"/items/(?P<id>\d+)/?", get_item)
    r.add_route("POST", r"/items/?", create_item)
    r.add_route("PUT", r"/items/(?P<id>\d+)/?", update_item)
    r.add_route("DELETE", r"/items/(?P<id>\d+)/?", delete_item)
    return r


def main():
    parser = argparse.ArgumentParser(description="REST API Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--data-file", type=str, default="items.json",
                        help="JSON file for persistence (default: items.json)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("server")

    storage = ItemStorage(file_path=args.data_file)
    router = build_router()

    # Inject shared instances into the handler class
    RequestHandler.shared_router = router
    RequestHandler.shared_storage = storage

    server = ThreadingHTTPServer(("0.0.0.0", args.port), RequestHandler)
    logger.info("Starting server on port %d (data: %s)", args.port, args.data_file)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()

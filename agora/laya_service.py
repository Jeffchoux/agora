"""Opt-in Mac companion, using its separately installed laya-coreml runtime."""

import argparse
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from agora.laya import QUESTIONS, private_token, suggestion, validate_brief


class LocalPredictor:
    def __init__(self, model_dir):
        model_dir = Path(model_dir)
        if not model_dir.is_absolute() or not model_dir.is_dir():
            raise ValueError("An existing absolute model directory is required")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        import laya_coreml

        self.agent = laya_coreml.load(
            str(model_dir), local_files_only=True, compute_units="cpu"
        )

    def __call__(self, brief):
        agent = self.agent
        state = brief.replace(agent.tok.mask_token, " ")
        tokens = agent.tok(state, add_special_tokens=False)["input_ids"]
        empty, _ = agent.prepare("", QUESTIONS)
        prepared, _ = agent.prepare(brief, QUESTIONS)
        expected = len(empty[0]["ids"]) + len(tokens)
        limit = min(1024, agent.cfg.get("max_len", 512), agent.shape["max_length"])
        if len(tokens) > 512 or expected > limit or len(prepared[0]["ids"]) != expected:
            raise ValueError("Brief exceeds the local model's token budget")
        result = agent.predict(brief, QUESTIONS)
        try:
            return suggestion(result["answers"]["specialty"]["choice"])
        except (KeyError, TypeError, ValueError):
            raise RuntimeError("Invalid Laya response") from None


def make_server(token, predict, port=18769):
    """Single-threaded server serializes inference and bounds pending sockets."""
    class Handler(BaseHTTPRequestHandler):
        server_version = "AgoraLaya"
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *_args):
            pass

        def respond(self, status, data):
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            self.close_connection = True

        def do_POST(self):
            # Authenticate before reading or decoding any brief.
            authorization = self.headers.get_all("Authorization", [])
            if len(authorization) != 1 or not hmac.compare_digest(
                authorization[0].encode("utf-8"), ("Bearer " + token).encode("ascii")
            ):
                return self.respond(401, {"error": "Credential required"})
            if self.path != "/suggest":
                return self.respond(404, {"error": "Not found"})
            lengths = self.headers.get_all("Content-Length", [])
            if (
                self.headers.get("Transfer-Encoding") is not None
                or len(lengths) != 1
                or len(lengths[0]) > 4
                or not lengths[0].isascii()
                or not lengths[0].isdigit()
                or not 1 <= int(lengths[0]) <= 8192
            ):
                return self.respond(400, {"error": "Invalid request"})
            try:
                length = int(lengths[0])
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError()
                brief = validate_brief(json.loads(body))
                result = predict(brief)
                if result != suggestion(result.get("category")):
                    raise RuntimeError()
            except (ValueError, UnicodeError):
                return self.respond(400, {"error": "Invalid or oversized brief"})
            except Exception:  # noqa: BLE001 — native model errors must not leak request data.
                return self.respond(503, {"error": "Local suggestion unavailable"})
            return self.respond(200, result)

    class Server(HTTPServer):
        request_queue_size = 4

        def handle_error(self, _request, _client_address):
            # Disconnected clients must not cause credential/body tracebacks.
            pass

    return Server(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--port", type=int, default=18769)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    try:
        token = private_token(args.token_file)
        predictor = LocalPredictor(args.model_dir)
        server = make_server(token, predictor, args.port)
    except Exception:  # noqa: BLE001 — optional native runtime failures get a generic diagnostic.
        parser.exit(1, "Laya unavailable: check the private token, local model and runtime.\n")
    with server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

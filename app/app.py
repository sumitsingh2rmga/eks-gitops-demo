import os
from flask import Flask, jsonify

app = Flask(__name__)
VERSION = os.getenv("APP_VERSION", "v1")


@app.get("/")
def home():
    return jsonify(message="hello from eks-gitops-demo", version=VERSION)


@app.get("/health")
def health():
    # Simulate a broken application release by returning HTTP 500 Internal Server Error
    return jsonify(status="error"), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
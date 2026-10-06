
import hmac
import os
import subprocess
import sys
from flask import Flask, request, abort

app = Flask(__name__)

# --- CONFIGURATION ---
# Generate a long random secret and export it as the WEBHOOK_SECRET environment variable.
# IMPORTANT: This secret MUST match the one you set in your GitHub webhook settings.
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')
if not WEBHOOK_SECRET:
    sys.exit('WEBHOOK_SECRET environment variable is required.')
# The path to your deployment script
DEPLOYMENT_SCRIPT_PATH = './deploy.sh'
# --- END CONFIGURATION ---

def is_valid_signature(signature, payload):
    """
    Validates the GitHub webhook signature.
    """
    if not signature:
        print("Signature missing!")
        return False

    secret_bytes = WEBHOOK_SECRET.encode('utf-8')
    payload_bytes = payload

    # Calculate the expected signature
    hasher = hmac.new(secret_bytes, payload_bytes, 'sha256')
    expected_signature = 'sha256=' + hasher.hexdigest()

    # Compare signatures securely
    return hmac.compare_digest(expected_signature, signature)

@app.route('/webhook', methods=['POST'])
def webhook():
    """
    The main webhook endpoint.
    """
    # Get the signature from the headers
    signature = request.headers.get('X-Hub-Signature-256')
    
    # Get the raw request body
    payload = request.data

    # Validate the signature
    if not is_valid_signature(signature, payload):
        abort(403, "Invalid signature.")

    # Check if it's a push to the main/master branch (optional but recommended)
    event = request.headers.get('X-GitHub-Event', 'ping')
    if event == 'push':
        payload_json = request.get_json()
        ref = payload_json.get('ref', '')
        if 'main' in ref or 'master' in ref:
            print("Valid push to main/master branch received. Triggering deployment...")
            try:
                # Ensure deploy.sh is executable
                # Run the deployment script using bash to avoid executable permission issues
                subprocess.run(['bash', DEPLOYMENT_SCRIPT_PATH], check=True, text=True, capture_output=True)
                print("Deployment script executed successfully.")
            except subprocess.CalledProcessError as e:
                print(f"Error during deployment script execution: {e.stderr}")
                return "Deployment script failed.", 500
            return "Deployment successful!", 200
        else:
            print(f"Ignoring push to non-default branch: {ref}")
            return "Push to non-default branch ignored.", 200

    return "Ping event received.", 200

if __name__ == '__main__':
    # Make sure to use a production-ready server like Gunicorn or Waitress in a real setup
    # For simplicity, we use Flask's built-in server here.
    # Listen on all interfaces on port 5000
    app.run(host='0.0.0.0', port=5000)

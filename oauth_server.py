from flask import Flask, request

app = Flask(__name__)

@app.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    if not code:
        return "Authorization failed: No code received.", 400
    
    return f"Authorization successful! Your code: {code}", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)

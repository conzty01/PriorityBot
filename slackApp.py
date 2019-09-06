from flask import Flask, request, jsonify
#import psycopg2
import os

app = Flask(__name__)
VERIFICATION_TOKEN = os.environ["VERIFICATION_TOKEN"]
#conn = psycopg2.connect(os.environ["DATABASE_URL"])

@app.route("/nextp", methods=["POST"])
def nextp():
    if request.form["token"] == VERIFICATION_TOKEN:
        print(request.form["command"])
        print(request.form["text"])
        return "Hello, Slack!"
    
    return "Denied", 401
    
@app.route("/", methods=["GET"])
def index():
    return "<h1>Hello, World!</h1>"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True)

    # curl localhost:5000/nextp -X POST
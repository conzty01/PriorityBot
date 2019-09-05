from flask import Flask, request
#import psycopg2
import os

app = Flask(__name__)
#conn = psycopg2.connect(os.environ["DATABASE_URL"])

@app.route("/nextp", methods=["POST"])
def nextp():
    print(request.get_json())
    return "Hello, Slack!"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True)

    # curl localhost:5000/nextp -X POST
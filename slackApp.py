from flask import Flask, request, jsonify
import threading
import time
#import psycopg2
import os

app = Flask(__name__)
VERIFICATION_TOKEN = os.environ["VERIFICATION_TOKEN"]
#conn = psycopg2.connect(os.environ["DATABASE_URL"])
"""
    /nextp Workflow:
        1) User uses slash command to send information about the next priority issue to PriorityBot
        2) PriorityBot sends message to group chat
            Message contains:
                A. Info provided from the user
        3) PriorityBot sends message to user up for P1/P2 and asks for confirmation (2 minute Timeout)
            If confirmed,
                A. PriorityBot acknowledges user confirmation
                B. Sends message to group chat informing of the next person up for P1/P2
            If denied,
                A. PriorityBot acknowledges user rejection
                B. Repeat step 3
            If timeout,
                A. PriorityBot sends timeout message to user
                B. Repeat step 3
            If all users pinged,
                A. PriorityBot sends @here message to group chat about the priority issue
"""

class PriorityThread(threading.Thread):

	def __init__(self, message, replyURL, senderID):
		super(PriorityThread, self).__init__()
		
		self.message = message
		self.replyURL = replyURL
		self.senderID = senderID

	def run(self):
		print("Starting PriorityThread")
		
		assigned = False
		while not assigned:
			assigned = True
			print("Working on PriorityThread!")
			time.sleep(5)
			print("PriorityThread Complete!")
			

	def pingUser(self,userID):
		pass

	def pingChannel(self,chnlID):
		pass

	def notifyNext(self,userID):
		pass

@app.route("/nextp", methods=["POST"])
def nextp():
	"""/nextp P1/P2 Ft. Worth cert issue. <@U4SCYHQUX|conzty01> connected but cannot see problem. Case #123123123"""

	if request.form["token"] == VERIFICATION_TOKEN:

		if request.form["command"] == '/nextp':
			
			rawText = request.form["text"]
			replyURL = request.form["response_url"]
			senderID = request.form["user_id"]

			# Create a new thread to handle the heavy lifting
			t = PriorityThread(rawText,replyURL,senderID)
			t.start()

			# Acknowledge the slash command
			return "Thank you! Your message has been received and will be sent out to the team!"

		if request.form["command"] == '/listp':
			return "1)  Jonathan Lewis\n2)  Austin Luther\n3)  Monica Zweibohmer\n  4)Shawn Pollard\netc..."

	return "Denied", 401

@app.route("/", methods=["GET"])
def index():
	return "<h1>Hello, World!</h1>"

if __name__ == "__main__":
	port = int(os.environ.get('PORT', 5000))
	app.run(debug=True)

	# curl localhost:5000/nextp -X POST


"""
[
	{
		"type": "section",
		"text": {
			"type": "mrkdwn",
			"text": "A P1/P2 has come in. See the details below:"
		}
	},
	{
		"type": "section",
		"fields": [
			{
				"type": "mrkdwn",
				"text": "*Type:*\nComputer (laptop)"
			},
			{
				"type": "mrkdwn",
				"text": "*When:*\nSubmitted Aut 10"
			},
			{
				"type": "mrkdwn",
				"text": "*Last Update:*\nMar 10, 2015 (3 years, 5 months)"
			},
			{
				"type": "mrkdwn",
				"text": "*Reason:*\nAll vowel keys aren't working."
			},
			{
				"type": "mrkdwn",
				"text": "*Specs:*\n\"Cheetah Pro 15\" - Fast, really fast\""
			}
		]
	},
	{
		"type": "actions",
		"elements": [
			{
				"type": "button",
				"text": {
					"type": "plain_text",
					"emoji": true,
					"text": "Approve"
				},
				"style": "primary",
				"value": "click_me_123"
			},
			{
				"type": "button",
				"text": {
					"type": "plain_text",
					"emoji": true,
					"text": "Deny"
				},
				"style": "danger",
				"value": "click_me_123"
			}
		]
	}
]

https://api.slack.com/tools/block-kit-builder?blocks=%5B%7B%22type%22%3A%22section%22%2C%22text%22%3A%7B%22type%22%3A%22mrkdwn%22%2C%22text%22%3A%22A%20P1%2FP2%20has%20come%20in.%20See%20the%20details%20below%3A%22%7D%7D%2C%7B%22type%22%3A%22section%22%2C%22fields%22%3A%5B%7B%22type%22%3A%22mrkdwn%22%2C%22text%22%3A%22*Type%3A*%5CnComputer%20(laptop)%22%7D%2C%7B%22type%22%3A%22mrkdwn%22%2C%22text%22%3A%22*When%3A*%5CnSubmitted%20Aut%2010%22%7D%2C%7B%22type%22%3A%22mrkdwn%22%2C%22text%22%3A%22*Last%20Update%3A*%5CnMar%2010%2C%202015%20(3%20years%2C%205%20months)%22%7D%2C%7B%22type%22%3A%22mrkdwn%22%2C%22text%22%3A%22*Reason%3A*%5CnAll%20vowel%20keys%20aren%27t%20working.%22%7D%2C%7B%22type%22%3A%22mrkdwn%22%2C%22text%22%3A%22*Specs%3A*%5Cn%5C%22Cheetah%20Pro%2015%5C%22%20-%20Fast%2C%20really%20fast%5C%22%22%7D%5D%7D%2C%7B%22type%22%3A%22actions%22%2C%22elements%22%3A%5B%7B%22type%22%3A%22button%22%2C%22text%22%3A%7B%22type%22%3A%22plain_text%22%2C%22emoji%22%3Atrue%2C%22text%22%3A%22Approve%22%7D%2C%22style%22%3A%22primary%22%2C%22value%22%3A%22click_me_123%22%7D%2C%7B%22type%22%3A%22button%22%2C%22text%22%3A%7B%22type%22%3A%22plain_text%22%2C%22emoji%22%3Atrue%2C%22text%22%3A%22Deny%22%7D%2C%22style%22%3A%22danger%22%2C%22value%22%3A%22click_me_123%22%7D%5D%7D%5D
"""
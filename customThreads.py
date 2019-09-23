import threading
import requests
import time

class PriorityThread(threading.Thread):

    def __init__(self, replyURL, payload, slackClient):
        super(PriorityThread, self).__init__()
        
        self.payload = payload
        self.replyURL = replyURL
        self.client = slackClient

    def run(self):
        print("Starting PriorityThread")

        assigned = False
        while not assigned:
            assigned = True
            print("Working on PriorityThread!")

            """d = {"token":'','types':'im'}
            r = requests.get("https://slack.com/api/conversations.list", params=d, verify=False)
            print(r.status_code)
            print(r.json())
            time.sleep(10)
            d5 = {"token":'',"user":"USLACKBOT"}
            r = requests.post("https://slack.com/api/auth.test",data=d5, json=d5, verify=False, headers={'Content-Type': 'application/json; charset=utf-8', })
            print(r.status_code)
            c = r.json()
            print(c)
            d2 = {"token":'',"channel":'C4KL3RD9T',"text":"Hello, World!","blocks":self.payload,"as_user":False}
            r = requests.post("https://slack.com/api/chat.postMessage",json=d2, verify=False)"""

            response = self.client.chat_postMessage(
                channel='D4RMZCVJ6',
                text='A high priority case has come in',
                blocks=self.payload
            )
            print(response["ok"])
            print(response)
            print("PriorityThread Complete!")

    def _sendToReplyURL():
        requests.post(self.replyURL, json=self.payload)

    def pingUser(self,userID):
        pass

    def pingChannel(self,chnlID):
        pass

    def notifyNext(self,userID):
        pass


class Message:
    """Base Message object which can generate a message payload"""
    
    def __init__(self,channel,username):
        self.channel = channel
        self.username = username
        self.timestamp = ""
        self.icon_emoji = ":robot_face:"
        self.blocks = []

    def getMessagePayload(self):
        return {
            "ts": self.timestamp,
            "channel": self.channel,
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "blocks": self.blocks
        }

    def getBlocks(self):
        return self.blocks

class PriorityMessage(Message):
    """Constructs a High Priority Case Notification message"""

    def __init__(self, channel, userName, msg):
        super().__init__(channel, "High Priority Case Notification")
        self.colors = {"orange":"#F4490C","purple":"#370761"}

        self.NOTIFICATION = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"A high priority case has come from {userName} with the following message:",
            }
        }

        self.DIVIDER_BLOCK = {"type": "divider"}

        self.MESSAGE_BLOCK = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": msg
            }
        }

        self.AD_ACTION_BLOCK = {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Accept"
                    },
                    "style": "primary",
                    "value": "Accept"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Deny"
                    },
                    "style": "danger",
                    "value": "Deny"
                }
            ]
        }

        self.blocks = [
            self.NOTIFICATION,
            self.DIVIDER_BLOCK,
            self.MESSAGE_BLOCK,
            self.AD_ACTION_BLOCK
        ]

    def getMessage(self):
        """Return the Message as provided"""
        return self.MESSAGE_BLOCK["text"]["text"]

class PriorityReply(PriorityMessage):
    """Constructs a High Priority Case reply message"""

    def __init__(self, channel, userName, msg, action):
        super().__init__(channel, userName, msg)

        AD_ACTION_BLOCK = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"You have elected to *{action}* the case"
            }
        }

        self.blocks[-1] = AD_ACTION_BLOCK


class ListMessage(Message):
    """Constructs a Tech Priority List message"""
    pass


if __name__ == '__main__':
    print(PriorityMessage("TEST CHANNEL", "Tyler Conzett", "TEST MESSAGE").getMessagePayload())
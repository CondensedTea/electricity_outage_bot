class MessageAlreadyPosted(Exception):
    pass


class MessageUpdateRequired(Exception):
    def __init__(self, date: str, time: str, message_id: int):
        self.new_date = date
        self.new_time = time
        self.message_id = message_id

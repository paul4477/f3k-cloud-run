import asyncio

class MessageAnnouncer:

    def __init__(self):
        
        self.listeners = []

    def listen(self):
        q = asyncio.Queue(maxsize=50)
        self.listeners.append(q)
        return q

    def announce(self, msg):
        for i in reversed(range(len(self.listeners))):
            try:
                self.listeners[i].put_nowait(msg)
            except asyncio.Full:
                del self.listeners[i]
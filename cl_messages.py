

class MessageAnnouncer:

    def __init__(self):
        
        self.listeners = []

    def listen(self):
        import queue
        q = queue.Queue(maxsize=50)
        self.listeners.append(q)
        return q

    def announce(self, msg):
        import queue
        for i in reversed(range(len(self.listeners))):
            try:
                self.listeners[i].put_nowait(msg)
            except queue.Full:
                del self.listeners[i]
import socket
from selectors import DefaultSelector, EVENT_WRITE, EVENT_READ

selector = DefaultSelector()
stopped = False
urls_todo = {'/', '/1', '/2', '/3', '/4', '/5', '/6', '/7', '/8', '/9'}


class Future:
    def __init__(self):
        self.result = None
        self._callbacks = []

    def add_done_callback(self, fn):
        self._callbacks.append(fn)

    def set_result(self, result):
        self.result = result
        for fn in self._callbacks:
            fn(self)

    def __iter__(self):
        yield self
        return self.result


def connect(sock, address):
    f = Future()
    sock.setblocking(False)
    try:
        sock.connect(address)
    except IOError:
        pass

    def on_connected():
        f.set_result(None)

    selector.register(sock.fileno(), EVENT_WRITE, on_connected)
    yield from f
    selector.unregister(sock.fileno())


def read(sock):
    f = Future()

    def on_readable():
        f.set_result(sock.recv(4096))

    selector.register(sock.fileno(), EVENT_READ, on_readable)
    chunk = yield from f
    selector.unregister(sock.fileno())
    return chunk


def read_all(sock):
    response = []
    chunk = yield from read(sock)
    while chunk:
        response.append(chunk)
        chunk = yield from read(sock)
    return b''.join(response)


class Crawler(object):
    def __init__(self, url):
        self.url = url
        self.response = b''

    def fetch(self):
        global stopped
        sock = socket.socket()
        yield from connect(sock, ('example.com', 80))
        get = 'GET {0} HTTP/1.0\r\nHost: example.com\r\n\r\n'.format(self.url)
        sock.send(get.encode('ascii'))
        self.response = yield from read_all(sock)
        urls_todo.remove(self.url)
        if not urls_todo:
            stopped = True


class Task:
    def __init__(self, coro):
        self.coro = coro  # line 95
        f = Future()
        f.set_result(None)
        self.step(f)

    def step(self, future):
        try:
            # send 进入 coro 执行，即 fetch，直到下次 yield
            # next_future 为 yield 返回的对象
            next_future = self.coro.send(future.result)
        except StopIteration:
            return
        next_future.add_done_callback(self.step)


def loop():
    while not stopped:
        events = selector.select()
        for event_key, enevt_mask in events:
            callback = event_key.data
            callback()


if __name__ == '__main__':
    import time
    start = time.time()
    for url in urls_todo:
        crawler = Crawler(url)
        Task(crawler.fetch())
    loop()
    print(time.time() - start)

# ------------------------
# Tom Aarsen   - s1027401
# Bart Janssen - s4630270
# ------------------------

from threading import Lock

class BTCPSocket:
    # Base class of BTCPClientSocket and BTCPServerSocket
    def __init__(self, window, timeout, debug, _type):
        self._window = window
        self._timeout = timeout
        self._debug = debug
        self._type = _type
        # Store hidden state variable.
        # state is accessible via the property, which allows us to wrap every 
        # access and modification of `self.state` with a mutex.
        self._state = 0

        self.s_mutex = Lock()
    
    def print(self, string: str):
        if self._debug:
            print(string)

    @property
    def state(self):
        with self.s_mutex:
            return self._state

    @state.setter
    def state(self, value):
        with self.s_mutex:
            if value != self._state:
                self.print(f"Setting {self._type} state to {value}.")
                self._state = value


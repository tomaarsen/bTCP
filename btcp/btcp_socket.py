class BTCPSocket:
    def __init__(self, window, timeout):
        self._window = window
        self._timeout = timeout
        self._state = 0
    
    @property
    def state(self):
        #print("Accessing state")
        return self._state

    @state.setter
    def state(self, value):
        print(f"Setting state to {value}.")
        self._state = value


from nmigen import (
        Elaboratable,
        Signal
)

class CommandTask(Elaboratable):
    def __init__(self):
        self.start = Signal()
        self.done = Signal()

        self.tx_data = Signal(8)
        self.tx_rdy = Signal()
        self.tx_ack = Signal()


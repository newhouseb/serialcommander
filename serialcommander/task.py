from nmigen import (
        Elaboratable,
        Signal
)

class CommandTask(Elaboratable):
    """This is the base class that all commands should impplement"""
    def __init__(self):
        # This goes high for at least once cycle when the Task has control of the TX ports
        self.start = Signal()
        # This signals when the Task has completed and TX port control can be surrendered
        self.done = Signal()

        # The character to transmit
        self.tx_data = Signal(8)
        # Put high when the task has data to send
        self.tx_rdy = Signal()
        # Goes high when the UART has sent the most recent byte
        self.tx_ack = Signal()


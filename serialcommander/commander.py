import math

from nmigen import *
from nmigen.sim import Simulator

from serialcommander.task import CommandTask


class Commander(Elaboratable):
    def __init__(self, uart, commands):
        self.uart = uart
        self.commands = commands

    def elaborate(self, platform):
        m = Module()
        
        activeCommand = Signal(range(len(self.commands) + 1))
        activeStart = Signal()
        activeDone = Signal()

        indexToMod = {} # Command index to submod
        letterToIndex = {}

        i = 1
        for k, submod in self.commands.items():
            setattr(m.submodules, 'command' + k, submod)
            indexToMod[i] = submod
            letterToIndex[k] = i
            i += 1

        with m.Switch(activeCommand):
            with m.Case(0):
                m.d.comb += [
                    self.uart.tx_data.eq(0),
                    self.uart.tx_rdy.eq(0),
                    activeDone.eq(0),
                ]
                for _, submod in self.commands.items():
                    submod.start.eq(0)
                    submod.tx_ack.eq(0)

            for i in range(1, len(self.commands) + 1):
                with m.Case(i):
                    m.d.comb += [
                        self.uart.tx_data.eq(indexToMod[i].tx_data),
                        self.uart.tx_rdy.eq(indexToMod[i].tx_rdy),
                        indexToMod[i].tx_ack.eq(self.uart.tx_ack),

                        indexToMod[i].start.eq(activeStart),
                        activeDone.eq(indexToMod[i].done),
                    ]

        with m.FSM() as fsm:
            with m.State("WAIT_MESSAGE"):
                m.d.sync += self.uart.rx_ack.eq(0)
                with m.If(self.uart.rx_rdy):
                    m.next = "READ_CHAR"

            with m.State("READ_CHAR"):
                m.d.sync += self.uart.rx_ack.eq(1)
                with m.Switch(self.uart.rx_data):
                    for k, i in letterToIndex.items():
                        with m.Case(ord(k)):
                            m.d.sync += activeCommand.eq(i)
                            m.next = "RUN_TASK_START"
                    with m.Default():
                        m.next = "WAIT_MESSAGE"

            with m.State("RUN_TASK_START"):
                m.d.sync += self.uart.rx_ack.eq(0)
                m.d.sync += activeStart.eq(1)
                m.next = "RUN_TASK_WAIT"

            with m.State("RUN_TASK_WAIT"):
                m.d.sync += activeStart.eq(0)
                done_last = Signal()
                m.d.sync += done_last.eq(activeDone)
                with m.If(activeDone & ~done_last):
                    m.d.sync += activeCommand.eq(0)
                    m.next = "WAIT_MESSAGE"

        return m

if __name__ == '__main__':
    pass

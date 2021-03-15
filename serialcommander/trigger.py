
from nmigen import (
        Elaboratable,
        Module,
        Signal
)
from nmigen.build import Platform

from serialcommander.task import CommandTask

class Trigger(CommandTask):
    def __init__(self):
        super().__init__()
        self.output = Signal()

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        start_last = Signal()
        m.d.sync += start_last.eq(self.start)

        with m.FSM() as fsm:
            with m.State("IDLE"):
                with m.If(self.start & ~start_last):
                    m.d.sync += self.output.eq(1)
                    m.d.sync += self.done.eq(1)
                    m.next = "FINISH"
            with m.State("FINISH"):
                    m.d.sync += self.output.eq(0)
                    m.d.sync += self.done.eq(0)
                    m.next = "IDLE"

        return m

def test_trigger():
    from nmigen.sim import Simulator
    from serialcommander.commander import Commander
    from serialcommander.uart import UART

    class TestRig(Elaboratable):
        def elaborate(self, platform: Platform) -> Module:
            m = Module()

            self.trigger = Trigger()
            self.uart = UART(divisor=5)

            self.counter = Signal(3)
            with m.If(self.trigger.output):
                m.d.sync += self.counter.eq(self.counter + 1)
            
            m.submodules.uart = self.uart
            m.submodules.commander = Commander(self.uart, {
                '1': self.trigger
            })

            return m

    rig = TestRig()
    sim = Simulator(rig)
    sim.add_clock(1e-6)

    def wait(n):
        for i in range(n):
            yield

    def transmit_proc():
        assert (yield rig.counter) == 0

        # Increment 3 times
        for i in range(3):
            yield from rig.uart.test_send_char('1')
            yield from wait(5)

        assert (yield rig.counter) == 3

    sim.add_sync_process(transmit_proc)

    with sim.write_vcd("trigger.vcd"):
        sim.run()

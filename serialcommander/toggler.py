from nmigen import (
        Elaboratable,
        Module,
        Signal
)

from serialcommander.task import CommandTask

class Toggler(CommandTask):
    def __init__(self):
        super().__init__()
        self.output = Signal()

    def elaborate(self, platform):
        m = Module()

        start_last = Signal()
        m.d.sync += start_last.eq(self.start)

        with m.FSM() as fsm:
            with m.State("IDLE"):
                with m.If(self.start & ~start_last):
                    m.d.sync += self.output.eq(~self.output)
                    m.d.sync += self.done.eq(1)
                    m.next = "FINISH"
            with m.State("FINISH"):
                    m.d.sync += self.done.eq(0)
                    m.next = "IDLE"

        return m

def test_toggler():
    from nmigen.sim import Simulator
    from serialcommander.commander import Commander
    from serialcommander.uart import UART

    class TestRig(Elaboratable):
        def elaborate(self, platform):
            m = Module()

            self.toggler = Toggler()
            self.uart = UART(divisor=5)
            
            m.submodules.uart = self.uart
            m.submodules.commander = Commander(self.uart, {
                '1': self.toggler
            })

            return m

    rig = TestRig()
    sim = Simulator(rig)
    sim.add_clock(1e-6)

    def wait(n):
        for i in range(n):
            yield

    def transmit_proc():
        # Assert the toggler is off
        assert not (yield rig.toggler.output)

        yield from rig.uart.test_send_char('1')
        yield from wait(4)
        assert (yield rig.toggler.output)

        yield from rig.uart.test_send_char('1')
        yield from wait(4)
        assert not (yield rig.toggler.output)

    sim.add_sync_process(transmit_proc)

    with sim.write_vcd("toggler.vcd", "toggler.gtkw"):
        sim.run()

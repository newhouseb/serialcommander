import sys
import select
import termios
import tty

from nmigen import *
from nmigen.build import Platform

from nmigen.sim import Simulator
from serialcommander.commander import Commander
from serialcommander.uart import UART
from serialcommander.printer import DecimalSignalPrinter
from serialcommander.trigger import Trigger

if __name__ == '__main__':
    class TestRig(Elaboratable):
        def elaborate(self, platform: Platform) -> Module:
            m = Module()

            counter = Signal(8)
            increment = Trigger()
            decrement = Trigger()
            
            self.printer = DecimalSignalPrinter(counter)

            with m.If(increment.output):
                m.d.sync += counter.eq(counter + 1)
            with m.Elif(decrement.output):
                m.d.sync += counter.eq(counter - 1)
                
            self.uart = UART(divisor=5)
            m.submodules.uart = self.uart
            m.submodules.commander = Commander(self.uart, {
                '\n': self.printer,
                '+': increment,
                '-': decrement
            })

            return m

    rig = TestRig()
    sim = Simulator(rig)
    sim.add_clock(1e-6)

    def playground_proc():
        while True:
            if select.select([sys.stdin.fileno()], [], [], 0.0)[0]:
                c = sys.stdin.read(1)
                # Note that on a real device there is no echo unless you
                # configure it client-side in your serial terminal
                print(c, end='', flush=True)
                yield from rig.uart.test_send_char(c)

            if not (yield rig.uart.tx_o):
                print((yield from rig.uart.test_receive_char()), end='', flush=True)

            yield

    sim.add_sync_process(playground_proc)

    tattr = termios.tcgetattr(sys.stdin.fileno())
    tty.setcbreak(sys.stdin.fileno(), termios.TCSANOW)

    with sim.write_vcd("playground.vcd"):
        sim.run()

import math

from nmigen import (
        Cat,
        Elaboratable,
        Memory,
        Module,
        Mux,
        Signal
)
from nmigen.build import Platform

from serialcommander.task import CommandTask

class TextMemoryPrinter(CommandTask):
    """Prints a null terminated ASCII string with a trailing newline"""
    def __init__(self, mem: Memory, length: int):
        super().__init__()
        
        self.mem = mem
        self.length = length

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        m.submodules.r_port = r_port = self.mem.read_port()

        print_newline = Signal()

        m_idx = Signal(range(self.length + 1))
        m.d.comb += r_port.addr.eq(m_idx)
        m.d.comb += self.tx_data.eq(Mux(print_newline, ord('\n'), r_port.data))

        start_last = Signal()
        m.d.sync += start_last.eq(self.start)

        with m.FSM() as fsm:
            with m.State("IDLE"):
                m.d.sync += [
                    self.done.eq(0),
                    print_newline.eq(0)
                ]
                with m.If(self.start & ~start_last):
                    m.next = "FETCH"
            with m.State("FETCH"):
                # Just waiting for the memory to fetch
                m.next = "SEND"
            with m.State("SEND"):
                # Terminate on zero a la C-style strings
                with m.If(self.tx_data == 0 & ~print_newline):
                    m.d.sync += print_newline.eq(1)
                with m.Else():
                    # Tell the UART we're ready
                    m.d.sync += self.tx_rdy.eq(1)
                    m.next = "WAIT_ACK_DOWN"
            with m.State("WAIT_ACK_DOWN"):
                # Wait for the ack to go low (indicating that it's working)
                with m.If(self.tx_ack == 0):
                    m.next = "WAIT_ACK_UP"
            with m.State("WAIT_ACK_UP"):
                # Wait for the ack to go high (indicating it's done),
                # then increment the message index
                m.d.sync += self.tx_rdy.eq(0)
                with m.If(self.tx_ack):
                    with m.If(print_newline | (m_idx == (self.length - 1))):
                        m.next = "IDLE"
                        m.d.sync += m_idx.eq(0)
                        m.d.sync += self.done.eq(1)
                    with m.Else():
                        m.next = "FETCH"
                        m.d.sync += m_idx.eq(m_idx + 1)

        return m

class BinarySignalPrinter(CommandTask):
    """Prints a signal in binary with LSB first"""
    def __init__(self, signal: Signal):
        super().__init__()
        
        self.signal = signal 
        self.digits = len(signal)

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        snapshot = Signal(len(self.signal))
        digit = Signal(range(self.digits))
        char = Signal(8)

        start_last = Signal()
        m.d.sync += start_last.eq(self.start)

        m.d.comb += self.tx_data.eq(char)

        with m.FSM() as fsm:
            with m.State("IDLE"):
                m.d.sync += self.done.eq(0)
                with m.If(self.start & ~start_last):
                    m.d.sync += [
                        snapshot.eq(self.signal),
                        digit.eq(0),
                        char.eq(ord('0'))
                    ]
                    m.next = "SEND"
            with m.State("SEND"):
                with m.If(snapshot[0]):
                    m.d.sync += [
                        char.eq(ord('1'))
                    ]
                with m.Else():
                    m.d.sync += [
                        char.eq(ord('0'))
                    ]
                m.d.sync += self.tx_rdy.eq(1)
                m.next = "WAIT_ACK_DOWN"
            with m.State("WAIT_ACK_DOWN"):
                # Wait for the ack to go low (indicating that it's working)
                with m.If(self.tx_ack == 0):
                    m.next = "WAIT_ACK_UP"
            with m.State("WAIT_ACK_UP"):
                # Wait for the ack to go high (indicating it's done),
                # then process the next digit
                m.d.sync += self.tx_rdy.eq(0)
                with m.If(self.tx_ack):
                    with m.If(digit < self.digits - 1):
                        m.d.sync += [
                            snapshot.eq(Cat(snapshot[1:], 0)),
                            digit.eq(digit + 1),
                        ]
                        m.next = "SEND"
                    with m.Else():
                        m.d.sync += self.done.eq(1)
                        m.next = "IDLE"

        return m

class BinaryMemoryPrinter(CommandTask):
    """Prints words from a Memory instance with LSB first."""

    def __init__(self, mem: Memory, width: int, length: int):
        super().__init__()
        
        self.mem = mem
        self.width = width
        self.length = length

    def elaborate(self, platform: Platform) -> Module:
        m = Module()
        m.submodules.r_port = r_port = self.mem.read_port()

        m_idx = Signal(range(self.length + 1))
        b_idx = Signal(range(self.width + 1)) 

        m.d.comb += r_port.addr.eq(m_idx)
        with m.If((r_port.data & (1 << b_idx)) > 0):
            m.d.comb += self.tx_data.eq(ord('1'))
        with m.Else():
            m.d.comb += self.tx_data.eq(ord('0'))

        start_last = Signal()
        m.d.sync += start_last.eq(self.start)

        with m.FSM() as fsm:
            with m.State("IDLE"):
                m.d.sync += self.done.eq(0)
                with m.If(self.start & ~start_last):
                    m.next = "FETCH"
            with m.State("FETCH"):
                # Just waiting for the memory to fetch
                m.next = "SEND"
            with m.State("SEND"):
                # Tell the UART we're ready
                m.d.sync += self.tx_rdy.eq(1)
                m.next = "WAIT_ACK_DOWN"
            with m.State("WAIT_ACK_DOWN"):
                # Wait for the ack to go low (indicating that it's working)
                with m.If(self.tx_ack == 0):
                    m.next = "WAIT_ACK_UP"
            with m.State("WAIT_ACK_UP"):
                # Wait for the ack to go high (indicating it's done),
                # then increment the message index
                m.d.sync += self.tx_rdy.eq(0)
                with m.If(self.tx_ack):
                    with m.If((m_idx == (self.length - 1)) & (b_idx == (self.width - 1))):
                        m.next = "IDLE"
                        m.d.sync += m_idx.eq(0)
                        m.d.sync += b_idx.eq(0)
                        m.d.sync += self.done.eq(1)
                    with m.Else():
                        with m.If(b_idx == (self.width - 1)):
                            m.d.sync += m_idx.eq(m_idx + 1)
                            m.d.sync += b_idx.eq(0)
                            m.next = "FETCH"
                        with m.Else():
                            m.d.sync += b_idx.eq(b_idx + 1)
                            m.next = "SEND"

        return m

class DecimalSignalPrinter(CommandTask):
    """Prints a Signal in decimal with leading zeros so that any valid value has the same length"""

    def __init__(self, signal: Signal):
        super().__init__()
        
        self.signal = signal 
        self.digits = math.ceil(math.log(2**len(signal))/math.log(10))

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        snapshot = Signal(len(self.signal))
        digit = Signal(range(self.digits))
        char = Signal(8)
        base = Signal(len(self.signal))
        baseExp = Signal(range(self.digits))

        start_last = Signal()
        m.d.sync += start_last.eq(self.start)

        m.d.comb += self.tx_data.eq(char)

        with m.FSM() as fsm:
            with m.State("IDLE"):
                m.d.sync += self.done.eq(0)
                with m.If(self.start & ~start_last):
                    m.d.sync += [
                        snapshot.eq(self.signal),
                        digit.eq(self.digits - 1),
                        base.eq(1),
                        baseExp.eq(0),
                        char.eq(ord('0'))
                    ]
                    m.next = "MAKE_BASE"
            with m.State("MAKE_BASE"):
                # Multiply the base by 10 until we get to the right
                # base fo rthe given digit
                with m.If(baseExp < digit):
                    m.d.sync += [
                        base.eq((base << 3) + (base << 1)),
                        baseExp.eq(baseExp + 1)
                    ]
                with m.Else():
                    m.next = "COUNTDOWN"
            with m.State("COUNTDOWN"):
                # If the base is greater than what's left
                # print this digit
                with m.If(snapshot < base):
                    m.next = "SEND"
                with m.Else():
                    m.d.sync += [
                        snapshot.eq(snapshot - base),
                        char.eq(char + 1),
                    ]
            with m.State("SEND"):
                # Tell the UART we're ready
                m.d.sync += self.tx_rdy.eq(1)
                m.next = "WAIT_ACK_DOWN"
            with m.State("WAIT_ACK_DOWN"):
                # Wait for the ack to go low (indicating that it's working)
                with m.If(self.tx_ack == 0):
                    m.next = "WAIT_ACK_UP"
            with m.State("WAIT_ACK_UP"):
                # Wait for the ack to go high (indicating it's done),
                # then process the next digit
                m.d.sync += self.tx_rdy.eq(0)
                with m.If(self.tx_ack):
                    with m.If(digit > 0):
                        m.d.sync += [
                                digit.eq(digit - 1),
                                base.eq(1),
                                baseExp.eq(0),
                                char.eq(ord('0'))
                            ]
                        m.next = "MAKE_BASE"
                    with m.Else():
                        m.d.sync += self.done.eq(1)
                        m.next = "IDLE"

        return m

def test_text_memory_printer():
    from nmigen.sim import Simulator
    from serialcommander.commander import Commander
    from serialcommander.uart import UART

    message = "Hello World\0"

    class TestRig(Elaboratable):
        def elaborate(self, platform: Platform) -> Module:
            m = Module()

            self.printer = TextMemoryPrinter(Memory(width=8,
                                                    depth=len(message), 
                                                    init=[ord(c) for c in message]),
                                               length=len(message))
            self.uart = UART(divisor=5)
            
            m.submodules.uart = self.uart
            m.submodules.commander = Commander(self.uart, {
                '1': self.printer
            })

            return m

    rig = TestRig()
    sim = Simulator(rig)
    sim.add_clock(1e-6)

    def transmit_proc():
        yield from rig.uart.test_send_char('1')
        assert (yield from rig.uart.test_expect_string(message.replace('\0','\n')))

    sim.add_sync_process(transmit_proc)

    with sim.write_vcd("text_memory_printer.vcd"):
        sim.run()

def test_decimal_signal_printer():
    from nmigen.sim import Simulator
    from serialcommander.commander import Commander
    from serialcommander.uart import UART

    class TestRig(Elaboratable):
        def elaborate(self, platform: Platform) -> Module:
            m = Module()

            sig = Signal(8, reset=128)

            self.printer = DecimalSignalPrinter(sig)
            self.uart = UART(divisor=5)
            
            m.submodules.uart = self.uart
            m.submodules.commander = Commander(self.uart, {
                '1': self.printer
            })

            return m

    rig = TestRig()
    sim = Simulator(rig)
    sim.add_clock(1e-6)

    def transmit_proc():
        yield from rig.uart.test_send_char('1')
        assert (yield from rig.uart.test_expect_string('128'))

    sim.add_sync_process(transmit_proc)

    with sim.write_vcd("decimal_signal_printer.vcd"):
        sim.run()

def test_binary_memory_printer():
    from nmigen.sim import Simulator
    from serialcommander.commander import Commander
    from serialcommander.uart import UART

    class TestRig(Elaboratable):
        def elaborate(self, platform: Platform) -> Module:
            m = Module()

            self.printer = BinaryMemoryPrinter(Memory(width=4, depth=4, init=[0b0001, 0b0110, 0b1001, 0b1000]),
                                               width=4,
                                               length=4)
            self.uart = UART(divisor=5)
            
            m.submodules.uart = self.uart
            m.submodules.commander = Commander(self.uart, {
                '1': self.printer
            })

            return m

    rig = TestRig()
    sim = Simulator(rig)
    sim.add_clock(1e-6)

    def transmit_proc():
        yield from rig.uart.test_send_char('1')
        assert (yield from rig.uart.test_expect_string('1000011010010001'))

    sim.add_sync_process(transmit_proc)

    with sim.write_vcd("binary_memory_printer.vcd"):
        sim.run()

def test_binary_signal_printer():
    from nmigen.sim import Simulator
    from serialcommander.commander import Commander
    from serialcommander.uart import UART

    class TestRig(Elaboratable):
        def elaborate(self, platform: Platform) -> Module:
            m = Module()

            sig = Signal(5, reset=0b10101)

            self.printer = BinarySignalPrinter(sig)
            self.uart = UART(divisor=5)
            
            m.submodules.uart = self.uart
            m.submodules.commander = Commander(self.uart, {
                '1': self.printer
            })

            return m

    rig = TestRig()
    sim = Simulator(rig)
    sim.add_clock(1e-6)

    def transmit_proc():
        yield from rig.uart.test_send_char('1')
        assert (yield from rig.uart.test_expect_string('10101'))

    sim.add_sync_process(transmit_proc)

    with sim.write_vcd("binary_signal_printer.vcd"):
        sim.run()

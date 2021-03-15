from nmigen import *

class UART(Elaboratable):
    """
    Parameters
    ----------
    divisor : int
        Set to ``round(clk-rate / baud-rate)``.
        E.g. ``12e6 / 115200`` = ``104``.
    """
    def __init__(self, divisor, data_bits=8):
        assert divisor >= 4

        self.data_bits = data_bits
        self.divisor   = divisor

        self.tx_o    = Signal()
        self.rx_i    = Signal()

        self.tx_data = Signal(data_bits)
        self.tx_rdy  = Signal()
        self.tx_ack  = Signal()

        self.rx_data = Signal(data_bits)
        self.rx_err  = Signal()
        self.rx_ovf  = Signal()
        self.rx_rdy  = Signal()
        self.rx_ack  = Signal()

    def elaborate(self, platform):
        m = Module()

        tx_phase = Signal(range(self.divisor))
        tx_shreg = Signal(1 + self.data_bits + 1, reset=-1)
        tx_count = Signal(range(len(tx_shreg) + 1))

        m.d.comb += self.tx_o.eq(tx_shreg[0])
        with m.If(tx_count == 0):
            m.d.comb += self.tx_ack.eq(1)
            with m.If(self.tx_rdy):
                m.d.sync += [
                    tx_shreg.eq(Cat(C(0, 1), self.tx_data, C(1, 1))),
                    tx_count.eq(len(tx_shreg)),
                    tx_phase.eq(self.divisor - 1),
                ]
        with m.Else():
            with m.If(tx_phase != 0):
                m.d.sync += tx_phase.eq(tx_phase - 1)
            with m.Else():
                m.d.sync += [
                    tx_shreg.eq(Cat(tx_shreg[1:], C(1, 1))),
                    tx_count.eq(tx_count - 1),
                    tx_phase.eq(self.divisor - 1),
                ]

        rx_phase = Signal(range(self.divisor))
        rx_shreg = Signal(1 + self.data_bits + 2, reset=-1)
        rx_count = Signal(range(len(rx_shreg) + 1))

        m.d.comb += self.rx_data.eq(rx_shreg[1:-1])
        with m.If(rx_count == 0):
            m.d.comb += self.rx_err.eq(~(~rx_shreg[0] & rx_shreg[-1]))
            with m.If(~self.rx_i):
                with m.If(self.rx_ack | ~self.rx_rdy):
                    m.d.sync += [
                        self.rx_rdy.eq(0),
                        self.rx_ovf.eq(0),
                        rx_count.eq(len(rx_shreg)),
                        rx_phase.eq(self.divisor // 2),
                    ]
                with m.Else():
                    m.d.sync += self.rx_ovf.eq(1)
            with m.If(self.rx_ack):
                m.d.sync += self.rx_rdy.eq(0)
        with m.Else():
            with m.If(rx_phase != 0):
                m.d.sync += rx_phase.eq(rx_phase - 1)
            with m.Else():
                m.d.sync += [
                    rx_shreg.eq(Cat(rx_shreg[1:], self.rx_i)),
                    rx_count.eq(rx_count - 1),
                    rx_phase.eq(self.divisor - 1),
                ]
                with m.If(rx_count == 1):
                    m.d.sync += self.rx_rdy.eq(1)

        return m

    def test_send_char(self, char):
        char = ord(char)
        print("Sending ", bin(char))

        # Start bit
        yield self.rx_i.eq(0)
        for i in range(self.divisor):
            yield 

        # Data bits
        for i in range(8):
            yield self.rx_i.eq(1 if ((1 << i) & char) else 0)
            for i in range(self.divisor):
                yield 

        # Stop bit
        yield self.rx_i.eq(0)
        for i in range(self.divisor):
            yield 

        # Put things back high
        yield self.rx_i.eq(1)
        for i in range(self.divisor):
            yield 

    def test_receive_char(self):
        # Wait for signal to go low
        while True:
            if (yield self.tx_o) == 0:
                print ("Receiving")
                break
            yield

        # Wait for half the divisor to get to the
        # center of the bit
        for i in range(self.divisor//2):
            yield

        # Read each bit
        out = 0
        for i in range(8):
            for _ in range(self.divisor):
                yield
            if (yield self.tx_o):
                out += (1 << i)

        # Don't care about stop bit
        for i in range(self.divisor):
            yield

        return chr(out)

    def test_expect_string(self, string):
        for c in string:
            r = yield from self.test_receive_char()
            if r != c:
                raise Exception("Expected {} but got {}".format(c, r))
        return True

def test_uart_loopback():
    from nmigen.sim import Simulator, Passive

    class TestRig(Elaboratable):
        def elaborate(self, platform):
            m = Module()

            m.submodules.uart = uart = UART(divisor=5)
            self.uart = uart

            m.d.comb += [
                uart.rx_i.eq(uart.tx_o),
            ]

            return m

    rig = TestRig()
    sim = Simulator(rig)
    sim.add_clock(1e-6)

    def transmit_proc():
        test_byte = 0x72

        # Assert that TX is caught up and nothing is
        # waiting on RX
        assert (yield rig.uart.tx_ack)
        assert not (yield rig.uart.rx_rdy)

        # Send a byte and strobe that we're ready
        yield rig.uart.tx_data.eq(test_byte)
        yield rig.uart.tx_rdy.eq(1)
        yield
        yield rig.uart.tx_rdy.eq(0)
        yield

        # The data transmission isn't instant so ensure
        # we're not told otherwise
        assert not (yield rig.uart.tx_ack)

        # Wait for the data to be send
        for _ in range(rig.uart.divisor * 12): yield

        # Assert that we're acked and ready to go
        assert (yield rig.uart.tx_ack)
        assert (yield rig.uart.rx_rdy)
        assert not (yield rig.uart.rx_err)

        # Assert that the data is what we sent
        assert (yield rig.uart.rx_data) == test_byte

        # Acknowledge the read
        yield rig.uart.rx_ack.eq(1)
        yield

    sim.add_sync_process(transmit_proc)

    with sim.write_vcd("uart.vcd", "uart.gtkw"):
        sim.run()

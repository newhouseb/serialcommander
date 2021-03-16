# serialcommander
## A small, convenient way to add a CLI to your digital logic

`serialcommander` is a small nmigen tool that executes various 'tasks' when sent various characters over a serial port/UART.

## Quick Example

Let's say you want to test a counter that can be incremented and decremented on real hardware and read out its value. 

```python
# At the top of your module
from serialcommander.commander import Commander
from serialcommander.uart import UART
from serialcommander.printer import DecimalSignalPrinter
from serialcommander.trigger import Trigger

# This is normally inside of an Elaboratable's elaborate(self, platform) method
# and assumes m = Module()

# Some state
counter = Signal(8)

# Command Task
increment = Trigger()
decrement = Trigger()
printer = DecimalSignalPrinter(counter)

# If either of the triggers fire, increment or decrement
with m.If(increment.output):
    m.d.sync += counter.eq(counter + 1)
with m.Elif(decrement.output):
    m.d.sync += counter.eq(counter - 1)
    
# Instantiate the Commander and map characters to tasks
# Replace "5" with int(clock rate / baud rate)
uart = UART(divisor=5) 
m.submodules.uart = suart
m.submodules.commander = Commander(uart, {
    '\n': printer,
    '+': increment,
    '-': decrement
})

# Connect the UART ports to the real pins
m.d.comb += [
    platform.request('tx').eq(uart.tx_o),
    uart.rx_i.eq(platform.request('rx'))
]
```

If you build this on real hardware and test it with a serial console, you will see the following (after hitting enter and + and - numerous times):

```
000++++
004--
002-++
003
003
```

Note that this is echoing the characters you send, but most terminals don't do this by default.

## Things I have used this for

- Testing various SERDES configurations where I needed to read out sample data coming in 5gbps. By writing that data first into memory (deserialized to 250mhz), I could read out chunks of it via `serialcommander` for further analysis.
- Testing an asynchronous gray code counter by writing clocked values into memory (at the default clock rate), later read out and verified with `BinaryMemoryPrinter`
- I almost always use a `Toggler` connected to an LED to verify I've set up my UART correctly.
- When testing my bluetooth demodulator, I used `DecimalSignalPrinter` to measure the average magnitude of I&Q channels sampled from a test signal.

## Included "Tasks"

- **`Trigger`:** Sets a signal high for one cycle
- **`Toggle`:** Toggles a signal from high to low
- **`TextMemoryPrinter`:** Prints a null-terminated string from Memory.
- **`BinaryMemoryPrinter`:** Prints words in a Memory in binary.
- **`BinarySignalPrinter`:** Prints a signal's value in binary.
- **`DecimalSignalPrinter`:** Prints a signal's value in decimal.

## Motivation

Often times when I'm working on a component in a digital design, I need a way to read out values and twiddle bits. 

The "traditional" way to do this would be to hook up a button and debounce it or set up LEDs for readout. Couple issues with this:

- It's kind of a pain to wire up random buttons, remember what they do and debounce the specific button you happen to use. My dev boards are often on the other side of my desk, which doesn't help.
- I often need to read out a multi-bit value once per clock cycle for a short period time. One could use a ton of parallel pins and a logic analyzer but why rely on spaghetti when you can get away without it?

I suppose with a full CPU you could get a lot more introspection, but I suspect that would slow down synthesis times and lengthen one's iteration cycle (especially on Xilinx platforms). Also you end up writing a ton more glue than you nead just to read some bits from BRAM.

## Setup

The only true dependency is nmigen, which I typically run from the HEAD on github. I'd suggest you run things in a venv:

```
python3 -m venv env
. env/bin/activate
```

And then install from github nmigen and this pacakge:

```
pip install git+https://github.com/nmigen/nmigen
pip install git+https://github.com/newhouseb/serialcommander
```

To test that everything without, there's an included playground that can be run with no hardware that explores the example above (on WSL on Windows, Linux or MacOS only):

```
python -m serialcommander.playground
```

This will emulate a serial console so you can type '+', '-' or (enter) to play around.

To put things on real hardware, that might look something like this (note that it's targeting my TE0714 board which is fairly uncommon, board definition can be found at http://github.com/newhouseb/boards). This example uses 44 LUTs, so pretty small.

```python
from boards.trenz import TE0714

from nmigen import *
from nmigen.build import *

from serialcommander.commander import Commander
from serialcommander.toggler import Toggler
from serialcommander.uart import UART

import sys
import os
import subprocess

class CommanderBlinky(Elaboratable):
    def elaborate(self, platform):
        m = Module()
        m.submodules.uart = uart = UART(int(25e6 / 115200))

        self.toggler = Toggler()
        m.submodules.commander = Commander(uart, {
            '1': self.toggler,
        })

        m.d.comb += platform.request('led').eq(self.toggler.output)

        m.d.comb += [
            platform.request('uart_tx').eq(uart.tx_o),
            uart.rx_i.eq(platform.request('uart_rx')),
        ]

        return m

TE0714.resources += [
    Resource("uart_rx", 0, Pins("R13", dir="i"), Attrs(IOSTANDARD="LVCMOS33")),
    Resource("uart_tx", 0, Pins("T13", dir="o"), Attrs(IOSTANDARD="LVCMOS33")),
]

if __name__ == '__main__':
    if len(sys.argv) == 1:
        TE0714().build(CommanderBlinky(), do_program=True)
    else:
        subprocess.check_call([
            'openocd',
            '-f', 'interface/jlink.cfg',
            '-f', 'cpld/xilinx-xc7.cfg',
            '-c', 'adapter speed 4000',
            '-c', 'init',
            '-c', 'xc7_program xc7.tap',
            '-c', 'pld load 0 {}'.format('build\\top.bit'.replace("\\", "\\\\")),
            '-c', 'exit'
            ])
```


## Testing

I use pytest (`pip install pytest`) to run quick correctness tests. This uses the built-in nmigen simulator rather than cocotb / iverilog because, frankly, all this logic is pretty simple and efficient.

```
$ python -m pytest serialcommander/*.py
===================================== test session starts =====================================
platform linux -- Python 3.8.5, pytest-6.2.2, py-1.10.0, pluggy-0.13.1
rootdir: /home/ben/playground/serialcommander
collected 7 items

serialcommander/printer.py ....                                                         [ 57%]
serialcommander/toggler.py .                                                            [ 71%]
serialcommander/trigger.py .                                                            [ 85%]
serialcommander/uart.py .                                                               [100%]

====================================== 7 passed in 0.27s ======================================
```

## Contributing

Contributions welcome, although digital interfaces tend to be brittle so I want to be thoughtful about changing them.

Feedback also welcome, I've written a lot of software professionally but much less gateware.


## Future Ideas

I already use this in virtually every design I make, but in the future I could imagine:

- The UART printing terminal control characters so you can have persistent UI that indicates the state of a given signal.
- A websocket bridge to render logic-analyzer like UI in the browser

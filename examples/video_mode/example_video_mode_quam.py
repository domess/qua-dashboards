# %% Imports
from qua_dashboards.video_mode.dash_tools import *
import numpy as np
from matplotlib import pyplot as plt
from qua_dashboards.video_mode.voltage_parameter import *
from qua_dashboards.video_mode.sweep_axis import *
from qua_dashboards.video_mode.data_acquirers import *
from qua_dashboards.video_mode import scan_modes
from qua_dashboards.video_mode.inner_loop_actions import BasicInnerLoopActionQuam
from qua_dashboards.video_mode import VideoModeApp

from quam.components import (
    BasicQuAM,
    SingleChannel,
    InOutSingleChannel,
    pulses,
    StickyChannelAddon,
)

from qm import QuantumMachinesManager

import logging

# Update the logging configuration
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("hpack.hpack").setLevel(logging.WARNING)
logging.getLogger("matplotlib").setLevel(logging.WARNING)

# %% Create config and connect to QM
machine = BasicQuAM()  # Root QuAM object, serves as top-level container for all other QuAM components

# Add OPX output channel
machine.channels["ch1"] = SingleChannel(
    opx_output=("con1", 1),
    sticky=StickyChannelAddon(duration=1_000, digital=False),
    operations={"step": pulses.SquarePulse(amplitude=0.1, length=1000)},
)
# Add OPX output channel
machine.channels["ch2"] = SingleChannel(
    opx_output=("con1", 2),
    sticky=StickyChannelAddon(duration=1_000, digital=False),
    operations={"step": pulses.SquarePulse(amplitude=0.1, length=1000)},
)
readout_pulse = pulses.SquareReadoutPulse(
    id="readout", length=1000, amplitude=0.1
)
# Add OPX input/output channel
machine.channels["ch1_readout"] = InOutSingleChannel(
    opx_output=("con1", 3),
    opx_input=("con1", 1),
    intermediate_frequency=0,
    operations={"readout": readout1_pulse},
)

qmm = QuantumMachinesManager(host="192.168.8.4", cluster_name="Cluster_1")  # host, where to find QM orchestrator (server)
config = machine.generate_config() # Generate the QUA configuration from QuAM

# Open the quantum machine
# qm = qmm.open_qm(config, close_other_machines=True)


# %% Run OPXQuamDataAcquirer


x_offset = VoltageParameter(name="X Voltage Offset", initial_value=0.0)
y_offset = VoltageParameter(name="Y Voltage Offset", initial_value=0.0)
inner_loop_action = BasicInnerLoopActionQuam(
    x_element=machine.channels["ch1"],
    y_element=machine.channels["ch2"],
    readout_pulse=readout_pulse,
    ramp_rate=1_000,
    use_dBm=True,
)

scan_mode = scan_modes.SwitchRasterScan()
data_acquirer = OPXQuamDataAcquirer(
    qmm=qmm,
    machine=machine,
    qua_inner_loop_action=inner_loop_action,
    scan_mode=scan_mode,
    x_axis=SweepAxis("x", span=0.03, points=5, offset_parameter=x_offset),
    y_axis=SweepAxis("y", span=0.03, points=5, offset_parameter=y_offset),
    result_type="I",
)

# %% Test simulation
from qm import SimulationConfig

prog = data_acquirer.generate_program()
simulation_config = SimulationConfig(duration=10000)  # In clock cycles = 4ns
job = qmm.simulate(config, prog, simulation_config)
con1 = job.get_simulated_samples().con1

plt.figure(figsize=(10, 5))
con1.plot(analog_ports=["1", "2"])

plt.figure()
plt.plot(con1.analog["1"], con1.analog["2"])

plt.figure()
data_acquirer.scan_mode.plot_scan(
    data_acquirer.x_axis.points, data_acquirer.y_axis.points
)

# %% Run program and acquire data
data_acquirer.run_program()

results = data_acquirer.acquire_data()
print(f"Mean of results: {np.mean(np.abs(results))}")

# plt.figure()
# plt.pcolormesh(results)
# plt.colorbar()

# %% Run Video Mode
live_plotter = VideoModeApp(data_acquirer=data_acquirer, update_interval=1)
live_plotter.run(use_reloader=False)

# %% DEBUG: Generate QUA script
from qm import generate_qua_script

qua_script = generate_qua_script(data_acquirer.generate_program(), config)
print(qua_script)

# %% DEBUG: Simulate results
from qm import SimulationConfig

prog = data_acquirer.generate_program()
simulation_config = SimulationConfig(duration=20000)  # In clock cycles = 4ns
job = qmm.simulate(config, prog, simulation_config)
con1 = job.get_simulated_samples().con1

plt.figure(figsize=(10, 5))
con1.plot(analog_ports=["1", "2"])

plt.figure()
plt.plot(con1.analog["1"], con1.analog["2"])

plt.figure()
data_acquirer.scan_mode.plot_scan(
    data_acquirer.x_axis.points, data_acquirer.y_axis.points
)

# %% DEBUG:Validate readout inputs
results = []
for readout_pulse in [readout1_pulse, readout2_pulse]:
    inner_loop_action.readout_pulse = readout_pulse
    data_acquirer.program = data_acquirer.generate_program()
    data_acquirer.run_program()

    results.append(data_acquirer.acquire_data())

fig, axes = plt.subplots(1, 2, figsize=(10, 5))
for ax, result, ch in zip(axes, results, [1, 2]):
    im = ax.pcolormesh(result, rasterized=True)
    ax.set_title(f"Channel {ch}")
# %%

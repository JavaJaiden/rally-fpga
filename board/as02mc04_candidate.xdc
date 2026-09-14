# SPDX-License-Identifier: MIT
# Independently selected pin facts; NOT a board-revision guarantee.
# Source: fpganinja/taxi, commit 8567f91ef6bab46a261e98f5ab660731162605f5,
# src/cndm/board/AS02MC04/fpga/fpga.xdc (Alex Forencich / FPGA Ninja).
# GPIO assignments are a LAB WIRING CHOICE. Verify accessible J5 pads and VCCO.
set_property PACKAGE_PIN E18 [get_ports clk_100mhz_p]
set_property PACKAGE_PIN D18 [get_ports clk_100mhz_n]
set_property IOSTANDARD LVDS [get_ports {clk_100mhz_p clk_100mhz_n}]
create_clock -name system_clock -period 10.000 [get_ports clk_100mhz_p]
set_property PACKAGE_PIN A14 [get_ports uart_rx]
set_property PACKAGE_PIN E12 [get_ports uart_tx]
set_property PACKAGE_PIN B9 [get_ports led_hb]
set_property IOSTANDARD LVCMOS33 [get_ports {uart_rx uart_tx led_hb}]
set_property PULLUP true [get_ports uart_rx]
set_property SLEW SLOW [get_ports {uart_tx led_hb}]
set_property DRIVE 4 [get_ports {uart_tx led_hb}]
set_property CFGBVS GND [current_design]
set_property CONFIG_VOLTAGE 1.8 [current_design]
# Asynchronous serial and human-visible LED outputs have no external sample clock.
# Constrain their internal register-to-pad delay rather than inventing one.
set_max_delay -datapath_only 10.000 -to [get_ports {uart_tx led_hb}]

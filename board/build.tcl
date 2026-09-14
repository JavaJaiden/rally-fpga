# SPDX-License-Identifier: MIT
# vivado -mode batch -source board/build.tcl -tclargs VERIFIED_PART MODE [ACK]
# MODE: synth | implement | bitstream. Never programs hardware or writes flash.
if {$argc < 2 || $argc > 3} { error "Pass exact part, mode, and optional board-verification acknowledgment" }
lassign $argv part mode ack
if {![regexp {^xcku3p-ffvb676-[123]-[ei]$} $part]} { error "Expected an explicitly verified XCKU3P FFVB676 part" }
if {$mode ni {synth implement bitstream}} { error "Unknown mode" }
if {$mode ne "synth" && $ack ne "BOARD_PINOUT_AND_VOLTAGE_VERIFIED"} {
    error "Implementation requires physical pinout, voltage, power and clock verification"
}
set root [file normalize [file join [file dirname [info script]] ..]]
set out [file join $root out vivado_$mode]
file mkdir $out
create_project -in_memory -part $part
read_verilog -sv [file join $root rtl rally.sv]
read_verilog -sv [file join $root rtl uart.sv]
read_verilog -sv [file join $root board rally_as02mc04.sv]
read_xdc [file join $root board as02mc04_candidate.xdc]
synth_design -top rally_as02mc04 -part $part
# Cut ONLY the asynchronous pad-to-first-synchronizer stage. The synchronizer's
# internal stages and all datapaths remain timed. Fail if hierarchy no longer matches.
set first_stage [get_pins -hier -filter {NAME =~ *rx_receiver/rx_meta_reg/D}]
if {[llength $first_stage] != 1} { error "Cannot identify unique UART first-stage synchronizer; review constraints" }
set_false_path -from [get_ports uart_rx] -to $first_stage
report_utilization -file [file join $out utilization.rpt]
report_timing_summary -report_unconstrained -file [file join $out synthesis_timing.rpt]
report_cdc -details -file [file join $out cdc.rpt]
write_checkpoint -force [file join $out synthesized.dcp]
if {$mode eq "synth"} { puts "Synthesis only: no route, bitstream, or hardware evidence"; exit }
opt_design
place_design
phys_opt_design
route_design
report_timing_summary -report_unconstrained -file [file join $out routed_timing.rpt]
report_drc -file [file join $out drc.rpt]
check_timing -verbose -file [file join $out check_timing.rpt]
write_checkpoint -force [file join $out routed.dcp]
foreach delay {max min} {
    set path [get_timing_paths -delay_type $delay -max_paths 1]
    if {[llength $path] != 1} { error "No $delay timing path; constraints need review" }
    if {[get_property SLACK $path] < 0} { error "Negative $delay slack; refusing bitstream" }
}
if {$mode eq "bitstream"} {
    # Vivado's bitstream DRC checks stay enabled. No severity downgrades.
    write_bitstream -force [file join $out rally_as02mc04.bit]
}
puts "Review CDC, unconstrained-path, DRC and timing reports before any programming."

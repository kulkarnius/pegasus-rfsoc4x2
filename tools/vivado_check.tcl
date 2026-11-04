# Toolchain smoke test: board files found, part licensed, trivial synth passes.
#
#     tools\vivado.cmd tools\vivado_check.tcl
#
# Expected (2026-10-27): BOARDS: realdigital.org:rfsoc4x2:part0:1.0, VERSION: 2024.1, SYNTH_OK.
# Vivado echoes each Tcl line as "# <line>", so grep the log for ^SYNTH_OK, not SYNTH_OK.

set_param board.repoPaths [list [file normalize [file dirname [info script]]/../boards]]
puts "BOARDS: [get_board_parts -quiet *rfsoc4x2*]"
puts "VERSION: [version -short]"
puts "PARTS: [get_parts xczu48dr*]"

set chk_v [file join $::env(TEMP) vivado_check_t.v]
set chk_f [open $chk_v w]; puts $chk_f "module t(input wire a, output wire y); assign y = ~a; endmodule"; close $chk_f
read_verilog $chk_v
if {[catch {synth_design -top t -part xczu48dr-ffvg1517-2-e} err]} { puts "SYNTH_FAIL: $err" } else { puts "SYNTH_OK" }

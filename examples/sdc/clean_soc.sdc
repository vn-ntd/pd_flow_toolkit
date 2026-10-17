###############################################################################
# Gold-Standard Clean SDC Constraints
# Design: soc_top
###############################################################################

# 1. Primary System Clocks
create_clock -name sys_clk -period 4.000 -waveform {0.000 2.000} [get_ports i_sys_clk]
create_clock -name pclk -period 10.000 -waveform {0.000 5.000} [get_ports i_pclk]

# 2. Generated Clocks
create_generated_clock -name div_clk \
    -source [get_ports i_sys_clk] \
    -divide_by 2 \
    -master_clock sys_clk \
    [get_pins u_clk_div/clk_out_reg/Q]

# 3. Clock Uncertainty (Setup & Hold Jitter Margin)
set_clock_uncertainty -setup 0.150 [get_clocks {sys_clk div_clk}]
set_clock_uncertainty -hold 0.050 [get_clocks {sys_clk div_clk}]
set_clock_uncertainty -setup 0.250 [get_clocks pclk]
set_clock_uncertainty -hold 0.080 [get_clocks pclk]

# 4. Clock Transition / Slew
set_clock_transition 0.080 [get_clocks sys_clk]
set_clock_transition 0.120 [get_clocks pclk]

# 5. Asynchronous Clock Domain Groups
set_clock_groups -asynchronous \
    -group [get_clocks {sys_clk div_clk}] \
    -group [get_clocks pclk]

# 6. Constrained Input Delays
set_input_delay -clock sys_clk -max 1.200 [get_ports {i_data[*]}]
set_input_delay -clock sys_clk -min 0.200 [get_ports {i_data[*]}]
set_input_delay -clock pclk -max 2.500 [get_ports {i_apb_pwrite i_apb_psel}]

# 7. Constrained Output Delays
set_output_delay -clock sys_clk -max 1.000 [get_ports {o_data[*]}]
set_output_delay -clock sys_clk -min 0.150 [get_ports {o_data[*]}]
set_output_delay -clock pclk -max 2.000 [get_ports {o_apb_pready}]

# 8. Scoped Timing Exceptions
set_false_path -from [get_pins u_rst_sync/rst_sync_reg2/Q]
set_multicycle_path 2 -setup -from [get_pins u_dsp/mult_pipe_reg1/Q] -to [get_pins u_dsp/acc_reg/D]
set_multicycle_path 1 -hold -from [get_pins u_dsp/mult_pipe_reg1/Q] -to [get_pins u_dsp/acc_reg/D]

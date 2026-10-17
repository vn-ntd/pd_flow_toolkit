###############################################################################
# Problematic SDC Constraints (Contains real-world linting bugs)
# Design: buggy_soc_top
###############################################################################

# Bug 1: Clock with negative period
create_clock -name bad_clk -period -5.000 [get_ports i_bad_clk]

# Bug 2: Clock with invalid waveform (rising edge 6.0 >= falling edge 2.0)
create_clock -name inverted_clk -period 10.000 -waveform {6.000 2.000} [get_ports i_inv_clk]

# Bug 3: Generated clock referencing non-existent master_clock 'phantom_pll_clk' and missing -source
create_generated_clock -name pll_div_clk \
    -divide_by 4 \
    -master_clock phantom_pll_clk \
    [get_pins u_pll/clk_out]

# Bug 4: Dangerous broad wildcard false path (will mask real functional failures!)
set_false_path -from * -to *

# Bug 5: Conflicting False Path & Multicycle Path on identical pins
set_false_path -from [get_pins u_mac/reg_a/Q] -to [get_pins u_mac/reg_b/D]
set_multicycle_path 3 -from [get_pins u_mac/reg_a/Q] -to [get_pins u_mac/reg_b/D]

# Bug 6: Extreme input delay (9.5 ns on a 10 ns clock = 95% cycle budget stolen)
set_input_delay -clock inverted_clk -max 9.500 [get_ports i_data_in]

# Bug 7: Deprecated synthesis command
set_dont_use [get_lib_cells slow_lib/DFF_X0_weak]

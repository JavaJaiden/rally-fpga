// SPDX-License-Identifier: MIT
`default_nettype none
// Candidate AS02MC04 wrapper. Confirm the exact device, GPIO wiring and voltage
// before implementation. No PCIe, Ethernet, DMA or USB device logic is present.
module rally_as02mc04 (
    input wire clk_100mhz_p, clk_100mhz_n,
    input wire uart_rx,
    output wire uart_tx,
    output wire led_hb
);
    wire clk_raw, clk;
    IBUFDS clock_input (.I(clk_100mhz_p), .IB(clk_100mhz_n), .O(clk_raw));
    BUFG clock_buffer (.I(clk_raw), .O(clk));

    // Configuration initializes this register; no unverified button polarity.
    reg [15:0] power_on = 16'b0;
    always @(posedge clk) if (!(&power_on)) power_on <= power_on + 1'b1;
    wire rst = !(&power_on);
    reg [25:0] heartbeat;
    always @(posedge clk) begin
        if (rst) heartbeat <= 0;
        else heartbeat <= heartbeat + 1'b1;
    end
    assign led_hb = heartbeat[25];

    wire rx_valid, framing_error, tx_valid, tx_ready;
    wire [7:0] rx_data, tx_data;
    uart_rx #(.CLKS_PER_BIT(868)) rx_receiver (
        .clk(clk), .rst(rst), .rx(uart_rx), .valid(rx_valid),
        .data(rx_data), .framing_error(framing_error)
    );
    rally_framer #(.GAP_CYCLES(1000000)) framer (
        .clk(clk), .rst(rst | framing_error), .rx_valid(rx_valid), .rx_data(rx_data),
        .tx_valid(tx_valid), .tx_ready(tx_ready), .tx_data(tx_data)
    );
    uart_tx #(.CLKS_PER_BIT(868)) tx_transmitter (
        .clk(clk), .rst(rst), .valid(tx_valid), .ready(tx_ready),
        .data(tx_data), .tx(uart_tx)
    );
endmodule
`default_nettype wire

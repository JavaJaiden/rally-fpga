// SPDX-License-Identifier: MIT
`default_nettype none
// 8N1; CLKS_PER_BIT must be >= 8. RX is synchronized, not oversampling-voted.
module uart_rx #(parameter integer CLKS_PER_BIT=868) (
    input wire clk, rst, rx,
    output reg valid,
    output reg [7:0] data,
    output reg framing_error
);
    (* ASYNC_REG = "TRUE" *) reg rx_meta, rx_sync;
    localparam integer W = (CLKS_PER_BIT < 2) ? 1 : $clog2(CLKS_PER_BIT);
    reg [W-1:0] timer;
    reg [2:0] bit_index;
    reg [7:0] shift;
    reg [2:0] state;
    localparam IDLE=0, START=1, DATA=2, STOP=3, RECOVER=4;
    always @(posedge clk) begin
        if (rst) begin rx_meta <= 1; rx_sync <= 1; end
        else begin rx_meta <= rx; rx_sync <= rx_meta; end
    end
    always @(posedge clk) begin
        if (rst) begin
            state <= IDLE; timer <= 0; bit_index <= 0; shift <= 0;
            data <= 0; valid <= 0; framing_error <= 0;
        end else begin
            valid <= 0; framing_error <= 0;
            case (state)
                IDLE: if (!rx_sync) begin timer <= CLKS_PER_BIT/2-1; state <= START; end
                START: if (timer != 0) timer <= timer-1'b1;
                    else if (rx_sync) state <= IDLE;
                    else begin state <= DATA; timer <= CLKS_PER_BIT-1; bit_index <= 0; end
                DATA: if (timer != 0) timer <= timer-1'b1;
                    else begin
                        shift[bit_index] <= rx_sync; timer <= CLKS_PER_BIT-1;
                        if (bit_index == 7) state <= STOP;
                        else bit_index <= bit_index+1'b1;
                    end
                STOP: if (timer != 0) timer <= timer-1'b1;
                    else if (rx_sync) begin data <= shift; valid <= 1; state <= IDLE; end
                    else begin framing_error <= 1; state <= RECOVER; end
                RECOVER: if (rx_sync) state <= IDLE;
                default: state <= IDLE;
            endcase
        end
    end
endmodule

module uart_tx #(parameter integer CLKS_PER_BIT=868) (
    input wire clk, rst,
    input wire valid,
    output wire ready,
    input wire [7:0] data,
    output wire tx
);
    localparam integer W = (CLKS_PER_BIT < 2) ? 1 : $clog2(CLKS_PER_BIT);
    reg [W-1:0] timer;
    reg [3:0] bits_left;
    reg [9:0] shift;
    assign ready = (bits_left == 0);
    assign tx = ready ? 1'b1 : shift[0];
    always @(posedge clk) begin
        if (rst) begin timer <= 0; bits_left <= 0; shift <= 10'h3ff; end
        else if (ready) begin
            if (valid) begin shift <= {1'b1, data, 1'b0}; bits_left <= 10; timer <= CLKS_PER_BIT-1; end
        end else if (timer != 0) timer <= timer-1'b1;
        else begin
            shift <= {1'b1, shift[9:1]}; bits_left <= bits_left-1'b1; timer <= CLKS_PER_BIT-1;
        end
    end
endmodule
`default_nettype wire

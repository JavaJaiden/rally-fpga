// SPDX-License-Identifier: MIT
`default_nettype none
module rally_control (
    input wire [15:0] ball, paddle,
    input wire [7:0] flags,
    output reg signed [7:0] move,
    output reg [7:0] status
);
    reg signed [16:0] error;
    always @* begin
        error = $signed({1'b0, ball}) - $signed({1'b0, paddle});
        status = {5'b0, (|flags[7:1]), ((ball > 16'd1023) || (paddle > 16'd1023)), !flags[0]};
        move = 0;
        if (status == 0) begin
            if (error > 17'sd8) move = 8'sd8;
            else if (error < -17'sd8) move = -8'sd8;
            else if ((error > 17'sd2) || (error < -17'sd2)) move = error[7:0];
        end
    end
endmodule

// Single outstanding request. RX bytes during a pending reply are discarded.
// A sliding window resynchronizes after noise; a gap clears partial frames.
module rally_framer #(
    parameter integer GAP_CYCLES = 1000000
) (
    input wire clk, rst,
    input wire rx_valid,
    input wire [7:0] rx_data,
    output wire tx_valid,
    input wire tx_ready,
    output wire [7:0] tx_data
);
    reg [79:0] window;
    wire [79:0] candidate = {window[71:0], rx_data};
    reg [3:0] count;
    localparam integer GW = (GAP_CYCLES < 2) ? 1 : $clog2(GAP_CYCLES + 1);
    reg [GW-1:0] gap;
    reg busy;
    reg [2:0] left;
    reg [55:0] reply;
    wire signed [7:0] move;
    wire [7:0] status;
    wire [47:0] body = {8'h5a, 8'h01, candidate[63:56], candidate[55:48], move, status};
    function automatic [7:0] crc_byte(input [7:0] crc, input [7:0] value);
        reg [7:0] c; integer k;
        begin
            c = crc ^ value;
            for (k=0; k<8; k=k+1) c = c[7] ? ((c << 1) ^ 8'h07) : (c << 1);
            crc_byte = c;
        end
    endfunction
    reg [7:0] request_crc, reply_crc;
    integer i;
    always @* begin
        request_crc = 0;
        reply_crc = 0;
        for (i=0; i<9; i=i+1) request_crc = crc_byte(request_crc, candidate[79-i*8 -: 8]);
        for (i=0; i<6; i=i+1) reply_crc = crc_byte(reply_crc, body[47-i*8 -: 8]);
    end
    rally_control control (
        .ball({candidate[39:32], candidate[47:40]}),
        .paddle({candidate[23:16], candidate[31:24]}),
        .flags(candidate[15:8]), .move(move), .status(status)
    );
    assign tx_valid = busy;
    assign tx_data = reply[55:48];
    always @(posedge clk) begin
        if (rst) begin
            window <= 0; count <= 0; gap <= 0;
            busy <= 0; left <= 0; reply <= 0;
        end else begin
            if (busy) begin
                if (tx_ready) begin
                    if (left == 1) begin busy <= 0; left <= 0; end
                    else begin reply <= {reply[47:0], 8'b0}; left <= left - 1'b1; end
                end
            end else if (rx_valid) begin
                window <= candidate;
                gap <= 0;
                if (count < 10) count <= count + 1'b1;
                if ((count >= 9) && (candidate[79:64] == 16'ha501) &&
                    (request_crc == candidate[7:0])) begin
                    reply <= {body, reply_crc};
                    busy <= 1; left <= 7; count <= 0; window <= 0;
                end
            end else if (gap >= GAP_CYCLES-1) begin
                count <= 0; window <= 0;
            end else gap <= gap + 1'b1;
        end
    end
endmodule
`default_nettype wire

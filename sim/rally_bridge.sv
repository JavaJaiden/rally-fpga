// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module rally_bridge;
    reg clk=0, rst=1, rx_valid=0, tx_ready=0;
    reg [7:0] rx_data=0;
    wire tx_valid;
    wire [7:0] tx_data;
    always #5 clk=~clk;
    rally_framer #(.GAP_CYCLES(64)) dut(.*);
    reg [319:0] frame;
    reg [55:0] result;
    reg [7:0] held;
    integer rc, n, i, cycles, received;
    initial begin
        repeat (4) @(negedge clk);
        rst=0;
        forever begin
            rc=$fscanf(32'h80000000, "%d %h", n, frame);
            if (rc != 2) $finish;
            if (n < 1 || n > 40) $fatal(1, "invalid input length");
            tx_ready=0;
            for (i=n-1; i>=0; i=i-1) begin
                @(negedge clk); rx_data=frame[i*8 +: 8]; rx_valid=1;
                @(negedge clk); rx_valid=0;
            end
            result=0; received=0; cycles=0;
            while ((received < 7) && (cycles < 256)) begin
                // Deliberately stall every third cycle; validate stable data.
                @(negedge clk); tx_ready=(cycles%3 != 0); held=tx_data;
                @(posedge clk);
                if (tx_valid && tx_ready) begin result={result[47:0], tx_data}; received=received+1; end
                #1;
                if (tx_valid && !tx_ready && tx_data !== held) $fatal(1, "stalled reply changed");
                cycles=cycles+1;
            end
            @(negedge clk); tx_ready=0;
            if (received == 7) $display("R %014h", result);
            else $display("TIMEOUT");
            $fflush();
        end
    end
    initial begin #1000000000; $fatal(1, "simulation watchdog"); end
endmodule

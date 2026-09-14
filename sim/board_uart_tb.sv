// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
// Behavioral clock buffers permit testing the actual board wrapper wiring.
// These models do not validate differential electrical behavior or device timing.
module IBUFDS(input I,IB,output O); assign O=I; endmodule
module BUFG(input I,output O); assign O=I; endmodule
module board_uart_tb;
localparam CPB=868, N=__COUNT__;
reg clk_100mhz_p=0,uart_rx=1;
wire clk_100mhz_n=~clk_100mhz_p;
wire uart_tx,led_hb;
rally_as02mc04 dut(.*);
always #5 clk_100mhz_p=~clk_100mhz_p;
reg [7:0] expected [0:N*7-1];
reg [79:0] packet;
reg [7:0] value;
integer fd,rc,i,j,received=0,sent=0,bit_index;
// Independent bit sampler, not the production UART RX used in a loopback.
initial forever begin
 @(negedge uart_tx);
 repeat(CPB/2) @(posedge clk_100mhz_p);
 if(uart_tx!==0) $fatal(1,"invalid reply start bit");
 for(bit_index=0;bit_index<8;bit_index=bit_index+1) begin
  repeat(CPB) @(posedge clk_100mhz_p); value[bit_index]=uart_tx;
 end
 repeat(CPB) @(posedge clk_100mhz_p);
 if(uart_tx!==1) $fatal(1,"invalid reply stop bit");
 if(received>=N*7 || value!==expected[received])
  $fatal(1,"UART reply byte %0d got %h expected %h",received,value,expected[received]);
 received=received+1;
end
task send_byte(input [7:0] data);
 integer b;
 begin
  @(negedge clk_100mhz_p); uart_rx=0;
  repeat(CPB) @(negedge clk_100mhz_p);
  for(b=0;b<8;b=b+1) begin
   uart_rx=data[b]; repeat(CPB) @(negedge clk_100mhz_p);
  end
  uart_rx=1; repeat(CPB) @(negedge clk_100mhz_p);
 end
endtask
initial begin
 $readmemh("board-expected.txt",expected);
 // Actual power-on reset counter, no test override of wrapper parameters.
 repeat(66000) @(negedge clk_100mhz_p);
 // Invalid stop then recovery, followed by a partial packet and gap expiry.
 uart_rx=0; repeat(CPB*12) @(negedge clk_100mhz_p);
 uart_rx=1; repeat(CPB*3) @(negedge clk_100mhz_p);
 send_byte(8'ha5); send_byte(1); send_byte(8'hff);
 repeat(1000100) @(negedge clk_100mhz_p);
 if(received) $fatal(1,"partial request emitted a reply");
 fd=$fopen("board-input.txt","r"); if(!fd) $fatal(1,"missing requests");
 while(!$feof(fd)) begin
  rc=$fscanf(fd,"%h",packet);
  if(rc==1) begin
   // Bad CRC must not produce a reply; valid retransmission must recover.
   if(sent%7==0) begin
    for(i=9;i>=0;i=i-1) send_byte(packet[i*8 +:8] ^ (i==0 ? 8'h01 : 8'h00));
    repeat(CPB*12) @(negedge clk_100mhz_p);
    if(received!=sent*7) $fatal(1,"bad CRC produced output");
   end
   for(i=9;i>=0;i=i-1) send_byte(packet[i*8 +:8]);
   sent=sent+1;
   while(received!=sent*7) @(negedge clk_100mhz_p);
   repeat(CPB*2) @(negedge clk_100mhz_p);
  end
 end
 // Drain beyond one complete UART frame to catch spurious trailing replies.
 repeat(CPB*12) @(negedge clk_100mhz_p);
 if(sent!=N || received!=N*7) $fatal(1,"missing board transactions");
 $display("PASS board-wrapper UART: %0d requests, default 868-clock divisor, CRC rejection, framing and partial-gap recovery",sent);
 $finish;
end
initial begin #1000000000; $fatal(1,"board UART watchdog"); end
endmodule

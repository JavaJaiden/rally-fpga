"""Compile this project's RTL and compare it with its Python reference.

Missing tools are an error, not a passing or skipped HDL result.
"""
from __future__ import annotations
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rally as r
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out' / 'rtl'

def simulate(name: str, text: str, sources: list[str]) -> str:
    tb=OUT/f'{name}.sv'; tb.write_text(text,encoding='utf-8')
    subprocess.run(['iverilog','-g2012','-s',name,'-o',str(OUT/name),str(tb),
                    *[str(ROOT/s) for s in sources]],check=True,timeout=60)
    run=subprocess.run(['vvp',str(OUT/name)],cwd=OUT,text=True,capture_output=True,timeout=90)
    (OUT/f'{name}.log').write_text(run.stdout+run.stderr,encoding='utf-8')
    if run.returncode or 'PASS' not in run.stdout:
        raise RuntimeError(f'{name}: {run.stdout}\n{run.stderr}')
    print(run.stdout.strip())
    return run.stdout

def rally_check() -> int:
    rng=random.Random(52); backend=r.RTLBackend(); count=0
    try:
        fixtures=[(0,0,1023,1),(65535,1023,0,1),(7,500,498,1),(8,500,497,1),
                  (9,65535,0,1),(10,500,0,0),(11,500,0,3)]
        fixtures += [(rng.randrange(65536),rng.randrange(1100),rng.randrange(1100),rng.randrange(4)) for _ in range(1000)]
        for seq,ball,paddle,flags in fixtures:
            wire=r.request(seq,ball,paddle,flags)
            actual=r.decode_reply(backend.exchange(wire),seq)
            assert (actual.move,actual.status)==r.decision(ball,paddle,flags), (seq,actual)
            count+=1
        wire=r.request(123,900,200)
        assert backend.exchange(b'\x00\xff\x5a\xa5\x03'+wire)==r.ModelBackend().exchange(wire)
        count+=1
        for bit in range(80):
            bad=bytearray(wire); bad[bit//8]^=1<<(bit%8)
            try: backend.exchange(bytes(bad))
            except r.ProtocolError: pass
            else: raise AssertionError(f'accepted corrupt bit {bit}')
            assert backend.exchange(wire)==r.ModelBackend().exchange(wire)
            count+=2
        try: backend.exchange(wire[:5])
        except r.ProtocolError: pass
        else: raise AssertionError('accepted partial request')
        assert backend.exchange(wire)==r.ModelBackend().exchange(wire)
        count+=2
    finally: backend.close()
    print(f'PASS rally: {count} transactions, corruption, recovery and reply stalls')
    return count

def uart_check() -> int:
    simulate('uart_tb',r'''
`timescale 1ns/1ps
module uart_tb;
reg clk=0,rst=1,valid=0;
reg [7:0] data=0;
wire ready,tx,rx_valid,framing_error;
wire [7:0] rx_data;
reg manual=0,manual_rx=1;
wire rx=manual ? manual_rx : tx;
uart_tx #(.CLKS_PER_BIT(8)) transmitter(.*);
uart_rx #(.CLKS_PER_BIT(8)) receiver(.clk(clk),.rst(rst),.rx(rx),.valid(rx_valid),.data(rx_data),.framing_error(framing_error));
always #5 clk=~clk;
integer received=0,errors=0,i,j;
always @(posedge clk) begin
 if(!rst && rx_valid) begin
  if(rx_data !== received[7:0]) $fatal(1,"UART mismatch %0d got %0d",received,rx_data);
  received=received+1;
 end
 if(!rst && framing_error) errors=errors+1;
end
initial begin
 repeat(4) @(negedge clk); rst=0;
 for(i=0;i<256;i=i+1) begin
  @(negedge clk); while(!ready) @(negedge clk);
  valid=1; data=i[7:0]; @(negedge clk); valid=0;
  while(!ready) @(negedge clk);
 end
 repeat(20) @(negedge clk);
 if(received!=256 || errors!=0) $fatal(1,"UART counts");
 manual=1; manual_rx=0;
 repeat(120) @(negedge clk);
 manual_rx=1; repeat(24) @(negedge clk);
 if(errors!=1 || received!=256) $fatal(1,"framing error recovery");
 $display("PASS UART: 256 bytes and invalid-stop rejection"); $finish;
end
initial begin #10000000; $fatal(1,"timeout"); end
endmodule
''',['rtl/uart.sv'])
    return 257

def main() -> None:
    for tool in ('iverilog', 'vvp'):
        if not shutil.which(tool):
            raise SystemExit(f'{tool} is required; RTL verification NOT RUN')
    OUT.mkdir(parents=True, exist_ok=True)
    counts = {'rally_transactions': rally_check(), 'uart_cases': uart_check()}
    result = {'status': 'PASS', 'engine': 'Icarus Verilog',
              'counts': counts, 'hardware_tested': False}
    (OUT / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))

if __name__ == '__main__':
    main()

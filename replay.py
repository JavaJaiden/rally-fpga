"""Export an actual Rally JSONL trace to a self-contained, clearly labeled replay."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path


def export(trace: Path, output: Path) -> None:
    raw = trace.read_bytes()
    records = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line.strip()]
    if not records:
        raise ValueError('trace is empty')
    labels = {r['backend'] for r in records}
    if len(labels) != 1:
        raise ValueError('mixed backends must not be presented as one experiment')
    label = labels.pop()
    rows = []
    for r in records:
        values = [r[k] for k in ('frame', 'x', 'y', 'paddle', 'move', 'hits', 'misses')]
        if any(not isinstance(v, int) for v in values):
            raise ValueError('trace coordinates and counters must be integers')
        rows.append(values + [bool(r['error']), r['status']])
    data = json.dumps(rows, separators=(',', ':')).replace('<', '\\u003c')
    digest = hashlib.sha256(raw).hexdigest()
    page = '''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rally experiment replay</title>
<style>
body{font:16px/1.5 system-ui,sans-serif;max-width:1000px;margin:36px auto;padding:0 24px;color:#181818;background:#fff}
h1{font-size:34px;margin-bottom:8px}h2{font-size:22px;margin-top:32px}
.notice{border-top:2px solid #222;border-bottom:1px solid #bbb;padding:16px 0;margin:24px 0}
canvas{display:block;width:100%;max-width:720px;height:auto;background:#111}
.controls{display:flex;gap:14px;align-items:center;margin:20px 0;flex-wrap:wrap}
button,select{font:inherit;padding:5px 14px;background:#fff;border:1px solid #777}
input{flex:1;min-width:180px}pre{white-space:pre-wrap;background:#f3f3f3;padding:16px}
small{overflow-wrap:anywhere;color:#555}table{border-collapse:collapse;width:100%;max-width:720px}
td,th{text-align:left;padding:8px;border-bottom:1px solid #ddd}
</style>
<h1>Rally experiment replay</h1>
<p>Recorded game state and bounded controller responses, with deliberately injected frame corruption.</p>
<div class="notice"><strong>__LABEL__</strong><br>This page replays a retained trace. It does not execute FPGA hardware or a live game.</div>
<canvas id="game" width="720" height="480" aria-label="Recorded single-paddle Pong game"></canvas>
<div class="controls"><button id="play">Pause</button><input id="frame" aria-label="Frame" type="range" min="0" max="__MAX__" value="0">
<select id="speed" aria-label="Replay speed"><option value="1">1x</option><option value="2">2x</option><option value="4">4x</option></select></div>
<table><tr><th>Frame</th><th>Movement</th><th>Hits / misses</th><th>Frame validation</th></tr>
<tr><td id="n"></td><td id="move"></td><td id="score"></td><td id="fault"></td></tr></table>
<h2>Experiment boundary</h2>
<pre>Custom game -> state + sequence + CRC -> controller
Custom game <- bounded move + status  <- controller
Invalid or missing reply -> zero movement</pre>
<p>The model and hardware use the same intended protocol, but a model pass is not an RTL or board pass. Displayed playback speed is not a latency measurement.</p>
<small>Trace: __NAME__<br>SHA-256: __SHA__</small>
<script>
'use strict';
const rows=__DATA__, canvas=document.getElementById('game'), c=canvas.getContext('2d');
const slider=document.getElementById('frame'), button=document.getElementById('play');
let index=0,playing=true,last=0;
function draw(){const r=rows[index];c.fillStyle='#111';c.fillRect(0,0,720,480);
 c.fillStyle='#fff';c.fillRect(12,r[3]*480/1024-45,10,90);
 c.beginPath();c.arc(r[1]*720/1024,r[2]*480/1024,5,0,2*Math.PI);c.fill();
 slider.value=String(index);document.getElementById('n').textContent=r[0];
 document.getElementById('move').textContent=r[4];document.getElementById('score').textContent=r[5]+' / '+r[6];
 document.getElementById('fault').textContent=r[7]?'Rejected; movement suppressed':(r[8]?'Control disabled or invalid':'Accepted');}
button.onclick=()=>{playing=!playing;button.textContent=playing?'Pause':'Play';};
slider.oninput=()=>{index=Number(slider.value);draw();};
function tick(now){if(playing&&now-last>=1000/(60*Number(document.getElementById('speed').value))){
 if(index+1<rows.length){index++;draw();}else{playing=false;button.textContent='Replay';}last=now;}
 requestAnimationFrame(tick);}
button.addEventListener('click',()=>{if(index===rows.length-1&&playing){index=0;draw();}});
draw();requestAnimationFrame(tick);
</script></html>'''
    for key, value in {'LABEL': html.escape(label), 'MAX': str(len(rows)-1),
                       'NAME': html.escape(trace.name), 'SHA': digest, 'DATA': data}.items():
        page = page.replace('__' + key + '__', value)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding='utf-8')
    print(f'Wrote {len(rows)} recorded frames to {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace', type=Path, default=Path('out/rally.jsonl'))
    parser.add_argument('--output', type=Path, default=Path('out/rally-replay.html'))
    args = parser.parse_args()
    export(args.trace, args.output)
